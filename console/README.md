# console/—the flight dynamics console

**Why is this an agent?** A script can tell you the miss distance. It takes an agent to work out what to do about
it: is the tracking fresh enough to act on, can the other object move, what is the cheapest burn that clears it
and when, does that burn cause a new problem, write it up for the flight director, and wait for a human to say go.

The console makes that visible. Time runs over the pinned week; a **watcher** (plain code, no model) notices what
matters; it **wakes the agent** to decide; the agent posts a card; the operator presses **Approve** or **Hold**.
The physics stays in deterministic tools. The agent runs the playbook around them.

| Piece | What it is |
|---|---|
| `sim.py` | The clock (1×, 1 min/s, 10 min/s, 1 h/s; Skip to next) and the watcher's rules. Deterministic |
| `agent_bridge.py` | The same `root_agent` as `adk web` and Cloud Run, run in-process (`InMemoryRunner`), one session for the cards and the chat. Records every live alert; replays a recording |
| `app.py` + `static/` | FastAPI and the one-page screen: fleet, encounter picture, range gauge, the desk feed, the week |
| `orbits.py`, `physics.py` | SGP4 on the pinned elements; the sandbox's own `orbit_whatif`, run here to re-check an approved burn |
| `data.py` | Reads the console's slice of the snapshot from BigQuery into `.snapshot_extract.json` (git-ignored) |
| `make_scenario.py` → `scenario.json` | The storyline, and the **one simulated input**: Tuesday's fresh tracking for moment B |
| `test_sim.py` | The whole week headless with a scripted stand-in for the agent: prints every card |

## The watcher's rules

- At the start: one card for the week; "too late to act" for anything under 30 minutes away; one "fresh tracking
  requested" card listing everything whose elements will be over 5 days old at closest approach.
- **ESCALATE** (worst-case Pc ≥ 1e-4) on fresh tracking: wake the agent 18 hours before closest approach.
- A tracking update arrives: recompute, card, and wake the agent to re-assess.
- An approved burn executes at its time; every approach we were tracking gets a card as it passes.
- The clock stops while the agent works and waits for Approve or Hold.

## The one thing that is simulated

The snapshot has no future, so moment B's fresh tracking on Tuesday is made by `make_scenario.py` from the
snapshot's own elements: moved to the new epoch with SGP4's secular rates and re-anchored to where the original
elements put the object (SGP4's drag terms are not secular, so the move alone drifts a few km; the script checks
the miss comes back at the snapshot's value), then shifted along the object's own track to a stated target miss. It is
labelled SIMULATED on every card and in the agent's instructions.

## Run it

```bash
source scripts/activate.sh
python console/data.py                  # once per project: the console's slice of the snapshot
python console/make_scenario.py         # only if you change the storyline; scenario.json is committed
python console/test_sim.py              # the week, headless, no Gemini
uvicorn console.app:app --port 8080     # then Web Preview > Preview on port 8080
bash console/deploy.sh                  # Cloud Run: cymbal-console, one instance, authentication required
```

## If Gemini is slow on the day: replay

Every live run records its agent turns to `console/recordings/run-<time>.json`. Keep a good rehearsal by renaming
it `rehearsal.json` and committing it. The menu (⋯) switches the agent to **replay**: the same cards at the same
sim moments, with the same steps, and no model call. The header says REPLAY while it is on. A recording is only
ever written by a real run.
