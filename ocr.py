import re
import logging
from io import BytesIO

import cv2
import numpy as np
from PIL import Image
from tensorflow.keras.models import load_model
from tensorflow.keras import backend as K

import config

log = logging.getLogger(__name__)

# ============================================================
# MODEL LOAD
# ============================================================

_model = None


def get_model():
    """Lazy-loads the CRNN model once and caches it."""
    global _model
    if _model is None:
        log.info(f"Loading CRNN model from {config.MODEL_PATH}")
        _model = load_model(config.MODEL_PATH, compile=False)
        log.info("Model loaded successfully.")
    return _model


# ============================================================
# CHARACTER MAP
# ============================================================

_num_to_char = {idx: ch for idx, ch in enumerate(config.CHARACTERS)}


# ============================================================
# PREPROCESSING
# ============================================================

def _preprocess(image_bytes: bytes) -> np.ndarray:
    """
    Accepts raw PNG bytes from a Selenium element screenshot.
    Returns a normalised (H, W, 1) float32 array ready for the model.
    Uses element.screenshot_as_png to avoid HiDPI coordinate mismatch.
    """
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    gray  = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur  = cv2.GaussianBlur(gray, (5, 5), 0)

    _, thresh = cv2.threshold(
        blur, 0, 255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    kernel = np.ones((2, 2), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    thresh = 255 - thresh   # invert

    thresh = cv2.resize(thresh, (config.IMG_WIDTH, config.IMG_HEIGHT))
    thresh = thresh.astype(np.float32) / 255.0
    thresh = np.expand_dims(thresh, axis=-1)

    return thresh


# ============================================================
# CTC DECODE
# ============================================================

def _decode(pred: np.ndarray) -> list[str]:
    input_len = np.ones(pred.shape[0]) * pred.shape[1]
    decoded   = K.ctc_decode(pred, input_length=input_len, greedy=True)[0][0]
    decoded   = decoded.numpy()

    texts = []
    for seq in decoded:
        text = "".join(
            _num_to_char[n]
            for n in seq
            if n != -1 and n < len(config.CHARACTERS)
        )
        texts.append(text)
    return texts


# ============================================================
# PUBLIC API
# ============================================================

def predict_captcha(captcha_element) -> str | None:
    """
    Accepts a Selenium WebElement (the captcha <img>).
    Returns a 6-character alphanumeric prediction, or None if rejected.

    Using element.screenshot_as_png avoids the HiDPI coordinate bug
    that affects full-page screenshot + crop approaches.
    """
    try:
        png_bytes = captcha_element.screenshot_as_png
        image     = _preprocess(png_bytes)
        image     = np.expand_dims(image, axis=0)

        model     = get_model()
        pred      = model.predict(image, verbose=0)
        texts     = _decode(pred)
        raw       = texts[0] if texts else ""

        # Strip anything that isn't alphanumeric
        cleaned = re.sub(r'[^A-Za-z0-9]', '', raw)

        if len(cleaned) != 6:
            log.debug(f"OCR rejected (len={len(cleaned)}): '{cleaned}'")
            return None

        return cleaned

    except Exception as e:
        log.warning(f"predict_captcha error: {e}")
        return None
