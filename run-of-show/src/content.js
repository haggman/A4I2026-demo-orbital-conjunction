// THE single source for the kickoff demo's run-of-show. Three renderers read it:
//   teleprompter.js    → docs/TELEPROMPTER - A4I kickoff demo.docx   on the day: one step per page, the tab first
//   teleprompter_md.js → docs/TELEPROMPTER.md                        the same, readable on GitHub
//   guide.js           → docs/PLANNING GUIDE - A4I kickoff demo.docx  prep: how it works, setup, talk track, fact sheet
// Edit here, then:  bash run-of-show/src/build.sh      Never edit the generated documents; the next build overwrites them.
// Every number below comes from the pinned snapshot 20260925T0137Z (see the fact sheet). Don't change one without re-checking it.

const PACK = {
  course: "A4I 2026 kickoff demo",
  scenario: "Cymbal Orbital",
  subtitle: "A live demo, no deck: one step per page, and the tab to be on is the first thing on each page. Under ten minutes. "
    + "It walks the room's own build path (Load & Explore, Build, Differentiate, Deploy, Show) on a finished sixth challenge.",
  filesNote: "Everything runs from one Cloud Shell started with bash scripts/start_demo.sh.",
  fictionNote: "Cymbal Orbital and its twelve satellites are fictional. Everything they could hit is real: U.S. Space Command, via Space-Track.org.",
  docs: { teleprompter: "TELEPROMPTER - A4I kickoff demo.docx", guide: "PLANNING GUIDE - A4I kickoff demo.docx" },
  sessions: [
    { id: 1, label: "KICKOFF", before: [
      "Cloud Shell, repo root:  bash scripts/start_demo.sh   → ends with \"Ready\" and both ports ✓",
      "Tab 1: GitHub ▸ haggman/A4I2026-demo-orbital-conjunction (the README)",
      "Tab 2: Colab Enterprise ▸ demo_01_load_explore.ipynb, run this morning (Runtime ▸ Run all)",
      "Tab 3: Web Preview ▸ Change port ▸ 8000 (ADK web UI) ▸ cymbal_ops ▸ new session",
      "Tab 4: Google Cloud console ▸ Cloud Run ▸ cymbal-ops",
      "Tab 5: Web Preview ▸ Change port ▸ 8080 (console): header says REPLAY, clock Fri 25 Sep 01:00:00 UTC",
    ] },
  ],
  tags: {
    SHELL: { label: "CLOUD SHELL" },
    TYPE: { label: "TYPE in the ADK web UI" },
    "FOLLOW-UP": { label: "FOLLOW-UP (same session)" },
  },
};

const blocks = [
// ---------------------------------------------------------------------------------------------------------------- 1
{
  id: "card", session: 1, tab: "GitHub · the demo repo", mins: 0.5,
  title: "The challenge: which of these warnings is real?",
  needs: "README at the top: the title and \"Our satellites are made up. Everything they could hit is real.\"",
  steps: [
    { tag: "SAY", text: "A sixth challenge, built exactly the way you'll build yours today, and taken all the way to the end." },
    { tag: "DO", text: "Point at the one-line problem: a small constellation, 32,000 tracked objects, warnings that never stop." },
  ],
  why: "Every team starts at the same place: a person, a decision, a deadline. This one is finished, so they can see where the day ends.",
  say: ["You operate twelve small Earth-observation satellites. About 32,000 tracked objects share their sky, the warnings never stop, and nearly all of them are noise. Which ones are real, and what do you do about them?",
        "It's built the way your challenge is built: load the data, build an agent, give it one thing only your challenge has, deploy it, show it. I'll walk you through each step in a minute or two."],
},
// ---------------------------------------------------------------------------------------------------------------- 2
{
  id: "data", session: 1, tab: "Colab Enterprise · the data notebook", mins: 1.5,
  title: "Load & Explore: load it, distrust it, validate it",
  needs: "demo_01_load_explore.ipynb, already run end to end (Runtime ▸ Run all, this morning, same project).",
  steps: [
    { tag: "DO", text: "Table of contents ▸ 3—The wrong answer first", expect: "Thousands of objects whose orbit crosses our 880 km altitude. Every one of them really is at our height." },
    { tag: "SAY", text: "Same height is not same place. Altitude is a filter, not an answer." },
    { tag: "DO", text: "Table of contents ▸ 7—What the data says ▸ the hook query", expect: "About a quarter of what crosses our altitude comes from two events: the 2007 anti-satellite test and the 2009 collision." },
    { tag: "DO", text: "Table of contents ▸ 10—The honest numbers", expect: "850 approaches under 10 km this week: 1 ESCALATE, 7 WATCH, 842 noise." },
  ],
  gotcha: "If the outputs are gone (kernel restarted), don't re-run live: the screen takes two minutes. Say the numbers from this page and move on.",
  why: "The data lane's job: load real data, find what's wrong with it, and hand the agent clean, validated tables in BigQuery.",
  say: ["First thing every team does: load and explore. Here's the obvious first answer: anything that can reach our altitude is a threat. That's thousands of objects. And it's wrong, because being at the same height isn't being in the same place at the same second.",
        "This is the query that surprises people: a big share of what's up there came from two moments, 2007 and 2009. Kessler syndrome in one table.",
        "And here's the honest answer for the week: 850 close approaches, and one worth escalating. Everything after this point is about that one."],
  detail: ["The notebook also carries the real messes we hit (the end of the old TLE format, stale tracking, a timestamp BigQuery refused) and a validation section that re-reads the loaded tables. Mention them only if someone asks: they're what the data lane will live through."],
},
// ---------------------------------------------------------------------------------------------------------------- 3
{
  id: "build", session: 1, tab: "ADK web UI · port 8000", mins: 1.5,
  title: "Build: an agent on the required stack",
  needs: "cymbal_ops selected, new session.",
  steps: [
    { tag: "TYPE", text: "What should we worry about this week?",
      expect: "One to escalate: CYMBAL-04 vs FENGYUN 1C DEB, Fri 25 Sep 20:16 UTC, 301.1 m, worst-case 1.01e-04. CYMBAL-01's pass is two minutes away and can't be acted on. About 15 s." },
    { tag: "SAY", text: "While it works: ADK is the frame, Gemini is the reasoning, and it reads BigQuery through Google's managed MCP server." },
    { tag: "DO", text: "Events panel ▸ click an execute_sql_readonly call", expect: "The SQL the agent wrote against the conjunctions table." },
  ],
  gotcha: "Slow? Keep talking: every call has a time limit and retries. Past a minute, go to the console tab: its chat box is the same agent.",
  why: "The agent lane's required stack, visible in one answer: ADK, Gemini, BigQuery, a managed MCP server.",
  say: ["Second step: build the agent. Same required stack as yours: ADK, Gemini, BigQuery, and a Google-managed MCP server it uses to query the tables.",
        "Watch what it does: it decided that question needs a query, wrote it, ran it through the MCP server, and summarised. Nobody wrote that SQL for it."],
},
// ---------------------------------------------------------------------------------------------------------------- 4
{
  id: "differentiate", session: 1, tab: "ADK web UI · same session", mins: 2,
  title: "Differentiate: our own tool, and the code sandbox",
  sameChat: true,
  steps: [
    { tag: "FOLLOW-UP", text: "What is the smallest burn that gets CYMBAL-04 clear? Compare burning at 04:00 and at 12:00 UTC today, and tell me what each costs.",
      expect: "04:00: 0.0181 m/s prograde → 3,036 m, 1.54 days of mission life. 12:00: 0.0343 m/s → 3,035 m, 2.92 days. About 30 s." },
    { tag: "SAY", text: "While it works: assess_conjunction is our own Python tool; the physics runs in the Agent Runtime code sandbox; maneuver_cost prices it." },
    { tag: "DO", text: "Events panel ▸ click the run_in_sandbox call", expect: "Four lines of Python the model wrote, using our orbit_whatif module." },
  ],
  gotcha: "Past a minute: say \"the console will show us the same answer\" and move to step 5. The console replays a real run of this question.",
  why: "Two of the requirements in one question: at least one tool you wrote, and the one differentiator your challenge names.",
  say: ["Third step: differentiate. Every challenge names one thing only it has. Ours is a code sandbox: the agent writes Python and runs it somewhere isolated, not in its own process.",
        "And this is why we require a custom tool even though MCP can run queries: assess_conjunction decides whether the tracking is fresh enough to act on, whether the other object can move, and what counts as clear. That's judgment, and judgment is code.",
        "Burning earlier is cheaper: half the fuel, and the difference is more than a day of the satellite's life."],
},
// ---------------------------------------------------------------------------------------------------------------- 5
{
  id: "deploy", session: 1, tab: "Google Cloud console · Cloud Run", mins: 0.5,
  title: "Deploy: the same agent, running in the cloud",
  needs: "Navigation menu ▸ Cloud Run ▸ cymbal-ops, already open.",
  steps: [
    { tag: "DO", text: "Point at the service URL, Authentication: Require authentication, and the one instance.", expect: "cymbal-ops, healthy, one revision." },
    { tag: "SAY", text: "One command put it there: bash agent/deploy.sh. Your agent has to actually run somewhere too." },
  ],
  why: "Deploy is a required step on their path; seeing it is one command makes it less scary.",
  say: ["Fourth: deploy. Same agent, on Cloud Run, authentication required, one command. Yours goes to Cloud Run or Agent Runtime, your choice."],
},
// ---------------------------------------------------------------------------------------------------------------- 6
{
  id: "show", session: 1, tab: "Console · port 8080", mins: 3,
  title: "Show: the finished product",
  needs: "Header says REPLAY. Clock Fri 25 Sep 01:00:00 UTC. If not: ⋯ ▸ Restart the week.",
  intro: "Press Skip to next for each step. The clock stops by itself when the agent is woken and waits for Approve.",
  steps: [
    { tag: "DO", text: "Skip to next", expect: "CYMBAL-01's pass at real time: the amber dot slides by at 382 m. \"Too late to act\" was already on the desk." },
    { tag: "DO", text: "Skip to next", expect: "Decision needed: CYMBAL-04. The agent's steps tick in, then YOUR CALL: MANEUVER, 0.0181 m/s prograde at 04:00 → 3,036 m, 1.54 days." },
    { tag: "DO", text: "Approve", expect: "Dotted green line: after the burn (scheduled), 3,036 m." },
    { tag: "DO", text: "Skip to next ▸ Skip to next ▸ Skip to next", expect: "Burn executed at 04:00 · a quick watch-list pass · CYMBAL-04's pass: missed by 3,036 m, red ghost line at 301 m." },
    { tag: "DO", text: "Skip to next ▸ Skip to next", expect: "Tuesday: fresh tracking for SL-3 R/B (pink SIMULATED). The dot jumps from 421 m to 3,700 m and the agent says no burn." },
    { tag: "DO", text: "Approve" },
  ],
  gotcha: "If the header says LIVE AGENT, switch: ⋯ ▸ Agent ▸ replay · rehearsal, then Skip to next. Replay never calls Gemini.",
  why: "What \"an agent, not a chat box\" looks like: plain code watches, the agent decides, a human approves. Two alerts, two opposite answers.",
  say: ["Last step, and it's what your judges will see: show it. This is the finished product. Time runs over the week; plain code, no AI, watches for anything that matters; and when something needs a decision, it wakes the agent.",
        "Eighteen hours out, the agent runs the playbook you just watched: assess, size the burn at two times, price it, write it up. Then it waits for a human. I approve.",
        "There it goes. Without the burn, 301 metres. With it, three kilometres, for a day and a half of the satellite's life.",
        "Now the other alert. On Friday this rocket body was stale: the tracking was a week old, so the agent asked for fresh tracking instead of spending fuel. Tuesday it arrives, and the right answer is: do nothing. Same agent, opposite answer. That's judgment.",
        "The cards you just saw are a recording of a real run of the agent, played back so a demo on conference wifi runs the same every time. That's a trick worth stealing for your own Show step."],
},
// ---------------------------------------------------------------------------------------------------------------- 7
{
  id: "close", session: 1, tab: "Console · the CYMBAL-04 card", mins: 0.5,
  title: "Close: rigor and judgment",
  steps: [
    { tag: "DO", text: "CYMBAL-04 agent card ▸ Conjunction Assessment & Maneuver Recommendation", expect: "Risk: worst case and assumed side by side · What we cannot see." },
    { tag: "SAY", text: "Every number says what it rests on. That's what rigor and judgment means when you're scored." },
  ],
  why: "Their judging rubric rewards rigor and judgment; the write-up shows what that looks like on paper.",
  say: ["Look at how it writes it up: the worst case, which needs no assumptions, next to the number under an assumed uncertainty, and a section on what we can't see. And the Tuesday update is labelled SIMULATED wherever it appears.",
        "That's the bar: every number from a tool or a query, every assumption stated. Now go build yours."],
},
];

const GUIDE = {
  lede: "A live demo, under ten minutes, no deck. It walks the five steps of the room's build path on a finished sixth challenge, "
    + "Cymbal Orbital's conjunction screening, and ends on the finished product. Everything in this folder is public: the students may keep it.",
  howItWorks: [
    "Steps 3 and 4 are live: the real agent, real Gemini, in the ADK web UI. Talk over the waits (about 15 s and 30 s on a good day).",
    "Step 6, the console, runs in REPLAY: the agent cards are a recording of a real run (console/recordings/rehearsal.json), "
      + "played back at the same sim moments with the same steps, so it behaves the same every time. The header says REPLAY; say so in the talk track.",
    "Everything else is pre-built and only looked at: the notebook was run in the morning, the agent was deployed to Cloud Run once.",
    "One start block (bash scripts/start_demo.sh) gets every tab ready. No resets between steps: it's one finished thing, looked at five ways.",
    "Pacing is yours: each step is a brief look, and any step can be shortened to its one SAY line.",
  ],
  story: [
    "Cymbal Orbital (fictional) flies twelve small Earth-observation satellites at 880 km. The sky they share is real: 32,578 tracked objects "
      + "from U.S. Space Command, pinned to one snapshot so every city sees the same numbers.",
    { table: { headers: ["Build-path step", "Demo step", "What the room sees"], rows: [
      ["Load & Explore", "2", "The notebook: the wrong answer first, the two events, 850 → 1 that matters"],
      ["Build", "3", "ADK + Gemini + BigQuery through the managed MCP server"],
      ["Differentiate", "4", "Our own tool, and the Agent Runtime code sandbox running the physics"],
      ["Deploy", "5", "The same agent on Cloud Run"],
      ["Show", "6–7", "The console: watcher, agent, human approval; the write-up"],
    ] } },
    "Two alerts carry the story. Moment A (CYMBAL-04, fresh tracking, worst case on the escalation line): burn, while it's cheap. "
      + "Moment B (CYMBAL-11, tracking a week old): don't spend fuel yet, ask for fresh tracking; when it arrives (simulated), stand down.",
  ],
  setup: [
    { h2: "Once per project (a Google Skills project or your own)" },
    { step: { tag: "SHELL", label: "CLOUD SHELL · about 10 minutes: data, environment, sandbox, smoke test, Cloud Run", text: "git clone https://github.com/haggman/A4I2026-demo-orbital-conjunction.git\ncd A4I2026-demo-orbital-conjunction\nbash scripts/build_demo.sh",
      expect: "Ends with Ready. The smoke test's 7 checks PASS; the Cloud Run service cymbal-ops is up." } },
    { step: { tag: "DO", label: "COLAB ENTERPRISE · about 3 minutes", text: "Open notebooks/demo_01_load_explore.ipynb ▸ Runtime ▸ Run all",
      expect: "Section 10 shows 850 approaches; section 11's checks all PASS. Leave the tab open: its outputs are step 2." } },
    { h2: "The rehearsal recording (once; it's committed, so every later run reuses it)" },
    "The console replays a real run of the agent. Make one, check it, keep it:",
    { step: { tag: "SHELL", label: "CLOUD SHELL · the console, live", text: "source scripts/activate.sh\npython console/data.py\nuvicorn console.app:app --port 8080",
      expect: "Web Preview ▸ Change port ▸ 8080. Header says LIVE AGENT." } },
    { numbered: ["Skip to next until the CYMBAL-04 card asks for a decision; wait for YOUR CALL; Approve.",
      "Skip to next until Tuesday's card; wait for YOUR CALL; Approve. Then stop uvicorn (Ctrl+C in that terminal)."] },
    { step: { tag: "SHELL", label: "CLOUD SHELL · keep it", text: "python console/keep_recording.py",
      expect: "Kept run-… → console/recordings/rehearsal.json · moment A: 0.0181 m/s prograde at 04:00 → 3,036 m · replayed the week twice: identical." } },
    "If it says NOT KEPT, it says why (usually: the agent chose 12:00, or a turn timed out). Rehearse again. "
      + "Then get rehearsal.json into the repo: commit and push from Cloud Shell, or ⋯ More ▸ Download and commit it from your Mac.",
    { h2: "Morning of" },
    { step: { tag: "SHELL", label: "CLOUD SHELL · the start block", text: "bash scripts/start_demo.sh",
      expect: "Sandbox ✓ · the model check says the default is quick · port 8000 ✓ · port 8080 ✓ · console: replay rehearsal." } },
    { bullets: ["Open the five tabs in the order on the BEFORE KICKOFF page.", "Notebook outputs still there (re-run if the runtime was recycled).",
      "If the model check says Gemini is slow, the console still runs on time (replay); steps 3–4 have their fallback lines."] },
  ],
  factSheet: [
    { h2: "The snapshot" },
    { bullets: ["Snapshot 20260925T0137Z; the demo's frozen \"now\" is Fri 25 Sep 2026 01:00 UTC.",
      "32,578 tracked objects on orbit (Space-Track, elements newer than 30 days).",
      "850 approaches under 10 km in the week across 12 satellites: 1 ESCALATE, 7 WATCH, 842 noise.",
      "ESCALATE = worst-case probability at or above 1 in 10,000. WATCH = closer than 1 km. Stale = tracking more than 5 days old at closest approach.",
      "Clear = worst-case probability below 1 in a million: a miss of about 3,033 m at a 5 m hard-body radius."] },
    { h2: "Moment A — burn" },
    { bullets: ["CYMBAL-04 vs FENGYUN 1C DEB (31178), a fragment of the 2007 anti-satellite test.",
      "Fri 25 Sep 20:16:10 UTC · 301.1 m · worst case 1.01e-04 · closing at 7.5 km/s · tracking 2.55 days old (fresh).",
      "Burn at 04:00: 0.0181 m/s prograde → 3,036 m, 1.54 days of mission life. At 12:00: 0.0343 m/s, 2.92 days.",
      "Mission-life figures rest on a stated budget: 30 m/s over a 7-year design life (about 85 days per m/s). Fictional."] },
    { h2: "Moment B — wait" },
    { bullets: ["CYMBAL-11 vs SL-3 R/B (8520), a Soviet upper stage.",
      "Thu 1 Oct 17:45 UTC · 420.7 m · tracking 7.72 days old at closest approach (stale) → fresh tracking requested, no burn.",
      "Tue 29 Sep 06:00: fresh tracking arrives (SIMULATED: made by console/make_scenario.py from the snapshot's own elements, moved 7 km along track). Recomputed: 3,700 m, worst case 6.7e-07. Stand down."] },
    { h2: "Also on screen" },
    { bullets: ["CYMBAL-01 vs SL-3 R/B (11289) at 01:02 UTC, 382 m: two minutes from \"now\", too late to act.",
      "Five other WATCH approaches on stale tracking: one watcher card lists them."] },
  ],
  confirm: [
    "Colab Enterprise: the Table of contents entry names for sections 3, 7 and 10, and the count of objects crossing 855–905 km printed in section 3 (put the number on the teleprompter).",
    "Section 7's hook numbers (the share of objects and of debris from the 2007 and 2009 events) as printed in this project.",
    "ADK web UI 2.7.0: the name of the events / trace panel and that clicking a tool call shows its arguments.",
    "Two Web Preview tabs from one Cloud Shell (ports 8000 and 8080) at the same time.",
    "The Cloud Run page shows cymbal-ops with \"Require authentication\" and one instance.",
  ],
  files: [
    ["scripts/start_demo.sh", "Start", "The start block: sandbox, model check, ADK web UI on 8000, console on 8080 in replay"],
    ["scripts/build_demo.sh", "Setup", "Builds the whole demo in a project, once"],
    ["notebooks/demo_01_load_explore.ipynb", "Step 2", "Load & Explore"],
    ["agent/cymbal_ops/", "Steps 3–5", "The agent: tools.py, prompt.py, the sandbox physics"],
    ["console/", "Steps 6–7", "The console; console/recordings/rehearsal.json is the replay"],
    ["console/keep_recording.py", "Setup", "Checks a live rehearsal and keeps it as the replay"],
  ],
};

module.exports = { PACK, blocks, GUIDE };
