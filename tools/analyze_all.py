"""Пакетный анализ всех _calib_* пар."""
import os, re

import cv2
import numpy as np

COLORS = [
    ("currency (orange)", [255, 120, 0]),
    ("fragments (purple)", [180, 0, 255]),
    ("waystones (cyan)", [50, 200, 255]),
    ("uniques (green)", [0, 255, 0]),
    ("gems (red)", [255, 40, 40]),
    ("marker_rgb (pink)", [255, 0, 200]),
]

DIR = os.path.join(os.path.dirname(__file__), "..", "_debug")

def rgb_to_h(rgb):
    px = np.uint8([[[rgb[2], rgb[1], rgb[0]]]])
    return int(cv2.cvtColor(px, cv2.COLOR_BGR2HSV)[0][0][0])

def analyze(frame_path, mask_path):
    frame = cv2.imread(frame_path)
    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
    if frame is None or mask is None:
        return None
    fh, fw = frame.shape[:2]
    mh, mw = mask.shape[:2]

    _, bin_mask = cv2.threshold(mask, 128, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(bin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    areas = [cv2.contourArea(c) for c in contours] if contours else [0]
    big = sum(1 for a in areas if a >= 200)

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    pix_counts = {}
    for name, rgb in COLORS:
        h = rgb_to_h(rgb)
        lo = np.array([max(0, h-8), 120, 120], dtype=np.uint8)
        hi = np.array([min(179, h+8), 255, 255], dtype=np.uint8)
        pix_counts[name] = cv2.countNonZero(cv2.inRange(hsv, lo, hi))

    return {
        "w": fw, "h": fh,
        "blobs": len(contours),
        "big_blobs": big,
        "pixels": pix_counts,
    }

# collect pairs
pairs = {}
for f in os.listdir(DIR):
    m = re.match(r'_calib_frame_(\d+)\.png', f)
    if m:
        ts = m.group(1)
        mask = f'_calib_mask_{ts}.png'
        if os.path.exists(os.path.join(DIR, mask)):
            pairs[ts] = (os.path.join(DIR, f), os.path.join(DIR, mask))

print(f"Найдено пар: {len(pairs)}")
print()

results = []
for ts in sorted(pairs)[:8]:
    r = analyze(*pairs[ts])
    if r:
        results.append((ts, r))
        pix = " | ".join(f"{k.split()[0]}={v}" for k, v in sorted(r['pixels'].items()))
        print(f"  {ts}  {r['w']}x{r['h']}  blobs={r['blobs']}  >=200={r['big_blobs']}")
        print(f"       pixels: {pix}")

print()
# summary
if results:
    avg_blobs = np.mean([r['blobs'] for _, r in results])
    avg_big = np.mean([r['big_blobs'] for _, r in results])
    print(f"Среднее: blobs={avg_blobs:.0f}  >=200={avg_big:.0f}")
