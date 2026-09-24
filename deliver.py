#!/usr/bin/env python3
"""
The delivery and capture leg.

The report is shown in full on screen first. The address is asked for afterwards,
for two reasons that are worth being explicit about:

  Commercially, an address given by someone who has just read something useful is
  worth more than one extracted before they saw anything. Value before friction.

  Operationally, it keeps address verification off the critical path. The only
  addresses this system ever sends to are ones a person typed in about their own
  company, which is a completely different risk class from an inferred address.
  A previous campaign elsewhere was pulled after guessed addresses on catch all
  domains produced a mass hard bounce, and the rule that came out of it is that a
  domain resolving in DNS is not a mailbox existing.

The second action, sending the report to a co founder or a board member, is the
one that matters most commercially. It introduces a second qualified contact with
a warm referral already attached, which no amount of outbound buys.

Every capture is logged with explicit, separable consent and a timestamp.
"""

import csv
import datetime as dt
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
CAPTURES = ROOT / "captures.csv"

CAPTURE_COLUMNS = [
    "captured_at",
    "run_id",
    "company_name",
    "email",
    "action",              # copy_to_self | share_onward
    "consent_report_copy",
    "consent_followup",    # separable, and defaults to false
    "recipient_note",
    "send_status",
]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]{2,}$")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)


def load_env():
    """
    Secrets first, then .env.

    On Streamlit Community Cloud there is no .env file, so without this the send
    leg silently has no key in exactly the deployment where someone would use it.
    """
    try:
        import streamlit as st

        if getattr(st, "secrets", None) and "BREVO_API_KEY" in st.secrets:
            return {
                "BREVO_API_KEY": st.secrets.get("BREVO_API_KEY"),
                "BREVO_SENDER_EMAIL": st.secrets.get("BREVO_SENDER_EMAIL"),
                "BREVO_SENDER_NAME": st.secrets.get("BREVO_SENDER_NAME"),
            }
    except Exception:  # noqa: BLE001
        pass

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


def valid_email(addr):
    """
    Shape only. This deliberately does not claim to verify deliverability, because
    a regex cannot, and pretending otherwise is how the bounce problem starts.
    Deliverability is established by the send itself and recorded per capture.
    """
    return bool(addr and EMAIL_RE.match(addr.strip()))


def log_capture(run_id, company, email, action, consent_copy, consent_followup, note, status):
    exists = CAPTURES.exists()
    with open(CAPTURES, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAPTURE_COLUMNS)
        if not exists:
            w.writeheader()
        w.writerow(
            {
                "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "run_id": run_id,
                "company_name": company,
                "email": email,
                "action": action,
                "consent_report_copy": consent_copy,
                "consent_followup": consent_followup,
                "recipient_note": note or "",
                "send_status": status,
            }
        )


def brevo_send(to_email, subject, html_body, to_name=None):
    """
    Transactional send, not a campaign. A campaign attaches a List-Unsubscribe
    header, which routes a one to one message into Gmail's Promotions tab, which
    is the wrong place for a report somebody just asked for.

    Returns (ok, detail).
    """
    env = load_env()
    key = env.get("BREVO_API_KEY")
    sender_email = env.get("BREVO_SENDER_EMAIL")
    sender_name = env.get("BREVO_SENDER_NAME") or "Leadership Gap Diagnostic"

    if not key:
        return False, "no BREVO_API_KEY configured"
    if not sender_email:
        return False, "no BREVO_SENDER_EMAIL configured"

    payload = {
        "sender": {"email": sender_email, "name": sender_name},
        "to": [{"email": to_email, **({"name": to_name} if to_name else {})}],
        "subject": subject,
        "htmlContent": html_body,
    }
    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode(),
        headers={
            "api-key": key,
            "Content-Type": "application/json",
            "accept": "application/json",
            # Brevo sits behind Cloudflare, which blocks the default Python user
            # agent on some endpoints with a 1010 error that looks like auth failure.
            "User-Agent": UA,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return True, f"sent, http {r.status}"
    except urllib.error.HTTPError as e:
        return False, f"http {e.code}: {e.read().decode()[:200]}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)[:200]


def email_report(report, to_email, report_html, share=False, note=None, consent_followup=False):
    """
    Deliver a copy of a report the person has already read on screen.

    `share` marks the onward send to a co founder or board member, which is logged
    as a distinct action because it is a different commercial event: it creates a
    second contact with a referral attached rather than a second touch on the same
    one.
    """
    run_id = report.get("run_id")
    company = report.get("company_name") or report.get("url")

    if not valid_email(to_email):
        log_capture(run_id, company, to_email, "share_onward" if share else "copy_to_self",
                    True, consent_followup, note, "rejected, malformed address")
        return False, "That address does not look right. Nothing was sent."

    if share:
        subject = f"A leadership read on {company}"
        intro = (
            f"<p>Someone at {company} asked us to send you this.</p>"
            + (f"<p><em>{note}</em></p>" if note else "")
        )
    else:
        subject = f"Your leadership gap read, {company}"
        intro = "<p>Here is the report you just read, so you have it in writing.</p>"

    body = (
        "<div style=\"font:16px/1.6 -apple-system,system-ui,sans-serif;color:#16181d\">"
        + intro
        + "<p>Every gap named in it carries the evidence it rests on and a confidence "
        "level, and the section at the end lists what the report could not see. Those "
        "unanswered questions are the most useful part.</p>"
        + report_html
        + "</div>"
    )

    ok, detail = brevo_send(to_email, subject, body)
    log_capture(
        run_id, company, to_email,
        "share_onward" if share else "copy_to_self",
        True, consent_followup, note,
        detail if ok else f"failed: {detail}",
    )

    if ok:
        return True, "Sent."
    # The capture is kept either way. A send failure must not lose the lead, and it
    # must not be reported as a success.
    return False, f"Captured, but the send did not go out ({detail})."


def main():
    if len(sys.argv) < 3:
        print("usage: python deliver.py <run.json> <email> [--share]")
        return 1
    run_path, to = sys.argv[1], sys.argv[2]
    share = "--share" in sys.argv
    report = json.loads(Path(run_path).read_text(encoding="utf-8"))

    import render

    # The onward share is read by somebody who did not run the diagnostic, so it
    # needs the framing that lets it stand alone in a forwarded email.
    ctx = "shared" if share else "self_serve"
    html_body = render.render(report, context=ctx).split("<body>")[1].split("</body>")[0]

    ok, msg = email_report(report, to, html_body, share=share)
    print(msg)
    print(f"capture log: {CAPTURES}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
