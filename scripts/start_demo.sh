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
#   4. makes sure the Cloud Run service (step 5) keeps one instance warm, so it is never asleep
#   5. starts the ADK web UI on port 8000 (run-of-show steps 3 and 4: the live agent)
#   6. starts the console on port 8080 in REPLAY mode (step 6: the finished product), playing
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

bold "1/5  Code sandbox: reuse and warm"
python agent/setup_sandbox.py >/dev/null 2>"${RUN_DIR}/sandbox.err" || { cat "${RUN_DIR}/sandbox.err"; fail "python agent/setup_sandbox.py"; }
echo "  ✓ sandbox ready"

bold "2/5  Gemini: is the model quick right now?"
python agent/model_check.py 2>/dev/null | tail -4 | sed 's/^/  /'

bold "3/5  Cloud Run: one instance kept warm"
CR_SERVICE="${SERVICE:-cymbal-ops}"; CR_REGION="${REGION:-us-central1}"
CR_PROJECT="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
min=$(gcloud run services describe "${CR_SERVICE}" --project "${CR_PROJECT}" --region "${CR_REGION}" --format=json 2>/dev/null \
  | python -c 'import json,sys; d=json.load(sys.stdin); print(d["spec"]["template"]["metadata"].get("annotations",{}).get("autoscaling.knative.dev/minScale","0"))' 2>/dev/null)
if [[ -z "${min}" ]]; then
  echo "  ! ${CR_SERVICE} isn't deployed in ${CR_PROJECT} (${CR_REGION}): run bash agent/deploy.sh before the show"
elif [[ "${min}" == "1" ]]; then
  echo "  ✓ ${CR_SERVICE}: minimum instances 1, never asleep"
else
  gcloud run services update "${CR_SERVICE}" --project "${CR_PROJECT}" --region "${CR_REGION}" --min-instances 1 --quiet >/dev/null 2>&1 \
    && echo "  ✓ ${CR_SERVICE}: minimum instances set to 1 (it was ${min}), never asleep" \
    || echo "  ! couldn't set minimum instances on ${CR_SERVICE}: it may be asleep when you show it"
fi

bold "4/5  Starting the ADK web UI (port 8000) and the console (port 8080, replay)"
stop_all
nohup bash scripts/adk_web.sh >"${RUN_DIR}/adk-web.log" 2>&1 &   # Cloud Shell-safe flags: see the script
echo $! >"${RUN_DIR}/adk-web.pid"
A4I_CONSOLE_MODE=replay A4I_CONSOLE_REPLAY=rehearsal nohup uvicorn console.app:app --port 8080 --workers 1 >"${RUN_DIR}/console.log" 2>&1 &
echo $! >"${RUN_DIR}/console.pid"

bold "5/5  Checking both answer"
for port in 8000 8080; do
  ok=""
  for _ in $(seq 1 30); do curl -s -o /dev/null "http://localhost:${port}/" && { ok=1; break; }; sleep 1; done
  [[ -n "${ok}" ]] && echo "  ✓ port ${port} answering" || fail "nothing on port ${port}: see ${RUN_DIR}/$([[ ${port} == 8000 ]] && echo adk-web || echo console).log"
done
mode=$(curl -s http://localhost:8080/api/state | python -c 'import json,sys; d=json.load(sys.stdin); print(d["mode"], d["recording"], d.get("agent_error") or "")')
echo "  ✓ console: ${mode}"

echo
bold "Ready. Click each link to open it in its own Web Preview tab:"
echo "  http://0.0.0.0:8000/dev-ui/?app=cymbal_ops    the ADK web UI, cymbal_ops already picked (steps 3 and 4)"
echo "  http://0.0.0.0:8080                           the console (step 6)"
echo "  Stop both later with: bash scripts/start_demo.sh --stop"
