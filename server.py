"""Process entry point — Render starts the app with `python server.py`.

Bootstrap only: build the Flask app, create the schema, and spawn the
background workers. All behavior lives under app/, agents/, and pipelines/.
"""

import os
import threading

from app import create_app
from app.modules.agent_api.timer_runner import start_thread as start_timer_thread
from pipelines.collector import start_collector_service
from core.logging import configure_logger
from db.schema import create_database

logger = configure_logger(__name__)

app = create_app()


def main():
    logger.info("Initializing database...")
    create_database()

    threading.Thread(target=start_collector_service, daemon=True).start()
    start_timer_thread()

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


if __name__ == "__main__":
    main()
