"""
Guardian - 风险检查模块
基于技术指标的多维度风险评估
支持: RSI, MACD, Bollinger Bands, KDJ, Volume, ADX
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Literal
from enum import Enum


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CheckStatus(Enum):
    """检查状态"""
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class RiskCheck:
    """单项风险检查结果"""
    indicator: str  # RSI, MACD, etc.
    status: str  # "pass", "warn", "fail"
    message: str  # Human-readable message
    value: Optional[float] = None  # Current indicator value
    threshold: Optional[float] = None  # Threshold used
    risk_weight: int = 0  # Risk weight for scoring

    def to_dict(self) -> Dict[str, Any]:
        return {
            "indicator": self.indicator,
            "status": self.status,
            "message": self.message,
            "value": self.value,
            "threshold": self.threshold,
        }


@dataclass
class RiskReport:
    """完整风险报告"""
    risk_level: str  # "low", "medium", "high", "critical"
    risk_score: int  # -100 to +100
    can_proceed: bool  # Execution eligibility
    checks: List[Dict[str, Any]]  # Individual check results
    warnings: List[str]  # Human-readable warnings
    recommendation: str  # Action recommendation
    summary: str = ""  # Brief summary

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "can_proceed": self.can_proceed,
            "checks": self.checks,
            "warnings": self.warnings,
            "recommendation": self.recommendation,
            "summary": self.summary,
        }


@dataclass
class RiskConfig:
    """风险配置"""
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    boll_low: float = 0.2
    boll_high: float = 0.8
    kdj_oversold: float = 20.0
    kdj_overbought: float = 80.0
    volume_low: float = 0.5
    volume_high: float = 1.5
    adx_weak: float = 20.0
    adx_strong: float = 25.0

    # Risk weights
    rsi_weight: int = -20
    macd_weight: int = -10
    boll_weight: int = -15
    kdj_weight: int = -10
    volume_weight: int = -5
    adx_weight: int = -5


class Guardian:
    """
    风险守护者
    检查: RSI, MACD, Bollinger, KDJ, Volume, ADX
    """

    # Risk scoring thresholds
    SCORE_LOW_MAX = 0
    SCORE_MEDIUM_MAX = 30
    SCORE_HIGH_MAX = 60

    def __init__(self, risk_config: Optional[RiskConfig] = None):
        self.config = risk_config or RiskConfig()

    def check_risk(
        self,
        indicators: Dict[str, float],
        intent: Dict[str, Any]
    ) -> RiskReport:
        """
        执行全面的风险检查

        Args:
            indicators: 技术指标字典，包含:
                - rsi: RSI 值 (0-100)
                - macd_histogram: MACD 柱状图
                - macd: MACD 值
                - macd_signal: Signal 线
                - boll_position: 布林带位置 (0-1)
                - boll_upper: 布林上轨
                - boll_lower: 布林下轨
                - kdj_k: K 值
                - kdj_d: D 值
                - volume_ratio: 成交量比率
                - adx: ADX 趋势强度
            intent: 交易意图，包含 action (buy/sell)

        Returns:
            RiskReport: 详细风险报告
        """
        checks = []
        risk_score = 0
        warnings = []

        action = intent.get("action", "buy")

        # 1. RSI 检查
        rsi_check = self._check_rsi(indicators, action)
        checks.append(rsi_check)
        risk_score += rsi_check.risk_weight

        # 2. MACD 检查
        macd_check = self._check_macd(indicators, action)
        checks.append(macd_check)
        risk_score += macd_check.risk_weight

        # 3. 布林带检查
        boll_check = self._check_bollinger(indicators, action)
        checks.append(boll_check)
        risk_score += boll_check.risk_weight

        # 4. KDJ 检查
        kdj_check = self._check_kdj(indicators, action)
        checks.append(kdj_check)
        risk_score += kdj_check.risk_weight

        # 5. 成交量检查
        volume_check = self._check_volume(indicators, action)
        checks.append(volume_check)
        risk_score += volume_check.risk_weight

        # 6. ADX 检查
        adx_check = self._check_adx(indicators, action)
        checks.append(adx_check)
        risk_score += adx_check.risk_weight

        # Collect warnings
        warnings = [c.message for c in checks if c.status in ["warn", "fail"]]

        # Calculate risk level
        risk_level = self._calculate_risk_level(risk_score)

        # Determine if can proceed
        can_proceed = risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]

        # Generate recommendation
        recommendation = self._generate_recommendation(risk_level, action, checks)

        # Generate summary
        summary = self._generate_summary(checks, risk_level)

        return RiskReport(
            risk_level=risk_level.value,
            risk_score=risk_score,
            can_proceed=can_proceed,
            checks=[c.to_dict() for c in checks],
            warnings=warnings,
            recommendation=recommendation,
            summary=summary
        )

    def _check_rsi(self, indicators: Dict[str, float], action: str) -> RiskCheck:
        """RSI 风险检查"""
        rsi = indicators.get("rsi", 50)
        cfg = self.config

        if action == "buy":
            if rsi < cfg.rsi_oversold:
                return RiskCheck(
                    indicator="RSI",
                    status="pass",
                    message=f"RSI 超卖 ({rsi:.1f} < {cfg.rsi_oversold}), 适合买入",
                    value=rsi,
                    threshold=cfg.rsi_oversold,
                    risk_weight=cfg.rsi_weight
                )
            elif rsi > cfg.rsi_overbought:
                return RiskCheck(
                    indicator="RSI",
                    status="warn",
                    message=f"RSI 超买 ({rsi:.1f} > {cfg.rsi_overbought}), 注意风险",
                    value=rsi,
                    threshold=cfg.rsi_overbought,
                    risk_weight=30
                )
            else:
                return RiskCheck(
                    indicator="RSI",
                    status="pass",
                    message=f"RSI 中性 ({rsi:.1f})",
                    value=rsi,
                    threshold=None,
                    risk_weight=0
                )
        else:  # sell
            if rsi > cfg.rsi_overbought:
                return RiskCheck(
                    indicator="RSI",
                    status="pass",
                    message=f"RSI 超买 ({rsi:.1f} > {cfg.rsi_overbought}), 适合卖出",
                    value=rsi,
                    threshold=cfg.rsi_overbought,
                    risk_weight=cfg.rsi_weight
                )
            elif rsi < cfg.rsi_oversold:
                return RiskCheck(
                    indicator="RSI",
                    status="warn",
                    message=f"RSI 超卖 ({rsi:.1f} < {cfg.rsi_oversold}), 注意反弹",
                    value=rsi,
                    threshold=cfg.rsi_oversold,
                    risk_weight=30
                )
            else:
                return RiskCheck(
                    indicator="RSI",
                    status="pass",
                    message=f"RSI 中性 ({rsi:.1f})",
                    value=rsi,
                    threshold=None,
                    risk_weight=0
                )

    def _check_macd(self, indicators: Dict[str, float], action: str) -> RiskCheck:
        """MACD 风险检查"""
        macd_hist = indicators.get("macd_histogram", 0)
        macd = indicators.get("macd", 0)
        macd_signal = indicators.get("macd_signal", 0)

        # Check for golden cross / death cross
        # Golden cross: MACD crosses above signal line (for buy)
        # Death cross: MACD crosses below signal line (for sell)

        if action == "buy":
            if macd_hist > 0:
                # MACD above signal line (bullish)
                msg = f"MACD 金叉 (柱状图: {macd_hist:.4f})"
                if macd > 0:
                    msg += ", MACD 零轴上方"
                return RiskCheck(
                    indicator="MACD",
                    status="pass",
                    message=msg,
                    value=macd_hist,
                    threshold=0,
                    risk_weight=self.config.macd_weight
                )
            elif macd_hist < 0:
                return RiskCheck(
                    indicator="MACD",
                    status="warn",
                    message=f"MACD 死叉 (柱状图: {macd_hist:.4f}), 趋势偏空",
                    value=macd_hist,
                    threshold=0,
                    risk_weight=15
                )
            else:
                return RiskCheck(
                    indicator="MACD",
                    status="warn",
                    message="MACD 趋势不明确",
                    value=0,
                    threshold=0,
                    risk_weight=5
                )
        else:  # sell
            if macd_hist < 0:
                msg = f"MACD 死叉 (柱状图: {macd_hist:.4f})"
                if macd < 0:
                    msg += ", MACD 零轴下方"
                return RiskCheck(
                    indicator="MACD",
                    status="pass",
                    message=msg,
                    value=macd_hist,
                    threshold=0,
                    risk_weight=self.config.macd_weight
                )
            elif macd_hist > 0:
                return RiskCheck(
                    indicator="MACD",
                    status="warn",
                    message=f"MACD 金叉 (柱状图: {macd_hist:.4f}), 趋势偏多",
                    value=macd_hist,
                    threshold=0,
                    risk_weight=15
                )
            else:
                return RiskCheck(
                    indicator="MACD",
                    status="warn",
                    message="MACD 趋势不明确",
                    value=0,
                    threshold=0,
                    risk_weight=5
                )

    def _check_bollinger(self, indicators: Dict[str, float], action: str) -> RiskCheck:
        """布林带风险检查"""
        boll_pos = indicators.get("boll_position", 0.5)
        cfg = self.config

        if action == "buy":
            if boll_pos < cfg.boll_low:
                depth = (cfg.boll_low - boll_pos) / cfg.boll_low
                return RiskCheck(
                    indicator="Bollinger",
                    status="pass",
                    message=f"价格接近布林下轨 (位置: {boll_pos:.2%})",
                    value=boll_pos,
                    threshold=cfg.boll_low,
                    risk_weight=self.config.boll_weight
                )
            elif boll_pos > cfg.boll_high:
                return RiskCheck(
                    indicator="Bollinger",
                    status="warn",
                    message=f"价格接近布林上轨 (位置: {boll_pos:.2%})",
                    value=boll_pos,
                    threshold=cfg.boll_high,
                    risk_weight=15
                )
            else:
                return RiskCheck(
                    indicator="Bollinger",
                    status="pass",
                    message=f"价格在中轨附近 (位置: {boll_pos:.2%})",
                    value=boll_pos,
                    threshold=None,
                    risk_weight=0
                )
        else:  # sell
            if boll_pos > cfg.boll_high:
                return RiskCheck(
                    indicator="Bollinger",
                    status="pass",
                    message=f"价格接近布林上轨 (位置: {boll_pos:.2%})",
                    value=boll_pos,
                    threshold=cfg.boll_high,
                    risk_weight=self.config.boll_weight
                )
            elif boll_pos < cfg.boll_low:
                return RiskCheck(
                    indicator="Bollinger",
                    status="warn",
                    message=f"价格接近布林下轨 (位置: {boll_pos:.2%})",
                    value=boll_pos,
                    threshold=cfg.boll_low,
                    risk_weight=15
                )
            else:
                return RiskCheck(
                    indicator="Bollinger",
                    status="pass",
                    message=f"价格在中轨附近 (位置: {boll_pos:.2%})",
                    value=boll_pos,
                    threshold=None,
                    risk_weight=0
                )

    def _check_kdj(self, indicators: Dict[str, float], action: str) -> RiskCheck:
        """KDJ 风险检查"""
        kdj_k = indicators.get("kdj_k", 50)
        kdj_d = indicators.get("kdj_d", 50)
        kdj_j = indicators.get("kdj_j", 50)
        cfg = self.config

        if action == "buy":
            if kdj_k < cfg.kdj_oversold:
                return RiskCheck(
                    indicator="KDJ",
                    status="pass",
                    message=f"KDJ 超卖 (K: {kdj_k:.1f})",
                    value=kdj_k,
                    threshold=cfg.kdj_oversold,
                    risk_weight=self.config.kdj_weight
                )
            elif kdj_k > cfg.kdj_overbought:
                return RiskCheck(
                    indicator="KDJ",
                    status="warn",
                    message=f"KDJ 超买 (K: {kdj_k:.1f})",
                    value=kdj_k,
                    threshold=cfg.kdj_overbought,
                    risk_weight=15
                )
            else:
                return RiskCheck(
                    indicator="KDJ",
                    status="pass",
                    message=f"KDJ 中性 (K: {kdj_k:.1f})",
                    value=kdj_k,
                    threshold=None,
                    risk_weight=0
                )
        else:  # sell
            if kdj_k > cfg.kdj_overbought:
                return RiskCheck(
                    indicator="KDJ",
                    status="pass",
                    message=f"KDJ 超买 (K: {kdj_k:.1f})",
                    value=kdj_k,
                    threshold=cfg.kdj_overbought,
                    risk_weight=self.config.kdj_weight
                )
            elif kdj_k < cfg.kdj_oversold:
                return RiskCheck(
                    indicator="KDJ",
                    status="warn",
                    message=f"KDJ 超卖 (K: {kdj_k:.1f})",
                    value=kdj_k,
                    threshold=cfg.kdj_oversold,
                    risk_weight=15
                )
            else:
                return RiskCheck(
                    indicator="KDJ",
                    status="pass",
                    message=f"KDJ 中性 (K: {kdj_k:.1f})",
                    value=kdj_k,
                    threshold=None,
                    risk_weight=0
                )

    def _check_volume(self, indicators: Dict[str, float], action: str) -> RiskCheck:
        """成交量风险检查"""
        volume_ratio = indicators.get("volume_ratio", 1.0)
        cfg = self.config

        if volume_ratio >= cfg.volume_low and volume_ratio <= cfg.volume_high:
            return RiskCheck(
                indicator="Volume",
                status="pass",
                message=f"成交量正常 (比率: {volume_ratio:.2f})",
                value=volume_ratio,
                threshold=None,
                risk_weight=0
            )
        elif volume_ratio < cfg.volume_low:
            return RiskCheck(
                indicator="Volume",
                status="warn",
                message=f"成交量萎缩 (比率: {volume_ratio:.2f})",
                value=volume_ratio,
                threshold=cfg.volume_low,
                risk_weight=5
            )
        else:  # volume_ratio > volume_high
            return RiskCheck(
                indicator="Volume",
                status="pass",
                message=f"成交量放大 (比率: {volume_ratio:.2f})",
                value=volume_ratio,
                threshold=cfg.volume_high,
                risk_weight=self.config.volume_weight
            )

    def _check_adx(self, indicators: Dict[str, float], action: str) -> RiskCheck:
        """ADX 趋势强度检查"""
        adx = indicators.get("adx", 25)
        cfg = self.config

        if adx < cfg.adx_weak:
            return RiskCheck(
                indicator="ADX",
                status="warn",
                message=f"趋势较弱 (ADX: {adx:.1f})",
                value=adx,
                threshold=cfg.adx_weak,
                risk_weight=10
            )
        elif adx >= cfg.adx_strong:
            return RiskCheck(
                indicator="ADX",
                status="pass",
                message=f"趋势明确 (ADX: {adx:.1f})",
                value=adx,
                threshold=cfg.adx_strong,
                risk_weight=self.config.adx_weight
            )
        else:
            return RiskCheck(
                indicator="ADX",
                status="pass",
                message=f"趋势中等 (ADX: {adx:.1f})",
                value=adx,
                threshold=cfg.adx_weak,
                risk_weight=0
            )

    def _calculate_risk_level(self, risk_score: int) -> RiskLevel:
        """根据风险评分计算风险等级"""
        if risk_score >= self.SCORE_HIGH_MAX:
            return RiskLevel.CRITICAL
        elif risk_score >= self.SCORE_MEDIUM_MAX:
            return RiskLevel.HIGH
        elif risk_score > self.SCORE_LOW_MAX:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _generate_recommendation(self, risk_level: RiskLevel, action: str, checks: List[RiskCheck]) -> str:
        """生成交易建议"""
        if not risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]:
            return "建议暂缓交易，等待更佳时机"

        passed = sum(1 for c in checks if c.status == "pass")
        total = len(checks)

        if passed == total:
            return f"建议{action.upper()}"
        elif passed >= total * 0.7:
            return f"可以{action.upper()}，但需注意风险"
        else:
            return "建议等待更多信号确认"

    def _generate_summary(self, checks: List[RiskCheck], risk_level: RiskLevel) -> str:
        """生成简短摘要"""
        passed = sum(1 for c in checks if c.status == "pass")
        warned = sum(1 for c in checks if c.status == "warn")
        return f"{passed}/{len(checks)} 项检查通过，风险等级: {risk_level.value}"

    def generate_report(self, risk_report: RiskReport) -> str:
        """生成人类可读风险报告"""
        lines = [
            "=" * 50,
            "Guardian 风险报告",
            "=" * 50,
            f"风险等级: {risk_report.risk_level.upper()}",
            f"风险评分: {risk_report.risk_score}",
            f"建议: {risk_report.recommendation}",
            "",
            "检查结果:",
        ]

        status_icons = {"pass": "[PASS]", "warn": "[WARN]", "fail": "[FAIL]"}
        for check in risk_report.checks:
            icon = status_icons.get(check["status"], "[?]")
            value_str = f" (值: {check['value']:.2f})" if check["value"] is not None else ""
            lines.append(f"  {icon} {check['indicator']}: {check['message']}{value_str}")

        if risk_report.warnings:
            lines.append("")
            lines.append("警告:")
            for w in risk_report.warnings:
                lines.append(f"  ! {w}")

        lines.append("")
        can_proceed = "可以执行" if risk_report.can_proceed else "建议暂缓"
        lines.append(f"结论: {can_proceed}")
        lines.append("=" * 50)

        return "\n".join(lines)


def get_guardian(risk_config: RiskConfig = None) -> Guardian:
    """获取 Guardian 实例"""
    return Guardian(risk_config)