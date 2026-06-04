import os
from collections import Counter

# ============================================================
# PATHS
# ============================================================

USN_FILE        = r"C:\Users\india\Desktop\VTU_results\usn_list.xlsx"
OUTPUT_FILE     = r"C:\Users\india\Desktop\VTU_results\vtu_results.xlsx"
CHECKPOINT_FILE = r"C:\Users\india\Desktop\VTU_results\checkpoint.txt"
FAILED_FILE     = r"C:\Users\india\Desktop\VTU_results\failed_usns.txt"
LOG_FILE        = r"C:\Users\india\Desktop\VTU_results\scraper.log"
MODEL_PATH      = r"C:\Users\india\Desktop\VTU_results\crnn_9_prediction_model.keras"

# ============================================================
# SCRAPER BEHAVIOUR
# ============================================================

MAX_CAPTCHA_RETRIES = 10
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
# STARTUP VALIDATION
# ============================================================

def validate():
    """Run once at startup. Logs warnings for config issues."""
    issues = []

    url_counts = Counter(SEMESTER_URLS.values())
    for url, count in url_counts.items():
        if count > 1:
            sems = [s for s, u in SEMESTER_URLS.items() if u == url]
            issues.append(f"Duplicate URL across semesters {sems}: {url}")

    for path in [USN_FILE]:
        if not os.path.exists(path):
            issues.append(f"Required file not found: {path}")

    model_dir = os.path.dirname(MODEL_PATH) or "."
    if not os.path.exists(MODEL_PATH):
        issues.append(f"Model file not found: {MODEL_PATH}")

    return issues
