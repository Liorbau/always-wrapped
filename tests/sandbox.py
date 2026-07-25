"""Point the suite at a throwaway database. Import before any app module.

``db/connection.py`` calls ``load_dotenv()``, and python-dotenv resolves the
repo ``.env`` by walking up from wherever the process started. Without this,
a plain ``python tests/test_dj.py`` connects to whatever DATABASE_URL names —
in practice the production database — and the suites that record agent run
costs write straight into the live spend ledger.

Order matters: ``SQLITE_PATH`` is read once, at ``db.connection`` import time.
"""

import atexit
import os
import shutil
import tempfile

_TEMP_DIR = tempfile.mkdtemp(prefix="aw-tests-")

# An empty value still counts as present, so load_dotenv() leaves it alone.
os.environ["DATABASE_URL"] = ""
os.environ["SQLITE_PATH"] = os.path.join(_TEMP_DIR, "test.db")

atexit.register(shutil.rmtree, _TEMP_DIR, True)
