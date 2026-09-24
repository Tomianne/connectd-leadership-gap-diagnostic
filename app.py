#!/usr/bin/env python3
"""
The front door.

Live by default. Paste a startup's URL, get a real report in about ninety
seconds, with no key and no signup.

Two things drove the layout, both from watching it as the person arriving rather
than the person who built it.

A run takes 75 to 150 seconds, which is long enough that an unexplained spinner
loses people. So the wait is narrated: every stage reports what it is doing, and
the interesting part, a second model trying to disprove the first, is visible
while it happens rather than buried in the result.

And a refusal has to be framed before it happens. Told up front that the system
can decline, a reviewer reads that as rigour. Discovered cold at the end of a
ninety second wait, it reads as a broken tool.

Spend is bounded three ways rather than trusted: a separate OpenRouter key with
its own hard credit limit, a pre-flight balance check so a run cannot die part
way, and a per session cap.

Run locally:   streamlit run app.py
"""

import json
import urllib.error
import urllib.request
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent
REPO = "https://github.com/Tomianne/connectd-leadership-gap-diagnostic"
WRITEUP = "https://tomianne.github.io/connectd-leadership-gap-diagnostic/"

MIN_CREDIT_TO_START = 0.35
SESSION_RUN_CAP = 4

st.set_page_config(
    page_title="Leadership Gap Diagnostic",
    page_icon="•",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
  .stApp { background: #ffffff;
           font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI",
                        Helvetica, Arial, sans-serif; }
  .stApp, .stApp p, .stApp li, .stApp label, .stApp div[data-testid] {
           font-family: inherit; }
  .block-container { max-width: 840px; padding-top: 2rem; padding-bottom: 4rem; }
  h1 { font-size: 2.15rem !important; line-height: 1.15 !important;
       letter-spacing: -.022em !important; font-weight: 680 !important;
       margin-bottom: .4rem !important; }
  .lede { font-size: 1.06rem; color: #565b66; line-height: 1.55; margin: 0 0 1.4rem; }
  .eyebrow { font-size: 10.5px; letter-spacing: .16em; text-transform: uppercase;
             color: #8b909c; margin: 0 0 .7rem; font-weight: 600; }

  /* the three outcomes, stated before they happen */
  .outcomes { display: flex; gap: 10px; margin: 0 0 1.5rem; flex-wrap: wrap; }
  .oc { flex: 1 1 200px; border: 1px solid #e4e4e0; border-radius: 9px;
        padding: 13px 15px; font-size: 13.5px; color: #565b66; line-height: 1.45; }
  .oc b { display: block; color: #16181d; font-size: 13.5px; margin-bottom: 3px; }
  .oc.a b { color: #1f6b3f; } .oc.b b { color: #b4532a; } .oc.c b { color: #8a6100; }

  .outcome { display: inline-block; font-size: 11px; letter-spacing: .09em;
             text-transform: uppercase; padding: 4px 9px; border-radius: 3px;
             border: 1px solid currentColor; font-weight: 640; }
  .delivered { color: #1f6b3f; }
  .refused { color: #8a6100; }
  .out_of_icp { color: #b4532a; }
  .error { color: #a02020; }
  .note { background: #f7f7f5; border-radius: 8px; padding: 13px 15px;
          font-size: 14px; line-height: 1.5; }
  .foot { font-size: 13px; color: #8b909c; line-height: 1.6; }
  .foot a { color: #b4532a; }

  div.stButton > button[kind="primary"] {
      background: #16181d; border: none; font-weight: 600; }
  div.stButton > button[kind="primary"]:hover { background: #000; }
  div.stButton > button[kind="secondary"] {
      border: 1px solid #e4e4e0; color: #16181d; font-weight: 500;
      background: #fff; font-size: 13.5px; }
  div.stButton > button[kind="secondary"]:hover {
      border-color: #16181d; color: #16181d; }
  [data-testid="stTabs"] button p { font-weight: 600; }

  /* the heading the embedded report no longer carries */
  .rpt-head { border-top: 1px solid #e4e4e0; padding-top: 22px; margin-top: 8px; }
  .rpt-title { font-size: 1.5rem !important; font-weight: 660 !important;
               letter-spacing: -.015em; margin: 0 0 4px !important; color: #16181d; }
  .rpt-meta { font-size: 13px; color: #8b909c; margin: 0 0 14px; word-break: break-all; }
  .rpt-meta a { color: #8b909c; }
  iframe { border: none !important; }
</style>
""",
    unsafe_allow_html=True,
)

SAMPLES = {
    "Anemo Labs, deep tech, produced a report": "anemo-labs",
    "Ridelogix, logistics, two claims were discarded": "ridelogix",
    "Chatterbox, screened out as too late stage": "chatterbox",
    "Rule, refused for having too little to read": "rule-money",
}

TRY_THESE = [
    ("Anemo Labs", "https://anemolabs.com"),
    ("Ridelogix", "https://ridelogix.com"),
    ("Chatterbox", "https://www.chatterbox.io"),
]

OUTCOME_BLURB = {
    "delivered": "Up to three gaps, each carrying the evidence it rests on.",
    "refused": "It declined to diagnose rather than guess.",
    "out_of_icp": "Screened out before any judgement about gaps was made.",
    "error": "The analysis did not complete, and says so rather than showing an empty result.",
}

STEP_LABEL = {
    "fetch": "Reading the site",
    "fetched": "Site read",
    "extract": "Pulling out the facts",
    "extracted": "Evidence collected",
    "classify": "Matching against the archetypes",
    "classified": "Candidates proposed",
    "adversary": "Trying to disprove them",
    "refused": "Declined",
    "out_of_icp": "Screened out",
}


def hosted_key():
    try:
        return st.secrets.get("OPENROUTER_API_KEY")
    except Exception:  # noqa: BLE001
        return None


@st.cache_data(ttl=60, show_spinner=False)
def credit_remaining(key):
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/key", headers={"Authorization": f"Bearer {key}"}
    )
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=15).read().decode()).get("data", {})
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
        return None
    return d.get("limit_remaining")


def load_run(slug):
    p = ROOT / "samples" / f"{slug}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def load_html(slug):
    """
    Render the sample fresh in embed mode rather than reading the standalone
    file. The committed HTML carries its own page header, which duplicates what
    the app has already shown and is what made the report look pasted in.
    """
    report = load_run(slug)
    if not report:
        return None
    import render

    return render.render(report, embed=True).split("<body>")[1].split("</body>")[0]


def embed_height(body_html):
    """
    Estimate the rendered height so the report does not scroll inside a page that
    already scrolls. A box with its own scrollbar is the thing that made this read
    as an attachment rather than as part of the page.

    Overshooting a little is fine, the host page just shows white. Undershooting
    reintroduces the scrollbar, so the estimate leans long.
    """
    import re as _re

    text = _re.sub(r"<[^>]+>", " ", body_html or "")
    text = _re.sub(r"\s+", " ", text)
    lines = len(text) / 78          # characters per line at this width
    blocks = body_html.count('class="field"') + body_html.count('class="gap"')
    return int(min(max(lines * 27 + blocks * 26 + 320, 700), 9000))


def show_report(report, body_html=None, key_prefix=""):
    """
    The app supplies the heading that the embedded report no longer carries, so
    the reader gets the company name once rather than twice.
    """
    outcome = report.get("outcome", "error")
    company = report.get("company_name") or report.get("url") or ""
    src = report.get("url") or ""
    when = (report.get("generated_at") or "")[:10]

    st.markdown(
        f'<div class="rpt-head">'
        f'<h3 class="rpt-title">{company}</h3>'
        f'<p class="rpt-meta">Read from <a href="{src}">{src}</a>'
        + (f" on {when}" if when else "")
        + "</p></div>",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([1, 3])
    with c1:
        st.markdown(
            f'<span class="outcome {outcome}">{str(outcome).replace("_", " ")}</span>',
            unsafe_allow_html=True,
        )
    with c2:
        st.caption(OUTCOME_BLURB.get(outcome, ""))

    drops = [d for d in (report.get("demotions") or []) if d.get("action") == "drop"]
    if drops:
        st.markdown(
            f'<div class="note"><b>{len(drops)} claim(s) were discarded on this run.</b> '
            "A second model was given the same evidence and asked to disprove every "
            "candidate gap. These did not survive, so they are not in the report.</div>",
            unsafe_allow_html=True,
        )
        st.write("")

    if body_html:
        doc = f'<div style="background:#fff">{body_html}</div>'
        h = embed_height(body_html)
        # st.components.v1.html is deprecated as of June 2026. Prefer st.iframe
        # where it exists and fall back so this still runs on older versions.
        if hasattr(st, "iframe"):
            st.iframe(srcdoc=doc, height=h, scrolling=False)
        else:
            st.components.v1.html(doc, height=h, scrolling=False)


# ---------------------------------------------------------------------------
st.markdown('<p class="eyebrow">Leadership Gap Diagnostic</p>', unsafe_allow_html=True)
st.title("Which three senior people does this startup actually need?")
st.markdown(
    '<p class="lede">Give it an early stage startup\'s website. It names up to three '
    "senior advisory gaps, each with the evidence behind it, in about ninety seconds.</p>",
    unsafe_allow_html=True,
)

# The three outcomes, stated BEFORE a run. A refusal discovered cold at the end of
# a ninety second wait reads as a broken tool. Announced in advance it reads as
# the judgement it is.
st.markdown(
    """
<div class="outcomes">
  <div class="oc a"><b>It reports</b>Up to three gaps, fewer when the evidence supports fewer.</div>
  <div class="oc b"><b>Or screens you out</b>If you are past the stage this is built for, it says so.</div>
  <div class="oc c"><b>Or refuses</b>If your site shows too little, it declines rather than guessing.</div>
</div>
""",
    unsafe_allow_html=True,
)

key = hosted_key()
remaining = credit_remaining(key) if key else None
runs_used = st.session_state.get("runs_used", 0)
budget_ok = key is not None and (remaining is None or remaining >= MIN_CREDIT_TO_START)
session_ok = runs_used < SESSION_RUN_CAP

tab_live, tab_demo = st.tabs(["Run it now", "See example reports"])

# ---------------------------------------------------------------------------
with tab_live:
    if not key:
        st.info(
            "This deployment has no key configured, so live runs are off. The example "
            "reports in the next tab are real runs and need nothing."
        )
    elif not budget_ok:
        st.warning(
            "The shared budget for this page has run out. The example reports in the "
            "next tab are real and still work, and the code is on GitHub if you want "
            "to run it on your own key."
        )
    elif not session_ok:
        st.warning(
            f"That is {SESSION_RUN_CAP} runs this session, which is the per visitor cap. "
            "Reload to reset it, or clone the repo and run it yourself."
        )
    else:
        default_url = st.session_state.get("prefill", "")
        url = st.text_input(
            "Startup website",
            value=default_url,
            placeholder="https://example.com",
            label_visibility="collapsed",
        )

        b1, b2 = st.columns([1, 2])
        with b1:
            go = st.button("Run the diagnostic", type="primary", disabled=not url, use_container_width=True)
        with b2:
            st.caption(
                f"Free, nothing to sign up for. {max(int(remaining / 0.12), 0) if remaining is not None else '-'} "
                f"runs left in the shared budget, {SESSION_RUN_CAP - runs_used} left this session."
            )

        st.caption("Or try one of these:")
        cols = st.columns(len(TRY_THESE))
        for col, (name, u) in zip(cols, TRY_THESE):
            with col:
                if st.button(name, key=f"try_{name}", use_container_width=True):
                    st.session_state["prefill"] = u
                    st.rerun()

        if go:
            import os

            os.environ["OPENROUTER_API_KEY"] = str(key)
            import importlib

            import diagnose
            importlib.reload(diagnose)
            import render

            with st.status("Reading the site", expanded=True) as status:
                def on_step(stage, detail):
                    label = STEP_LABEL.get(stage)
                    if label:
                        status.update(label=label)
                    if detail:
                        st.write(detail)

                try:
                    report = diagnose.run(url.strip(), confirm=False, on_step=on_step)
                except SystemExit as exc:
                    status.update(label="Stopped", state="error")
                    st.error(str(exc))
                    st.stop()
                except Exception as exc:  # noqa: BLE001
                    status.update(label="Stopped", state="error")
                    st.error(f"That did not complete: {exc}")
                    st.stop()

                st.session_state["runs_used"] = runs_used + 1
                cost = (report.get("run_cost") or {}).get("usd", 0)
                secs = report.get("duration_seconds")
                st.write(
                    f"Done. Cost ${cost:.3f}"
                    + (f", {secs:.0f} seconds" if isinstance(secs, (int, float)) else "")
                )
                status.update(
                    label=f"Done in {secs:.0f}s" if isinstance(secs, (int, float)) else "Done",
                    state="complete",
                    expanded=False,
                )

            st.write("")
            body = render.render(report, embed=True).split("<body>")[1].split("</body>")[0]
            show_report(report, body)

            st.download_button(
                "Download the run record",
                data=json.dumps(report, indent=2),
                file_name=f"{report.get('slug') or report.get('run_id')}.json",
                mime="application/json",
            )

# ---------------------------------------------------------------------------
with tab_demo:
    st.caption(
        "Four real UK companies, run on 24 September 2026. Two produced reports, one "
        "was screened out, one was refused. The two that produced nothing are the ones "
        "worth looking at first, because a diagnostic that only knows how to produce a "
        "diagnosis will produce one whether or not it should."
    )
    label = st.selectbox("Pick a run", list(SAMPLES.keys()), label_visibility="collapsed")
    slug = SAMPLES[label]
    report = load_run(slug)
    if not report:
        st.error(f"Sample {slug} is missing.")
    else:
        show_report(report, load_html(slug), key_prefix="demo")
        with st.expander("The machine readable record for this run"):
            st.json(
                {
                    k: v
                    for k, v in report.items()
                    if k in (
                        "run_id", "outcome", "evidence_completeness", "taxonomy_version",
                        "demotions", "icp_reasons", "refusal_reason", "run_cost",
                        "duration_seconds", "models",
                    )
                }
            )

st.divider()
st.markdown(
    f'<p class="foot">Built as a task for Connectd, September 2026. The gap taxonomy and '
    f"the qualification rules are inferred from Connectd's public offer, not from their "
    f"bench or their CRM, and both live in editable config files for that reason.<br>"
    f'<a href="{WRITEUP}">Read the write up</a> &nbsp;&middot;&nbsp; '
    f'<a href="{REPO}">Read the code</a></p>',
    unsafe_allow_html=True,
)
