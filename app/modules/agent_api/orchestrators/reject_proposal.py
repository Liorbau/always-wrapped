from app.errors import validation_error
from app.modules.agent_api import events, proposals


def execute(proposal_id, reason=None):
    if not proposal_id:
        raise validation_error("Missing proposal_id.")
    proposals.reject(proposal_id, reason)
    events.record("user", f"proposal rejected ({(reason or 'no reason')[:40]})")
    return {"type": "rejected"}
