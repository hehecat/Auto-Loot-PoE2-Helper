"""Оценка лута: правила + опциональный LLM для принятия решений.

Базовый evaluator работает по правилам (список имён/паттернов).
LLM evaluator отправляет текст подписи в модель для оценки.
"""
import re
import logging

_log = logging.getLogger("autoloot.evaluator")

# === Правила по умолчанию ===
# Приоритет: 1 = всегда подбирать, 2 = подбирать обычно, 3 = только если пусто, 0 = пропуск
DEFAULT_RULES = {
    # Валюта — высокий приоритет
    "chaos_orb": 1, "divine_orb": 1, "exalted_orb": 1, "mirror_of_kalandra": 1,
    "orb_of_alchemy": 1, "orb_of_chaos": 1, "regal_orb": 2, "orb_of_fusing": 2,
    "orb_of_regret": 2, "orb_of_scouring": 2, "blessed_orb": 2, "chisel": 2,
    "vaal_orb": 2, "chromatic_orb": 3, "jewellers_orb": 3, "orb_of_chance": 3,
    "orb_of_blasting": 2, "stacked_deck": 2,
    # Фрагменты
    "sacrifice": 2, "mortal": 2, "fragment": 2, "splinter": 3,
    "set碎片": 2,
    # Вейстоуны
    "waystone": 3, "tower": 3,
    # Гемы
    "uncut": 2, "skill gem": 3, "support gem": 3, "spirit gem": 3,
    # Карты
    "map": 3, "cartographer": 3,
    # Мусор — не подбирать
    "scroll": 0, "portal": 0, "identify": 0,
}

# Паттерны для категорий (regex)
CATEGORY_PATTERNS = {
    "currency": r"(?i)(orb|scroll|alchemy|chaos|divine|exalted|mirror|regal|fusing|scouring|blessed|chisel|vaal|chromatic|jewellers|blasting|stacked|coin)",
    "fragments": r"(?i)(fragment|splinter|sacrifice|mortal|set碎片)",
    "waystones": r"(?i)(waystone|tower)",
    "gems": r"(?i)(uncut|skill gem|support gem|spirit gem)",
    "maps": r"(?i)(map|cartographer)",
    "uniques": r"(?i)(unique|rare)",
}


def classify_text(text):
    """Определить категорию по тексту подписи."""
    for cat, pattern in CATEGORY_PATTERNS.items():
        if re.search(pattern, text):
            return cat
    return "unknown"


def evaluate_loot(text):
    """Оценить лут по тексту подписи. Возвращает приоритет (0=пропуск, 1=всегда, 2=обычно, 3=опц.)."""
    text_lower = text.lower().strip()

    for pattern, priority in DEFAULT_RULES.items():
        if pattern in text_lower:
            return priority

    if not text or len(text) < 2:
        return 3

    return 3


class RuleEvaluator:
    """Оценка лута по правилам (быстрый, без внешних API)."""

    def __init__(self, custom_rules=None):
        self.rules = dict(DEFAULT_RULES)
        if custom_rules:
            self.rules.update(custom_rules)

    def evaluate(self, text, category=None):
        """Оценить лут. Возвращает (priority, category)."""
        if category and category != "?":
            cat_priority = {
                "currency": 1, "fragments": 2, "gems": 3, "waystones": 3,
            }
            return cat_priority.get(category, 3), category

        text_lower = text.lower().strip()
        for pattern, priority in self.rules.items():
            if pattern in text_lower:
                return priority, classify_text(text)

        return 3, classify_text(text) if text else "unknown"


class LLMEvaluator:
    """Оценка лута через LLM API (опционально).

    Отправляет текст подписи в модель и получает оценку.
    Требует API ключ OpenAI или совместимого провайдера.
    """

    def __init__(self, api_key=None, model="gpt-4o-mini", base_url=None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self._client = None

    def _get_client(self):
        if self._client is None and self.api_key:
            try:
                from openai import OpenAI
                kwargs = {"api_key": self.api_key}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self._client = OpenAI(**kwargs)
            except ImportError:
                _log.warning("openai не установлен — LLM evaluator недоступен.")
        return self._client

    def evaluate(self, text, category=None):
        """Оценить лут через LLM. Возвращает (priority, reason)."""
        client = self._get_client()
        if not client or not text:
            return 3, "no llm"

        try:
            prompt = (
                f"Оцени лут для Path of Exile 2. Предмет: '{text}'. "
                f"Ответь одним числом: 1=всегда подбирать, 2=обычно подбирать, "
                f"3=подбирать если есть место, 0=не подбирать. "
                f"Только число, без объяснений."
            )
            resp = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=5,
                temperature=0,
            )
            answer = resp.choices[0].message.content.strip()
            priority = int(answer) if answer.isdigit() else 3
            return max(0, min(3, priority)), "llm"
        except Exception as e:
            _log.debug("LLM ошибка: %s", e)
            return 3, "llm error"
