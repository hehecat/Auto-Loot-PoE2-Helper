"""Быстрый захват региона экрана: dxcam (DirectX) с фолбэком на mss. Возвращает BGR numpy-кадр.

Поддержка double-buffer: захват в фоновом потоке, основной поток читает последний готовый кадр.
"""
import logging
import threading

import numpy as np

_log = logging.getLogger("autoloot.capture")


class ScreenCapture:
    def __init__(self, backend="dxcam", double_buffer=False):
        self.backend = backend
        self._dxcam = None
        self._mss = None
        self._last_frame = None
        self._double_buffer = double_buffer
        self._buf_lock = threading.Lock()
        self._buf_frame = None
        self._buf_thread = None
        self._buf_stop = threading.Event()
        self._init_backend()

    def _init_backend(self):
        if self.backend == "dxcam":
            try:
                import dxcam

                self._dxcam = dxcam.create(output_color="BGR")
                if self._dxcam is None:
                    raise RuntimeError("dxcam.create() вернул None")
                return
            except Exception as e:
                _log.warning("dxcam недоступен (%s) — фолбэк на mss.", e)
                self.backend = "mss"  # тихий фолбэк

        self._init_mss()

    def _init_mss(self):
        import mss

        self._mss = mss.mss()
        self.backend = "mss"

    def start_buffer(self, region, target_fps=30):
        """Запустить фоновый захват кадров (double-buffer mode)."""
        if not self._double_buffer:
            return

        def _capture_loop():
            interval = 1.0 / target_fps
            while not self._buf_stop.is_set():
                frame = self._grab_raw(region)
                if frame is not None:
                    with self._buf_lock:
                        self._buf_frame = frame
                self._buf_stop.wait(interval)

        self._buf_thread = threading.Thread(target=_capture_loop, daemon=True)
        self._buf_thread.start()

    def stop_buffer(self):
        """Остановить фоновый захват."""
        self._buf_stop.set()
        if self._buf_thread:
            self._buf_thread.join(timeout=1.0)

    def grab(self, region):
        """region: dict(left, top, width, height). Возвращает BGR-кадр (H, W, 3) или None."""
        if self._double_buffer:
            with self._buf_lock:
                if self._buf_frame is not None:
                    self._last_frame = self._buf_frame
                    return self._buf_frame
            return self._last_frame
        return self._grab_raw(region)

    def _grab_raw(self, region):
        """Одиночный захват кадра (без буфера)."""
        if self.backend == "dxcam":
            l, t = region["left"], region["top"]
            r, b = l + region["width"], t + region["height"]
            try:
                frame = self._dxcam.grab(region=(l, t, r, b))
            except Exception:
                self._init_mss()
                return self._grab_raw(region)
            if frame is None:
                return self._last_frame
            self._last_frame = frame
            return frame

        mon = {
            "left": region["left"],
            "top": region["top"],
            "width": region["width"],
            "height": region["height"],
        }
        img = np.asarray(self._mss.grab(mon))  # BGRA
        self._last_frame = np.ascontiguousarray(img[:, :, :3])  # BGR
        return self._last_frame
