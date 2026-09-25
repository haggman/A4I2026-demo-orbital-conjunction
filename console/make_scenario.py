"""Write console/scenario.json: the console's storyline for the pinned week, and its ONE piece of simulated data.

Everything the console shows comes from the snapshot, except one thing: on Tuesday a fresh element set arrives for
the rocket body in moment B, and the recomputed miss clears. The snapshot has no future, so that update is
SIMULATED, and labelled so everywhere it appears. How it is made, so you can check it:

  1. Start from the snapshot's own element set for the object.
  2. Move it to the new epoch with SGP4's own secular rates (mean anomaly, node, argument of perigee).
     Alone, that changes nothing: the recomputed miss must come back at the snapshot's value. We check it.
  3. Shift the object along its own track (a change of mean anomaly) until the recomputed miss equals a stated
     target. Along-track error is what grows fastest in old elements, so this is the realistic kind of change.

No random numbers: the target is stated below, the search is a fixed grid plus Brent's method, and the output
is committed. Run it again and you get the same file.

    python console/make_scenario.py            # needs console/.snapshot_extract.json (python console/data.py)
"""
import json
import sys
from datetime import timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import data                                    # noqa: E402
import elements as E                           # noqa: E402
import orbits as O                             # noqa: E402

# ---- the storyline: every number here is a stated choice --------------------------------------------------------
START = "2026-09-25T01:00:00Z"                 # the frozen "now" of the notebook and the agent
DAYS = 7
MOMENT_A = ("CYMBAL-04", 31178)                # ESCALATE, fresh tracking: the agent plans a burn
MOMENT_B = ("CYMBAL-11", 8520)                 # WATCH, stale tracking: fresh tracking is requested
BURN_SLOTS_A = ["2026-09-25T04:00:00Z", "2026-09-25T12:00:00Z"]   # the two command windows the agent compares
DECISION_LEAD_H = 18.0                         # wake the agent this long before an ESCALATE approach
ACT_LIMIT_MIN = 30.0                           # closer than this to closest approach: too late to act
UPDATE_B_ARRIVES = "2026-09-29T06:00:00Z"      # when the simulated fresh tracking reaches the desk (Tuesday)
UPDATE_B_EPOCH = "2026-09-29T04:00:00Z"        # the epoch of that element set: two hours earlier
UPDATE_B_TARGET_M = 3700.0                     # its recomputed miss: beyond the ~3,033 m "clear" line
HBR_M, CLEAR_PC = 5.0, 1e-6


def event(d, sat, norad):
    rows = [c for c in d["conjunctions"] if c["fleet_sat"] == sat and int(c["norad_cat_id"]) == norad]
    if not rows:
        raise SystemExit(f"{sat} vs {norad} is not in the extract's conjunctions")
    return min(rows, key=lambda c: float(c["miss_m"]))


def main():
    d = data.load()
    fleet = {f["OBJECT_NAME"]: f for f in d["fleet"]}
    out_checks = []

    # Re-measure the three named approaches from the elements alone: they must agree with the table.
    for label, (sat, norad) in (("A", MOMENT_A), ("B", MOMENT_B)):
        ev = event(d, sat, norad)
        s, o = O.satrec(fleet[sat]), O.satrec(d["objects"][str(norad)])
        enc = O.encounter(s, o, O.closest(s, o, O.utc(ev["tca_utc"])))
        out_checks.append({"moment": label, "table_miss_m": float(ev["miss_m"]), "recomputed_miss_m": enc["miss_m"],
                           "table_tca_utc": ev["tca_utc"][:23], "recomputed_tca_utc": enc["tca_utc"]})

    # Moment B's simulated update.
    sat, norad = MOMENT_B
    ev = event(d, sat, norad)
    s = O.satrec(fleet[sat])
    orig = {k: d["objects"][str(norad)][k] for k in data.OMM}
    moved = E.to_epoch(orig, O.utc(UPDATE_B_EPOCH))
    miss_moved, _ = E.miss_with(s, moved, O.utc(ev["tca_utc"]))
    dm = E.tune_miss(s, moved, O.utc(ev["tca_utc"]), UPDATE_B_TARGET_M)
    new = E.shift_anomaly(moved, dm)
    o_new = O.satrec(new)
    enc = O.encounter(s, o_new, O.closest(s, o_new, O.utc(ev["tca_utc"])))
    a_km = (398600.4418 / (float(orig["MEAN_MOTION"]) * 2 * 3.141592653589793 / 86400) ** 2) ** (1 / 3)
    age = (O.utc(enc["tca_utc"]) - O.utc(UPDATE_B_EPOCH)).total_seconds() / 86400
    update = {
        "SIMULATED": True,
        "label": "SIMULATED tracking update: the snapshot has no future, so this element set was made by "
                 "console/make_scenario.py from the snapshot's own elements (see its docstring).",
        "fleet_sat": sat, "norad_cat_id": norad, "object_name": ev["object_name"],
        "arrives_utc": UPDATE_B_ARRIVES, "epoch_utc": UPDATE_B_EPOCH,
        "omm": {k: str(v) for k, v in new.items()},
        "how": {"from_epoch_utc": O.iso(O.utc(orig["EPOCH"]), "milliseconds"), "moved_by_secular_rates_to": UPDATE_B_EPOCH,
                "miss_after_move_only_m": round(miss_moved, 1), "snapshot_miss_m": float(ev["miss_m"]),
                "mean_anomaly_shift_deg": round(dm, 7), "along_track_shift_km": round(abs(dm) * 3.141592653589793 / 180 * a_km, 2),
                "target_miss_m": UPDATE_B_TARGET_M},
        "result": {**enc, "max_pc": O.max_pc(enc["miss_m"], HBR_M), "element_age_at_tca_days": round(age, 2),
                   "elements_stale": age > 5.0, "clear": O.max_pc(enc["miss_m"], HBR_M) < CLEAR_PC},
    }
    scenario = {
        "about": "The flight dynamics console's storyline for the pinned week. Everything comes from snapshot "
                 f"{d['snapshot_info'].get('snapshot')} except the entries marked SIMULATED. Written by console/make_scenario.py.",
        "snapshot": d["snapshot_info"].get("snapshot"),
        "start_utc": START, "end_utc": O.iso(O.utc(START) + timedelta(days=DAYS)),
        "speeds": [{"label": "1×", "x": 1}, {"label": "1 min/s", "x": 60}, {"label": "10 min/s", "x": 600}, {"label": "1 h/s", "x": 3600}],
        "rules": {"decision_lead_h": DECISION_LEAD_H, "act_limit_min": ACT_LIMIT_MIN, "escalate_pc": 1e-4, "watch_m": 1000.0,
                  "stale_days": 5.0, "clear_pc": CLEAR_PC, "hbr_m": HBR_M},
        "moments": {"A": {"fleet_sat": MOMENT_A[0], "norad_cat_id": MOMENT_A[1], "burn_slots_utc": BURN_SLOTS_A},
                    "B": {"fleet_sat": MOMENT_B[0], "norad_cat_id": MOMENT_B[1]}},
        "tracking_updates": [update],
        "checks": out_checks,
    }
    (HERE / "scenario.json").write_text(json.dumps(scenario, indent=1) + "\n")
    print(json.dumps({"checks": out_checks, "update_how": update["how"], "update_result": update["result"]}, indent=1))


if __name__ == "__main__":
    main()
