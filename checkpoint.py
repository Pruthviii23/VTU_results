import os
import logging

log = logging.getLogger(__name__)


def load_checkpoint(path: str) -> str | None:
    """
    Returns the last successfully scraped USN string,
    or None if no checkpoint exists.
    """
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            usn = f.read().strip()
            if usn:
                log.info(f"Checkpoint found: resuming after {usn}")
                return usn
    except Exception as e:
        log.warning(f"Could not read checkpoint: {e}")
    return None


def save_checkpoint(path: str, usn: str):
    """
    Writes the last successfully scraped USN to the checkpoint file.
    Only call this AFTER the student data has been appended to the list.
    """
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            f.write(usn)
    except Exception as e:
        log.warning(f"Could not save checkpoint for {usn}: {e}")


def resolve_start_index(usn_list: list[str], last_usn: str | None) -> int:
    """
    Given the full USN list and the last checkpointed USN,
    returns the index to start from.

    - If last_usn is None       → start from 0
    - If last_usn found in list → start from next index
    - If last_usn not found     → warn and start from 0
      (handles the case where usn_list.xlsx was edited between runs)
    """
    if last_usn is None:
        return 0

    try:
        idx = usn_list.index(last_usn)
        log.info(f"Resuming from index {idx + 1} (after {last_usn})")
        return idx + 1
    except ValueError:
        log.warning(
            f"Checkpointed USN '{last_usn}' not found in current USN list. "
            f"This usually means usn_list.xlsx was edited between runs. "
            f"Starting from the beginning."
        )
        return 0


def clear_checkpoint(path: str):
    """Deletes checkpoint file on successful full completion."""
    try:
        if os.path.exists(path):
            os.remove(path)
            log.info("Checkpoint cleared — run completed successfully.")
    except Exception as e:
        log.warning(f"Could not clear checkpoint: {e}")
