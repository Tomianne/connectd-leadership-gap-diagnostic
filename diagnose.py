#!/usr/bin/env python3
"""
Leadership Gap Diagnostic: the core engine.

Takes a startup's public website and returns up to three named senior advisory
gaps, each one carrying the specific evidence that supports it and a confidence
tier, plus an explicit record of what could not be seen.

Design notes, because the mechanism is the point:

  The expensive failure in this system is not a lost lead. It is a confidently
  wrong gap, in writing, in a document a founder may forward to their board, with
  a brand attached to it. Every other failure costs a lead. That one costs
  credibility with exactly the population the business needs to be trusted by.

  So all the quality gates sit at one seam, evidence to named gap, and nowhere
  else. Five of them:

    1. Closed taxonomy. The model classifies, it does not generate.
    2. Mandatory citation. No gap without quoted evidence and a source URL.
    3. Permission to name fewer than three. The count is an output, not a target.
    4. An adversarial pass. A second model tries to falsify each claim.
    5. An unknowns section, which removes the incentive to fill silence.

  Gates are deliberately absent elsewhere. Extraction is cheap and its worst
  failure is caught by the confirmation step. There is no human review of an
  individual report when all the gap rules passed, because a human in that seat at
  volume rubber stamps, and a rubber stamp is worse than a rule since it looks
  like oversight.

Usage:
    python diagnose.py https://example.com
    python diagnose.py https://example.com --slug example --no-confirm
    python diagnose.py --help
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install pyyaml")

class LLMEmptyResponse(RuntimeError):
    """The model returned no usable content. Distinct from a transport failure."""


ROOT = Path(__file__).parent
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)

# Cheap model for extraction, stronger for the judgement call, small and
# different for the adversary. Cost discipline is a design constraint here, not
# an afterthought: the whole run has to stay worth doing at volume.
MODEL_EXTRACT = os.environ.get("MODEL_EXTRACT", "anthropic/claude-haiku-4.5")
MODEL_CLASSIFY = os.environ.get("MODEL_CLASSIFY", "anthropic/claude-sonnet-5")
MODEL_ADVERSARY = os.environ.get("MODEL_ADVERSARY", "anthropic/claude-haiku-4.5")

PAGES_TO_TRY = [
    "",
    "/about",
    "/about-us",
    "/team",
    "/our-team",
    "/people",
    "/company",
    "/careers",
    "/jobs",
    "/pricing",
    "/contact",
]


# --------------------------------------------------------------------------
# config and environment
# --------------------------------------------------------------------------

def load_env():
    """Walk up from this file until a .env is found. Returns {} if there is none."""
    for parent in [ROOT] + list(ROOT.parents):
        candidate = parent / ".env"
        if candidate.exists():
            env = {}
            with open(candidate, encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        env[k.strip()] = v.strip().strip('"').strip("'")
            return env
    return {}


def api_key():
    key = os.environ.get("OPENROUTER_API_KEY") or load_env().get("OPENROUTER_API_KEY")
    if not key:
        sys.exit(
            "OPENROUTER_API_KEY not found. Set it in the environment or in a .env "
            "file, or run the Streamlit app in demo mode, which needs no key."
        )
    return key


def load_yaml(name):
    with open(ROOT / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


# --------------------------------------------------------------------------
# step 1 and 2: fetch, and the identity confirmation gate
# --------------------------------------------------------------------------

def fetch(url, timeout=15):
    """Fetch one URL as text. Returns None on any failure, which is not fatal."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(600_000)
            charset = r.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace")
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
        return None


def strip_html(html):
    """Crude but adequate text extraction. No dependency on a parser."""
    html = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?s)<!--.*?-->", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )
    return re.sub(r"\s+", " ", text).strip()


def crawl(base_url, max_pages=8):
    """
    Fetch a handful of predictable pages. Deliberately not a real crawler: the
    pages that carry leadership evidence are nearly always at known paths, and a
    broad crawl costs time and goodwill for very little extra signal.
    """
    base_url = base_url.rstrip("/")
    if not base_url.startswith("http"):
        base_url = "https://" + base_url

    pages, seen = [], set()
    for path in PAGES_TO_TRY:
        if len(pages) >= max_pages:
            break
        url = base_url + path
        if url in seen:
            continue
        seen.add(url)
        html = fetch(url)
        if not html:
            continue
        text = strip_html(html)
        if len(text) < 120:
            continue
        title = ""
        m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
        if m:
            title = strip_html(m.group(1))[:200]
        pages.append({"url": url, "title": title, "text": text[:14_000]})
    return pages


def identity_card(pages):
    """
    Cheap, deterministic summary for the confirmation gate. This runs before any
    expensive call: it stops the entire report being about the wrong company,
    which is the cheapest catastrophic failure available, and it doubles as the
    spend gate because nothing costly runs until a human has confirmed.
    """
    if not pages:
        return None
    home = pages[0]
    desc = ""
    for p in pages:
        snippet = p["text"][:400]
        if len(snippet) > len(desc):
            desc = snippet
    return {
        "url": home["url"],
        "title": home["title"],
        "first_impression": desc[:400],
        "pages_found": [p["url"] for p in pages],
    }


# --------------------------------------------------------------------------
# the LLM transport
# --------------------------------------------------------------------------

def llm(model, system, user, key, max_tokens=3000, temperature=0.0):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/leadership-gap-diagnostic",
            "X-Title": "Leadership Gap Diagnostic",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            body = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        sys.exit(f"OpenRouter returned {e.code}: {e.read().decode()[:400]}")

    choices = body.get("choices") or []
    if not choices:
        raise LLMEmptyResponse(f"{model} returned no choices: {str(body)[:300]}")
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    finish = choices[0].get("finish_reason")
    if not content:
        # A model can legitimately return nothing: a content filter, a refusal, or
        # the token budget consumed before any text was emitted. Callers decide
        # what to do about it, because the right answer differs per step.
        raise LLMEmptyResponse(
            f"{model} returned empty content (finish_reason={finish})"
        )
    return content


def parse_json(text):
    """Models wrap JSON in prose and fences more often than they should."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    depth, start = 0, None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    start = None
    return None


# --------------------------------------------------------------------------
# step 3: evidence extraction
# --------------------------------------------------------------------------

EXTRACT_SYSTEM = """You extract verifiable facts from a company's own public website.

You are building an evidence record that a human will audit. Rules, in order of
importance:

1. Record only what the text states or shows. Never infer, never fill a gap with
   what is usually true of companies like this.
2. Every populated field carries the source URL it came from.
3. If the text does not support a field, return null for it and add a short note
   to `not_visible` saying what you looked for and did not find. An honest null is
   worth more than a plausible guess, because everything downstream trusts this
   record.
4. Do not assess the company. Do not name strengths, weaknesses or gaps. That is
   someone else's job and doing it here corrupts the evidence.

Return only JSON matching this shape:

{
  "company_name": str|null,
  "one_line": str|null,
  "what_they_sell": str|null,
  "who_they_sell_to": str|null,
  "sector": str|null,
  "apparent_stage": "pre-seed"|"seed"|"series-a"|"later"|"unknown",
  "team_members": [{"name": str, "role": str, "source_url": str}],
  "team_size_estimate": int|null,
  "open_roles": [{"title": str, "source_url": str}],
  "funding_mentions": [{"detail": str, "source_url": str}],
  "customer_or_logo_claims": [str],
  "pricing_visible": bool,
  "regulated_sector_signals": [str],
  "handles_personal_data_signals": [str],
  "physical_product_signals": [str],
  "last_activity_seen": str|null,
  "not_visible": [str],
  "sources": [str]
}"""


def extract_evidence(pages, key):
    corpus = "\n\n".join(
        f"=== {p['url']} ===\nTITLE: {p['title']}\n{p['text']}" for p in pages
    )[:90_000]
    try:
        out = llm(MODEL_EXTRACT, EXTRACT_SYSTEM, corpus, key, max_tokens=4000)
    except LLMEmptyResponse as e:
        sys.exit(f"Extraction failed: {e}")
    ev = parse_json(out)
    if ev is None:
        sys.exit("Extraction did not return parseable JSON. Re-run or lower the page count.")
    ev.setdefault("sources", [p["url"] for p in pages])
    ev["_extracted_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    return ev


def evidence_completeness(ev):
    """How much did we actually see? Drives the refusal gate."""
    fields = [
        bool(ev.get("company_name")),
        bool(ev.get("what_they_sell")),
        bool(ev.get("who_they_sell_to")),
        bool(ev.get("team_members")),
        bool(ev.get("open_roles")),
        bool(ev.get("funding_mentions")),
        bool(ev.get("sector")),
        ev.get("apparent_stage") not in (None, "unknown"),
    ]
    return sum(fields), len(fields)


def has_leadership_visibility(ev):
    """
    Can we see anything at all about who runs this company?

    This is the load bearing check, and it was added after reading real output.
    A run against a 615 character site produced two gaps rated medium confidence,
    where the stated reasoning was, in effect, "there is no team page, so there is
    no compliance lead". That is inference from the absence of a page, not
    evidence about the company, and it is the single failure mode this whole
    system exists to avoid.

    You cannot diagnose a LEADERSHIP gap with no visibility of the leadership.
    """
    return bool(ev.get("team_members")) or bool(ev.get("open_roles"))


def should_refuse(ev, taxonomy):
    rule = taxonomy["refusal"]
    score, _ = evidence_completeness(ev)
    if score < rule["min_evidence_fields"]:
        return True, f"only {score} of 8 evidence fields populated, threshold is {rule['min_evidence_fields']}"
    if not has_leadership_visibility(ev):
        return True, (
            "no leadership visibility: no team members and no open roles were found, "
            "so any gap named would be inferred from the absence of a page rather "
            "than from evidence about the company"
        )
    return False, None



# --------------------------------------------------------------------------
# step 3b: ICP qualification
#
# This step was missing from the first build, and its absence produced a full
# report for a 29 person company with a named blue chip client, which sits
# outside the stated ICP. A funnel that reports on everything it is given has no
# ICP, it has a preference. The screen runs on extracted evidence, before any
# judgement is made about gaps.
# --------------------------------------------------------------------------

def qualify(ev, icp):
    """Return (verdict, reasons). Verdict is 'in', 'out' or 'review'."""
    reasons = []
    target = icp["target"]

    stage = ev.get("apparent_stage")
    if stage and stage != "unknown" and stage not in target["stage"]:
        reasons.append(
            f"apparent stage '{stage}' is outside the target stages "
            f"({', '.join(target['stage'])})"
        )

    size = ev.get("team_size_estimate")
    if not size and ev.get("team_members"):
        size = len(ev["team_members"])
    if size:
        if size > target["team_size"]["max"]:
            reasons.append(
                f"team of about {size} is above the maximum of "
                f"{target['team_size']['max']}, so the company can likely hire "
                f"outright rather than needing pro bono advisory"
            )
        elif size < target["team_size"]["min"]:
            reasons.append(f"team of about {size} is below the minimum of {target['team_size']['min']}")

    # A full senior team present is the explicit disqualifier that matters most,
    # because naming a gap here would mean inventing one.
    roles = " ".join((t.get("role") or "").lower() for t in (ev.get("team_members") or []))
    has_finance = any(k in roles for k in ("cfo", "finance director", "head of finance", "chief financial"))
    has_commercial = any(
        k in roles for k in ("cro", "chief revenue", "cco", "chief commercial", "vp sales", "head of sales", "sales director")
    )
    if has_finance and has_commercial:
        reasons.append("a finance lead and a commercial lead are both already named on the team")

    if not reasons:
        return "in", []
    return "out", reasons

# --------------------------------------------------------------------------
# step 4: classification against the closed taxonomy
# --------------------------------------------------------------------------

CLASSIFY_SYSTEM = """You classify a company's senior advisory gaps against a CLOSED list of archetypes.

You are not asked what this company needs. You are asked which of the supplied
archetypes the evidence supports. That distinction is the whole job.

Hard rules:

1. Select ONLY from the archetype ids provided. Never invent one, never merge two.
2. Name AT MOST {max_gaps}. Naming fewer is the correct answer when the evidence
   supports fewer. Do not reach the maximum for its own sake. An empty list is a
   valid answer.
3. Every gap requires a `quoted_evidence` string lifted verbatim from the evidence
   record, and the `source_url` it came from. No citation means no gap.
4. Assign confidence honestly against the supplied definitions. Inference from
   absence alone is `low` and must be phrased as an open question.
5. A disqualifier overrides everything. If the evidence shows the role is already
   filled, do not name that gap.

Return only JSON:

{
  "gaps": [
    {
      "archetype_id": str,
      "confidence": "high"|"medium"|"low",
      "quoted_evidence": str,
      "source_url": str,
      "reasoning": str,
      "what_goes_wrong": str
    }
  ],
  "open_questions": [str],
  "notes_for_human": str
}"""


def classify(ev, taxonomy, key):
    archetypes = [
        {
            "id": a["id"],
            "name": a["name"],
            "covers": a["covers"],
            "signals": a["signals"],
        }
        for a in taxonomy["archetypes"]
    ]
    system = CLASSIFY_SYSTEM.replace("{max_gaps}", str(taxonomy["meta"]["max_gaps_per_report"]))
    user = json.dumps(
        {
            "evidence": ev,
            "archetypes": archetypes,
            "confidence_definitions": taxonomy["confidence_tiers"],
        },
        indent=2,
    )[:120_000]
    last_error = None
    for attempt in (1, 2):
        try:
            out = llm(MODEL_CLASSIFY, system, user, key, max_tokens=8000)
        except LLMEmptyResponse as e:
            last_error = str(e)
            continue
        result = parse_json(out)
        if result is not None:
            return result
        last_error = f"unparseable JSON on attempt {attempt}"

    # Fail closed. An unreadable classifier response must never become an empty
    # gap list presented as "no gaps found", because that reads to a founder as a
    # clean bill of health nobody actually established. The caller turns this
    # into an error outcome, not a delivered one.
    return {"gaps": [], "open_questions": [], "classifier_failed": last_error}


# --------------------------------------------------------------------------
# step 5: the adversarial pass
# --------------------------------------------------------------------------

ADVERSARY_SYSTEM = """Your only job is to falsify claims. You are not here to be balanced.

You receive an evidence record and a set of claimed advisory gaps. Run FOUR checks
on each claim, in this order. Any one of them failing is enough to act.

CHECK 1, direct contradiction.
Does the evidence show the role is already filled? A named CFO contradicts a
finance gap. A head of sales contradicts a commercial gap.

CHECK 2, evidence inversion. This is the most important check and the one most
often missed.
Does the quoted evidence actually support the claim, or does it support the
OPPOSITE? A named blue chip customer is evidence the company CAN sell to
enterprises, not evidence that it cannot. A published pricing page is evidence
pricing exists. A detailed privacy notice is evidence someone thought about
privacy. If the citation points the other way, the claim is inverted and must be
dropped, however plausible the surrounding reasoning sounds.

CHECK 3, relevance of the citation.
Does the quoted evidence actually bear on THIS archetype? A missing advisory board
section is not the same thing as lacking domain expertise, if the team already
includes qualified specialists. Cite mismatch means demote at minimum.

CHECK 4, shared evidence.
If two or more claims rest on the same quoted evidence, at most one of them is
genuinely evidenced. Demote the others.

Do not assess whether a claim is reasonable or commercially sensible. Only run
these four checks.

For each claim return:

{
  "verdicts": [
    {
      "archetype_id": str,
      "contradicted": true|false,
      "failed_check": 1|2|3|4|null,
      "contradicting_evidence": str|null,
      "recommended_action": "keep"|"demote_to_question"|"drop"
    }
  ]
}

Use "drop" for check 1 or check 2 failures, because both mean the claim is wrong
rather than merely uncertain. Use "demote_to_question" for check 3 and check 4.
Return only JSON."""


def adversarial_pass(ev, gaps, key):
    if not gaps:
        return {"verdicts": []}
    user = json.dumps(
        {
            "evidence": ev,
            "claims": [
                {
                    "archetype_id": g["archetype_id"],
                    "quoted_evidence": g.get("quoted_evidence"),
                    "reasoning": g.get("reasoning"),
                }
                for g in gaps
            ],
        },
        indent=2,
    )[:120_000]
    try:
        out = llm(MODEL_ADVERSARY, ADVERSARY_SYSTEM, user, key, max_tokens=2000)
    except LLMEmptyResponse as e:
        # The adversarial pass is a safety gate. If it did not run, say so on the
        # report rather than presenting unchallenged claims as though they had
        # survived a challenge.
        return {"verdicts": [], "adversary_failed": str(e)}
    return parse_json(out) or {"verdicts": [], "adversary_failed": "unparseable JSON"}


def flag_shared_evidence(gaps):
    """
    Deterministic version of adversary check 4. Two gaps resting on identical
    quoted evidence cannot both be independently evidenced. Observed in a real
    run: a commercial gap and a finance gap both cited the same team list.
    """
    seen = {}
    for g in gaps:
        q = (g.get("quoted_evidence") or "").strip().lower()
        if not q:
            continue
        if q in seen:
            g["confidence"] = "low"
            g["shared_evidence_with"] = seen[q]
            g["cap_reason"] = (
                "This gap cites the same evidence as another gap in the same "
                "report, so it is not independently evidenced. Presented as an "
                "open question."
            )
        else:
            seen[q] = g["archetype_id"]
    return gaps


def cap_confidence(gaps, ev):
    """
    Enforce the confidence tiers in code rather than trusting the model to apply
    its own instructions. The classifier was observed rating a gap `medium` when
    its own stated reasoning was inference from absence, which the tier
    definitions call `low`. Asking more firmly in the prompt is not a control.
    This is.
    """
    team_visible = bool(ev.get("team_members"))
    capped = []
    for g in gaps:
        if not team_visible and g.get("confidence") in ("high", "medium"):
            g["confidence_capped_from"] = g["confidence"]
            g["confidence"] = "low"
            g["cap_reason"] = (
                "No team members were visible, so this gap rests on absence of "
                "evidence rather than evidence of absence. Presented as an open "
                "question."
            )
        capped.append(g)
    return capped


def adjudicate(gaps, verdicts):
    """Apply the adversary's findings. Demotions and drops are recorded, not silent."""
    by_id = {v["archetype_id"]: v for v in verdicts.get("verdicts", [])}
    kept, demotions = [], []
    for g in gaps:
        v = by_id.get(g["archetype_id"])
        if not v or not v.get("contradicted"):
            kept.append(g)
            continue
        action = v.get("recommended_action", "demote_to_question")
        demotions.append(
            {
                "archetype_id": g["archetype_id"],
                "action": action,
                "failed_check": v.get("failed_check"),
                "contradicting_evidence": v.get("contradicting_evidence"),
            }
        )
        if action == "drop":
            continue
        g["confidence"] = "low"
        g["demoted"] = True
        g["contradicting_evidence"] = v.get("contradicting_evidence")
        kept.append(g)
    return kept, demotions


# --------------------------------------------------------------------------
# assembly
# --------------------------------------------------------------------------

def enrich(gaps, taxonomy):
    """Attach the human authored archetype content to each machine selected gap."""
    lookup = {a["id"]: a for a in taxonomy["archetypes"]}
    out = []
    for g in gaps:
        a = lookup.get(g["archetype_id"])
        if not a:
            continue  # the model invented an id; drop it silently and count it
        out.append(
            {
                **g,
                "name": a["name"],
                "covers": a["covers"],
                "profile": a["profile"],
                "first_questions": a["first_questions"],
                "unfilled_six_months": g.get("what_goes_wrong") or a["unfilled_six_months"],
            }
        )
    return out


def run(url, slug=None, confirm=True):
    taxonomy = load_yaml("taxonomy.yml")
    key = api_key()
    run_id = uuid.uuid4().hex[:12]
    started = dt.datetime.now(dt.timezone.utc)

    print(f"[1/6] fetching {url}")
    pages = crawl(url)
    if not pages:
        return {
            "run_id": run_id,
            "slug": slug,
            "url": url,
            "outcome": "unreachable",
            "message": "Nothing could be fetched from that address.",
        }
    print(f"      {len(pages)} pages retrieved")

    card = identity_card(pages)
    print(f"[2/6] identity: {card['title'][:70] or '(no title)'}")
    if confirm:
        print("\n      " + (card["first_impression"][:300] or ""))
        if input("\n      Is this the right company? [y/N] ").strip().lower() not in ("y", "yes"):
            return {"run_id": run_id, "slug": slug, "url": url, "outcome": "wrong_company"}

    print("[3/6] extracting evidence")
    ev = extract_evidence(pages, key)
    score, total = evidence_completeness(ev)
    print(f"      completeness {score}/{total}")

    refuse, why = should_refuse(ev, taxonomy)
    if refuse:
        print(f"[4/6] REFUSING: {why}")
        return {
            "run_id": run_id,
            "slug": slug,
            "url": url,
            "company_name": ev.get("company_name"),
            "outcome": "refused",
            "refusal_reason": why,
            "refusal_message": taxonomy["refusal"]["message"].strip(),
            "evidence": ev,
            "evidence_completeness": f"{score}/{total}",
        }

    icp = load_yaml("icp.yml")
    verdict, why = qualify(ev, icp)
    if verdict == "out":
        print(f"[4/6] OUT OF ICP: {'; '.join(why)}")
        return {
            "run_id": run_id,
            "slug": slug,
            "url": url,
            "company_name": ev.get("company_name"),
            "outcome": "out_of_icp",
            "icp_reasons": why,
            "evidence": ev,
            "evidence_completeness": f"{score}/{total}",
            "message": (
                "This company sits outside the profile this diagnostic is built for. "
                "Producing a leadership gap report anyway would mean inventing a gap "
                "to fill a template."
            ),
        }

    print("[4/6] classifying against taxonomy")
    result = classify(ev, taxonomy, key)
    raw_gaps = result.get("gaps", [])
    print(f"      {len(raw_gaps)} candidate gaps: {[g['archetype_id'] for g in raw_gaps]}")

    if result.get("classifier_failed"):
        print(f"[5/6] CLASSIFIER FAILED: {result['classifier_failed']}")
        return {
            "run_id": run_id,
            "slug": slug,
            "url": url,
            "company_name": ev.get("company_name"),
            "outcome": "error",
            "error": f"classification failed: {result['classifier_failed']}",
            "evidence": ev,
            "evidence_completeness": f"{score}/{total}",
            "message": (
                "We could not complete this analysis. Rather than show you an empty "
                "result that reads like a clean bill of health, we would rather say "
                "it did not run."
            ),
        }

    print("[5/6] adversarial pass")
    verdicts = adversarial_pass(ev, raw_gaps, key)
    kept, demotions = adjudicate(raw_gaps, verdicts)
    kept = flag_shared_evidence(kept)
    kept = cap_confidence(kept, ev)
    shared = [g["archetype_id"] for g in kept if g.get("shared_evidence_with")]
    if shared:
        print(f"      demoted, evidence shared with another gap: {shared}")
    capped = [g["archetype_id"] for g in kept if g.get("confidence_capped_from")]
    if capped:
        print(f"      confidence capped to low (no team visible): {capped}")
    if demotions:
        for d in demotions:
            print(f"      {d['action']}: {d['archetype_id']}")
    else:
        print("      no contradictions found")

    gaps = enrich(kept, taxonomy)
    print(f"[6/6] {len(gaps)} gaps confirmed")

    return {
        "run_id": run_id,
        "slug": slug or re.sub(r"[^a-z0-9]+", "-", (ev.get("company_name") or "company").lower()).strip("-"),
        "url": url,
        "outcome": "delivered",
        "company_name": ev.get("company_name"),
        "one_line": ev.get("one_line"),
        "generated_at": started.isoformat(timespec="seconds"),
        "taxonomy_version": taxonomy["meta"]["version"],
        "evidence": ev,
        "evidence_completeness": f"{score}/{total}",
        "gaps": gaps,
        "open_questions": result.get("open_questions", []),
        "not_visible": ev.get("not_visible", []),
        "demotions": demotions,
        "notes_for_human": result.get("notes_for_human", ""),
        "classifier_failed": result.get("classifier_failed"),
        "adversary_failed": verdicts.get("adversary_failed"),
    }




# --------------------------------------------------------------------------
# the run log
#
# One row per run, written on every outcome including the refusals and the
# screens. The refusals matter most: refusal rate is a monitored guardrail, and it
# can only be monitored if a refusal is logged as an event rather than treated as
# a non event.
# --------------------------------------------------------------------------

def log_run(report, cost_usd=0.0):
    import csv as _csv

    from loop import COLUMNS  # single definition of the schema, imported not copied

    ev = report.get("evidence") or {}
    gaps = report.get("gaps") or []
    demotions = report.get("demotions") or []

    row = {
        "run_id": report.get("run_id"),
        "timestamp": report.get("generated_at") or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "input_url": report.get("url"),
        "company_name": report.get("company_name"),
        "confirmation_corrected": "",
        "evidence_completeness": report.get("evidence_completeness"),
        "leadership_visible": bool(ev.get("team_members") or ev.get("open_roles")),
        "outcome": report.get("outcome"),
        "icp_verdict": "out" if report.get("outcome") == "out_of_icp" else ("in" if gaps or report.get("outcome") == "delivered" else ""),
        "archetypes_named": "|".join(g.get("archetype_id", "") for g in gaps),
        "confidence_per_archetype": "|".join(g.get("confidence", "") for g in gaps),
        "adversary_drops": "|".join(d.get("archetype_id", "") for d in demotions if d.get("action") == "drop"),
        "confidence_caps": "|".join(g.get("archetype_id", "") for g in gaps if g.get("confidence_capped_from") or g.get("shared_evidence_with")),
        "gaps_final_count": len(gaps),
        "config_version": _config_version(),
        "taxonomy_version": report.get("taxonomy_version", ""),
        "variant_ids": "baseline",
        "delivered": report.get("outcome") == "delivered",
        # These are filled by the funnel, not by the engine. They are blank here and
        # that is the honest state: the loop has no behavioural data yet.
        "emailed": "",
        "shared": "",
        "returned": "",
        "booked": "",
        "founder_rating": "",
        "human_gap_verdicts": "",
        "brief_accepted": "",
        "llm_cost_usd": f"{cost_usd:.5f}" if cost_usd else "",
    }

    path = ROOT / "runs.csv"
    exists = path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=COLUMNS)
        if not exists:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in COLUMNS})


def _config_version():
    try:
        return load_yaml("config.yml").get("version", "")
    except Exception:
        return ""


def main():
    ap = argparse.ArgumentParser(description="Leadership Gap Diagnostic")
    ap.add_argument("url", help="the startup's website")
    ap.add_argument("--slug", help="output filename stem")
    ap.add_argument("--no-confirm", action="store_true", help="skip the identity gate")
    ap.add_argument("--out", default="runs", help="output directory for the JSON")
    args = ap.parse_args()

    report = run(args.url, slug=args.slug, confirm=not args.no_confirm)

    outdir = ROOT / args.out
    outdir.mkdir(exist_ok=True)
    stem = report.get("slug") or report["run_id"]
    path = outdir / f"{stem}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwrote {path}")
    print(f"outcome: {report['outcome']}")
    return 0 if report["outcome"] in ("delivered", "refused") else 1


if __name__ == "__main__":
    sys.exit(main())
