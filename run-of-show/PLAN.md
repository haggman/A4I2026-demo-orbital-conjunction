# Plan: the kickoff demo run-of-show

**Agreed with Patrick, 2026-10-09.** The scripted version is in `docs/` (built from `src/content.js`).

## What the demo is for

The room is about to spend a day building an agent in teams. The demo is a **mini-tour of what they will do, on
a finished example**: a sixth challenge, orbital conjunction screening ("Which of these warnings is real?"),
built the same way as theirs and taken all the way to the end. It walks their build path, one brief look per
step, and finishes on the finished product so they can see, at least conceptually, what theirs could become.

## Decisions

- **No deck, no slide numbers.** A live demo; each teleprompter page leads with the tab to be on.
- **One start block, then a sequence.** Everything is pre-built and running; `scripts/start_demo.sh` gets it all ready.
  No resets between steps.
- **Under ten minutes**, one brief look per step. Pacing is the instructor's call; there is no cut list.
- **The console runs in replay**, from a recording of a real run, so it behaves the same every time. Steps 3 and 4
  show the agent live. The replay is labelled on screen and said out loud.
- **Step 5 shows the Cloud Run page**, nothing more.
- **Everything lives in the demo repo and is public.** Nothing project-specific is committed: the start block reads
  the project at run time, and `console/keep_recording.py` scrubs the recording.
- **The story passes' run-in** (Skip to next before a closest approach) is 20 s at real time; other watch-list passes 10 s.

## The steps

| # | Build-path step | Tab | The one look | Min |
|---|---|---|---|---|
| — | Start block | Cloud Shell | `bash scripts/start_demo.sh`, then open the five tabs | — |
| 1 | The challenge | GitHub: this repo | "Which of these warnings is real?" Same shape as yours, finished | 0.5 |
| 2 | Load & Explore | Colab Enterprise: the notebook, already run | The wrong answer first · the two events · 850 approaches → 1 escalate, 7 watch, 842 noise | 1.5 |
| 3 | Build | ADK web UI | "What should we worry about this week?" and the MCP query in the events panel | 1.5 |
| 4 | Differentiate | ADK web UI | The burn question: our own tool, sandbox code, the cost | 2 |
| 5 | Deploy | Cloud Run page | The same agent, running in the cloud | 0.5 |
| 6 | Show | Console (replay) | Decision card, Approve, the fly-by (301 m → 3,036 m); Tuesday's "don't burn" | 3 |
| 7 | Close | Console write-up | Worst case vs assumed; what we cannot see | 0.5 |

## Still to confirm in the dry run

Listed at the end of the planning guide (`GUIDE.confirm` in `src/content.js`): Colab's table-of-contents labels and two
printed numbers, the ADK web UI's events panel, two Web Preview ports at once, and the Cloud Run page.
