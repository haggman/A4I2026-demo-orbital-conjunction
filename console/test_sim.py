"""Run the whole pinned week headless, at full speed, with a SCRIPTED stand-in for the agent, and print every
card in order. No Gemini, no BigQuery, no sandbox: the stand-in sizes burns with the same orbit_whatif module
in-process, so the numbers are real physics on the pinned elements; only the words are scripted.

    python console/test_sim.py            # needs console/.snapshot_extract.json and console/scenario.json
"""
import json
import sys
import textwrap
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import data                                      # noqa: E402
import orbits as O                               # noqa: E402
import physics                                   # noqa: E402
from sim import Sim, fmt                         # noqa: E402

DAYS_PER_M_S = 7 * 365.25 / 30                   # Cymbal Orbital's stated budget, as maneuver_cost uses it


def scripted_agent(sim, wake):
    """What the real agent is asked to do, done with the same tools' physics, without a model."""
    e = sim.events[wake["key"]]
    if wake["why"] == "decide":
        slots = [l.split(": ", 1)[1] for l in wake["brief"].splitlines() if l.startswith("Command windows")]
        m = next(v for v in sim.sc["moments"].values() if sim._key(v["fleet_sat"], v["norad_cat_id"]) == wake["key"])
        options = []
        for slot in m["burn_slots_utc"]:
            t0 = time.perf_counter()
            b = physics.smallest_burn(sim, e, slot)
            options.append(b)
            print(f"      [stand-in] smallest prograde burn at {slot}: {b.get('delta_v_m_s')} m/s → "
                  f"{b.get('miss_after_m')} m, {round(b.get('delta_v_m_s', 0) * DAYS_PER_M_S, 2)} days "
                  f"({time.perf_counter() - t0:.1f} s)")
        best = min((b for b in options if b.get("feasible")), key=lambda b: b["delta_v_m_s"])
        a = {"recommendation": "MANEUVER", "maneuver": {
            "burn_utc": best["burn_utc"], "delta_v_m_s": best["delta_v_m_s"], "direction": "prograde",
            "miss_after_m": best["miss_after_m"], "cost_days_of_mission_life": round(best["delta_v_m_s"] * DAYS_PER_M_S, 2)}}
        return a, "(scripted) Burn at the earlier window: it is cheaper and clears it."
    return {"recommendation": "NO ACTION"}, "(scripted) Fresh tracking clears it. Stand down; no burn."


def main():
    sim = Sim(data.load(), json.loads((HERE / "scenario.json").read_text()))
    sim.set_speed(3)
    sim.play(True)
    check = physics.checker(sim)
    t0 = time.perf_counter()
    printed = 0
    while sim.t < sim.t_end_s:
        acts = sim.advance(3600.0)                          # an hour of wall time at 1 h/s: jumps to the next trigger
        for a in acts:
            if "wake" in a:
                assessment, text = scripted_agent(sim, a["wake"])
                sim.agent_result(a["wake"]["card_id"], assessment, text)
                sim.decide(a["wake"]["card_id"], "approve", check)
        for c in sim.cards[printed:]:
            print(f"\n[{c['at']}] {c['who'].upper():<7} {c['level']:<8} {c['title']}")
            for l in c["lines"] + ([c["summary"]] if c.get("summary") else []) + ([f"decision: {c['decision']}"] if c.get("decision") else []):
                print(textwrap.fill(l, 110, initial_indent="      ", subsequent_indent="      "))
        printed = len(sim.cards)
        if not sim.playing and sim.t < sim.t_end_s:
            break
    print(f"\n{len(sim.cards)} cards, sim end {fmt(sim.now())}, {time.perf_counter() - t0:.1f} s wall")
    a = sim.events[sim.moments["A"]]
    print("moment A focus:", {k: a[k] for k in ("miss_m", "max_pc", "plane_m", "triage")}, "before burn:", a.get("before_burn"))
    # range gauge near A's closest approach
    for dt in (-600, -60, -10, 0, 10, 60):
        print(f"   range at TCA{dt:+d}s: {sim.range_km(a, a['tca'] + O.timedelta(seconds=dt)) if hasattr(O, 'timedelta') else ''}")


if __name__ == "__main__":
    main()
