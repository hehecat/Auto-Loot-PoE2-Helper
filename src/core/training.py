"""学习模式：通过点击记忆新物品。

用户点击屏幕上的物品，输入名称/类别，机器人会记住该物品的颜色特征
以供未来拾取。

规则保存在 profiles 文件夹中的 custom_rules.yaml 文件中。
"""
import json
import logging
import time
from pathlib import Path

import cv2
import numpy as np

_log = logging.getLogger("autoloot.training")

_RULES_FILE = Path(__file__).resolve().parents[2] / "config" / "profiles" / "custom_rules.json"


def _load_rules():
    if _RULES_FILE.exists():
        try:
            return json.loads(_RULES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"items": []}


def _save_rules(rules):
    _RULES_FILE.parent.mkdir(parents=True, exist_ok=True)
    _RULES_FILE.write_text(json.dumps(rules, indent=2, ensure_ascii=False), encoding="utf-8")


def _sample_region_hsv(frame_bgr, x, y, radius=15):
    """收集点周围区域的 HSV 统计数据。"""
    h, w = frame_bgr.shape[:2]
    x1 = max(0, x - radius)
    y1 = max(0, y - radius)
    x2 = min(w, x + radius)
    y2 = min(h, y + radius)

    crop = frame_bgr[y1:y2, x1:x2]
    if crop.size == 0:
        return None

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    pixels = hsv.reshape(-1, 3)

    return {
        "h_mean": float(np.mean(pixels[:, 0])),
        "s_mean": float(np.mean(pixels[:, 1])),
        "v_mean": float(np.mean(pixels[:, 2])),
        "h_std": float(np.std(pixels[:, 0])),
        "s_std": float(np.std(pixels[:, 1])),
        "v_std": float(np.std(pixels[:, 2])),
        "rgb_center": frame_bgr[y, x][::-1].tolist(),  # BGR -> RGB
    }


class TrainingMode:
    """交互式学习新物品模式。"""

    def __init__(self):
        self.rules = _load_rules()
        self._recording = False
        self._current_item = None

    def start_record(self, name, category="custom"):
        """开始记录新物品。"""
        self._recording = True
        self._current_item = {
            "name": name,
            "category": category,
            "samples": [],
            "added_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        _log.info("开始记录物品 '%s' (分类: %s)。请点击物品。", name, category)

    def add_sample(self, frame_bgr, x, y):
        """按坐标添加物品样本。"""
        if not self._recording or self._current_item is None:
            return False

        sample = _sample_region_hsv(frame_bgr, x, y)
        if sample:
            self._current_item["samples"].append(sample)
            _log.info("样本 #%d 用于 '%s': RGB=%s",
                      len(self._current_item["samples"]),
                      self._current_item["name"],
                      sample["rgb_center"])
            return True
        return False

    def stop_record(self):
        """完成记录并保存物品。"""
        if not self._recording or self._current_item is None:
            return None

        if self._current_item["samples"]:
            samples = self._current_item["samples"]
            avg_h = np.mean([s["h_mean"] for s in samples])
            avg_s = np.mean([s["s_mean"] for s in samples])
            avg_v = np.mean([s["v_mean"] for s in samples])
            max_h_std = max(s["h_std"] for s in samples)

            self._current_item["avg_hsv"] = [float(avg_h), float(avg_s), float(avg_v)]
            self._current_item["hue_tolerance"] = max(5, int(max_h_std * 2))
            self._current_item["sat_min"] = max(50, int(avg_s - 40))
            self._current_item["val_min"] = max(50, int(avg_v - 40))
            self._current_item["marker_rgb"] = self._current_item["samples"][0]["rgb_center"]

            self.rules["items"].append(self._current_item)
            _save_rules(self.rules)
            _log.info("物品 '%s' 已保存 (%d 个样本)。",
                      self._current_item["name"], len(samples))

        item = self._current_item
        self._recording = False
        self._current_item = None
        return item

    def get_rules(self):
        """获取所有学习规则。"""
        return self.rules.get("items", [])

    def find_match(self, hsv_pixel):
        """查找像素与已学习物品的匹配。

        返回 (name, category) 或 None。
        """
        h, s, v = hsv_pixel
        for item in self.rules.get("items", []):
            avg = item.get("avg_hsv", [0, 0, 0])
            tol = item.get("hue_tolerance", 8)
            s_min = item.get("sat_min", 80)
            v_min = item.get("val_min", 80)

            if (abs(h - avg[0]) <= tol and
                s >= s_min and v >= v_min):
                return item["name"], item.get("category", "custom")
        return None

    def delete_item(self, name):
        """按名称删除物品。"""
        before = len(self.rules.get("items", []))
        self.rules["items"] = [i for i in self.rules.get("items", []) if i["name"] != name]
        after = len(self.rules["items"])
        if before != after:
            _save_rules(self.rules)
            _log.info("物品 '%s' 已删除。", name)
            return True
        return False
