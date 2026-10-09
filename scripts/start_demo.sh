#!/usr/bin/env bash
# The kickoff demo's start block: everything the run-of-show needs, running, in one command.
#
#     bash scripts/start_demo.sh            # start (or restart) both web apps
#     bash scripts/start_demo.sh --stop     # stop them
#
# Run it in Cloud Shell from the repo root, after `bash scripts/build_demo.sh` has built the demo once in this
# project. Safe to run again at any time: it stops what it started last time and starts fresh.
#
# What it does:
#   1. switches on the Python environment and shows the settings (scripts/activate.sh)
#   2. reuses and warms the Agent Runtime code sandbox (agent/setup_sandbox.py)
#   3. times the Gemini models right now and says whether the default is quick (agent/model_check.py)
#   4. starts the ADK web UI on port 8000 (run-of-show steps 3 and 4: the live agent)
#   5. starts the console on port 8080 in REPLAY mode (step 6: the finished product), playing
#      console/recordings/rehearsal.json, a recording of a real run, so it behaves the same every time
# Logs: ~/.a4i-demo/adk-web.log and ~/.a4i-demo/console.log

RUN_DIR="${HOME}/.a4i-demo"
mkdir -p "${RUN_DIR}"
stop_all() {
  for name in adk-web console; do
    if [[ -f "${RUN_DIR}/${name}.pid" ]]; then
      kill "$(cat "${RUN_DIR}/${name}.pid")" 2>/dev/null && echo "  stopped ${name}"
      rm -f "${RUN_DIR}/${name}.pid"
    fi
  done
}
if [[ "${1:-}" == "--stop" ]]; then stop_all; exit 0; fi

cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
# shellcheck disable=SC1091
source scripts/activate.sh || exit 1
bold() { printf '\033[1m%s\033[0m\n' "$*"; }
fail() { printf '\n\033[1mSTOPPED:\033[0m %s\n\n' "$*" >&2; exit 1; }

[[ -f console/.snapshot_extract.json ]] || { bold "First run in this project: the console's slice of the snapshot"; python console/data.py >/dev/null || fail "python console/data.py"; }
[[ -f console/recordings/rehearsal.json ]] || fail "console/recordings/rehearsal.json is missing: the console's replay needs it (see run-of-show/README.md)."

bold "1/4  Code sandbox: reuse and warm"
python agent/setup_sandbox.py >/dev/null 2>"${RUN_DIR}/sandbox.err" || { cat "${RUN_DIR}/sandbox.err"; fail "python agent/setup_sandbox.py"; }
echo "  ✓ sandbox ready"

bold "2/4  Gemini: is the model quick right now?"
python agent/model_check.py 2>/dev/null | tail -4 | sed 's/^/  /'

bold "3/4  Starting the ADK web UI (port 8000) and the console (port 8080, replay)"
stop_all
nohup adk web --port 8000 agent >"${RUN_DIR}/adk-web.log" 2>&1 &
echo $! >"${RUN_DIR}/adk-web.pid"
A4I_CONSOLE_MODE=replay A4I_CONSOLE_REPLAY=rehearsal nohup uvicorn console.app:app --port 8080 --workers 1 >"${RUN_DIR}/console.log" 2>&1 &
echo $! >"${RUN_DIR}/console.pid"

bold "4/4  Checking both answer"
for port in 8000 8080; do
  ok=""
  for _ in $(seq 1 30); do curl -s -o /dev/null "http://localhost:${port}/" && { ok=1; break; }; sleep 1; done
  [[ -n "${ok}" ]] && echo "  ✓ port ${port} answering" || fail "nothing on port ${port}: see ${RUN_DIR}/$([[ ${port} == 8000 ]] && echo adk-web || echo console).log"
done
mode=$(curl -s http://localhost:8080/api/state | python -c 'import json,sys; d=json.load(sys.stdin); print(d["mode"], d["recording"], d.get("agent_error") or "")')
echo "  ✓ console: ${mode}"

echo
bold "Ready. Open two Web Preview tabs:"
echo "  Web Preview ▸ Change port ▸ 8000   the ADK web UI (pick cymbal_ops)"
echo "  Web Preview ▸ Change port ▸ 8080   the console"
echo "  Stop both later with: bash scripts/start_demo.sh --stop"
