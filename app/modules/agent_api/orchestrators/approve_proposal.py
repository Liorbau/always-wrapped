"""The HITL gate. Every Spotify account write enters through here."""

from app.errors import validation_error
from app.modules.agent_api import proposals


def execute(proposal_id):
    if not proposal_id:
        raise validation_error("Missing proposal_id.")
    return {"type": "pushed", **proposals.push(proposal_id)}
