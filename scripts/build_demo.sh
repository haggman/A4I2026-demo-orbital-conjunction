#!/usr/bin/env bash
#
# A4I 2026 kickoff demo - build the whole thing in one Google Cloud project.
#
#     bash scripts/build_demo.sh                  # data, agent, sandbox, smoke test, Cloud Run
#     bash scripts/build_demo.sh --skip-deploy    # everything except Cloud Run (faster; good for rehearsal)
#     bash scripts/build_demo.sh --full-smoke     # ask the agent all six test questions, not two
#
# Run it from the repo root in Cloud Shell, as a user who can enable APIs, create a service account and
# grant it roles (a Google Skills lab project's Owner is enough). Safe to run again: every step reuses
# what is already there.
#
# What it does, in order:
#   1. enables the APIs the demo uses
#   2. loads the five a4i_orbit tables (skipped if they are already there; otherwise scripts/load.sh)
#   3. makes a Python environment with the pinned ADK
#   4. creates and warms the Agent Runtime code sandbox (agent/setup_sandbox.py)
#   5. asks the agent a few operator questions and checks the answers used every part of it
#   6. deploys the agent to Cloud Run (agent/deploy.sh)

set -euo pipefail

ADK_VERSION="${ADK_VERSION:-2.7.0}"
VENV="${A4I_VENV:-${HOME}/.venvs/a4i-demo}"
DATASET="a4i_orbit"
SKIP_DEPLOY=0
SMOKE_ARGS=(--quick)
for arg in "$@"; do
  case "${arg}" in
    --skip-deploy) SKIP_DEPLOY=1 ;;
    --full-smoke)  SMOKE_ARGS=() ;;
    -h|--help)     sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) printf 'Unknown option: %s\n' "${arg}" >&2; exit 2 ;;
  esac
done

bold() { printf '\n\033[1m%s\033[0m\n' "$*"; }
fail() { printf '\n\033[1mERROR:\033[0m %s\n\nSafe to run again once fixed.\n\n' "$*" >&2; exit 1; }

[[ -f scripts/load.sh && -d agent/cymbal_ops ]] || fail "Run this from the repo root (the folder with scripts/ and agent/)."
PROJECT="$(gcloud config get-value project 2>/dev/null || true)"
[[ -n "${PROJECT}" && "${PROJECT}" != "(unset)" ]] || fail "No project set. Run: gcloud config set project YOUR_PROJECT_ID"
export GOOGLE_CLOUD_PROJECT="${PROJECT}"
bold "Building the Cymbal Orbital demo in ${PROJECT}"

bold "1/6  Enabling APIs (a minute or two the first time)"
gcloud services enable bigquery.googleapis.com aiplatform.googleapis.com run.googleapis.com \
  cloudbuild.googleapis.com artifactregistry.googleapis.com iam.googleapis.com \
  --project "${PROJECT}"

bold "2/6  Data"
rows="$(bq --project_id="${PROJECT}" query --use_legacy_sql=false --format=csv \
          "SELECT COUNT(*) FROM \`${PROJECT}.${DATASET}.conjunctions\`" 2>/dev/null | tail -n 1 || true)"
if [[ "${rows}" =~ ^[0-9]+$ && "${rows}" -gt 0 ]]; then
  echo "  ${DATASET} is already loaded (${rows} conjunctions) - leaving it alone"
else
  bash scripts/load.sh
fi

bold "3/6  Python environment (${VENV}, ADK ${ADK_VERSION})"
# shellcheck disable=SC1091
source scripts/activate.sh || fail "The Python environment could not be set up - see the message above."

bold "4/6  Agent Runtime code sandbox (the first one can take three minutes)"
python agent/setup_sandbox.py --project "${PROJECT}"

bold "5/6  Smoke test: asking the agent what an operator would ask"
python agent/smoke_test.py "${SMOKE_ARGS[@]}" || fail "The smoke test failed a check - its diagnostic block above says which."

if [[ "${SKIP_DEPLOY}" -eq 1 ]]; then
  bold "6/6  Skipped Cloud Run (--skip-deploy)"
else
  bold "6/6  Cloud Run"
  bash agent/deploy.sh
fi

bold "Ready."
cat <<EOF

  In any new Cloud Shell terminal, start with:
    source scripts/activate.sh

  Then:
    adk web agent                      the ADK web UI (Web Preview > Change port > 8000), pick cymbal_ops
    python agent/model_check.py        which Gemini model is quick right now (settings live in demo.env)
    python agent/setup_sandbox.py      before a session: reset the sandbox to the start state

EOF
