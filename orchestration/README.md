# The orchestration layer

`connectd-funnel.n8n.json` imports into n8n as a single workflow with two
triggers. It covers the layer the Python build deliberately does not own.

## Why this is not the diagnostic

The diagnostic itself stays in Python, and that is a decision rather than an
accident.

Every quality gate in this system has to fire on every run. `guard_absence()`,
`cap_confidence()`, `flag_shared_evidence()` and `suppress_by_unrendered_sections()`
are functions with tests, and a rule that must never be skipped belongs in code
where it cannot be dragged out of the path, disabled for one execution, or
quietly reordered.

What n8n is genuinely better at is everything around that: schedules, credential
handling, retries with backoff, fan-out over a list, waiting three days without
holding a process open, and branching on an outcome. So that is what it holds
here.

The split is the point. A visual orchestrator is the right tool for orchestration
and the wrong tool for a guarantee.

## Branch A: what happens after a founder asks for their report

Trigger: `POST /webhook/connectd/capture`, fired by the app once a report has
been delivered and an address captured.

It does not resend the report. `deliver.py` has already done that, on screen,
at the moment of capture. This branch owns what comes after.

1. **Consent to follow up?** Consent is separable in `captures.csv`, so the no
   branch still records the run against the contact and then stops. Nothing
   follows a contact who did not agree to be followed.
2. **Upsert the contact with the run.** Outcome, archetypes named and run id go
   onto the Brevo contact record, so the CRM holds the qualification rather than
   just the address.
3. **Which outcome**, three ways:
   - **Report.** Wait three days, check whether they already booked, and if not
     ask which gap was wrong. That answer is the human label the optimisation
     loop cannot get from behaviour, and it is the only branch that produces one.
   - **Not the ICP.** Route to the exec side and tag as supply. A screened-out
     company is not a dead end, it is a lead for the other half of the
     marketplace.
   - **Refused.** Wait a day, then offer the ten minute call. When the system
     could not say anything honest, the only honest offer left is a person.

## Branch B: the funding signal agent

Trigger: weekdays at 07:00.

The signal is **SH01**, the allotment of shares. That is the filing a company
makes when it issues new equity, so it is the legal record of a round landing
with a date attached, rather than a press mention that may be describing
something six months old.

Getting it takes two calls, because neither can do it alone.

1. **Companies House ICP watchlist.** Advanced search by SIC code, incorporation
   date and active status. This cannot filter on filings, so its job is the
   candidate set and nothing more.
2. **Split Out.** The search replies with one object holding an `items` array,
   so without this the next node runs once against a `company_number` that does
   not exist at the top level. It was missing in the first version and the
   failure was invisible: the call went out malformed, the response had no
   `items`, the SH01 filter read an empty list and emitted nothing, and every
   node went green. A zero there is indistinguishable from a day with no funding
   rounds. It was caught by reading the item counts on the edges, not the ticks.
3. **Capital filings for each.** The filing history endpoint per company,
   category `capital`, batched five at a time to stay inside the rate limit.
4. **An SH01 since the last run?** Keeps only companies with an SH01 dated in
   the last 36 hours, and carries the filing date forward. Verified against live
   filings by widening the window to a year for one execution: 7 SH01s across
   the 100 companies in the watchlist. The window is back at 36 hours, which is
   the schedule interval plus slack for a weekend.
5. **Screen against `icp.yml`** before the expensive step, not after, so the
   agent never spends a diagnostic run on a company it would have rejected.
6. **Run the diagnostic.** This is where the branch currently stops, and the
   reason is in the table below.
7. **Did it produce a report?** If it refused or screened out, the branch ends
   at `No report, no outreach`. The outbound is only ever sent when there is a
   real read to open with. That node is the whole argument for the refusal path:
   without it, a diagnostic that declines to diagnose would still trigger a cold
   email, and the one thing worse than no personalisation is personalisation
   that is wrong.

## What needs attaching before it runs

| Node group | Needs | Notes |
|---|---|---|
| Every Brevo node | one Header Auth credential, `api-key` | The same key the build already sends with. One credential covers all six. |
| Both Companies House nodes | Basic Auth, key as username, password blank | Free REST key from `developer.company-information.service.gov.uk`. One credential covers both. |
| `Run the diagnostic` | `DIAGNOSTIC_URL` variable | `diagnose.py` is a library with a CLI and is not exposed over HTTP, so this node needs a small wrapper deployed. Branch A needs no such thing. |
| `Run the diagnostic` | a website for each company | **The larger gap.** See below. |
| Brevo template ids 4, 5, 6 | the three follow-up templates | Referenced by id rather than inlined, so the copy is editable without touching the workflow. |

## The gap between the signal and the diagnostic

Companies House publishes the number, the name, the registered address, the
officers and the filings. **It does not publish a website.**

The diagnostic takes a URL and nothing else. So the funding branch has a real
discontinuity in the middle of it: it can tell you, accurately and with a date,
that a company just issued equity, and it cannot tell you where to point the
diagnostic. The `$json.website` that `Run the diagnostic` passes does not exist
on a Companies House record and never will.

This is documented rather than solved, deliberately. Closing it means a
resolution step, matching a registered company name to a live domain, and that
is a whole class of problem with its own failure modes: the wrong company, a
dead domain, a parked page, a holding company whose trading name differs. A
resolution step written quickly under time pressure would be the least tested
thing in the build, feeding the most expensive one. The right place to solve it
is against a real data source Connectd chooses, not a guess made here.

Everything before that node is verified. Everything after it is built and
unreachable until it is closed.

## Honest status

Branch A runs once the Brevo credential is attached.

Branch B runs as far as the SH01 detection, which has been executed against live
Companies House data. It stops at `Run the diagnostic`, which needs two things:
the diagnostic behind an endpoint, and a way to get from a company number to a
website.

Neither branch is claimed as running in production, and the write-up says so in
the same words.
