"""
Indicator Code Quality Analyzer - 指标代码质量分析
基于原仓库 indicator_code_quality.py 简化
"""

import re
from typing import Dict, Any, List

from quant_core.strategy.compiler import StrategyCompiler


class IndicatorCodeQualityAnalyzer:
    """分析指标代码质量，提供改进建议"""

    @staticmethod
    def analyze(code: str) -> List[Dict[str, Any]]:
        """
        分析指标代码质量

        Returns:
            List of hints:
            { "severity": "info"|"warn"|"error", "code": str, "params": dict optional }
        """
        hints: List[Dict[str, Any]] = []
        raw = (code or "").strip()

        if not raw:
            return [{"severity": "error", "code": "EMPTY_CODE", "params": {}}]

        # 检查指标名称
        name_match = re.search(r"^\s*my_indicator_name\s*=\s*[\"'](.+?)[\"']", raw, re.MULTILINE)
        if not name_match:
            hints.append({"severity": "warn", "code": "MISSING_INDICATOR_NAME", "params": {}})

        # 检查输出字典
        if not re.search(r"\boutput\s*=\s*\{", raw):
            hints.append({"severity": "error", "code": "MISSING_OUTPUT", "params": {}})

        # 检查 df.copy()
        if not re.search(r"df\s*=\s*df\.copy\s*\(\s*\)", raw):
            hints.append({"severity": "info", "code": "MISSING_DF_COPY", "params": {}})

        # 检查买卖信号
        has_buy = bool(re.search(r"df\s*\[\s*['\"]buy['\"]\s*\]", raw))
        has_sell = bool(re.search(r"df\s*\[\s*['\"]sell['\"]\s*\]", raw))
        if not (has_buy or has_sell):
            hints.append({"severity": "warn", "code": "MISSING_BUY_SELL_COLUMNS", "params": {}})

        # 检查声明但未使用的参数
        declared_params = IndicatorCodeQualityAnalyzer._declared_param_names(raw)
        if declared_params:
            unread = [name for name in declared_params if not IndicatorCodeQualityAnalyzer._uses_params_get(raw, name)]
            if unread:
                hints.append({
                    "severity": "warn",
                    "code": "DECLARED_PARAMS_NOT_READ_VIA_PARAMS_GET",
                    "params": {"names": unread}
                })

        # 检查信号标记方式
        if re.search(r"\.where\s*\([^)]*,\s*None\s*\)\s*\.tolist\s*\(", raw):
            hints.append({
                "severity": "info",
                "code": "SIGNAL_MARKERS_USE_WHERE_NONE",
                "params": {}
            })

        # 检查未知的策略注解
        unknown_keys = IndicatorCodeQualityAnalyzer._unknown_strategy_keys(raw)
        for bad_key in unknown_keys:
            hints.append({
                "severity": "warn",
                "code": "UNKNOWN_STRATEGY_KEY",
                "params": {"key": bad_key}
            })

        # 解析策略配置
        cfg = StrategyCompiler.validate_strategy({"entry_conditions": [], "exit_conditions": []})  # 只获取验证结果

        if has_buy or has_sell:
            # 检查止盈止损配置
            stop_loss_match = re.search(r"stop.?loss", raw, re.IGNORECASE)
            take_profit_match = re.search(r"take.?profit", raw, re.IGNORECASE)

            if not stop_loss_match and not take_profit_match:
                hints.append({
                    "severity": "warn",
                    "code": "NO_STOP_AND_TAKE_PROFIT",
                    "params": {}
                })
            elif not stop_loss_match:
                hints.append({"severity": "info", "code": "NO_STOP_LOSS", "params": {}})
            elif not take_profit_match:
                hints.append({"severity": "info", "code": "NO_TAKE_PROFIT", "params": {}})

        # 检查是否为空模板
        if re.search(r"['\"]plots['\"]\s*:\s*\[\s*\]", raw) and re.search(r"['\"]signals['\"]\s*:\s*\[\s*\]", raw):
            hints.append({
                "severity": "info",
                "code": "EMPTY_PLOTS_AND_SIGNALS",
                "params": {}
            })

        return hints

    @staticmethod
    def _declared_param_names(code: str) -> List[str]:
        """提取声明的参数名"""
        names: List[str] = []
        for m in re.finditer(
            r"^\s*#\s*@param\s+(\w+)\s+(int|float|bool|str|string)\s+\S+",
            code or "",
            re.MULTILINE | re.IGNORECASE,
        ):
            names.append(m.group(1))
        return names

    @staticmethod
    def _uses_params_get(code: str, name: str) -> bool:
        """检查是否通过 params.get() 使用参数"""
        pattern = rf"params\s*\.?\s*get\s*\(\s*['\"]{re.escape(name)}['\"]\s*,?"
        return bool(re.search(pattern, code or ""))

    @staticmethod
    def _unknown_strategy_keys(code: str) -> List[str]:
        """检查未知的策略注解键"""
        valid = set(StrategyCompiler.validate_strategy({})[1])  # 获取有效键
        valid.update({"stopLossPct", "takeProfitPct", "entryPct", "trailingEnabled", "trailingStopPct"})
        unknown: List[str] = []
        for m in re.finditer(
            r"^\s*#\s*@strategy\s+(\w+)\s+(\S+)",
            code or "",
            re.MULTILINE | re.IGNORECASE
        ):
            key = m.group(1)
            if key not in valid and key.lower() not in ("leverage",):
                unknown.append(key)
        return unknown


def analyze_indicator_code_quality(code: str) -> List[Dict[str, Any]]:
    """便捷函数：分析指标代码质量"""
    return IndicatorCodeQualityAnalyzer.analyze(code)
