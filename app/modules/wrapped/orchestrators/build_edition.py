import re

from app.errors import validation_error
from app.modules.agent_api import events
from pipelines.wrapped import get_wrapped

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def execute(period="week", force=False, start=None, end=None):
    if period == "custom":
        _validate_range(start, end)

    events.record(
        "wrapped", f"{period} edition requested" + (" (fresh look)" if force else "")
    )
    edition = get_wrapped(period=period, force=force, start=start, end=end)
    if edition.get("cost_usd") is not None and edition.get("generated_at"):
        events.record(
            "wrapped",
            f"edition {edition.get('key')} ready (${edition.get('cost_usd', 0):.3f})",
        )
    return edition


def _validate_range(start, end):
    if not (start and end and ISO_DATE.match(start) and ISO_DATE.match(end)):
        raise validation_error(
            "Custom range needs start and end dates as YYYY-MM-DD.",
            {"start": start, "end": end},
        )
    if start > end:
        raise validation_error(
            "The start date must not be after the end date.",
            {"start": start, "end": end},
        )
