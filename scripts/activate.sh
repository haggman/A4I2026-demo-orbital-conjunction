# Get a Cloud Shell terminal ready to run the demo. SOURCE it, from anywhere:
#
#     source scripts/activate.sh
#
# It makes the Python environment if it is missing (and updates it if the requirements changed), switches it
# on, points Google Cloud at your current project, moves you to the repo root, and prints the settings in
# force: demo.env, plus the sandbox that agent/setup_sandbox.py recorded. Safe to source again at any time.

_a4i_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
_a4i_venv="${A4I_VENV:-$HOME/.venvs/a4i-demo}"
_a4i_adk="${ADK_VERSION:-2.7.0}"
_a4i_reqs="${_a4i_root}/agent/cymbal_ops/requirements.txt"

if [[ ! -x "${_a4i_venv}/bin/python" ]]; then
  echo "Making the Python environment at ${_a4i_venv} (a minute or two, once)..."
  python3 -m venv "${_a4i_venv}" || { echo "Could not make ${_a4i_venv}." >&2; return 1; }
fi
# shellcheck disable=SC1091
source "${_a4i_venv}/bin/activate"

_a4i_want="$( { cat "${_a4i_reqs}"; echo "google-adk[mcp]==${_a4i_adk}"; } | sha256sum | cut -c1-16)"
if [[ "$(cat "${_a4i_venv}/.a4i-installed" 2>/dev/null)" != "${_a4i_want}" ]]; then
  echo "Installing the pinned packages (ADK ${_a4i_adk})..."
  pip install -q --upgrade pip \
    && pip install -q "google-adk[mcp]==${_a4i_adk}" -r "${_a4i_reqs}" \
    && echo "${_a4i_want}" > "${_a4i_venv}/.a4i-installed" \
    || { echo "The install failed; fix the error above and source this again." >&2; return 1; }
fi

_a4i_project="$(gcloud config get-value project 2>/dev/null)"
if [[ -z "${_a4i_project}" || "${_a4i_project}" == "(unset)" ]]; then
  echo "No Google Cloud project set. Run: gcloud config set project YOUR_PROJECT_ID, then source this again." >&2
  return 1
fi
export GOOGLE_CLOUD_PROJECT="${_a4i_project}"
cd "${_a4i_root}" || return 1

echo "Ready: $(python -c 'import importlib.metadata as m; print("google-adk", m.version("google-adk"))') in ${_a4i_venv}"
python agent/cymbal_ops/config.py | sed 's/^/  /'
if grep -q '^A4I_SANDBOX=' agent/cymbal_ops/.env 2>/dev/null; then
  echo "  sandbox: $(grep '^A4I_SANDBOX=' agent/cymbal_ops/.env | cut -d= -f2- | sed 's#.*/reasoningEngines/#reasoningEngines/#')"
else
  echo "  sandbox: none yet. Run: python agent/setup_sandbox.py"
fi
echo "  settings file: demo.env    try: python agent/smoke_test.py --quick  ·  python agent/model_check.py  ·  adk web agent"
unset _a4i_root _a4i_venv _a4i_adk _a4i_reqs _a4i_want _a4i_project
