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

import render as _render

st.markdown(
    "<style>" + _render.CSS + "</style>", unsafe_allow_html=True
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
      background: #16181d !important; border: none !important;
      color: #ffffff !important; font-weight: 600; }
  div.stButton > button[kind="primary"] p,
  div.stButton > button[kind="primary"] div { color: #ffffff !important; }
  div.stButton > button[kind="primary"]:hover { background: #000 !important; }
  div.stButton > button[kind="primary"]:disabled,
  div.stButton > button[kind="primary"]:disabled p {
      background: #e4e4e0 !important; color: #8b909c !important; }
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


def actions(report, key_prefix=""):
    """
    The three calls to action, doing what they say.

    They were anchors going nowhere for the whole build, while deliver.py sat
    there sending real transactional email with consent logging and address
    rejection. A capture step that captures nothing is the worst kind of gap,
    because the interface claims a mechanism the system actually has.

    Rendered as Streamlit controls rather than HTML because an anchor inside
    injected markup cannot trigger a callback.
    """
    import render as _r

    booking = (_r.load_offer().get("booking_url") or "").strip()
    # Both the call site and the run identify the widgets. The previous version
    # was `run_id or key_prefix`, so key_prefix was never used when a run_id
    # existed, and two call sites showing the same report would have produced
    # identical widget keys and shared each other's state. That is the most
    # likely cause of the two address fields colliding.
    rid = f"{key_prefix or 'live'}_{report.get('run_id') or 'none'}"
    company = report.get("company_name") or ""

    st.markdown("---")
    st.markdown("##### Next")

    if booking:
        st.link_button("Book a ten minute call", booking, use_container_width=False)

    # One form, one address. Two forms side by side had their session state
    # collide, so typing an address into one populated the other. The deeper
    # problem was that two forms and four fields was more interface than a
    # single decision needs: the only thing that varies is who it goes to.
    with st.form(f"send_{rid}", border=True):
        who = st.radio(
            "Send the report to",
            ["Me", "My co-founder or board"],
            horizontal=True,
            key=f"who_{rid}",
        )
        share = who != "Me"

        addr = st.text_input(
            "Email address",
            key=f"addr_{rid}",
            placeholder="them@company.com" if share else "you@company.com",
        )

        note = ""
        if share:
            note = st.text_input(
                "A line from you, optional",
                key=f"note_{rid}",
                placeholder="Thought this was worth a look",
            )

        consent = st.checkbox(
            "Connectd may follow up about this", key=f"consent_{rid}"
        )

        if st.form_submit_button("Send the report", type="primary"):
            _send(report, addr, share=share, note=note, consent=consent)

    # The feedback question. Weakest of the three label sources the loop uses, and
    # the only one available before anybody books anything.
    st.markdown("**Did we get this right?**")
    f1, f2, f3 = st.columns(3)
    for col, label, val in [
        (f1, "Yes, that is fair", "yes"),
        (f2, "Partly", "partly"),
        (f3, "No, we have these covered", "no"),
    ]:
        with col:
            if st.button(label, key=f"fb_{val}_{rid}", use_container_width=True):
                _log_feedback(report, val)
                st.success("Logged. A no is the most useful answer we get.")


def review_gate(report, key_prefix=""):
    """
    Accept, edit or reject each gap before a brief reaches an exec.

    Per gap rather than per report, because a report with one good gap and one
    bad one is the normal case, and a whole-report verdict throws away exactly
    the distinction the loop needs.

    Only shown on the internal view. A founder should not be asked to audit the
    system that just read their website.
    """
    gaps = report.get("gaps") or []
    if not gaps:
        return

    rid = f"{key_prefix or 'live'}_{report.get('run_id') or 'none'}"

    st.markdown("---")
    st.markdown("##### Review before this becomes a brief")
    st.caption(
        "The one per lead human gate. It sits here because this is the first point "
        "where a wrong answer costs a senior person six months rather than a few pence "
        "of API time. Each verdict is written against the run and is the strongest "
        "label the optimisation loop gets."
    )

    with st.form(f"review_{rid}", border=True):
        verdicts = {}
        for i, g in enumerate(gaps, 1):
            st.markdown(f"**{i}. {g.get('name')}**  \n*{g.get('quoted_evidence', '')[:120]}*")
            verdicts[g.get("archetype_id")] = st.radio(
                "verdict",
                ["Accept", "Edit", "Reject"],
                horizontal=True,
                key=f"v_{i}_{rid}",
                label_visibility="collapsed",
            )
            if i < len(gaps):
                st.markdown("")

        reason = st.text_input(
            "Why, if you edited or rejected anything",
            key=f"why_{rid}",
            placeholder="The evidence did not support it, we have nobody for this, wrong read of the stage",
        )

        if st.form_submit_button("Record the review", type="primary"):
            _log_review(report, verdicts, reason)
            rej = [k for k, v in verdicts.items() if v == "Reject"]
            if rej:
                st.warning(
                    f"Recorded. {len(rej)} rejected, which is the useful signal. "
                    "Archetypes named often and rejected often are what the slow loop "
                    "looks for when it proposes taxonomy changes."
                )
            else:
                st.success("Recorded. All accepted, so this is ready to route to the bench.")


def _log_review(report, verdicts, reason):
    """
    One row per review. The column the loop calls its strongest label, which had
    been specified everywhere and collected nothing.
    """
    import csv as _csv
    import datetime as _dt

    p = ROOT / "reviews.csv"
    exists = p.exists()
    try:
        with open(p, "a", newline="", encoding="utf-8") as f:
            w = _csv.writer(f)
            if not exists:
                w.writerow(["at", "run_id", "company", "archetype", "verdict", "reason"])
            now = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
            for archetype, verdict in verdicts.items():
                w.writerow([
                    now, report.get("run_id"), report.get("company_name"),
                    archetype, verdict.lower(), reason,
                ])
    except OSError:
        pass


def _send(report, addr, share=False, note=None, consent=False):
    import deliver
    import render as _r

    if not addr:
        st.warning("Enter an address first.")
        return
    if not deliver.valid_email(addr):
        st.warning("That address does not look right. Nothing was sent.")
        return

    body = _r.render(report, context="shared" if share else "self_serve")
    body = body.split("<body>")[1].split("</body>")[0]

    with st.spinner("Sending"):
        ok, msg = deliver.email_report(
            report, addr.strip(), body, share=share, note=note,
            consent_followup=consent,
        )
    (st.success if ok else st.warning)(msg)


def _log_feedback(report, value):
    """One row per answer, against the run, which is what the loop reads."""
    import csv as _csv
    import datetime as _dt

    p = ROOT / "feedback.csv"
    exists = p.exists()
    try:
        with open(p, "a", newline="", encoding="utf-8") as f:
            w = _csv.writer(f)
            if not exists:
                w.writerow(["at", "run_id", "company", "rating"])
            w.writerow([
                _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
                report.get("run_id"), report.get("company_name"), value,
            ])
    except OSError:
        pass  # a read only filesystem must not break the page


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
        # Straight into the page, not into an iframe. The stylesheet is already
        # loaded above, scoped under .lgd, so this inherits the page's width,
        # scroll and font resolution instead of fighting them.
        st.markdown(f'<div class="lgd">{body_html}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
st.markdown('<p class="eyebrow">Leadership Gap Diagnostic</p>', unsafe_allow_html=True)
st.title("Which senior people does your startup actually need?")
st.markdown(
    '<p class="lede">Put in your website. It names up to three senior advisory gaps, '
    "each with the evidence behind it, in about ninety seconds.</p>",
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

# ---------------------------------------------------------------------------
with st.container():
    if not key:
        st.info(
            "This deployment has no key configured, so live runs are off. The write up "
            f"carries four real runs end to end: {WRITEUP}"
        )
    elif not budget_ok:
        st.warning(
            "The shared budget for this page has run out. The write up carries four "
            f"real runs end to end ({WRITEUP}), and the code is on GitHub if you want "
            f"to run it on your own key ({REPO})."
        )
    elif not session_ok:
        st.warning(
            f"That is {SESSION_RUN_CAP} runs this session, which is the per visitor cap. "
            "Reload to reset it, or clone the repo and run it yourself."
        )
    else:
        default_url = st.session_state.get("prefill", "")
        url = st.text_input(
            "Your website",
            value=default_url,
            placeholder="https://yourcompany.com",
            label_visibility="collapsed",
        )

        b1, b2 = st.columns([1, 2])
        with b1:
            go = st.button("Run the diagnostic", type="primary", disabled=not url, use_container_width=True)
        with b2:
            # No run counts and no budget figures. They are operator telemetry, and a
            # customer facing page that shows the founder how much credit is left is
            # asking them to think about the operator's costs instead of their own
            # company. The caps still apply, they are just not narrated.
            st.caption("Free, and nothing to sign up for.")

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
            actions(report)

            with st.expander("What Connectd sees: the review gate"):
                review_gate(report)

            st.download_button(
                "Download the run record",
                data=json.dumps(report, indent=2),
                file_name=f"{report.get('slug') or report.get('run_id')}.json",
                mime="application/json",
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
