"""
Strategy Snapshot - 策略快照
将策略配置转换为可回测的快照格式
"""

import json
from typing import Dict, Any, Optional


class StrategySnapshot:
    """
    策略快照解析器
    将存储的策略行转换为回测就绪的配置
    """

    def __init__(self):
        pass

    def resolve(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """
        将策略配置解析为回测配置

        Args:
            strategy: 原始策略配置（包含 trading_config 等）

        Returns:
            回测就绪的策略配置
        """
        if not strategy:
            return self._default_config()

        # 提取交易配置
        trading_config = strategy.get("trading_config", {}) or {}
        if isinstance(trading_config, str):
            try:
                trading_config = json.loads(trading_config)
            except (json.JSONDecodeError, TypeError):
                trading_config = {}

        return {
            "name": strategy.get("name", "Unnamed Strategy"),
            "signal_mode": trading_config.get("signal_mode", "confirmed"),
            "risk": {
                "stopLossPct": self._percent_to_ratio(trading_config.get("stop_loss_pct")),
                "takeProfitPct": self._percent_to_ratio(trading_config.get("take_profit_pct")),
                "trailing": {
                    "enabled": self._to_bool(trading_config.get("trailing_enabled") or trading_config.get("trailing_stop")),
                    "pct": self._percent_to_ratio(trading_config.get("trailing_stop_pct")),
                    "activationPct": self._percent_to_ratio(trading_config.get("trailing_activation_pct")),
                },
            },
            "position": {
                "entryPct": self._percent_to_ratio(trading_config.get("entry_pct", 100)),
            },
            "scale": {
                "trendAdd": {
                    "enabled": self._to_bool(trading_config.get("trend_add_enabled")),
                    "stepPct": self._percent_to_ratio(trading_config.get("trend_add_step_pct")),
                    "sizePct": self._percent_to_ratio(trading_config.get("trend_add_size_pct")),
                    "maxTimes": self._to_int(trading_config.get("trend_add_max_times")),
                },
                "dcaAdd": {
                    "enabled": self._to_bool(trading_config.get("dca_add_enabled")),
                    "stepPct": self._percent_to_ratio(trading_config.get("dca_add_step_pct")),
                    "sizePct": self._percent_to_ratio(trading_config.get("dca_add_size_pct")),
                    "maxTimes": self._to_int(trading_config.get("dca_add_max_times")),
                },
            },
            "indicators": strategy.get("indicators", []),
            "code": strategy.get("code", ""),
        }

    def _percent_to_ratio(self, value: Any, default: float = 0.0) -> float:
        """百分比转比率"""
        raw = self._to_float(value, default)
        if raw <= 0:
            return 0.0
        if raw > 100:
            raw = 100.0
        return raw / 100.0

    def _to_bool(self, value: Any) -> bool:
        """转换为布尔值"""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on", "enabled")
        return bool(value)

    def _to_float(self, value: Any, default: float = 0.0) -> float:
        """转换为浮点数"""
        try:
            return float(value)
        except (ValueError, TypeError):
            return float(default or 0.0)

    def _to_int(self, value: Any, default: int = 0) -> int:
        """转换为整数"""
        try:
            return int(value)
        except (ValueError, TypeError):
            return int(default or 0)

    def _default_config(self) -> Dict[str, Any]:
        """默认配置"""
        return {
            "name": "Default Strategy",
            "signal_mode": "confirmed",
            "risk": {
                "stopLossPct": 0.02,
                "takeProfitPct": 0.06,
                "trailing": {
                    "enabled": False,
                    "pct": 0.0,
                    "activationPct": 0.0,
                },
            },
            "position": {
                "entryPct": 1.0,
            },
            "scale": {
                "trendAdd": {
                    "enabled": False,
                    "stepPct": 0.0,
                    "sizePct": 0.0,
                    "maxTimes": 0,
                },
                "dcaAdd": {
                    "enabled": False,
                    "stepPct": 0.0,
                    "sizePct": 0.0,
                    "maxTimes": 0,
                },
            },
            "indicators": [],
            "code": "",
        }


def get_strategy_snapshot() -> StrategySnapshot:
    """获取策略快照实例"""
    return StrategySnapshot()
