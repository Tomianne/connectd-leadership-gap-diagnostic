#!/usr/bin/env python3
"""
Render a diagnostic run to a self contained HTML report.

Four outcomes render differently on purpose, because the honest answer is
different in each case:

  delivered   the report, up to three gaps, with evidence and confidence
  refused     we could not see enough, here is a call instead
  out_of_icp  you are not who this is built for, and we say so
  error       it did not run, and we would rather say that than show you nothing
              and let it read as a clean bill of health

The last three are not error pages bolted on. They are the product. A diagnostic
that only knows how to produce a diagnosis will produce one whether or not it
should.

Usage:
    python render.py runs/anemo-labs.json
    python render.py runs/*.json --out samples
"""

import argparse
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent

CSS = """
:root {
  --ink: #16181d;
  --ink-soft: #565b66;
  --ink-faint: #8b909c;
  --bg: #ffffff;
  --panel: #f7f7f5;
  --line: #e4e4e0;
  --accent: #b4532a;
  --high: #1f6b3f;
  --medium: #8a6100;
  --low: #6b6f7a;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font: 16px/1.62 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 760px; margin: 0 auto; padding: 56px 16px 96px; }
header { border-bottom: 1px solid var(--line); padding-bottom: 26px; margin-bottom: 34px; }
.eyebrow {
  font-size: 11px; letter-spacing: .14em; text-transform: uppercase;
  color: var(--ink-faint); margin: 0 0 14px;
}
h1 { font-size: 30px; line-height: 1.22; margin: 0 0 8px; font-weight: 640; letter-spacing: -.015em; }
.sub { color: var(--ink-soft); margin: 0; font-size: 16px; }
.meta { margin-top: 18px; font-size: 13px; color: var(--ink-faint); }
.meta a { color: var(--ink-faint); }
h2 {
  font-size: 12px; letter-spacing: .12em; text-transform: uppercase;
  color: var(--ink-faint); margin: 46px 0 16px; font-weight: 620;
}
h3 { font-size: 19px; margin: 0 0 4px; font-weight: 620; letter-spacing: -.01em; }
p { margin: 0 0 13px; }
ul { margin: 0 0 13px; padding-left: 20px; }
li { margin-bottom: 7px; }
.gap { border: 1px solid var(--line); border-radius: 10px; padding: 24px 24px 20px; margin-bottom: 18px; }
.gap h3 .num { color: var(--accent); font-variant-numeric: tabular-nums; }
.lead-tag {
  font-size: 10.5px; letter-spacing: .1em; text-transform: uppercase;
  color: var(--accent); font-weight: 700; margin: 0 0 10px;
}
.intro {
  background: var(--panel); border-radius: 10px;
  padding: 18px 22px; margin: 0 0 30px; font-size: 15px;
}
.gap-head { display: flex; align-items: baseline; justify-content: space-between; gap: 14px; flex-wrap: wrap; }
.covers { color: var(--ink-soft); font-size: 14px; margin: 2px 0 18px; }
.tag {
  font-size: 10.5px; letter-spacing: .09em; text-transform: uppercase;
  padding: 4px 9px; border-radius: 3px; white-space: nowrap; font-weight: 640;
  border: 1px solid currentColor;
}
.tag.high { color: var(--high); }
.tag.medium { color: var(--medium); }
.tag.low { color: var(--low); }
.ev {
  background: var(--panel); border-left: 2px solid var(--accent);
  padding: 13px 15px; margin: 0 0 15px; font-size: 14.5px;
}
.ev .label {
  display: block; font-size: 14px; color: var(--ink);
  margin-bottom: 5px; font-weight: 680;
}
.ev cite { font-style: normal; display: block; margin-top: 7px; font-size: 12.5px; color: var(--ink-faint); }
.field { margin-bottom: 18px; }
.field .v { display: block; }
h2.doc-title { margin-top: 0; margin-bottom: 14px; }
.field .k {
  font-size: 14px; color: var(--ink); font-weight: 680;
  display: block; margin-bottom: 4px; letter-spacing: -.005em;
}
.gap .field { padding-left: 14px; border-left: 2px solid var(--line); }
.gap .field.answer {
  border-left: 3px solid var(--accent); background: var(--panel);
  padding: 15px 16px; border-radius: 0 7px 7px 0; margin-bottom: 16px;
}
.gap .field.answer .k { color: var(--accent); font-size: 15px; font-weight: 700; }
.gap .field.answer .v { color: var(--ink); }
.gap-cta {
  display: inline-block; margin-top: 9px; font-weight: 640;
  color: var(--accent); font-size: 14px;
}
.gap .field .v { color: var(--ink-soft); }
.note {
  background: #fdf6ec; border: 1px solid #f0dcc0; border-radius: 8px;
  padding: 15px 17px; font-size: 14.5px; margin-bottom: 18px;
}
.panel { background: var(--panel); border-radius: 10px; padding: 26px; }
.cta { border-top: 1px solid var(--line); margin-top: 52px; padding-top: 32px; }
.feedback {
  border: 1px solid var(--line); border-radius: 10px;
  padding: 24px 26px; margin: 34px 0 0;
}
.btn {
  display: inline-block; background: var(--ink); color: #fff; text-decoration: none;
  padding: 13px 22px; border-radius: 7px; font-size: 14.5px; font-weight: 560;
  margin: 0 9px 10px 0;
}
.btn.ghost { background: transparent; color: var(--ink); border: 1px solid var(--line); }
footer {
  margin-top: 58px; padding-top: 22px; border-top: 1px solid var(--line);
  font-size: 12.5px; color: var(--ink-faint);
}
.sources { font-size: 12.5px; color: var(--ink-faint); word-break: break-all; }
.big { font-size: 19px; line-height: 1.55; }
@media (max-width: 600px) {
  .wrap { padding: 34px 16px 72px; }
  h1 { font-size: 25px; }
}
"""


# Model output arrives with em dashes and double hyphens in it. Everything the
# reader sees passes through e(), so the house style is enforced once, here,
# rather than hoped for in three separate prompts.
_DASH_FIXES = [
    ("—", ", "),   # em dash
    ("–", " to "),  # en dash, almost always a range in this output
    (" -- ", ", "),
    ("--", ", "),
]


def load_offer():
    """
    Facts about Connectd that this build has no access to. Config driven so they
    can be made true in an hour rather than invented here.
    """
    try:
        import yaml

        cfg = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
        return (cfg or {}).get("offer") or {}
    except Exception:  # noqa: BLE001
        return {}


def e(x):
    t = str(x if x is not None else "")
    for bad, good in _DASH_FIXES:
        t = t.replace(bad, good)
    t = t.replace("  ", " ").replace(" ,", ",")
    return html.escape(t)


def field(label, value):
    """
    A labelled value that still reads correctly with no stylesheet at all.

    The <br> is load bearing rather than lazy. Gmail strips the <style> block, and
    without a structural break the label ran straight into its value, producing
    "What it doesOlfactory sensors combining proprietary hardware...". CSS is an
    enhancement here, not a dependency.
    """
    return (
        '<div class="field"><strong class="k">' + e(label) + '</strong><br>'
        '<span class="v">' + value + '</span></div>'
    )


def answer_field(label, value):
    """
    Same shape as field(), given visual weight.

    "The person who fills it" is the payoff line. Everything above it describes a
    problem the reader already half knew about; this is the part they act on. It
    was rendering with the same weight as its siblings, so it read as one more
    attribute rather than as the answer.
    """
    return (
        '<div class="field answer"><strong class="k">' + e(label) + '</strong><br>'
        '<span class="v">' + value + '</span></div>'
    )


def shell(title, body, company=None):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="robots" content="noindex">
<style>{CSS}</style>
</head>
<body><div class="wrap">{body}</div></body>
</html>
"""


def header(report, strapline, audience="founder"):
    """
    The eyebrow is a real heading, not a styled paragraph, because mail clients
    strip the stylesheet and it then landed as an orphaned line of body text.

    Run ids and taxonomy versions are build internals. They tell a founder
    nothing and make a document written for them read like a system dump, so
    they appear only in the internal view.
    """
    company = report.get("company_name") or report.get("url")
    url = report.get("url", "")
    when = (report.get("generated_at") or "")[:10]

    meta = f'Read from <a href="{e(url)}">{e(url)}</a>'
    if when:
        meta += f" on {e(when)}"
    if audience == "internal":
        meta += (
            f" &middot; run {e(report.get('run_id'))}"
            f" &middot; taxonomy v{e(report.get('taxonomy_version', 0))}"
        )

    return f"""<header>
  <h2 class="eyebrow doc-title">Leadership Gap Diagnostic</h2>
  <h1>{e(company)}</h1>
  <p class="sub">{e(strapline)}</p>
  <p class="meta">{meta}</p>
</header>"""


def intro_block(context, company=None):
    """
    How the reader arrived decides what the opening has to do.

    Shared context is the interesting one commercially: the reader did not run
    this, so the report has to carry enough framing to stand on its own in a
    forwarded email, while crediting the person who sent it.
    """
    if context == "outbound":
        body = (
            "<strong>We ran a leadership gap analysis on "
            + (e(company) if company else "your company")
            + ".</strong> Connectd places senior operators into early stage companies "
            "as advisors and non executives, and this is how we work out who might "
            "be worth introducing you to. It is built from your public website only. "
            "Nobody has spoken to your team, so it is a starting point rather than an "
            "assessment, and every claim below shows the evidence behind it."
        )
    elif context == "shared":
        body = (
            "<strong>This is a leadership gap analysis of "
            + (e(company) if company else "the company")
            + ", shared with you by someone who has already read it.</strong> It was "
            "produced by Connectd, who place senior operators into early stage "
            "companies as advisors and non executives. It is built from the public "
            "website only and nobody has spoken to the team, so every claim shows the "
            "evidence behind it and can be checked or dismissed quickly."
        )
    else:  # self_serve
        # They typed a URL into a form ten seconds ago. They know nobody spoke to
        # their team, and pre-emptively downgrading the report just tells them to
        # expect less before they have read it. The invitation to disagree already
        # exists, in the feedback block, where it can actually be acted on.
        body = (
            "<strong>We read your public website, and nothing else.</strong> Every claim "
            "below shows the evidence behind it, so you can check or dismiss any of it in "
            "seconds. The last section sets out what we could not see."
        )
    return f'<div class="intro"><p style="margin-bottom:0">{body}</p></div>'


def provenance(ev):
    """
    Where the answer came from. Real, checkable, deliberately near the bottom.

    This used to open the report, on the reasoning that a reader should see what
    was read before they see what was concluded. Read as the founder, it is a
    screen of their own website recited back at them before anything useful
    arrives. They know what their company does. It belongs as provenance for
    anyone who wants to check the working, not as the opening move.
    """
    out = ["<h2>Where this came from</h2>", '<div class="panel">']
    for k, v in [
        ("What we understood you to do", ev.get("what_they_sell")),
        ("Who we understood you to sell to", ev.get("who_they_sell_to")),
    ]:
        if v:
            out.append(field(k, e(v)))

    team = ev.get("team_members") or []
    if team:
        names = "".join(f"<li>{e(t.get('name'))}, {e(t.get('role'))}</li>" for t in team[:14])
        more = f"<li>and {len(team) - 14} others</li>" if len(team) > 14 else ""
        out.append(field("The people we could see", f"<ul>{names}{more}</ul>"))

    fund = ev.get("funding_mentions") or []
    if fund:
        out.append(field(
            "Funding mentioned on the site",
            "<ul>" + "".join(f"<li>{e(f.get('detail'))}</li>" for f in fund) + "</ul>",
        ))

    srcs = ev.get("sources") or []
    if srcs:
        out.append(field("Pages read", '<span class="sources">'
                         + " &middot; ".join(e(x) for x in srcs) + "</span>"))
    out.append("</div>")
    return "".join(out)


def method_footer():
    """
    One statement, not three.

    The caveats were spread across an unrendered notice, a could-not-find list and
    a three paragraph footer, all making the same point. Rigour read once reads as
    rigour. Read three times it reads as uncertainty, which is not what Connectd
    wants its name attached to.
    """
    return """<footer>
<p><strong>How this was made.</strong> Read from the company's public website, nothing
else, with no contact with the team. Every gap carries the evidence behind it, so any
claim here can be checked or dismissed in seconds. A gap marked <strong>open
question</strong> is one the evidence pointed at without settling, and we would rather
ask than assert. If we have missed something that is plainly on your site, tell us and
we will correct it.</p>
</footer>"""


def offer_block(gaps):
    """
    The answer to the problem the report just described.

    Rewritten after reading it as Connectd's Head of GTM. The first version
    defined the offer by what it was not, gave no sense of the bench that is the
    actual asset, and asked for ten minutes without saying what happens in them.
    """
    offer = load_offer()
    count = len(gaps)
    noun = "gap" if count == 1 else "gaps"
    brief_line = (
        f"The {count} {noun} above are written as a brief for exactly that reason. Each "
        "one names the experience that fills it and the questions to put to whoever we "
        "introduce, so you are judging the person rather than taking our word for the "
        "match."
        if gaps
        else "When we do name gaps, they are written as a brief: the experience that "
        "fills each one and the questions to put to whoever we introduce. Working out "
        "which three apply to you is what the call is for."
    )
    close = (
        f"If the {noun} we named are the wrong ones, say so on the call. Getting that "
        "wrong is more useful to us than you politely agreeing."
        if gaps
        else "A conversation gets to the right three faster than a website ever will."
    )

    bench_size = (offer.get("bench_size") or "").strip()
    bench_line = (offer.get("bench_line") or "").strip()
    opener = (
        f"{e(bench_size)} are on Connectd's bench."
        if bench_size
        else "Connectd keeps a bench of senior operators."
    )
    follow = "We place up to three of them" if not bench_size else "Connectd places up to three of them"

    steps = offer.get("process") or []
    steps_html = (
        "<ol>" + "".join(f"<li>{e(x)}</li>" for x in steps) + "</ol>" if steps else ""
    )

    return f"""<h2>What you can do about it</h2>
<div class="panel">
<p class="big"><strong>{opener}</strong> {follow} into a company like yours as advisors
or non executives, for three to six months.</p>
<p>{e(bench_line)}</p>
<p>{brief_line}</p>
</div>

<h3 style="margin-top:30px">What happens if you say yes</h3>
<div class="panel">
{steps_html}
<p style="margin-bottom:0">{close}</p>
</div>"""


def feedback_block(report):
    """
    One question, and it does double duty.

    For the founder it is a chance to push back, which makes the report feel like
    the start of a conversation rather than a verdict. For the system it is the
    highest volume ground truth label the optimisation loop has, and the only one
    available before anybody books anything.
    """
    return """<div class="feedback">
<h2 style="margin-top:0">Did we get this right?</h2>
<p>One question, and it genuinely changes what this tool does next.</p>
<p style="margin-bottom:0">
  <a class="btn ghost" href="#rate-yes">Yes, that is fair</a>
  <a class="btn ghost" href="#rate-partly">Partly</a>
  <a class="btn ghost" href="#rate-no">No, we have these covered</a>
</p>
<p class="sources" style="margin-top:14px;margin-bottom:0">A "no" is the most useful
answer we get.</p>
</div>"""


def capture_block(report):
    """
    The capture step. The report is shown in full first, then the address is asked
    for. Value before friction, and an address given by someone who has just read
    something is worth more than one extracted before they saw it.

    The second action is the one that matters commercially: sending it to a co
    founder or a board member introduces a second qualified contact with a warm
    referral already attached.
    """
    return f"""<div class="cta">
<h2>Next</h2>
<p>
  <a class="btn" href="#book">Book a ten minute call</a>
  <a class="btn ghost" href="#email">Email me a copy</a>
  <a class="btn ghost" href="#share">Send to my co-founder or board</a>
</p>
<p class="sources">Supplying an address is optional and it is only ever used for what
you asked for. You have already read the report; nothing is held back behind the
form.</p>
</div>"""


def render_delivered(r, audience="founder", context="self_serve"):
    """
    Ordered for the person receiving it.

    The first version opened with the tool's limitations, then recited the
    reader's own website back at them, put the gaps two screens down, and left
    the offer until after a list of things it could not find. It also never said
    who sent it, which for an unsolicited document about somebody's company is
    their first question.

    Order now: who this is from, the gaps, the offer, then the caveats and the
    working for anyone who wants to check it.

    `audience` is a real distinction rather than a setting. The list of claims
    the system considered and discarded is internal: to the person it is about,
    "we also wondered whether you had no commercial leadership but decided
    against it" is unsettling rather than reassuring.
    """
    ev = r.get("evidence", {})
    gaps = r.get("gaps", [])

    # Lead with what is best evidenced. config.yml specified this ordering and
    # nothing implemented it, so an open question could appear above a finding.
    _rank = {"high": 0, "medium": 1, "low": 2}
    gaps = sorted(gaps, key=lambda g: _rank.get(g.get("confidence"), 3))

    n = len(gaps)
    if n == 0:
        strap = "We could not evidence an advisory gap from your public footprint."
    elif n == 1:
        strap = "One senior advisory gap, with the evidence behind it."
    else:
        strap = f"{n} senior advisory gaps, with the evidence behind each."

    out = [header(r, strap, audience)]

    out.append(intro_block(context, r.get("company_name")))

    if not gaps:
        out.append("""<h2>We could not evidence a gap</h2>
<div class="panel">
<p class="big">Every candidate we considered was either contradicted by something on
your site, or rested on an absence rather than evidence. So we are not naming one.</p>
<p>That is a real result rather than a blank. A system like this can always produce
three plausible gaps for anybody, and one that does is telling you about its template
rather than about your company.</p>
<p style="margin-bottom:0">What it does mean is that your public footprint is not
showing the seams. Those usually sit where a website cannot reach: who actually owns
revenue, what decision keeps getting deferred, which hire you have tried twice and got
wrong. Ten minutes covers all three.</p>
</div>""")

    if gaps:
        out.append("<h2>Where the gaps are</h2>")
        for i, g in enumerate(gaps, 1):
            conf = g.get("confidence", "low")
            label = {
                "high": "Confidence: well evidenced",
                "medium": "Confidence: evidenced",
                "low": "Confidence: open question",
            }[conf]
            out.append('<div class="gap">')
            if i == 1 and len(gaps) > 1:
                out.append('<p class="lead-tag">Where we would start</p>')
            out.append(
                f'<div class="gap-head"><h3><span class="num">{i}.</span> {e(g.get("name"))}</h3>'
                f'<span class="tag {conf}">{e(label)}</span></div>'
            )
            out.append(field("What this covers", e(g.get("covers"))))

            if g.get("quoted_evidence"):
                src = g.get("source_url") or ""
                out.append(
                    '<div class="ev"><strong class="label">The evidence this rests on</strong><br>'
                    f"{e(g['quoted_evidence'])}"
                    + (f'<br><cite>Source: <a href="{e(src)}">{e(src)}</a></cite>' if src else "")
                    + "</div>"
                )

            if g.get("cap_reason"):
                out.append(f'<div class="note">{e(g["cap_reason"])}</div>')

            if g.get("unfilled_six_months"):
                out.append(field("If this stays unfilled for six months",
                                 e(g["unfilled_six_months"])))
            if g.get("profile"):
                cta = (load_offer().get("per_gap_cta") or "").strip()
                val = e(g["profile"])
                if cta:
                    val += f'<br><span class="gap-cta">{e(cta)}</span>'
                out.append(answer_field("Who fills it", val))
            fq = g.get("first_questions") or []
            if fq:
                out.append(field(
                    "Three questions for the first twenty minutes",
                    "<ul>" + "".join(f"<li>{e(q)}</li>" for q in fq) + "</ul>",
                ))
            out.append("</div>")

    # internal working, never shown to the subject
    drops = [d for d in (r.get("demotions") or []) if d.get("action") == "drop"]
    if drops and audience == "internal":
        out.append("<h2>Claims we tested and discarded</h2>")
        out.append(
            "<p>A second model reviewed every candidate gap and tried to disprove it "
            "from the same evidence. These did not survive.</p>"
        )
        out.append('<div class="panel">')
        for d in drops:
            out.append(field(
                d.get("archetype_id"),
                "Discarded. Contradicted by: " + e(d.get("contradicting_evidence")),
            ))
        out.append("</div>")

    # the offer, directly after the problem rather than three sections later
    out.append(offer_block(gaps))
    out.append(capture_block(r))

    # caveats and working, for anyone who wants to check it
    oq = [q for q in (r.get("open_questions") or []) if q][:3]
    if oq:
        out.append("<h2>What we would need to ask you</h2>")
        out.append('<div class="panel"><ul>'
                   + "".join(f"<li>{e(x)}</li>" for x in oq) + "</ul></div>")

    nv = (r.get("not_visible") or ev.get("not_visible") or [])[:5]
    if nv:
        out.append('<div class="panel" style="margin-top:14px">' + field(
            "Things your site did not tell us",
            "<ul>" + "".join(f"<li>{e(x)}</li>" for x in nv) + "</ul>",
        ) + "</div>")

    unrendered = r.get("unrendered_pages") or []
    if unrendered:
        word = "page" if len(unrendered) == 1 else "pages"
        out.append(
            '<div class="note"><strong>Some of your site we could not read.</strong> '
            + e(str(len(unrendered))) + f" {word} build content with scripts we do not "
            "run. Nothing above rests on something appearing to be missing from "
            "those pages.</div>"
        )

    out.append(provenance(ev))
    out.append(feedback_block(r))
    out.append(method_footer())
    return shell(f"Leadership gaps: {r.get('company_name')}", "".join(out))


def render_refused(r, audience="founder", context="self_serve"):
    """
    A refusal is still a document somebody reads about their own company, so it
    should be useful to them. The first version told them our evidence field count
    and that we monitor our refusal rate for drift. That is a note to Connectd
    wearing a founder's report as a disguise.
    """
    out = [header(r, "We stopped rather than guess.", audience)]

    out.append("<h2>Why there is no report here</h2>")
    out.append(
        '<p class="big">Your website did not show us enough about who runs the company '
        "for us to say anything useful about it. We would rather tell you that than "
        "invent something that sounds insightful.</p>"
    )
    out.append(
        "<p>That is not a criticism of the site. Plenty of good companies keep their "
        "team off it, and plenty of sites build that page in a way our reader cannot "
        "follow. Either way, guessing from what we could not see would produce a "
        "confident answer with nothing behind it.</p>"
    )

    out.append("<h2>The questions a website cannot answer</h2>")
    out.append("""<div class="panel"><ul>
<li>Who owns revenue today, and is that the same person who owns the product</li>
<li>Who would you call first if the next six months went better than planned</li>
<li>What decision are you putting off because nobody in the room has done it before</li>
<li>Which of your investors or advisors do you actually ring</li>
</ul>
<p style="margin-bottom:0">Ten minutes on those four gets further than any amount of
reading your website.</p></div>""")

    out.append("""<h2>What we can still do</h2>
<div class="panel">
<p style="margin-bottom:0">Connectd places up to three senior operators with early stage
companies, pro bono, for three to six months. Working out which three is a conversation,
and it does not depend on what your website happens to show.</p>
</div>""")

    if audience == "internal":
        out.append("<h2>Internal</h2>")
        out.append('<div class="panel">')
        out.append(field("Refusal reason", e(r.get("refusal_reason"))))
        out.append(field("Evidence completeness", e(r.get("evidence_completeness"))))
        out.append(field("Why this matters", (
            "Refusal rate is a monitored guardrail. It is watched for drifting towards "
            "zero, because a diagnostic that stops refusing has learned to guess."
        )))
        out.append("</div>")

    out.append('<div class="cta"><p><a class="btn" href="#book">Book the ten minute call</a></p></div>')
    out.append(method_footer())
    return shell(f"Not enough to go on: {r.get('company_name')}", "".join(out))


def render_out_of_icp(r, audience="founder", context="self_serve"):
    """
    Telling somebody they are "outside the profile" and quoting the config line
    that excluded them is a rejection letter. The same fact can be delivered as a
    compliment, because it usually is one: they are past the stage where this
    offer helps.
    """
    out = [header(r, "You are past the point this is built for.", audience)]

    out.append("<h2>Why there is no report here</h2>")
    out.append(
        '<p class="big">This diagnostic is built for companies too early to afford the '
        "senior people they need. From the outside, you look past that.</p>"
    )
    out.append(
        "<p>We could produce three gaps for you. Any system like this can produce three "
        "gaps for anyone. It would mean picking them to fill a template rather than "
        "because the evidence pointed at them, and that is not worth your time or ours.</p>"
    )
    out.append(
        "<p>If we have read that wrong, and it does happen from the outside, a short "
        "conversation will sort it out faster than the website will.</p>"
    )

    if audience == "internal":
        out.append("<h2>Internal</h2>")
        out.append('<div class="panel">')
        for reason in r.get("icp_reasons", []):
            out.append(field("Screen", e(reason)))
        out.append(field("Why this matters", (
            "A funnel that reports on everything it is handed does not have an ideal "
            "customer profile. It has a preference."
        )))
        out.append("</div>")

    out.append('<div class="cta"><p><a class="btn" href="#book">Tell us if we read it wrong</a></p></div>')
    out.append(method_footer())
    return shell(f"Not the right fit: {r.get('company_name')}", "".join(out))


def render_error(r):
    out = [header(r, "This analysis did not complete.")]
    out.append("<h2>What happened</h2>")
    out.append(f'<p class="big">{e(r.get("message"))}</p>')
    out.append('<div class="panel">' + field("Technical detail", e(r.get("error"))) + "</div>")
    out.append(
        "<p>An empty result is not the same as a clean result. Showing you nothing and "
        "letting it read as no gaps found would be the more comfortable failure and the "
        "more damaging one, so the system reports the failure instead.</p>"
    )
    out.append(method_footer())
    return shell("Did not complete", "".join(out))


RENDERERS = {
    "delivered": render_delivered,
    "refused": render_refused,
    "out_of_icp": render_out_of_icp,
    "error": render_error,
}


def render(report, audience="founder", context="self_serve"):
    fn = RENDERERS.get(report.get("outcome"))
    if fn in (render_delivered, render_refused, render_out_of_icp):
        return fn(report, audience=audience, context=context)
    if not fn:
        return render_error(
            {
                **report,
                "message": "This run did not produce a result.",
                "error": f"outcome was '{report.get('outcome')}'",
            }
        )
    return fn(report)


def main():
    ap = argparse.ArgumentParser(description="Render a diagnostic run to HTML")
    ap.add_argument("runs", nargs="+", help="run JSON files")
    ap.add_argument("--out", default="samples", help="output directory")
    ap.add_argument(
        "--context",
        choices=["self_serve", "shared", "outbound"],
        default="self_serve",
        help="how the reader arrived, which decides the opening",
    )
    ap.add_argument(
        "--audience",
        choices=["founder", "internal"],
        default="founder",
        help="founder omits the discarded-claims working; internal includes it",
    )
    args = ap.parse_args()

    outdir = ROOT / args.out
    outdir.mkdir(exist_ok=True)

    for path in args.runs:
        p = Path(path)
        if not p.exists():
            print(f"skip, not found: {p}")
            continue
        report = json.loads(p.read_text(encoding="utf-8"))
        stem = report.get("slug") or report.get("run_id") or p.stem
        suffix = "-internal" if args.audience == "internal" else ""
        target = outdir / f"{stem}{suffix}.html"
        target.write_text(
            render(report, audience=args.audience, context=args.context), encoding="utf-8"
        )
        print(f"{report.get('outcome'):<12} -> {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
