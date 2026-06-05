"""
PDF Summary Report  —  Executive Style
=======================================
Designed for HODs, faculty, and academic coordinators.
Principles: clarity over decoration, insights over raw data,
minimal charts, professional typography.

Structure:
  Page 1 — Executive Summary + Key Insights
  Page 2 — Subject Performance Analysis
  Page 3 — Student Performance Analysis (top performers + SGPA chart)
"""

import os
import io
import logging
import datetime
from collections import defaultdict, Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, HRFlowable, KeepTogether,
)

import config
import sgpa as sgpa_calc

log = logging.getLogger(__name__)

# ============================================================
# PALETTE  — minimal, professional
# ============================================================

_NAVY        = colors.HexColor("#1B3A5C")
_BLUE        = colors.HexColor("#2E6DA4")
_LIGHT_BLUE  = colors.HexColor("#EAF2FB")
_MID_BLUE    = colors.HexColor("#D0E4F5")
_GREEN       = colors.HexColor("#1A6B3C")
_LIGHT_GREEN = colors.HexColor("#E8F5EE")
_AMBER       = colors.HexColor("#B45309")
_LIGHT_AMBER = colors.HexColor("#FEF3C7")
_RED         = colors.HexColor("#9B1C1C")
_LIGHT_RED   = colors.HexColor("#FEE2E2")
_GREY        = colors.HexColor("#F8F9FA")
_MID_GREY    = colors.HexColor("#E5E7EB")
_DARK_GREY   = colors.HexColor("#374151")
_WHITE       = colors.white
_BLACK       = colors.HexColor("#111827")

# ============================================================
# TYPOGRAPHY
# ============================================================

_S = getSampleStyleSheet()

def _style(name, **kw):
    return ParagraphStyle(name, parent=_S["Normal"], **kw)

_TITLE    = _style("T", fontSize=20, textColor=_NAVY,
                   fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=4)
_SUBTITLE = _style("ST", fontSize=10, textColor=_BLUE,
                   alignment=TA_CENTER, spaceAfter=2)
_DATELINE = _style("DL", fontSize=8, textColor=colors.HexColor("#6B7280"),
                   alignment=TA_CENTER, spaceAfter=16)
_H2       = _style("H2", fontSize=12, textColor=_NAVY,
                   fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=6)
_H3       = _style("H3", fontSize=9, textColor=_BLUE,
                   fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=4)
_BODY     = _style("B", fontSize=8.5, textColor=_DARK_GREY,
                   leading=13, spaceAfter=4)
_CAPTION  = _style("CA", fontSize=7.5, textColor=colors.HexColor("#6B7280"),
                   alignment=TA_CENTER, spaceAfter=6)
_INSIGHT  = _style("IN", fontSize=8.5, textColor=_DARK_GREY,
                   leading=14, leftIndent=10, spaceAfter=2)


# ============================================================
# HELPERS
# ============================================================

def _hr(story, colour=_MID_GREY, thickness=0.5, space_before=2, space_after=8):
    story.append(Spacer(1, space_before))
    story.append(HRFlowable(width="100%", thickness=thickness,
                             color=colour, spaceAfter=space_after))


def _fig_to_image(fig, width_cm=15.5) -> Image:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    buf.seek(0)
    plt.close(fig)
    return Image(buf, width=width_cm * cm, height=width_cm * 0.42 * cm)


def _table(data, col_widths, style_cmds, row_heights=None) -> Table:
    t = Table(data, colWidths=col_widths, rowHeights=row_heights)
    base = [
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0),  8),
        ("BACKGROUND",   (0, 0), (-1, 0),  _NAVY),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  _WHITE),
        ("FONTNAME",     (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",     (0, 1), (-1, -1), 8),
        ("TEXTCOLOR",    (0, 1), (-1, -1), _DARK_GREY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_WHITE, _GREY]),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",         (0, 0), (-1, -1), 0.3, _MID_GREY),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    t.setStyle(TableStyle(base + style_cmds))
    return t


def _remark(pct: float) -> tuple[str, object]:
    """Returns (remark text, text colour)."""
    if pct >= 90:
        return "Excellent", _GREEN
    if pct >= 75:
        return "Good",      _BLUE
    return "Needs Attention", _RED


# ============================================================
# DATA ANALYSIS
# ============================================================

def _analyse(all_students: list[dict], semester: int, scheme: str) -> dict:
    sub_stats   = defaultdict(lambda: {"total": 0, "pass": 0, "fail": 0, "marks": []})
    sgpa_values = []
    ranked      = []

    for student in all_students:
        sem_subjects = student["semesters"].get(semester, [])
        if not sem_subjects:
            continue

        result  = sgpa_calc.compute_sgpa(sem_subjects, scheme, student["USN"])
        sgpa_v  = result["sgpa"]

        if sgpa_v is not None:
            sgpa_values.append(sgpa_v)
            ranked.append({
                "USN":  student["USN"],
                "Name": student["Name"],
                "SGPA": sgpa_v,
            })

        for subj in sem_subjects:
            code   = subj["code"]
            result_val = subj.get("result", "").upper()
            try:
                sub_stats[code]["marks"].append(int(subj.get("total", "")))
            except (ValueError, TypeError):
                pass
            sub_stats[code]["total"] += 1
            if result_val == "P":
                sub_stats[code]["pass"] += 1
            elif result_val == "F":
                sub_stats[code]["fail"] += 1

    ranked.sort(key=lambda s: s["SGPA"], reverse=True)

    n         = len(ranked)
    avg_sgpa  = round(sum(sgpa_values) / n, 2) if n else None
    high_sgpa = max(sgpa_values) if sgpa_values else None
    low_sgpa  = min(sgpa_values) if sgpa_values else None

    # Overall pass: students with no F in target semester
    total_students = len(all_students)
    pass_count = sum(
        1 for s in all_students
        if all(
            sub.get("result", "").upper() != "F"
            for sub in s["semesters"].get(semester, [])
        )
        and s["semesters"].get(semester)
    )
    overall_pass_pct = round(100 * pass_count / total_students, 1) if total_students else 0

    return {
        "sub_stats":        dict(sub_stats),
        "ranked":           ranked,
        "sgpa_values":      sgpa_values,
        "total_students":   total_students,
        "avg_sgpa":         avg_sgpa,
        "high_sgpa":        high_sgpa,
        "low_sgpa":         low_sgpa,
        "overall_pass_pct": overall_pass_pct,
        "pass_count":       pass_count,
    }


def _key_insights(data: dict, scheme: str) -> list[str]:
    """Generate 3-5 insight strings from the data."""
    insights = []
    sub      = data["sub_stats"]

    if not sub:
        return ["Insufficient data to generate insights."]

    # Best and worst subjects by pass%
    def pass_pct(code):
        s = sub[code]
        return 100 * s["pass"] / s["total"] if s["total"] else 0

    sorted_subs = sorted(sub.keys(), key=pass_pct)
    worst = sorted_subs[0]  if sorted_subs else None
    best  = sorted_subs[-1] if sorted_subs else None

    if best:
        bp = pass_pct(best)
        name = config.lookup_name(best, scheme)
        insights.append(f"Best performing subject: {best} – {name} ({bp:.0f}% pass rate).")

    if worst and worst != best:
        wp = pass_pct(worst)
        name = config.lookup_name(worst, scheme)
        tag  = "requires immediate attention" if wp < 50 else "needs monitoring"
        insights.append(f"Lowest performing subject: {worst} – {name} ({wp:.0f}% pass rate) — {tag}.")

    attention = [c for c in sub if pass_pct(c) < 75]
    if attention:
        insights.append(
            f"{len(attention)} subject(s) below 75% pass rate: {', '.join(sorted(attention))}."
        )

    avg = data["avg_sgpa"]
    if avg is not None:
        if avg >= 8.0:
            insights.append(f"Class SGPA average of {avg} indicates strong overall performance.")
        elif avg >= 6.5:
            insights.append(f"Class SGPA average of {avg} indicates moderate overall performance.")
        else:
            insights.append(f"Class SGPA average of {avg} is below expectations — intervention recommended.")

    opp = data["overall_pass_pct"]
    fail_count = data["total_students"] - data["pass_count"]
    if fail_count > 0:
        insights.append(
            f"{fail_count} student(s) have at least one backlog "
            f"({100 - opp:.0f}% of class)."
        )

    return insights[:5]


# ============================================================
# PAGE TEMPLATE
# ============================================================

def _on_page(canvas, doc, semester: int, label: str, scheme: str):
    canvas.saveState()
    w, h = A4

    # Top bar
    canvas.setFillColor(_NAVY)
    canvas.rect(0, h - 1.1*cm, w, 1.1*cm, fill=1, stroke=0)
    canvas.setFillColor(_WHITE)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(1.5*cm, h - 0.72*cm,
                      f"VTU Results  |  Semester {semester}  |  Scheme {scheme}  |  {label}")
    canvas.drawRightString(w - 1.5*cm, h - 0.72*cm,
                           datetime.datetime.now().strftime("%d %b %Y"))

    # Bottom bar
    canvas.setFillColor(_MID_GREY)
    canvas.rect(0, 0, w, 0.7*cm, fill=1, stroke=0)
    canvas.setFillColor(_DARK_GREY)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawCentredString(w/2, 0.22*cm,
                             f"Confidential — For Internal Academic Use Only  |  Page {doc.page}")
    canvas.restoreState()


# ============================================================
# SECTION 1: EXECUTIVE SUMMARY
# ============================================================

def _metric_box(label: str, value: str) -> list:
    """Single metric card as a mini 2-row table."""
    t = Table(
        [[label], [value]],
        colWidths=[3.6*cm],
        rowHeights=[0.65*cm, 0.85*cm],
    )
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, 0), _NAVY),
        ("BACKGROUND",    (0, 1), (0, 1), _LIGHT_BLUE),
        ("TEXTCOLOR",     (0, 0), (0, 0), _WHITE),
        ("TEXTCOLOR",     (0, 1), (0, 1), _NAVY),
        ("FONTNAME",      (0, 0), (0, 0), "Helvetica-Bold"),
        ("FONTNAME",      (0, 1), (0, 1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (0, 0), 7),
        ("FONTSIZE",      (0, 1), (0, 1), 14),
        ("ALIGN",         (0, 0), (0, -1), "CENTER"),
        ("VALIGN",        (0, 0), (0, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (0, -1), 4),
        ("BOTTOMPADDING", (0, 0), (0, -1), 4),
        ("BOX",           (0, 0), (0, -1), 0.5, _MID_BLUE),
    ]))
    return t


def _executive_summary(story, semester: int, scheme: str, data: dict, label: str):
    # Title block
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph("Academic Results Summary", _TITLE))
    story.append(Paragraph(f"Semester {semester}  ·  Scheme {scheme}  ·  {label}", _SUBTITLE))
    story.append(Paragraph(datetime.datetime.now().strftime("%d %B %Y"), _DATELINE))
    _hr(story, _BLUE, thickness=1.5, space_after=14)

    # Metric cards row
    n    = data["total_students"]
    avg  = f"{data['avg_sgpa']:.2f}"  if data["avg_sgpa"]  else "—"
    high = f"{data['high_sgpa']:.2f}" if data["high_sgpa"] else "—"
    low  = f"{data['low_sgpa']:.2f}"  if data["low_sgpa"]  else "—"
    opp  = f"{data['overall_pass_pct']}%"

    metrics = [
        ("TOTAL STUDENTS",   str(n)),
        ("AVERAGE SGPA",     avg),
        ("HIGHEST SGPA",     high),
        ("LOWEST SGPA",      low),
        ("OVERALL PASS %",   opp),
    ]

    cards = [[_metric_box(lbl, val) for lbl, val in metrics]]
    gap   = (A4[0] - 3 * cm - 5 * 3.6*cm) / 4   # auto-space 5 cards
    card_table = Table(cards, colWidths=[3.6*cm + gap] * 5)
    card_table.setStyle(TableStyle([
        ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(card_table)
    story.append(Spacer(1, 0.5*cm))

    # Key Insights
    _hr(story, _MID_GREY, space_before=4, space_after=6)
    story.append(Paragraph("Key Insights", _H2))

    insights = _key_insights(data, scheme)
    for idx, insight in enumerate(insights, 1):
        story.append(Paragraph(f"<b>{idx}.</b>  {insight}", _INSIGHT))

    story.append(Spacer(1, 0.3*cm))


# ============================================================
# SECTION 2: SUBJECT PERFORMANCE
# ============================================================

def _subject_performance(story, data: dict, scheme: str):
    _hr(story, _NAVY, thickness=1, space_before=6, space_after=10)
    story.append(Paragraph("Subject Performance Analysis", _H2))

    sub   = data["sub_stats"]
    rows  = [["Code", "Subject Name", "Appeared", "Passed", "Failed", "Pass %",
               "Avg Marks", "Remarks"]]

    style_cmds = [
        ("ALIGN",  (0, 0), (0, -1), "LEFT"),   # code left
        ("ALIGN",  (1, 0), (1, -1), "LEFT"),   # name left
        ("ALIGN",  (7, 0), (7, -1), "LEFT"),   # remarks left
    ]

    for r_idx, code in enumerate(sorted(sub.keys()), start=1):
        s     = sub[code]
        total = s["total"]
        passed = s["pass"]
        failed = s["fail"]
        marks  = s["marks"]

        pct    = 100 * passed / total if total else 0
        avg_m  = f"{sum(marks)/len(marks):.1f}" if marks else "—"
        name   = config.lookup_name(code, scheme)
        remark, rem_colour = _remark(pct)

        rows.append([
            code, name, total, passed, failed,
            f"{pct:.1f}%", avg_m, remark,
        ])

        # Colour the remarks cell
        style_cmds.append(("TEXTCOLOR", (7, r_idx), (7, r_idx), rem_colour))
        style_cmds.append(("FONTNAME",  (7, r_idx), (7, r_idx), "Helvetica-Bold"))

        # Light red row if needs attention
        if pct < 75:
            style_cmds.append(
                ("BACKGROUND", (0, r_idx), (-1, r_idx), _LIGHT_RED)
            )

    cw = [2.2*cm, 5.8*cm, 1.6*cm, 1.6*cm, 1.5*cm, 1.6*cm, 2*cm, 2.8*cm]
    story.append(_table(rows, cw, style_cmds))
    story.append(Spacer(1, 0.2*cm))

    # Legend
    legend_data = [[
        Paragraph("<font color='#1A6B3C'><b>■</b></font>  Excellent  (≥ 90%)", _CAPTION),
        Paragraph("<font color='#2E6DA4'><b>■</b></font>  Good  (75–89%)",     _CAPTION),
        Paragraph("<font color='#9B1C1C'><b>■</b></font>  Needs Attention  (< 75%)", _CAPTION),
    ]]
    lt = Table(legend_data, colWidths=[5*cm, 4.5*cm, 5*cm])
    lt.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    story.append(lt)


# ============================================================
# SECTION 3: STUDENT PERFORMANCE
# ============================================================

def _sgpa_bar_chart(ranked: list[dict]) -> Image | None:
    """
    Horizontal bar chart of SGPA per student.
    Only generated if student count is between 2 and 40
    (too few = not useful; too many = unreadable).
    """
    n = len(ranked)
    if n < 2 or n > 40:
        return None

    names  = [f"{r['USN'][-4:]}" for r in ranked]   # last 4 chars of USN
    sgpas  = [r["SGPA"] for r in ranked]
    colours = ["#1B3A5C" if s >= 8.0 else "#2E6DA4" if s >= 6.0 else "#9B1C1C"
               for s in sgpas]

    fig_h  = max(3.5, n * 0.28)
    fig, ax = plt.subplots(figsize=(7, fig_h))
    bars = ax.barh(names, sgpas, color=colours, edgecolor="white", height=0.6)
    ax.bar_label(bars, fmt="%.2f", fontsize=6.5, padding=3, color="#374151")
    ax.set_xlim(0, 10.5)
    ax.set_xlabel("SGPA", fontsize=8, color="#374151")
    ax.tick_params(axis="y", labelsize=6.5)
    ax.tick_params(axis="x", labelsize=7)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    ax.axvline(x=8.0, color="#1A6B3C", linestyle=":", linewidth=0.8, alpha=0.7)
    ax.axvline(x=6.0, color="#B45309", linestyle=":", linewidth=0.8, alpha=0.7)
    ax.set_title("SGPA Distribution by Student", fontsize=9,
                 color="#1B3A5C", pad=8, fontweight="bold")
    fig.tight_layout()

    width_cm = 15.5
    height_cm = max(4, fig_h * 1.5)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    buf.seek(0)
    plt.close(fig)
    return Image(buf, width=width_cm*cm, height=height_cm*cm)


def _student_performance(story, data: dict):
    story.append(PageBreak())
    story.append(Paragraph("Student Performance Analysis", _H2))
    _hr(story, _MID_GREY, space_before=2, space_after=8)

    ranked = data["ranked"]
    if not ranked:
        story.append(Paragraph("No SGPA data available.", _BODY))
        return

    # Top performers table — all students, ranked
    story.append(Paragraph("Student Rankings", _H3))

    rows = [["Rank", "USN", "Student Name", "SGPA", "Class"]]
    style_cmds = [
        ("ALIGN",  (2, 0), (2, -1), "LEFT"),   # name left
    ]

    def classify(s):
        if s >= 9.0: return "First Class with Distinction"
        if s >= 7.5: return "First Class"
        if s >= 6.0: return "Second Class"
        if s >= 5.0: return "Pass"
        return "Fail"

    for rank, student in enumerate(ranked, 1):
        cls    = classify(student["SGPA"])
        colour = (_GREEN if "Distinction" in cls else
                  _BLUE  if "First" in cls else
                  _AMBER if "Second" in cls else
                  _RED   if "Fail" in cls else _DARK_GREY)

        rows.append([rank, student["USN"], student["Name"],
                     f"{student['SGPA']:.2f}", cls])

        style_cmds.append(("TEXTCOLOR", (4, rank), (4, rank), colour))
        style_cmds.append(("FONTNAME",  (4, rank), (4, rank), "Helvetica-Bold"))

        # Gold highlight for top 3
        if rank <= 3:
            style_cmds.append(
                ("BACKGROUND", (0, rank), (-1, rank), colors.HexColor("#FFFBEB"))
            )

    cw = [1.5*cm, 3.5*cm, 6.5*cm, 2*cm, 5*cm]
    story.append(_table(rows, cw, style_cmds))
    story.append(Spacer(1, 0.5*cm))

    # Class summary box
    from collections import Counter as C
    class_counts = C(classify(r["SGPA"]) for r in ranked)
    order = ["First Class with Distinction", "First Class",
             "Second Class", "Pass", "Fail"]

    summary_rows = [["Classification", "Count", "Percentage"]]
    total = len(ranked)
    sc    = []
    for cls in order:
        cnt = class_counts.get(cls, 0)
        if cnt:
            summary_rows.append([cls, cnt, f"{100*cnt/total:.1f}%"])
            sc.append((cls, cnt))

    summary_cmds = []
    colour_map = {
        "First Class with Distinction": _GREEN,
        "First Class":                  _BLUE,
        "Second Class":                 _AMBER,
        "Pass":                         _DARK_GREY,
        "Fail":                         _RED,
    }
    for r_idx, (cls, _) in enumerate(sc, start=1):
        c = colour_map.get(cls, _DARK_GREY)
        summary_cmds.append(("TEXTCOLOR", (0, r_idx), (0, r_idx), c))
        summary_cmds.append(("FONTNAME",  (0, r_idx), (0, r_idx), "Helvetica-Bold"))

    KeepTogether([
        Paragraph("Class Distribution", _H3),
        _table(summary_rows, [7*cm, 3*cm, 4*cm], summary_cmds),
    ])
    story.append(Paragraph("Class Distribution", _H3))
    story.append(_table(summary_rows, [7*cm, 3*cm, 4*cm], summary_cmds))

    # SGPA bar chart — only if useful
    story.append(Spacer(1, 0.5*cm))
    chart = _sgpa_bar_chart(ranked)
    if chart:
        story.append(Paragraph("SGPA Overview", _H3))
        story.append(chart)
        story.append(Paragraph(
            "Blue = SGPA ≥ 8.0  ·  Steel = 6.0–7.9  ·  Red = below 6.0  "
            "|  Green dotted line = 8.0  ·  Amber dotted line = 6.0",
            _CAPTION
        ))


# ============================================================
# PUBLIC API
# ============================================================

def write_pdf(all_students: list[dict], output_path: str,
              semester: int, scheme: str = "2022", batch: str = ""):
    """
    Generates the executive-style summary PDF.

    Args:
        all_students : list of student dicts from scraper
        output_path  : destination file path
        semester     : target semester number
        scheme       : e.g. "2022"
        batch        : display label e.g. "2022 Batch · AI&ML"
    """
    if not all_students:
        log.warning("No student data — PDF not generated.")
        return

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    data  = _analyse(all_students, semester, scheme)
    label = batch or f"Semester {semester}"

    doc = SimpleDocTemplate(
        output_path,
        pagesize     = A4,
        leftMargin   = 1.5*cm,
        rightMargin  = 1.5*cm,
        topMargin    = 1.8*cm,
        bottomMargin = 1.4*cm,
        title        = f"VTU Results Sem {semester} — {label}",
        author       = "VTU Scraper",
    )

    story = []

    _executive_summary(story, semester, scheme, data, label)
    story.append(PageBreak())
    _subject_performance(story, data, scheme)
    _student_performance(story, data)

    on_page = lambda c, d: _on_page(c, d, semester, label, scheme)
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)

    log.info(f"PDF report saved: {output_path}")