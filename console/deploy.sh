#!/usr/bin/env bash
#
# Deploy the flight dynamics console to Cloud Run: one service, one instance, with the agent inside it.
#
#     bash console/deploy.sh
#
# Run from the repo root in Cloud Shell, after `source scripts/activate.sh`, `python agent/setup_sandbox.py`
# and `python console/data.py` (the console's slice of the snapshot). About five minutes the first time.
#
# Same pattern as agent/deploy.sh: its own service account with exactly the roles it needs, and
# authentication REQUIRED. The console can wake an agent that runs code and queries BigQuery.

set -euo pipefail

ADK_VERSION="${ADK_VERSION:-2.7.0}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-cymbal-console}"
SA_NAME="cymbal-ops-agent"                # the agent's service account: the console runs the same agent
MEMORY="${MEMORY:-2Gi}"
CPU="${CPU:-2}"
MIN_INSTANCES="${MIN_INSTANCES:-0}"       # 1 on the day keeps it warm (and billing while it is up)
ENV_FILE="agent/cymbal_ops/.env"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
fail() { printf '\n\033[1mERROR:\033[0m %s\n\n' "$*" >&2; exit 1; }

[[ -f "${ENV_FILE}" ]] || fail "${ENV_FILE} not found. Run: python agent/setup_sandbox.py"
[[ -f console/.snapshot_extract.json ]] || fail "console/.snapshot_extract.json not found. Run: python console/data.py"
[[ -f console/scenario.json ]] || fail "console/scenario.json not found. Run: python console/make_scenario.py"
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
for role in roles/bigquery.dataViewer roles/bigquery.jobUser roles/mcp.toolUser \
            roles/aiplatform.user roles/serviceusage.serviceUsageConsumer; do
  gcloud projects add-iam-policy-binding "${PROJECT}" --member "serviceAccount:${SA}" \
    --role "${role}" --condition=None --quiet >/dev/null
  echo "  ${role}"
done

bold "2/3  Building and deploying ${SERVICE} to ${REGION}"
STAGE="$(mktemp -d)"
trap 'rm -rf "${STAGE}"' EXIT
mkdir -p "${STAGE}/agent" "${STAGE}/console"
cp -r agent/cymbal_ops "${STAGE}/agent/"
rm -f "${STAGE}/agent/cymbal_ops/.env"              # settings go as variables, below
cp console/*.py console/scenario.json console/.snapshot_extract.json console/requirements.txt "${STAGE}/console/"
cp -r console/static "${STAGE}/console/"
[[ -d console/recordings ]] && cp -r console/recordings "${STAGE}/console/"
cp console/Dockerfile "${STAGE}/Dockerfile"
find "${STAGE}" -name __pycache__ -prune -exec rm -rf {} +
SETTINGS="$(python agent/cymbal_ops/config.py --deploy-env)" || fail "Could not read the settings (demo.env)."
ENV_VARS="GOOGLE_CLOUD_PROJECT=${PROJECT},GOOGLE_GENAI_USE_VERTEXAI=True,A4I_SANDBOX=${A4I_SANDBOX},${SETTINGS}"
ENV_VARS="${ENV_VARS},A4I_CONSOLE_MODE=${A4I_CONSOLE_MODE:-live},A4I_CONSOLE_REPLAY=${A4I_CONSOLE_REPLAY:-rehearsal}"
echo "  settings: ${SETTINGS}"
gcloud run deploy "${SERVICE}" --project "${PROJECT}" --region "${REGION}" --source "${STAGE}" \
  --service-account "${SA}" --set-env-vars "${ENV_VARS}" --no-allow-unauthenticated \
  --memory "${MEMORY}" --cpu "${CPU}" --no-cpu-throttling --max-instances 1 --min-instances "${MIN_INSTANCES}" \
  --timeout 3600 --quiet

bold "3/3  Reaching it"
URL="$(gcloud run services describe "${SERVICE}" --project "${PROJECT}" --region "${REGION}" --format='value(status.url)')"
echo "  Service URL: ${URL}   (authentication required)"
echo
echo "  From Cloud Shell:"
echo "    gcloud run services proxy ${SERVICE} --project ${PROJECT} --region ${REGION} --port 8080"
echo "  then Web Preview > Preview on port 8080."
