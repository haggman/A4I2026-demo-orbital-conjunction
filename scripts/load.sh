#!/usr/bin/env bash
#
# A4I 2026 - Kickoff demo: orbital conjunction screening
# Headless fallback for notebooks/demo_01_load_explore.ipynb
#
# Rebuilds the same five BigQuery tables the notebook produces - catalog, satcat,
# fleet, conjunctions, snapshot_info - from Parquet in Cloud Storage. Use it when
# a Colab Enterprise runtime is slow or unavailable, or to reset the demo to its
# start state in about a minute.
#
# Run it from the repo root in Cloud Shell (no chmod needed - invoke with bash):
#     bash scripts/load.sh                     # the pinned snapshot the kickoff uses
#     bash scripts/load.sh 20260925T0137Z      # a specific snapshot
#     bash scripts/load.sh --list              # snapshots that have published tables
#
# The notebook is the better path when you can run it: it shows the wrong answer
# first, walks through the messes in public orbital data, and runs the seven-day
# screen itself. This script restores the result of all that and teaches nothing.

set -euo pipefail

BUCKET="gs://class-demo/a4i-2026/demo-orbital-conjunction/tables"
DATASET="a4i_orbit"
LOCATION="US"
DEFAULT_SNAPSHOT="20260925T0137Z"

# Every table the notebook creates, in the order it creates them. If this list
# and the notebook drift apart, the agent asks for a table that is not there.
TABLES=(catalog satcat fleet conjunctions snapshot_info)

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
bold()  { printf '\033[1m%s\033[0m\n' "$*"; }
info()  { printf '  %s\n' "$*"; }
fail()  { printf '\n\033[1mERROR:\033[0m %s\n\n%s\n\n' "$*" \
          "This script is safe to run again - every table load replaces whatever was there." >&2
          exit 1; }

on_interrupt() {
  printf '\n\n\033[1mInterrupted.\033[0m Nothing is broken.\n'
  printf 'Every load replaces the whole table, so just run this script again:\n'
  printf '    bash scripts/load.sh %s\n\n' "${SNAPSHOT:-}"
  exit 130
}
trap on_interrupt INT TERM

list_snapshots() {
  bold "Snapshots with published tables"
  local found=0 stamp
  while read -r stamp; do
    [[ -z "${stamp}" ]] && continue
    found=1
    if [[ "${stamp}" == "${DEFAULT_SNAPSHOT}" ]]; then
      printf '  %s   <- the kickoff default\n' "${stamp}"
    else
      printf '  %s\n' "${stamp}"
    fi
  done < <(gcloud storage ls "${BUCKET}/" 2>/dev/null | sed 's|.*/\([^/]*\)/$|\1|')
  [[ "${found}" -eq 1 ]] || fail "Could not list ${BUCKET}/. Check that you are signed in, and that a
       maintainer has run the notebook with PUBLISH = True at least once."
  echo
  echo "Usage: bash scripts/load.sh <SNAPSHOT>"
}

# --------------------------------------------------------------------------
# Arguments
# --------------------------------------------------------------------------
SNAPSHOT="${1:-${DEFAULT_SNAPSHOT}}"

case "${SNAPSHOT}" in
  --list|-l) list_snapshots; exit 0 ;;
  --help|-h) sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
esac

# A snapshot stamp is a UTC timestamp like 20260925T0137Z. Anything else is a typo,
# and a typo here produces "no snapshot found", which sends you looking for a
# missing upload instead of a missing character.
[[ "${SNAPSHOT}" =~ ^[0-9]{8}T[0-9]{4}Z$ ]] \
  || fail "'${SNAPSHOT}' does not look like a snapshot stamp (e.g. ${DEFAULT_SNAPSHOT}).
       Try: bash scripts/load.sh --list"

SRC="${BUCKET}/${SNAPSHOT}"

# --------------------------------------------------------------------------
# Preflight
# --------------------------------------------------------------------------
bold "A4I kickoff demo - loading orbital conjunction tables, snapshot ${SNAPSHOT}"
echo

command -v bq     >/dev/null 2>&1 || fail "'bq' not found. Run this in Cloud Shell."
command -v gcloud >/dev/null 2>&1 || fail "'gcloud' not found. Run this in Cloud Shell."

PROJECT_ID="$(gcloud config get-value project 2>/dev/null || true)"
[[ -n "${PROJECT_ID}" && "${PROJECT_ID}" != "(unset)" ]] \
  || fail "No project set. Run: gcloud config set project YOUR_PROJECT_ID"

info "Project  : ${PROJECT_ID}"
info "Snapshot : ${SNAPSHOT}"
info "Source   : ${SRC}"
info "Dataset  : ${DATASET} (${LOCATION})"
echo

if ! gcloud storage ls "${SRC}/" >/dev/null 2>&1; then
  bold "No published tables for snapshot '${SNAPSHOT}'."
  echo
  list_snapshots
  exit 1
fi

# --------------------------------------------------------------------------
# Create the dataset
# --------------------------------------------------------------------------
bold "1/3  Creating dataset"

# `bq ls -d NAME` does NOT ask whether a dataset exists - it lists the datasets in a
# PROJECT called NAME. It reports "missing" for a dataset that is there, and the
# following `mk` then dies on the second run. `bq show --dataset` asks the right question.
dataset_exists() {
  bq --project_id="${PROJECT_ID}" show --dataset --format=none \
     "${PROJECT_ID}:${DATASET}" >/dev/null 2>&1
}

if dataset_exists; then
  info "${DATASET} already exists - reusing it"
else
  if mk_out="$(bq --project_id="${PROJECT_ID}" --location="${LOCATION}" \
                  mk --dataset "${PROJECT_ID}:${DATASET}" 2>&1)"; then
    info "created ${DATASET}"
  elif grep -qi "already exists" <<<"${mk_out}"; then
    info "${DATASET} already exists - reusing it"
  else
    fail "Could not create dataset ${DATASET}:
       ${mk_out}"
  fi
fi
echo

# --------------------------------------------------------------------------
# Load each table
# --------------------------------------------------------------------------
bold "2/3  Loading tables"
for table in "${TABLES[@]}"; do
  uri="${SRC}/${table}/data.parquet"
  gcloud storage ls "${uri}" >/dev/null 2>&1 \
    || fail "Missing ${uri}. The published snapshot is incomplete - re-publish from the notebook."
  info "loading ${table}..."
  bq --project_id="${PROJECT_ID}" --location="${LOCATION}" load \
     --source_format=PARQUET --replace \
     "${DATASET}.${table}" "${uri}" >/dev/null
done
echo

# --------------------------------------------------------------------------
# Verify - never trust a load you did not check
# --------------------------------------------------------------------------
bold "3/3  Verifying"
count() {
  bq --project_id="${PROJECT_ID}" --location="${LOCATION}" query --use_legacy_sql=false \
     --format=csv "SELECT COUNT(*) FROM \`${PROJECT_ID}.${DATASET}.$1\`" | tail -n 1
}
FAILED=0
for table in "${TABLES[@]}"; do
  rows="$(count "${table}")"
  if [[ "${rows}" == "0" ]]; then
    printf '  %-16s %s\n' "${table}" "0 rows  <-- EMPTY"; FAILED=1
  else
    printf '  %-16s %s rows\n' "${table}" "${rows}"
  fi
done
echo
[[ "${FAILED}" -eq 0 ]] || fail "A table loaded empty. Re-publish the snapshot from the notebook."

fleet="$(count fleet)"
[[ "${fleet}" == "12" ]] || fail "fleet has ${fleet} rows; Cymbal Orbital has 12 satellites."

bold "The week, as the screen saw it"
bq --project_id="${PROJECT_ID}" --location="${LOCATION}" query --use_legacy_sql=false --format=pretty \
  "SELECT fleet_sat, object_name, FORMAT_TIMESTAMP('%a %d %b %H:%M UTC', tca_utc) AS closest_approach,
          miss_m, element_age_at_tca_days AS elements_days_old, triage
   FROM \`${PROJECT_ID}.${DATASET}.conjunctions\`
   ORDER BY max_pc DESC LIMIT 5"
echo

bold "Ready."
echo
echo "  Your tables are in ${PROJECT_ID}.${DATASET}"
echo "  Safe to re-run at any time - each load replaces the whole table."
echo
echo "  Remember what the probabilities rest on: public orbital elements carry no"
echo "  covariance, so every probability in 'conjunctions' is either a worst case"
echo "  or computed under a stated assumption - see snapshot_info. Say which."
echo
