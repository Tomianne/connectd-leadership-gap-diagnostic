#!/usr/bin/env python3
"""
The funnel and the seams, as one image.

Drawn in code rather than generated, for a reason worth stating: the argument
this diagram carries is that the gates cluster at one seam and are deliberately
absent elsewhere. That is a claim about structure, and a generated image cannot
be held to a structure. Every box here corresponds to a function that runs.

Run: python make_diagram.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent
OUT = ROOT / "docs" / "diagram.png"

W, H = 1600, 1000
SCALE = 2  # drawn at 2x and downsampled, which is the cheapest anti-aliasing

INK = (22, 24, 29)
SOFT = (86, 91, 102)
FAINT = (139, 144, 156)
LINE = (228, 228, 224)
PANEL = (247, 247, 245)
ACCENT = (180, 83, 42)
GREEN = (31, 107, 63)
AMBER = (138, 97, 0)
WHITE = (255, 255, 255)


def font(size, bold=False):
    path = "C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"
    try:
        return ImageFont.truetype(path, size * SCALE)
    except OSError:
        return ImageFont.load_default()


def rounded(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle([c * SCALE for c in box], radius=r * SCALE, fill=fill,
                        outline=outline, width=width * SCALE)


def text(d, xy, s, f, fill=INK, anchor="la"):
    d.text((xy[0] * SCALE, xy[1] * SCALE), s, font=f, fill=fill, anchor=anchor)


def wrap(d, xy, s, f, fill, max_w, leading):
    """Naive word wrap. Enough for labels."""
    words, line, y = s.split(), "", xy[1]
    for w in words:
        trial = (line + " " + w).strip()
        if d.textlength(trial, font=f) / SCALE > max_w and line:
            text(d, (xy[0], y), line, f, fill)
            y += leading
            line = w
        else:
            line = trial
    if line:
        text(d, (xy[0], y), line, f, fill)
        y += leading
    return y


def arrow(d, x, y1, y2, colour=LINE, w=2):
    d.line([(x * SCALE, y1 * SCALE), (x * SCALE, y2 * SCALE)], fill=colour, width=w * SCALE)
    s = 7
    d.polygon(
        [
            (x * SCALE, y2 * SCALE),
            ((x - s / 2) * SCALE, (y2 - s) * SCALE),
            ((x + s / 2) * SCALE, (y2 - s) * SCALE),
        ],
        fill=colour,
    )


def build():
    img = Image.new("RGB", (W * SCALE, H * SCALE), WHITE)
    d = ImageDraw.Draw(img)

    f_title = font(30, True)
    f_h = font(17, True)
    f_b = font(14)
    f_s = font(12)
    f_tiny = font(11, True)

    text(d, (60, 52), "The funnel, and where the gates are", f_title)
    wrap(
        d, (60, 100),
        "Six steps. A human touches one of them. All the quality gates sit at a single seam, "
        "and their absence everywhere else is the design, not an oversight.",
        f_b, SOFT, 900, 22,
    )

    # ---------------- the six steps, left column
    x, w = 60, 560
    steps = [
        ("1  Fetch", "Known paths only: /, /about, /team, /careers. Text to markup ratio flags pages built by scripts we do not run.", None),
        ("2  Confirm", "\u201cWe found X, is this you?\u201d The only per run human gate. Cheap, deterministic, and it gates spend: nothing expensive runs until the subject is confirmed.", "human"),
        ("3  Extract", "Cheap model. Every field carries a source URL and a date. Unknowns recorded as unknown, never guessed.", None),
        ("3b  Qualify", "ICP screen: stage, size, disqualifiers. May exit here as out of profile.", "exit"),
        ("3c  Refusal gate", "Enough evidence? Leadership visible at all? May exit here as refused.", "exit"),
        ("4  Classify", "Stronger model. Up to three archetypes from a CLOSED list of 21, each with quoted evidence, a source and a confidence tier.", "gates"),
        ("5  Adversarial pass", "A different model tries to FALSIFY each claim. Five checks, then three more in deterministic code.", "gates"),
        ("6  Render and capture", "Report on screen, then the offer, then the address. Value before friction.", None),
    ]

    y = 168
    boxes = []
    for name, body, kind in steps:
        h = 34 + 20 * (2 if len(body) < 130 else 3)
        border = ACCENT if kind == "gates" else (AMBER if kind == "human" else LINE)
        wdt = 2 if kind in ("gates", "human") else 1
        rounded(d, (x, y, x + w, y + h), 9, fill=WHITE, outline=border, width=wdt)
        text(d, (x + 18, y + 13), name, f_h)
        wrap(d, (x + 18, y + 36), body, f_s, SOFT, w - 40, 17)

        if kind == "human":
            text(d, (x + w - 18, y + 14), "HUMAN GATE", f_tiny, AMBER, anchor="ra")
        if kind == "exit":
            text(d, (x + w - 18, y + 14), "CAN EXIT", f_tiny, FAINT, anchor="ra")
        if kind == "gates":
            text(d, (x + w - 18, y + 14), "GATED", f_tiny, ACCENT, anchor="ra")

        boxes.append((y, y + h, kind))
        y += h + 16

    for i in range(len(boxes) - 1):
        arrow(d, x + w / 2, boxes[i][1] + 2, boxes[i + 1][0] - 3)

    # ---------------- the seam panel, right column
    px, pw = 700, 840
    py = 168
    ph = 360
    rounded(d, (px, py, px + pw, py + ph), 11, fill=PANEL)
    text(d, (px + 30, py + 26), "The expensive seam: evidence to named gap", f_h, ACCENT)
    yy = wrap(
        d, (px + 30, py + 58),
        "Every other failure in this funnel costs a lead. This one costs credibility, in writing, "
        "in a document a founder may forward to their board. So every gate is here.",
        f_b, INK, pw - 60, 22,
    )

    gates = [
        ("Closed taxonomy", "classification, not generation", "config"),
        ("Mandatory citation", "no quoted evidence, no gap", "prompt"),
        ("Fewer than three allowed", "the count is an output, not a target", "prompt"),
        ("Adversarial pass", "a second model tries to disprove each claim", "prompt"),
        ("Leadership visibility", "cannot diagnose a leadership gap with no leadership visible", "CODE"),
        ("Confidence cap", "absence based claims can never rate above low", "CODE"),
        ("Shared evidence check", "two gaps, one citation, at most one is evidenced", "CODE"),
    ]
    yy += 8
    for label, why, where in gates:
        col = ACCENT if where == "CODE" else FAINT
        text(d, (px + 30, yy), "\u25aa", f_s, col)
        text(d, (px + 48, yy), label, f_s, INK)
        text(d, (px + 250, yy), why, f_s, SOFT)
        text(d, (px + pw - 30, yy), where, f_tiny, col, anchor="ra")
        yy += 21

    wrap(
        d, (px + 30, yy + 8),
        "The last three are in code, not in the prompt. Asking a model more firmly to respect its "
        "own confidence definitions is not a control. A rule is.",
        f_s, ACCENT, pw - 60, 18,
    )

    # ---------------- where there is deliberately no gate
    py2 = py + ph + 26
    ph2 = 210
    rounded(d, (px, py2, px + pw, py2 + ph2), 11, fill=WHITE, outline=LINE, width=1)
    text(d, (px + 30, py2 + 24), "Where there is deliberately no gate", f_h)
    yy = py2 + 56
    for line in [
        "Extraction. Cheap, and its worst failure is caught by step 2.",
        "Copy variants in the fast loop. Nothing a copy test gets wrong is expensive.",
        "Individual reports, when every gap rule passed. A human in that seat at volume",
        "rubber stamps, and a rubber stamp is worse than a rule because it looks like oversight.",
    ]:
        text(d, (px + 30, yy), line, f_s, SOFT)
        yy += 20
    wrap(
        d, (px + 30, yy + 8),
        "Naming where the gates are absent is what makes the principle real rather than decorative.",
        f_s, INK, pw - 60, 18,
    )

    # ---------------- outcomes
    py3 = py2 + ph2 + 26
    outs = [
        ("Report", "up to three gaps, each evidenced", GREEN),
        ("Screened out", "past the stage, and told so", ACCENT),
        ("Refused", "too little to read, declines", AMBER),
    ]
    bw = (pw - 2 * 16) / 3
    for i, (t, sub, col) in enumerate(outs):
        bx = px + i * (bw + 16)
        rounded(d, (bx, py3, bx + bw, py3 + 92), 9, fill=WHITE, outline=col, width=2)
        text(d, (bx + 20, py3 + 20), t, f_h, col)
        wrap(d, (bx + 20, py3 + 48), sub, f_s, SOFT, bw - 40, 17)

    text(
        d, (px, py3 + 112),
        "Two of the last six live runs produced a report. A diagnostic that only knows how to "
        "produce a diagnosis will produce one whether or not it should.",
        f_s, FAINT,
    )

    text(d, (60, H - 46), "Leadership Gap Diagnostic  \u00b7  built for Connectd, September 2026", f_s, FAINT)

    img = img.resize((W, H), Image.LANCZOS)
    OUT.parent.mkdir(exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT}  ({OUT.stat().st_size // 1024} KB, {W}x{H})")


if __name__ == "__main__":
    build()
