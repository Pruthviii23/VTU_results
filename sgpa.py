"""
SGPA Calculator
===============
VTU formula:
    SGPA = Σ(Credits × GradePoints) / Σ(Credits)

Grade is determined from PERCENTAGE (raw / max_marks × 100),
not raw marks — per the official VTU grading table.
Zero-credit subjects (NSS, PE, Yoga) are skipped automatically.
"""

import logging
import config

log = logging.getLogger(__name__)


# Non-pass result categories
_FAIL_RESULTS   = {"F", "W", "--"}
_ABSENT_RESULTS = {"A", "AB", "ABSENT"}   # VTU uses "A" on results page


def compute_sgpa(subjects: list[dict], scheme: str, usn: str = "") -> dict:
    """
    Args:
        subjects : list of subject dicts from scraper
                   each has keys: code, name, internal, external, total, result
        scheme   : e.g. "2022"
        usn      : for log messages only

    Returns dict:
    {
        "sgpa":             8.45,
        "total_credits":    20,
        "earned_credits":   17,
        "missing_credits":  ["XYZ101"],
        "subjects_detail":  [
            {
                "code":         "BCS501",
                "name":         "Software Engineering...",
                "credits":      4,
                "max_marks":    100,
                "raw_marks":    71,
                "percentage":   71.0,
                "grade":        "A",
                "grade_points": 8,
                "weighted":     32,
                "passed":       True,
                "absent":       False,
            }, ...
        ]
    }

    Absent ("A") subjects:
      - Contribute 0 grade points (same as fail)
      - Contribute 0 earned credits
      - Are included in total_credits denominator
      - Are flagged with absent=True for downstream use
    """
    detail          = []
    missing_credits = []
    sum_weighted    = 0
    sum_credits     = 0
    earned_credits  = 0

    for subj in subjects:
        code   = subj.get("code",   "").upper().strip()
        total  = subj.get("total",  "")
        result = subj.get("result", "").upper().strip()
        name   = subj.get("name",   code)

        # ── Credit + max_marks lookup ────────────────────────
        lookup = config.lookup_credits(code, scheme)

        if lookup is None:
            log.warning(
                f"[{usn}] Credits not found for '{code}' in scheme {scheme} "
                f"— excluded from SGPA. Add it to config.SUBJECT_CREDITS['{scheme}']."
            )
            missing_credits.append(code)
            continue

        credits, max_marks = lookup

        # ── Skip zero-credit subjects (NSS, PE, Yoga) ────────
        if credits == 0:
            log.debug(f"[{usn}] '{code}' has 0 credits — skipped in SGPA.")
            continue

        # ── Classify result ───────────────────────────────────
        absent = result in _ABSENT_RESULTS
        failed = result in _FAIL_RESULTS or absent   # absent = effectively fail for SGPA

        # ── Percentage for grade lookup ───────────────────────
        if absent:
            pct    = 0.0
            grade  = "A"
            points = 0
        elif failed:
            try:
                raw = float(total)
                pct = (raw / max_marks) * 100.0
            except (ValueError, TypeError):
                raw, pct = 0, 0.0
            grade, points = "F", 0
        else:
            try:
                raw = float(total)
                pct = (raw / max_marks) * 100.0
            except (ValueError, TypeError):
                raw, pct = 0, 0.0
            grade, points = config.get_grade(pct)

        passed        = result == "P"
        weighted      = credits * points
        sum_weighted += weighted
        sum_credits  += credits

        if passed:
            earned_credits += credits

        if absent:
            log.info(f"[{usn}] '{code}' marked Absent — 0 grade points, 0 earned credits.")

        detail.append({
            "code":         code,
            "name":         name,
            "credits":      credits,
            "max_marks":    max_marks,
            "raw_marks":    total,
            "percentage":   round(pct, 1),
            "grade":        grade,
            "grade_points": points,
            "weighted":     weighted,
            "passed":       passed,
            "absent":       absent,
        })

    # ── SGPA ──────────────────────────────────────────────────
    if sum_credits == 0:
        sgpa = None
        log.warning(f"[{usn}] SGPA uncalculable — no subjects with known credits.")
    else:
        sgpa = round(sum_weighted / sum_credits, 2)

    return {
        "sgpa":            sgpa,
        "total_credits":   sum_credits,
        "earned_credits":  earned_credits,
        "missing_credits": missing_credits,
        "subjects_detail": detail,
    }