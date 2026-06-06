import os
from collections import Counter

# ============================================================
# PATHS
# ============================================================

USN_FILE        = r"VTU_results\Inp-Out\usn_list.xlsx"
OUTPUT_FILE     = r"VTU_results\Inp-Out\vtu_results.xlsx"
CHECKPOINT_FILE = r"VTU_results\Inp-Out\checkpoint.txt"
FAILED_FILE     = r"VTU_results\Inp-Out\failed_usns.txt"
LOG_FILE        = r"VTU_results\Inp-Out\scraper.log"
MODEL_PATH      = r"VTU_results\Inp-Out\crnn_10_prediction_model.keras"

# ============================================================
# SCRAPER BEHAVIOUR
# ============================================================

MAX_CAPTCHA_RETRIES = 7
MAX_USN_RETRIES     = 3
WAIT_TIMEOUT        = 15       # seconds for WebDriverWait
DELAY               = 1.5      # seconds between page loads
CAPTCHA_WARN_RATE   = 0.60     # alert if success rate drops below this

# ============================================================
# MODEL / IMAGE
# ============================================================

IMG_WIDTH  = 200
IMG_HEIGHT = 80
CHARACTERS = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789"
)

# ============================================================
# SEMESTER URLs
# NOTE: Sem 1's URL does not work
# ============================================================

SEMESTER_URLS = {
    1: "https://results.vtu.ac.in/JFEcbcs23/index.php",
    2: "https://results.vtu.ac.in/JJEcbcs23/index.php",
    3: "https://results.vtu.ac.in/DJcbcs24/index.php",
    4: "https://results.vtu.ac.in/JJEcbcs24/index.php",
    5: "https://results.vtu.ac.in/DJcbcs25/index.php",
    6: "https://results.vtu.ac.in/JJEcbcs25/index.php",
    7: "https://results.vtu.ac.in/D25J26Ecbcs/index.php",   
    8: "https://results.vtu.ac.in/MJ26cbcs/index.php",
}

# ============================================================
# GRADE TABLE  (per VTU photo — thresholds are PERCENTAGES)
# ============================================================
 
GRADE_TABLE = [
    (90, "O",   10),
    (80, "A+",   9),
    (70, "A",    8),
    (60, "B+",   7),
    (55, "B",    6),
    (50, "C",    5),
    (40, "P",    4),
    ( 0, "F",    0),
]
 
 
def get_grade(percentage: float) -> tuple[str, int]:
    """
    Returns (letter_grade, grade_points) for a given PERCENTAGE score.
    Percentage must already be computed by the caller
    (total_marks / max_marks * 100).
    """
    try:
        pct = float(percentage)
    except (ValueError, TypeError):
        return ("—", 0)
    for threshold, grade, points in GRADE_TABLE:
        if pct >= threshold:
            return (grade, points)
    return ("F", 0)
 
 
# ============================================================
# SUBJECT CREDITS  —  keyed by scheme year (string)
#
# Format per entry:  "SUBJECT_CODE": [credits, max_marks]
#   max_marks is used to convert raw marks → percentage for
#   grade lookup. Typical values:
#     100 → theory (50 internal + 50 external)
#      50 → lab (25+25 or 50+0)
#
# Wildcard codes (e.g. "BAI515x") are stored WITHOUT the
# trailing variant letter.  lookup_credits() handles matching.
#
# Zero-credit subjects (NSS, PE, Yoga) are included so the
# subject name is known, but SGPA skips them automatically.
# ============================================================
 
SUBJECT_CREDITS: dict[str, dict[str, list]] = {
 
    "2022": {
 
        # ── Sem 1 ───────────────────────────────────────────
        "BMATS101":  [4, 100],
        "BPHYS102":  [4, 100],
        "BPOPS103":  [3, 100],
        "BESCK104":  [3, 100],   # wildcard: BESCK104x
        "BETCK105":  [3, 100],   # wildcard: BETCK105x
        "BPLCK105":  [3, 100],   # wildcard: BPLCK105x
        "BENGK106":  [1, 100],
        "BPWSK106":  [1, 100],
        "BKSKK107":  [1, 100],
        "BKBKK107":  [1, 100],
        "BICOK107":  [1, 100],
        "BIDTK158":  [1, 100],
        "BSFHK158":  [1, 100],
 
        # ── Sem 2 ───────────────────────────────────────────
        "BMATS201":  [4, 100],
        "BCHES202":  [4, 100],
        "BCHEE202":  [4, 100],
        "BCEDK203":  [3, 100],
        "BESCK204":  [3, 100],   # wildcard: BESCK204x
        "BETCK205":  [3, 100],   # wildcard: BETCK205x
        "BPLCK205":  [3, 100],   # wildcard: BPLCK205x
        "BPWSK206":  [1, 100],
        "BENGK206":  [1, 100],
        "BICOK207":  [1, 100],
        "BKSKK207":  [1, 100],
        "BKBKK207":  [1, 100],
        "BSFHK258":  [1, 100],
        "BIDTK258":  [1, 100],
        "KIDTK258":  [1, 100],
 
        # ── Sem 3 (CS / AI&ML / DS / IS / CY) ─────────────
        "BCS301":    [4, 100],
        "BCS302":    [4, 100],
        "BCS303":    [4, 100],
        "BCS304":    [3, 100],
        "BCSL305":   [1,  50],
        "BCS306":    [3, 100],   # wildcard: BCS306x
        "BCS358":    [1, 100],   # wildcard: BCS358x
        "BRMK557":   [3, 100],
        "BSCK307":   [1, 100],
        "BXX306":    [3, 100],   # wildcard: BXX306x
        "BXX358":    [1, 100],   # wildcard: BXX358x
 
        # EC Sem 3
        "BMATEC301": [3, 100],
        "BEC302":    [4, 100],
        "BEC303":    [4, 100],
        "BEC304":    [3, 100],
        "BECL305":   [1,  50],
 
        # ── Sem 4 (CS / AI&ML / DS / IS / CY) ─────────────
        "BCS401":    [3, 100],
        "BCS402":    [4, 100],
        "BCS403":    [4, 100],
        "BCSL404":   [1,  50],
        "BCS405":    [3, 100],   # wildcard: BCS405x
        "BCS456":    [1, 100],   # wildcard: BCS456x
        "BBOC407":   [2, 100],
        "BBOK407":   [3, 100],
        "BAD402":    [4, 100],
        "BIS402":    [4, 100],
        "BXX405":    [3, 100],   # wildcard: BXX405x
        "BDS456":    [1, 100],   # wildcard: BDS456x
        "BUHK408":   [1, 100],
 
        # EC Sem 4
        "BEC401":    [3, 100],
        "BEC402":    [4, 100],
        "BEC403":    [4, 100],
        "BECL404":   [1,  50],
        "BEC405":    [3, 100],   # wildcard: BEC405x
        "BXX456":    [1, 100],   # wildcard: BXX456x
 
        # Zero-credit (NSS / PE / Yoga) — skipped in SGPA
        "BNSK359":   [0, 100],
        "BPEK359":   [0, 100],
        "BYOK359":   [0, 100],
        "BNSK459":   [0, 100],
        "BPEK459":   [0, 100],
        "BYOK459":   [0, 100],
 
        # ── Sem 5 (CS) ──────────────────────────────────────
        "BCS501":    [4, 100],
        "BCS502":    [4, 100],
        "BCS503":    [4, 100],
        "BCSL504":   [1,  50],
        "BCS515":    [3, 100],   # wildcard: BCS515x
        "BCS586":    [2, 100],
        "BCS508":    [1, 100],
        "BNSK559":   [0, 100],
        "BPEK559":   [0, 100],
        "BYOK559":   [0, 100],
 
        # Sem 5 (DS)
        "BCD501":    [4, 100],
        "BCD502":    [4, 100],
        "BCD503":    [4, 100],
        "BCDL504":   [1,  50],
        "BCD515":    [3, 100],   # wildcard: BCD515x
        "BCD586":    [2, 100],
 
        # Sem 5 (IS)
        "BIS501":    [3, 100],
        "BIS502":    [4, 100],
        "BIS503":    [4, 100],
        "BISL504":   [1,  50],
        "BIS515":    [3, 100],   # wildcard: BIS515x
        "BIS586":    [2, 100],
 
        # Sem 5 (AI&ML — BAI)
        "BAI501":    [3, 100],
        "BAI502":    [4, 100],
        "BAI503":    [4, 100],
        "BAIL504":   [1,  50],
        "BAI515":    [3, 100],   # wildcard: BAI515x
        "BAI586":    [2, 100],
 
        # Sem 5 (DS — BAD)
        "BAD501":    [3, 100],
        "BAD502":    [4, 100],
        "BAD503":    [4, 100],
        "BADL504":   [1,  50],
        "BAD515":    [3, 100],   # wildcard: BAD515x
        "BAD586":    [2, 100],
 
        # Sem 5 (CI — BCI)
        "BCI501":    [3, 100],
        "BCI502":    [4, 100],
        "BCI503":    [4, 100],
        "BCIL504":   [1,  50],
        "BCI515":    [3, 100],   # wildcard: BCI515x
        "BCI586":    [2, 100],
 
        # Sem 5 (EC)
        "BEC501":    [3, 100],
        "BEC502":    [4, 100],
        "BEC503":    [4, 100],
        "BECL504":   [1,  50],
        "BEC515":    [3, 100],   # wildcard: BEC515x
        "BEC586":    [2, 100],
 
        # Shared Sem 5
        "BESK508":   [2, 100],
        "BXX515":    [3, 100],   # wildcard: BXX515x
 
        # ── Sem 6 ───────────────────────────────────────────
        "BCS601":    [4, 100],
        "BCS602":    [4, 100],
        "BCS613":    [3, 100],   # wildcard: BCS613x
        "BCS654":    [3, 100],   # wildcard: BCS654x
        "BCS685":    [2, 100],
        "BCSL606":   [1,  50],
        "BCS657":    [1, 100],   # wildcard: BCS657x
 
        "BCD601":    [4, 100],
        "BCD602":    [4, 100],
        "BCD603":    [4, 100],
        "BCD613":    [3, 100],   # wildcard: BCD613x
        "BCD654":    [3, 100],   # wildcard: BCD654x
        "BCD685":    [2, 100],
        "BCDL606":   [1,  50],
        "BCD657":    [1, 100],   # wildcard: BCD657x
 
        "BIS601":    [4, 100],
        "BIS602":    [4, 100],
        "BIS603":    [4, 100],
        "BIS614":    [3, 100],   # wildcard: BIS614x
        "BIS654":    [3, 100],   # wildcard: BIS654x
        "BIS685":    [6, 100],
 
        "BAI601":    [4, 100],
        "BAI602":    [4, 100],
        "BAI613":    [3, 100],   # wildcard: BAI613x
        "BAI654":    [3, 100],   # wildcard: BAI654x
        "BAI685":    [2, 100],
        "BAIL606":   [1,  50],
        "BAI657":    [1, 100],   # wildcard: BAI657x
 
        "BAD601":    [4, 100],
        "BAD602":    [4, 100],
        "BAD603":    [4, 100],
        "BAD613":    [3, 100],   # wildcard: BAD613x
        "BAD654":    [3, 100],   # wildcard: BAD654x
        "BAD685":    [2, 100],
        "BADL606":   [1,  50],
        "BAD657":    [1, 100],   # wildcard: BAD657x
 
        "BCI601":    [4, 100],
        "BCI602":    [4, 100],
        "BCI613":    [3, 100],   # wildcard: BCI613x
        "BCI654":    [3, 100],   # wildcard: BCI654x
        "BCI685":    [2, 100],
        "BCIL606":   [1,  50],
        "BCI657":    [1, 100],   # wildcard: BCI657x
 
        "BNSK658":   [0, 100],
        "BPEK658":   [0, 100],
        "BYOK658":   [0, 100],
 
        # ── Sem 7 ───────────────────────────────────────────
        "BCS701":    [4, 100],
        "BCS702":    [4, 100],
        "BCS703":    [4, 100],
        "BCS714":    [3, 100],   # wildcard: BCS714x
        "BCS755":    [3, 100],   # wildcard: BCS755x
        "BCS786":    [6, 100],
 
        "BCD701":    [4, 100],
        "BCD702":    [4, 100],
        "BCD703":    [4, 100],
        "BCD714":    [3, 100],   # wildcard: BCD714x
        "BCD755":    [3, 100],   # wildcard: BCD755x
        "BCD786":    [6, 100],
 
        "BIS701":    [4, 100],
        "BIS702":    [4, 100],
        "BIS703":    [4, 100],
        "BIS714":    [3, 100],   # wildcard: BIS714x
        "BIS755":    [3, 100],   # wildcard: BIS755x
        "BIS786":    [6, 100],
 
        "BAI701":    [4, 100],
        "BAI702":    [4, 100],
        "BAI703":    [4, 100],
        "BAI714":    [3, 100],   # wildcard: BAI714x
        "BAI755":    [3, 100],   # wildcard: BAI755x
        "BAI786":    [6, 100],
 
        "BAD701":    [4, 100],
        "BAD702":    [4, 100],
        "BAD703":    [4, 100],
        "BAD714":    [3, 100],   # wildcard: BAD714x
        "BAD755":    [3, 100],   # wildcard: BAD755x
        "BAD786":    [6, 100],
 
        "BCI701":    [4, 100],
        "BCI702":    [4, 100],
        "BCI703":    [4, 100],
        "BCI714":    [3, 100],   # wildcard: BCI714x
        "BCI755":    [3, 100],   # wildcard: BCI755x
        "BCI786":    [6, 100],
 
        # ── Sem 8 ───────────────────────────────────────────
        "BCS801":    [3, 100],   # wildcard: BCS801x
        "BCS802":    [3, 100],   # wildcard: BCS802x
        "BCS803":    [10, 200],
 
        "BCD801":    [3, 100],   # wildcard: BCD801x
        "BCD802":    [3, 100],   # wildcard: BCD802x
        "BCD803":    [10, 200],
 
        "BIS801":    [3, 100],   # wildcard: BIS801x
        "BIS802":    [3, 100],   # wildcard: BIS802x
        "BIS803":    [10, 200],
 
        "BAI801":    [3, 100],   # wildcard: BAI801x
        "BAI802":    [3, 100],   # wildcard: BAI802x
        "BAI803":    [10, 200],
        "BINT803":   [10, 200],  # wildcard: BINT803x — alternate internship code (Sem 8)
 
        "BAD801":    [3, 100],   # wildcard: BAD801x
        "BAD802":    [3, 100],   # wildcard: BAD802x
        "BAD803":    [10, 200],
 
        "BCI801":    [3, 100],   # wildcard: BCI801x
        "BCI802":    [3, 100],   # wildcard: BCI802x
        "BCI803":    [10, 200],
    },
 
    "2025": {
 
    # ──────────────────────────────────────────────────────
    # SEMESTER 1 — CHEMISTRY CYCLE
    # Stream variants for Mathematics: x = S, C, M, E
    # All resolve to same credits — wildcard handles the rest
    # ──────────────────────────────────────────────────────
 
    "1BMATS101": [4, 100],   # Applied Mathematics-I (CSE stream)
    "1BMATC101": [4, 100],   # Applied Mathematics-I (Civil stream)
    "1BMATM101": [4, 100],   # Applied Mathematics-I (Mech stream)
    "1BMATE101": [4, 100],   # Applied Mathematics-I (ECE stream)
 
    "1BCHES102": [4, 100],   # Applied Chemistry for Smart Systems (CSE stream)
    "1BCHEC102": [4, 100],   # Applied Chemistry for Smart Systems (Civil stream)
    "1BCHEM102": [4, 100],   # Applied Chemistry for Smart Systems (Mech stream)
    "1BCHEE102": [4, 100],   # Applied Chemistry for Smart Systems (ECE stream)
 
    "1BCEDC103": [3, 100],   # Computer-Aided Engineering Drawing
 
    "1BESC104A": [3, 100],   # Engineering Science Elective-I (Intro to Civil)
    "1BESC104B": [3, 100],   # Engineering Science Elective-I (Electrical)
    "1BESC104C": [3, 100],   # Engineering Science Elective-I (Electronics)
 
    "1BPLC105E": [3, 100],   # Programming Language Course (C Programming)
    "1BPLC105A": [3, 100],   # Programming Language Course (Python)
    "1BPLC105B": [3, 100],   # Programming Language Course (C++)
    "1BPLC105C": [3, 100],   # Programming Language Course (Java)
 
    "1BHSM106":  [1, 100],   # Communicative / Professional English
 
    "1BPOPL107": [1, 50],    # Programming Laboratory
 
    "1BKSK108":  [1, 50],    # Samskrutika Kannada
    "1BKBK108":  [1, 50],    # Balake Kannada
 
    # ──────────────────────────────────────────────────────
    # SEMESTER 1 — PHYSICS CYCLE
    # Same math codes as Chemistry cycle (shared)
    # ──────────────────────────────────────────────────────
 
    "1BPHYS102": [4, 100],   # Applied Physics (CSE stream)
    "1BPHYC102": [4, 100],   # Applied Physics (Civil stream)
    "1BPHYM102": [4, 100],   # Applied Physics (Mech stream)
    "1BPHYE102": [4, 100],   # Applied Physics (ECE stream)
 
    "1BME103":   [3, 100],   # IDEA Lab / Elements of Mechanical Engineering
 
    "1BAIA104":  [3, 100],   # Introduction to AI & Foundations
    "1BXX104":   [3, 100],   # Introduction to AI & Foundations (generic code variant)
 
    "1BXX105":   [3, 100],   # Stream Specific Core Fundamental (generic)
    "1BECE105":  [3, 100],   # Basics of Electronics (ECE stream variant)
 
    "1BXXL107":  [1, 50],    # Stream Specific Lab Core (generic)
    "1BECEL107": [1, 50],    # Electronics Lab (ECE stream variant)
 
    "1BICO108":  [1, 100],   # Indian Constitution & Innovation
 
    "1BSFH109":  [1, 100],   # Scientific Foundations of Health & Yoga
 
},

}
 
 
# ============================================================
# SUBJECT NAMES  (for PDF report display)
# Also keyed by scheme. Populated from your JSON data.
# ============================================================
 
SUBJECT_NAMES: dict[str, dict[str, str]] = {
    "2022": {
        "BMATS101": "Mathematics-I for CSE Stream",
        "BPHYS102": "Applied Physics for CSE Stream",
        "BPOPS103": "Principles of Programming Using C",
        "BENGK106": "Communicative English",
        "BKSKK107": "Samskrutika Kannada",
        "BICOK107":  "Indian Constitution",
        "BIDTK158": "Innovation and Design Thinking",
        "BSFHK158": "Scientific Foundations of Health",
        "BMATS201": "Mathematics-II for CSE Stream",
        "BCHES202": "Applied Chemistry for CSE Stream",
        "BCEDK203": "Computer-Aided Engineering Drawing",
        "BCS301":   "Mathematics for Computer Science",
        "BCS302":   "Digital Design & Computer Organization",
        "BCS303":   "Operating Systems",
        "BCS304":   "Data Structures and Applications",
        "BCSL305":  "Data Structures Lab",
        "BCS401":   "Analysis & Design of Algorithms",
        "BCS402":   "Microcontrollers",
        "BCS403":   "Database Management Systems",
        "BCSL404":  "Analysis & Design of Algorithms Lab",
        "BBOC407":  "Biology For Computer Engineers",
        "BCS501":   "Software Engineering & Project Management",
        "BCS502":   "Computer Networks",
        "BCS503":   "Theory of Computation",
        "BCSL504":  "Web Technology Lab",
        "BCS586":   "Mini Project",
        "BCS601":   "Cloud Computing",
        "BCS602":   "Machine Learning",
        "BCS685":   "Project Phase I",
        "BCSL606":  "Machine Learning Lab",
        "BCS701":   "Internet of Things",
        "BCS702":   "Parallel Computing",
        "BCS703":   "Cryptography & Network Security",
        "BCS786":   "Major Project Phase-II",
        "BCS803":   "Internship",
        "BAI501":   "Software Engineering & Project Management",
        "BAI502":   "Computer Networks",
        "BAI503":   "Theory of Computation",
        "BAIL504":  "Data Visualization Lab",
        "BAI586":   "Mini Project",
        "BAI601":   "Natural Language Processing",
        "BAI602":   "Machine Learning-I",
        "BAI685":   "Project Phase I",
        "BAIL606":  "Machine Learning Lab",
        "BAI701":   "Deep Learning & Reinforcement Learning",
        "BAI702":   "Machine Learning-II",
        "BAI703":   "Data Security & Privacy",
        "BAI786":   "Major Project Phase-II",
        "BAI803":   "Internship",
        "BAD701":   "Deep Learning & Reinforcement Learning",
        "BAD702":   "Statistical Machine Learning for Data Science",
        "BAD703":   "Data Security & Privacy",
        "BAD786":   "Major Project Phase-II",
        "BRMK557":  "Research Methodology and IPR",
        "BESK508":  "Environmental Studies & E-Waste Management",
        "BEC501":   "Technology Innovation & Entrepreneurship",
        "BEC502":   "Digital Signal Processing",
        "BEC503":   "Digital Communication",
        "BECL504":  "Digital Communication Lab",
        "BEC586":   "Mini Project",
        # Generic labels for wildcard families
        "BESCK104": "Engineering Science Course-I",
        "BETCK105": "Emerging Technology Course-I",
        "BPLCK105": "Programming Language Course-I",
        "BESCK204": "Engineering Science Course-II",
        "BETCK205": "Programming Language Course-II",
        "BPLCK205": "Emerging Technology Course-II",
        "BCS306":   "Elective Course-III",
        "BCS358":   "Ability Enhancement Course-III",
        "BCS405":   "Elective Course",
        "BCS456":   "Ability Enhancement Course-IV",
        "BCS515":   "Professional Elective",
        "BCS654":   "Open Elective",
        "BCS714":   "Professional Elective",
        "BCS755":   "Open Elective",
        "BAI515":   "Professional Elective",
        "BAI614":   "Professional Elective",
        "BAI654":   "Open Elective",
        "BAI714":   "Professional Elective",
        "BAI755":   "Open Elective",
        "BAD714":   "Professional Elective",
        "BAD755":   "Open Elective",
    },

    "2025": {
 
    "1BMATS101": "Applied Mathematics-I",
    "1BMATC101": "Applied Mathematics-I",
    "1BMATM101": "Applied Mathematics-I",
    "1BMATE101": "Applied Mathematics-I",
 
    "1BCHES102": "Applied Chemistry for Smart Systems",
    "1BCHEC102": "Applied Chemistry for Smart Systems",
    "1BCHEM102": "Applied Chemistry for Smart Systems",
    "1BCHEE102": "Applied Chemistry for Smart Systems",
 
    "1BCEDC103": "Computer-Aided Engineering Drawing",
 
    "1BESC104A": "Engineering Science Elective-I (Intro to Civil)",
    "1BESC104B": "Engineering Science Elective-I (Electrical)",
    "1BESC104C": "Engineering Science Elective-I (Electronics)",
 
    "1BPLC105E": "Programming Language Course (C Programming)",
    "1BPLC105A": "Programming Language Course (Python)",
    "1BPLC105B": "Programming Language Course (C++)",
    "1BPLC105C": "Programming Language Course (Java)",
 
    "1BHSM106":  "Communicative / Professional English",
    "1BPOPL107": "Programming Laboratory",
    "1BKSK108":  "Samskrutika Kannada",
    "1BKBK108":  "Balake Kannada",
 
    "1BPHYS102": "Applied Physics for Engineers",
    "1BPHYC102": "Applied Physics for Engineers",
    "1BPHYM102": "Applied Physics for Engineers",
    "1BPHYE102": "Applied Physics for Engineers",
 
    "1BME103":   "IDEA Lab / Elements of Mechanical Engineering",
    "1BAIA104":  "Introduction to AI & Foundations",
    "1BXX104":   "Introduction to AI & Foundations",
    "1BXX105":   "Stream Specific Core Fundamental",
    "1BECE105":  "Basics of Electronics",
    "1BXXL107":  "Stream Specific Lab Core",
    "1BECEL107": "Electronics Lab",
    "1BICO108":  "Indian Constitution & Innovation",
    "1BSFH109":  "Scientific Foundations of Health & Yoga",
 
 },
}
 
 
# ============================================================
# CREDIT LOOKUP  (with wildcard + slash handling)
# ============================================================
 
def lookup_credits(code: str, scheme: str) -> tuple[int, int] | None:
    """
    Looks up (credits, max_marks) for a subject code in the given scheme.
 
    Handles three cases:
      1. Exact match            — "BCS501"   → direct lookup
      2. Wildcard suffix        — "BAI515A"  → try "BAI515" (strip last char)
      3. Slash-separated codes  — stored as individual keys already
 
    Returns None if not found in any form.
    """
    table = SUBJECT_CREDITS.get(scheme, {})
    code  = code.upper().strip()
 
    # 1. Exact match
    if code in table:
        val = table[code]
        return (val[0], val[1])
 
    # 2. Wildcard: strip trailing variant letter if the base exists
    if len(code) > 3 and code[-1].isalpha():
        base = code[:-1]
        if base in table:
            val = table[base]
            return (val[0], val[1])
 
    return None
 
 
def lookup_name(code: str, scheme: str) -> str:
    """Returns the subject name for display, or the code itself if unknown."""
    table = SUBJECT_NAMES.get(scheme, {})
    code  = code.upper().strip()
 
    if code in table:
        return table[code]
 
    # Wildcard fallback
    if len(code) > 3 and code[-1].isalpha():
        base = code[:-1]
        if base in table:
            return table[base]
 
    return code   # fallback: just show the code
 
 
# ============================================================
# STARTUP VALIDATION
# ============================================================
 
def validate(scheme: str) -> list[str]:
    """Run once at startup. Returns list of warning strings."""
    issues = []
 
    url_counts = Counter(SEMESTER_URLS.values())
    for url, count in url_counts.items():
        if count > 1:
            sems = [s for s, u in SEMESTER_URLS.items() if u == url]
            issues.append(f"Duplicate URL across semesters {sems}: {url}")
 
    if not os.path.exists(USN_FILE):
        issues.append(f"Required file not found: {USN_FILE}")
 
    if not os.path.exists(MODEL_PATH):
        issues.append(f"Model file not found: {MODEL_PATH}")
 
    if scheme not in SUBJECT_CREDITS:
        issues.append(f"Scheme '{scheme}' not in SUBJECT_CREDITS.")
    elif not SUBJECT_CREDITS[scheme]:
        issues.append(f"Scheme '{scheme}' has no subject entries yet.")
 
    return issues
 