"""Визуализация региона HP-детекции.

Запуск: python tools/debug_hp.py
Сохраняет _debug/hp_region_debug.png — на нём виден прямоугольник
где программа смотрит орб ХП, и вырезанный регион отдельно.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
import numpy as np

from src.capture.screen import ScreenCapture
from src.capture.window import GameWindow
from src.config_manager import load_config
from src.vision.hp_detector import detect_hp_ratio, _HP_LOW, _HP_HIGH, _HP_LOW2, _HP_HIGH2

cfg = load_config(None)
hp_cfg = cfg.get("hp_flask", {})
region_rel = hp_cfg.get("hp_region", {"x": 0.01, "y": 0.84, "w": 0.10, "h": 0.15})

win = GameWindow(cfg["game"]["window_title"])
region = win.get_region() if win.find() else GameWindow.primary_region()
cap = ScreenCapture(cfg["capture"]["backend"])

print("Захватываю кадр... (убедись что игра видна на экране)")
frame = cap.grab(region)
if frame is None:
    print("Кадр не получен")
    sys.exit(1)

fh, fw = frame.shape[:2]
x1 = max(0, int(region_rel["x"] * fw))
y1 = max(0, int(region_rel["y"] * fh))
x2 = min(fw, int((region_rel["x"] + region_rel["w"]) * fw))
y2 = min(fh, int((region_rel["y"] + region_rel["h"]) * fh))

# рисуем прямоугольник на полном кадре
vis = frame.copy()
cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 3)
cv2.putText(vis, "HP region", (x1, max(20, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

# вырезаем регион и показываем маску
crop = frame[y1:y2, x1:x2]
hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
mask = cv2.bitwise_or(
    cv2.inRange(hsv, _HP_LOW, _HP_HIGH),
    cv2.inRange(hsv, _HP_LOW2, _HP_HIGH2),
)
ratio = detect_hp_ratio(frame, region_rel)

os.makedirs("_debug", exist_ok=True)
cv2.imwrite("_debug/hp_region_debug.png", vis)
cv2.imwrite("_debug/hp_region_crop.png", crop)
cv2.imwrite("_debug/hp_region_mask.png", mask)

print(f"Кадр: {fw}x{fh}")
print(f"HP регион: ({x1},{y1}) -> ({x2},{y2})")
print(f"Определённый HP%: {ratio*100:.0f}%")
print()
print("Файлы сохранены в _debug/:")
print("  hp_region_debug.png — полный кадр с зелёным прямоугольником региона")
print("  hp_region_crop.png  — вырезанный регион (что видит детектор)")
print("  hp_region_mask.png  — маска красного (что считается за HP)")
