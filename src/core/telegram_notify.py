"""Telegram 通知：发送稀有掉落消息。

使用 Telegram Bot API。需要在配置中设置 bot_token 和 chat_id。
发送贵重物品通知（货币、碎片、传奇物品）。
"""
import logging
import time
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from urllib.error import URLError

_log = logging.getLogger("autoloot.telegram")

# 需要通知的类别
NOTIFY_CATEGORIES = {"currency", "fragments", "uniques"}

# 通知的最小优先级（1=总是、2=通常、3=可选）
NOTIFY_PRIORITY_THRESHOLD = 2


class TelegramNotifier:
    """发送 Telegram 通知。"""

    def __init__(self, bot_token=None, chat_id=None, enabled=True):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled and bot_token and chat_id
        self._last_send = 0
        self._cooldown = 2.0  # 消息之间最小间隔

        if self.enabled:
            _log.info("Telegram: 通知已开启 (chat_id=%s)", chat_id)

    def notify(self, category, item_name="", x=0, y=0, priority=2):
        """发送拾取通知。"""
        if not self.enabled:
            return

        if category not in NOTIFY_CATEGORIES:
            return

        if priority > NOTIFY_PRIORITY_THRESHOLD:
            return

        now = time.time()
        if now - self._last_send < self._cooldown:
            return

        emoji = {
            "currency": "\U0001f4b0",
            "fragments": "\U0001f536",
            "uniques": "\u2b50",
        }.get(category, "\u2728")

        text = f"{emoji} {category.upper()}"
        if item_name:
            text += f": {item_name}"
        text += f"\n\U0001f4cd ({x}, {y})"

        self._send(text)
        self._last_send = now

    def _send(self, text):
        """通过 Telegram Bot API 发送消息。"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = urlencode({
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
            }).encode("utf-8")

            req = Request(url, data=data, method="POST")
            with urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    _log.debug("Telegram: 已发送 '%s'", text[:50])
                else:
                    _log.warning("Telegram: 错误 %s", resp.status)
        except URLError as e:
            _log.debug("Telegram: 网络不可用 (%s)", e)
        except Exception as e:
            _log.debug("Telegram: 发送失败: %s", e)

    def test_connection(self):
        """检查 Telegram 连接。"""
        if not self.enabled:
            return False, "通知已禁用"
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
            with urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    return True, "OK"
                return False, f"HTTP {resp.status}"
        except Exception as e:
            return False, str(e)
