"""Small orbital helpers the console shares: elements to SGP4, positions at a time, closest approach, the
encounter plane, and the worst-case probability. No model, no cloud: plain SGP4 on the pinned elements.

The same conventions as the notebook's screen and the sandbox's orbit_whatif: TEME positions in km from SGP4,
RIC = radial / in-track / cross-track from our satellite's point of view, and the worst case over every
isotropic uncertainty for the probability.
"""
import math
from datetime import datetime, timedelta, timezone  # noqa: F401 (timedelta re-exported)

import numpy as np
from sgp4 import omm as _omm
from sgp4.api import Satrec, jday

from data import omm_fields

UTC = timezone.utc


def utc(s) -> datetime:
    if isinstance(s, datetime):
        return s.astimezone(UTC) if s.tzinfo else s.replace(tzinfo=UTC)
    t = datetime.fromisoformat(str(s).replace("Z", "+00:00").replace(" ", "T"))
    return t.astimezone(UTC) if t.tzinfo else t.replace(tzinfo=UTC)     # a bare time is UTC, never local


def iso(t: datetime, spec="seconds") -> str:
    return t.astimezone(UTC).isoformat(timespec=spec).replace("+00:00", "Z")


def satrec(rec: dict) -> Satrec:
    s = Satrec()
    _omm.initialize(s, omm_fields(rec))
    return s


def rv(s: Satrec, t: datetime):
    t = utc(t)
    jd, fr = jday(t.year, t.month, t.day, t.hour, t.minute, t.second + t.microsecond / 1e6)
    e, r, v = s.sgp4(jd, fr)
    if e:
        raise ValueError(f"SGP4 error {e} at {iso(t)}")
    return np.array(r), np.array(v)


def closest(sat: Satrec, obj: Satrec, guess: datetime, half_window_s=120.0):
    """Closest approach near `guess`: a one-second scan, then golden-section to the millisecond (as the notebook)."""
    d = lambda s: float(np.linalg.norm(rv(sat, guess + timedelta(seconds=s))[0] - rv(obj, guess + timedelta(seconds=s))[0]))
    ts = np.arange(-half_window_s, half_window_s + 1, 1.0)
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
    return guess + timedelta(seconds=(a + b) / 2)


def ric_basis(r, v):
    R = r / np.linalg.norm(r)
    C = np.cross(r, v); C /= np.linalg.norm(C)
    return R, np.cross(C, R), C


def encounter_basis(r_sat, v_sat, v_obj):
    """The plane perpendicular to the relative velocity at closest approach.
    e1 = our radial direction with its along-v_rel part removed; e2 = v_rel_hat x e1."""
    w = (v_obj - v_sat); w = w / np.linalg.norm(w)
    R = r_sat / np.linalg.norm(r_sat)
    e1 = R - (R @ w) * w; e1 /= np.linalg.norm(e1)
    return e1, np.cross(w, e1)


def max_pc(miss_m, hbr_m):
    return min(1.0, hbr_m ** 2 / (math.e * miss_m ** 2)) if miss_m > 3 * hbr_m else 1.0


def miss_needed(pc, hbr_m):
    return hbr_m / math.sqrt(math.e * pc)


def encounter(sat: Satrec, obj: Satrec, tca: datetime) -> dict:
    """Everything the console draws about one approach, at its closest point."""
    rs, vs = rv(sat, tca)
    ro, vo = rv(obj, tca)
    d = (ro - rs) * 1000.0
    R, I, C = ric_basis(rs, vs)
    e1, e2 = encounter_basis(rs, vs, vo)
    return {"tca_utc": iso(tca, "milliseconds"), "miss_m": round(float(np.linalg.norm(d)), 1),
            "radial_m": round(float(d @ R), 1), "in_track_m": round(float(d @ I), 1), "cross_track_m": round(float(d @ C), 1),
            "rel_speed_km_s": round(float(np.linalg.norm(vo - vs)), 3),
            "plane_m": [round(float(d @ e1), 1), round(float(d @ e2), 1)]}


def ric_to_plane(sat: Satrec, obj: Satrec, tca: datetime, radial_m, in_track_m, cross_track_m):
    """A miss given in our RIC frame (as the sandbox reports it after a burn), drawn in the same encounter plane."""
    rs, vs = rv(sat, tca)
    _, vo = rv(obj, tca)
    R, I, C = ric_basis(rs, vs)
    e1, e2 = encounter_basis(rs, vs, vo)
    d = radial_m * R + in_track_m * I + cross_track_m * C
    return [round(float(d @ e1), 1), round(float(d @ e2), 1)]
