"""
策略编译器 - 将自然语言策略编译为可执行代码
"""
import json
from typing import Dict, Any, List, Tuple

from quant_core.llm import get_llm_service


class StrategyCompiler:
    """策略编译器"""

    def __init__(self):
        self.llm = get_llm_service()

    def compile_strategy(self, description: str, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        将自然语言策略描述编译为结构化策略

        Args:
            description: 自然语言策略描述
            market_data: 市场数据上下文

        Returns:
            结构化策略字典
        """
        system_prompt = """你是一个量化策略专家。将用户的策略描述编译为结构化策略。

输出格式(JSON):
{
    "name": "策略名称",
    "entry_conditions": ["条件1", "条件2"],
    "exit_conditions": ["条件1", "条件2"],
    "indicators": [{"name": "RSI", "params": {"period": 14}}],
    "risk_management": {
        "stop_loss_pct": 2.0,
        "take_profit_pct": 6.0,
        "trailing_stop": true,
        "trailing_pct": 1.5
    },
    "position_size": {
        "method": "fixed",
        "value": 100
    }
}"""

        user_prompt = f"""
市场数据:
- 交易对: {market_data.get('symbol', 'N/A')}
- 当前价格: {market_data.get('last', 'N/A')}
- 24h变化: {market_data.get('change_pct', 'N/A')}%
- 24h成交量: {market_data.get('volume', 'N/A')}

策略描述: {description}

请编译为结构化策略。
"""

        default_structure = {
            "name": "默认策略",
            "entry_conditions": [],
            "exit_conditions": [],
            "indicators": [],
            "risk_management": {
                "stop_loss_pct": 2.0,
                "take_profit_pct": 6.0,
                "trailing_stop": False,
                "trailing_pct": 0
            },
            "position_size": {"method": "fixed", "value": 100}
        }

        return self.llm.safe_call_llm(system_prompt, user_prompt, default_structure)

    def generate_signal(self, strategy: Dict[str, Any], df, current_price: float) -> Dict[str, Any]:
        """
        根据策略生成交易信号

        Returns:
            {"action": "buy"|"sell"|"hold", "confidence": 0.0-1.0, "reason": "..."}
        """
        # 简单的信号生成逻辑
        # 实际实现应该更复杂
        indicators = {ind["name"]: ind.get("params", {}) for ind in strategy.get("indicators", [])}

        signal = {"action": "hold", "confidence": 0.5, "reason": "No clear signal"}

        if "RSI" in indicators:
            rsi_period = indicators["RSI"].get("period", 14)
            if len(df) >= rsi_period:
                rsi = df["rsi"].iloc[-1] if "rsi" in df else None
                if rsi and rsi < 30:
                    signal = {"action": "buy", "confidence": 0.7, "reason": f"RSI oversold: {rsi:.2f}"}
                elif rsi and rsi > 70:
                    signal = {"action": "sell", "confidence": 0.7, "reason": f"RSI overbought: {rsi:.2f}"}

        if "MACD" in indicators:
            if "macd" in df and "macd_signal" in df:
                macd = df["macd"].iloc[-1]
                signal_line = df["macd_signal"].iloc[-1]
                if macd > signal_line:
                    signal = {"action": "buy", "confidence": 0.8, "reason": "MACD golden cross"}
                elif macd < signal_line:
                    signal = {"action": "sell", "confidence": 0.8, "reason": "MACD death cross"}

        return signal

    def ai_generate_signal(self, df, symbol: str, current_price: float) -> Dict[str, Any]:
        """
        AI驱动的实时交易信号生成

        Args:
            df: K线数据
            symbol: 交易对
            current_price: 当前价格

        Returns:
            {"action": "buy"|"sell"|"hold", "confidence": 0.0-1.0, "reason": "...", "entry_price": float, "stop_loss": float, "take_profit": float}
        """
        # 获取最近的数据
        recent = df.tail(20).copy()

        # 计算基础指标
        close = recent['close'].values
        high = recent['high'].values
        low = recent['low'].values
        volume = recent['volume'].values if 'volume' in recent else [0] * len(recent)

        # 计算 RSI
        delta = recent['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).iloc[-1] if len(recent) >= 14 else 50

        # 计算 MACD
        ema12 = recent['close'].ewm(span=12, adjust=False).mean().iloc[-1]
        ema26 = recent['close'].ewm(span=26, adjust=False).mean().iloc[-1]
        macd = ema12 - ema26
        signal_line = macd * 0.9  # 简化

        # 计算布林带
        boll_mid = recent['close'].rolling(window=20).mean().iloc[-1]
        boll_std = recent['close'].rolling(window=20).std().iloc[-1]
        boll_upper = boll_mid + 2 * boll_std
        boll_lower = boll_mid - 2 * boll_std

        # 价格变化
        price_change_1h = (close[-1] - close[-4]) / close[-4] * 100 if len(close) >= 4 else 0
        price_change_4h = (close[-1] - close[-16]) / close[-16] * 100 if len(close) >= 16 else 0

        # 波动率
        volatility = boll_std / boll_mid * 100

        system_prompt = """你是一个专业的加密货币交易分析师。根据实时市场数据给出交易建议。

输出格式(JSON):
{
    "action": "buy|sell|hold",
    "confidence": 0.0-1.0,
    "reason": "详细分析理由",
    "entry_price": 建议入场价(数字),
    "stop_loss": 止损价(数字),
    "take_profit": 止盈价(数字)
}

注意:
- action: buy=买入, sell=卖出, hold=观望
- confidence: 0.0-1.0，越高越确定
- 入场/止损/止盈价格必须是具体数字
- 止损建议设置在关键支撑/阻力位下方/上方1-2%"""

        market_context = f"""当前市场数据:
- 交易对: {symbol}
- 当前价格: ${current_price:.4f}
- RSI(14): {rsi:.2f}
- MACD: {macd:.4f}
- 布林上轨: ${boll_upper:.4f}
- 布林中轨: ${boll_mid:.4f}
- 布林下轨: ${boll_lower:.4f}
- 1小时涨跌: {price_change_1h:.2f}%
- 4小时涨跌: {price_change_4h:.2f}%
- 波动率: {volatility:.2f}%
- 最近成交量: {volume[-1]:.2f}

当前价格位置: {'接近布林上轨(超买区域)' if current_price > boll_upper * 0.98 else '接近布林下轨(超卖区域)' if current_price < boll_lower * 1.02 else '布林中轨附近(中性)'}

请给出交易建议:"""

        default_signal = {
            "action": "hold",
            "confidence": 0.5,
            "reason": "等待更明确信号",
            "entry_price": current_price,
            "stop_loss": current_price * 0.97,
            "take_profit": current_price * 1.05
        }

        result = self.llm.safe_call_llm(system_prompt, market_context, default_signal)

        # 确保返回字段完整
        if isinstance(result, dict):
            result.setdefault("action", "hold")
            result.setdefault("confidence", 0.5)
            result.setdefault("reason", "AI分析完成")
            result.setdefault("entry_price", current_price)
            result.setdefault("stop_loss", current_price * 0.97)
            result.setdefault("take_profit", current_price * 1.05)

        return result

    @staticmethod
    def validate_strategy(strategy: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """验证策略结构"""
        errors = []

        required = ["name", "entry_conditions", "exit_conditions"]
        for field in required:
            if field not in strategy:
                errors.append(f"Missing required field: {field}")

        if "risk_management" in strategy:
            rm = strategy["risk_management"]
            if "stop_loss_pct" in rm and (rm["stop_loss_pct"] < 0 or rm["stop_loss_pct"] > 100):
                errors.append("stop_loss_pct must be 0-100")
            if "take_profit_pct" in rm and (rm["take_profit_pct"] < 0 or rm["take_profit_pct"] > 1000):
                errors.append("take_profit_pct must be 0-1000")

        return len(errors) == 0, errors
