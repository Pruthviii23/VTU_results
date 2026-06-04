import logging
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoAlertPresentException,
    TimeoutException,
    UnexpectedAlertPresentException,
)

import config
import ocr

log = logging.getLogger(__name__)

# ============================================================
# CAPTCHA STATS  (tracked per run for accuracy monitoring)
# ============================================================

_captcha_attempts = 0
_captcha_successes = 0


def get_captcha_accuracy() -> float:
    if _captcha_attempts == 0:
        return 1.0
    return _captcha_successes / _captcha_attempts


# ============================================================
# DRIVER
# ============================================================

def init_driver() -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless")   # uncomment for headless mode
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    log.info("Chrome driver initialised.")
    return driver


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _dismiss_any_alert(driver) -> str | None:
    """
    Attempts to switch to any open alert and accept it.
    Returns the alert text, or None if no alert present.
    """
    try:
        alert = driver.switch_to.alert
        text  = alert.text
        alert.accept()
        return text
    except NoAlertPresentException:
        return None


def _wait_for_alert(driver, timeout: float = 3.0) -> str | None:
    """
    Waits up to `timeout` seconds for an alert.
    Returns alert text if found, None otherwise.
    """
    try:
        WebDriverWait(driver, timeout).until(EC.alert_is_present())
        return _dismiss_any_alert(driver)
    except TimeoutException:
        return None


def _enter_usn(wait, usn: str):
    usn_box = wait.until(EC.presence_of_element_located((By.NAME, "lns")))
    usn_box.clear()
    usn_box.send_keys(usn)


def _get_captcha_element(wait):
    return wait.until(
        EC.presence_of_element_located(
            (By.XPATH, "//img[contains(@src,'captcha')]")
        )
    )


def _submit(driver, wait):
    btn = wait.until(EC.element_to_be_clickable((By.ID, "submit")))
    btn.click()


def _results_loaded(wait) -> bool:
    """Returns True if the results table is present."""
    try:
        # Wait for table AND at least one non-empty cell
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "divTableRow")))
        wait.until(
            lambda d: d.find_element(
                By.CLASS_NAME, "divTableCell"
            ).text.strip() != ""
        )
        return True
    except TimeoutException:
        return False


# ============================================================
# PUBLIC: SUBMIT ONE USN
# ============================================================

def submit_usn(driver, url: str, usn: str) -> bool:
    """
    Full flow: enter USN → solve captcha → submit → confirm results loaded.

    Returns True on success.
    Raises ValueError  if the USN itself is rejected by the site.
    Raises RuntimeError if captcha fails after MAX_CAPTCHA_RETRIES attempts.
    """
    global _captcha_attempts, _captcha_successes

    wait = WebDriverWait(driver, config.WAIT_TIMEOUT)

    for attempt in range(1, config.MAX_CAPTCHA_RETRIES + 1):
        try:
            _enter_usn(wait, usn)

            captcha_el  = _get_captcha_element(wait)
            prediction  = ocr.predict_captcha(captcha_el)

            _captcha_attempts += 1

            if prediction is None:
                log.warning(f"[{usn}] Captcha OCR rejected (attempt {attempt})")
                driver.refresh()
                time.sleep(config.DELAY)
                continue

            log.info(f"[{usn}] Captcha attempt {attempt}: {prediction}")

            captcha_box = driver.find_element(By.NAME, "captchacode")
            captcha_box.clear()
            captcha_box.send_keys(prediction)

            _submit(driver, wait)

            # ------------------------------------------------
            # Check for alert (invalid captcha / invalid USN)
            # ------------------------------------------------
            alert_text = _wait_for_alert(driver, timeout=3.0)

            if alert_text is not None:
                log.warning(f"[{usn}] Alert: '{alert_text}'")

                if "Invalid captcha" in alert_text:
                    time.sleep(config.DELAY)
                    continue

                elif "Invalid" in alert_text and "USN" in alert_text:
                    raise ValueError(f"USN rejected by site: {usn}")

                else:
                    # Unknown alert — log and retry
                    log.warning(f"[{usn}] Unknown alert text: '{alert_text}' — retrying")
                    driver.get(url)
                    time.sleep(config.DELAY)
                    continue

            # ------------------------------------------------
            # No alert — check results loaded
            # ------------------------------------------------
            if _results_loaded(wait):
                _captcha_successes += 1

                # Accuracy health check
                accuracy = get_captcha_accuracy()
                if accuracy < config.CAPTCHA_WARN_RATE:
                    log.warning(
                        f"Captcha accuracy dropped to "
                        f"{accuracy:.0%} — model may need retraining."
                    )

                log.info(f"[{usn}] Results loaded ✓")
                return True

            # Results didn't load but no alert either — unknown state
            log.warning(f"[{usn}] Unknown page state after submit (attempt {attempt})")
            driver.get(url)
            time.sleep(config.DELAY)

        except (ValueError, RuntimeError):
            raise

        except UnexpectedAlertPresentException:
            _dismiss_any_alert(driver)
            driver.get(url)
            time.sleep(config.DELAY)

        except Exception as e:
            log.warning(f"[{usn}] Browser error on attempt {attempt}: {e}")
            driver.get(url)
            time.sleep(config.DELAY)

    raise RuntimeError(
        f"[{usn}] Captcha failed after {config.MAX_CAPTCHA_RETRIES} attempts."
    )
