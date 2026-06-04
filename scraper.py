import re
import logging

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

# ============================================================
# INTERNAL HELPERS
# ============================================================

def _safe_text(cell) -> str:
    """Strip and normalise text from a BeautifulSoup cell."""
    return cell.get_text(strip=True)


def _parse_subject_row(cells) -> dict | None:
    """
    Parse one divTableRow into a subject dict.
    Returns None if the row is malformed or a header row.
    """
    if len(cells) < 6:
        return None

    code = _safe_text(cells[0]).upper()

    # Skip header rows (first row of each table has text like "Subject Code")
    if not code or "SUBJECT" in code:
        return None

    return {
        "code":       code,
        "name":       _safe_text(cells[1]),
        "internal":   _safe_text(cells[2]),
        "external":   _safe_text(cells[3]),
        "total":      _safe_text(cells[4]),
        "result":     _safe_text(cells[5]),
    }


def _parse_semester_block(header_div) -> tuple[int, list[dict]]:
    """
    Given the semester header div (e.g. <div>Semester : 5</div>),
    walks to its sibling divTableBody and parses all subject rows.

    Returns (semester_number, [subject_dicts])
    """
    match = re.search(r"\d+", header_div.get_text())
    if not match:
        return -1, []

    sem_num   = int(match.group())
    table_div = header_div.find_next("div", class_="divTableBody")

    if not table_div:
        log.warning(f"Semester {sem_num}: no divTableBody found — skipping block.")
        return sem_num, []

    rows     = table_div.find_all("div", class_="divTableRow")
    subjects = []

    for row in rows:
        cells   = row.find_all("div", class_="divTableCell")
        subject = _parse_subject_row(cells)
        if subject:
            subjects.append(subject)

    return sem_num, subjects


# ============================================================
# PUBLIC API
# ============================================================

def scrape_student(driver, usn: str, target_semester: int) -> dict | None:
    """
    Parses the currently loaded results page.

    Returns a dict:
    {
        "USN":  "1AM22AI056",
        "Name": "V PRUTHVI RAJ GOWDA",
        "semesters": {
            5: [{"code": "BCS501", "name": "...", "internal": "43", ...}, ...],
            4: [{"code": "BCS405A", ...}],   # backlog entries, if any
        }
    }

    Returns None on failure (caller adds USN to failed list).
    """
    try:
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # ------------------------------------------------
        # Name & USN
        # ------------------------------------------------
        student_data = {"USN": usn, "Name": "", "semesters": {}}

        for row in soup.find_all("tr"):
            text = row.get_text()
            tds  = row.find_all("td")
            if len(tds) < 2:
                continue
            if "Student Name" in text:
                student_data["Name"] = tds[1].get_text(strip=True).lstrip(":").strip()
            if "University Seat Number" in text:
                student_data["USN"]  = tds[1].get_text(strip=True).lstrip(":").strip().upper()

        # ------------------------------------------------
        # Semester blocks
        # ------------------------------------------------
        sem_headers = soup.find_all(
            "div",
            string=re.compile(r"Semester\s*:\s*\d+", re.IGNORECASE)
        )

        # BeautifulSoup's string= match is exact — fall back to a wider search
        if not sem_headers:
            sem_headers = [
                div for div in soup.find_all("div")
                if re.search(r"Semester\s*:\s*\d+", div.get_text(), re.IGNORECASE)
                and len(div.get_text(strip=True)) < 30  # avoid grabbing large containers
            ]

        if not sem_headers:
            log.error(
                f"[{usn}] No semester blocks found — "
                f"possible HTML structure change or no results published."
            )
            return None

        for header in sem_headers:
            sem_num, subjects = _parse_semester_block(header)

            if sem_num == -1:
                continue

            if not subjects:
                log.warning(f"[{usn}] Semester {sem_num} block found but has no subject rows.")
                continue

            student_data["semesters"][sem_num] = subjects

        # ------------------------------------------------
        # Sanity checks
        # ------------------------------------------------
        if not student_data["semesters"]:
            log.error(f"[{usn}] Parsed zero semesters — returning None.")
            return None

        if target_semester not in student_data["semesters"]:
            log.warning(
                f"[{usn}] Target semester {target_semester} not in parsed semesters "
                f"{list(student_data['semesters'].keys())}. "
                f"Student may not have sat this exam."
            )

        log.info(
            f"[{usn}] Scraped: {student_data['Name']} | "
            f"Semesters found: {sorted(student_data['semesters'].keys())}"
        )
        return student_data

    except Exception as e:
        log.error(f"[{usn}] Scrape error: {e}", exc_info=True)
        return None
