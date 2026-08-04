"""One conversation turn: run the harness, then pack, top up, verify, deliver."""

from agents.dj import packer, supply, verifier
from agents.dj.constraints import (
    DEFAULT_DURATION_MIN,
    MAX_COST_USD,
    MAX_REPAIR_ROUNDS,
    MAX_STEPS,
)
from agents.dj.decision_trace import attach_decision_trace
from agents.dj.prompt import DJ_SYSTEM_PROMPT
from agents.harness import AgentHarness
from agents.schemas import parse_playlist
from agents.tools import TOOL_REGISTRY, TOOL_SCHEMAS
from core.logging import configure_logger

logger = configure_logger(__name__)

SUPPLY_MAX_STEPS = 8
SALVAGE_NOTE = (
    "(I hit my step budget mid-build — this is my best verified set; "
    "ask me to extend or adjust it.)"
)


def build_dj(llm=None, max_cost_usd=MAX_COST_USD):
    """Configured harness for the DJ agent, seasoned with learned preferences."""
    # lazy: avoids an import cycle with evaluator → tools → …
    from agents.evaluator import format_biases_for_dj, top_biases

    biases = top_biases()
    dj = AgentHarness(
        llm=llm,
        tool_schemas=TOOL_SCHEMAS,
        tool_registry=TOOL_REGISTRY,
        system_prompt=DJ_SYSTEM_PROMPT + format_biases_for_dj(biases),
        max_cost_usd=max_cost_usd,
    )
    # Same snapshot the prompt saw — decision_trace must not re-read later.
    dj.bias_snapshot = biases
    return dj


def run_dj_turn(dj, message, max_steps=MAX_STEPS):
    """Returns {'response', 'playlist', 'violations', 'status', ...}.

    'playlist' is None when the turn ended without a verified proposal — a
    clarifying question, caps hit, or a verification failure. Never push then.
    """
    response = dj.run(message, max_steps=max_steps)
    if _asked_a_question(dj):
        return _turn_result(dj, response, None, None, [])

    pool_acc = []
    playlist, packed, gap, response = _gather_pool(dj, pool_acc, response)
    playlist, packed, gap = _top_up_from_history(playlist, packed, gap)

    note = None
    if dj.metadata["status"] != "satisfied":
        packed, gap, note, response = _salvage(dj, playlist, pool_acc, response)

    note = _with_shortfall_note(note, packed, gap)
    packed, violations = _repair_if_noncompliant(packed)
    return _turn_result(dj, response, packed, note, violations)


def request_playlist(request, llm=None, max_steps=MAX_STEPS):
    """One-shot convenience: fresh DJ, single turn (scripts/tests/smoke)."""
    return run_dj_turn(build_dj(llm=llm), request, max_steps=max_steps)


def _asked_a_question(dj):
    """Satisfied but deliberately no playlist — deliver the question as-is."""
    return (dj.metadata["status"] == "satisfied"
            and parse_playlist((dj.last_parsed or {}).get("playlist")) is None)


def _gather_pool(dj, pool_acc, response):
    """The packing loop. The only thing we ask the model to fix is SUPPLY (more
    candidates), never math — and pools merge, so a reply needs only new entries."""
    playlist, packed, gap = None, None, None
    for round_no in range(MAX_REPAIR_ROUNDS + 1):
        if dj.metadata["status"] != "satisfied":
            break
        parsed = parse_playlist((dj.last_parsed or {}).get("playlist"))
        if parsed:
            playlist = packer.merge_pool(playlist, parsed, pool_acc)
        packed, gap = packer.pack(playlist)
        if packed is not None and not gap:
            break
        if round_no == MAX_REPAIR_ROUNDS:
            break
        logger.warning("Packer short by %s min — supply round %d", gap, round_no + 1)
        response = dj.run(
            supply.supply_message(playlist, packed, gap or 0, dj=dj),
            max_steps=SUPPLY_MAX_STEPS,
        )
    return playlist, packed, gap, response


def _top_up_from_history(playlist, packed, gap):
    if not gap or not playlist or playlist.get("familiarity_constraint") == "mostly_never":
        return playlist, packed, gap
    playlist = supply.reserve_topup(playlist, packed)
    packed, gap = packer.pack(playlist)
    return playlist, packed, gap


def _salvage(dj, playlist, pool_acc, response):
    """The run died on a budget — pack whatever draft pool exists."""
    draft = parse_playlist((dj.last_parsed or {}).get("playlist"))
    pool = packer.merge_pool(playlist, draft, pool_acc) if draft else playlist
    packed, gap = packer.pack(pool)
    if packed:
        logger.info("DJ delivered salvaged pack (status=%s)", dj.metadata["status"])
        return packed, gap, SALVAGE_NOTE, response

    logger.warning("DJ proposal withheld (status=%s)", dj.metadata["status"])
    return None, gap, None, supply.withhold_explanation(response, [], dj.metadata["status"])


def _with_shortfall_note(note, packed, gap):
    if not packed or not gap:
        return note
    target = packed.get("target_duration_min") or DEFAULT_DURATION_MIN
    shortfall = (
        f"Heads up: this came out at ~{packed['total_duration_min']:.0f} min "
        f"vs the ~{target:.0f} min you asked for — it's every track that "
        "fit the request. Approve it, or ask me to extend it."
    )
    return (note + " " + shortfall) if note else shortfall


def _repair_if_noncompliant(packed):
    """The packer is compliant by construction, so a non-duration violation here
    is a packer bug — repair it rather than shipping something broken."""
    if not packed:
        return packed, []
    violations = [v for v in verifier.verify_playlist(packed)
                  if not v.startswith("real total duration")]
    if violations:
        logger.error("PACKER BUG — packed playlist failed verify: %s", violations)
        packed, _ = verifier.sanitize(packed)
    return packed, violations


def _turn_result(dj, response, playlist, note, violations):
    if playlist is not None:
        playlist = attach_decision_trace(
            playlist,
            biases=getattr(dj, "bias_snapshot", None) or [],
            violations=violations,
        )
    return {
        "response": response,
        "playlist": playlist,
        "note": note,
        "violations": violations,
        "status": dj.metadata["status"],
        "cost_usd": dj.metadata["cost_usd"],
        "steps": dj.metadata["step_count"],
    }
