"""OCR детекция: чтение текста подписей предметов на экране.

Использует pytesseract для распознавания текста в区域内 рядом с обнаруженными
цветовыми маркерами. Опциональная зависимость — если pytesseract не установлен,
модуль работает в режиме заглушки.
"""
import logging

import cv2
import numpy as np

_log = logging.getLogger("autoloot.ocr")

_HAS_TESSERACT = False
try:
    import pytesseract
    _HAS_TESSERACT = True
except ImportError:
    pass


def read_text_around(frame_bgr, x, y, radius=40):
    """Прочитать текст в области вокруг точки (x, y) на кадре.

    Возвращает распознанный текст или пустую строку.
    """
    if not _HAS_TESSERACT:
        return ""

    h, w = frame_bgr.shape[:2]
    x1 = max(0, x - radius)
    y1 = max(0, y - radius)
    x2 = min(w, x + radius)
    y2 = min(h, y + radius)

    crop = frame_bgr[y1:y2, x1:x2]
    if crop.size == 0:
        return ""

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    try:
        text = pytesseract.image_to_string(thresh, config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 ")
        return text.strip()
    except Exception:
        return ""


def read_all_labels(frame_bgr, points, radius=40):
    """Прочитать текст подписей для всех найденных точек.

    Возвращает [(x, y, text), ...]
    """
    results = []
    for x, y, _area in points:
        text = read_text_around(frame_bgr, x, y, radius)
        if text:
            results.append((x, y, text))
    return results
