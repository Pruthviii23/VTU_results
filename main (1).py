"""
VTU Results Scraper
===================
Just run:
    python main.py

You will be prompted for the semester number.
Everything else (USN file, output path) uses the defaults in config.py.
"""

import os
import sys
import time
import logging
import datetime

import pandas as pd

import config
import checkpoint as ckpt
import browser
import scraper
import exporter

# ============================================================
# LOGGING SETUP
# ============================================================

os.makedirs(os.path.dirname(config.LOG_FILE) or ".", exist_ok=True)

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S",
    handlers = [
        logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
        # StreamHandler intentionally omitted during scraping —
        # log lines would break the live progress bar.
        # All activity is written to LOG_FILE in real time.
    ]
)

log = logging.getLogger("main")


# ============================================================
# HELPERS
# ============================================================

def load_usn_list(path: str) -> list[str]:
    df = pd.read_excel(path, dtype=str)

    if "USN" not in df.columns:
        raise ValueError(f"'USN' column not found in {path}. Columns found: {df.columns.tolist()}")

    usns = df["USN"].dropna().str.strip().str.upper().tolist()

    # Deduplicate while preserving order
    seen, unique = set(), []
    for u in usns:
        if u not in seen:
            seen.add(u)
            unique.append(u)

    duplicates = len(usns) - len(unique)
    if duplicates:
        log.warning(f"{duplicates} duplicate USN(s) removed from input list.")

    log.info(f"Loaded {len(unique)} unique USNs from {path}")
    return unique


def write_failed(failed: list[str], path: str):
    if not failed:
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(failed))
    log.warning(f"{len(failed)} failed USN(s) written to {path}")


# ============================================================
# PROGRESS TRACKER
# ============================================================

class Progress:
    """
    Prints a live-updating progress bar to the terminal.

    Example output:
      [████████████░░░░░░░░]  60%  12/20  ✓ 11  ✗ 1  ETA 00:01:24  1AM22AI067
    """

    BAR_WIDTH = 20

    def __init__(self, total: int, start_index: int = 0):
        self.total      = total
        self.done       = 0          # USNs processed (success + fail)
        self.success    = 0
        self.failed     = 0
        self.current    = ""         # current USN being processed
        self.status     = ""         # short status tag e.g. "solving captcha"
        self._start     = time.time()
        self._start_idx = start_index   # for offset display when resuming

    # ---- update calls ----------------------------------------

    def update(self, usn: str, status: str = ""):
        """Call at the start of each USN."""
        self.current = usn
        self.status  = status
        self._render()

    def mark_success(self):
        self.done    += 1
        self.success += 1
        self.status   = "✓ scraped"
        self._render()

    def mark_failed(self):
        self.done   += 1
        self.failed += 1
        self.status  = "✗ failed"
        self._render()

    def set_status(self, status: str):
        self.status = status
        self._render()

    def finish(self):
        """Print final summary line and move to next line."""
        elapsed = self._elapsed_str()
        acc     = self.success / self.done if self.done else 0
        print(
            f"\r  Done — "
            f"{self.success} scraped  "
            f"{self.failed} failed  "
            f"Accuracy {acc:.0%}  "
            f"Time {elapsed}"
            + " " * 20   # clear any trailing chars
        )

    # ---- internal --------------------------------------------

    def _elapsed_str(self) -> str:
        secs = int(time.time() - self._start)
        return str(datetime.timedelta(seconds=secs))

    def _eta_str(self) -> str:
        if self.done == 0:
            return "--:--:--"
        elapsed  = time.time() - self._start
        per_usn  = elapsed / self.done
        remaining = (self.total - self.done) * per_usn
        return str(datetime.timedelta(seconds=int(remaining)))

    def _bar(self) -> str:
        filled = int(self.BAR_WIDTH * self.done / self.total) if self.total else 0
        return "█" * filled + "░" * (self.BAR_WIDTH - filled)

    def _render(self):
        pct      = int(100 * self.done / self.total) if self.total else 0
        absolute = f"{self._start_idx + self.done}/{self._start_idx + self.total}"
        status   = self.status[:18].ljust(18)   # fixed width so bar doesn't jump
        usn      = self.current

        line = (
            f"\r  [{self._bar()}] {pct:>3}%  "
            f"{absolute}  "
            f"✓{self.success} ✗{self.failed}  "
            f"ETA {self._eta_str()}  "
            f"{status}  {usn}"
        )
        # \r overwrites the same line; flush ensures it appears immediately
        print(line, end="", flush=True)


# ============================================================
# INTERACTIVE PROMPT
# ============================================================

def prompt_semester() -> int:
    """
    Asks the user to pick a semester interactively.
    Keeps re-asking until a valid number is entered.
    """
    valid = sorted(config.SEMESTER_URLS.keys())

    print("\n" + "=" * 45)
    print("       VTU Results Scraper")
    print("=" * 45)
    print(f"  Available semesters: {valid}")
    print("=" * 45)

    while True:
        try:
            raw = input("\n  Enter semester number: ").strip()
            sem = int(raw)
            if sem in valid:
                return sem
            print(f"  ✗ '{sem}' is not a valid semester. Choose from {valid}.")
        except ValueError:
            print(f"  ✗ Please enter a number (e.g. 5).")
        except (KeyboardInterrupt, EOFError):
            print("\n\n  Cancelled. Exiting.")
            sys.exit(0)


def prompt_resume() -> bool:
    """
    If a checkpoint exists, asks whether to resume or restart.
    Returns True to resume, False to restart from scratch.
    Skipped entirely if no checkpoint exists.
    """
    if not os.path.exists(config.CHECKPOINT_FILE):
        return True   # nothing to resume, irrelevant

    print("\n  A previous run was interrupted.")

    while True:
        try:
            raw = input("  Resume from where it stopped? [Y/n]: ").strip().lower()
            if raw in ("", "y", "yes"):
                return True
            if raw in ("n", "no"):
                return False
            print("  ✗ Please enter Y or N.")
        except (KeyboardInterrupt, EOFError):
            print("\n\n  Cancelled. Exiting.")
            sys.exit(0)


# ============================================================
# MAIN
# ============================================================

def main():
    semester  = prompt_semester()
    do_resume = prompt_resume()

    print(f"\n  Starting scraper for Semester {semester}...")
    print(f"  USN file : {config.USN_FILE}")
    print(f"  Output   : {config.OUTPUT_FILE}\n")

    issues = config.validate()
    for issue in issues:
        log.warning(f"CONFIG WARNING: {issue}")

    if semester not in config.SEMESTER_URLS:
        log.error(f"Semester {semester} not in SEMESTER_URLS. Exiting.")
        sys.exit(1)

    url = config.SEMESTER_URLS[semester]
    log.info(f"Semester {semester} → {url}")

    # ------------------------------------------------
    # Load USNs
    # ------------------------------------------------
    usn_list = load_usn_list(config.USN_FILE)

    # ------------------------------------------------
    # Checkpoint / resume
    # ------------------------------------------------
    if not do_resume:
        start_idx = 0
        log.info("User chose to restart from scratch.")
    else:
        last_usn  = ckpt.load_checkpoint(config.CHECKPOINT_FILE)
        start_idx = ckpt.resolve_start_index(usn_list, last_usn)

    remaining = usn_list[start_idx:]
    log.info(f"Processing {len(remaining)} USN(s) (starting at index {start_idx}).")

    # ------------------------------------------------
    # Browser init
    # ------------------------------------------------
    driver = browser.init_driver()
    driver.get(url)
    time.sleep(config.DELAY)

    all_students : list[dict] = []
    failed_usns  : list[str]  = []

    # ------------------------------------------------
    # Main loop
    # ------------------------------------------------
    total    = len(remaining)
    progress = Progress(total, start_index=start_idx)

    print()  # blank line before progress bar starts

    for i, usn in enumerate(remaining, 1):
        log.info(f"--- [{i}/{total}] {usn} ---")
        progress.update(usn, "starting")

        success = False

        for usn_attempt in range(1, config.MAX_USN_RETRIES + 1):
            try:
                driver.get(url)
                time.sleep(config.DELAY)

                progress.set_status("solving captcha")
                browser.submit_usn(driver, url, usn)

                progress.set_status("scraping")
                data = scraper.scrape_student(driver, usn, semester)

                if data is not None:
                    all_students.append(data)
                    ckpt.save_checkpoint(config.CHECKPOINT_FILE, usn)
                    success = True
                    progress.mark_success()
                    break

                else:
                    log.warning(f"[{usn}] Scrape returned None (attempt {usn_attempt})")
                    progress.set_status(f"retry {usn_attempt}")

            except ValueError as e:
                log.error(str(e))
                break

            except RuntimeError as e:
                log.error(str(e))
                break

            except Exception as e:
                log.error(f"[{usn}] Unexpected error (attempt {usn_attempt}): {e}",
                          exc_info=True)
                progress.set_status(f"error, retry {usn_attempt}")
                driver.get(url)
                time.sleep(config.DELAY)

        if not success:
            failed_usns.append(usn)
            progress.mark_failed()
            log.warning(f"[{usn}] Added to failed list.")

    progress.finish()

    # ------------------------------------------------
    # Cleanup
    # ------------------------------------------------
    driver.quit()
    log.info("Browser closed.")

    accuracy = browser.get_captcha_accuracy()
    log.info(f"Captcha accuracy this run: {accuracy:.1%}")

    # ------------------------------------------------
    # Write outputs
    # ------------------------------------------------
    if all_students:
        exporter.write_excel(all_students, config.OUTPUT_FILE, semester)
    else:
        log.warning("No student data collected — Excel not written.")

    write_failed(failed_usns, config.FAILED_FILE)

    if not failed_usns:
        ckpt.clear_checkpoint(config.CHECKPOINT_FILE)

    log.info(
        f"\nDone. Scraped: {len(all_students)} | "
        f"Failed: {len(failed_usns)} | "
        f"Captcha accuracy: {accuracy:.1%}"
    )


if __name__ == "__main__":
    main()
