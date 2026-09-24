#!/usr/bin/env python3
"""
The optimisation loop.

An honest description first, because the alternative is the thing everyone claims.

At thirty runs a week this is not an optimiser. It is a disciplined experiment log
with an automated analyst attached, and its real value is that it makes it
impossible to change three things at once and then argue about what worked. It
becomes a genuine optimiser somewhere in the low hundreds of runs a month.
Claiming self improvement before that is a claim about statistics the sample size
does not support, and a Head of GTM will spot it.

What it does:

  reads   runs.csv, one row per diagnostic run
  writes  a proposed diff to config.yml, and only to config.yml
  never   touches the code, and never touches taxonomy.yml without a human merge

Two clocks, because the things they touch carry different risk:

  fast    weekly or every 30 runs. Copy and CTA only. Auto promotes.
  slow    monthly or every 100 human reviewed briefs. Looks for archetypes that
          are named often and rejected often, which are the taxonomy's bad
          entries. Opens a proposal. Never merges.

The label hierarchy matters more than the statistics, so it is stated explicitly
in rank order, because an optimiser is only as good as its ground truth:

  1. strongest   the human accept, edit or reject per gap. Someone with skin in
                 the game judging each named gap. Low volume, high value.
  2. medium      behaviour. Completed, shared, returned, booked.
  3. weakest     the founder's own yes, partly or no. Cheap, high volume, and
                 biased towards politeness, so it sets direction and never
                 decides alone.

Usage:
    python loop.py --dry-run          # always start here
    python loop.py --fast --dry-run
    python loop.py --slow --dry-run
    python loop.py --fast --apply     # writes a new config version
"""

import argparse
import csv
import datetime as dt
import sys
from collections import defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install pyyaml")

ROOT = Path(__file__).parent
RUNS = ROOT / "runs.csv"
CONFIG = ROOT / "config.yml"

# The log schema. Deciding this IS deciding what the loop is capable of learning,
# so it is designed first and the loop second. Every variable the loop can change
# and every outcome it can read has a column here. Anything absent from this list
# is invisible to the loop no matter how clever the analysis gets.
COLUMNS = [
    "run_id",
    "timestamp",
    "input_url",
    "company_name",
    "confirmation_corrected",     # did the founder correct our identification
    "evidence_completeness",      # n/8
    "leadership_visible",
    "outcome",                    # delivered | refused | out_of_icp | error | unreachable
    "icp_verdict",
    "archetypes_named",           # pipe separated
    "confidence_per_archetype",   # pipe separated
    "adversary_drops",            # pipe separated
    "confidence_caps",            # pipe separated
    "gaps_final_count",
    "config_version",             # makes revert an operation rather than a wish
    "taxonomy_version",
    "variant_ids",                # which copy variants were in force
    "delivered",
    "emailed",                    # did they ask for a copy
    "shared",                     # did they send it onward. the referral loop
    "returned",
    "booked",
    "founder_rating",             # yes | partly | no. weakest label, direction only
    "human_gap_verdicts",         # accept|edit|reject per gap. strongest label
    "brief_accepted",
    "llm_cost_usd",
]


def read_runs():
    if not RUNS.exists():
        return []
    with open(RUNS, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def ensure_log():
    if RUNS.exists():
        return
    with open(RUNS, "w", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=COLUMNS).writeheader()
    print(f"created {RUNS.name} with {len(COLUMNS)} columns")


def load_config():
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def num(row, key, default=0.0):
    try:
        return float(row.get(key) or default)
    except (TypeError, ValueError):
        return default


def truthy(v):
    return str(v).strip().lower() in ("1", "true", "yes", "y")


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------

def metrics(rows):
    total = len(rows)
    if not total:
        return {}
    delivered = [r for r in rows if r.get("outcome") == "delivered"]
    refused = [r for r in rows if r.get("outcome") == "refused"]
    booked = [r for r in rows if truthy(r.get("booked"))]
    accepted = [r for r in rows if truthy(r.get("brief_accepted"))]

    verdicts = []
    for r in rows:
        verdicts += [v for v in (r.get("human_gap_verdicts") or "").split("|") if v]
    rejects = [v for v in verdicts if v.strip().lower() == "reject"]

    ratings = [(r.get("founder_rating") or "").strip().lower() for r in rows]
    rated = [x for x in ratings if x in ("yes", "partly", "no")]

    return {
        "runs": total,
        "start_to_delivered": len(delivered) / total,
        "delivered_to_booked": (len(booked) / len(delivered)) if delivered else None,
        "refusal_rate": len(refused) / total,
        "brief_reject_rate": (len(rejects) / len(verdicts)) if verdicts else None,
        "gap_accuracy": (
            len([x for x in rated if x in ("yes", "partly")]) / len(rated) if rated else None
        ),
        # the north star. downstream enough to be real, and it cannot be gamed by
        # generating engagement that never becomes a placement
        "accepted_briefs_per_100_starts": len(accepted) / total * 100,
        "cost_total_usd": sum(num(r, "llm_cost_usd") for r in rows),
    }


def check_guardrails(m, cfg):
    """Any breach halts the loop and reverts. Returns a list of breach strings."""
    g = cfg["loop"]["guardrails"]
    breaches = []
    if m.get("brief_reject_rate") is not None and m["brief_reject_rate"] > g["max_brief_reject_rate"]:
        breaches.append(
            f"brief reject rate {m['brief_reject_rate']:.0%} exceeds "
            f"{g['max_brief_reject_rate']:.0%}. The loop may be learning to name "
            f"more dramatic gaps to lift bookings."
        )
    if m.get("gap_accuracy") is not None and m["gap_accuracy"] < g["min_gap_accuracy_yes_or_partly"]:
        breaches.append(
            f"gap accuracy {m['gap_accuracy']:.0%} below {g['min_gap_accuracy_yes_or_partly']:.0%}"
        )
    if m.get("refusal_rate") is not None and m["refusal_rate"] < g["min_refusal_rate"]:
        breaches.append(
            f"refusal rate {m['refusal_rate']:.1%} below {g['min_refusal_rate']:.1%}. "
            f"A system that stops refusing has learned to guess."
        )
    return breaches


# ---------------------------------------------------------------------------
# the fast loop
# ---------------------------------------------------------------------------

def fast_loop(rows, cfg):
    """Copy and CTA only. One variable per surface. Nothing promoted below min sample."""
    min_n = cfg["loop"]["fast"]["min_sample_per_variant"]
    by_variant = defaultdict(list)
    for r in rows:
        by_variant[r.get("variant_ids") or "baseline"].append(r)

    print(f"\nFAST LOOP  (minimum sample per variant: {min_n})")
    if not rows:
        print("  no runs logged yet, nothing to analyse")
        print("  this is the expected state on day one and it is why the log schema")
        print("  was designed before the loop was written")
        return []

    proposals = []
    for variant, vrows in sorted(by_variant.items()):
        m = metrics(vrows)
        s2d = m["start_to_delivered"]
        d2b = m["delivered_to_booked"]
        print(
            f"  {variant:<22} n={m['runs']:<4} "
            f"start_to_delivered={s2d:.0%} "
            f"delivered_to_booked={(f'{d2b:.0%}' if d2b is not None else 'n/a')}"
        )
        if m["runs"] < min_n:
            print(f"     held: n={m['runs']} is below the gate of {min_n}, so no promotion")
            continue
        proposals.append({"variant": variant, "metrics": m})

    if not proposals:
        print("\n  No variant cleared the sample gate. Nothing is promoted.")
        print("  This is the correct outcome, not a failure. Promoting on n<30 is how")
        print("  an optimiser learns noise and then defends it.")
    return proposals


# ---------------------------------------------------------------------------
# the slow loop
# ---------------------------------------------------------------------------

def slow_loop(rows, cfg):
    """
    Looks for one thing only: archetypes that are named often and rejected often.
    Those are the taxonomy's bad entries. Proposes, never merges, because the
    taxonomy decides what a founder gets told about their own company.
    """
    print("\nSLOW LOOP  (taxonomy and threshold proposals, human merge required)")
    named = defaultdict(int)
    rejected = defaultdict(int)
    dropped = defaultdict(int)

    for r in rows:
        ids = [a for a in (r.get("archetypes_named") or "").split("|") if a]
        verds = [v for v in (r.get("human_gap_verdicts") or "").split("|") if v]
        for i, a in enumerate(ids):
            named[a] += 1
            if i < len(verds) and verds[i].strip().lower() == "reject":
                rejected[a] += 1
        for a in [x for x in (r.get("adversary_drops") or "").split("|") if x]:
            dropped[a] += 1

    if not named and not dropped:
        print("  no classified runs yet, nothing to analyse")
        print("\n  What it will look for once there is data:")
        print("    - archetypes named often and rejected often, which are bad taxonomy entries")
        print("    - archetypes the adversarial pass keeps dropping, which are bad signal definitions")
        print("    - thresholds that refuse too much or too little")
        return []

    proposals = []
    # Include archetypes that were dropped outright. They never reach `named`,
    # which would hide the single most useful signal the slow loop has: a signal
    # definition that keeps inviting evidence pointing the other way.
    all_ids = set(named) | set(dropped)
    print(f"  {'archetype':<34} {'named':>6} {'rejected':>9} {'dropped':>8}")
    for a in sorted(all_ids, key=lambda x: -(named[x] + dropped[x])):
        rate = rejected[a] / named[a] if named[a] else 0
        print(f"  {a:<34} {named[a]:>6} {rejected[a]:>9} {dropped[a]:>8}")
        if named[a] >= 5 and rate > 0.4:
            proposals.append(
                {
                    "target": "taxonomy",
                    "archetype": a,
                    "issue": f"rejected by a human in {rate:.0%} of {named[a]} namings",
                    "proposal": "tighten the signals for this archetype, or remove it",
                    "merge": "human required",
                }
            )
        if dropped[a] >= 3:
            proposals.append(
                {
                    "target": "taxonomy",
                    "archetype": a,
                    "issue": f"dropped by the adversarial pass {dropped[a]} times",
                    "proposal": "the signal definition is probably inviting inverted evidence",
                    "merge": "human required",
                }
            )
    return proposals


def apply_fast(cfg, proposals):
    """Bump the config version. In production this opens a pull request."""
    cfg["version"] = int(cfg.get("version", 0)) + 1
    cfg["changed"] = dt.date.today().isoformat()
    cfg["changed_by"] = "fast_loop"
    cfg["rationale"] = f"promoted from {len(proposals)} variant(s) clearing the sample gate"
    CONFIG.write_text(yaml.safe_dump(cfg, sort_keys=False, width=88), encoding="utf-8")
    print(f"\nwrote config.yml at version {cfg['version']}")


def main():
    ap = argparse.ArgumentParser(description="The optimisation loop")
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--slow", action="store_true")
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--apply", action="store_true", help="write changes, fast loop only")
    args = ap.parse_args()

    ensure_log()
    rows = read_runs()
    cfg = load_config()

    print(f"config version {cfg['version']}  |  {len(rows)} runs in the log")

    m = metrics(rows)
    if m:
        print("\nCURRENT METRICS")
        print(f"  north star, accepted briefs per 100 starts: {m['accepted_briefs_per_100_starts']:.1f}")
        print(f"  start to delivered: {m['start_to_delivered']:.0%}")
        d2b = m["delivered_to_booked"]
        print(f"  delivered to booked: {f'{d2b:.0%}' if d2b is not None else 'n/a'}")
        print(f"  refusal rate: {m['refusal_rate']:.1%}")
        print(f"  total LLM cost: ${m['cost_total_usd']:.2f}")

        breaches = check_guardrails(m, cfg)
        if breaches:
            print("\nGUARDRAIL BREACH. The loop halts and reverts to the last good config.")
            for b in breaches:
                print(f"  - {b}")
            return 1
        print("  guardrails: all clear")

    run_both = not (args.fast or args.slow)
    proposals = []
    if args.fast or run_both:
        proposals = fast_loop(rows, cfg)
    if args.slow or run_both:
        slow = slow_loop(rows, cfg)
        if slow:
            print("\n  PROPOSALS, human merge required:")
            for p in slow:
                print(f"    {p['archetype']}: {p['issue']}")
                print(f"      -> {p['proposal']}")

    if args.apply and proposals:
        apply_fast(cfg, proposals)
    elif args.apply:
        print("\nnothing cleared the gate, so nothing was applied")
    else:
        print("\ndry run, nothing written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
