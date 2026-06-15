import threading
import time


from src.core.automation import Automation


class FakeKB:
    def __init__(self):
        self.presses = []

    def press(self, k):
        self.presses.append(str(k))

    def release(self, k):
        pass


def test_disabled_returns_immediately(log):
    a = Automation(
        {"enabled": False, "actions": [{"name": "x", "key": "1", "interval_ms": 10, "enabled": True}]},
        lambda: (True, True), threading.Event(), log,
    )
    a.run()  # enabled=False -> мгновенный выход, не зависает
    assert True


def test_timing_master_gate_and_disabled_skip(log):
    cfg = {
        "enabled": True,
        "only_when_foreground": False,
        "actions": [
            {"name": "life", "key": "1", "interval_ms": 50, "enabled": True},
            {"name": "off", "key": "3", "interval_ms": 20, "enabled": False},
        ],
    }
    stop = threading.Event()
    master = {"on": False}
    a = Automation(cfg, lambda: (master["on"], True), stop, log)
    a._kb = FakeKB()
    a.start()

    time.sleep(0.12)
    assert len(a._kb.presses) == 0  # мастер выключен -> тишина

    master["on"] = True
    time.sleep(0.32)
    master["on"] = False
    stop.set()
    a.join(timeout=1)

    life = sum(1 for p in a._kb.presses if p.endswith("'1'"))
    off = sum(1 for p in a._kb.presses if p.endswith("'3'"))
    assert off == 0          # отключённое действие не сработало
    assert life >= 3         # ~6 ожидается за 0.32с @50мс (нижняя граница с запасом)
