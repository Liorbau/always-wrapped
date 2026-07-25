"""Provider-seam tests: env-driven selection over LiteLLM, no network.

Runnable directly:  ./venv/bin/python tests/test_llm.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import sandbox  # noqa: F401  — must precede every app import

from agents.llm import get_client, LiteLLMClient, cost_usd


def _with_env(env, fn):
    saved = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        return fn()
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.update({k: v})


def test_provider_selection_is_env_only():
    c = _with_env({"LLM_PROVIDER": "openai"}, get_client)
    assert type(c) is LiteLLMClient and c.model == "gpt-4o"

    c = _with_env({"LLM_PROVIDER": "google"}, get_client)
    assert c.model == "gemini/gemini-2.5-flash"   # litellm routing prefix

    c = _with_env({"LLM_PROVIDER": "anthropic"}, get_client)
    assert c.model == "anthropic/claude-sonnet-5"

    c = _with_env({"LLM_PROVIDER": "openai", "LLM_MODEL": "gpt-4o-mini"}, get_client)
    assert c.model == "gpt-4o-mini"


def test_unknown_provider_rejected():
    try:
        _with_env({"LLM_PROVIDER": "grok"}, get_client)
        raise AssertionError("unknown provider accepted")
    except ValueError as exc:
        assert "grok" in str(exc)


def test_cost_from_maintained_tables():
    assert cost_usd("gpt-4o", 1_000_000, 0) == 2.50
    # the old hand-rolled PRICING reported $0 for non-OpenAI models — fixed
    assert cost_usd("gemini/gemini-2.5-flash", 1000, 1000) > 0
    assert cost_usd("not-a-real-model-xyz", 1000, 1000) == 0.0


if __name__ == "__main__":
    test_provider_selection_is_env_only()
    test_unknown_provider_rejected()
    test_cost_from_maintained_tables()
    print("OK: all llm tests passed")
