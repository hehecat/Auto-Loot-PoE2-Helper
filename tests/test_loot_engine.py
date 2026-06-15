import time

from src.core.loot_engine import LootEngine

REGION = {"left": 100, "top": 50, "width": 400, "height": 400}
SHAPE = (400, 400, 3)  # центр кадра (200, 200)


class MockMouse:
    def __init__(self):
        self.clicks = []
        self.pos = (0, 0)

    def move_click(self, x, y, **kwargs):
        self.clicks.append((x, y))

    def position(self):
        return self.pos


def test_pick_once_nearest_in_radius_with_screen_offset(log):
    mm = MockMouse()
    e = LootEngine(mm, REGION, [0, 0], 100, 0, log, dedup_px=20, dedup_ms=300)
    assert e.pick_once([(210, 210, 9), (390, 390, 9)], SHAPE)
    assert mm.clicks == [(310, 260)]  # 100+210, 50+210


def test_anti_double_click(log):
    mm = MockMouse()
    e = LootEngine(mm, REGION, [0, 0], 100, 0, log, dedup_px=20, dedup_ms=300)
    pts = [(210, 210, 9)]
    assert e.pick_once(pts, SHAPE)
    assert not e.pick_once(pts, SHAPE)


def test_cooldown(log):
    mm = MockMouse()
    e = LootEngine(mm, REGION, [0, 0], 100, 200, log, dedup_px=1, dedup_ms=0)
    assert e.pick_once([(205, 205, 9)], SHAPE)
    assert not e.pick_once([(195, 195, 9)], SHAPE)
    time.sleep(0.22)
    assert e.pick_once([(195, 195, 9)], SHAPE)


def test_nearest_of_many(log):
    mm = MockMouse()
    e = LootEngine(mm, REGION, [0, 0], 150, 0, log, dedup_px=1, dedup_ms=0)
    e.pick_once([(260, 200, 9), (220, 200, 9), (300, 200, 9)], SHAPE)
    assert mm.clicks == [(320, 250)]  # ближайший к центру = 220 -> 100+220, 50+200


def test_lazy_pick_at_from_cursor(log):
    mm = MockMouse()
    e = LootEngine(mm, REGION, [0, 0], 450, 0, log, dedup_px=1, dedup_ms=0)
    assert e.pick_at([(320, 310, 9), (50, 50, 9)], (300, 300), 60)
    assert mm.clicks == [(420, 360)]


def test_lazy_ignores_out_of_radius(log):
    mm = MockMouse()
    e = LootEngine(mm, REGION, [0, 0], 450, 0, log, dedup_px=1, dedup_ms=0)
    assert not e.pick_at([(50, 50, 9)], (300, 300), 60)


def test_targets_in_radius(log):
    mm = MockMouse()
    e = LootEngine(mm, REGION, [0, 0], 100, 0, log)
    assert len(e.targets_in_radius([(210, 210, 9), (390, 390, 9)], SHAPE)) == 1
