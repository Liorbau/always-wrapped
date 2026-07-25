"""The observatory's live activity feed: a bounded, in-memory ring of events.

Owned here rather than in the agents router so any module (the Wrapped
pipeline, the Planner, timers) can narrate itself without importing HTTP code.
"""

import itertools
import time
from collections import deque

MAX_EVENTS = 80
FEED_WINDOW = 40
MAX_TEXT = 120

EVENTS = deque(maxlen=MAX_EVENTS)

_next_id = itertools.count(1)


def record(node, text):
    event = {
        "id": next(_next_id),
        "ts": time.strftime("%H:%M:%S"),
        "node": node,
        "text": text[:MAX_TEXT],
    }
    EVENTS.append(event)
    return event


def recent():
    return list(EVENTS)[-FEED_WINDOW:]


def clear():
    EVENTS.clear()
