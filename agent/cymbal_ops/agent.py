"""Cymbal Orbital's conjunction-assessment agent.

One ADK agent, three kinds of tool:
- BigQuery's Google-managed MCP server, read-only, for any question the tables can answer;
- three tools we wrote, for the judgment (assess_conjunction, maneuver_cost, build_assessment);
- an Agent Runtime code sandbox for the orbital what-ifs: through our run_in_sandbox tool by default, or through
  ADK's AgentEngineSandboxCodeExecutor (A4I_CODE_PATH=executor).
"""
import logging
import os
import time

import google.auth
import google.auth.transport.requests
from google.adk.agents import LlmAgent
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
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

# Every time the model came back empty and we asked again: the smoke test prints these.
EMPTY_REPLIES: list[dict] = []
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
    """Gemini, with two fixes for running ADK's code executor on stage.

    1. A reply that contains code is passed on WITHOUT its finish reason. ADK 2.7.0 runs the code, then blanks
       the reply so the flow will ask the model again ("look at the output, carry on"). But a later check sees
       a blank reply that says finish_reason=STOP, flags it MODEL_RETURNED_NO_CONTENT, and ends the turn right
       there: the code runs, and the operator never hears what it found. With no finish reason on the reply,
       that check stands aside and the flow loops back to the model, as the code executor intends.
       (Streaming turns, which adk web can use, skip that check already.)
    2. If a reply still comes back with nothing in it (no words, no tool call, no code), ask once more. Gemini
       sometimes answers MALFORMED_FUNCTION_CALL; a second sample usually comes back well-formed. After plain text
       (such as sandbox output) we add a one-line nudge; after a tool result we resend the request unchanged,
       because in testing, adding text to a tool result made the API answer 400 ("ending with a model turn").
    """

    async def generate_content_async(self, llm_request, stream: bool = False):
        for attempt in range(config.EMPTY_REPLY_RETRIES + 1):
            held, useful, t0 = [], False, time.perf_counter()
            if not getattr(self, "_where_logged", False):   # once: which endpoint are we really calling?
                c = getattr(self.api_client, "_api_client", None)
                timing.log(f"Gemini client: model {llm_request.model}, vertex {getattr(c, 'vertexai', '?')}, "
                           f"project {getattr(c, 'project', '?')}, location {getattr(c, 'location', '?')}, "
                           f"thinking {config.THINKING_LEVEL}")
                object.__setattr__(self, "_where_logged", True)
            timing.log(f"model call {attempt + 1} sent ({len(llm_request.contents)} contents)")
            async for r in super().generate_content_async(llm_request, stream):
                useful = useful or _useful(r)
                if not r.partial and _has_code(r) and not r.error_code:
                    r.finish_reason = None      # fix 1, above
                if r.partial:
                    yield r                     # streamed words go straight to the UI
                else:
                    held.append(r)              # the complete reply waits until we know it is not empty
            last = held[-1] if held else None
            reason = str(getattr(last, "finish_reason", None) or "").split(".")[-1] or None
            um = getattr(last, "usage_metadata", None)
            timing.log(f"model reply: {time.perf_counter() - t0:.1f}s, finish {reason}, tokens in "
                       f"{getattr(um, 'prompt_token_count', '?')} think {getattr(um, 'thoughts_token_count', 0) or 0} "
                       f"out {getattr(um, 'candidates_token_count', '?')}")
            if useful or attempt == config.EMPTY_REPLY_RETRIES or reason not in _RETRYABLE:
                for r in held:
                    yield r
                return
            EMPTY_REPLIES.append({"finish_reason": reason, "error_code": getattr(last, "error_code", None),
                                  "error_message": (getattr(last, "error_message", None) or "")[:200],
                                  "seconds": round(time.perf_counter() - t0, 1)})
            log.warning("Empty model reply (finish_reason=%s); asking once more.", reason)
            tail = llm_request.contents[-1] if llm_request.contents else None
            if tail is not None and tail.role == "user" and not any(p.function_response for p in tail.parts or []):
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
    # A busy endpoint answers 429 now and then; retry quietly rather than fail on stage.
    retry_options=types.HttpRetryOptions(attempts=3, initial_delay=1.0),
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
    generate_content_config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_level=config.THINKING_LEVEL.upper()),
    ),
)
