from app.modules.agent_api import runs


def execute(run_id):
    return runs.status(run_id)
