# Leadership Gap Diagnostic

Project instructions. This file is why the repository is legible to Claude Code as a
project rather than as a folder of scripts, and it is committed because a harness you
actually work in leaves artefacts.

## What this is

A lead magnet for acquiring startups, and the agentic funnel behind it. A founder
enters their website. The system names up to three senior advisory gaps, each with
the evidence it rests on, and says explicitly what it could not see.

## The one rule that overrides the others

**Never name a gap that is not evidenced.**

The expensive failure here is not a missed gap or a lost lead. It is a confidently
wrong gap, in writing, in a document a founder may forward to their board. Every
other failure costs a lead. That one costs credibility with the exact population
this business needs to be trusted by.

When in doubt: name fewer gaps, lower the confidence, or refuse.

## Where the gates live, and why not elsewhere

All quality gates sit at one seam, evidence to named gap. Do not add gates
elsewhere by default, and do not remove these:

- `taxonomy.yml` is a closed vocabulary. The classifier selects, it never invents.
- Every gap carries quoted evidence and a source URL, or it does not ship.
- `has_leadership_visibility()` refuses when the leadership is not visible at all.
- `cap_confidence()` and `flag_shared_evidence()` are deterministic. They exist
  because asking a model to respect its own confidence definitions is not a control.
- The adversarial pass runs four checks, and check 2, evidence inversion, is the one
  that catches the failures that read most plausibly.

## Boundaries

- The optimisation loop may write to `config.yml` only.
- The loop may **propose** taxonomy and threshold changes. A human merges them.
- `taxonomy.yml` and `icp.yml` are v0, inferred from Connectd's public offer.
  Replacing them with real criteria is a config edit, not a rebuild. Keep them that
  way.

## House style

- No em dashes, no double hyphens used as dashes, no emojis.
- Say what the thing does and stop.
- Never state an outcome the evidence does not support. If a number has no source,
  it does not go in.

## Before changing anything

Run it on the four committed cases and read the output. Two of them are supposed to
produce no report at all:

```bash
python diagnose.py https://rulemoney.co.uk --no-confirm   # must refuse
python diagnose.py https://www.chatterbox.io --no-confirm # must screen out
python loop.py --dry-run                                  # must refuse to promote at n<30
```

If the refusal or the screen stops firing, that is a regression in the only thing
that matters, whatever the reports look like.
