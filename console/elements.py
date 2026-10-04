"""Moving an element set to a new epoch, and nudging it along its own track. Used to make the one simulated
tracking update in the scenario (console/make_scenario.py), and by the offline tests.

SGP4's mean elements change steadily with time: the mean anomaly, the node and the argument of perigee each
advance at a constant (secular) rate that SGP4 works out when it initialises an element set. sgp4 2.27 exposes
those rates on the Satrec object as mdot, nodedot and argpdot, in radians per minute (mdot includes the mean
motion itself). Moving an element set to a new epoch with those rates is most of the job, but not all of it:
SGP4 also applies drag to the mean anomaly with terms that grow as t squared and faster, and those are not
secular rates. Over five days that leaves the moved set kilometres from where the original set says the object
is. So we re-anchor: three small corrections (mean anomaly, mean motion, node) that put the moved set back on the
original set's position at the time that matters (anchor()). THEN a fresh measurement moves the object a little:
we simulate that as a further shift along its own track, which is how tracking updates mostly differ in practice.
"""
import math
from datetime import datetime

import numpy as np
from scipy.optimize import brentq

import orbits as O


def to_epoch(rec: dict, new_epoch: datetime) -> dict:
    s = O.satrec(rec)
    dt_min = (O.utc(new_epoch) - O.utc(rec["EPOCH"])).total_seconds() / 60.0
    out = dict(rec)
    out["EPOCH"] = O.utc(new_epoch).strftime("%Y-%m-%dT%H:%M:%S.%f")
    out["MEAN_ANOMALY"] = (float(rec["MEAN_ANOMALY"]) + math.degrees(s.mdot * dt_min)) % 360
    out["RA_OF_ASC_NODE"] = (float(rec["RA_OF_ASC_NODE"]) + math.degrees(s.nodedot * dt_min)) % 360
    out["ARG_OF_PERICENTER"] = (float(rec["ARG_OF_PERICENTER"]) + math.degrees(s.argpdot * dt_min)) % 360
    rev = float(rec.get("REV_AT_EPOCH") or 0) + float(rec["MEAN_MOTION"]) * dt_min / 1440.0
    out["REV_AT_EPOCH"] = str(int(rev))
    out["ELEMENT_SET_NO"] = str(int(float(rec.get("ELEMENT_SET_NO") or 0)) + 1)
    return out


def shift_anomaly(rec: dict, dm_deg: float) -> dict:
    out = dict(rec)
    out["MEAN_ANOMALY"] = (float(rec["MEAN_ANOMALY"]) + dm_deg) % 360
    return out


def anchor(orig: dict, moved: dict, at):
    """Re-anchor a moved element set to the original's prediction at time `at`.

    SGP4's drag shows up mostly along-track (the mean anomaly) and as a slowly rising mean motion, with a hair
    of node. So we fit three small corrections (mean anomaly in degrees, mean motion in rev/day, node in degrees)
    until the moved set puts the object exactly where the original set does at `at`. Deterministic: a fixed
    start and a least-squares solve. Returns (anchored set, the corrections, metres apart before, metres after).
    """
    from scipy.optimize import least_squares
    target = O.rv(O.satrec(orig), at)[0]

    def make(x):
        r = shift_anomaly(moved, x[0])
        r["MEAN_MOTION"] = float(moved["MEAN_MOTION"]) + x[1] * 1e-4
        r["RA_OF_ASC_NODE"] = (float(moved["RA_OF_ASC_NODE"]) + x[2]) % 360
        return r

    resid = lambda x: (O.rv(O.satrec(make(x)), at)[0] - target) * 1000.0
    before = float(np.linalg.norm(resid([0.0, 0.0, 0.0])))
    # start from the best pure along-track shift on a fixed grid, then solve for all three
    grid = np.linspace(-2.0, 2.0, 401)
    g0 = float(grid[int(np.argmin([np.linalg.norm(resid([g, 0.0, 0.0])) for g in grid]))])
    sol = least_squares(resid, [g0, 0.0, 0.0], x_scale=[0.01, 1.0, 0.01], xtol=1e-14, ftol=1e-14, gtol=1e-14)
    x = sol.x
    return make(x), {"mean_anomaly_deg": round(float(x[0]), 7), "mean_motion_rev_day": round(float(x[1]) * 1e-4, 9),
                     "raan_deg": round(float(x[2]), 9)}, before, float(np.linalg.norm(sol.fun))


def miss_with(sat, rec: dict, tca_guess, window_s=300.0):
    ob = O.satrec(rec)
    t = O.closest(sat, ob, tca_guess, window_s)
    return float(np.linalg.norm(O.rv(sat, t)[0] - O.rv(ob, t)[0])) * 1000.0, t


def tune_miss(sat, rec: dict, tca_guess, target_m: float, span_deg=0.2, steps=81):
    """The smallest mean-anomaly shift (degrees) that makes the miss equal target_m. Deterministic: a fixed
    grid to bracket the root, then Brent's method."""
    grid = np.linspace(-span_deg, span_deg, steps)
    vals = [miss_with(sat, shift_anomaly(rec, g), tca_guess)[0] - target_m for g in grid]
    roots = []
    for a, b, fa, fb in zip(grid[:-1], grid[1:], vals[:-1], vals[1:]):
        if fa == 0 or fa * fb < 0:
            roots.append(brentq(lambda x: miss_with(sat, shift_anomaly(rec, x), tca_guess)[0] - target_m, a, b, xtol=1e-9))
    if not roots:
        raise ValueError(f"no shift within ±{span_deg}° gives a {target_m} m miss (closest {min(vals) + target_m:.0f} m)")
    return min(roots, key=abs)
