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

1. **Companies House advanced search**, filtered to the SIC codes in scope.
   SH01 is the allotment of shares filing, which is the legal record of a round
   landing, so it is a dated public event rather than a press mention that may
   describe something six months old.
2. **Screen against `icp.yml`** before the expensive step, not after, so the
   agent never spends a diagnostic run on a company it would have rejected.
3. **Run the diagnostic.**
4. **Did it produce a report?** If it refused or screened out, the branch ends
   at `No report, no outreach`. The outbound is only ever sent when there is a
   real read to open with. That node is the whole argument for the refusal path:
   without it, a diagnostic that declines to diagnose would still trigger a cold
   email, and the one thing worse than no personalisation is personalisation
   that is wrong.

## What needs attaching before it runs

| Node group | Needs | Notes |
|---|---|---|
| Every Brevo node | one Header Auth credential, `api-key` | The same key the build already sends with. One credential covers all six. |
| Companies House | Basic Auth, key as username, blank password | Free API key from their developer portal. |
| `Run the diagnostic` | `DIAGNOSTIC_URL` variable | The one genuine gap. `diagnose.py` is a library with a CLI and is not currently exposed over HTTP, so this node needs a small wrapper deployed before branch B can run end to end. Branch A needs no such thing. |
| Brevo template ids 4, 5, 6 | the three follow-up templates | Referenced by id rather than inlined, so the copy is editable without touching the workflow. |

## Honest status

Branch A runs once the Brevo credential is attached. Branch B runs once the
diagnostic is behind an endpoint. Neither is claimed as running in production,
and the write-up says so in the same words.
