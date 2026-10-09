# Planning guide · A4I 2026 kickoff demo · Cymbal Orbital

A live demo, under ten minutes, no deck. It walks the five steps of the room's build path on a finished sixth challenge, Cymbal Orbital's conjunction screening, and ends on the finished product. Everything in this folder is public: the students may keep it.

*This is the prep document. On the day, use the teleprompter (TELEPROMPTER.md, or the Word copy). Both are generated from `src/content.js`.*

**How this demo works**

- New to this demo? Read docs/INSTRUCTOR-GUIDE.md first: how the console would run for real, why the agent is woken 18 hours out, what Skip does, how to read the picture, and what the agent did, beat by beat with screenshots.
- Steps 3 and 4 are live: the real agent, real Gemini, in the ADK web UI. Talk over the waits (about 15 s and 30 s on a good day).
- Step 6, the console, runs in REPLAY: the agent cards are a recording of a real run (console/recordings/rehearsal.json), played back at the same sim moments with the same steps, so it behaves the same every time. The header says REPLAY; say so in the talk track.
- Everything else is pre-built and only looked at: the notebook was run in the morning, the agent was deployed to Cloud Run once.
- One start block (bash scripts/start_demo.sh) gets every tab ready. No resets between steps: it's one finished thing, looked at five ways.
- Pacing is yours: each step is a brief look, and any step can be shortened to its one SAY line.


---

## 1. The story in one page

Cymbal Orbital (fictional) flies twelve small Earth-observation satellites at 880 km. The sky they share is real: 32,578 tracked objects from U.S. Space Command, pinned to one snapshot so every city sees the same numbers.

| Build-path step | Demo step | What the room sees |
|---|---|---|
| Load & Explore | 2 | The notebook: the wrong answer first, the two events, 850 → 1 that matters |
| Build | 3 | ADK + Gemini + BigQuery through the managed MCP server |
| Differentiate | 4 | Our own tool, and the Agent Runtime code sandbox running the physics |
| Deploy | 5 | The same agent on Cloud Run |
| Show | 6–7 | The console: watcher, agent, human approval; the write-up |

Two alerts carry the story. Moment A (CYMBAL-04, fresh tracking, worst case on the escalation line): burn, while it's cheap. Moment B (CYMBAL-11, tracking a week old): don't spend fuel yet, ask for fresh tracking; when it arrives (simulated), stand down.


---

## 2. Demo map

| # | Tab | Time | Block |
|---|---|---|---|
| 1 | GitHub · the demo repo | ~0.5 min | The challenge: which of these warnings is real? |
| 2 | Colab Enterprise · the data notebook | ~1.5 min | Load & Explore: load it, distrust it, validate it |
| 3 | ADK web UI · port 8000 | ~1.5 min | Build: an agent on the required stack |
| 4 | ADK web UI · same session | ~2 min | Differentiate: our own tool, and the code sandbox |
| 5 | Google Cloud console · Cloud Run | ~0.5 min | Deploy: the same agent, running in the cloud |
| 6 | Console · port 8080 | ~3 min | Show: the finished product |
| 7 | Console · the CYMBAL-04 card | ~0.5 min | Close: rigor and judgment |


---

## 3. Setup

### Once per project (a Google Skills project or your own)

**CLOUD SHELL · about 10 minutes: data, environment, sandbox, smoke test, Cloud Run**

```text
git clone https://github.com/haggman/A4I2026-demo-orbital-conjunction.git
cd A4I2026-demo-orbital-conjunction
bash scripts/build_demo.sh
```

→ *Ends with Ready. The smoke test's 7 checks PASS; the Cloud Run service cymbal-ops is up.*

**COLAB ENTERPRISE · about 3 minutes**

Open notebooks/demo_01_load_explore.ipynb ▸ Runtime ▸ Run all

→ *Section 10 shows 850 approaches; section 11's checks all PASS. Leave the tab open: its outputs are step 2.*

### The rehearsal recording (once; it's committed, so every later run reuses it)

The console replays a real run of the agent. Make one, check it, keep it:

**CLOUD SHELL · the console, live**

```text
source scripts/activate.sh
python console/data.py
uvicorn console.app:app --port 8080
```

→ *Click http://0.0.0.0:8080 in Cloud Shell. Header says LIVE AGENT.*

1. Skip to next until the CYMBAL-04 card asks for a decision; wait for YOUR CALL; Approve.
2. Skip to next until Tuesday's card; wait for YOUR CALL; Approve. Then stop uvicorn (Ctrl+C in that terminal).

**CLOUD SHELL · keep it**

```text
python console/keep_recording.py
```

→ *Kept run-… → console/recordings/rehearsal.json · moment A: 0.0181 m/s prograde at 04:00 → 3,036 m · replayed the week twice: identical.*

If it says NOT KEPT, it says why (usually: the agent chose 12:00, or a turn timed out). Rehearse again. Then get rehearsal.json into the repo: commit and push from Cloud Shell, or ⋯ More ▸ Download and commit it from your Mac.

### Morning of

**CLOUD SHELL · the start block**

```text
bash scripts/start_demo.sh
```

→ *Sandbox ✓ · the model check says the default is quick · port 8000 ✓ · port 8080 ✓ · console: replay rehearsal.*

- Open the five tabs in the order on the BEFORE KICKOFF page.
- Notebook outputs still there (re-run if the runtime was recycled).
- If the model check says Gemini is slow, the console still runs on time (replay); steps 3–4 have their fallback lines.


---

## 4. Block by block: why, talk track, steps, expected results

### 1. The challenge: which of these warnings is real?

*Tab: GitHub · the demo repo · ~0.5 min*

**Why** Every team starts at the same place: a person, a decision, a deadline. This one is finished, so they can see where the day ends.

> You operate twelve small Earth-observation satellites. About 32,000 tracked objects share their sky, the warnings never stop, and nearly all of them are noise. Which ones are real, and what do you do about them?

> It's built the way your challenge is built: load the data, build an agent, give it one thing only your challenge has, deploy it, show it. I'll walk you through each step in a minute or two.

> It's all in this repo, and the box at the top tells you where each piece lives. Read your own challenge first; come back here when you want to see what the end looks like.

**Needs** README at the top: the title and the "This one has been solved for you" box.

**SAY**

A sixth challenge, built exactly the way you'll build yours today, and taken all the way to the end.

**DO**

Point at the box's table: the five build-path steps, each with the folder that solves it.

**DO**

Scroll to Why this one matters: a small constellation, 32,000 tracked objects, warnings that never stop.

### 2. Load & Explore: load it, distrust it, validate it

*Tab: Colab Enterprise · the data notebook · ~1.5 min*

**Why** The data lane's job: load real data, find what's wrong with it, and hand the agent clean, validated tables in BigQuery.

> First thing every team does: load and explore. Here's the obvious first answer: anything that can reach our altitude is a threat. That's thousands of objects. And it's wrong, because being at the same height isn't being in the same place at the same second.

> This is the query that surprises people: a big share of what's up there came from two moments, 2007 and 2009. Kessler syndrome in one table.

> And here's the honest answer for the week: 850 close approaches, and one worth escalating. Everything after this point is about that one.

**Needs** demo_01_load_explore.ipynb, already run end to end (Runtime ▸ Run all, this morning, same project).

**DO**

Table of contents ▸ 3—The wrong answer first

→ *Thousands of objects whose orbit crosses our 880 km altitude. Every one of them really is at our height.*

**SAY**

Same height is not same place. Altitude is a filter, not an answer.

**DO**

Table of contents ▸ 7—What the data says ▸ the hook query

→ *About a quarter of what crosses our altitude comes from two events: the 2007 anti-satellite test and the 2009 collision.*

**DO**

Table of contents ▸ 10—The honest numbers

→ *850 approaches under 10 km this week: 1 ESCALATE, 7 WATCH, 842 noise.*

The notebook also carries the real messes we hit (the end of the old TLE format, stale tracking, a timestamp BigQuery refused) and a validation section that re-reads the loaded tables. Mention them only if someone asks: they're what the data lane will live through.

**If it goes wrong:** If the outputs are gone (kernel restarted), don't re-run live: the screen takes two minutes. Say the numbers from this page and move on.

### 3. Build: an agent on the required stack

*Tab: ADK web UI · port 8000 · ~1.5 min*

**Why** The agent lane's required stack, visible in one answer: ADK, Gemini, BigQuery, a managed MCP server.

> Second step: build the agent. Same required stack as yours: ADK, Gemini, BigQuery, and a Google-managed MCP server it uses to query the tables.

> Watch what it does: it decided that question needs a query, wrote it, ran it through the MCP server, and summarised. Nobody wrote that SQL for it.

**Needs** cymbal_ops selected, new session.

**TYPE in the ADK web UI**

```text
What should we worry about this week?
```

→ *One to escalate: CYMBAL-04 vs FENGYUN 1C DEB, Fri 25 Sep 20:16 UTC, 301.1 m, worst-case 1.01e-04. CYMBAL-01's pass is two minutes away and can't be acted on. About 15 s.*

**SAY**

While it works: ADK is the frame, Gemini is the reasoning, and it reads BigQuery through Google's managed MCP server.

**DO**

Events panel ▸ click an execute_sql_readonly call

→ *The SQL the agent wrote against the conjunctions table.*

**If it goes wrong:** Slow? Keep talking: every call has a time limit and retries. Past a minute, go to the console tab: its chat box is the same agent.

### 4. Differentiate: our own tool, and the code sandbox

*Tab: ADK web UI · same session · ~2 min*

**Why** Two of the requirements in one question: at least one tool you wrote, and the one differentiator your challenge names.

> Third step: differentiate. Every challenge names one thing only it has. Ours is a code sandbox: the agent writes Python and runs it somewhere isolated, not in its own process.

> And this is why we require a custom tool even though MCP can run queries: assess_conjunction decides whether the tracking is fresh enough to act on, whether the other object can move, and what counts as clear. That's judgment, and judgment is code.

> Burning earlier is cheaper: half the fuel, and the difference is more than a day of the satellite's life.

**SAME CHAT**

**FOLLOW-UP (same session)**

```text
What is the smallest burn that gets CYMBAL-04 clear? Compare burning at 04:00 and at 12:00 UTC today, and tell me what each costs.
```

→ *04:00: 0.0181 m/s prograde → 3,036 m, 1.54 days of mission life. 12:00: 0.0343 m/s → 3,035 m, 2.92 days. About 30 s.*

**SAY**

While it works: assess_conjunction is our own Python tool; the physics runs in the Agent Runtime code sandbox; maneuver_cost prices it.

**DO**

Events panel ▸ click the run_in_sandbox call

→ *Four lines of Python the model wrote, using our orbit_whatif module.*

**If it goes wrong:** Past a minute: say "the console will show us the same answer" and move to step 5. The console replays a real run of this question.

### 5. Deploy: the same agent, running in the cloud

*Tab: Google Cloud console · Cloud Run · ~0.5 min*

**Why** Deploy is a required step on their path; seeing it is one command makes it less scary.

> Fourth: deploy. This is Cloud Run: Google runs our container, we manage no servers. It's the same agent you just watched, on a real URL, one command.

> Two settings worth stealing. Authentication required, because this agent can run code and query our data. And one instance kept warm, because the first request after a quiet hour is usually the one you make on stage. Yours goes to Cloud Run or Agent Runtime, your choice.

**Needs** Navigation menu ▸ Cloud Run ▸ cymbal-ops, already open.

**WHAT THEY'RE LOOKING AT**

Cloud Run: Google runs your container for you, no servers to manage.  
cymbal-ops: the same agent as step 3, plus the ADK web UI, packaged as a container by adk deploy.  
URL: where it answers on the internet.  
Require authentication: only signed-in people with access can reach it. The agent can run code and query BigQuery; an open URL on a slide is an invitation.  
Minimum instances 1: one copy always running, so the first request after a quiet hour doesn't wait for a cold start.  
Revision: each deploy is a new version; Cloud Run can roll back to any of them.

**DO**

Point at the service URL and Authentication: Require authentication. Minimum instances 1 is in the revision's details; if it isn't quick to find, just say it.

→ *cymbal-ops, healthy, one instance kept warm.*

**SAY**

One command put it there: bash agent/deploy.sh. Your agent has to actually run somewhere too.

### 6. Show: the finished product

*Tab: Console · port 8080 · ~3 min*

**Why** What "an agent, not a chat box" looks like: plain code watches, the agent decides, a human approves. Two alerts, two opposite answers.

> Last step, and it's what your judges will see: show it. This is the finished product. Time runs over the week; plain code, no AI, watches for anything that matters; and when something needs a decision, it wakes the agent.

> Eighteen hours out, when the tracking is as good as it will get and there's still time to burn cheaply, the agent runs the playbook you just watched: assess, size the burn at two times, price it, write it up. Then it waits for a human. I approve.

> There it goes. Without the burn, 301 metres. With it, three kilometres, for a day and a half of the satellite's life.

> Now the other alert. On Friday this rocket body was stale: the tracking was a week old, so the agent asked for fresh tracking instead of spending fuel. Tuesday it arrives, and the right answer is: do nothing. Same agent, opposite answer. That's judgment.

> The cards you just saw are a recording of a real run of the agent, played back so a demo on conference wifi runs the same every time. That's a trick worth stealing for your own Show step.

**Needs** Header says REPLAY. Clock Fri 25 Sep 01:00:00 UTC. If not: ⋯ ▸ Restart the week.

*Press Skip to next for each step. The clock stops by itself when the agent is woken and waits for Approve.*

**DO**

Skip to next

→ *CYMBAL-01's pass at real time: the amber dot slides by at 382 m. "Too late to act" was already on the desk.*

**DO**

Skip to next

→ *Decision needed: CYMBAL-04. The agent's steps tick in, then YOUR CALL: MANEUVER, 0.0181 m/s prograde at 04:00 → 3,036 m, 1.54 days.*

**THE PURPLE AGENT CARD, TOP TO BOTTOM**

Watcher's line: why it woke the agent. 18 h out (tracking as good as it gets, still time to burn cheaply), worst case 1 in 10,000, tracking fresh.  
assess_conjunction (our tool): the facts from BigQuery; is the tracking fresh, can the debris dodge (no); stages the case in the sandbox.  
run_in_sandbox: the agent's own Python, run in the Agent Runtime code sandbox. Sizes the burn at 04:00 (0.0181 m/s) and noon (0.0343 m/s).  
maneuver_cost ×2: each burn in days of satellite life: 1.54 vs 2.92.  
build_assessment: writes it up, re-reading every fact from BigQuery.  
Then: the agent's words · the bold summary · the write-up (click to open) · Approve / Hold · how long it took (about 23 s).

**DO**

Approve

→ *Dotted green line: after the burn (scheduled), 3,036 m.*

**DO**

Skip to next ▸ Skip to next

→ *Burn executed at 04:00: the dot jumps up to the green line · CYMBAL-04's pass at real time: missed by 3,036 m, red ghost line at 301 m.*

**DO**

Skip to next

→ *Tuesday: fresh tracking for SL-3 R/B (pink SIMULATED). The dot jumps from 421 m to 3,700 m and the agent says no burn.*

**DO**

Approve

**If it goes wrong:** If the header says LIVE AGENT, switch: ⋯ ▸ Agent ▸ replay · rehearsal, then Skip to next. Replay never calls Gemini.

### 7. Close: rigor and judgment

*Tab: Console · the CYMBAL-04 card · ~0.5 min*

**Why** Their judging rubric rewards rigor and judgment; the write-up shows what that looks like on paper.

> Look at how it writes it up: the worst case, which needs no assumptions, next to the number under an assumed uncertainty, and a section on what we can't see. And the Tuesday update is labelled SIMULATED wherever it appears.

> That's the bar: every number from a tool or a query, every assumption stated. Now go build yours.

**DO**

CYMBAL-04 agent card ▸ Conjunction Assessment & Maneuver Recommendation

→ *Risk: worst case and assumed side by side · What we cannot see.*

**SAY**

Every number says what it rests on. That's what rigor and judgment means when you're scored.


---

## 5. Fact sheet: keep on the second screen

### The snapshot

- Snapshot 20260925T0137Z; the demo's frozen "now" is Fri 25 Sep 2026 01:00 UTC.
- 32,578 tracked objects on orbit (Space-Track, elements newer than 30 days).
- 850 approaches under 10 km in the week across 12 satellites: 1 ESCALATE, 7 WATCH, 842 noise.
- ESCALATE = worst-case probability at or above 1 in 10,000. WATCH = closer than 1 km. Stale = tracking more than 5 days old at closest approach.
- Clear = worst-case probability below 1 in a million: a miss of about 3,033 m at a 5 m hard-body radius.

### Moment A — burn

- CYMBAL-04 vs FENGYUN 1C DEB (31178), a fragment of the 2007 anti-satellite test.
- Fri 25 Sep 20:16:10 UTC · 301.1 m · worst case 1.01e-04 · closing at 7.5 km/s · tracking 2.55 days old (fresh).
- Burn at 04:00: 0.0181 m/s prograde → 3,036 m, 1.54 days of mission life. At 12:00: 0.0343 m/s, 2.92 days.
- Mission-life figures rest on a stated budget: 30 m/s over a 7-year design life (about 85 days per m/s). Fictional.

### Moment B — wait

- CYMBAL-11 vs SL-3 R/B (8520), a Soviet upper stage.
- Thu 1 Oct 17:45 UTC · 420.7 m · tracking 7.72 days old at closest approach (stale) → fresh tracking requested, no burn.
- Tue 29 Sep 06:00: fresh tracking arrives (SIMULATED: made by console/make_scenario.py from the snapshot's own elements, moved 7 km along track). Recomputed: 3,700 m, worst case 6.7e-07. Stand down.

### Also on screen

- CYMBAL-01 vs SL-3 R/B (11289) at 01:02 UTC, 382 m: two minutes from "now", too late to act.
- Five other WATCH approaches on stale tracking: one watcher card lists them.


---

## 6. Confirm in the dry run

These come from the docs, not from the live product. Check each once and correct content.js if a label differs:

- [ ] Colab Enterprise: the Table of contents entry names for sections 3, 7 and 10, and the count of objects crossing 855–905 km printed in section 3 (put the number on the teleprompter).
- [ ] Section 7's hook numbers (the share of objects and of debris from the 2007 and 2009 events) as printed in this project.
- [ ] ADK web UI 2.7.0: the name of the events / trace panel and that clicking a tool call shows its arguments.
- [ ] Cloud Run page: where Minimum instances 1 shows for cymbal-ops without clicking around (put the exact place on the teleprompter).
- [ ] The start block's two links each open their own Web Preview tab (ports 8000 and 8080), both working at once.
- [ ] The Cloud Run page shows cymbal-ops with "Require authentication" and one instance.


---

## Appendix: files

| Path | Used in | What it is |
|---|---|---|
| scripts/start_demo.sh | Start | The start block: sandbox, model check, ADK web UI on 8000, console on 8080 in replay |
| scripts/build_demo.sh | Setup | Builds the whole demo in a project, once |
| notebooks/demo_01_load_explore.ipynb | Step 2 | Load & Explore |
| agent/cymbal_ops/ | Steps 3–5 | The agent: tools.py, prompt.py, the sandbox physics |
| console/ | Steps 6–7 | The console; console/recordings/rehearsal.json is the replay |
| console/keep_recording.py | Setup | Checks a live rehearsal and keeps it as the replay |


*Cymbal Orbital and its twelve satellites are fictional. Everything they could hit is real: U.S. Space Command, via Space-Track.org.*

*Generated from `src/content.js` by `src/guide_md.js`: edit the source, not this file.*
