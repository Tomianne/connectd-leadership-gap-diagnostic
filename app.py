#!/usr/bin/env python3
"""
The front door.

Live by default. Paste a startup's URL, get a real report in about ninety
seconds, with no key and no signup.

Running somebody else's API key on a public page is normally a bad idea, so the
spend is bounded three ways rather than trusted:

  1. The key deployed here is a separate OpenRouter key with its own hard credit
     limit. When that limit is reached it stops working and nothing else is
     affected. The blast radius is the cap, not an account balance.
  2. The app checks remaining credit before each run and refuses rather than
     failing part way, so a reviewer never sees a half finished report.
  3. A per session run cap stops one visitor consuming the budget alone.

Remaining budget is shown on the page. That is deliberate: a tool that spends
money per use should say so, and cost per run is the number that decides whether
something like this scales.

Run locally:   streamlit run app.py
"""

import json
import urllib.error
import urllib.request
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent

# Enough headroom that a run cannot start and then run out part way through.
MIN_CREDIT_TO_START = 0.35
SESSION_RUN_CAP = 4

st.set_page_config(page_title="Leadership Gap Diagnostic", page_icon="•", layout="centered")

st.markdown(
    """
<style>
  .stApp { background: #ffffff; }
  .block-container { max-width: 820px; padding-top: 2.2rem; }
  h1, h2, h3 { letter-spacing: -.015em; }
  .eyebrow { font-size: 11px; letter-spacing: .14em; text-transform: uppercase;
             color: #8b909c; margin-bottom: .5rem; }
  .outcome { display: inline-block; font-size: 11px; letter-spacing: .09em;
             text-transform: uppercase; padding: 4px 9px; border-radius: 3px;
             border: 1px solid currentColor; font-weight: 640; }
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
    "Ridelogix, urban logistics, claims discarded by the adversary": "ridelogix",
    "Chatterbox, screened out as outside the profile": "chatterbox",
    "Rule, refused because there was too little to work from": "rule-money",
}

OUTCOME_BLURB = {
    "delivered": "Up to three gaps, each carrying the evidence it rests on.",
    "refused": "The system declined to diagnose rather than guess.",
    "out_of_icp": "Screened out before any judgement was made about gaps.",
    "error": "The analysis did not complete, and says so rather than showing an empty result.",
}


def hosted_key():
    """The capped key, if one is configured for this deployment."""
    try:
        return st.secrets.get("OPENROUTER_API_KEY")
    except Exception:  # noqa: BLE001
        return None


@st.cache_data(ttl=60, show_spinner=False)
def credit_remaining(key):
    """
    What is left on this key. Cached briefly so a page refresh is not a request.

    Returns None when the key carries no limit, which means it is running
    uncapped and the page should not imply a bound that does not exist.
    """
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
    p = ROOT / "samples" / f"{slug}.html"
    if not p.exists():
        return None
    t = p.read_text(encoding="utf-8")
    return t.split("<body>")[1].split("</body>")[0] if "<body>" in t else t


def show_report(report, body_html=None):
    outcome = report.get("outcome", "error")
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
            f'<div class="note"><strong>The adversarial pass discarded {len(drops)} '
            "claim(s) on this run.</strong> A second model was given the evidence and the "
            "candidate gaps and asked to disprove them, and these did not survive.</div>",
            unsafe_allow_html=True,
        )

    if body_html:
        st.components.v1.html(
            f'<div style="background:#fff">{body_html}</div>', height=900, scrolling=True
        )


st.markdown('<p class="eyebrow">Leadership Gap Diagnostic</p>', unsafe_allow_html=True)
st.title("Which three senior people does this startup actually need?")
st.write(
    "Give it a startup's website. It reads the public footprint and names up to three "
    "senior advisory gaps, with the evidence behind each one and an explicit record of "
    "what it could not see. It names fewer than three when the evidence supports fewer, "
    "and it refuses outright when there is too little to work from."
)

key = hosted_key()
remaining = credit_remaining(key) if key else None
runs_used = st.session_state.get("runs_used", 0)

budget_ok = key is not None and (remaining is None or remaining >= MIN_CREDIT_TO_START)
session_ok = runs_used < SESSION_RUN_CAP

tab_live, tab_demo = st.tabs(["Run it on any startup", "Four runs I already did"])

# ---------------------------------------------------------------------------
with tab_live:
    if not key:
        st.info(
            "This deployment has no key configured, so live runs are off. The four "
            "completed runs in the next tab are real and need nothing."
        )
    elif not budget_ok:
        st.warning(
            "The demo budget for this page has run out. Everything in the next tab is "
            "a real run and still works, and the repository has the code if you want "
            "to run it on your own key."
        )
    elif not session_ok:
        st.warning(
            f"That is {SESSION_RUN_CAP} runs this session, which is the per visitor cap. "
            "Reload to reset it, or clone the repo and run it on your own key."
        )
    else:
        bits = []
        if remaining is not None:
            bits.append(f"about {max(int(remaining / 0.12), 0)} runs left in the demo budget")
        bits.append(f"{SESSION_RUN_CAP - runs_used} left this session")
        st.caption(
            "Runs on my key, so you need nothing. Three model calls, typically six to "
            "fifteen pence, and the run record below shows what it actually cost. "
            + " &middot; ".join(bits)
        )

        url = st.text_input(
            "Startup website",
            placeholder="https://example.com",
            help="Built for early stage UK companies. It will tell you if a company sits outside that profile.",
        )
        go = st.button("Run the diagnostic", type="primary", disabled=not url)

        if go:
            import os

            os.environ["OPENROUTER_API_KEY"] = str(key)
            import importlib

            import diagnose
            importlib.reload(diagnose)
            import render

            with st.status("Running", expanded=True) as status:
                st.write("Fetching the public footprint")
                try:
                    report = diagnose.run(url.strip(), confirm=False)
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
                st.write(f"Outcome: {report.get('outcome')}  |  cost ${cost:.4f}")
                status.update(label=f"Done, {report.get('outcome')}", state="complete")

            body = render.render(report).split("<body>")[1].split("</body>")[0]
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
        "I would look at first."
    )
    label = st.selectbox("Pick a run", list(SAMPLES.keys()))
    slug = SAMPLES[label]
    report = load_run(slug)
    if not report:
        st.error(f"Sample {slug} is missing from samples/.")
    else:
        show_report(report, load_html(slug))
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
st.caption(
    "Built as a task for Connectd, September 2026. The gap taxonomy and the "
    "qualification rules are inferred from Connectd's public offer, not from their "
    "bench or their CRM, and both live in editable config files for that reason. "
    "Write up and source: github.com/Tomianne/connectd-leadership-gap-diagnostic"
)
