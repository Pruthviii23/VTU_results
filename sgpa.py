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
            }, ...
        ]
    }
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

        # ── Percentage for grade lookup ───────────────────────
        try:
            raw = float(total)
            pct = (raw / max_marks) * 100.0
        except (ValueError, TypeError):
            # Non-numeric total (AB, --, W etc.) → treat as fail
            raw, pct = 0, 0.0

        # ── Grade ─────────────────────────────────────────────
        if result in ("F", "W", "AB", "--"):
            grade, points = "F", 0
            passed = False
        else:
            grade, points = config.get_grade(pct)
            passed = result == "P"

        weighted      = credits * points
        sum_weighted += weighted
        sum_credits  += credits

        if passed:
            earned_credits += credits

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