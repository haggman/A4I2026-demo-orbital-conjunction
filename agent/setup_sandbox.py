"""Create (or reuse) the Agent Runtime code sandbox the agent runs its what-ifs in, and warm it up.

Run it once before rehearsing, and again as the first line of every reset block:

    python agent/setup_sandbox.py              # reuse the sandbox named in agent/cymbal_ops/.env if it still runs
    python agent/setup_sandbox.py --new        # make a fresh Agent Runtime instance and sandbox

Why a script and not the agent: the first sandbox in a new Agent Runtime instance took three minutes to
create in testing, and ADK's executor would otherwise do that lazily, on stage, in front of everyone.
The agent runs on Cloud Run; its sandbox belongs to an Agent Runtime instance either way.

It writes agent/cymbal_ops/.env, which `adk web` reads and agent/deploy.sh passes to Cloud Run.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV_FILE = HERE / "cymbal_ops" / ".env"
LOCATION = "us-central1"


def read_env() -> dict:
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def setup(project: str, new: bool = False, write_env: bool = True) -> dict:
    """Return {'engine', 'sandbox', 'timings', 'stage'}; creates only what is missing."""
    import vertexai
    from vertexai import types

    client = vertexai.Client(project=project, location=LOCATION)
    env, t, out = read_env(), {}, {}
    engine, sbx = env.get("A4I_ENGINE"), env.get("A4I_SANDBOX")

    if sbx and not new:
        try:
            state = client.agent_engines.sandboxes.get(name=sbx).state
            if str(state).endswith("RUNNING"):
                print(f"reusing sandbox {sbx}")
            else:
                print(f"sandbox is {state}; making a new one"); sbx = None
        except Exception as e:
            print(f"sandbox not found ({type(e).__name__}); making a new one"); sbx = None
    else:
        sbx = None
    if new:
        engine = None

    if not engine:
        s = time.perf_counter()
        engine = client.agent_engines.create(config={"display_name": "cymbal-ops"}).api_resource.name
        t["create_agent_runtime_s"] = round(time.perf_counter() - s, 1)
        print(f"created Agent Runtime instance {engine} in {t['create_agent_runtime_s']} s")
    if not sbx:
        s = time.perf_counter()
        op = client.agent_engines.sandboxes.create(
            name=engine, spec={"code_execution_environment": {}},
            config=types.CreateAgentEngineSandboxConfig(display_name="cymbal-ops-sandbox", ttl=f"{14 * 86400}s"))
        sbx = op.response.name
        t["create_sandbox_s"] = round(time.perf_counter() - s, 1)
        print(f"created sandbox {sbx} in {t['create_sandbox_s']} s")

    # Stage the physics toolkit and import it once, so the first call on stage is fast.
    os.environ["A4I_SANDBOX"] = sbx
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project)
    sys.path.insert(0, str(HERE))
    from cymbal_ops import sandbox as sb
    sb.client.cache_clear()
    s = time.perf_counter()
    staged = sb.stage(sandbox=sbx)
    t["stage_and_warm_s"] = round(time.perf_counter() - s, 1)
    print("staged:", staged["stdout"].strip() or staged)
    if staged["stderr"].strip():
        print("stderr:", staged["stderr"][-800:])

    if write_env:
        keep = {k: v for k, v in env.items() if k not in ("A4I_ENGINE", "A4I_SANDBOX", "GOOGLE_CLOUD_PROJECT")}
        keep.update({"GOOGLE_CLOUD_PROJECT": project, "GOOGLE_GENAI_USE_VERTEXAI": "True",
                     "A4I_ENGINE": engine, "A4I_SANDBOX": sbx})
        ENV_FILE.write_text("".join(f"{k}={v}\n" for k, v in keep.items()))
        print(f"wrote {ENV_FILE}")
    out.update({"engine": engine, "sandbox": sbx, "timings": t, "stage": staged})
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=os.environ.get("GOOGLE_CLOUD_PROJECT"))
    ap.add_argument("--new", action="store_true", help="create a fresh Agent Runtime instance and sandbox")
    a = ap.parse_args()
    if not a.project:
        import google.auth
        a.project = google.auth.default()[1]
    r = setup(a.project, new=a.new)
    print(json.dumps({k: r[k] for k in ("engine", "sandbox", "timings")}, indent=1))
