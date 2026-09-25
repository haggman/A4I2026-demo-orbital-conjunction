"""Every setting the agent reads, in one place. Environment variables win; the defaults match the notebook."""
import os

import google.auth

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT") or google.auth.default()[1]
DATASET = os.environ.get("A4I_DATASET", "a4i_orbit")

# The Agent Runtime code sandbox, created ahead of time by agent/setup_sandbox.py and handed over by name.
# Creating the first sandbox in an Agent Runtime instance took three minutes in testing, and ADK's executor
# does not remember a sandbox it created itself between turns—so we never let it create one.
SANDBOX = os.environ.get("A4I_SANDBOX", "")

# Gemini 3.8 Flash, served from the GLOBAL endpoint. Regional endpoints (us-central1 and the rest) may answer
# 404 for newer models, and Cloud Run sets a regional location for the service—agent.py overrides it for the model.
MODEL = os.environ.get("A4I_MODEL", "gemini-3.8-flash")
MODEL_LOCATION = os.environ.get("A4I_MODEL_LOCATION", "global")

# The demo's frozen "now"—the same instant notebooks/demo_01_load_explore.ipynb screens from.
NOW_UTC = os.environ.get("A4I_NOW_UTC", "2026-09-25T01:00:00Z")

# Cymbal Orbital is fictional, so its spacecraft budget is ours to state. These two numbers are the ONLY
# source of every "days of mission life" figure the agent quotes. Say so when you quote one.
DESIGN_LIFE_YEARS = float(os.environ.get("A4I_DESIGN_LIFE_YEARS", "7"))
DELTA_V_BUDGET_M_S = float(os.environ.get("A4I_DELTA_V_BUDGET_M_S", "30"))

# "Clear" means the worst-case collision probability is below this. With a 5 m hard-body radius that is
# a miss of about 3 km. A policy choice, not a physical constant.
CLEAR_PC = float(os.environ.get("A4I_CLEAR_PC", "1e-6"))
