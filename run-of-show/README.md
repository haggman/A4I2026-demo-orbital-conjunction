# run-of-show/—how the kickoff demo is presented

The kickoff demo is a **live, ten-minute walk through the same five steps your team takes today**, on this
finished example: **Load & Explore → Build → Differentiate → Deploy → Show**. No deck. This folder is the
script: we're leaving it here because a good Show step is part of a finished project, and you're welcome to
borrow anything in it.

| File | What it is |
|---|---|
| [`docs/TELEPROMPTER.md`](docs/TELEPROMPTER.md) | One step per page: the tab to be on, what to click, what to type, what a good result looks like |
| `docs/TELEPROMPTER - A4I kickoff demo.docx` | The same, for a second monitor |
| `docs/PLANNING GUIDE - A4I kickoff demo.docx` | The night-before document: how it works, setup, the talk track, a fact sheet |
| [`PLAN.md`](PLAN.md) | Why the demo is shaped this way, and the decisions behind it |
| `src/content.js` | The one source all three documents are built from |

## Run it

```bash
bash scripts/start_demo.sh          # from the repo root in Cloud Shell, after scripts/build_demo.sh has run once
```

It warms the code sandbox, checks Gemini is quick, starts the ADK web UI on port 8000 and the console on port
8080, and tells you which Web Preview ports to open. `bash scripts/start_demo.sh --stop` stops both.

## One thing worth knowing: the console replays a real run

In the last step, the console's agent cards are **a recording of a real run of the agent**, played back at the same
moments with the same steps (`console/recordings/rehearsal.json`). The header says REPLAY while it's on. Steps 3
and 4 show the same agent working live, so nothing is being hidden; the replay is there so a demo on conference
wifi runs the same way every time. To make your own recording: run the console live, approve both cards, then
`python console/keep_recording.py`, which checks the recording tells the story, removes anything project-specific,
plays the week twice to prove the replay is identical, and writes `rehearsal.json`.

## Rebuild the documents

```bash
cd run-of-show && npm install && bash src/build.sh
```

Edit `src/content.js`, never the generated files in `docs/`. The renderers come from the demo-pack starter kit
Patrick uses for his class demos.
