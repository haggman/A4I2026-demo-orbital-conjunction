"""Cymbal Orbital's conjunction-assessment agent.

One ADK agent, three kinds of tool:
- BigQuery's Google-managed MCP server, read-only, for any question the tables can answer;
- three tools we wrote, for the judgment (assess_conjunction, maneuver_cost, build_assessment);
- an Agent Runtime code sandbox for the orbital what-ifs: through our run_in_sandbox tool by default, or through
  ADK's AgentEngineSandboxCodeExecutor (A4I_CODE_PATH=executor).
"""
import asyncio
import logging
import os
import random
import time

import google.auth
import google.auth.transport.requests
from google.adk.agents import LlmAgent
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.genai import types

from . import config, timing
from .prompt import INSTRUCTION
from .tools import assess_conjunction, build_assessment, maneuver_cost, run_in_sandbox

log = logging.getLogger("cymbal_ops")

if not config.SANDBOX:
    raise RuntimeError("A4I_SANDBOX is not set. Run `python agent/setup_sandbox.py` first; it writes agent/cymbal_ops/.env.")

# Gemini is served from the global endpoint; the sandbox's region comes from its own resource name.
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
os.environ["GOOGLE_CLOUD_PROJECT"] = config.PROJECT
os.environ["GOOGLE_CLOUD_LOCATION"] = config.MODEL_LOCATION

# Every model try that failed (too slow, or empty) and was retried: the smoke test prints these.
RETRIES: list[dict] = []
EMPTY_REPLIES = RETRIES          # the name the smoke test used first
_NUDGE = ("Your last reply was empty. Carry on from where you were: if code just ran, read its output above and "
          "answer the operator's question in full, calling maneuver_cost for every burn you quote.")
_RETRYABLE = {None, "STOP", "FINISH_REASON_UNSPECIFIED", "UNEXPECTED_TOOL_CALL", "MALFORMED_FUNCTION_CALL", "OTHER"}


def _has_code(r) -> bool:
    parts = r.content.parts if r.content and r.content.parts else []
    return any(p.executable_code or (p.text and "```python" in p.text and not p.thought) for p in parts)


def _useful(r) -> bool:
    """True if a response carries something the operator or the flow can use: words, a tool call or code."""
    parts = r.content.parts if r.content and r.content.parts else []
    return any((p.text and p.text.strip() and not p.thought) or p.function_call or p.executable_code for p in parts)


class DemoGemini(Gemini):
    """Gemini, made fit for a stage: three things on top of ADK's Gemini class.

    1. A reply that contains code is passed on WITHOUT its finish reason. ADK 2.7.0 runs the code, then blanks
       the reply so the flow will ask the model again ("look at the output, carry on"). But a later check sees
       a blank reply that says finish_reason=STOP, flags it MODEL_RETURNED_NO_CONTENT, and ends the turn right
       there: the code runs, and the operator never hears what it found. With no finish reason on the reply,
       that check stands aside and the flow loops back to the model, as the code executor intends.
       (Streaming turns, which adk web can use, skip that check already.)
    2. Patience, with exponential backoff. Each try gets a time limit (A4I_MODEL_TIMEOUT_S, doubling each retry),
       and a pause between tries (1, 2, 4, then 8 s at most), up to A4I_MODEL_ATTEMPTS tries in all. A try is
       abandoned if it runs out of time before any words arrive; once words are streaming, it is left to finish.
       HTTP 429 and 5xx answers are retried with the same backoff inside the client.
    3. If a reply comes back with nothing in it (no words, no tool call, no code), it counts as a failed try.
       Gemini sometimes answers MALFORMED_FUNCTION_CALL; a second sample usually comes back well-formed. After
       plain text (such as sandbox output) we add a one-line nudge; after a tool result we resend the request
       unchanged, because in testing, adding text to a tool result made the API answer 400 ("ending with a
       model turn").
    """

    async def generate_content_async(self, llm_request, stream: bool = False):
        if not getattr(self, "_where_logged", False):   # once: which endpoint are we really calling?
            c = getattr(self.api_client, "_api_client", None)
            timing.log(f"Gemini client: model {llm_request.model}, vertex {getattr(c, 'vertexai', '?')}, "
                       f"project {getattr(c, 'project', '?')}, location {getattr(c, 'location', '?')}, "
                       f"thinking {config.THINKING_LEVEL or '(not sent)'}")
            object.__setattr__(self, "_where_logged", True)
        for attempt in range(config.MODEL_ATTEMPTS):
            last_try = attempt == config.MODEL_ATTEMPTS - 1
            limit = config.MODEL_TIMEOUT_S * 2 ** attempt if config.MODEL_TIMEOUT_S > 0 else None
            held, useful, streaming, timed_out, t0 = [], False, False, False, time.perf_counter()
            timing.log(f"model call {attempt + 1} sent ({len(llm_request.contents)} contents"
                       + (f", limit {limit:g}s)" if limit else ")"))
            replies = super().generate_content_async(llm_request, stream).__aiter__()
            try:
                while True:
                    try:
                        if limit and not streaming:
                            left = max(0.1, limit - (time.perf_counter() - t0))
                            r = await asyncio.wait_for(replies.__anext__(), timeout=left)
                        else:
                            r = await replies.__anext__()
                    except StopAsyncIteration:
                        break
                    useful = useful or _useful(r)
                    if not r.partial and _has_code(r) and not r.error_code:
                        r.finish_reason = None      # fix 1, above
                    if r.partial:
                        streaming = True            # words are on screen: no more time limit, no retry
                        yield r
                    else:
                        held.append(r)              # the complete reply waits until we know it is not empty
            except asyncio.TimeoutError:
                timed_out = True
            finally:
                await replies.aclose()
            last = held[-1] if held else None
            reason = "TIMEOUT" if timed_out else (str(getattr(last, "finish_reason", None) or "").split(".")[-1] or None)
            um = getattr(last, "usage_metadata", None)
            timing.log(f"model reply: {time.perf_counter() - t0:.1f}s, finish {reason}, tokens in "
                       f"{getattr(um, 'prompt_token_count', '?')} think {getattr(um, 'thoughts_token_count', 0) or 0} "
                       f"out {getattr(um, 'candidates_token_count', '?')}")
            if not timed_out and (useful or streaming or last_try or reason not in _RETRYABLE):
                for r in held:
                    yield r
                return
            if timed_out and last_try:
                yield LlmResponse(error_code="MODEL_TIMEOUT", error_message=(
                    f"Gemini ({config.MODEL}) did not answer in {config.MODEL_ATTEMPTS} tries. The endpoint may be "
                    "busy: try again, or switch A4I_MODEL (python agent/model_check.py times the candidates)."))
                return
            RETRIES.append({"try": attempt + 1, "reason": reason, "error_code": getattr(last, "error_code", None),
                            "seconds": round(time.perf_counter() - t0, 1)})
            pause = min(config.BACKOFF_MAX_S, config.BACKOFF_FIRST_S * 2 ** attempt) + random.uniform(0, 0.5)
            log.warning("Model try %d: %s after %.1fs; trying again in %.1fs.", attempt + 1, reason,
                        time.perf_counter() - t0, pause)
            timing.log(f"model try {attempt + 1} {reason}; backing off {pause:.1f}s")
            await asyncio.sleep(pause)
            if not timed_out:
                tail = llm_request.contents[-1] if llm_request.contents else None
                if tail is not None and tail.role == "user" and not any(p.function_response for p in tail.parts or []):
                    if not any(p.text == _NUDGE for p in tail.parts or []):
                        tail.parts = list(tail.parts or []) + [types.Part(text=_NUDGE)]


_creds = None


def _bigquery_auth(_ctx) -> dict[str, str]:
    """A fresh bearer token for every MCP request. Tokens expire after an hour; demos run longer."""
    global _creds
    if _creds is None:
        _creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/bigquery"])
    if not _creds.valid:
        _creds.refresh(google.auth.transport.requests.Request())
    return {"Authorization": f"Bearer {_creds.token}", "x-goog-user-project": config.PROJECT}


class TimedMcpToolset(McpToolset):
    """ADK asks the toolset for its tools before every model call; on a new connection that means an MCP
    handshake with BigQuery. Log how long it takes, because it is the step most likely to differ between
    Cloud Shell and Cloud Run."""

    async def get_tools(self, readonly_context=None):
        t0 = time.perf_counter()
        tools = await super().get_tools(readonly_context)
        timing.log(f"BigQuery MCP tool list: {time.perf_counter() - t0:.1f}s ({len(tools)} tools)")
        return tools


bigquery_mcp = TimedMcpToolset(
    connection_params=StreamableHTTPConnectionParams(url="https://bigquery.googleapis.com/mcp", timeout=30.0),
    header_provider=_bigquery_auth,
    tool_filter=["execute_sql_readonly", "get_table_info", "list_table_ids"],   # read-only, on purpose
)

model = DemoGemini(
    model=config.MODEL,
    # The global endpoint, explicitly, whatever region Cloud Run or Cloud Shell sets for everything else.
    client_kwargs={"vertexai": True, "project": config.PROJECT, "location": config.MODEL_LOCATION},
    # A busy endpoint answers 429 or 503 now and then: retry with exponential backoff (1, 2, 4 s, ...).
    retry_options=types.HttpRetryOptions(attempts=config.MODEL_ATTEMPTS, initial_delay=config.BACKOFF_FIRST_S,
                                         max_delay=config.BACKOFF_MAX_S, exp_base=2.0),
)

# The sandbox, reached one of two ways (config.CODE_PATH). By default, a function tool: the model calls
# run_in_sandbox(code) and our tool runs it in the Agent Runtime sandbox. Or ADK's own code executor, which runs
# ```python blocks from the model's reply in the same sandbox. ADK's executor also accepts ```tool_code and shows
# output back fenced as ```tool_output, which is how Gemini's built-in code tool talks; this agent does not have
# that tool, so we keep to ```python in, and output that says where it came from.
TOOLS = [bigquery_mcp, assess_conjunction, maneuver_cost, build_assessment]
if config.CODE_PATH == "executor":
    code_executor = AgentEngineSandboxCodeExecutor(
        sandbox_resource_name=config.SANDBOX,
        code_block_delimiters=[("```python\n", "\n```")],
        execution_result_delimiters=("Sandbox output (the code above ran in the Agent Runtime sandbox):\n```\n", "\n```"),
    )
else:
    code_executor = None
    TOOLS.insert(2, run_in_sandbox)

root_agent = LlmAgent(
    name="cymbal_ops",
    model=model,
    description="Conjunction assessment and maneuver planning for Cymbal Orbital's (fictional) constellation.",
    instruction=INSTRUCTION,
    tools=TOOLS,
    code_executor=code_executor,
    before_agent_callback=timing.before_agent,
    after_agent_callback=timing.after_agent,
    before_tool_callback=timing.before_tool,
    after_tool_callback=timing.after_tool,
    generate_content_config=config.generate_config(),   # thinking level and service tier, from demo.env
)
