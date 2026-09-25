"""The tools we wrote. Everything that is judgment rather than a query lives here.

- assess_conjunction: gathers every fact about one close approach, states the assumptions, makes the
  judgments that do not need a model (is the tracking stale? can the other object dodge?), and stages a
  case file in the sandbox so the model's what-if code can pick it up.
- maneuver_cost: turns delta-v into days of mission life, from Cymbal Orbital's stated budget.
- build_assessment: assembles the Conjunction Assessment & Maneuver Recommendation. It re-reads the facts
  from BigQuery itself, so the numbers in the report come from the data, not from the model's memory.
"""
import json
import math
from functools import lru_cache

from google.adk.tools import ToolContext
from google.cloud import bigquery

from . import config, sandbox

OMM = ["OBJECT_NAME", "OBJECT_ID", "EPOCH", "MEAN_MOTION", "ECCENTRICITY", "INCLINATION", "RA_OF_ASC_NODE",
       "ARG_OF_PERICENTER", "MEAN_ANOMALY", "EPHEMERIS_TYPE", "CLASSIFICATION_TYPE", "NORAD_CAT_ID",
       "ELEMENT_SET_NO", "REV_AT_EPOCH", "BSTAR", "MEAN_MOTION_DOT", "MEAN_MOTION_DDOT"]
RECOMMENDATIONS = ("MANEUVER", "ESCALATE", "WATCH", "NO ACTION")


@lru_cache(maxsize=1)
def _bq():
    return bigquery.Client(project=config.PROJECT)


def _rows(sql: str, **params) -> list[dict]:
    typ = lambda v: "INT64" if isinstance(v, int) else "FLOAT64" if isinstance(v, float) else "STRING"
    cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter(k, typ(v), v) for k, v in params.items()])
    return [dict(r) for r in _bq().query(sql.replace("{D}", f"`{config.PROJECT}.{config.DATASET}`"), job_config=cfg).result()]


def _plain(v):
    """Dates as ISO strings; timestamps in UTC to the second, whatever zone the client handed them back in."""
    if hasattr(v, "astimezone") and getattr(v, "tzinfo", None) is not None:
        from datetime import timezone
        return v.astimezone(timezone.utc).isoformat(timespec="seconds")
    return v.isoformat() if hasattr(v, "isoformat") else v


def _facts(fleet_sat: str, norad_cat_id: int) -> dict | None:
    ev = _rows("SELECT * FROM {D}.conjunctions WHERE fleet_sat = @f AND norad_cat_id = @n ORDER BY miss_m LIMIT 1",
               f=fleet_sat, n=int(norad_cat_id))
    if not ev:
        return None
    obj = _rows("SELECT * FROM {D}.catalog WHERE NORAD_CAT_ID = @n", n=int(norad_cat_id))[0]
    sat = _rows("SELECT * FROM {D}.fleet WHERE OBJECT_NAME = @f", f=fleet_sat)[0]
    sc = _rows("SELECT OWNER, LAUNCH_DATE, OPS_STATUS_CODE, RCS_M2 FROM {D}.satcat WHERE NORAD_CAT_ID = @n", n=int(norad_cat_id))
    info = _rows("SELECT * FROM {D}.snapshot_info")[0]
    return {"event": {k: _plain(v) for k, v in ev[0].items()}, "object": obj, "fleet": sat,
            "satcat": {k: _plain(v) for k, v in (sc[0] if sc else {}).items()}, "info": info}


def _miss_needed(hbr_m: float) -> float:
    return hbr_m / math.sqrt(math.e * config.CLEAR_PC)


def assess_conjunction(fleet_sat: str, norad_cat_id: int, tool_context: ToolContext) -> dict:
    """Everything known about one close approach between a Cymbal Orbital satellite and a catalogued object.

    Call this before discussing any specific approach, and ALWAYS before writing what-if code: it stages the
    case file that orbit_whatif reads in the sandbox.

    Args:
        fleet_sat: our satellite's name, e.g. "CYMBAL-04".
        norad_cat_id: the other object's catalogue number, e.g. 31178.

    Returns:
        The event, the other object, the assumptions every number rests on, the judgments that need no model,
        and the name of the staged case file with a code example for the sandbox.
    """
    f = _facts(fleet_sat, norad_cat_id)
    if f is None:
        return {"error": f"No screened approach between {fleet_sat} and {norad_cat_id} within 10 km this week.",
                "hint": "List candidates with execute_sql_readonly on the conjunctions table first."}
    ev, obj, info = f["event"], f["object"], f["info"]
    hbr = float(ev["hbr_m"])
    ops = (f["satcat"].get("OPS_STATUS_CODE") or ev.get("ops_status") or "").strip()
    case_file = f"case_{fleet_sat}_{int(norad_cat_id)}.json"
    case = {"fleet_sat": fleet_sat, "object_name": ev["object_name"], "norad_cat_id": int(norad_cat_id),
            "fleet_omm": {k: str(f["fleet"][k]) for k in OMM}, "object_omm": {k: str(obj[k]) for k in OMM},
            "now_utc": config.NOW_UTC, "tca_utc": ev["tca_utc"], "tca_s": float(ev["hours_from_now"]) * 3600.0,
            "miss_m": float(ev["miss_m"]), "hbr_m": hbr, "clear_pc": config.CLEAR_PC}
    staged = sandbox.stage({case_file: json.dumps(case).encode()})
    tool_context.state["last_case"] = {"fleet_sat": fleet_sat, "norad_cat_id": int(norad_cat_id), "case_file": case_file}
    return {
        "now_utc": config.NOW_UTC,
        "event": {k: ev[k] for k in ("fleet_sat", "object_name", "tca_utc", "hours_from_now", "miss_m", "radial_m",
                                     "in_track_m", "cross_track_m", "rel_speed_km_s", "max_pc", "pc_sigma_200m",
                                     "pc_sigma_1km", "triage")},
        "object": {"name": ev["object_name"], "norad_cat_id": int(norad_cat_id), "international_designator": obj["OBJECT_ID"],
                   "type": obj.get("OBJECT_TYPE"), "type_source": obj.get("OBJECT_TYPE_SOURCE", "SATCAT"),
                   "owner": f["satcat"].get("OWNER"), "launch_date": f["satcat"].get("LAUNCH_DATE"),
                   "parent_event": ev.get("parent_event"), "perigee_km": round(float(obj["PERIGEE_KM"]), 1),
                   "apogee_km": round(float(obj["APOGEE_KM"]), 1)},
        "assumptions": {"hard_body_radius_m": hbr, "covariance": "none published; worst case is over every isotropic size",
                        "assumed_sigmas_m": info.get("sigma_m_assumed"), "clear_means": f"worst-case Pc below {config.CLEAR_PC:g}",
                        "escalation_line_pc": info.get("escalate_max_pc"),
                        "spacecraft_budget": f"{config.DELTA_V_BUDGET_M_S:g} m/s over a {config.DESIGN_LIFE_YEARS:g}-year design life (fictional, stated)"},
        "judgments": {
            "elements_days_old_at_tca": ev["element_age_at_tca_days"],
            "elements_stale": bool(ev["elements_stale"]),
            "stale_means": f"the object's elements will be more than {info.get('stale_days')} days old at closest approach; ask for fresh tracking before spending propellant",
            "other_object_can_maneuver": ops == "+",
            "other_object_status": {"+": "operational—it might move too; coordinate with its operator", "-": "dead—it cannot move",
                                    "": "debris or rocket body—it cannot move"}.get(ops, f"status code {ops!r}"),
            "miss_needed_to_clear_m": round(_miss_needed(hbr), 0),
            "already_clear": float(ev["max_pc"]) < config.CLEAR_PC,
        },
        "sandbox": {"case_file": case_file, "staged": "ok" if '"ok": true' in staged["stdout"] else staged,
                    "example_code": (f"import orbit_whatif as ow\ncase = ow.load_case('{case_file}')\n"
                                     f"print(ow.baseline(case))\nprint(ow.smallest_burn(case, '<burn time UTC, ISO>'))")},
    }


def maneuver_cost(delta_v_m_s: float) -> dict:
    """What a burn costs Cymbal Orbital, in days of mission life.

    Cymbal Orbital is fictional; its budget is a stated assumption, and every answer from this tool says so.

    Args:
        delta_v_m_s: the size of the burn in metres per second (the sign does not matter).
    """
    dv = abs(float(delta_v_m_s))
    days_per_m_s = config.DESIGN_LIFE_YEARS * 365.25 / config.DELTA_V_BUDGET_M_S
    days = dv * days_per_m_s
    return {"delta_v_m_s": dv, "days_of_mission_life": round(days, 2), "hours_of_mission_life": round(days * 24, 1),
            "pct_of_lifetime_budget": round(100 * dv / config.DELTA_V_BUDGET_M_S, 3),
            "days_per_m_s": round(days_per_m_s, 1),
            "assumption": f"Cymbal Orbital (fictional) carries {config.DELTA_V_BUDGET_M_S:g} m/s of delta-v for a "
                          f"{config.DESIGN_LIFE_YEARS:g}-year design life; propellant spent dodging is life not lived."}


def build_assessment(fleet_sat: str, norad_cat_id: int, recommendation: str, rationale: str,
                     tool_context: ToolContext, burn_utc: str = "", delta_v_m_s: float = 0.0,
                     direction: str = "prograde", miss_after_m: float = 0.0) -> dict:
    """Assemble the Conjunction Assessment & Maneuver Recommendation for one approach.

    The facts are re-read from BigQuery here; you supply only the decision and, for a maneuver, the numbers
    your sandbox run produced—copied exactly from its output.

    Args:
        fleet_sat: our satellite, e.g. "CYMBAL-04".
        norad_cat_id: the other object's catalogue number.
        recommendation: one of MANEUVER, ESCALATE, WATCH, NO ACTION.
        rationale: two or three plain sentences a flight director would accept.
        burn_utc: for MANEUVER, the burn time (ISO 8601, UTC).
        delta_v_m_s: for MANEUVER, the burn size from smallest_burn.
        direction: for MANEUVER, prograde, retrograde, radial or normal.
        miss_after_m: for MANEUVER, the miss distance after the burn from smallest_burn.
    """
    rec = recommendation.strip().upper()
    if rec not in RECOMMENDATIONS:
        return {"error": f"recommendation must be one of {RECOMMENDATIONS}"}
    if rec == "MANEUVER" and not (burn_utc and delta_v_m_s > 0 and miss_after_m > 0):
        return {"error": "a MANEUVER needs burn_utc, delta_v_m_s and miss_after_m from the sandbox run"}
    f = _facts(fleet_sat, norad_cat_id)
    if f is None:
        return {"error": f"No screened approach between {fleet_sat} and {norad_cat_id}."}
    ev, info = f["event"], f["info"]
    hbr = float(ev["hbr_m"])
    a = {
        "title": "Conjunction Assessment & Maneuver Recommendation",
        "as_of_utc": config.NOW_UTC, "operator": "Cymbal Orbital (fictional)",
        "event": {"our_satellite": fleet_sat, "object": ev["object_name"], "norad_cat_id": int(norad_cat_id),
                  "object_type": ev["object_type"], "parent_event": ev.get("parent_event"),
                  "closest_approach_utc": ev["tca_utc"], "hours_from_now": ev["hours_from_now"],
                  "miss_m": ev["miss_m"], "radial_m": ev["radial_m"], "in_track_m": ev["in_track_m"],
                  "cross_track_m": ev["cross_track_m"], "relative_speed_km_s": ev["rel_speed_km_s"]},
        "risk": {"worst_case_pc": ev["max_pc"], "pc_if_sigma_200m": ev["pc_sigma_200m"], "pc_if_sigma_1km": ev["pc_sigma_1km"],
                 "elements_days_old_at_tca": ev["element_age_at_tca_days"], "elements_stale": bool(ev["elements_stale"])},
        "recommendation": rec, "rationale": rationale.strip(),
        "assumptions": [f"Hard-body radius {hbr:g} m (both objects together).",
                        "No covariance is published with public elements: the worst case is taken over every isotropic uncertainty.",
                        f"'Clear' means worst-case probability below {config.CLEAR_PC:g}, a miss of about {_miss_needed(hbr):,.0f} m.",
                        f"Cymbal Orbital's budget: {config.DELTA_V_BUDGET_M_S:g} m/s over {config.DESIGN_LIFE_YEARS:g} years (fictional)."],
        "cannot_see": ["Objects the tracking network has not updated in 30 days are not in the catalogue we screened.",
                       "Public mean elements carry position errors that can run to kilometres, growing with their age.",
                       "A real operator would request a conjunction data message, with covariance, before committing propellant."],
        "source": info.get("citation"),
    }
    if rec == "MANEUVER":
        cost = maneuver_cost(delta_v_m_s)
        a["maneuver"] = {"burn_utc": burn_utc, "delta_v_m_s": delta_v_m_s, "direction": direction,
                         "miss_after_m": miss_after_m,
                         "worst_case_pc_after": min(1.0, hbr ** 2 / (math.e * miss_after_m ** 2)),
                         "cost_days_of_mission_life": cost["days_of_mission_life"],
                         "cost_pct_of_budget": cost["pct_of_lifetime_budget"]}
    md = [f"## {a['title']}", f"*As of {a['as_of_utc']} · {a['operator']}*", "",
          f"**{fleet_sat}** meets **{ev['object_name']}** ({ev['object_type']}, catalogue {int(norad_cat_id)}"
          + (f", from the {ev['parent_event']}" if ev.get("parent_event") else "") + ")",
          f"at **{ev['tca_utc']}**, {ev['hours_from_now']} h from now: **{ev['miss_m']:,.1f} m** at {ev['rel_speed_km_s']} km/s "
          f"(radial {ev['radial_m']:,.0f} · in-track {ev['in_track_m']:,.0f} · cross-track {ev['cross_track_m']:,.0f} m).", "",
          f"**Risk.** Worst case {ev['max_pc']:.1e}; if the 1-sigma uncertainty is 200 m, {ev['pc_sigma_200m']:.1e}; if 1 km, "
          f"{ev['pc_sigma_1km']:.1e}. The object's elements will be {ev['element_age_at_tca_days']} days old"
          + (" — **stale**." if ev["elements_stale"] else "."), "",
          f"**Recommendation: {rec}.** {rationale.strip()}"]
    if rec == "MANEUVER":
        m = a["maneuver"]
        md += ["", f"**Maneuver.** {m['delta_v_m_s']} m/s {m['direction']} at {m['burn_utc']} → miss {m['miss_after_m']:,.0f} m, "
                   f"worst case {m['worst_case_pc_after']:.1e}. **Cost: {m['cost_days_of_mission_life']} days of mission life** "
                   f"({m['cost_pct_of_budget']}% of the lifetime budget)."]
    md += ["", "**Assumptions.** " + " ".join(a["assumptions"]), "", "**What we cannot see.** " + " ".join(a["cannot_see"]),
           "", f"*{a['source']}*"]
    a["markdown"] = "\n".join(md)
    tool_context.state["assessment"] = a
    return a
