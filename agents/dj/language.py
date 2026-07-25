"""Hebrew detection.

Hebrew requests are a large slice of this library, so the code-side supply has
to stay on-theme when one is in play — global top-played would be off-topic.
"""

import re

HEBREW = re.compile(r"[\u0590-\u05FF]")


def is_hebrew(text):
    return bool(HEBREW.search(text or ""))


def mostly_hebrew(names):
    return bool(names) and sum(is_hebrew(name) for name in names) > len(names) / 2
