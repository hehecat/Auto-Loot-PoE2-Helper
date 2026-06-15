"""Benchmark: замер FPS захвата и времени детекции.

Запуск:
    python tools/benchmark.py                  # стандартный тест
    python tools/benchmark.py --duration 10    # тест 10 секунд
    python tools/benchmark.py --backend mss    # тест с mss бэкендом
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
import numpy as np

from src.capture.screen import ScreenCapture
from src.capture.window import GameWindow
from src.config_manager import load_config
from src.vision.color_detector import ColorDetector


def benchmark_capture(cap, region, duration=5.0, label=""):
    """Замерить FPS захвата."""
    frames = 0
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < duration:
        frame = cap.grab(region)
        if frame is not None:
            frames += 1
    elapsed = time.perf_counter() - t0
    fps = frames / elapsed if elapsed > 0 else 0
    print(f"  [{label}] Захват: {fps:.1f} FPS ({frames} кадров за {elapsed:.1f}с)")
    return fps


def benchmark_detection(frame, detector, iterations=100):
    """Замерить время детекции."""
    if frame is None:
        print("  Детекция: нет кадра для теста")
        return 0

    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        detector.detect(frame)
        times.append(time.perf_counter() - t0)

    avg_ms = np.mean(times) * 1000
    p95_ms = np.percentile(times, 95) * 1000
    max_ms = np.max(times) * 1000
    print(f"  Детекция: avg={avg_ms:.1f}ms, p95={p95_ms:.1f}ms, max={max_ms:.1f}ms")
    return avg_ms


def benchmark_full(frame, detector, engine, iterations=50):
    """Замерить полный цикл: захват + детекция + подбор."""
    if frame is None:
        print("  Полный цикл: нет кадра")
        return

    times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        points, mask = detector.detect(frame)
        in_radius = engine.targets_in_radius(points, frame.shape)
        times.append(time.perf_counter() - t0)

    avg_ms = np.mean(times) * 1000
    print(f"  Полный цикл: avg={avg_ms:.1f}ms ({1000/avg_ms:.0f}理论 FPS)")


def main():
    parser = argparse.ArgumentParser(description="Benchmark Auto Loot")
    parser.add_argument("--duration", type=float, default=5.0, help="длительность теста захвата (сек)")
    parser.add_argument("--backend", default=None, help="бэкенд захвата (dxcam|mss)")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)
    backend = args.backend or cfg["capture"]["backend"]

    print(f"=== Auto Loot Benchmark ===")
    print(f"Бэкенд: {backend}")
    print()

    win = GameWindow(cfg["game"]["window_title"])
    region = win.get_region() if win.find() else GameWindow.primary_region()
    print(f"Регион: {region}")
    print()

    cap = ScreenCapture(backend)
    print(f"Захват: backend={cap.backend}")
    fps = benchmark_capture(cap, region, args.duration, "warmup")
    benchmark_capture(cap, region, args.duration, "main")

    frame = cap.grab(region)
    if frame is not None:
        print(f"  Кадр: {frame.shape[1]}x{frame.shape[0]}")
        print()

        v = cfg["vision"]
        detector = ColorDetector(
            markers=[cfg["filter"]["marker_rgb"]],
            hue_tol=v.get("hue_tolerance", 8),
            sat_min=v.get("sat_min", 120),
            val_min=v.get("val_min", 120),
            min_blob_area=v.get("min_blob_area", 12),
            close_px=v.get("close_px", 3),
        )
        print("Детекция:")
        benchmark_detection(frame, detector)

        from src.core.loot_engine import LootEngine
        from src.input.mouse import Mouse

        mouse = Mouse(human_move=False)
        engine = LootEngine(
            mouse=mouse, region=region,
            center_offset=[0, 0],
            radius=cfg["loot"]["pickup_radius_px"],
            cooldown_ms=0, log=None,
        )
        print()
        print("Полный цикл:")
        benchmark_full(frame, detector, engine)

    print()
    print("=== Benchmark завершён ===")


if __name__ == "__main__":
    main()
