---
name: gap-diagnostic
description: Run the leadership gap diagnostic on a company, review the output, and render it. Use when asked to diagnose a startup's advisory gaps, test the diagnostic, or add a sample. Trigger on "run the diagnostic on X", "diagnose X", "add a sample for X".
---

# Running the diagnostic

## The order, and it matters

```bash
python diagnose.py <url> --slug <slug> --no-confirm
python render.py runs/<slug>.json --out samples
```

Then **read the output before doing anything else**. Every defect this system has
fixed was found by reading a report about a real company and disagreeing with it, not
by testing. Use the `diagnostic-reviewer` agent for anything that will be published.

## The four outcomes are all correct outcomes

| Outcome | Means |
|---|---|
| `delivered` | Up to three evidenced gaps |
| `refused` | Not enough visible to diagnose without guessing |
| `out_of_icp` | Screened before any gap judgement |
| `error` | It did not run, and says so rather than showing an empty result |

Do not treat `refused` or `out_of_icp` as a failure to fix. A diagnostic that only
knows how to produce a diagnosis will produce one whether or not it should.

## Cost

Three model calls per run. Cheap model to extract, stronger to classify, small and
different for the adversary. Check the balance before a batch:

```bash
curl -s https://openrouter.ai/api/v1/credits -H "Authorization: Bearer $OPENROUTER_API_KEY"
```

## Before publishing a report about a real company

- Every quoted claim verified against the live page.
- Framing is opportunity, not deficiency.
- The company is genuinely inside the ICP.
- Nothing in the file names a brand that should not be on it.
