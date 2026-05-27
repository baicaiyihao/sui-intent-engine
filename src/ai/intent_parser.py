"""
Intent Parser - 意图解析模块
将自然语言解析为结构化的交易意图
支持 LLM (MiniMax) 解析和规则解析 fallback
"""
import json
import re
import uuid
import sys
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, Literal
from datetime import datetime

# Add src to path for quant_core imports
_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.dirname(_current_dir)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from quant_core.llm import get_llm_service


@dataclass
class TriggerCondition:
    """触发条件"""
    indicator: str  # RSI, MACD, KDJ, etc.
    condition: str  # "<", ">", "cross_up", "cross_down"
    threshold: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Intent:
    """交易意图结构"""
    action: Literal["buy", "sell"]
    asset: str  # e.g., "SUI"
    amount_usd: float  # Dollar amount
    trigger: Optional[TriggerCondition] = None  # Conditional trigger
    stop_loss_pct: float = 2.0  # Stop loss percentage
    take_profit_pct: float = 6.0  # Take profit percentage
    timeframe: str = "1H"  # Analysis timeframe (e.g., "1H")
    created_at: datetime = field(default_factory=datetime.now)
    session_id: str = field(default_factory=lambda: f"sess_{uuid.uuid4().hex[:12]}")

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "action": self.action,
            "asset": self.asset,
            "amount_usd": self.amount_usd,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "timeframe": self.timeframe,
            "created_at": self.created_at.isoformat(),
            "session_id": self.session_id,
        }
        if self.trigger:
            result["trigger"] = self.trigger.to_dict()
        return result


class IntentParser:
    """
    意图解析器 - 将自然语言转换为结构化意图
    支持: RSI/MACD/价格条件, 买入/卖出, 止损止盈
    """

    # 支持的指标
    INDICATORS = ["RSI", "MACD", "KDJ", "BOLL", "ADX", "VOLUME", "MA", "EMA"]

    # 金额模式
    AMOUNT_PATTERNS = [
        (r'(\d+(?:\.\d+)?)\s*(?:美元|usd|\$)', 'usd'),
        (r'(\d+(?:\.\d+)?)\s*(?:刀)', 'usd'),
    ]

    # 触发条件模式
    TRIGGER_PATTERNS = [
        # RSI < 30, RSI > 70, rsi低于30, rsi高于70
        (r'(?:rsi|RSI)\s*(<|>|小于|低于|大于|高于|小于等于|低于等于|大于等于|高于等于)\s*(\d+(?:\.\d+)?)', 'RSI'),
        # MACD 金叉, MACD 死叉, macd < 0, macd > 0
        (r'(?:macd|MACD)\s*(金叉|死叉|cross_up|cross_down|<|>)\s*(\d+(?:\.\d+)?)?', 'MACD'),
        # KDJ < 20, KDJ > 80
        (r'(?:kdj|KDJ)\s*(<|>)\s*(\d+(?:\.\d+)?)', 'KDJ'),
        # 价格 < 1.5, 价格 > 2.0
        (r'(?:价格|price)\s*(<|>)\s*(\d+(?:\.\d+)?)', 'PRICE'),
    ]

    # 动作词
    BUY_WORDS = ["买", "做多", "long", "buy", "买入", "做多", "开多", "做多", "开仓买入"]
    SELL_WORDS = ["卖", "做空", "short", "sell", "卖出", "做空", "开空", "平仓卖出"]

    def __init__(self, llm_service=None):
        self.llm = llm_service
        self.default_intent = {
            "action": "buy",
            "asset": "SUI",
            "amount_usd": 100.0,
            "trigger": None,
            "stop_loss_pct": 2.0,
            "take_profit_pct": 6.0,
            "timeframe": "1H"
        }

    def parse(self, user_input: str) -> Intent:
        """
        解析用户输入

        Args:
            user_input: 自然语言输入 (e.g., "RSI < 30 时买入 100 USD SUI")

        Returns:
            Intent: 结构化交易意图
        """
        # Try LLM parsing first
        if self.llm:
            try:
                result = self._parse_with_llm(user_input)
                if result:
                    return result
            except Exception:
                pass

        # Fallback to rule-based parsing
        return self._parse_with_rules(user_input)

    def _parse_with_llm(self, user_input: str) -> Optional[Intent]:
        """使用 LLM (MiniMax) 解析"""
        if not self.llm:
            return None

        system_prompt = """你是一个加密货币交易意图解析器。将用户的自然语言输入解析为结构化的交易意图。

返回格式 (JSON):
{
    "action": "buy" 或 "sell",
    "asset": "SUI" 或其他代币符号,
    "amount_usd": 金额 (数字),
    "trigger": {
        "indicator": "RSI" 或 "MACD" 或 "KDJ" 或 "PRICE",
        "condition": "<" 或 ">" 或 "cross_up" 或 "cross_down",
        "threshold": 阈值 (数字)
    },
    "stop_loss_pct": 止损百分比 (默认 2),
    "take_profit_pct": 止盈百分比 (默认 6),
    "timeframe": "1H" (默认)
}

如果用户没有指定触发条件，trigger 设为 null。
如果用户没有指定止损止盈，使用默认值 stop_loss_pct=2, take_profit_pct=6。
只返回 JSON，不要其他内容。"""

        default_structure = {
            "action": "buy",
            "asset": "SUI",
            "amount_usd": 100.0,
            "trigger": None,
            "stop_loss_pct": 2.0,
            "take_profit_pct": 6.0,
            "timeframe": "1H"
        }

        try:
            result = self.llm.safe_call_llm(system_prompt, user_input, default_structure)
            if result and "action" in result:
                return self._dict_to_intent(result)
        except Exception:
            pass

        return None

    def _parse_with_rules(self, user_input: str) -> Intent:
        """使用规则解析"""
        text = user_input.lower().strip()

        intent = self._create_default_intent()

        # 解析买卖
        intent.action = self._parse_action(text)

        # 解析金额
        intent.amount_usd = self._parse_amount(text)

        # 解析资产
        intent.asset = self._parse_asset(text)

        # 解析触发条件
        intent.trigger = self._parse_trigger(text)

        # 解析止损止盈
        sl, tp = self._parse_stop_loss_take_profit(text)
        intent.stop_loss_pct = sl
        intent.take_profit_pct = tp

        # 解析时间周期
        intent.timeframe = self._parse_timeframe(text)

        return intent

    def _create_default_intent(self) -> Intent:
        """创建默认意图"""
        return Intent(
            action="buy",
            asset="SUI",
            amount_usd=100.0,
            trigger=None,
            stop_loss_pct=2.0,
            take_profit_pct=6.0,
            timeframe="1H"
        )

    def _parse_action(self, text: str) -> str:
        """解析买卖方向"""
        # Check for sell first to avoid "买" matching in "卖出"
        for word in self.SELL_WORDS:
            if word in text:
                return "sell"
        for word in self.BUY_WORDS:
            if word in text:
                return "buy"
        return "buy"  # Default

    def _parse_amount(self, text: str) -> float:
        """解析交易金额"""
        for pattern, _ in self.AMOUNT_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return float(match.group(1))
        return 100.0  # Default

    def _parse_asset(self, text: str) -> str:
        """解析交易资产"""
        # Common crypto assets
        assets = ["SUI", "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT"]
        text_upper = text.upper()
        for asset in assets:
            if asset in text_upper:
                return asset
        return "SUI"  # Default

    def _parse_trigger(self, text: str) -> Optional[TriggerCondition]:
        """解析触发条件"""
        for pattern, indicator in self.TRIGGER_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                condition_raw = match.group(1)
                threshold_str = match.group(2) if len(match.groups()) > 1 and match.group(2) else None

                condition = self._normalize_condition(condition_raw, indicator)

                if threshold_str:
                    threshold = float(threshold_str)
                elif indicator == "PRICE":
                    # For price triggers without explicit threshold, use percentage
                    threshold = 0.0
                else:
                    # Default thresholds based on indicator
                    threshold = self._default_threshold(indicator, condition)

                return TriggerCondition(
                    indicator=indicator,
                    condition=condition,
                    threshold=threshold
                )

        return None

    def _normalize_condition(self, raw: str, indicator: str) -> str:
        """标准化条件符号"""
        raw = raw.lower().strip()

        if raw in ["<", "小于", "低于"]:
            return "<"
        elif raw in [">", "大于", "高于"]:
            return ">"
        elif raw in ["<=", "小于等于", "低于等于"]:
            return "<="
        elif raw in [">=", "大于等于", "高于等于"]:
            return ">="
        elif raw in ["金叉", "cross_up"]:
            return "cross_up"
        elif raw in ["死叉", "cross_down"]:
            return "cross_down"

        return raw

    def _default_threshold(self, indicator: str, condition: str) -> float:
        """获取指标默认阈值"""
        defaults = {
            "RSI": {"<": 30, ">": 70},
            "MACD": {"cross_up": 0, "cross_down": 0, "<": 0, ">": 0},
            "KDJ": {"<": 20, ">": 80},
            "BOLL": {"<": 0.2, ">": 0.8},
            "ADX": {"<": 20, ">": 25},
            "PRICE": {"<": 0, ">": 0},
        }

        if indicator in defaults:
            if condition in defaults[indicator]:
                return defaults[indicator][condition]

        return 0.0

    def _parse_stop_loss_take_profit(self, text: str) -> tuple:
        """解析止损止盈"""
        stop_loss = 2.0  # Default 2%
        take_profit = 6.0  # Default 6%

        # 止损
        sl_patterns = [
            r'止损[:\s]*(\d+(?:\.\d+)?)%?',
            r'stop\s*loss[:\s]*(\d+(?:\.\d+)?)%?',
            r'sl[:\s]*(\d+(?:\.\d+)?)%?',
        ]
        for pattern in sl_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                stop_loss = float(match.group(1))
                break

        # 止盈
        tp_patterns = [
            r'止盈[:\s]*(\d+(?:\.\d+)?)%?',
            r'take\s*profit[:\s]*(\d+(?:\.\d+)?)%?',
            r'tp[:\s]*(\d+(?:\.\d+)?)%?',
        ]
        for pattern in tp_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                take_profit = float(match.group(1))
                break

        return stop_loss, take_profit

    def _parse_timeframe(self, text: str) -> str:
        """解析时间周期"""
        tf_patterns = {
            r'1分钟|1m': "1m",
            r'5分钟|5m': "5m",
            r'15分钟|15m': "15m",
            r'30分钟|30m': "30m",
            r'1小时|1h|1H': "1H",
            r'4小时|4h|4H': "4H",
            r'1天|1d|1D': "1D",
            r'1周|1w|1W': "1W",
        }

        for pattern, tf in tf_patterns.items():
            if re.search(pattern, text):
                return tf

        return "1H"  # Default

    def _dict_to_intent(self, data: Dict[str, Any]) -> Intent:
        """将字典转换为 Intent 对象"""
        trigger_data = data.get("trigger")
        trigger = None
        if trigger_data and isinstance(trigger_data, dict):
            trigger = TriggerCondition(
                indicator=trigger_data.get("indicator", "RSI"),
                condition=trigger_data.get("condition", "<"),
                threshold=float(trigger_data.get("threshold", 30))
            )

        return Intent(
            action=data.get("action", "buy"),
            asset=data.get("asset", "SUI"),
            amount_usd=float(data.get("amount_usd", 100)),
            trigger=trigger,
            stop_loss_pct=float(data.get("stop_loss_pct", 2)),
            take_profit_pct=float(data.get("take_profit_pct", 6)),
            timeframe=data.get("timeframe", "1H"),
            session_id=f"sess_{uuid.uuid4().hex[:12]}"
        )

    def to_human_readable(self, intent: Intent) -> str:
        """转换为人类可读格式"""
        action = "买入" if intent.action == "buy" else "卖出"
        lines = [
            f"操作: {action} {intent.asset}",
            f"金额: ${intent.amount_usd:.2f}"
        ]
        if intent.trigger:
            t = intent.trigger
            indicator_name = {
                "RSI": "RSI",
                "MACD": "MACD",
                "KDJ": "KDJ",
                "BOLL": "布林带",
                "ADX": "ADX",
                "PRICE": "价格",
            }.get(t.indicator, t.indicator)

            condition_map = {
                "<": "低于",
                ">": "高于",
                "<=": "低于等于",
                ">=": "高于等于",
                "cross_up": "金叉",
                "cross_down": "死叉",
            }
            condition_text = condition_map.get(t.condition, t.condition)
            lines.append(f"触发条件: {indicator_name} {condition_text} {t.threshold}")

        lines.append(f"止损: -{intent.stop_loss_pct}%")
        lines.append(f"止盈: +{intent.take_profit_pct}%")
        lines.append(f"时间周期: {intent.timeframe}")
        return "\n".join(lines)


def get_intent_parser(llm_service=None) -> IntentParser:
    """获取 IntentParser 实例"""
    if llm_service is None:
        try:
            llm_service = get_llm_service()
        except Exception:
            pass
    return IntentParser(llm_service)
