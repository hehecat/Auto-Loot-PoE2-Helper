"""战利品评估：规则 + 可选的 LLM 用于决策。

基础评估器按规则工作（名称/模式列表）。
LLM 评估器将标签文本发送到模型进行评估。
"""
import re
import logging

_log = logging.getLogger("autoloot.evaluator")

# === 默认规则 ===
# 优先级：1 = 总是拾取，2 = 通常拾取，3 = 仅空闲时，0 = 跳过
DEFAULT_RULES = {
    # 货币 — 高优先级
    "chaos_orb": 1, "divine_orb": 1, "exalted_orb": 1, "mirror_of_kalandra": 1,
    "orb_of_alchemy": 1, "orb_of_chaos": 1, "regal_orb": 2, "orb_of_fusing": 2,
    "orb_of_regret": 2, "orb_of_scouring": 2, "blessed_orb": 2, "chisel": 2,
    "vaal_orb": 2, "chromatic_orb": 3, "jewellers_orb": 3, "orb_of_chance": 3,
    "orb_of_blasting": 2, "stacked_deck": 2,
    # 碎片
    "sacrifice": 2, "mortal": 2, "fragment": 2, "splinter": 3,
    "set碎片": 2,
    # 界石
    "waystone": 3, "tower": 3,
    # 技能宝石
    "uncut": 2, "skill gem": 3, "support gem": 3, "spirit gem": 3,
    # 地图
    "map": 3, "cartographer": 3,
    # 垃圾 — 不拾取
    "scroll": 0, "portal": 0, "identify": 0,
}

# 类别模式（正则表达式）
CATEGORY_PATTERNS = {
    "currency": r"(?i)(orb|scroll|alchemy|chaos|divine|exalted|mirror|regal|fusing|scouring|blessed|chisel|vaal|chromatic|jewellers|blasting|stacked|coin)",
    "fragments": r"(?i)(fragment|splinter|sacrifice|mortal|set碎片)",
    "waystones": r"(?i)(waystone|tower)",
    "gems": r"(?i)(uncut|skill gem|support gem|spirit gem)",
    "maps": r"(?i)(map|cartographer)",
    "uniques": r"(?i)(unique|rare)",
}


def classify_text(text):
    """根据标签文本确定类别。"""
    for cat, pattern in CATEGORY_PATTERNS.items():
        if re.search(pattern, text):
            return cat
    return "unknown"


def evaluate_loot(text):
    """根据标签文本评估战利品。返回优先级（0=跳过、1=总是、2=通常、3=可选）。"""
    text_lower = text.lower().strip()

    for pattern, priority in DEFAULT_RULES.items():
        if pattern in text_lower:
            return priority

    if not text or len(text) < 2:
        return 3

    return 3


class RuleEvaluator:
    """基于规则的战利品评估（快速，无需外部 API）。"""

    def __init__(self, custom_rules=None):
        self.rules = dict(DEFAULT_RULES)
        if custom_rules:
            self.rules.update(custom_rules)

    def evaluate(self, text, category=None):
        """评估战利品。返回 (priority, category)。"""
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
    """通过 LLM API 评估战利品（可选）。

    将标签文本发送到模型并获取评估。
    需要 OpenAI 或兼容提供商的 API 密钥。
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
                _log.warning("openai 未安装 — LLM 评估器不可用。")
        return self._client

    def evaluate(self, text, category=None):
        """通过 LLM 评估战利品。返回 (priority, reason)。"""
        client = self._get_client()
        if not client or not text:
            return 3, "no llm"

        try:
            prompt = (
                f"评估 Path of Exile 2 战利品。物品：'{text}'。 "
                f"回复一个数字：1=总是拾取，2=通常拾取，"
                f"3=有空间时拾取，0=不拾取。"
                f"只回复数字，无需解释。"
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
            _log.debug("LLM 错误: %s", e)
            return 3, "llm error"
