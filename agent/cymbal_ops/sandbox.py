"""Putting files into the Agent Runtime code sandbox.

The model's code runs in the sandbox through ADK's AgentEngineSandboxCodeExecutor. Our tools use the same
sandbox directly, to stage the files that code needs: sgp4's pure-Python modules (the sandbox has numpy
and scipy but no sgp4, and no network to install it), our orbit_whatif module, and one case file per
conjunction. Everything is re-sent on every staging call, so a sandbox that has been reset heals itself.
"""
import io
import json
import re
import zipfile
from functools import lru_cache
from pathlib import Path

from . import config

FILES = Path(__file__).parent / "sandbox_files"


def location_of(resource_name: str) -> str:
    m = re.match(r"^projects/[^/]+/locations/([^/]+)/", resource_name or "")
    if not m:
        raise ValueError("A4I_SANDBOX is not set to a sandbox resource name. Run agent/setup_sandbox.py first.")
    return m.group(1)


@lru_cache(maxsize=1)
def client():
    import vertexai
    return vertexai.Client(project=config.PROJECT, location=location_of(config.SANDBOX))


@lru_cache(maxsize=1)
def sgp4_zip() -> bytes:
    """sgp4's own .py files (MIT licence included), zipped so the sandbox can import them with no install."""
    import sgp4
    root = Path(sgp4.__file__).parent
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(root.glob("*.py")):
            if f.name not in ("tests.py", "wulfgar.py"):
                z.write(f, f"sgp4/{f.name}")
        for lic in list(root.parent.glob("sgp4-*.dist-info/licenses/LICENSE")) + list(root.parent.glob("sgp4-*.dist-info/LICENSE*")):
            z.write(lic, "sgp4/LICENSE")
            break
    return buf.getvalue()


def run(code: str, files: dict[str, bytes] | None = None, sandbox: str | None = None) -> dict:
    """Execute code in the sandbox, optionally with files; return stdout, stderr and output file names."""
    data = {"code": code}
    if files:
        data["files"] = [{"name": n, "content": c, "mime_type": "application/octet-stream"} for n, c in files.items()]
    resp = client().agent_engines.sandboxes.execute_code(name=sandbox or config.SANDBOX, input_data=data)
    out = {"stdout": "", "stderr": "", "files": []}
    for o in resp.outputs:
        attrs = (o.metadata.attributes if o.metadata and o.metadata.attributes else {}) or {}
        if o.mime_type == "application/json" and "file_name" not in attrs:
            j = json.loads(o.data.decode())
            out["stdout"], out["stderr"] = j.get("msg_out", ""), j.get("msg_err", "")
        else:
            out["files"].append(attrs.get("file_name"))
    return out


def stage(extra: dict[str, bytes] | None = None, sandbox: str | None = None) -> dict:
    """Upload the physics toolkit (and any case files), then import it once so the first real call is fast."""
    files = {"sgp4_pure.zip": sgp4_zip(), "orbit_whatif.py": (FILES / "orbit_whatif.py").read_bytes()}
    files.update(extra or {})
    code = ("import importlib, json, os, sys\n"
            "sys.path.insert(0, os.getcwd()) if os.getcwd() not in sys.path else None\n"
            "import orbit_whatif\n"
            "importlib.reload(orbit_whatif)\n"
            "print(json.dumps({'ok': True, 'files': sorted(os.listdir('.'))}))")
    return run(code, files, sandbox)
