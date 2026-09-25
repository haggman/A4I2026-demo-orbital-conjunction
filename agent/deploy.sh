#!/usr/bin/env bash
#
# Deploy the Cymbal Orbital agent to Cloud Run.
#
#     bash agent/deploy.sh
#
# Run from the repo root in Cloud Shell, AFTER `python agent/setup_sandbox.py` (which writes
# agent/cymbal_ops/.env with the sandbox's resource name). Takes about five minutes the first time.
#
# What it does:
#   1. creates a service account for the agent with exactly the roles it needs
#   2. deploys agent/cymbal_ops with ADK's Cloud Run deployer, pinned to the ADK version we tested,
#      with the ADK web UI (segment 4 shows it) and authentication REQUIRED
#   3. prints how to reach it
#
# Authentication is required on purpose: the agent can run code in its sandbox and query BigQuery,
# and an open URL on a conference slide is an open invitation. Reach it through the Cloud Shell proxy
# (printed at the end), or decide deliberately to open it for the event.

set -euo pipefail

ADK_VERSION="${ADK_VERSION:-2.7.0}"      # what Colab Enterprise ships, and what we tested against
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-cymbal-ops}"
SA_NAME="cymbal-ops-agent"
# Cloud Run's defaults (512 MiB, 1 vCPU, any number of instances) are too small for ADK plus the Google
# clients, and the ADK web UI keeps sessions in memory, so a second instance would not know your session.
# One instance, room to work. MIN_INSTANCES=1 on the day keeps it warm (it bills while it is up).
MEMORY="${MEMORY:-2Gi}"
CPU="${CPU:-2}"
MIN_INSTANCES="${MIN_INSTANCES:-0}"
ENV_FILE="agent/cymbal_ops/.env"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
fail() { printf '\n\033[1mERROR:\033[0m %s\n\n' "$*" >&2; exit 1; }

[[ -f "${ENV_FILE}" ]] || fail "${ENV_FILE} not found. Run: python agent/setup_sandbox.py"
command -v adk >/dev/null 2>&1 || fail "'adk' not found. Run: source scripts/activate.sh"

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a
PROJECT="${GOOGLE_CLOUD_PROJECT:?GOOGLE_CLOUD_PROJECT missing from ${ENV_FILE}}"
: "${A4I_SANDBOX:?A4I_SANDBOX missing from ${ENV_FILE} - run python agent/setup_sandbox.py}"
SA="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"

bold "1/3  Service account ${SA}"
if ! gcloud iam service-accounts describe "${SA}" --project "${PROJECT}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SA_NAME}" --project "${PROJECT}" \
    --display-name "Cymbal Orbital agent (A4I demo)" >/dev/null
fi
# Read BigQuery through its managed MCP server; run Gemini and the sandbox; bill the requests to this project.
for role in roles/bigquery.dataViewer roles/bigquery.jobUser roles/mcp.toolUser \
            roles/aiplatform.user roles/serviceusage.serviceUsageConsumer; do
  gcloud projects add-iam-policy-binding "${PROJECT}" --member "serviceAccount:${SA}" \
    --role "${role}" --condition=None --quiet >/dev/null
  echo "  ${role}"
done

bold "2/3  Deploying ${SERVICE} (ADK ${ADK_VERSION}) to ${REGION}"
# Cloud Run cannot see demo.env, so its settings (model, thinking, tier, timeouts, dataset...) go as variables.
SETTINGS="$(python agent/cymbal_ops/config.py --deploy-env)" || fail "Could not read the settings (demo.env)."
ENV_VARS="GOOGLE_CLOUD_PROJECT=${PROJECT},GOOGLE_GENAI_USE_VERTEXAI=True,A4I_SANDBOX=${A4I_SANDBOX},${SETTINGS}"
echo "  settings: ${SETTINGS}"
adk deploy cloud_run --project "${PROJECT}" --region "${REGION}" --service_name "${SERVICE}" \
  --adk_version "${ADK_VERSION}" --with_ui agent/cymbal_ops \
  -- --service-account "${SA}" --set-env-vars "${ENV_VARS}" --no-allow-unauthenticated \
     --memory "${MEMORY}" --cpu "${CPU}" --max-instances 1 --min-instances "${MIN_INSTANCES}" --timeout 600

bold "3/3  Reaching it"
URL="$(gcloud run services describe "${SERVICE}" --project "${PROJECT}" --region "${REGION}" --format='value(status.url)')"
echo "  Service URL: ${URL}   (authentication required)"
echo
echo "  To open the ADK web UI from Cloud Shell:"
echo "    gcloud run services proxy ${SERVICE} --project ${PROJECT} --region ${REGION} --port 8080"
echo "  then Web Preview > Preview on port 8080."
