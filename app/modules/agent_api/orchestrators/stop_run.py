from app.modules.agent_api import runs


def execute(run_id):
    return runs.stop(run_id)
