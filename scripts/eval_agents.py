"""Pre-release evals: golden-set checks of live LLM behavior.

Run manually before merging/deploying (costs a few cents, needs API keys):

    ./venv/bin/python scripts/eval_agents.py            # router only (~$0.01)
    ./venv/bin/python scripts/eval_agents.py --dj       # + one live DJ build (~$0.40)
    ./venv/bin/python scripts/eval_agents.py --dj-long  # + the 2h Hebrew packer gate

Router cases assert the scope gate and follow-up routing; the DJ case asserts
the whole loop ends in a verifier-clean playlist.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.router import route_message

CTX = ("build a hebrew playlist of about 2 hours", "playlist_request")

ROUTER_CASES = [
    # (message, context, expected)
    ("build me a workout mix", None, "playlist_request"),
    ("what's my top artist this month?", None, "data_question"),
    ("give me a chocolate cake recipe", None, "off_topic"),
    ("write me a python script", None, "off_topic"),
    ("did i listen to any portuguese songs lately?", None, "data_question"),
    ("i want happy songs for my drive home", None, "playlist_request"),
    ("what's the weather tomorrow?", None, "off_topic"),
    ("how many plays do i have?", None, "data_question"),
    # follow-ups inherit the conversation domain
    ("how for example?", CTX, "playlist_request"),
    ("make it longer", CTX, "playlist_request"),
    ("and without mizrahi songs", CTX, "playlist_request"),
    # self-contained requests do NOT inherit
    ("give me a chocolate cake recipe", CTX, "off_topic"),
]


def eval_router():
    passed = 0
    for message, context, expected in ROUTER_CASES:
        got = route_message(message, context=context)
        ok = got == expected
        passed += ok
        print(f"  {'PASS' if ok else 'FAIL'}  {message!r:50} -> {got:16} (want {expected})")
    print(f"router: {passed}/{len(ROUTER_CASES)}")
    return passed == len(ROUTER_CASES)


def eval_dj():
    from agents.dj import request_playlist, verify_playlist

    print("\nlive DJ build (this costs ~$0.2-0.5)...")
    out = request_playlist(
        "a ~40 minute playlist of songs I know well for a relaxed evening")
    ok = out["playlist"] is not None and not verify_playlist(out["playlist"])
    print(f"  {'PASS' if ok else 'FAIL'}  status={out['status']} "
          f"steps={out['steps']} cost=${out['cost_usd']:.3f} "
          f"tracks={len((out['playlist'] or {}).get('tracks', []))}")
    return ok


def eval_dj_long():
    """The packer gate: the exact 2h Hebrew request that used to fail live."""
    from agents.dj import request_playlist, verify_playlist

    print("\nlive LONG DJ build (this costs ~$0.3-0.6)...")
    out = request_playlist(
        "build a hebrew playlist of about 2 hours total that will keep me "
        "awake during the afternoon work time")
    pl = out["playlist"] or {}
    violations = verify_playlist(pl) if pl else ["no playlist"]
    ok = bool(pl) and not violations
    print(f"  {'PASS' if ok else 'FAIL'}  status={out['status']} "
          f"steps={out['steps']} cost=${out['cost_usd']:.3f} "
          f"tracks={len(pl.get('tracks', []))} "
          f"duration={pl.get('total_duration_min')}min "
          f"note={out.get('note')!r} violations={violations}")
    return ok


def main():
    ok = eval_router()
    if "--dj" in sys.argv:
        ok = eval_dj() and ok
    if "--dj-long" in sys.argv:
        ok = eval_dj_long() and ok
    print("\nEVAL:", "ALL PASS" if ok else "FAILURES — do not release")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
