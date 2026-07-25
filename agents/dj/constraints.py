"""The playlist constraints the packer enforces and the prompt advertises.

One definition each, so the prompt can never drift from the code that checks it.
"""

DEFAULT_DURATION_MIN = 60
MAX_COST_USD = 2.00
MAX_STEPS = 16
MAX_REPAIR_ROUNDS = 2
DURATION_TOLERANCE = 0.25
MAX_PER_ARTIST = 2
MAX_PLAYED_FRAC = 0.4  # never-heard playlists: played tracks stay <= this share

TOLERANCE_PCT = int(DURATION_TOLERANCE * 100)
