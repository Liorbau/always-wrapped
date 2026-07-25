"""Proof that the suite cannot reach a real database.

Runnable directly:  ./venv/bin/python tests/test_sandbox.py
"""

import glob
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import sandbox  # noqa: F401  — must precede every app import

from agents.store import run_costs
from db.connection import get_db_connection

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))


def test_dotenv_cannot_reinstate_the_real_database():
    """Importing db.connection runs load_dotenv(); the empty value must survive."""
    assert os.environ["DATABASE_URL"] == "", "the repo .env leaked back in"


def test_connection_lands_on_a_throwaway_file():
    conn, driver = get_db_connection()
    try:
        assert driver == "sqlite"
    finally:
        conn.close()
    path = os.path.abspath(os.environ["SQLITE_PATH"])
    assert path.startswith(tempfile.gettempdir())
    assert not path.startswith(os.path.dirname(TESTS_DIR) + os.sep), "wrote inside the repo"


def test_recorded_costs_stay_in_the_sandbox():
    """The spend ledger is the table this guard exists to protect."""
    run_costs.record("run-sandbox-probe", 0.0042, day="19700101")
    assert run_costs.spent_on("19700101") == 0.0042
    assert os.path.exists(os.environ["SQLITE_PATH"])


def test_every_test_module_imports_the_sandbox():
    """A new suite that forgets the import would silently reopen the hole."""
    missing = []
    for path in sorted(glob.glob(os.path.join(TESTS_DIR, "test_*.py"))):
        with open(path, encoding="utf-8") as handle:
            if "from tests import sandbox" not in handle.read():
                missing.append(os.path.basename(path))
    assert not missing, "test modules missing the sandbox import: %s" % missing


if __name__ == "__main__":
    test_dotenv_cannot_reinstate_the_real_database()
    test_connection_lands_on_a_throwaway_file()
    test_recorded_costs_stay_in_the_sandbox()
    test_every_test_module_imports_the_sandbox()
    print("OK: all sandbox tests passed")
