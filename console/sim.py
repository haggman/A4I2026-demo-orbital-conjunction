"""The simulator behind the flight dynamics console: a clock over the pinned week, and a watcher.

- The CLOCK runs over the snapshot's week at a preset speed. Positions come from SGP4 on the pinned elements at
  the sim time, so time is continuous. "Skip to next" jumps to just before the next thing that matters and
  slows down so the room sees it.
- The WATCHER is plain code: no model, no call per tick. Its rules decide when something is worth a card, and
  when it is worth waking the agent. When it wakes the agent the clock pauses; Approve or Hold resumes it.
- Deterministic: the same extract and scenario.json give the same cards at the same sim times, every run.

Nothing here talks to the cloud. The backend (app.py) runs the agent when the watcher asks for it, and feeds
the agent's result back with agent_result().
"""
import math
import sys
from datetime import timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import orbits as O                              # noqa: E402

WEEKDAY = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
NEAR_TCA_S = 600.0                              # inside this, the range gauge uses the straight-line form


def fmt(t) -> str:
    """'Fri 25 Sep 20:16:10 UTC'—the way every card says a time."""
    return f"{WEEKDAY[t.weekday()]} {t.day} {t.strftime('%b %H:%M:%S')} UTC"


def fmt_short(t) -> str:
    return f"{WEEKDAY[t.weekday()]} {t.strftime('%H:%M')}"


def fmt_pc(p) -> str:
    return f"{p:.2e}"         # three figures: 9.99e-07 is under the clear line, and "1.0e-06" would hide that


def span(seconds: float) -> str:
    s = abs(seconds)
    if s < 90:
        return f"{s:.0f} s"
    if s < 5400:
        return f"{s / 60:.0f} min"
    if s < 2 * 86400:
        return f"{s / 3600:.1f} h"
    return f"{s / 86400:.1f} days"


class Sim:
    def __init__(self, extract: dict, scenario: dict):
        self.x = extract
        self.sc = scenario
        self.rules = scenario["rules"]
        self.t0 = O.utc(scenario["start_utc"])
        self.t_end_s = (O.utc(scenario["end_utc"]) - self.t0).total_seconds()
        self.speeds = scenario["speeds"]
        self.fleet_rec = {f["OBJECT_NAME"]: f for f in extract["fleet"]}
        self.fleet = {n: O.satrec(r) for n, r in self.fleet_rec.items()}
        self._objs = {}
        self._planes = {}
        self.reset()

    # ------------------------------------------------------------------------------------------ set-up
    def _key(self, sat, norad):
        ks = [k for k, e in self.events.items() if e["fleet_sat"] == sat and e["norad_cat_id"] == int(norad)]
        return min(ks, key=lambda k: self.events[k]["miss_m"]) if ks else None

    def obj(self, norad: int, omm: dict | None = None):
        if omm is not None:
            return O.satrec(omm)
        if norad not in self._objs:
            self._objs[norad] = O.satrec(self.x["objects"][str(norad)])
        return self._objs[norad]

    def _triage(self, miss_m, pc, was_tracked=False):
        """The notebook's rule. An approach we were tracking that has since been moved past the clear line (by a
        burn, or by fresh tracking) is shown as CLEAR rather than as noise."""
        t = "ESCALATE" if pc >= self.rules["escalate_pc"] else "WATCH" if miss_m < self.rules["watch_m"] else "NOISE"
        return "CLEAR" if was_tracked and t == "NOISE" and pc < self.rules["clear_pc"] else t

    def _from_row(self, k, c) -> dict:
        tca = O.utc(c["tca_utc"])
        e = {"key": k, "fleet_sat": c["fleet_sat"], "norad_cat_id": int(c["norad_cat_id"]), "object_name": c["object_name"],
             "object_type": c.get("object_type"), "ops_status": c.get("ops_status") or "", "parent_event": c.get("parent_event"),
             "tca": tca, "miss_m": float(c["miss_m"]), "radial_m": float(c["radial_m"]), "in_track_m": float(c["in_track_m"]),
             "cross_track_m": float(c["cross_track_m"]), "rel_speed_km_s": float(c["rel_speed_km_s"]),
             "max_pc": float(c["max_pc"]), "age_days": float(c["element_age_at_tca_days"]), "stale": bool(c["elements_stale"]),
             "triage": c["triage"], "source": "snapshot", "plane_m": None}
        e["tracked"] = e["triage"] != "NOISE"
        if e["tracked"]:                         # the encounter-plane point is only drawn for the ones that matter
            if k not in self._planes:
                self._planes[k] = O.encounter(self.fleet[e["fleet_sat"]], self.obj(e["norad_cat_id"]), tca)["plane_m"]
            e["plane_m"] = self._planes[k]
        return e

    def reset(self):
        """Back to the start of the week, exactly as first loaded."""
        self.events = {}
        for c in self.x["conjunctions"]:
            k = f"{c['fleet_sat']}|{int(c['norad_cat_id'])}|{O.utc(c['tca_utc']).strftime('%Y%m%dT%H%M')}"
            self.events[k] = self._from_row(k, c)
        self.moments = {m: self._key(v["fleet_sat"], v["norad_cat_id"]) for m, v in self.sc["moments"].items()}
        self.t = 0.0
        self.speed_i = 1
        self.playing = False
        self.cards: list[dict] = []
        self.fired: set = set()
        self.overrides: dict[int, dict] = {}     # norad -> OMM, once a (simulated) tracking update has arrived
        self.burns: dict[str, dict] = {}         # event key -> the approved burn
        self.waiting: dict | None = None         # the agent card the clock is paused for
        self.focus = self.moments.get("A")
        self.fire((0.0, "start", "start"))      # the opening cards are on screen before anyone presses play

    # ------------------------------------------------------------------------------------------ time
    def now(self):
        return self.t0 + timedelta(seconds=self.t)

    def at(self, s):
        return self.t0 + timedelta(seconds=s)

    def _s(self, t):
        return (t - self.t0).total_seconds()

    def triggers(self) -> list[tuple[float, str, str]]:
        """Everything the watcher will act on, in time order, that has not fired yet."""
        r = self.rules
        out = [(0.0, "start", "start")]
        for k, e in self.events.items():
            ts = self._s(e["tca"])
            if e["triage"] == "ESCALATE" and not e["stale"] and ts - self.t_min_act() > 0:
                out.append((max(0.0, ts - r["decision_lead_h"] * 3600), "decide", k))
            if e["tracked"]:
                out.append((ts, "pass", k))
        for i, u in enumerate(self.sc.get("tracking_updates", [])):
            out.append((self._s(O.utc(u["arrives_utc"])), "update", str(i)))
        for k, b in self.burns.items():
            out.append((self._s(O.utc(b["burn_utc"])), "burn", k))
        return sorted(x for x in out if (x[1], x[2]) not in self.fired and x[0] <= self.t_end_s)

    def t_min_act(self):
        return self.rules["act_limit_min"] * 60

    def next_trigger(self):
        ts = [x for x in self.triggers() if x[0] >= self.t]
        return ts[0] if ts else None

    def advance(self, real_dt: float) -> list[dict]:
        """Move the clock by real_dt seconds of wall time at the current speed. Returns the watcher's actions
        (cards and wake-ups) in order. Stops exactly at a trigger that wakes the agent."""
        acts = []
        if not self.playing or self.waiting:
            return acts
        target = min(self.t_end_s, self.t + real_dt * self.speeds[self.speed_i]["x"])
        while True:
            nt = self.next_trigger()
            if nt is None or nt[0] > target:
                break
            self.t = max(self.t, nt[0])
            acts += self.fire(nt)
            if self.waiting:
                return acts
        self.t = target
        if self.t >= self.t_end_s:
            self.playing = False
        return acts

    def skip_to_next(self) -> dict | None:
        """Jump to just before the next thing that matters, and slow down so the room sees it happen:
        a pass at 1x through its last 90 seconds; anything else a minute early at 1 min/s. If we are already
        inside that lead-in, go on to the thing after it. Nothing is skipped over: every trigger on the way
        fires in order, and a skip stops early at one that wakes the agent."""
        lead = lambda x: 90.0 if x[1] == "pass" else 60.0
        nt = next((x for x in self.triggers() if x[1] != "start" and x[0] - lead(x) > self.t + 0.5), None)
        if nt is None:
            return None
        target = nt[0] - lead(nt)
        acts = []
        while True:
            t = self.next_trigger()
            if t is None or t[0] > target:
                break
            self.t = max(self.t, t[0])
            acts += self.fire(t)
            if self.waiting:
                return {"kind": t[1], "key": t[2], "at_utc": O.iso(self.at(t[0])), "acts": acts, "stopped_early": True}
        self.t = target
        self.speed_i = 0 if nt[1] == "pass" else 1
        if nt[1] == "pass":
            self.focus = nt[2]
        self.playing = True
        return {"kind": nt[1], "key": nt[2], "at_utc": O.iso(self.at(nt[0])), "acts": acts}

    # ------------------------------------------------------------------------------------------ the watcher
    def card(self, kind, title, lines, level="info", key=None, **extra) -> dict:
        c = {"id": f"c{len(self.cards) + 1}", "who": kind, "at_utc": O.iso(self.now()), "at": fmt(self.now()),
             "title": title, "lines": lines, "level": level, "event": key, **extra}
        self.cards.append(c)
        return c

    def fire(self, trig) -> list[dict]:
        ts, kind, key = trig
        self.fired.add((kind, key))
        return getattr(self, f"_on_{kind}")(key)

    def _describe(self, e) -> str:
        return f"{e['fleet_sat']} vs {e['object_name']} ({e['norad_cat_id']})"

    def _on_start(self, _):
        evs = sorted(self.events.values(), key=lambda e: e["tca"])
        n = {t: sum(1 for e in evs if e["triage"] == t) for t in ("ESCALATE", "WATCH", "NOISE")}
        acts = [{"card": self.card("watcher", "Screen loaded: the week ahead", [
            f"{len(evs)} approaches under 10 km in the next 7 days across our 12 satellites.",
            f"{n['ESCALATE']} ESCALATE (worst-case Pc at or above {self.rules['escalate_pc']:.0e}), {n['WATCH']} WATCH "
            f"(under {self.rules['watch_m']:,.0f} m), {n['NOISE']} noise.",
            f"Snapshot {self.sc.get('snapshot')}: fixed for this demo, so every run is the same."], "info")}]
        for e in evs:
            if not e["tracked"]:
                continue
            to_tca = self._s(e["tca"]) - self.t
            if to_tca < self.t_min_act():
                acts.append({"card": self.card("watcher", f"Too late to act: {self._describe(e)}", [
                    f"Closest approach {fmt(e['tca'])}, in {span(to_tca)}: {e['miss_m']:,.1f} m, worst-case Pc {fmt_pc(e['max_pc'])}.",
                    f"We cannot plan, command and execute a burn in under {self.rules['act_limit_min']:.0f} minutes. Logged; watching the pass."],
                    "watch", e["key"])})
            elif e["stale"]:
                acts.append({"card": self.card("watcher", f"Fresh tracking requested: {self._describe(e)}", [
                    f"Closest approach {fmt(e['tca'])}: {e['miss_m']:,.1f} m, {e['triage']}.",
                    f"The object's elements will be {e['age_days']:.2f} days old at closest approach (stale beyond "
                    f"{self.rules['stale_days']:.0f}). Nothing to decide on old tracking: fresh elements requested."],
                    "watch", e["key"])})
        return acts

    def _on_decide(self, key):
        e = self.events[key]
        self.focus = key
        m = next((v for v in self.sc["moments"].values() if self._key(v["fleet_sat"], v["norad_cat_id"]) == key), {})
        slots = [s for s in m.get("burn_slots_utc", []) if O.utc(s) > self.now()]
        brief = self.brief_decide(e, slots)
        return self._wake(key, "decide", f"Decision needed: {self._describe(e)}", brief,
                          [f"Closest approach {fmt(e['tca'])}, in {span(self._s(e['tca']) - self.t)}: {e['miss_m']:,.1f} m, "
                           f"worst-case Pc {fmt_pc(e['max_pc'])}, tracking fresh. Waking the agent."])

    def _on_update(self, idx):
        u = self.sc["tracking_updates"][int(idx)]
        key = self._key(u["fleet_sat"], u["norad_cat_id"])
        e = self.events[key]
        before = {k: e[k] for k in ("miss_m", "max_pc", "triage", "age_days", "stale")}
        self.overrides[int(u["norad_cat_id"])] = u["omm"]
        r = u["result"]
        e.update(tca=O.utc(r["tca_utc"]), miss_m=r["miss_m"], radial_m=r["radial_m"], in_track_m=r["in_track_m"],
                 cross_track_m=r["cross_track_m"], rel_speed_km_s=r["rel_speed_km_s"], max_pc=r["max_pc"],
                 age_days=r["element_age_at_tca_days"], stale=r["elements_stale"], plane_m=r["plane_m"],
                 source="SIMULATED update", before=before)
        e["triage"] = self._triage(e["miss_m"], e["max_pc"], True)
        self.focus = key
        acts = [{"card": self.card("watcher", f"Fresh tracking: {e['object_name']} ({e['norad_cat_id']}) [SIMULATED]", [
            f"New elements, epoch {fmt(O.utc(u['epoch_utc']))}. They supersede the snapshot for this object.",
            f"Recomputed {self._describe(e)}: {before['miss_m']:,.1f} m → {e['miss_m']:,.1f} m; worst-case Pc "
            f"{fmt_pc(before['max_pc'])} → {fmt_pc(e['max_pc'])}; tracking {e['age_days']:.2f} days old at closest approach.",
            "SIMULATED: made by console/make_scenario.py from the snapshot's own elements."], "info", key, simulated=True)}]
        acts += self._wake(key, "update", f"Re-assess on fresh tracking: {self._describe(e)}", self.brief_update(e, u, before),
                           ["Waking the agent to re-assess."])
        return acts

    def _on_burn(self, key):
        b = self.burns[key]
        e = self.events[key]
        b["status"] = "executed"
        e["before_burn"] = {"miss_m": e["miss_m"], "max_pc": e["max_pc"], "plane_m": e["plane_m"]}
        e.update(miss_m=b["miss_after_m"], max_pc=O.max_pc(b["miss_after_m"], self.rules["hbr_m"]),
                 plane_m=b.get("plane_after_m") or e["plane_m"], source=e["source"] + " + burn")
        if b.get("tca_after_utc"):
            e["tca"] = O.utc(b["tca_after_utc"])
        if b.get("ric_after_m"):
            e["radial_m"], e["in_track_m"], e["cross_track_m"] = b["ric_after_m"]
        e["triage"] = self._triage(e["miss_m"], e["max_pc"], True)
        self.focus = key
        return [{"card": self.card("watcher", f"Burn executed: {e['fleet_sat']}", [
            f"{b['delta_v_m_s']} m/s {b['direction']} at {fmt(O.utc(b['burn_utc']))}.",
            f"Predicted miss with {e['object_name']} now {e['miss_m']:,.0f} m (was {e['before_burn']['miss_m']:,.1f} m); "
            f"worst-case Pc {fmt_pc(e['max_pc'])}. Cost: {b.get('cost_days', '?')} days of mission life."], "ok", key)}]

    def _on_pass(self, key):
        e = self.events[key]
        burned = key in self.burns and self.burns[key]["status"] == "executed"
        lines = [f"Closest approach {fmt(e['tca'])}: {e['miss_m']:,.1f} m at {e['rel_speed_km_s']:.1f} km/s, "
                 f"worst-case Pc {fmt_pc(e['max_pc'])}."]
        if burned:
            lines.append(f"Without the burn it would have been {e['before_burn']['miss_m']:,.1f} m.")
        elif e.get("before"):
            lines.append(f"On the snapshot's tracking it was predicted at {e['before']['miss_m']:,.1f} m; "
                         f"the fresh tracking [SIMULATED] said {e['miss_m']:,.0f} m. No propellant spent.")
        elif key in self.burns:
            lines.append("The burn was held; no propellant spent.")
        lvl = "ok" if e["max_pc"] < self.rules["clear_pc"] else "watch" if e["triage"] != "ESCALATE" else "escalate"
        return [{"card": self.card("watcher", f"Pass: {self._describe(e)}", lines, lvl, key)}]

    # ------------------------------------------------------------------------------------------ the agent
    def _wake(self, key, why, title, brief, lines):
        e = self.events[key]
        c = self.card("agent", title, lines, "escalate" if e["triage"] == "ESCALATE" else "watch", key,
                      status="thinking", why=why, brief=brief)
        self.waiting = c
        self.playing = False                      # time stops while the desk decides
        return [{"card": c, "wake": {"card_id": c["id"], "key": key, "why": why, "brief": brief,
                                     "sim_now_utc": O.iso(self.now()), "overrides": dict(self.overrides)}}]

    def brief_decide(self, e, slots):
        s = [f"WATCHER ALERT. Sim time now: {fmt(self.now())}.",
             f"{self._describe(e)}: closest approach {fmt(e['tca'])}, {span(self._s(e['tca']) - self.t)} from now.",
             f"Screened miss {e['miss_m']:,.1f} m, worst-case Pc {fmt_pc(e['max_pc'])} ({e['triage']}); the object's "
             f"elements will be {e['age_days']:.2f} days old at closest approach (fresh)."]
        if slots:
            s.append("Command windows for a burn: " + " and ".join(fmt(O.utc(x)) for x in slots) + ".")
        s.append("Assess it with assess_conjunction; size the smallest prograde burn that clears it at each command "
                 "window in ONE run_in_sandbox call; cost each with maneuver_cost; recommend one; and finish with "
                 "build_assessment. Keep your reply under 120 words.")
        return "\n".join(s)

    def brief_update(self, e, u, before):
        return "\n".join([
            f"WATCHER ALERT. Sim time now: {fmt(self.now())}.",
            f"Fresh tracking for {e['object_name']} ({e['norad_cat_id']}) has arrived (epoch {fmt(O.utc(u['epoch_utc']))}). "
            "It is a SIMULATED update for this demo; it supersedes the snapshot's row for this object, and "
            "assess_conjunction will use it.",
            f"The watcher's recompute for {e['fleet_sat']}: miss {before['miss_m']:,.1f} m → {e['miss_m']:,.1f} m, "
            f"worst-case Pc {fmt_pc(before['max_pc'])} → {fmt_pc(e['max_pc'])}, closest approach {fmt(e['tca'])}.",
            "Earlier the tracking was stale, so fresh tracking was requested instead of a burn. Re-assess with "
            "assess_conjunction, say whether any burn is still needed, and finish with build_assessment. "
            "Keep your reply under 100 words."])

    def agent_result(self, card_id: str, assessment: dict | None, text: str, error: str | None = None) -> dict:
        c = next(c for c in self.cards if c["id"] == card_id)
        c["status"] = "error" if error else "ready"
        c["text"] = text
        c["error"] = error
        c["assessment"] = assessment
        if assessment:
            rec = assessment.get("recommendation")
            m = assessment.get("maneuver") or {}
            c["recommendation"] = rec
            c["summary"] = (f"{rec}: {m['delta_v_m_s']} m/s {m['direction']} at {fmt(O.utc(m['burn_utc']))} → "
                            f"miss {m['miss_after_m']:,.0f} m, {m['cost_days_of_mission_life']} days of life"
                            if rec == "MANEUVER" and m else f"{rec}")
        c["actions"] = ["approve", "hold"]
        return c

    def decide(self, card_id: str, choice: str, local_check=None) -> list[dict]:
        """Approve or Hold on an agent card. Approving a MANEUVER schedules its burn. local_check(event, maneuver)
        may return the console's own re-run of the burn (RIC after, plane point) to draw it."""
        c = next(c for c in self.cards if c["id"] == card_id)
        c["decision"] = choice
        c["actions"] = []
        acts = []
        a = c.get("assessment") or {}
        key = c["event"]
        if choice == "approve" and a.get("recommendation") == "MANEUVER" and a.get("maneuver"):
            m = a["maneuver"]
            b = {"burn_utc": O.iso(O.utc(m["burn_utc"])), "delta_v_m_s": m["delta_v_m_s"], "direction": m.get("direction", "prograde"),
                 "miss_after_m": float(m["miss_after_m"]), "cost_days": m.get("cost_days_of_mission_life"), "status": "scheduled"}
            if local_check:
                b.update(local_check(self.events[key], b) or {})
            self.burns[key] = b
            acts.append({"card": self.card("watcher", f"Burn scheduled: {self.events[key]['fleet_sat']}", [
                f"Approved by the operator: {b['delta_v_m_s']} m/s {b['direction']} at {fmt(O.utc(b['burn_utc']))}.",
                f"Predicted miss after: {b['miss_after_m']:,.0f} m."
                + (f" Console re-check: {b['check_miss_m']:,.0f} m." if b.get("check_miss_m") else "")], "ok", key)})
        elif choice == "approve":
            acts.append({"card": self.card("watcher", f"Approved: {a.get('recommendation', 'recommendation')}", [
                "No burn. Watching the pass."], "ok", key)})
        else:
            acts.append({"card": self.card("watcher", "Held by the operator", ["No action taken. The clock runs on."], "watch", key)})
        if self.waiting and self.waiting["id"] == card_id:
            self.waiting = None
            self.playing = True
        return acts

    # ------------------------------------------------------------------------------------------ what the page draws
    def range_km(self, e, t=None) -> float:
        t = t or self.now()
        dt = (t - e["tca"]).total_seconds()
        if abs(dt) < NEAR_TCA_S:
            return math.hypot(e["miss_m"] / 1000.0, e["rel_speed_km_s"] * dt)
        o = self.obj(e["norad_cat_id"], self.overrides.get(e["norad_cat_id"]))
        rs, _ = O.rv(self.fleet[e["fleet_sat"]], t)
        ro, _ = O.rv(o, t)
        return float(((rs - ro) ** 2).sum() ** 0.5)

    def fleet_board(self):
        rank = {"ESCALATE": 0, "WATCH": 1, "CLEAR": 2, "NOISE": 3}
        out = []
        for name in sorted(self.fleet):
            up = [e for e in self.events.values() if e["fleet_sat"] == name and e["tca"] > self.now()]
            w = min(up, key=lambda e: (rank[e["triage"]], -e["max_pc"])) if up else None
            out.append({"sat": name, "triage": (w["triage"] if w["triage"] != "CLEAR" else "CLEARED") if w else "CLEAR",
                        "event": w["key"] if w else None,
                        "next": f"{w['object_name']} {fmt_short(w['tca'])} {w['miss_m']:,.0f} m" if w else "nothing under 10 km"})
        return out

    def event_view(self, e) -> dict:
        v = {k: e[k] for k in ("key", "fleet_sat", "norad_cat_id", "object_name", "object_type", "miss_m", "radial_m",
                               "in_track_m", "cross_track_m", "rel_speed_km_s", "max_pc", "age_days", "stale", "triage",
                               "source", "plane_m", "tracked")}
        v.update(tca_utc=O.iso(e["tca"], "milliseconds"), tca=fmt(e["tca"]), t_s=self._s(e["tca"]))
        if e.get("before_burn"):
            v["plane_before_m"] = e["before_burn"]["plane_m"]
        if e.get("before"):
            v["before"] = e["before"]
        if e["key"] in self.burns:
            v["burn"] = self.burns[e["key"]]
        return v

    def state(self) -> dict:
        now = self.now()
        f = self.events.get(self.focus) if self.focus else None
        nt = next((x for x in self.triggers() if x[0] > self.t), None)
        return {
            "now_utc": O.iso(now), "now": fmt(now), "t_s": self.t, "end_s": self.t_end_s, "playing": self.playing,
            "speed_i": self.speed_i, "speeds": self.speeds, "waiting": self.waiting["id"] if self.waiting else None,
            "rules": self.rules, "snapshot": self.sc.get("snapshot"),
            "next": {"kind": nt[1], "at": fmt(self.at(nt[0])), "in": span(nt[0] - self.t)} if nt else None,
            "fleet": self.fleet_board(),
            "events": [self.event_view(e) for e in sorted(self.events.values(), key=lambda e: e["tca"])],
            "focus": dict(self.event_view(f), range_km=round(self.range_km(f), 3),
                          to_tca_s=(f["tca"] - now).total_seconds()) if f else None,
            "cards": self.cards,
        }

    # controls
    def play(self, on: bool):
        if not self.waiting:
            self.playing = on

    def set_speed(self, i: int):
        self.speed_i = max(0, min(len(self.speeds) - 1, int(i)))

    def set_focus(self, key):
        if key in self.events:
            self.focus = key
