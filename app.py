#!/usr/bin/env python3
"""
The front door.

Two modes, and the split is a deliberate cost decision rather than a convenience.

  Demo mode is the default. It serves the four pre computed runs that are committed
  to samples/. It needs no API key, costs nothing, and cannot fail in front of a
  reviewer. A live link that errors on someone's first click is worse than no live
  link.

  Live mode asks the reviewer to paste their own OpenRouter key. A public app wired
  to the author's key is an open invitation to spend the author's money, and
  choosing not to leave that surface open is part of the job rather than a caveat
  about it.

Run locally:   streamlit run app.py
"""

import json
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent

st.set_page_config(
    page_title="Leadership Gap Diagnostic",
    page_icon="•",
    layout="centered",
)

st.markdown(
    """
<style>
  .stApp { background: #ffffff; }
  .block-container { max-width: 800px; padding-top: 2.2rem; }
  h1, h2, h3 { letter-spacing: -.015em; }
  .eyebrow {
    font-size: 11px; letter-spacing: .14em; text-transform: uppercase;
    color: #8b909c; margin-bottom: .5rem;
  }
  .outcome {
    display: inline-block; font-size: 11px; letter-spacing: .09em;
    text-transform: uppercase; padding: 4px 9px; border-radius: 3px;
    border: 1px solid currentColor; font-weight: 640;
  }
  .delivered { color: #1f6b3f; }
  .refused { color: #8a6100; }
  .out_of_icp { color: #b4532a; }
  .error { color: #a02020; }
  .note { background: #f7f7f5; border-radius: 8px; padding: 14px 16px; font-size: 14.5px; }
</style>
""",
    unsafe_allow_html=True,
)

SAMPLES = {
    "Anemo Labs, London deep tech, raised 700k pre-seed": "anemo-labs",
    "Ridelogix, urban logistics, two claims discarded": "ridelogix",
    "Chatterbox, screened out as outside the profile": "chatterbox",
    "Rule, refused because the leadership was not visible": "rule-money",
}

OUTCOME_BLURB = {
    "delivered": "Up to three gaps, each carrying the evidence it rests on.",
    "refused": "The system declined to diagnose rather than guess.",
    "out_of_icp": "Screened out before any judgement was made about gaps.",
    "error": "The analysis did not complete, and says so rather than showing an empty result.",
}


def load_run(slug):
    """
    Demo records live in samples/ alongside the rendered HTML, not in runs/.
    runs/ is gitignored for ad hoc runs, so reading demo data from there would
    work locally and break the moment the app is deployed.
    """
    p = ROOT / "samples" / f"{slug}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def load_html(slug):
    p = ROOT / "samples" / f"{slug}.html"
    if not p.exists():
        return None
    t = p.read_text(encoding="utf-8")
    return t.split("<body>")[1].split("</body>")[0] if "<body>" in t else t


st.markdown('<p class="eyebrow">Leadership Gap Diagnostic</p>', unsafe_allow_html=True)
st.title("Which three senior people does this startup actually need?")
st.write(
    "Give it a startup's website. It reads the public footprint and names up to three "
    "senior advisory gaps, with the evidence behind each one and an explicit record of "
    "what it could not see. It names fewer than three when the evidence supports fewer, "
    "and it refuses outright when it cannot see the leadership at all."
)

mode = st.radio(
    "Mode",
    ["Demo, four real runs", "Live, bring your own API key"],
    horizontal=True,
    label_visibility="collapsed",
)

st.divider()

# ---------------------------------------------------------------------------
# demo mode
# ---------------------------------------------------------------------------
if mode.startswith("Demo"):
    st.caption(
        "Four real UK companies, run on 24 September 2026. Two produced reports, one "
        "was screened out, one was refused. Nothing here is invented and no API key is "
        "needed."
    )
    label = st.selectbox("Pick a run", list(SAMPLES.keys()))
    slug = SAMPLES[label]
    report = load_run(slug)

    if not report:
        st.error(f"Sample {slug} is missing from samples/.")
    else:
        outcome = report.get("outcome", "error")
        c1, c2 = st.columns([1, 3])
        with c1:
            st.markdown(
                f'<span class="outcome {outcome}">{outcome.replace("_", " ")}</span>',
                unsafe_allow_html=True,
            )
        with c2:
            st.caption(OUTCOME_BLURB.get(outcome, ""))

        drops = [d for d in (report.get("demotions") or []) if d.get("action") == "drop"]
        if drops:
            st.markdown(
                '<div class="note"><strong>The adversarial pass discarded '
                f'{len(drops)} claim(s) on this run.</strong> A second model was given the '
                "evidence and the candidate gaps, and asked to disprove them. Both "
                "discarded claims cited a named enterprise customer as proof the company "
                "could not sell to enterprises, which is evidence pointing the other way. "
                "Scroll to the end of the report to see them.</div>",
                unsafe_allow_html=True,
            )

        html_body = load_html(slug)
        if html_body:
            st.components.v1.html(
                f'<div style="background:#fff">{html_body}</div>',
                height=900,
                scrolling=True,
            )
        else:
            st.warning("Rendered sample missing. Run: python render.py runs/*.json")

        with st.expander("The machine readable record for this run"):
            st.json(
                {
                    k: v
                    for k, v in report.items()
                    if k in (
                        "run_id", "outcome", "evidence_completeness", "taxonomy_version",
                        "demotions", "icp_reasons", "refusal_reason",
                    )
                }
            )

# ---------------------------------------------------------------------------
# live mode
# ---------------------------------------------------------------------------
else:
    st.caption(
        "Live mode uses your own OpenRouter key, not the author's. A public app wired "
        "to one person's key is an open invitation to spend their money. Three model "
        "calls per run, typically a few pence."
    )
    key = st.text_input("Your OpenRouter API key", type="password", placeholder="sk-or-...")
    url = st.text_input("Startup website", placeholder="https://example.com")

    if st.button("Run the diagnostic", type="primary", disabled=not (key and url)):
        import os

        os.environ["OPENROUTER_API_KEY"] = key.strip()
        import importlib

        import diagnose
        importlib.reload(diagnose)
        import render

        with st.status("Running", expanded=True) as status:
            st.write("Fetching the public footprint")
            try:
                report = diagnose.run(url.strip(), confirm=False)
            except SystemExit as e:
                status.update(label="Stopped", state="error")
                st.error(str(e))
                st.stop()

            outcome = report.get("outcome")
            st.write(f"Outcome: {outcome}")
            status.update(label=f"Done, {outcome}", state="complete")

        st.markdown(
            f'<span class="outcome {outcome}">{str(outcome).replace("_", " ")}</span>',
            unsafe_allow_html=True,
        )
        body = render.render(report).split("<body>")[1].split("</body>")[0]
        st.components.v1.html(f'<div style="background:#fff">{body}</div>', height=900, scrolling=True)

        st.download_button(
            "Download the run record",
            data=json.dumps(report, indent=2),
            file_name=f"{report.get('slug') or report.get('run_id')}.json",
            mime="application/json",
        )

st.divider()
st.caption(
    "Built as a task for Connectd, September 2026. The gap taxonomy and the "
    "qualification rules are inferred from Connectd's public offer, not from their "
    "bench or their CRM, and both live in editable config files for exactly that "
    "reason. Full write up and source in the repository."
)
