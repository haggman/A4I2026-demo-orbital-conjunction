# agent/—the finished solution

**Unlike the five challenges, this folder holds a complete, working agent.** That is the point of a demo:
it shows teams what the end of the path looks like.

It is one ADK agent with three kinds of tool, plus a sandbox:

| Piece | What it is | Why it is there |
|---|---|---|
| **BigQuery's Google-managed MCP server** | `https://bigquery.googleapis.com/mcp`, filtered to `execute_sql_readonly`, `get_table_info`, `list_table_ids` | Any question the `a4i_orbit` tables can answer—*"what should I worry about this week?"*—without us writing a tool for it. Read-only on purpose |
| **`assess_conjunction`** (ours) | Every fact about one approach, the assumptions, and the judgments that need no model | Stale tracking? Can the other object dodge? What miss counts as clear? And it stages the case file in the sandbox |
| **`maneuver_cost`** (ours) | Delta-v → days of mission life | Cymbal Orbital's budget is fictional and stated: **30 m/s over a 7-year design life**, about 85 days per m/s |
| **`build_assessment`** (ours) | The **Conjunction Assessment & Maneuver Recommendation** | Re-reads the facts from BigQuery itself, so the report's numbers come from the data, not from the model's memory |
| **`run_in_sandbox`** (ours) + **Agent Runtime code sandbox** | The model writes Python and passes it to this tool, which runs it in the sandbox | Orbital what-ifs—*"what's the smallest burn that gets us clear?"*—run somewhere isolated, not in the agent's process. `A4I_CODE_PATH=executor` swaps in ADK's `AgentEngineSandboxCodeExecutor`, which runs the same code in the same sandbox |

The model is **Gemini 3.8 Flash on the global endpoint**. The agent itself runs on Cloud Run; its sandbox
belongs to an Agent Runtime instance either way.

## The sandbox, and five things we learned about it

- **It has numpy and scipy but no `sgp4`, no network, and no `pip`.** So `assess_conjunction` uploads
  `sgp4`'s own pure-Python modules (MIT-licensed) as a small zip, with our `orbit_whatif.py` beside it,
  every time it stages a case. A sandbox that has been reset heals itself on the next call.
- **The first sandbox in a new Agent Runtime instance took three minutes to create.** `setup_sandbox.py`
  creates it ahead of time and the agent is handed its name, so that never happens on stage.
- **Pure-Python SGP4 runs at about 32 µs a step there, and each call has 300 seconds.** Screening the whole
  sky does not fit, and is not the sandbox's job: the notebook does that. The sandbox does the per-event
  physics an operator asks about.
- **In ADK 2.7.0, a turn that runs code can end the moment the code finishes.** The code executor blanks the
  model's reply so the flow will go back to the model with the output, but a later check reads the blank reply
  as "the model said nothing" (`MODEL_RETURNED_NO_CONTENT`) and ends the turn. The code runs; the operator hears
  nothing. `agent.py` wraps Gemini to pass code-bearing replies on without their finish reason, which lets the
  flow loop back as intended, and asks the model once more if a reply ever comes back empty.
- **Gemini is steadier calling a tool than writing code into its reply.** With the executor, Gemini 3.8 Flash
  sometimes answered `MALFORMED_FUNCTION_CALL` or `UNEXPECTED_TOOL_CALL` where the code should have been:
  it tried to *call* something to run the code. So by default the code goes in as the argument to a function
  tool, `run_in_sandbox(code)`, the path the model is most practised at. Same sandbox, same code, fewer surprises.

How a burn is modelled, in `sandbox_files/orbit_whatif.py`: SGP4 stays the baseline for both objects, and we
integrate only the *difference* the burn makes (two-body + J2, once with the burn and once without). What the
simple model gets wrong, it gets wrong in both runs, and it cancels.

## Files

```
agent/
  cymbal_ops/                 the ADK agent (adk web / adk deploy point here)
    agent.py                  root_agent: model, MCP toolset, our tools, the sandbox executor
    prompt.py                 the instructions—including the honesty rules
    tools.py                  assess_conjunction, run_in_sandbox, maneuver_cost, build_assessment
    sandbox.py                staging files into the sandbox
    config.py                 every setting, with its reason
    sandbox_files/orbit_whatif.py   the physics that runs in the sandbox
    requirements.txt
  setup_sandbox.py            create or reuse the sandbox, warm it, write cymbal_ops/.env
  smoke_test.py               ask the agent operator questions, headless; one diagnostic block
  deploy.sh                   Cloud Run, with its own service account and authentication required
```

## Run it

The whole build is one command from the repo root in Cloud Shell—see `scripts/build_demo.sh`. By hand:

```bash
python3 -m venv ~/.venvs/a4i-demo && source ~/.venvs/a4i-demo/bin/activate
pip install "google-adk[mcp]==2.7.0" -r agent/cymbal_ops/requirements.txt
python agent/setup_sandbox.py          # needs the a4i_orbit tables: run the notebook or scripts/load.sh first
python agent/smoke_test.py --quick
adk web agent                          # then Web Preview on port 8000
bash agent/deploy.sh                   # Cloud Run
```
