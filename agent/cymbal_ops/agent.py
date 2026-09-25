"""Cymbal Orbital's conjunction-assessment agent.

One ADK agent, three kinds of tool:
- BigQuery's Google-managed MCP server, read-only, for any question the tables can answer;
- three tools we wrote, for the judgment (assess_conjunction, maneuver_cost, build_assessment);
- an Agent Runtime code sandbox, through ADK's AgentEngineSandboxCodeExecutor, for the orbital what-ifs.
"""
import os

import google.auth
import google.auth.transport.requests
from google.adk.agents import LlmAgent
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

from . import config
from .prompt import INSTRUCTION
from .tools import assess_conjunction, build_assessment, maneuver_cost

if not config.SANDBOX:
    raise RuntimeError("A4I_SANDBOX is not set. Run `python agent/setup_sandbox.py` first; it writes agent/cymbal_ops/.env.")

# Gemini is served from the global endpoint; the sandbox's region comes from its own resource name.
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
os.environ["GOOGLE_CLOUD_PROJECT"] = config.PROJECT
os.environ["GOOGLE_CLOUD_LOCATION"] = config.MODEL_LOCATION

_creds = None


def _bigquery_auth(_ctx) -> dict[str, str]:
    """A fresh bearer token for every MCP request. Tokens expire after an hour; demos run longer."""
    global _creds
    if _creds is None:
        _creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/bigquery"])
    if not _creds.valid:
        _creds.refresh(google.auth.transport.requests.Request())
    return {"Authorization": f"Bearer {_creds.token}", "x-goog-user-project": config.PROJECT}


bigquery_mcp = McpToolset(
    connection_params=StreamableHTTPConnectionParams(url="https://bigquery.googleapis.com/mcp", timeout=30.0),
    header_provider=_bigquery_auth,
    tool_filter=["execute_sql_readonly", "get_table_info", "list_table_ids"],   # read-only, on purpose
)

root_agent = LlmAgent(
    name="cymbal_ops",
    model=config.MODEL,
    description="Conjunction assessment and maneuver planning for Cymbal Orbital's (fictional) constellation.",
    instruction=INSTRUCTION,
    tools=[bigquery_mcp, assess_conjunction, maneuver_cost, build_assessment],
    code_executor=AgentEngineSandboxCodeExecutor(sandbox_resource_name=config.SANDBOX),
)
