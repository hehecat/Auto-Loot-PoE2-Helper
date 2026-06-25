"""OCR 检测：读取屏幕上物品标签的文字。

使用 pytesseract 识别检测到的颜色标记附近区域内的文本。
可选依赖 — 如果未安装 pytesseract，模块以桩模式运行。
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
    """读取帧上点 (x, y) 周围区域内的文本。

    返回识别出的文本或空字符串。
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
    """读取所有检测到的点的标签文本。

    返回 [(x, y, text), ...]
    """
    results = []
    for x, y, _area in points:
        text = read_text_around(frame_bgr, x, y, radius)
        if text:
            results.append((x, y, text))
    return results
