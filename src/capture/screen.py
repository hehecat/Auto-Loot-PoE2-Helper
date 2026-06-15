"""Быстрый захват региона экрана: dxcam (DirectX) с фолбэком на mss. Возвращает BGR numpy-кадр."""
import numpy as np


class ScreenCapture:
    def __init__(self, backend="dxcam"):
        self.backend = backend
        self._dxcam = None
        self._mss = None
        self._last_frame = None
        self._init_backend()

    def _init_backend(self):
        if self.backend == "dxcam":
            try:
                import dxcam

                self._dxcam = dxcam.create(output_color="BGR")
                if self._dxcam is None:
                    raise RuntimeError("dxcam.create() вернул None")
                return
            except Exception:
                self.backend = "mss"  # тихий фолбэк

        self._init_mss()

    def _init_mss(self):
        import mss

        self._mss = mss.mss()
        self.backend = "mss"

    def grab(self, region):
        """region: dict(left, top, width, height). Возвращает BGR-кадр (H, W, 3) или None."""
        if self.backend == "dxcam":
            l, t = region["left"], region["top"]
            r, b = l + region["width"], t + region["height"]
            try:
                frame = self._dxcam.grab(region=(l, t, r, b))
            except Exception:
                # регион вне основного монитора (окно на другом мониторе /
                # отрицательные координаты) -> переключаемся на mss
                self._init_mss()
                return self.grab(region)
            if frame is None:
                return self._last_frame  # нового кадра нет — отдаём предыдущий
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
