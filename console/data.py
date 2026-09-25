"""The slice of the snapshot the console needs, read once from BigQuery and kept in a local file.

The console's clock, watcher and pictures run on four things: our twelve satellites, every screened approach
(the `conjunctions` table), the elements of every object in those approaches, and the snapshot's stated
assumptions. That is a few hundred rows, so we read them once and keep them in `console/.snapshot_extract.json`
(git-ignored: the repository carries no orbital data, see data/README.md). The agent still reads BigQuery itself.

    python console/data.py            # read BigQuery, write the extract, print what it holds
    python console/data.py --show     # print what the extract holds, without touching BigQuery

A4I_CONSOLE_EXTRACT points somewhere else (the offline tests use it).
"""
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXTRACT = Path(os.environ.get("A4I_CONSOLE_EXTRACT", HERE / ".snapshot_extract.json"))
OMM = ["OBJECT_NAME", "OBJECT_ID", "EPOCH", "MEAN_MOTION", "ECCENTRICITY", "INCLINATION", "RA_OF_ASC_NODE",
       "ARG_OF_PERICENTER", "MEAN_ANOMALY", "EPHEMERIS_TYPE", "CLASSIFICATION_TYPE", "NORAD_CAT_ID",
       "ELEMENT_SET_NO", "REV_AT_EPOCH", "BSTAR", "MEAN_MOTION_DOT", "MEAN_MOTION_DDOT"]


def _plain(v):
    if isinstance(v, datetime):
        v = v.astimezone(timezone.utc) if v.tzinfo else v.replace(tzinfo=timezone.utc)
        return v.isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(v, date):
        return v.isoformat()
    if hasattr(v, "item"):                       # numpy scalars
        return v.item()
    return v


def omm_fields(rec: dict) -> dict:
    """OMM fields as the strings sgp4.omm.initialize wants (strict EPOCH format, integer counters)."""
    f = {k: str(rec[k]) for k in OMM}
    e = f["EPOCH"].replace(" ", "T").replace("Z", "").split("+")[0]
    f["EPOCH"] = e if "." in e else e + ".000000"
    for k in ("ELEMENT_SET_NO", "REV_AT_EPOCH", "EPHEMERIS_TYPE"):
        f[k] = f[k] if f[k].strip().lstrip("-").isdigit() else "0"
    f["CLASSIFICATION_TYPE"] = f["CLASSIFICATION_TYPE"] if f["CLASSIFICATION_TYPE"] not in ("", "None") else "U"
    return f


def export() -> dict:
    sys.path.insert(0, str(HERE.parent / "agent"))
    from cymbal_ops import config                  # project and dataset, from demo.env
    from google.cloud import bigquery
    bq = bigquery.Client(project=config.PROJECT)
    D = f"`{config.PROJECT}.{config.DATASET}`"
    rows = lambda sql: [{k: _plain(v) for k, v in dict(r).items()} for r in bq.query_and_wait(sql)]
    conj = rows(f"SELECT * FROM {D}.conjunctions ORDER BY tca_utc")
    ids = sorted({int(c["norad_cat_id"]) for c in conj})
    cols = ", ".join(OMM + ["OBJECT_TYPE", "OPS_STATUS_CODE", "PERIGEE_KM", "APOGEE_KM", "ELEMENT_AGE_DAYS", "PARENT_EVENT"])
    objs = rows(f"SELECT {cols} FROM {D}.catalog WHERE NORAD_CAT_ID IN ({','.join(map(str, ids))})") if ids else []
    out = {"source": f"{config.PROJECT}.{config.DATASET}", "exported_utc": _plain(datetime.now(timezone.utc)),
           "snapshot_info": rows(f"SELECT * FROM {D}.snapshot_info")[0],
           "fleet": rows(f"SELECT * FROM {D}.fleet ORDER BY OBJECT_NAME"),
           "conjunctions": conj, "objects": {str(int(o["NORAD_CAT_ID"])): o for o in objs}}
    EXTRACT.write_text(json.dumps(out, indent=0, default=str))
    return out


def load() -> dict:
    if not EXTRACT.exists():
        raise SystemExit(f"No snapshot extract at {EXTRACT}. Run: python console/data.py")
    return json.loads(EXTRACT.read_text())


def show(d: dict) -> None:
    info = d["snapshot_info"]
    tri = {}
    for c in d["conjunctions"]:
        tri[c["triage"]] = tri.get(c["triage"], 0) + 1
    print(f"extract {EXTRACT.name}: {d['source']}, snapshot {info.get('snapshot')}, screen start {info.get('screen_start_utc')}")
    print(f"  fleet {len(d['fleet'])} · approaches {len(d['conjunctions'])} {tri} · objects {len(d['objects'])}")
    for c in d["conjunctions"]:
        if c["triage"] != "NOISE" or float(c["hours_from_now"]) < 1:
            print(f"  {c['fleet_sat']:<10} {c['object_name']:<22} {int(c['norad_cat_id']):>6}  {c['tca_utc'][:19]}  "
                  f"{float(c['miss_m']):>8.1f} m  Pc {float(c['max_pc']):.2e}  age {c['element_age_at_tca_days']} d  "
                  f"{'STALE ' if c['elements_stale'] else ''}{c['triage']}")


if __name__ == "__main__":
    show(load() if "--show" in sys.argv else export())
