import numpy as np

from src.vision.color_detector import ColorDetector, normalize_colors, rgb_to_hsv_bounds


def test_normalize_colors():
    assert normalize_colors([0, 255, 255]) == [[0, 255, 255]]
    assert normalize_colors([[0, 255, 255], [1, 2, 3]]) == [[0, 255, 255], [1, 2, 3]]
    assert normalize_colors([]) == []


def test_hsv_bounds_cyan():
    ranges = rgb_to_hsv_bounds([0, 255, 255], 8, 120, 120)
    lo, hi = ranges[0]
    assert lo[0] <= 90 <= hi[0]  # циан ~ H=90 в OpenCV


def test_hsv_bounds_red_wrap():
    # красный [255,0,0] -> H=0 -> должно дать два диапазона (wrap-around)
    ranges = rgb_to_hsv_bounds([255, 0, 0], 8, 120, 120)
    assert len(ranges) == 2
    # первый диапазон: 0..8
    assert ranges[0][0][0] == 0 and ranges[0][1][0] == 8
    # второй диапазон: 171..179
    assert ranges[1][0][0] == 171 and ranges[1][1][0] == 179


def test_single_color_centroid():
    det = ColorDetector([0, 255, 255], min_blob_area=10)
    f = np.zeros((200, 300, 3), np.uint8)
    f[50:70, 100:160] = (255, 255, 0)  # BGR cyan
    pts, _ = det.detect(f)
    assert len(pts) == 1
    cx, cy, _ = pts[0]
    assert 125 <= cx <= 135 and 55 <= cy <= 65


def test_multi_color():
    det = ColorDetector([[0, 255, 255], [255, 0, 255]], min_blob_area=10)
    f = np.zeros((120, 200, 3), np.uint8)
    f[20:40, 20:40] = (255, 255, 0)    # cyan
    f[20:40, 150:170] = (255, 0, 255)  # magenta
    pts, _ = det.detect(f)
    assert len(pts) == 2


def test_min_area_filters_noise():
    det = ColorDetector([0, 255, 255], min_blob_area=500)
    f = np.zeros((100, 100, 3), np.uint8)
    f[10:14, 10:14] = (255, 255, 0)  # крошечное пятно
    pts, _ = det.detect(f)
    assert pts == []


def test_back_compat_low_high():
    det = ColorDetector([0, 255, 255])
    assert det.low is not None and det.high is not None
    assert len(det.bounds) == 1


def test_close_merges_fragments():
    # два близких куска (как фрагменты одной полупрозрачной подписи) -> один блоб
    det = ColorDetector([0, 255, 255], min_blob_area=10, close_px=9)
    f = np.zeros((60, 120, 3), np.uint8)
    f[20:30, 20:45] = (255, 255, 0)
    f[20:30, 50:75] = (255, 255, 0)  # зазор 5px
    pts, _ = det.detect(f)
    assert len(pts) == 1


def test_no_close_keeps_fragments():
    det = ColorDetector([0, 255, 255], min_blob_area=10, close_px=0)
    f = np.zeros((60, 120, 3), np.uint8)
    f[20:30, 20:45] = (255, 255, 0)
    f[20:30, 50:75] = (255, 255, 0)
    pts, _ = det.detect(f)
    assert len(pts) == 2
