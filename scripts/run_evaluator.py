"""Headless Evaluator run — the autonomous learning pass.

Run manually or on a schedule (cron / Render cron job):

    ./venv/bin/python scripts/run_evaluator.py

Account-read-only by design: this process can never write to Spotify; it only
reads listening history and writes soft weights to preference_bias.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.evaluator import run_evaluator, top_biases


def main():
    out = run_evaluator()
    print("\n=== EVALUATOR REPORT ===")
    print(out["report"])
    print(f"\nstatus={out['status']}  steps={out['steps']}  "
          f"proposed={out['proposed']}  applied={out['applied']}  "
          f"cost=${out['cost_usd']:.4f}")
    print("\n=== CURRENT LEARNED PREFERENCES (as the DJ will see them) ===")
    for b in top_biases():
        print(f"  {b['kind']:8} {b['key']}: {b['weight']:+.2f}")


if __name__ == "__main__":
    main()
