"""The console's line to the agent: the same root_agent as adk web and Cloud Run, run in-process with ADK's
InMemoryRunner, in ONE session that the watcher's alerts and the chat box share.

Before every turn the console sets the session's clock and fresh tracking (state_delta): state["sim_now_utc"] and
state["element_overrides"]. The agent's instruction and tools read them (agent/cymbal_ops/prompt.py, tools.py).
An alert turn ends with build_assessment, which leaves the structured result in state["assessment"]; the card's
Approve / Hold is built from that, never from parsing the model's words.

Recording and replay: every live alert turn is written to console/recordings/<name>.json as it happened (the brief,
each tool step with its time, the words, the assessment). In replay mode the same turns play back at the same sim
moments, with the same steps and a short typing delay, and no model call. A recording is only ever made by a
real run: this file has no way to write one by hand.
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RECORDINGS = HERE / "recordings"
APP, USER = "cymbal_console", "operator"


def _label(call) -> str:
    a = dict(call.args or {})
    if call.name == "assess_conjunction":
        return f"assess_conjunction({a.get('fleet_sat')}, {a.get('norad_cat_id')})"
    if call.name == "maneuver_cost":
        return f"maneuver_cost({a.get('delta_v_m_s')} m/s)"
    if call.name == "run_in_sandbox":
        return "run_in_sandbox: orbital what-ifs in the Agent Runtime sandbox"
    if call.name == "build_assessment":
        return f"build_assessment: {a.get('recommendation')}"
    if call.name == "execute_sql_readonly":
        return "BigQuery (MCP): execute_sql_readonly"
    return call.name


class LiveAgent:
    mode = "live"

    def __init__(self, record_to: str | None = None):
        sys.path.insert(0, str(HERE.parent / "agent"))
        from cymbal_ops.agent import root_agent            # the one agent, unchanged
        from google.adk.runners import InMemoryRunner
        self.runner = InMemoryRunner(agent=root_agent, app_name=APP)
        self.session_id = None
        self.lock = asyncio.Lock()                          # one turn at a time: it is one desk
        self.record_to = RECORDINGS / f"{record_to}.json" if record_to else None
        self.recording = {"made_utc": None, "model": os.environ.get("A4I_MODEL"), "turns": []}

    async def _session(self):
        if self.session_id is None:
            s = await self.runner.session_service.create_session(app_name=APP, user_id=USER)
            self.session_id = s.id
        return self.session_id

    async def reset(self):
        self.session_id = None
        self.recording["turns"] = []

    async def turn(self, text: str, sim_now_utc: str, overrides: dict, on_step=None, kind="chat", meta=None) -> dict:
        """One turn. on_step(label) is called as each tool starts, so the card can show the work as it happens."""
        from google.genai import types
        async with self.lock:
            sid = await self._session()
            t0 = time.perf_counter()
            steps, words, errors = [], [], []
            delta = {"sim_now_utc": sim_now_utc, "element_overrides": {str(k): v for k, v in (overrides or {}).items()},
                     "assessment": None}
            try:
                async for ev in self.runner.run_async(user_id=USER, session_id=sid, state_delta=delta,
                                                      new_message=types.Content(role="user", parts=[types.Part(text=text)])):
                    for p in (ev.content.parts if ev.content and ev.content.parts else []):
                        if p.function_call:
                            s = {"t": round(time.perf_counter() - t0, 1), "step": _label(p.function_call)}
                            steps.append(s)
                            if on_step:
                                await on_step(s)
                        elif p.text and not p.thought and ev.author != "user" and not ev.partial:
                            words.append(p.text)
                    if ev.error_code:
                        errors.append(f"{ev.error_code}: {ev.error_message or ''}".strip())
            except Exception as e:                           # the desk must never hang on one bad turn
                errors.append(f"{type(e).__name__}: {str(e)[:300]}")
            session = await self.runner.session_service.get_session(app_name=APP, user_id=USER, session_id=sid)
            out = {"kind": kind, "text": "\n".join(w.strip() for w in words if w.strip()),
                   "assessment": session.state.get("assessment") if kind == "alert" else None,
                   "steps": steps, "seconds": round(time.perf_counter() - t0, 1), "error": "; ".join(errors) or None}
            if kind == "alert" and self.record_to:
                self._record(dict(out, brief=text, sim_now_utc=sim_now_utc, **(meta or {})))
            return out

    def _record(self, turn):
        RECORDINGS.mkdir(exist_ok=True)
        self.recording["made_utc"] = self.recording["made_utc"] or datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.recording["turns"].append(turn)
        self.record_to.write_text(json.dumps(self.recording, indent=1, default=str) + "\n")


class ReplayAgent:
    """Plays a recording back: each alert turn at the matching sim moment (by the event and the reason it woke),
    with its tool steps and words on the recorded rhythm, compressed so no step waits more than a few seconds."""
    mode = "replay"

    def __init__(self, name: str, max_step_s: float = 2.5):
        self.path = RECORDINGS / f"{name}.json"
        self.rec = json.loads(self.path.read_text())
        self.max_step_s = max_step_s

    async def reset(self):
        pass

    async def turn(self, text, sim_now_utc, overrides, on_step=None, kind="chat", meta=None) -> dict:
        if kind != "alert":
            return {"kind": kind, "text": "Replay mode: the chat needs the live agent. Switch to live to ask questions.",
                    "assessment": None, "steps": [], "seconds": 0, "error": None}
        m = meta or {}
        t = next((t for t in self.rec["turns"] if t.get("key") == m.get("key") and t.get("why") == m.get("why")), None)
        if t is None:
            return {"kind": kind, "text": "", "assessment": None, "steps": [], "seconds": 0,
                    "error": f"No recorded turn for {m.get('why')} {m.get('key')} in {self.path.name}."}
        last = 0.0
        for s in t["steps"]:
            await asyncio.sleep(min(self.max_step_s, max(0.4, s["t"] - last)))
            last = s["t"]
            if on_step:
                await on_step(s)
        await asyncio.sleep(1.0)
        return {"kind": kind, "text": t["text"], "assessment": t["assessment"], "steps": t["steps"],
                "seconds": t["seconds"], "error": t.get("error"), "replayed_from": self.path.name}


def recordings() -> list[str]:
    return sorted(p.stem for p in RECORDINGS.glob("*.json") if not p.name.startswith(".")) if RECORDINGS.exists() else []
