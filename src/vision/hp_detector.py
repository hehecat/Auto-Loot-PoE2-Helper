"""通过屏幕左下角血球颜色检测 HP 等级。

获取血球区域的垂直中心切片，测量"HP 红色"填充像素的比例。
血球从下往上填充，因此红色像素比例 ≈ 当前 HP%。
"""
import cv2
import numpy as np

# PoE2 HP 血球：深红色（HSV H~0-12，高饱和度 S，中等亮度 V）
_HP_LOW = np.array([0, 90, 40], dtype=np.uint8)
_HP_HIGH = np.array([12, 255, 220], dtype=np.uint8)

# 红色的第二个范围（H 环绕：168-179）
_HP_LOW2 = np.array([168, 90, 40], dtype=np.uint8)
_HP_HIGH2 = np.array([179, 255, 220], dtype=np.uint8)

_DEFAULT_REGION = {"x": 0.01, "y": 0.84, "w": 0.10, "h": 0.15}


def detect_hp_ratio(frame_bgr, region=None):
    """返回近似的 HP 百分比（0.0 = 死亡，1.0 = 满血）。

    region: dict(x, y, w, h) — 相对于帧大小的比例（0..1）。
    出错时返回 1.0（假设 HP 满，避免频繁使用血瓶）。
    """
    if region is None:
        region = _DEFAULT_REGION

    fh, fw = frame_bgr.shape[:2]
    x1 = max(0, int(region["x"] * fw))
    y1 = max(0, int(region["y"] * fh))
    x2 = min(fw, int((region["x"] + region["w"]) * fw))
    y2 = min(fh, int((region["y"] + region["h"]) * fh))

    crop = frame_bgr[y1:y2, x1:x2]
    if crop.size == 0:
        return 1.0

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, _HP_LOW, _HP_HIGH)
    mask2 = cv2.inRange(hsv, _HP_LOW2, _HP_HIGH2)
    mask = cv2.bitwise_or(mask, mask2)

    # 中心垂直切片（宽度的 1/5）
    cw = crop.shape[1]
    sw = max(2, cw // 5)
    cx = cw // 2
    strip = mask[:, max(0, cx - sw // 2): cx + sw // 2 + 1]

    filled = int(cv2.countNonZero(strip))
    total = int(strip.size)
    return filled / max(total, 1)
