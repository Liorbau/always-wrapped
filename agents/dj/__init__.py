"""The DJ agent: natural-language request -> verified playlist proposal.

The DJ runs the shared harness with the guarded query_history tool and a
constraint-satisfaction prompt: parse the request into constraints, ground
every pick in the user's real history, VERIFY the constraints with SQL, and
revise until they hold. It only ever *proposes* — pushing to Spotify is a
separate human-approved action (HITL), never done by this agent.

    prompt      the contract shown to the model
    packer      deterministic assembly from the model's candidate pool
    verifier    independent constraint check + repair
    supply      what to do when the pool falls short
    turn        the loop that ties them together
"""

from agents.dj.constraints import (
    DEFAULT_DURATION_MIN,
    MAX_COST_USD,
    MAX_PER_ARTIST,
    MAX_PLAYED_FRAC,
    MAX_STEPS,
)
from agents.dj.prompt import DJ_SYSTEM_PROMPT
from agents.dj.turn import build_dj, request_playlist, run_dj_turn
from agents.dj.verifier import verify_playlist

__all__ = [
    "DJ_SYSTEM_PROMPT",
    "DEFAULT_DURATION_MIN",
    "MAX_COST_USD",
    "MAX_PER_ARTIST",
    "MAX_PLAYED_FRAC",
    "MAX_STEPS",
    "build_dj",
    "request_playlist",
    "run_dj_turn",
    "verify_playlist",
]
