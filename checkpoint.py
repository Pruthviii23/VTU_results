"""
Checkpoint module
=================
Stores the last successfully scraped USN along with scheme and semester,
so a resumed run never re-asks those questions.

File format (single line):
    <USN>|<scheme>|<semester>
Example:
    1AM22AI089|2022|5
"""

import os
import logging

log = logging.getLogger(__name__)

_SEP = "|"


def load_checkpoint(path: str) -> dict | None:
    """
    Returns {"usn": str, "scheme": str, "semester": int}
    or None if no checkpoint exists / file is malformed.
    """
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            line = f.read().strip()
        if not line:
            return None
        parts = line.split(_SEP)
        if len(parts) != 3:
            log.warning(f"Checkpoint format unrecognised ('{line}') — ignoring.")
            return None
        usn, scheme, semester = parts
        ckpt = {"usn": usn.strip(), "scheme": scheme.strip(), "semester": int(semester)}
        log.info(f"Checkpoint found: {ckpt}")
        return ckpt
    except Exception as e:
        log.warning(f"Could not read checkpoint: {e}")
        return None


def save_checkpoint(path: str, usn: str, scheme: str, semester: int):
    """
    Writes checkpoint. Call only AFTER the student has been
    successfully appended to all_students.
    """
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            f.write(f"{usn}{_SEP}{scheme}{_SEP}{semester}")
    except Exception as e:
        log.warning(f"Could not save checkpoint for {usn}: {e}")


def resolve_start_index(usn_list: list[str], last_usn: str | None) -> int:
    """
    Returns the index to start from given the checkpointed USN string.

    - None        → start from 0
    - Found       → start from next index
    - Not found   → warn and start from 0
      (handles the case where usn_list.xlsx was edited between runs)
    """
    if last_usn is None:
        return 0
    try:
        idx = usn_list.index(last_usn.upper())
        log.info(f"Resuming from index {idx + 1} (after {last_usn})")
        return idx + 1
    except ValueError:
        log.warning(
            f"Checkpointed USN '{last_usn}' not in current USN list — "
            f"usn_list.xlsx may have changed. Starting from beginning."
        )
        return 0


def clear_checkpoint(path: str):
    """Deletes checkpoint file after a clean full-run completion."""
    try:
        if os.path.exists(path):
            os.remove(path)
            log.info("Checkpoint cleared — run completed successfully.")
    except Exception as e:
        log.warning(f"Could not clear checkpoint: {e}")