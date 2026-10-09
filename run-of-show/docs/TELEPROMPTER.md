# Teleprompter · A4I 2026 kickoff demo · Cymbal Orbital

A live demo, no deck: one step per page, and the tab to be on is the first thing on each page. Under ten minutes. It walks the room's own build path (Load & Explore, Build, Differentiate, Deploy, Show) on a finished sixth challenge. Everything runs from one Cloud Shell started with bash scripts/start_demo.sh.

→ marks what a good result looks like.

| # | Tab | Time | Block |
|---|---|---|---|
| 1 | GitHub · the demo repo | 0.5 min | [The challenge: which of these warnings is real?](#b1) |
| 2 | Colab Enterprise · the data notebook | 1.5 min | [Load & Explore: load it, distrust it, validate it](#b2) |
| 3 | ADK web UI · port 8000 | 1.5 min | [Build: an agent on the required stack](#b3) |
| 4 | ADK web UI · same session | 2 min | [Differentiate: our own tool, and the code sandbox](#b4) |
| 5 | Google Cloud console · Cloud Run | 0.5 min | [Deploy: the same agent, running in the cloud](#b5) |
| 6 | Console · port 8080 | 3 min | [Show: the finished product](#b6) |
| 7 | Console · the CYMBAL-04 card | 0.5 min | [Close: rigor and judgment](#b7) |

---

## BEFORE THE SHOW · 1 · ONCE PER PROJECT

**CLOUD SHELL · a fresh project · about 10 minutes**

```text
git clone https://github.com/haggman/A4I2026-demo-orbital-conjunction.git
cd A4I2026-demo-orbital-conjunction
bash scripts/build_demo.sh
```

→ *Data loads (850 conjunctions) · sandbox created · smoke test: 7 checks PASS · Cloud Run deploys cymbal-ops · Ready.*

**COLAB ENTERPRISE · about 3 minutes**

Import notebooks/demo_01_load_explore.ipynb from the repo ▸ Runtime ▸ Run all

→ *Section 10: 850 approaches. Section 11: every check PASS. Keep this tab: it's step 2.*

Once per Google Cloud project. A new Google Skills lab is a new project: start here again.

---

## BEFORE THE SHOW · 2 · MORNING OF

**CLOUD SHELL · repo root · the start block**

```text
bash scripts/start_demo.sh
```

→ *Sandbox ✓ · model check · port 8000 ✓ · port 8080 ✓ · console: replay rehearsal · Ready.*

**READ THE MODEL CHECK**

Default model quick (a few seconds) → steps 3–4 run live as written.  
Slow → still run them; use each step's IF IT GOES WRONG line. The console is a replay either way.

**COLAB ENTERPRISE**

Notebook outputs still there? If the runtime was recycled: Runtime ▸ Run all (3 minutes).

---

## BEFORE THE SHOW · 3 · OPEN THE FIVE TABS

**IN THIS ORDER, LEFT TO RIGHT**

1  GitHub ▸ haggman/A4I2026-demo-orbital-conjunction (the README)  
2  Colab Enterprise ▸ demo_01_load_explore.ipynb  
3  Web Preview ▸ Change port ▸ 8000 ▸ cymbal_ops ▸ new session  
4  Google Cloud console ▸ Cloud Run ▸ cymbal-ops  
5  Web Preview ▸ Change port ▸ 8080

→ *Tab 5: header says REPLAY, clock Fri 25 Sep 01:00:00 UTC, three watcher cards on the desk.*

Stop both web apps afterwards with: bash scripts/start_demo.sh --stop

---

<a name="b1"></a>

## 1 · Tab: GitHub · the demo repo

### The challenge: which of these warnings is real?

~0.5 min

**NEEDS** README at the top: the title and "Our satellites are made up. Everything they could hit is real."

**SAY**

A sixth challenge, built exactly the way you'll build yours today, and taken all the way to the end.

**DO**

Point at the one-line problem: a small constellation, 32,000 tracked objects, warnings that never stop.

---

<a name="b2"></a>

## 2 · Tab: Colab Enterprise · the data notebook

### Load & Explore: load it, distrust it, validate it

~1.5 min

**NEEDS** demo_01_load_explore.ipynb, already run end to end (Runtime ▸ Run all, this morning, same project).

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

> **If it goes wrong:** If the outputs are gone (kernel restarted), don't re-run live: the screen takes two minutes. Say the numbers from this page and move on.

---

<a name="b3"></a>

## 3 · Tab: ADK web UI · port 8000

### Build: an agent on the required stack

~1.5 min

**NEEDS** cymbal_ops selected, new session.

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

> **If it goes wrong:** Slow? Keep talking: every call has a time limit and retries. Past a minute, go to the console tab: its chat box is the same agent.

---

<a name="b4"></a>

## 4 · Tab: ADK web UI · same session

### Differentiate: our own tool, and the code sandbox

~2 min

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

> **If it goes wrong:** Past a minute: say "the console will show us the same answer" and move to step 5. The console replays a real run of this question.

---

<a name="b5"></a>

## 5 · Tab: Google Cloud console · Cloud Run

### Deploy: the same agent, running in the cloud

~0.5 min

**NEEDS** Navigation menu ▸ Cloud Run ▸ cymbal-ops, already open.

**DO**

Point at the service URL, Authentication: Require authentication, and the one instance.

→ *cymbal-ops, healthy, one revision.*

**SAY**

One command put it there: bash agent/deploy.sh. Your agent has to actually run somewhere too.

---

<a name="b6"></a>

## 6 · Tab: Console · port 8080

### Show: the finished product

~3 min

**NEEDS** Header says REPLAY. Clock Fri 25 Sep 01:00:00 UTC. If not: ⋯ ▸ Restart the week.

Press Skip to next for each step. The clock stops by itself when the agent is woken and waits for Approve.

**DO**

Skip to next

→ *CYMBAL-01's pass at real time: the amber dot slides by at 382 m. "Too late to act" was already on the desk.*

**DO**

Skip to next

→ *Decision needed: CYMBAL-04. The agent's steps tick in, then YOUR CALL: MANEUVER, 0.0181 m/s prograde at 04:00 → 3,036 m, 1.54 days.*

**DO**

Approve

→ *Dotted green line: after the burn (scheduled), 3,036 m.*

**DO**

Skip to next ▸ Skip to next ▸ Skip to next

→ *Burn executed at 04:00 · a quick watch-list pass · CYMBAL-04's pass: missed by 3,036 m, red ghost line at 301 m.*

**DO**

Skip to next ▸ Skip to next

→ *Tuesday: fresh tracking for SL-3 R/B (pink SIMULATED). The dot jumps from 421 m to 3,700 m and the agent says no burn.*

**DO**

Approve

> **If it goes wrong:** If the header says LIVE AGENT, switch: ⋯ ▸ Agent ▸ replay · rehearsal, then Skip to next. Replay never calls Gemini.

---

<a name="b7"></a>

## 7 · Tab: Console · the CYMBAL-04 card

### Close: rigor and judgment

~0.5 min

**DO**

CYMBAL-04 agent card ▸ Conjunction Assessment & Maneuver Recommendation

→ *Risk: worst case and assumed side by side · What we cannot see.*

**SAY**

Every number says what it rests on. That's what rigor and judgment means when you're scored.

---

*Cymbal Orbital and its twelve satellites are fictional. Everything they could hit is real: U.S. Space Command, via Space-Track.org. Generated from `src/content.js` by `src/teleprompter_md.js`: edit the source, not this file.*
