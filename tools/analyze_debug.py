"""Анализ скриншотов: раскладывает маску по каждому цвету детекции.

Запуск:
    python analyze_debug.py                          # анализ существующих _debug_*
    python analyze_debug.py --frame _calib_frame.png --mask _calib_mask.png
"""
import argparse
import os
import sys

import cv2
import numpy as np

# Цвета детекции (R,G,B) из конфига
COLORS = [
    ("marker_rgb (fallback)", [255, 0, 200]),
    ("currency (orange)", [255, 120, 0]),
    ("fragments (purple)", [180, 0, 255]),
    ("waystones (cyan)", [50, 200, 255]),
    ("uniques (green)", [0, 255, 0]),
    ("gems (red)", [255, 40, 40]),
]

DIR = os.path.join(os.path.dirname(__file__), "..", "_debug")

HUE_TOL = 8
SAT_MIN = 120
VAL_MIN = 120


def rgb_to_hsv_bounds(rgb):
    r, g, b = rgb
    px = np.uint8([[[b, g, r]]])
    h = int(cv2.cvtColor(px, cv2.COLOR_BGR2HSV)[0][0][0])
    return h


def analyze_mask(mask_path, frame_path=None):
    print(f"\n=== Анализ: {os.path.basename(mask_path)} ===")
    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
    if mask is None:
        print("  НЕ УДАЛОСЬ ПРОЧИТАТЬ")
        return
    h, w = mask.shape
    print(f"  Размер: {w}x{h}")

    _, bin_mask = cv2.threshold(mask, 128, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(bin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"  Всего блобов: {len(contours)}")
    areas = [cv2.contourArea(c) for c in contours] if contours else [0]
    areas_str = ", ".join(f"{a:.0f}" for a in sorted(areas, reverse=True)[:10])
    print(f"  Площади (топ-10): {areas_str}")

    if frame_path:
        frame = cv2.imread(frame_path)
        if frame is not None:
            fh, fw = frame.shape[:2]
            print(f"  Кадр: {fw}x{fh}")
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            print(f"\n  --- Разбивка по цветам детекции (hue_tol={HUE_TOL}) ---")
            for name, rgb in COLORS:
                h_center = rgb_to_hsv_bounds(rgb)
                low = np.array([max(0, h_center - HUE_TOL), SAT_MIN, VAL_MIN], dtype=np.uint8)
                high = np.array([min(179, h_center + HUE_TOL), 255, 255], dtype=np.uint8)
                cmask = cv2.inRange(hsv, low, high)
                ccount = cv2.countNonZero(cmask)
                print(f"  {name:30s} H={h_center:3d} range={max(0,h_center-HUE_TOL):3d}-{min(179,h_center+HUE_TOL):3d}  пикселей: {ccount:6d}")

            # центр кадра
            cx, cy = fw // 2, fh // 2
            print(f"\n  Центр кадра: ({cx}, {cy})")

            # ищем белую окружность радиуса
            white = cv2.inRange(hsv, (0, 0, 200), (180, 40, 255))
            circles = cv2.HoughCircles(white, cv2.HOUGH_GRADIENT, 1.2, 50,
                                       param1=50, param2=10, minRadius=50)
            if circles is not None:
                c = circles[0][0]
                ox = int(c[0]) - cx
                oy = int(c[1]) - cy
                print(f"  Круг радиуса: центр=({int(c[0])},{int(c[1])}), R={int(c[2])}")
                print(f"  Смещение круга от центра кадра: ({ox}, {oy})")
            else:
                print(f"  Круг радиуса: не найден (R>=50)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frame", help="путь к _calib_frame_*.png")
    parser.add_argument("--mask", help="путь к _calib_mask_*.png")
    args = parser.parse_args()

    if args.frame and args.mask:
        analyze_mask(args.mask, args.frame)
        return

    # анализируем все _debug_* файлы
    for f in sorted(os.listdir(DIR)):
        if f.startswith("_debug_vis") or f.startswith("_debug_frame"):
            mask_name = f.replace("vis", "mask").replace("frame", "mask")
            mask_path = os.path.join(DIR, mask_name)
            frame_path = os.path.join(DIR, f)
            if os.path.exists(mask_path):
                analyze_mask(mask_path, frame_path)
            else:
                print(f"\n=== {f} — нет парной маски ===")

    # ищем _calib_* файлы
    calib_masks = sorted(f for f in os.listdir(DIR) if f.startswith("_calib_mask"))
    if not calib_masks:
        print("\n=== _calib_* файлов нет. Запусти --calibrate и нажми S для сохранения ===")


if __name__ == "__main__":
    main()
