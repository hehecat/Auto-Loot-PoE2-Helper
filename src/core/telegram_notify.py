"""Telegram уведомления: отправка сообщений о редких дропах.

Использует Telegram Bot API. Требует bot_token и chat_id в конфиге.
Отправляются уведомления о ценных предметах (валюта, фрагменты, уникалы).
"""
import logging
import time
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from urllib.error import URLError

_log = logging.getLogger("autoloot.telegram")

# Категории, о которых уведомлять
NOTIFY_CATEGORIES = {"currency", "fragments", "uniques"}

# Минимальный приоритет для уведомления (1=всегда, 2=обычно, 3=опц.)
NOTIFY_PRIORITY_THRESHOLD = 2


class TelegramNotifier:
    """Отправка уведомлений в Telegram."""

    def __init__(self, bot_token=None, chat_id=None, enabled=True):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled and bot_token and chat_id
        self._last_send = 0
        self._cooldown = 2.0  # минимум между сообщениями

        if self.enabled:
            _log.info("Telegram: уведомления включены (chat_id=%s)", chat_id)

    def notify(self, category, item_name="", x=0, y=0, priority=2):
        """Отправить уведомление о подборе."""
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
        """Отправить сообщение через Telegram Bot API."""
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
                    _log.debug("Telegram: отправлено '%s'", text[:50])
                else:
                    _log.warning("Telegram: ошибка %s", resp.status)
        except URLError as e:
            _log.debug("Telegram: сеть недоступна (%s)", e)
        except Exception as e:
            _log.debug("Telegram: ошибка отправки: %s", e)

    def test_connection(self):
        """Проверить соединение с Telegram."""
        if not self.enabled:
            return False, "Уведомления отключены"
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
            with urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    return True, "OK"
                return False, f"HTTP {resp.status}"
        except Exception as e:
            return False, str(e)
