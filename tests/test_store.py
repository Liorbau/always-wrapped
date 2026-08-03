"""Durable agent state: the spend ledger and the HITL decision log.

These used to be files under agent-runs/, which a deploy erased. The point of
these tests is that the budget cannot be reset and the Evaluator's signal
survives.

Runnable directly:  ./venv/bin/python tests/test_store.py
"""

import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import sandbox  # noqa: F401  — must precede every app import

from agents import ledger
from agents.store import hitl, run_costs


def _sqlite_at(path):
    def connect(readonly=False):
        return sqlite3.connect(path), "sqlite"
    return connect


class temp_db:
    """Point every store module at one throwaway SQLite file."""

    def __init__(self, modules=(run_costs, hitl)):
        self.modules = modules

    def __enter__(self):
        self._dir = tempfile.TemporaryDirectory()
        connect = _sqlite_at(os.path.join(self._dir.name, "store.db"))
        self._originals = [(m, m.get_db_connection) for m in self.modules]
        for module in self.modules:
            module.get_db_connection = connect
        return self

    def __exit__(self, *exc):
        for module, original in self._originals:
            module.get_db_connection = original
        self._dir.cleanup()


def test_run_costs_sum_per_day():
    with temp_db():
        run_costs.record("run-20260725-010101.json", 0.30, day="20260725")
        run_costs.record("run-20260725-020202.json", 0.20, day="20260725")
        run_costs.record("run-20200101-000000.json", 9.99, day="20200101")
        assert abs(run_costs.spent_on("20260725") - 0.50) < 1e-9
        assert abs(run_costs.spent_on("20200101") - 9.99) < 1e-9
        assert run_costs.spent_on("20991231") == 0.0


def test_spend_windows_week_and_month():
    with temp_db():
        # Wednesday 2026-07-29 — week Mon 27–Wed 29; month July 1–29
        run_costs.record("a", 1.00, day="20260727")
        run_costs.record("b", 2.00, day="20260729")
        run_costs.record("c", 4.00, day="20260701")
        run_costs.record("d", 8.00, day="20260630")  # prior month / week
        windows = ledger.spend_windows("20260729")
        assert abs(windows["today"] - 2.00) < 1e-9
        assert abs(windows["week"] - 3.00) < 1e-9
        assert abs(windows["month"] - 7.00) < 1e-9
        text = ledger.format_spend_reply(windows)
        assert "$2.00" in text and "$3.00" in text and "$7.00" in text


def test_repeated_saves_of_one_run_do_not_double_count():
    """The harness saves its log several times per run — cost must not accumulate."""
    with temp_db():
        for cost in (0.10, 0.25, 0.40):  # same run, growing cost
            run_costs.record("run-20260725-030303.json", cost, day="20260725")
        assert abs(run_costs.spent_on("20260725") - 0.40) < 1e-9


def test_budget_left_reflects_recorded_spend():
    with temp_db():
        assert abs(ledger.budget_left() - ledger.DAILY_BUDGET_USD) < 1e-9
        run_costs.record("run-today.json", 5.00)
        assert abs(ledger.budget_left() - (ledger.DAILY_BUDGET_USD - 5.00)) < 1e-9


def test_budget_fails_closed_when_the_ledger_is_unreadable():
    """Unknown spend must never be treated as zero spend."""
    original = run_costs.get_db_connection
    run_costs.get_db_connection = lambda readonly=False: (None, None)
    try:
        assert run_costs.spent_on() is None
        assert ledger.daily_spent() is None
        assert ledger.budget_left() <= 0
    finally:
        run_costs.get_db_connection = original


def test_hitl_records_and_reads_back_both_decisions():
    with temp_db():
        hitl.record_push({"name": "Run Fuel", "tracks": [{"track_id": "t1"}]},
                         "https://spotify/pl1", ts="2026-07-20T09:00:00")
        hitl.record_rejection({"name": "Too Mellow"}, "too mellow",
                              ts="2026-07-21T09:00:00")

        [push] = hitl.recent(hitl.PUSHED)
        assert push["playlist"]["name"] == "Run Fuel" and push["url"] == "https://spotify/pl1"

        [rejection] = hitl.recent(hitl.REJECTED)
        assert rejection["reason"] == "too mellow"
        assert rejection["playlist"]["name"] == "Too Mellow"


def test_recent_returns_oldest_first_within_the_limit():
    with temp_db():
        for day in range(1, 6):
            hitl.record_push({"name": f"P{day}"}, "u", ts=f"2026-07-0{day}T09:00:00")
        names = [p["playlist"]["name"] for p in hitl.recent(hitl.PUSHED, limit=3)]
        assert names == ["P3", "P4", "P5"]  # newest three, read chronologically


def test_pushes_since_filters_by_date():
    with temp_db():
        hitl.record_push({"name": "Old"}, "u", ts="2026-06-01T09:00:00")
        hitl.record_push({"name": "New"}, "u", ts="2026-07-15T09:00:00")
        names = [p["playlist"]["name"] for p in hitl.pushes_since("2026-07-01")]
        assert names == ["New"]


def test_backfill_is_idempotent():
    """Re-running the migration must not duplicate a decision."""
    with temp_db():
        for _ in range(3):
            hitl.record_push({"name": "Once"}, "u", ts="2026-07-01T09:00:00",
                             record_id="stable-key")
        assert len(hitl.recent(hitl.PUSHED, limit=10)) == 1


def test_hitl_survives_a_missing_database_without_raising():
    original = hitl.get_db_connection
    hitl.get_db_connection = lambda readonly=False: (None, None)
    try:
        assert hitl.record_push({"name": "X"}, "u") is False
        assert hitl.recent(hitl.PUSHED) == []
    finally:
        hitl.get_db_connection = original


if __name__ == "__main__":
    test_run_costs_sum_per_day()
    test_spend_windows_week_and_month()
    test_repeated_saves_of_one_run_do_not_double_count()
    test_budget_left_reflects_recorded_spend()
    test_budget_fails_closed_when_the_ledger_is_unreadable()
    test_hitl_records_and_reads_back_both_decisions()
    test_recent_returns_oldest_first_within_the_limit()
    test_pushes_since_filters_by_date()
    test_backfill_is_idempotent()
    test_hitl_survives_a_missing_database_without_raising()
    print("OK: all store tests passed")
