"""Turn a live rehearsal run into the recording the demo replays: console/recordings/rehearsal.json.

    python console/keep_recording.py                         # the newest console/recordings/run-*.json
    python console/keep_recording.py console/recordings/run-20261009T150000Z.json

It refuses a recording that would not tell the story, and it proves the replay is the same every time:
  1. both agent turns are there: the decision on moment A and the re-assessment on Tuesday's fresh tracking;
  2. both ended with a structured assessment: MANEUVER at one of the scenario's burn windows for A,
     and no burn for B;
  3. nothing project-specific is left in it (project IDs and resource names are replaced), because the
     recording is committed to a public repository;
  4. the whole week is played twice from it, headless, and the two card sequences must match exactly.
Then it writes console/recordings/rehearsal.json. Commit that file.
"""
import asyncio
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import agent_bridge                              # noqa: E402
import data                                      # noqa: E402
import physics                                   # noqa: E402
from sim import Sim                              # noqa: E402

REC = HERE / "recordings"


def fail(msg):
    raise SystemExit(f"\nNOT KEPT: {msg}\n")


def scrub(obj, words):
    """Replace project IDs, project numbers and Google Cloud resource names anywhere in the recording."""
    text = json.dumps(obj)
    text = re.sub(r"projects/[^/\"\s]+(/locations/[^/\"\s]+)?(/[A-Za-z]+/[^\"\s,)]+)*", "projects/…", text)
    for w in sorted({w for w in words if w and len(w) > 4}, key=len, reverse=True):
        text = text.replace(w, "<project>")
    text = re.sub(r"qwiklabs-gcp-[0-9a-z-]+", "<project>", text)
    return json.loads(text)


def week(sc, rec_name):
    """Play the whole week from a recording, approving every agent card; return the card sequence."""
    sim = Sim(data.load(), sc)
    agent = agent_bridge.ReplayAgent(rec_name, max_step_s=0.0)
    check = physics.checker(sim)
    sim.set_speed(3)
    sim.play(True)

    async def run():
        while sim.t < sim.t_end_s:
            for a in sim.advance(3600.0):
                if "wake" in a:
                    w = a["wake"]
                    out = await agent.turn(w["brief"], w["sim_now_utc"], w["overrides"], None, kind="alert",
                                           meta={"key": w["key"], "why": w["why"]})
                    if out["error"]:
                        fail(out["error"])
                    sim.agent_result(w["card_id"], out["assessment"], out["text"])
                    sim.decide(w["card_id"], "approve", check)
            if not sim.playing and sim.t < sim.t_end_s:
                fail(f"the week stopped early at {sim.state()['now']}")
    orig_sleep = asyncio.sleep
    asyncio.sleep = lambda *_a, **_k: orig_sleep(0)          # no typing delays in the check
    try:
        asyncio.run(run())
    finally:
        asyncio.sleep = orig_sleep
    return [(c["at_utc"], c["who"], c["title"], c.get("summary") or "", tuple(c["lines"])) for c in sim.cards]


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else max(REC.glob("run-*.json"), key=lambda p: p.stat().st_mtime, default=None)
    if not src or not src.exists():
        fail("no recording found. Run the console live through the week first (see run-of-show/README.md).")
    rec = json.loads(src.read_text())
    sc = json.loads((HERE / "scenario.json").read_text())
    sim = Sim(data.load(), sc)
    a_key, b_key = sim.moments["A"], sim.moments["B"]
    turns = {(t.get("why"), t.get("key")): t for t in rec.get("turns", [])}
    ta, tb = turns.get(("decide", a_key)), turns.get(("update", b_key))
    if not ta or not tb:
        fail(f"{src.name} needs both agent turns (the decision on moment A and Tuesday's re-assessment); it has "
             f"{sorted(k[0] for k in turns)}. Run the whole week, approving each card.")
    aa, ab = ta.get("assessment") or {}, tb.get("assessment") or {}
    slots = sc["moments"]["A"]["burn_slots_utc"]
    m = aa.get("maneuver") or {}
    if aa.get("recommendation") != "MANEUVER" or not m:
        fail(f"moment A's card recommended {aa.get('recommendation')!r}, not a burn. Rehearse again.")
    if not any(m["burn_utc"].startswith(s[:16]) for s in slots):
        fail(f"moment A's burn is at {m['burn_utc']}, not at a scenario window {slots}. Rehearse again.")
    if ab.get("recommendation") == "MANEUVER" or not ab:
        fail(f"Tuesday's card recommended {ab.get('recommendation')!r}; the story needs no burn. Rehearse again.")

    words = []
    try:
        sys.path.insert(0, str(HERE.parent / "agent"))
        from cymbal_ops import config
        words = [config.PROJECT, config.SANDBOX]
    except Exception:
        pass
    kept = scrub({**rec, "kept_from": src.name,
                  "about": "A real run of the live agent, recorded by the console and kept by console/keep_recording.py. "
                           "The console's replay mode plays it back at the same sim moments, with the same steps."}, words)
    out = REC / "rehearsal.json"
    tmp = REC / ".rehearsal.check.json"
    tmp.write_text(json.dumps(kept, indent=1) + "\n")
    try:
        one, two = week(sc, tmp.stem), week(sc, tmp.stem)
    finally:
        pass
    if one != two:
        tmp.unlink()
        fail("two replays of the week differ. That should never happen: send the output to Claude.")
    tmp.replace(out)
    print(f"Kept {src.name} → {out.relative_to(HERE.parent)}")
    print(f"  moment A: {m['delta_v_m_s']} m/s {m.get('direction', 'prograde')} at {m['burn_utc']} → {m['miss_after_m']:,.0f} m "
          f"({ta.get('seconds')} s live, {len(ta.get('steps', []))} tool steps)")
    print(f"  Tuesday:  {ab.get('recommendation')} ({tb.get('seconds')} s live, {len(tb.get('steps', []))} tool steps)")
    print(f"  replayed the week twice: {len(one)} cards, identical. Commit console/recordings/rehearsal.json.")


if __name__ == "__main__":
    main()
