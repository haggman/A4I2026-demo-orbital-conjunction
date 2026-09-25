"""orbit_whatif — the physics the agent runs inside its Agent Runtime code sandbox.

The sandbox has numpy and scipy but no sgp4 and no network, so the agent's setup uploads sgp4's own
pure-Python modules as sgp4_pure.zip beside this file. Everything here is plain functions returning
plain dicts, so the code the model writes can stay three lines long:

    import orbit_whatif as ow
    case = ow.load_case("case_CYMBAL-04_31178.json")      # staged by the assess_conjunction tool
    print(ow.smallest_burn(case, "2026-09-25T08:00:00Z"))

How a burn is modelled. Public elements are SGP4 mean elements, and you cannot add a velocity change
to mean elements directly. So we keep SGP4 as the baseline for both objects and compute only the
*difference* a burn makes: integrate our satellite twice from the burn time with a two-body + J2
model—once as-is, once with the delta-v added—and add that difference to the SGP4 position. Whatever
the simple model gets wrong, it gets wrong the same way in both integrations, and cancels.
"""
import json, math, sys
from datetime import datetime, timezone

sys.path.insert(0, "sgp4_pure.zip")
import numpy as np                                   # noqa: E402
from scipy.integrate import solve_ivp                # noqa: E402
from sgp4.api import Satrec                          # noqa: E402
from sgp4 import omm                                 # noqa: E402

MU, RE, J2 = 398600.4418, 6378.137, 1.08262668e-3    # km^3/s^2, km, —


# ---------------------------------------------------------------------------- loading
def _satrec(fields):
    f = {k: str(v) for k, v in fields.items()}
    if "." not in f["EPOCH"]:
        f["EPOCH"] += ".000000"
    s = Satrec()
    omm.initialize(s, f)
    return s


def _utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def load_case(path):
    """Read a case file staged by the agent's assess_conjunction tool."""
    with open(path) as fh:
        c = json.load(fh)
    c["_sat"], c["_obj"] = _satrec(c["fleet_omm"]), _satrec(c["object_omm"])
    c["_now"] = _utc(c["now_utc"])
    return c


def _t(case, when):
    """Seconds from the case's 'now' for an ISO time string (or a number of seconds)."""
    return float(when) if isinstance(when, (int, float)) else (_utc(when) - case["_now"]).total_seconds()


def _iso(case, t_s):
    return datetime.fromtimestamp(case["_now"].timestamp() + t_s, tz=timezone.utc).isoformat(timespec="seconds")


def _rv(s, case, t_s):
    jd, fr = _jd(case["_now"])
    e, r, v = s.sgp4(jd, fr + t_s / 86400.0)
    if e != 0:
        raise ValueError(f"SGP4 error {e} at t={t_s:.0f}s")
    return np.array(r), np.array(v)


def _jd(dt):
    from sgp4.api import jday
    return jday(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second + dt.microsecond / 1e6)


# ---------------------------------------------------------------------------- geometry
def _ric(r_sat, v_sat, r_obj):
    R = r_sat / np.linalg.norm(r_sat)
    C = np.cross(r_sat, v_sat); C /= np.linalg.norm(C)
    I = np.cross(C, R)
    d = (r_obj - r_sat) * 1000.0
    return {"radial_m": round(float(d @ R), 1), "in_track_m": round(float(d @ I), 1), "cross_track_m": round(float(d @ C), 1)}


def _closest(case, sat_pos, t_guess, half_window=120.0):
    """Closest approach between sat_pos(t) and the object, searched around t_guess (seconds)."""
    def d(t):
        return float(np.linalg.norm(sat_pos(t)[0] - _rv(case["_obj"], case, t)[0]))
    ts = np.arange(t_guess - half_window, t_guess + half_window, 1.0)
    t0 = float(ts[int(np.argmin([d(t) for t in ts]))])
    a, b = t0 - 1.0, t0 + 1.0
    g = (math.sqrt(5) - 1) / 2
    x1, x2 = b - g * (b - a), a + g * (b - a)
    f1, f2 = d(x1), d(x2)
    for _ in range(40):
        if f1 < f2:
            b, x2, f2 = x2, x1, f1; x1 = b - g * (b - a); f1 = d(x1)
        else:
            a, x1, f1 = x1, x2, f2; x2 = a + g * (b - a); f2 = d(x2)
    t = (a + b) / 2
    r_s, v_s = sat_pos(t)
    r_o, v_o = _rv(case["_obj"], case, t)
    return t, float(np.linalg.norm(r_o - r_s)) * 1000.0, _ric(r_s, v_s, r_o), float(np.linalg.norm(v_o - v_s))


def max_pc(miss_m, hbr_m):
    """Worst-case collision probability over every isotropic position uncertainty (small-object form)."""
    return min(1.0, hbr_m ** 2 / (math.e * miss_m ** 2)) if miss_m > 3 * hbr_m else 1.0


def miss_needed(pc_target, hbr_m):
    """The miss distance at which the worst-case probability falls to pc_target."""
    return hbr_m / math.sqrt(math.e * pc_target)


def baseline(case):
    """Re-measure the approach exactly as screened: time, miss, geometry, worst-case risk."""
    t, miss, ric, vrel = _closest(case, lambda t: _rv(case["_sat"], case, t), case["tca_s"])
    return {"fleet_sat": case["fleet_sat"], "object": case["object_name"], "tca_utc": _iso(case, t),
            "miss_m": round(miss, 1), **ric, "rel_speed_km_s": round(vrel, 2),
            "max_pc": max_pc(miss, case["hbr_m"]), "hbr_m": case["hbr_m"]}


# ---------------------------------------------------------------------------- burns
def _accel(_, y):
    r, v = y[:3], y[3:]
    rn = np.linalg.norm(r)
    z2 = (r[2] / rn) ** 2
    k = 1.5 * J2 * MU * RE ** 2 / rn ** 5
    a = -MU * r / rn ** 3 + k * np.array([r[0] * (5 * z2 - 1), r[1] * (5 * z2 - 1), r[2] * (5 * z2 - 3)])
    return np.concatenate([v, a])


def _burned(case, t_burn, dv_rtn_m_s, t_end):
    """sat_pos(t) for our satellite with a burn at t_burn: SGP4 baseline plus the integrated difference."""
    r0, v0 = _rv(case["_sat"], case, t_burn)
    R = r0 / np.linalg.norm(r0); N = np.cross(r0, v0); N /= np.linalg.norm(N); T = np.cross(N, R)
    dv = (dv_rtn_m_s[0] * R + dv_rtn_m_s[1] * T + dv_rtn_m_s[2] * N) / 1000.0
    kw = dict(method="DOP853", rtol=1e-11, atol=1e-9, dense_output=True)
    a = solve_ivp(_accel, (t_burn, t_end), np.concatenate([r0, v0]), **kw)
    b = solve_ivp(_accel, (t_burn, t_end), np.concatenate([r0, v0 + dv]), **kw)

    def pos(t):
        r, v = _rv(case["_sat"], case, t)
        ya, yb = a.sol(t), b.sol(t)
        return r + (yb[:3] - ya[:3]), v + (yb[3:] - ya[3:])
    return pos


def whatif(case, burn_utc, delta_v_m_s, direction="prograde"):
    """Apply one burn and re-measure the approach.

    direction: 'prograde' (along the direction of travel, +), 'retrograde' (−), 'radial' (away from Earth)
    or 'normal' (out of the orbit plane). delta_v_m_s is the magnitude in metres per second.
    """
    t_b = _t(case, burn_utc)
    if t_b >= case["tca_s"] - 60:
        raise ValueError("The burn has to happen before the closest approach—and realistically hours before it.")
    vec = {"prograde": (0, delta_v_m_s, 0), "retrograde": (0, -delta_v_m_s, 0),
           "radial": (delta_v_m_s, 0, 0), "normal": (0, 0, delta_v_m_s)}[direction]
    pos = _burned(case, t_b, vec, case["tca_s"] + 900)
    t, miss, ric, vrel = _closest(case, pos, case["tca_s"], half_window=300.0)
    base = baseline(case)
    return {"burn_utc": _iso(case, t_b), "hours_before_tca": round((case["tca_s"] - t_b) / 3600, 2),
            "delta_v_m_s": delta_v_m_s, "direction": direction,
            "miss_before_m": base["miss_m"], "miss_after_m": round(miss, 1), "tca_after_utc": _iso(case, t),
            **{k + "_after": v for k, v in ric.items()},
            "max_pc_before": base["max_pc"], "max_pc_after": max_pc(miss, case["hbr_m"])}


def _unit_response(case, t_b, direction, t_end, probe=0.01):
    """How far one metre per second of burn moves us, as a function of time.

    For burns of a metre per second or less the orbit's response is linear to a very good approximation,
    so we integrate once with a small probe burn and scale—instead of integrating again for every guess.
    """
    vec = {"prograde": (0, probe, 0), "retrograde": (0, -probe, 0), "radial": (probe, 0, 0), "normal": (0, 0, probe)}[direction]
    burned = _burned(case, t_b, vec, t_end)
    def delta(t):
        r1, v1 = burned(t); r0, v0 = _rv(case["_sat"], case, t)
        return (r1 - r0) / probe, (v1 - v0) / probe
    return delta


def smallest_burn(case, burn_utc, pc_target=None, direction="prograde", dv_max=1.0):
    """The smallest burn at burn_utc that brings the worst-case probability below pc_target.

    pc_target defaults to the case's 'clear' line. The search uses the linear response for speed, then the
    answer is re-checked with a full, separate integration—and that re-check is what is returned.
    """
    pc_target = pc_target or case["clear_pc"]
    need = miss_needed(pc_target, case["hbr_m"])
    t_b = _t(case, burn_utc)
    if t_b >= case["tca_s"] - 60:
        raise ValueError("The burn has to happen before the closest approach—and realistically hours before it.")
    unit = _unit_response(case, t_b, direction, case["tca_s"] + 900)
    # One-second samples, and at each one the straight-line closest approach inside that second—the same
    # trick as the screen. At 7-15 km/s, the minimum over raw samples alone would miss by kilometres.
    grid = np.arange(case["tca_s"] - 300, case["tca_s"] + 300, 1.0)
    o = [_rv(case["_obj"], case, t) for t in grid]; b0 = [_rv(case["_sat"], case, t) for t in grid]
    u = [unit(t) for t in grid]
    ro, vo = np.array([x[0] for x in o]), np.array([x[1] for x in o])
    rb, vb = np.array([x[0] for x in b0]), np.array([x[1] for x in b0])
    ru, vu = np.array([x[0] for x in u]), np.array([x[1] for x in u])

    def miss_lin(dv):
        p = ro - (rb + dv * ru); w = vo - (vb + dv * vu)
        tau = np.clip(-np.einsum("ij,ij->i", p, w) / np.einsum("ij,ij->i", w, w), -0.5, 0.5)
        return float(np.min(np.linalg.norm(p + w * tau[:, None], axis=1))) * 1000.0
    ok = lambda dv: miss_lin(dv) >= need
    if not ok(dv_max):
        return {"feasible": False, "reason": f"even {dv_max} m/s at {burn_utc} does not reach {need:.0f} m",
                "miss_needed_m": round(need, 1)}
    lo, hi = 0.0, dv_max
    for _ in range(30):                                # bisection to well under a millimetre per second
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if ok(mid) else (mid, hi)
        if hi - lo < 1e-5:
            break
    dv = math.ceil(hi * 1e4) / 1e4                     # round UP to 0.1 mm/s, so the answer still clears
    out = whatif(case, burn_utc, dv, direction)
    for _ in range(20):                                # the full integration is the judge; nudge up until it agrees
        if out["miss_after_m"] >= need:
            break
        dv = math.ceil(dv * 1.01 * 1e4) / 1e4
        out = whatif(case, burn_utc, dv, direction)
    else:
        return {"feasible": False, "reason": "the linear estimate and the full integration disagree; widen dv_max",
                "miss_needed_m": round(need, 1)}
    out.update({"feasible": True, "pc_target": pc_target, "miss_needed_m": round(need, 1)})
    return out
