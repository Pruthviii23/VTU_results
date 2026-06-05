"""
VTU Results Scraper
===================
Just run:
    python main.py

You will be prompted for scheme and semester.
Everything else uses the defaults in config.py.
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
import report


# ============================================================
# LOGGING  — file only during scraping so progress bar is clean
# ============================================================

os.makedirs(os.path.dirname(config.LOG_FILE) or ".", exist_ok=True)

logging.basicConfig(
    level    = logging.INFO,
    format   = "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt  = "%Y-%m-%d %H:%M:%S",
    handlers = [
        logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
        # StreamHandler intentionally omitted — log lines break the live
        # progress bar.  All activity is captured in LOG_FILE in real time.
    ]
)

log = logging.getLogger("main")


# ============================================================
# PROGRESS TRACKER
# ============================================================

class Progress:
    """
    Live single-line progress bar.

      [████████████░░░░░░░░]  60%  12/20  ✓11 ✗1  ETA 00:01:24  solving captcha  1AM22AI067
    """

    BAR_WIDTH = 20

    def __init__(self, total: int, start_index: int = 0):
        self.total     = total
        self.done      = 0
        self.success   = 0
        self.failed    = 0
        self.current   = ""
        self.status    = ""
        self._start    = time.time()
        self._start_idx = start_index

    def update(self, usn: str, status: str = ""):
        self.current = usn
        self.status  = status
        self._render()

    def mark_success(self):
        self.done    += 1
        self.success += 1
        self.status   = "scraped"
        self._render()

    def mark_failed(self):
        self.done   += 1
        self.failed += 1
        self.status  = "failed"
        self._render()

    def set_status(self, status: str):
        self.status = status
        self._render()

    def finish(self):
        elapsed = self._elapsed_str()
        acc     = self.success / self.done if self.done else 0
        print(
            f"\r  Done — "
            f"{self.success} scraped  "
            f"{self.failed} failed  "
            f"Accuracy {acc:.0%}  "
            f"Time {elapsed}"
            + " " * 20
        )

    def _elapsed_str(self) -> str:
        secs = int(time.time() - self._start)
        return str(datetime.timedelta(seconds=secs))

    def _eta_str(self) -> str:
        if self.done == 0:
            return "--:--:--"
        per_usn   = (time.time() - self._start) / self.done
        remaining = (self.total - self.done) * per_usn
        return str(datetime.timedelta(seconds=int(remaining)))

    def _bar(self) -> str:
        filled = int(self.BAR_WIDTH * self.done / self.total) if self.total else 0
        return "█" * filled + "░" * (self.BAR_WIDTH - filled)

    def _render(self):
        pct      = int(100 * self.done / self.total) if self.total else 0
        absolute = f"{self._start_idx + self.done}/{self._start_idx + self.total}"
        status   = self.status[:18].ljust(18)
        line = (
            f"\r  [{self._bar()}] {pct:>3}%  "
            f"{absolute}  "
            f"✓{self.success} ✗{self.failed}  "
            f"ETA {self._eta_str()}  "
            f"{status}  {self.current}"
        )
        print(line, end="", flush=True)


# ============================================================
# INTERACTIVE PROMPTS
# ============================================================

def prompt_scheme(existing: str | None = None) -> str:
    """Ask user to pick a scheme year. Skipped if resuming."""
    if existing:
        print(f"\n  Resuming with scheme: {existing}")
        return existing

    valid = sorted(config.SUBJECT_CREDITS.keys())

    print("\n" + "=" * 45)
    print("       VTU Results Scraper")
    print("=" * 45)
    print(f"  Available schemes : {valid}")

    while True:
        try:
            raw = input("\n  Enter scheme year (e.g. 2022): ").strip()
            if raw in valid:
                return raw
            print(f"  ✗ '{raw}' not recognised. Choose from {valid}.")
        except (KeyboardInterrupt, EOFError):
            print("\n\n  Cancelled. Exiting.")
            sys.exit(0)


def prompt_semester(existing: int | None = None) -> int:
    """Ask user to pick a semester. Skipped if resuming."""
    if existing is not None:
        print(f"  Resuming with semester: {existing}")
        return existing

    valid = sorted(config.SEMESTER_URLS.keys())
    print(f"\n  Available semesters: {valid}")

    while True:
        try:
            raw = input("  Enter semester number: ").strip()
            sem = int(raw)
            if sem in valid:
                return sem
            print(f"  ✗ '{sem}' not valid. Choose from {valid}.")
        except ValueError:
            print("  ✗ Please enter a number (e.g. 5).")
        except (KeyboardInterrupt, EOFError):
            print("\n\n  Cancelled. Exiting.")
            sys.exit(0)


def prompt_resume(ckpt_data: dict | None) -> bool:
    """
    If a checkpoint exists, ask whether to resume or restart.
    Returns True to resume, False to restart.
    Skipped entirely if no checkpoint.
    """
    if ckpt_data is None:
        return False

    print(
        f"\n  A previous run was interrupted after USN {ckpt_data['usn']}  "
        f"(Scheme {ckpt_data['scheme']}, Sem {ckpt_data['semester']})."
    )

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
# HELPERS
# ============================================================

def load_usn_list(path: str) -> list[str]:
    df = pd.read_excel(path, dtype=str)
    if "USN" not in df.columns:
        raise ValueError(
            f"'USN' column not found in {path}. "
            f"Columns: {df.columns.tolist()}"
        )
    usns = df["USN"].dropna().str.strip().str.upper().tolist()

    seen, unique = set(), []
    for u in usns:
        if u not in seen:
            seen.add(u)
            unique.append(u)

    dupes = len(usns) - len(unique)
    if dupes:
        log.warning(f"{dupes} duplicate USN(s) removed.")

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
# MAIN
# ============================================================

def main():

    # ── Load checkpoint (if any) ─────────────────────────────
    ckpt_data = ckpt.load_checkpoint(config.CHECKPOINT_FILE)
    resuming  = prompt_resume(ckpt_data)

    # ── Scheme & semester ────────────────────────────────────
    if resuming and ckpt_data:
        scheme   = prompt_scheme(existing=ckpt_data["scheme"])
        semester = prompt_semester(existing=ckpt_data["semester"])
    else:
        scheme   = prompt_scheme()
        semester = prompt_semester()

    print(f"\n  USN file : {config.USN_FILE}")
    print(f"  Output   : {config.OUTPUT_FILE}")
    print(f"  Log      : {config.LOG_FILE}\n")

    # ── Startup validation ───────────────────────────────────
    issues = config.validate(scheme)
    for issue in issues:
        print(f"  ⚠  {issue}")
        log.warning(f"CONFIG: {issue}")

    if semester not in config.SEMESTER_URLS:
        print(f"\n  ✗ Semester {semester} has no URL configured. Exiting.")
        sys.exit(1)

    url = config.SEMESTER_URLS[semester]
    log.info(f"Scheme={scheme}  Semester={semester}  URL={url}")

    # ── USN list ─────────────────────────────────────────────
    usn_list = load_usn_list(config.USN_FILE)

    # ── Start index ──────────────────────────────────────────
    if resuming and ckpt_data:
        start_idx = ckpt.resolve_start_index(usn_list, ckpt_data["usn"])
    else:
        start_idx = 0
        log.info("Starting from scratch.")

    remaining = usn_list[start_idx:]
    log.info(f"Processing {len(remaining)} USN(s) from index {start_idx}.")

    # ── Browser ──────────────────────────────────────────────
    driver = browser.init_driver()
    driver.get(url)
    time.sleep(config.DELAY)

    all_students: list[dict] = []
    failed_usns:  list[str]  = []

    # ── Main loop ─────────────────────────────────────────────
    total    = len(remaining)
    progress = Progress(total, start_index=start_idx)

    print()   # blank line before bar

    for i, usn in enumerate(remaining, 1):
        log.info(f"--- [{i}/{total}] {usn} ---")
        progress.update(usn, "starting")

        success = False

        for attempt in range(1, config.MAX_USN_RETRIES + 1):
            try:
                driver.get(url)
                time.sleep(config.DELAY)

                progress.set_status("solving captcha")
                browser.submit_usn(driver, url, usn)

                progress.set_status("scraping")
                data = scraper.scrape_student(driver, usn, semester)

                if data is not None:
                    all_students.append(data)
                    # Checkpoint AFTER successful append
                    ckpt.save_checkpoint(
                        config.CHECKPOINT_FILE, usn, scheme, semester
                    )
                    success = True
                    progress.mark_success()
                    break

                else:
                    log.warning(f"[{usn}] Scrape returned None (attempt {attempt})")
                    progress.set_status(f"retry {attempt}")

            except ValueError as e:
                log.error(str(e))
                break

            except RuntimeError as e:
                log.error(str(e))
                break

            except Exception as e:
                log.error(f"[{usn}] Error attempt {attempt}: {e}", exc_info=True)
                progress.set_status(f"error, retry {attempt}")
                driver.get(url)
                time.sleep(config.DELAY)

        if not success:
            failed_usns.append(usn)
            progress.mark_failed()
            log.warning(f"[{usn}] Added to failed list.")

    progress.finish()

    # ── Cleanup ───────────────────────────────────────────────
    driver.quit()
    log.info("Browser closed.")

    accuracy = browser.get_captcha_accuracy()
    log.info(f"Captcha accuracy: {accuracy:.1%}")

    # ── Write outputs ─────────────────────────────────────────
    print("\n  Writing outputs...")

    if all_students:
        exporter.write_excel(all_students, config.OUTPUT_FILE, semester, scheme)
        print(f"  Excel       → {config.OUTPUT_FILE}")

        pdf_path = config.OUTPUT_FILE.replace(".xlsx", "_report.pdf")
        batch    = f"Scheme {scheme}"
        report.write_pdf(all_students, pdf_path, semester, scheme, batch)

    else:
        log.warning("No student data collected — outputs not written.")
        print("  ⚠  No data collected.")

    write_failed(failed_usns, config.FAILED_FILE)

    if not failed_usns:
        ckpt.clear_checkpoint(config.CHECKPOINT_FILE)

    print(
        f"\n  Scraped : {len(all_students)}"
        f"   Failed : {len(failed_usns)}"
        f"   Captcha accuracy : {accuracy:.1%}"
        f"   Log : {config.LOG_FILE}"
    )


if __name__ == "__main__":
    main()