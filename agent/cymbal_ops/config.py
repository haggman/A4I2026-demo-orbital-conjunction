"""Every setting the agent reads, in one place.

Where a setting comes from, first match wins:
  1. the environment (a variable you exported, or one Cloud Run sets from agent/deploy.sh);
  2. demo.env at the repo root—THE file to edit, e.g. to try another model;
  3. agent/cymbal_ops/.env, written by agent/setup_sandbox.py (the sandbox's name; do not edit);
  4. the defaults below, which match the notebook.
Edit demo.env, then restart whatever is running (adk web, the smoke test) or redeploy.
"""
import os
from pathlib import Path

import google.auth

HERE = Path(__file__).resolve().parent
SETTINGS_FILE = HERE.parents[1] / "demo.env"       # repo root; not shipped to Cloud Run (deploy.sh passes values)
SANDBOX_FILE = HERE / ".env"


def _load(path: Path) -> None:
    """KEY=VALUE lines into the environment, without overriding anything already set."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load(SETTINGS_FILE)
_load(SANDBOX_FILE)

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT") or google.auth.default()[1]
DATASET = os.environ.get("A4I_DATASET", "a4i_orbit")

# The Agent Runtime code sandbox, created ahead of time by agent/setup_sandbox.py and handed over by name.
# Creating the first sandbox in an Agent Runtime instance took three minutes in testing, and ADK's executor
# does not remember a sandbox it created itself between turns—so we never let it create one.
SANDBOX = os.environ.get("A4I_SANDBOX", "")

# The model, and where it is served from. Gemini 3.8 Flash on the GLOBAL endpoint by default. Any Gemini model
# ID the project can use works here; agent/model_check.py times the candidates before a session.
MODEL = os.environ.get("A4I_MODEL", "gemini-3.8-flash")
MODEL_LOCATION = os.environ.get("A4I_MODEL_LOCATION", "global")

# How hard the model thinks before each step: minimal, low, medium or high. A turn here is several steps
# (query, tool, code, answer), and on a stage every step's thinking is dead air. "low" was enough for this
# agent's routing. Empty means "send no thinking setting", for a model that does not accept one.
THINKING_LEVEL = os.environ.get("A4I_THINKING_LEVEL", "low").strip().lower()

# Which queue the requests join. Empty = standard pay-as-you-go. "priority" asks for Vertex AI's Priority PayGo,
# which Google documents as priority processing at a premium per-token price; "flex" is the cheaper, slower one.
# Untested with this agent: agent/model_check.py tells you whether the endpoint accepts it and whether it helps.
SERVICE_TIER = os.environ.get("A4I_SERVICE_TIER", "").strip().lower()

# Other models agent/model_check.py should time alongside MODEL, space-separated.
MODEL_CANDIDATES = [m for m in os.environ.get("A4I_MODEL_CANDIDATES", "").split() if m]

# Patience with a slow model. The first try at each step gets MODEL_TIMEOUT_S seconds, each retry twice the
# time before, with an exponential pause between tries (1, 2, 4, then 8 s at most). MODEL_ATTEMPTS counts every
# try, the first included. Busy-endpoint answers (HTTP 429, 5xx) are retried the same way underneath.
# Why: on 2026-09-25 the same call took 2 s one minute and 42 s the next; a second try is often the fast one.
MODEL_TIMEOUT_S = float(os.environ.get("A4I_MODEL_TIMEOUT_S", "20"))
MODEL_ATTEMPTS = max(1, int(os.environ.get("A4I_MODEL_ATTEMPTS", "4")))
BACKOFF_FIRST_S, BACKOFF_MAX_S = 1.0, 8.0

# How the model's Python reaches the sandbox.
#   "tool"     (default) a function tool, run_in_sandbox(code), that runs the code in the Agent Runtime sandbox.
#              Function calling is the path Gemini is most practised at, so this is the one to put on a stage.
#   "executor" ADK's AgentEngineSandboxCodeExecutor: the model writes a ```python block in its reply and ADK runs
#              it in the same sandbox. Worth showing; in testing with ADK 2.7.0 and Gemini 3.8 Flash it was the
#              less dependable of the two (see agent.py and agent/README.md).
CODE_PATH = os.environ.get("A4I_CODE_PATH", "tool").strip().lower()

# The demo's frozen "now"—the same instant notebooks/demo_01_load_explore.ipynb screens from.
NOW_UTC = os.environ.get("A4I_NOW_UTC", "2026-09-25T01:00:00Z")

# Cymbal Orbital is fictional, so its spacecraft budget is ours to state. These two numbers are the ONLY
# source of every "days of mission life" figure the agent quotes. Say so when you quote one.
DESIGN_LIFE_YEARS = float(os.environ.get("A4I_DESIGN_LIFE_YEARS", "7"))
DELTA_V_BUDGET_M_S = float(os.environ.get("A4I_DELTA_V_BUDGET_M_S", "30"))

# "Clear" means the worst-case collision probability is below this. With a 5 m hard-body radius that is
# a miss of about 3 km. A policy choice, not a physical constant.
CLEAR_PC = float(os.environ.get("A4I_CLEAR_PC", "1e-6"))

# The settings Cloud Run needs, as agent/deploy.sh passes them (it cannot see demo.env).
DEPLOY_KEYS = ("A4I_DATASET", "A4I_MODEL", "A4I_MODEL_LOCATION", "A4I_THINKING_LEVEL", "A4I_SERVICE_TIER", "A4I_MODEL_TIMEOUT_S",
               "A4I_MODEL_ATTEMPTS", "A4I_CODE_PATH", "A4I_TIMING_LOGS")


def deploy_env() -> str:
    """KEY=VALUE,... for gcloud --set-env-vars, from the settings in force right now."""
    values = {"A4I_DATASET": DATASET, "A4I_MODEL": MODEL, "A4I_MODEL_LOCATION": MODEL_LOCATION,
              "A4I_THINKING_LEVEL": THINKING_LEVEL, "A4I_SERVICE_TIER": SERVICE_TIER, "A4I_MODEL_TIMEOUT_S": f"{MODEL_TIMEOUT_S:g}",
              "A4I_MODEL_ATTEMPTS": str(MODEL_ATTEMPTS), "A4I_CODE_PATH": CODE_PATH,
              "A4I_TIMING_LOGS": os.environ.get("A4I_TIMING_LOGS", "1")}
    return ",".join(f"{k}={values[k]}" for k in DEPLOY_KEYS)


def generate_config(**extra):
    """The per-request model settings the agent and agent/model_check.py both use."""
    from google.genai import types
    kw = dict(extra)
    if THINKING_LEVEL:
        kw["thinking_config"] = types.ThinkingConfig(thinking_level=THINKING_LEVEL.upper())
    if SERVICE_TIER:
        kw["service_tier"] = SERVICE_TIER.upper()
    return types.GenerateContentConfig(**kw) if kw else None


def summary() -> str:
    return (f"project {PROJECT} · dataset {DATASET} · model {MODEL} @ {MODEL_LOCATION} · thinking "
            f"{THINKING_LEVEL or '(not sent)'} · tier {SERVICE_TIER or 'standard'} · timeout {MODEL_TIMEOUT_S:g}s x{MODEL_ATTEMPTS} · code via {CODE_PATH}")


if __name__ == "__main__":
    import sys
    print(deploy_env() if "--deploy-env" in sys.argv else summary())
