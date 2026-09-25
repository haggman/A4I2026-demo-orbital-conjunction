"""The console's own run of the sandbox physics, in-process: the same orbit_whatif module the agent's sandbox
runs, on the same elements. Used for one thing: when the operator approves a burn, re-run it here to get the
geometry after the burn (to draw it) and a second opinion on the agent's miss distance."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "agent" / "cymbal_ops" / "sandbox_files"))
import orbit_whatif as ow                        # noqa: E402

import data                                      # noqa: E402
import orbits as O                               # noqa: E402


def case(sim, e) -> dict:
    fleet = {k: str(v) for k, v in data.omm_fields(sim.fleet_rec[e["fleet_sat"]]).items()}
    omm = sim.overrides.get(e["norad_cat_id"]) or sim.x["objects"][str(e["norad_cat_id"])]
    c = {"fleet_sat": e["fleet_sat"], "object_name": e["object_name"], "norad_cat_id": e["norad_cat_id"],
         "fleet_omm": fleet, "object_omm": {k: str(v) for k, v in data.omm_fields(omm).items()},
         "now_utc": O.iso(sim.t0), "tca_utc": O.iso(e["tca"], "milliseconds"), "tca_s": sim._s(e["tca"]),
         "miss_m": e["miss_m"], "hbr_m": sim.rules["hbr_m"], "clear_pc": sim.rules["clear_pc"]}
    c["_sat"], c["_obj"] = ow._satrec(c["fleet_omm"]), ow._satrec(c["object_omm"])
    c["_now"] = ow._utc(c["now_utc"])
    return c


def checker(sim):
    """A local_check for Sim.decide: re-run the approved burn and return what the page draws."""
    def run(e, burn):
        c = case(sim, e)
        w = ow.whatif(c, burn["burn_utc"], float(burn["delta_v_m_s"]), burn.get("direction", "prograde"))
        tca = O.utc(w["tca_after_utc"])
        o = sim.obj(e["norad_cat_id"], sim.overrides.get(e["norad_cat_id"]))
        return {"check_miss_m": w["miss_after_m"], "tca_after_utc": w["tca_after_utc"],
                "ric_after_m": [w["radial_m_after"], w["in_track_m_after"], w["cross_track_m_after"]],
                "plane_after_m": O.ric_to_plane(sim.fleet[e["fleet_sat"]], o, tca, w["radial_m_after"],
                                                w["in_track_m_after"], w["cross_track_m_after"])}
    return run


def smallest_burn(sim, e, burn_utc, direction="prograde"):
    return ow.smallest_burn(case(sim, e), burn_utc, direction=direction)
