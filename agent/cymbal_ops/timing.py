"""Where a turn's time goes, one line per step, in the service's logs.

Every line starts with [timing] and says how far into the turn it is, so on Cloud Run you can filter the logs
for "[timing]" and read one question from start to answer. Locally the lines go to the terminal.
Set A4I_TIMING_LOGS=0 to turn them off.
"""
import os
import time

ON = os.environ.get("A4I_TIMING_LOGS", "1") != "0"
_turn = {"t0": None}
_tools: dict[str, float] = {}


def log(msg: str) -> None:
    if ON:
        t0 = _turn["t0"]
        since = f"+{time.perf_counter() - t0:6.1f}s" if t0 else "   (no turn)"
        print(f"[timing] {since}  {msg}", flush=True)


def before_agent(callback_context):
    _turn["t0"] = time.perf_counter()
    log("turn started")
    return None


def after_agent(callback_context):
    log("turn finished")
    return None


def before_tool(tool, args, tool_context):
    _tools[tool_context.function_call_id or tool.name] = time.perf_counter()
    return None


def after_tool(tool, args, tool_context, tool_response):
    t = _tools.pop(tool_context.function_call_id or tool.name, None)
    log(f"tool {tool.name}: {time.perf_counter() - t:.1f}s" if t else f"tool {tool.name} done")
    return None
