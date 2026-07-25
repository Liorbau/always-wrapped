"""Cross-cutting infrastructure every other package may depend on.

Nothing here imports from app/, agents/, pipelines/, db/ or integrations/ —
that one-way rule is what makes it safe for all of them to import core.
"""
