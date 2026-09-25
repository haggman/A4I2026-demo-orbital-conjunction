"""The flight dynamics console: one FastAPI service, with the simulator and the agent in-process.

    uvicorn console.app:app --port 8080         # from the repo root, after `source scripts/activate.sh`

Then Cloud Shell's Web Preview > Preview on port 8080. One worker only: the clock, the watcher and the agent's
session live in this process (Cloud Run runs it as one instance, for the same reason).

Settings (environment):
  A4I_CONSOLE_MODE        live (default) or replay
  A4I_CONSOLE_REPLAY      the recording replay mode plays (console/recordings/<name>.json; default: rehearsal)
Every live run records itself to console/recordings/run-<UTC time>.json, a new file each time the week restarts,
so a live run on stage can never overwrite the rehearsal you meant to keep. Keep a good one by renaming it
(e.g. to rehearsal.json) and committing it.
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import agent_bridge                              # noqa: E402
import data                                      # noqa: E402
import physics                                   # noqa: E402
from sim import Sim                              # noqa: E402

TICK_S = 0.1
app = FastAPI(title="Cymbal Orbital flight dynamics console")
SIM = Sim(data.load(), json.loads((HERE / "scenario.json").read_text()))
CHECK = physics.checker(SIM)
STATE = {"mode": os.environ.get("A4I_CONSOLE_MODE", "live"), "replay": os.environ.get("A4I_CONSOLE_REPLAY", "rehearsal"),
         "recording": None, "agent": None, "agent_error": None, "chat": [], "busy": False}


def make_agent():
    try:
        if STATE["mode"] == "replay":
            STATE["recording"] = STATE["replay"]
            STATE["agent"] = agent_bridge.ReplayAgent(STATE["replay"])
        else:
            STATE["recording"] = "run-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
            STATE["agent"] = agent_bridge.LiveAgent(record_to=STATE["recording"])
        STATE["agent_error"] = None
    except Exception as e:                       # e.g. no sandbox configured, or no such recording
        STATE["agent"], STATE["agent_error"] = None, f"{type(e).__name__}: {e}"


async def handle_wake(w: dict):
    card = next(c for c in SIM.cards if c["id"] == w["card_id"])
    card["steps"] = []
    card["mode"] = STATE["mode"]

    async def on_step(s):
        card["steps"].append(s)

    agent = STATE["agent"]
    if agent is None:
        SIM.agent_result(w["card_id"], None, "", error=f"No agent: {STATE['agent_error']}")
        return
    STATE["busy"] = True
    try:
        out = await agent.turn(w["brief"], w["sim_now_utc"], w["overrides"], on_step, kind="alert",
                               meta={"key": w["key"], "why": w["why"], "card_title": card["title"]})
    finally:
        STATE["busy"] = False
    card["seconds"] = out["seconds"]
    card["replayed_from"] = out.get("replayed_from")
    err = out["error"] if not out["assessment"] else None
    SIM.agent_result(w["card_id"], out["assessment"], out["text"], error=err)


async def ticker():
    last = time.perf_counter()
    while True:
        await asyncio.sleep(TICK_S)
        now = time.perf_counter()
        for a in SIM.advance(now - last):
            if "wake" in a:
                asyncio.create_task(handle_wake(a["wake"]))
        last = now


@app.on_event("startup")
async def startup():
    make_agent()
    asyncio.create_task(ticker())


@app.get("/")
def page():
    return FileResponse(HERE / "static" / "index.html")


@app.get("/static/{name}")
def static(name: str):
    p = (HERE / "static" / name).resolve()
    if p.parent != (HERE / "static").resolve() or not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@app.get("/api/state")
def state():
    s = SIM.state()
    s["events_n"] = len(s.pop("events"))
    s.update(mode=STATE["mode"], recording=STATE["recording"], agent_error=STATE["agent_error"], busy=STATE["busy"],
             chat=STATE["chat"][-30:], recordings=agent_bridge.recordings(),
             burns={k: v for k, v in SIM.burns.items()})
    return JSONResponse(s)


@app.get("/api/events")
def events():
    return JSONResponse([e for e in SIM.state()["events"]])


class Control(BaseModel):
    action: str
    value: str | int | float | None = None


@app.post("/api/control")
async def control(c: Control):
    if c.action == "play":
        SIM.play(True)
    elif c.action == "pause":
        SIM.play(False)
    elif c.action == "speed":
        SIM.set_speed(int(c.value))
    elif c.action == "skip":
        r = SIM.skip_to_next() or {}
        for a in r.pop("acts", []):
            if "wake" in a:
                asyncio.create_task(handle_wake(a["wake"]))
        return {"skipped_to": r}
    elif c.action == "focus":
        SIM.set_focus(str(c.value))
    elif c.action == "reset":
        SIM.reset()
        STATE["chat"] = []
        make_agent()
    elif c.action == "mode":                    # "live", or "replay:<recording>"
        mode, _, name = str(c.value).partition(":")
        if mode not in ("live", "replay"):
            raise HTTPException(400, "mode is live or replay")
        STATE["mode"] = mode
        if name:
            STATE["replay"] = name
        SIM.reset()
        STATE["chat"] = []
        make_agent()
    else:
        raise HTTPException(400, f"unknown action {c.action}")
    return {"ok": True}


class Decision(BaseModel):
    card_id: str
    choice: str


@app.post("/api/decide")
async def decide(d: Decision):
    if d.choice not in ("approve", "hold"):
        raise HTTPException(400, "approve or hold")
    # the console's own re-run of an approved burn takes a second or two: keep it off the event loop
    loop = asyncio.get_running_loop()
    acts = await loop.run_in_executor(None, lambda: SIM.decide(d.card_id, d.choice, CHECK))
    return {"ok": True, "cards": [a["card"]["id"] for a in acts]}


class Chat(BaseModel):
    text: str


@app.post("/api/chat")
async def chat(m: Chat):
    agent = STATE["agent"]
    if agent is None:
        raise HTTPException(503, f"No agent: {STATE['agent_error']}")
    entry = {"q": m.text, "at": SIM.state()["now"], "at_utc": SIM.state()["now_utc"] + "~", "a": None, "steps": []}
    STATE["chat"].append(entry)

    async def on_step(s):
        entry["steps"].append(s)

    out = await agent.turn(m.text, SIM.state()["now_utc"], SIM.overrides, on_step, kind="chat")
    entry["a"], entry["error"], entry["seconds"] = out["text"], out["error"], out["seconds"]
    return entry
