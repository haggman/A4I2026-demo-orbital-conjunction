# The kickoff demo—Which of These Warnings Is Real? Orbital Conjunction Screening

**Agents for Impact 2026**

> ### This one has been solved for you
>
> **This is not your challenge.** Your table has one of five. This is a sixth, written to the same shape
> as yours, and then built all the way through, so you can see what the end of the path looks like before
> you start down your own. It is the demo from the kickoff.
>
> **How to use it, in about twenty minutes:**
>
> 1. **Read the challenge below** as if it were yours. Notice the shape: why it matters, the tracks, what
>    you're building, one required differentiator, the data, how you'll be judged. Yours has the same shape.
> 2. **Then look at how we solved it**, one build-path step at a time:
>
> | Build-path step | Our solution | Start with |
> |---|---|---|
> | **Load & Explore** | A notebook that loads the public orbital catalogue into BigQuery, gets the obvious answer wrong first, and screens our fleet against the sky | [`notebooks/demo_01_load_explore.ipynb`](notebooks/demo_01_load_explore.ipynb) |
> | **Build** | One ADK agent on Gemini, reading BigQuery through Google's managed MCP server, plus three tools we wrote | [`agent/README.md`](agent/README.md) |
> | **Differentiate** | Orbital what-ifs run in the Agent Runtime code sandbox, not in the agent's process | [`agent/cymbal_ops/tools.py`](agent/cymbal_ops/tools.py) · [`orbit_whatif.py`](agent/cymbal_ops/sandbox_files/orbit_whatif.py) |
> | **Deploy** | The same agent on Cloud Run, authentication required, one command | [`agent/deploy.sh`](agent/deploy.sh) |
> | **Show** | A flight dynamics console: plain code watches, the agent decides, a human approves | [`console/README.md`](console/README.md) |
>
> 3. **See it working, without running anything:** [`run-of-show/docs/INSTRUCTOR-GUIDE.md`](run-of-show/docs/INSTRUCTOR-GUIDE.md)
>    walks the finished console beat by beat, with screenshots, and explains what the agent did and why.
>    [`run-of-show/`](run-of-show/) is the whole ten-minute kickoff script. A good Show step is part of a
>    finished project; borrow anything.
> 4. **Or run it yourself**, in a Google Cloud project where you are Owner, from Cloud Shell:
>
>    ```bash
>    git clone https://github.com/haggman/A4I2026-demo-orbital-conjunction.git
>    cd A4I2026-demo-orbital-conjunction
>    bash scripts/build_demo.sh      # about 10 minutes: data, agent, sandbox, smoke test, Cloud Run
>    bash scripts/start_demo.sh      # the ADK web UI on port 8000 and the console on port 8080
>    ```
>
> **This is the far end of the path, not the bar.** A working agent in the ADK web UI, on your challenge's
> data, is a good finish. A team with a web developer, someone who knows the problem's world, and time to
> spare can get as far as this. The four lanes in Getting started say who does what.
>
> **Two differences from your repo.** Your `agent/` folder is empty on purpose; here it is full, because
> showing a finished one is the point. And this repo is not a template: clone it, don't build your team's
> project in it.
>
> Throughout the challenge below, boxes like this one marked **How we did it** point at the part of our
> solution that answers that section. Everything else reads exactly as your challenge does.

---

## Why this one matters

There are about 32,000 objects in orbit with published positions. A few thousand are working satellites.
The rest are dead satellites, spent rocket stages, and fragments: pieces of things that broke apart, some
of them on purpose.

If you fly satellites, every one of those objects is a warning waiting to happen. Your operations team gets
a steady stream of close-approach alerts, around the clock, and **nearly all of them are noise.** The
object will pass kilometres away, or the tracking is too old to mean anything, or it will be over before
anyone could act.

A few are not. And here is the trade that makes this hard rather than a matter of caution: **moving a
satellite costs propellant, and propellant is the satellite's remaining life.** Dodge everything and you end
the mission early to avoid collisions that were never going to happen. Dodge nothing and one day you become
debris yourself, and the next operator's warning.

That last part is not hypothetical. In 2009 a working Iridium satellite and a dead Russian one collided at
about 11.7 km/s. Seventeen years later, hundreds of their pieces are still up there, still generating
warnings for everybody else. One bad call makes the problem worse for every operator who comes after.

**An operator has a fleet, a week of warnings, and a few hours to decide which ones are real.** Your job is
to build the thing that helps them decide well, and says plainly when it can't.

> **Our satellites are made up. Everything they could hit is real.**

---

## How to read this

**This is a reference for your whole afternoon, not something to read end to end now.**

| If you are… | Read now | Come back for |
|---|---|---|
| **Everyone, together** | [The four things](#the-four-things-youre-working-with) · [Three tracks](#three-tracks-one-architecture) · [What you're building](#what-youre-building) | — |
| **Team lead** | [Step 0](#step-0organize-your-team) · [How you'll be judged](#how-youll-be-judged) | [What will set yours apart](#what-will-set-yours-apart) |
| **Data lane** | [Step 4, load the data](#step-4load-the-data) · [What you'll have](#what-youll-have) | [The data, and why we chose it](#the-data-and-why-we-chose-it) |
| **Agent lane** | [The technology](#the-technology-youll-use), especially the differentiator | [`agent/README.md`](agent/README.md) |
| **Front end lane** | [Front end lane](#front-end-lane2-people) | [Your output artifact](#your-output-artifact-the-conjunction-assessment) |
| **Story lane** | [Why this one matters](#why-this-one-matters) · [The honest numbers](#the-honest-numbers) | [What we cannot see](#what-the-data-cannot-do) |

**Three things everybody should know by the end of hour one:**

1. **Miss distance is measured; collision probability is not.** Public orbital data carries no statement of
   how uncertain each position is. You can compute how close two objects come rigorously. Probability needs
   an assumption, and an honest system says which one, next to the number.
2. **Most of the work is deciding what *not* to escalate.** Hundreds of approaches under 10 km in a week; a
   handful worth a human. An agent that sends everything to a person, or to a model, has missed the point.
3. **"Don't burn" is often the right answer.** Old tracking, a pass too soon to act on, an approach that
   clears itself on fresh data. The best solution will say so, and say why.

---

## The four things you're working with

| Term | What it means here |
|---|---|
| **Conjunction** | A close approach between one of our satellites and another object. Every row in your `conjunctions` table is one. |
| **TCA** | Time of closest approach: the moment the two are nearest. Everything counts down to it. |
| **Miss distance** | How close they come at TCA. Split into radial (up/down), in-track (ahead/behind) and cross-track (sideways), because a burn moves you mostly in-track. |
| **Elements** | The six numbers and a timestamp, published for every tracked object, that tell a propagator where it will be. They age: the further from their timestamp, the worse the prediction. |

---

## Three tracks, one architecture

The data and the physics are the same for all three. What changes is who is asking and on what clock.
**Pick the one your team wants to solve.** Combine two, or invent your own, if you can say why.

| Track | The decision | Who's asking |
|---|---|---|
| ⚡ **This week** | Of this week's warnings, which need a human, and which can be logged and left? | The operations desk |
| 🛰️ **This burn** | This one is real. Burn or not? When, how big, and what does it cost? | The flight dynamics engineer, then the flight director |
| 📋 **This mission** | How much propellant should we expect to spend dodging this year, and where is our risk coming from? | Mission management |

**⚡ This week** is triage. A strong version is mostly *not* an AI: deterministic rules that throw out
the noise, and a model only where judgment is needed. It explains each "ignore" as carefully as each
"escalate".

**🛰️ This burn** is the decision itself. A strong version sizes the smallest burn that clears the
approach at each command window, prices each one in days of mission life, recommends one, and waits for a
person to say go.

**📋 This mission** is the planning view: which debris clouds and which orbits drive your warnings, and what
dodging them costs over time. The honest limit: one week of screening is a sample, not a forecast. Say so.

> **How we did it.** We built **This week** and **This burn** together, as one console: a watcher (plain
> code) does the triage, and wakes the agent only for a decision. See [`console/README.md`](console/README.md),
> and the walkthrough in [`run-of-show/docs/INSTRUCTOR-GUIDE.md`](run-of-show/docs/INSTRUCTOR-GUIDE.md).

---

## What you're building

**An operations assistant for a satellite fleet.** Not a dashboard, and not one query with a chat box on
it: an agent an operator can hold a working conversation with, that reaches for real data and real physics
to answer.

**One week, one operator.** Everything below is a question they ask between now and next Thursday:

| The operator asks | What answers it |
|---|---|
| *"What should I worry about this week?"* | `conjunctions`, ranked, with the triage and the reasons |
| *"What exactly is that object?"* | `catalog` and `satcat`: what it is, who owns it, whether it can dodge, which event made it |
| *"How confident are you?"* | The assumptions: object size, the missing uncertainty, how old the tracking is |
| *"What if we burn at 04:00 instead of noon?"* | **Code the agent writes and runs in the sandbox:** propagate with the burn, re-measure the miss |
| *"What does that cost us?"* | Propellant is mission life. The conversion needs a stated budget, which is the operator's to set |
| *"Why not just dodge everything?"* | The week's numbers: hundreds of approaches, a handful worth a human |
| *"What can't you see?"* | Lost objects, the missing uncertainty, the error in public elements |

Notice these need **different things**. Some are a query. One is physics. Some need the agent to weigh a
trade and say why. One needs it to say *I don't know*.

### Your output artifact: the Conjunction Assessment

Whatever else your agent does, it should produce a **Conjunction Assessment & Maneuver Recommendation**:
which object, when, how close; what the risk is, under assumptions it states; what a maneuver would cost;
the recommendation; and what it cannot see. Something a flight director would actually receive.

> **How we did it.** `build_assessment` in [`agent/cymbal_ops/tools.py`](agent/cymbal_ops/tools.py) writes
> it, and re-reads every fact from BigQuery itself, so the numbers in the report come from the data, not
> from the model's memory. The instructor guide shows [a real one, section by section](run-of-show/docs/INSTRUCTOR-GUIDE.md#inside-the-agent-card).

---

## The technology you'll use

Every team, every challenge, uses the same core stack:

| | |
|---|---|
| **ADK** (Agent Development Kit) | You build your agent in Python with ADK. |
| **Gemini** | The reasoning model behind the agent. |
| **BigQuery** | All the data this challenge needs lives here, and your agent queries it. |
| **A managed MCP server** | Consume at least one—don't author your own. |
| **At least one custom Python tool** | Yours, not configuration. |
| **Deployed to Google Cloud** | Agent Runtime or Cloud Run, your choice. |

> **How we did it.** Gemini 3.8 Flash; BigQuery's Google-managed MCP server, filtered to read-only tools;
> three tools of our own (`assess_conjunction`, `maneuver_cost`, `build_assessment`) plus `run_in_sandbox`;
> deployed to Cloud Run. The table in [`agent/README.md`](agent/README.md) says what each piece is for.

### Why we also require a custom Python tool

The MCP server can answer *"which approaches are under 1 km?"* without a line of your code. It cannot
decide whether tracking that will be 7.7 days old at closest approach is good enough to spend propellant
on, or whether the other object is a working satellite that might dodge too. **That's judgment, and
judgment goes in a tool you wrote,** where you can test it and defend it.

### And one required differentiator: the **Agent Runtime code sandbox**

Each challenge has one required technology that makes it distinct. This one's is a **code sandbox**: the
agent writes Python, and it runs somewhere isolated, with no network, not in the agent's own process.

It belongs in this problem rather than being bolted on. *"What's the smallest burn that gets us clear, and
is 04:00 cheaper than noon?"* is not a query and not something to ask a language model to estimate. It's a
calculation: propagate both orbits with the burn applied, and re-measure the miss. The model's job is to
decide which calculation to run and to read the answer. The sandbox runs it.

> **How we did it.** `assess_conjunction` stages a case file and our small physics module,
> [`orbit_whatif.py`](agent/cymbal_ops/sandbox_files/orbit_whatif.py), into the sandbox; the agent writes a
> few lines against it and passes them to `run_in_sandbox`. [`agent/README.md`](agent/README.md) has five
> things we learned about the sandbox the hard way, including why the agent passes code to a tool rather
> than using ADK's code executor directly.

---

## Getting started

You have **4.5 hours** and there are **8–10 of you**. Spend twenty minutes on Step 0.

### Step 0—Organize your team

**Pick a team lead** to make the call when you're behind, and **a repo owner**. Everyone else creates a free
GitHub account if they don't have one and sends the repo owner their username. Agree your track and your
scenario, then **split into four lanes**, all starting at once.

#### Data lane—2 to 3 people

Running the notebook takes a few minutes; that is not the job. The job is understanding what the tables can
and cannot say, and handing the agent lane the exact queries its tools will wrap. Own the validation section,
and own the list of things the agent must admit it cannot see.

#### Agent lane—2 to 3 people

The system instruction, the custom tools, and the differentiator. **Decide what is a rule and what is
judgment** before you write a prompt: rules go in code, judgment goes to the model. Deploy early: the front
end is blocked on you.

#### Front end lane—2 people

Start on `adk web`. Then decide on purpose whether to finish there. An operations desk is a screen people
watch for a shift, not a chat window; if you build your own, show the decision, not the data.

> **How we did it.** A console: time runs over the week, a watcher posts cards, the agent's card waits for
> Approve or Hold. And because conference wifi is the most likely thing to fail all day, it can replay a
> recorded run of the real agent, labelled REPLAY. See [`console/README.md`](console/README.md).

#### Story lane—1 to 2 people, starting at minute zero

A short pitch and a quick demo. **Pick the one moment that lands and rehearse it.** Ours is two alerts, two
opposite answers: burn now while it's cheap, and don't burn on old tracking.

> **How we did it.** [`run-of-show/`](run-of-show/) is our whole script: the plan, a teleprompter, a planning
> guide and the instructor guide.

### Step 1—Get the code into Cloud Shell

In the Google Cloud console, open Cloud Shell with the **terminal icon (`>_`)** in the top right, then:

```bash
git clone https://github.com/haggman/A4I2026-demo-orbital-conjunction.git
cd A4I2026-demo-orbital-conjunction
```

*(For your own challenge you'll use **Use this template** instead. This repo isn't one.)*

### Step 2—Load the data

1. In the Google Cloud console, search for **Colab Enterprise** and open it. Enable the APIs it asks for
   (twice is normal).
2. **My Notebooks** → **Import** → source **URL**, and paste:

   ```
   https://raw.githubusercontent.com/haggman/A4I2026-demo-orbital-conjunction/main/notebooks/demo_01_load_explore.ipynb
   ```

3. Open it and **Runtime ▸ Run all**. About four minutes, most of it the seven-day screen. **Read the text
   between the cells**: it is written so someone who runs nothing can follow every decision.

**If the notebook won't run**, the headless fallback rebuilds the same tables in about a minute:

```bash
bash scripts/load.sh              # the pinned snapshot
bash scripts/load.sh --list       # snapshots with published tables
```

**Or build everything at once:** `bash scripts/build_demo.sh` loads the data, builds the agent and its
sandbox, tests it, and deploys it. Safe to run again.

### What you'll have

Five tables in your project, in a dataset called `a4i_orbit`:

| Table | What it is |
|---|---|
| `catalog` | Every tracked object with current elements: about 32,500 rows, with perigee, apogee, element age, and what each object is |
| `satcat` | Every object ever catalogued, including the ones that have re-entered |
| `fleet` | Cymbal Orbital's twelve fictional satellites, in the same shape as `catalog` |
| `conjunctions` | The screen's output: every approach under 10 km over seven days, with miss distance, its components, risk and triage |
| `snapshot_info` | Which snapshot, which moment, which assumptions |

---

## The data, and why we chose it

Every tracked object is catalogued by **U.S. Space Command**, which publishes its elements through
[Space-Track.org](https://www.space-track.org) (free, with an account) and, redistributed with no account,
through [CelesTrak](https://celestrak.org). We pulled the full catalogue from Space-Track once, because only it
reaches the dead satellites in bulk, and **dead satellites matter most: they cannot get out of the way.** What
each object *is* comes from CelesTrak's satellite catalogue.

The snapshot is **pinned** (`20260925T0137Z`), so every city sees the same numbers.

**The rights, and the one obligation.** U.S. Space Command gives express blanket approval to redistribute
basic orbital data, conditioned on citation. So, everywhere the data appears:

> *Orbital data: U.S. Space Command, via Space-Track.org; satellite catalogue via CelesTrak (celestrak.org).*

### The hook you will hit in the first ten minutes

The obvious first move is an altitude filter: keep everything whose orbit passes through ours. Every one of
those objects really will be at our height, twice an orbit. **Almost none will ever be near us,** because the
same height is not the same place at the same second. Section 3 of the notebook gets this wrong on purpose;
section 9 gets it right.

And a large share of what crosses our altitude traces back to **two events**: China's 2007 anti-satellite
test on its own weather satellite, Fengyun-1C, and the 2009 Iridium–Cosmos collision. Section 7 has the
query. It's Kessler syndrome in one table.

### What the data cannot do

- **No covariance.** A real operator gets a statement of how uncertain each position is. We get a position.
  Every probability rests on a stated assumption.
- **Mean elements are not measurements.** Their error grows with age and can run to kilometres, far larger
  than a 300 m miss. A public-data screen is **triage**; a real operator asks for higher-accuracy tracking
  before maneuvering.
- **Objects nobody has updated in 30 days are not in the pull at all**, about 2,100 of them. No news from
  them is not good news.

### The honest numbers

From the snapshot: **850** approaches under 10 km in seven days across twelve satellites. **One** worth a
burn decision: CYMBAL-04, 301 m from a Fengyun-1C fragment, 19 hours out, on fresh tracking. One more worth
watching for the opposite reason: CYMBAL-11, 421 m from a 1975 Soviet rocket stage, on tracking that will
be nearly eight days old by then. The honest answer there is *ask for fresh tracking*, not *burn*.

**At a 5 m object size, CYMBAL-04 escalates; at 3 m it does not.** Nothing about the orbits changed, only
a number we chose. That is why an honest system shows its assumptions next to its answer.

> **How we did it.** The console's Tuesday is the one thing we **simulated**: fresh tracking for that rocket
> stage, made from the snapshot's own elements and labelled SIMULATED wherever it appears. It moves the miss
> to 3.7 km, and the agent says don't burn. [`console/README.md`](console/README.md) says exactly how it's made.

---

## Going further

### What will set yours apart

- **Go deep on one decision** rather than shallow on seven questions.
- **Make "don't act" a first-class answer,** with its reason. It is harder than "act", and judges notice.
- **Keep the physics out of the model.** Every number from a tool or a query; the model decides which to ask
  for and what they mean.
- **Show your assumptions next to your answers,** and how far the answer moves when they do.
- **Give it a face an operator would keep open,** and a human who says go.

### Bringing your own data

The obvious additions are higher-accuracy tracking with covariance, a real operator's own maneuver history,
or space-weather data that changes drag. **Check the license before you load it**: the same bar applies as
in every challenge (no NonCommercial, no NoDerivatives, no share-alike, no personal data, no unstated
license).

---

## What's in this repository

```
README.md                         this file
notebooks/
  demo_01_load_explore.ipynb      Load & Explore. Run this first
  demo_90_stage_catalog.ipynb     Maintainers only: refresh the snapshot from Space-Track
scripts/
  load.sh                         Headless fallback for the notebook
  build_demo.sh                   The whole build, one command
  start_demo.sh                   Start the ADK web UI and the console (--stop to stop them)
  activate.sh                     The Python environment and settings, for any new terminal
agent/                            The finished agent. Full, unlike yours (agent/README.md)
console/                          The flight dynamics console: the Show step (console/README.md)
run-of-show/                      How the kickoff demo is presented, and the instructor guide
data/                             No orbital data is committed; see data/README.md
demo.env                          Every setting you might change: model, timeouts, dataset
```

---

## How you'll be judged

The same way your challenge is. **"Finished" is not the goalpost**: a team that gets three quarters of the
way with clear reasoning and honest limits beats a polished demo with nothing behind it.

| Dimension | Weight | The question judges are asking |
|---|---:|---|
| **Impact & insight** | 30 | Would your user actually use this? Is the answer specific enough to act on? |
| **Technical execution** | 30 | Does it work, and is the required stack genuinely used rather than name-checked? |
| **Rigor & judgment** | 25 | Can you defend the decisions you made along the way? |
| **Craft & communication** | 15 | Does the short pitch land, does the quick demo work, and can you justify your interface choice? |
| **Bonus—range** | **+10** | Technology breadth and ambition that *serves* the solution |

In this challenge, **rigor and judgment** looks like: knowing the data's license; validating the tables before
building on them (the notebook's section 11); saying what the probability rests on; listing what you cannot
see; and an agent that recommends *not* acting when the evidence says so.

---

## Getting help

Ask a coach. To report a problem with the data or the notebook, run the **diagnostic cell** at the bottom of
the notebook (Appendix B) and share everything it prints.

*Orbital data: U.S. Space Command, via Space-Track.org; satellite catalogue via CelesTrak (celestrak.org).
See `NOTICE`.*
