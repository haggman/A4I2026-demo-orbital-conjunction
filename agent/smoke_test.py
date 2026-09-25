"""Ask the agent what an operator would ask, headless, and print one diagnostic block.

    python agent/smoke_test.py              # after python agent/setup_sandbox.py
    python agent/smoke_test.py --quick      # two questions instead of six

It runs the agent in-process (no Cloud Run needed) against the a4i_orbit tables, and checks the things the
demo depends on: the managed MCP server answered, our tools ran, code ran in the sandbox, and an
assessment was produced. It prints what each turn did and how long it took.
"""
import argparse
import asyncio
import json
import os
import platform
import sys
import time
from importlib import metadata
from pathlib import Path

HERE = Path(__file__).resolve().parent

QUESTIONS = [
    "What should we worry about this week?",
    "Tell me about the object CYMBAL-04 meets tonight. Where did it come from, and how sure are you about the risk?",
    "What is the smallest burn that gets CYMBAL-04 clear? Compare burning at 04:00 and at 12:00 UTC today, and tell me what each costs.",
    "And CYMBAL-11's rocket body on Thursday: should we burn for that one?",
    "What can't you see?",
    "Write up the assessment for CYMBAL-04 with your recommendation.",
]
MCP_TOOLS = {"execute_sql_readonly", "get_table_info", "list_table_ids"}


def _env():
    f = HERE / "cymbal_ops" / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


async def run(questions):
    sys.path.insert(0, str(HERE))
    from google.adk.runners import InMemoryRunner
    from google.genai import types
    from cymbal_ops.agent import root_agent

    runner = InMemoryRunner(agent=root_agent, app_name="cymbal_ops")
    sess = await runner.session_service.create_session(app_name="cymbal_ops", user_id="smoke")
    turns = []
    for q in questions:
        t0, calls, errors, code, results, text = time.perf_counter(), [], [], [], [], []
        timeline, started, tool_s, thought_chars = [], {}, {}, 0
        try:
            async for ev in runner.run_async(user_id="smoke", session_id=sess.id,
                                             new_message=types.Content(role="user", parts=[types.Part(text=q)])):
                t = round(time.perf_counter() - t0, 1)
                kinds = []
                for p in (ev.content.parts if ev.content and ev.content.parts else []):
                    if p.function_call:
                        calls.append(p.function_call.name)
                        started[p.function_call.id or p.function_call.name] = t
                        kinds.append(f"call:{p.function_call.name}")
                    if p.function_response:
                        r = p.function_response.response or {}
                        name = p.function_response.name
                        t_start = started.get(p.function_response.id or name)
                        if t_start is not None:
                            tool_s.setdefault(name, []).append(round(t - t_start, 1))
                        kinds.append(f"result:{name}")
                        if isinstance(r, dict) and ("error" in r or r.get("isError")):
                            errors.append({name: str(r)[:300]})
                    if p.executable_code:
                        code.append(p.executable_code.code[:400])
                        kinds.append("code")
                    if p.code_execution_result:
                        results.append(str(p.code_execution_result.output)[:600])
                        kinds.append(f"sandbox:{str(p.code_execution_result.outcome).split('.')[-1]}")
                    if p.text and p.thought:
                        thought_chars += len(p.text)
                        kinds.append(f"thought({len(p.text)})")
                    elif p.text:
                        text.append(p.text)
                        kinds.append(f"text({len(p.text)})")
                fr = getattr(ev, "finish_reason", None)
                if getattr(ev, "error_code", None) or (fr and "STOP" not in str(fr)):
                    kinds.append(f"END finish_reason={fr} error_code={ev.error_code} {(ev.error_message or '')[:160]}")
                    if ev.error_code:
                        errors.append({"model": f"{ev.error_code}: {(ev.error_message or '')[:200]}"})
                if not kinds:
                    kinds.append("(no content)")
                timeline.append(f"{t:>6}s {ev.author}: " + ", ".join(kinds))
        except Exception as e:                       # a failed turn is a finding, not the end of the run
            errors.append({"exception": f"{type(e).__name__}: {str(e)[:400]}"})
        turns.append({"q": q, "seconds": round(time.perf_counter() - t0, 1), "tool_calls": calls, "errors": errors,
                      "tool_seconds": tool_s, "thought_chars": thought_chars, "timeline": timeline,
                      "code": code, "code_results": results, "answer": "".join(text)[-1500:]})
        print(f"\n### {q}\n[{turns[-1]['seconds']} s] tools={calls} code_blocks={len(code)} errors={len(errors)}")
        print("\n".join(timeline))
        print(turns[-1]["answer"][:1200] or "(NO ANSWER TEXT)")
    s = await runner.session_service.get_session(app_name="cymbal_ops", user_id="smoke", session_id=sess.id)
    return turns, dict(s.state)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    _env()
    qs = QUESTIONS[:1] + QUESTIONS[2:3] if a.quick else QUESTIONS
    t0 = time.perf_counter()
    turns, state = asyncio.run(run(qs))
    from cymbal_ops import config
    from cymbal_ops.agent import EMPTY_REPLIES
    calls = [c for t in turns for c in t["tool_calls"]]
    checks = {
        "managed BigQuery MCP server answered": bool(MCP_TOOLS & set(calls)),
        "assess_conjunction ran": "assess_conjunction" in calls,
        "code ran in the sandbox": any(t["code_results"] for t in turns),
        "the sandbox ran orbit_whatif": any("miss_after_m" in r for t in turns for r in t["code_results"]),
        "maneuver_cost ran": "maneuver_cost" in calls,
        "no tool returned an error": not any(t["errors"] for t in turns),
        "every turn ended with an answer": all(t["answer"].strip() for t in turns),
    }
    if not a.quick:
        checks["an assessment was built"] = isinstance(state.get("assessment"), dict)
    vers = {p: (metadata.version(p) if p in {d.metadata["Name"] for d in metadata.distributions()} else None)
            for p in ("google-adk", "google-genai", "google-cloud-aiplatform", "google-cloud-bigquery", "sgp4")}
    block = {"python": sys.version.split()[0], "platform": platform.platform(), "versions": vers,
             "project": os.environ.get("GOOGLE_CLOUD_PROJECT"), "sandbox": os.environ.get("A4I_SANDBOX"),
             "model": f"{config.MODEL} @ {config.MODEL_LOCATION}, thinking {config.THINKING_LEVEL}",
             "total_s": round(time.perf_counter() - t0, 1),
             "empty_model_replies_retried": EMPTY_REPLIES,
             "checks": {k: ("PASS" if v else "FAIL") for k, v in checks.items()},
             "assessment": (state.get("assessment") or {}).get("markdown"), "turns": turns}
    print("\n===== A4I DEMO AGENT — SMOKE TEST DIAGNOSTIC BLOCK =====")
    print(json.dumps(block, indent=1, default=str))
    print("===== END =====")
    sys.exit(0 if all(checks.values()) else 1)


if __name__ == "__main__":
    main()
