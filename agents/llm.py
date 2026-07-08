"""Provider-agnostic LLM seam, backed by LiteLLM.

Agent code never touches a vendor SDK — it calls
``get_client().complete(system, messages, tools)`` and gets one normalized
shape. Providers/models swap via env only:

    LLM_PROVIDER=openai|anthropic|google   (default: openai)
    LLM_MODEL=gpt-4o                       (default per provider below)
    OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY in .env

This file used to hold three hand-rolled vendor adapters (~130 lines); the
seam's interface let us swap the implementation to LiteLLM in one file with
zero changes to any agent — which is what the seam was for. LiteLLM also
brings retries, maintained pricing tables (accurate cost for every model),
and provider-mapped JSON response mode.

Normalized response dict:
    {"content": str|None,
     "tool_calls": [{"id", "name", "arguments": dict}, ...],
     "usage": {"input": int, "output": int}}

Canonical message format (what the harness stores) is OpenAI-style with dict
tool arguments; tool schemas are OpenAI function format.
"""

import json
import os

import litellm
from dotenv import load_dotenv

from logging_config import configure_logger

load_dotenv()
logger = configure_logger(__name__)

litellm.drop_params = True     # a provider missing a param ignores it, never errors
litellm.suppress_debug_info = True
if not os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_KEY"):
    os.environ["OPENAI_API_KEY"] = os.environ["OPENAI_KEY"]  # legacy env name
if not os.getenv("GEMINI_API_KEY") and os.getenv("GOOGLE_API_KEY"):
    os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_API_KEY"]  # litellm reads GEMINI_

NUM_RETRIES = 2  # transient provider errors no longer kill an agent run

PROVIDERS = {"openai": "openai", "anthropic": "anthropic", "google": "gemini"}
DEFAULT_MODELS = {
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-5",
    "google": "gemini-2.5-flash",
}


def _wire(messages):
    """Canonical messages (dict tool arguments) -> OpenAI wire format."""
    out = []
    for m in messages:
        if m["role"] == "assistant" and m.get("tool_calls"):
            out.append({
                "role": "assistant",
                "content": m.get("content"),
                "tool_calls": [
                    {"id": tc["id"], "type": "function",
                     "function": {"name": tc["name"],
                                  "arguments": json.dumps(tc["arguments"])}}
                    for tc in m["tool_calls"]
                ],
            })
        else:
            out.append({k: m[k] for k in ("role", "content", "tool_call_id") if k in m})
    return out


class LiteLLMClient:
    """One client for every provider; vendor differences live in litellm."""

    def __init__(self, model, provider="openai"):
        self.model = model
        self.provider = provider

    def complete(self, system, messages, tools=None):
        kwargs = {}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
            # JSON response mode + function-calling is OpenAI-only; Gemini 400s
            # on the combination, so only force it where it's known safe.
            if self.provider == "openai":
                kwargs["response_format"] = {"type": "json_object"}
        resp = litellm.completion(
            model=self.model,
            messages=[{"role": "system", "content": system}] + _wire(messages),
            num_retries=NUM_RETRIES,
            **kwargs,
        )
        msg = resp.choices[0].message
        return {
            "content": msg.content,
            "tool_calls": [
                {"id": tc.id, "name": tc.function.name,
                 "arguments": json.loads(tc.function.arguments)}
                for tc in (msg.tool_calls or [])
            ],
            "usage": {"input": resp.usage.prompt_tokens,
                      "output": resp.usage.completion_tokens},
        }


def get_client(model=None, provider=None):
    """Build the LLM client; provider/model override env (LLM_PROVIDER/LLM_MODEL)."""
    provider = (provider or os.getenv("LLM_PROVIDER", "openai")).lower()
    if provider not in PROVIDERS:
        raise ValueError(
            f"Unknown LLM_PROVIDER {provider!r}; expected one of {sorted(PROVIDERS)}"
        )
    model = model or os.getenv("LLM_MODEL") or DEFAULT_MODELS[provider]
    if "/" not in model and provider != "openai":
        model = f"{PROVIDERS[provider]}/{model}"  # litellm provider routing prefix
    logger.info("LLM client: provider=%s model=%s", provider, model)
    return LiteLLMClient(model, provider=provider)


def cost_usd(model, input_tokens, output_tokens):
    """Cost from litellm's maintained pricing tables; 0.0 for unknown models."""
    try:
        i, o = litellm.cost_per_token(model=model, prompt_tokens=input_tokens,
                                      completion_tokens=output_tokens)
        return i + o
    except Exception:
        return 0.0
