# Leadership Gap Diagnostic

A lead magnet for acquiring startups, and the agentic funnel behind it.

Built for Connectd, September 2026, by Hannah Tomi Ajiboye.

---

## The idea in one paragraph

Connectd's offer to a startup is **up to three senior experts, pro bono, for three
to six months**. So the lead magnet's output is deliberately **three named senior
advisory gaps**, in a fixed vocabulary, each carrying the evidence it rests on.

That means the magnet does not generate a lead and then hand it to someone to
qualify. **It generates the placement brief.** The artefact the founder wants and
the artefact the business needs are the same object, which is why this is worth
building properly rather than as a quiz.

A founder enters their website. About ninety seconds later they have a read on
their own leadership that is specific enough to argue with.

---

## Try it

| What | Where |
|---|---|
| The write up, the funnel, the loop | [`docs/index.html`](docs/) |
| Four real runs, rendered | [`samples/`](samples/) |
| **The app, live** | **https://connectd-leadership-gap-diagnostic-s96wwu6voq2rzlm5yqqc94.streamlit.app/** |

The hosted app runs live on a capped key, so it needs nothing from you. The spend
is bounded by a separate OpenRouter credit limit, a pre-flight balance check so a
run cannot die half way, and a per visitor cap. When the budget is gone it falls
back to the four completed runs rather than erroring.

```bash
pip install -r requirements.txt
python diagnose.py https://example.com --no-confirm   # one run
python render.py runs/*.json --out samples            # render to HTML
python loop.py --dry-run                              # the optimisation loop
streamlit run app.py                                  # the front door
```

---

## The four runs, and why they are the interesting part

These are real UK companies, read from their own public websites on 24 September
2026. Nothing is invented. **Two of the four produced no report at all, and those
two are the exhibits I would look at first.**

| Company | Outcome | What it demonstrates |
|---|---|---|
| **Anemo Labs** | Report | London deep tech, 700k pre-seed, three named staff. A third gap was named, published, found wrong by a human, and is now structurally impossible to produce. See below. |
| **Ridelogix** | Report | Claims citing a named enterprise customer as proof the company could not sell to enterprises were discarded by the adversarial pass. |
| **Chatterbox** | **Out of profile** | 29 staff, blue chip client, past the stage this is built for. Screened before any gap judgement was made. |
| **Rule** | **Refused** | A 615 character site. Too little to work from, so it declined to diagnose rather than infer a gap from an empty page. |

A diagnostic that only knows how to produce a diagnosis will produce one whether
or not it should. Two of these four are the system deciding not to.

The delivery leg is live. A report copy and an onward share to a second recipient
both send through a transactional endpoint, consent is logged per capture with a
timestamp, and a malformed address is rejected before anything goes out. Sends are
transactional rather than campaign, because a campaign attaches a List-Unsubscribe
header that routes a one to one message somebody asked for into the promotions tab.

---

## How it works

Six steps. A human touches one of them.

```
URL
 │
 ├─ 1  fetch          known paths only: /, /about, /team, /careers, /pricing
 │
 ├─ 2  confirm        "we found X, is this you?"      ← the only per-run human gate
 │                     cheap, deterministic, and it gates spend: nothing
 │                     expensive runs until the subject is confirmed
 │
 ├─ 3  extract        cheap model → evidence record, every field with a source URL
 │                     and a date. Unknowns recorded as unknown, never guessed.
 │
 ├─ 3b qualify        ICP screen: stage, size, disqualifiers → may exit as out_of_icp
 │
 ├─ 3c refusal gate   enough evidence? leadership visible? → may exit as refused
 │
 ├─ 4  classify       stronger model → up to 3 archetypes from a CLOSED list,
 │                     each with quoted evidence, a source, and a confidence tier
 │
 ├─ 5  adversarial    a different model tries to FALSIFY each claim. Four checks.
 │     pass            Then two deterministic checks in code.
 │
 └─ 6  render         report on screen at a unique URL, then the capture actions
```

### Why a closed taxonomy

`taxonomy.yml` holds 21 advisory archetypes. The classifier picks from that list
and may not invent one. That single constraint does two jobs:

- **It collapses the hallucination surface.** "What does this company need" invites
  invention. "Which of these 21 applies, and cite your evidence" is classification,
  and a human can check it in seconds.
- **It makes the output routable.** Gap names have to sit in the same vocabulary
  the exec bench is indexed by, or a named gap cannot be matched to a person. Free
  text gap descriptions are unroutable.

It is the difference between a doctor writing a free form note and picking a
diagnostic code.

---

## A note on the diagram

`docs/diagram.png` is drawn in code rather than generated. The argument it
carries is that the gates cluster at one seam and are deliberately absent
elsewhere, which is a claim about structure, and a generated image cannot be held
to a structure. Every box in it is a function that runs. Rebuild it with
`python make_diagram.py`.

---

## The seams, which is where the real work is

The interesting part of a system like this is never the individual agent. It is the
seams, where one agent's output becomes another's input, because that is where a
plausible but wrong answer does the most damage. So the gates belong there, not
sprinkled everywhere by default.

### The expensive seam: evidence to named gap

Every other failure in this funnel costs a lead. **This one costs credibility, in
writing, in a document a founder may forward to their board, with Connectd's name
on it.** It costs it with exactly the population Connectd needs to be trusted by.

So all the gates sit here:

| Gate | What it stops | Where it lives |
|---|---|---|
| Closed taxonomy | Invented gaps | `taxonomy.yml` |
| Mandatory citation | Unfalsifiable claims | classifier prompt |
| Permission to name fewer than three | Reaching a target for its own sake | prompt plus `max_gaps` |
| Adversarial pass, 4 checks | Contradicted and inverted claims | `adversarial_pass()` |
| Leadership visibility gate | Diagnosing from a missing page | `has_leadership_visibility()` |
| Confidence cap | Model over rating its own certainty | `cap_confidence()` |
| Shared evidence check | Two gaps, one piece of evidence | `flag_shared_evidence()` |
| Unknowns section | Filling silence with inference | the report template |

The last three are in **code, not in the prompt**, and that distinction is the
point. Asking a model more firmly to respect its own confidence definitions is not
a control. A rule is.

### Where there is deliberately no gate

Worth stating, because it is what makes the principle real rather than decorative.

- No gate on extraction. Cheap, and its worst failure is caught by step 2.
- No gate on copy variants in the fast loop. Nothing a copy test gets wrong is expensive.
- **No human review of an individual report** when every gap rule passed. A human
  in that seat at volume rubber stamps, and a rubber stamp is worse than a rule
  because it looks like oversight.
- The human gate sits instead at the point a brief would reach a senior exec,
  because that is the first moment a wrong answer consumes a scarce person rather
  than a cheap API call.

---

## How it fails, and what catches it

The question worth asking about a system like this is not whether it is clever.
It is whether you would put your name on what it tells a founder.

An early version told a startup its Scientific Advisory Board section was empty.
The board has three members. They load into the page by JavaScript and appear
nowhere in the HTML a scraper receives.

**Every automated gate passed it.** The claim carried a real citation, named a
real page, and survived the adversarial pass because nothing in the evidence
contradicted it. The evidence was incomplete in a way the system could not
detect. It failed *plausibly*, which is the failure mode that matters: an error
announces itself, a confident wrong answer does not.

A person read it and knew it was wrong. That is the argument for keeping a human
gate rather than a decoration on one, and it is why the accept or reject step
before a brief reaches an exec is built rather than described.

The fix was a reasoning one, not a scraping one. **A heading is evidence the
thing exists.** A company does not put "Scientific Advisory Board" on its team
page unless it has one. The system had been reading that heading as evidence of
absence, which is close to exactly backwards.

| Fix | Where |
|---|---|
| Detect pages that did not render, by text to markup ratio | `crawl()` |
| A heading for an unrendered section suppresses the matching archetype | `suppress_by_unrendered_sections()` |
| Absence can never be a citation | `guard_absence()` |
| Citing a person whose role IS the missing expertise is an inversion | `flag_person_inversion()` |

All in code, because this was never a matter of asking the model more firmly.

---

## The optimisation loop

`loop.py`. Run `python loop.py --dry-run`.

**An honest description first.** At thirty runs a week this is not an optimiser. It
is a disciplined experiment log with an automated analyst attached, and its real
value is that it makes it impossible to change three things at once and then argue
about what worked. It becomes a genuine optimiser somewhere in the low hundreds of
runs a month. Claiming self improvement before that is a claim about statistics the
sample size does not support.

**North star: accepted placement briefs per 100 diagnostic starts.** Downstream
enough to be real, and it is the only metric that cannot be gamed by generating
engagement that never becomes a placement. A thousand completions producing no
accepted briefs is a failed system that looks like a successful one.

**Three label sources, in rank order**, because an optimiser is only as good as its
ground truth:

1. **Strongest:** the human accept, edit or reject per gap, written to `reviews.csv`. Skin in the game, low volume, and the slow loop reads it directly when looking for archetypes that are named often and rejected often.
2. **Medium:** behaviour. Completed, shared, returned, booked.
3. **Weakest:** the founder's own yes, partly or no. Cheap, high volume, biased
   towards politeness. Sets direction, never decides alone.

**What it reads:** `runs.csv`, one row per run, 26 columns. Every variable the loop
can change and every outcome it can read has a column. **Deciding the log schema is
deciding what the loop is capable of learning**, which is why the schema was
designed before the loop was written.

**What it writes:** `config.yml`, and only `config.yml`. Copy and CTA variants.
Never the code. Never the taxonomy.

**Two clocks:**

- **Fast**, weekly or every 30 runs. Copy only. One variable per surface per cycle,
  because at low n concurrent changes are unattributable and the honest answer is
  that you would not know which one did it. **Nothing promoted below n=30.**
- **Slow**, monthly. Looks for one thing: archetypes named often and rejected
  often, which are the taxonomy's bad entries. Opens a proposal. **Never merges**,
  because the taxonomy decides what a founder gets told about their own company.

**Guardrails, any breach reverts to the last good config and halts:** brief reject
rate, gap accuracy, cost ceilings, and a **minimum refusal rate**. That last one
exists because the loop could otherwise learn to lift bookings by naming more
dramatic gaps. A system that stops refusing has learned to guess.

---

## Distribution, which is where a lead magnet usually dies

An artefact with no route to founders is not a funnel. Ranked, with a
recommendation.

**1. Recommended first: distribute through the exec side of the marketplace.**

Give every senior exec on Connectd's books a personalised diagnostic link to send
into their own network. Three things make this the right first route, and no other
route has all three:

- The distributor is motivated by something better than goodwill. A placement is
  the outcome they are already chasing.
- The relationships are warm, so it needs no verified email and no cold sender.
- **No competitor can copy it.** Nobody else has a motivated senior exec network
  pointed at early stage startups.

It is also the route that treats Connectd as a two sided marketplace rather than a
generic B2B business.

**2. The funding signal agent.** A startup that just closed a round is the best
qualified lead this funnel will ever see, because "get senior leadership in place
fast" becomes urgent exactly when the cash lands and the board starts asking about
the plan. The agent watches funding signals against the ICP and **runs the
diagnostic automatically on a match**, so the outreach opens with a real read of
their leadership rather than a template. The lead magnet becomes the outbound
personalisation layer.

The verification gate is what makes this safe, and it is not theoretical. Accept
only `valid` and `deliverable`. Reject `catch_all`, `accept_all`, `risky`,
`unknown`, blank, and anything unrecognised, failing safe by default. A catch all
domain accepts any address whether the mailbox exists or not, which is the exact
condition that produces a mass hard bounce and gets a campaign pulled.

**3.** Accelerator and syndicate platform teams, whose job is handing portfolio
companies useful free things. One partnership reaches a whole cohort.

**4.** Connectd's own surfaces, and previously unconverted startups. Zero marginal
cost, and it is where the first thirty runs come from, which is what unblocks the
loop.

**5.** Founder communities. Posting, not scraping.

**6.** Paid, deliberately after the free conversion rate is known, because paid
multiplies whatever rate you already have.

**7.** Manual human outreach on LinkedIn. Effective, available today, and **not
agentic**, which is worth saying rather than dressing up.

---

## What a run costs

Measured, not projected. OpenRouter reports real cost per call and every run logs
what it spent.

| Outcome | Calls | Cost |
|---|---|---|
| Full report | 3 to 4 | $0.075 to $0.151 |
| Screened out of profile | 1 | $0.016 |
| Refused | 1 | $0.003 |

**The quality gates are also cost gates.** A refusal costs about fifty times less
than a full report, because it exits before the expensive model runs. The ICP
screen and the refusal gate were built to stop the system saying something it
could not support. At volume they also stop it spending money on companies it was
never going to help.

---

## How it expands

**Week 1.** Diagnostic live on real URLs. Taxonomy v0. Run log populated. Own
surfaces only. Human reviews everything. Target thirty runs, not for conversion but
for a config baseline and to find out how the classifier fails on real inputs.

**Month 1.** Per exec links with attribution. Fast loop on. Booking webhook exits
the nurture sequence. First slow loop pass on the taxonomy using real reject
reasons. Two accelerator conversations open.

**Quarter.** Cohort distribution through partnerships. **Archetype level demand
reporting feeding exec side recruitment**, which is the point where the startup
funnel starts paying for itself twice. Tiered review replaces full review. Six
month re runs producing before and after case studies without anyone remembering
to write them.

**What breaks first, in order:**

1. **The human accept gate.** The only per lead human step. Comfortable at ten a
   week, a full time job at a hundred, and it breaks quietly by degrading into
   rubber stamping. Fix: auto pass where all gaps are high confidence and the
   adversary found nothing, human review the mixed cases, random sample audit to
   keep the auto pass rule honest.
2. **The exec bench.** Diagnostic demand outruns matchable supply. No amount of
   funnel engineering fixes a supply problem. Naming it is what separates a
   marketplace plan from a lead generation plan. Mitigation: the archetype demand
   data tells exec recruitment which profiles to go and find.
3. **Scrape reliability.** Bot blocking, client side rendering, thin footprints.
   Refusal rate is monitored so this degrades visibly rather than silently.
4. **Unit cost**, then **attribution** once several routes are live.

---

## What this does not claim

| Not claimed | The honest version |
|---|---|
| The funnel runs end to end | The diagnostic does, on real companies. The routing and nurture layer is designed, and has a working precedent in another stack. It is not connected here. |
| It knows Connectd's business | It was built from Connectd's public offer. No access to the CRM, the bench, the real ICP or the real qualification thresholds. Both config files exist so that is an hour of work to fix, not a rebuild. |
| The taxonomy is validated | It is a v0 drafted from the public offer. Its errors are the slow loop's first job. |
| The loop is self optimising | It is specified, the schema and config exist, and it has four rows of data. It needs about thirty runs per variant before its output means anything. |
| The report is accurate | It is accurate about what is publicly visible, and it says so in the body rather than a footnote. Where it cannot see, it says so and asks. |
| Emails are sent at volume | The delivery leg is live and tested end to end: a report copy and an onward share both sent through a transactional endpoint, and a malformed address was rejected without sending. Three sends is a working mechanism, not a campaign, and no list has been mailed. |
| Fully autonomous | Two human gates are designed, at named seams, with a stated reason for each. |
| Fully autonomous | Two human gates, both built. Identity confirmation at step 2, and accept, edit or reject per gap before a brief reaches an exec. Everything between them runs unattended. |

### Known limitations

- **Static fetch only.** No JavaScript execution. This produced the false claim
  described above. The system now detects unrendered pages and refuses to build
  claims on absence from them, which contains the failure but does not remove the
  underlying limit: there is content on some sites it simply cannot read. The
  mitigations are the rendering notice on the report, the suppression rules, and the
  founder confirming or correcting at step 2.
- **Run to run variance.** Temperature is zero and runs still differ. On one run the
  adversarial pass demoted Anemo Labs' domain advisory gap, and on the next it did
  not. A safety gate that fires probabilistically is a weaker gate than one that
  fires deterministically, which is why three of the checks were moved into code.
- **Small sample.** Four runs. Everything about the loop is specification, not result.

---

## Files

```
taxonomy.yml     21 advisory archetypes, confidence tiers, refusal rules
icp.yml          who this is for, disqualifiers, lawful basis
config.yml       the surface the loop may change, versioned
diagnose.py      fetch, extract, qualify, classify, adversarial pass
render.py        four outcomes, four renderings
deliver.py       the capture leg and transactional send
loop.py          the optimisation loop, dry run by default
app.py           the front door, demo and live modes
runs.csv         the log, 26 columns
runs/            machine readable run records
samples/         the four rendered reports
```

Built with Claude Code. `CLAUDE.md` and `.claude/` carry the project's own
instructions and the agent definition used to build it, because a harness you
actually work in leaves artefacts, and those are more informative than a claim.

n8n would be the natural production home for the routing and scheduling layer
described above. Two walkthroughs on the tooling, including why I moved off n8n
Cloud and how to wire Google Cloud into it, are on the AI with Hannah channel:
[why I cancelled n8n Cloud](https://youtube.com/watch?v=tZNzfJvQ0EE) and
[connecting Google Cloud to n8n](https://youtube.com/watch?v=lucBq6iw37g).

---

## A note on the order of work

The taxonomy and the ICP were written before the engine, and that was not
sequencing for its own sake.

At a previous company I was the sole marketing hire across five product divisions,
each selling a different technical product to a different industrial buyer. Five
ideal customer profiles, five narratives, one person. I defined the positioning
separately for each before building the engine that executed against it: five
interconnected workflows handling research, drafting, image generation and
publishing across five divisional sites. It cut a two day cycle to under two hours
and still runs.

The part that mattered was the order. Without the ICP work first, I would have
built a faster way to publish the wrong thing five times over.

Same here. The taxonomy and the evidence rules are the prior work that gives the
loop something worth optimising. A loop pointed at the wrong definition of a good
lead just finds the wrong leads faster.
