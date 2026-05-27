"""
市场分析器 - AI驱动的市场分析
"""
import pandas as pd
from typing import Dict, Any, List

from quant_core.llm import get_llm_service
from quant_core.strategy.indicators import calculate_indicator


class MarketAnalyzer:
    """AI市场分析器"""

    def __init__(self):
        self.llm = get_llm_service()

    def analyze(self, df: pd.DataFrame, symbol: str, timeframe: str, live_price: float = None) -> Dict[str, Any]:
        """
        分析市场数据

        Args:
            df: K线数据
            symbol: 交易对
            timeframe: 时间周期
            live_price: 实时价格（可选）

        Returns:
            分析报告
        """
        # 计算技术指标
        indicators_df = calculate_indicator(df.copy(), "RSI", period=14)
        indicators_df = calculate_indicator(indicators_df, "MACD")
        indicators_df = calculate_indicator(indicators_df, "BOLL", period=20)
        indicators_df = calculate_indicator(indicators_df, "ATR", period=14)

        # 获取最新指标值
        latest = {
            "rsi": indicators_df["rsi"].iloc[-1] if "rsi" in indicators_df else None,
            "macd": indicators_df["macd"].iloc[-1] if "macd" in indicators_df else None,
            "macd_signal": indicators_df["macd_signal"].iloc[-1] if "macd_signal" in indicators_df else None,
            "macd_hist": indicators_df["macd_hist"].iloc[-1] if "macd_hist" in indicators_df else None,
            "boll_upper": indicators_df["boll_upper"].iloc[-1] if "boll_upper" in indicators_df else None,
            "boll_middle": indicators_df["boll_middle"].iloc[-1] if "boll_middle" in indicators_df else None,
            "boll_lower": indicators_df["boll_lower"].iloc[-1] if "boll_lower" in indicators_df else None,
            "atr": indicators_df["atr"].iloc[-1] if "atr" in indicators_df else None,
        }

        # 价格统计 - 优先使用实时价格，否则使用K线最后收盘价
        current_price = live_price if live_price else df["close"].iloc[-1]
        price_change = (df["close"].iloc[-1] - df["close"].iloc[0]) / df["close"].iloc[0] * 100 if len(df) > 1 else 0
        high_24h = df["high"].max()
        low_24h = df["low"].min()
        avg_volume = df["volume"].mean()

        # 构建分析提示
        system_prompt = """你是一个专业的加密货币技术分析师。基于提供的数据进行分析并给出交易建议。

分析维度:
1. 趋势判断(上涨/下跌/震荡)
2. 支撑位和阻力位
3. 动能分析(RSI/MACD)
4. 波动性分析(ATR/布林带)
5. 交易信号和风险评估

输出JSON格式:
{
    "trend": "bullish|bearish|neutral",
    "trend_strength": 0.0-1.0,
    "support": 价格数值,
    "resistance": 价格数值,
    "rsi_analysis": "超买|超卖|中性",
    "macd_analysis": "金叉|死叉|震荡",
    "signals": ["信号1", "信号2"],
    "risk_level": "high|medium|low",
    "recommendation": "建议描述",
    "summary": "总结"
}"""

        user_prompt = f"""
交易对: {symbol}
时间周期: {timeframe}
当前价格: {current_price:.4f}
24h涨跌: {price_change:.2f}%
24h最高: {high_24h:.4f}
24h最低: {low_24h:.4f}
平均成交量: {avg_volume:.2f}

技术指标:
- RSI(14): {f"{latest['rsi']:.2f}" if latest['rsi'] is not None else 'N/A'}
- MACD: {f"{latest['macd']:.4f}" if latest['macd'] is not None else 'N/A'}
- MACD Signal: {f"{latest['macd_signal']:.4f}" if latest['macd_signal'] is not None else 'N/A'}
- MACD Hist: {f"{latest['macd_hist']:.4f}" if latest['macd_hist'] is not None else 'N/A'}
- Bollinger Upper: {f"{latest['boll_upper']:.4f}" if latest['boll_upper'] is not None else 'N/A'}
- Bollinger Middle: {f"{latest['boll_middle']:.4f}" if latest['boll_middle'] is not None else 'N/A'}
- Bollinger Lower: {f"{latest['boll_lower']:.4f}" if latest['boll_lower'] is not None else 'N/A'}
- ATR(14): {f"{latest['atr']:.4f}" if latest['atr'] is not None else 'N/A'}

请进行技术分析并给出建议。
"""

        default_structure = {
            "trend": "neutral",
            "trend_strength": 0.5,
            "support": current_price * 0.95,
            "resistance": current_price * 1.05,
            "rsi_analysis": "中性",
            "macd_analysis": "震荡",
            "signals": [],
            "risk_level": "medium",
            "recommendation": "观望",
            "summary": "数据分析失败"
        }

        result = self.llm.safe_call_llm(system_prompt, user_prompt, default_structure)
        result["symbol"] = symbol
        result["timeframe"] = timeframe
        result["current_price"] = current_price
        result["indicators"] = latest

        return result

    def compare_symbols(self, data_dict: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """
        比较多个交易对

        Args:
            data_dict: {symbol: df} 格式的数据字典

        Returns:
            比较分析结果
        """
        analyses = {}
        for symbol, df in data_dict.items():
            if len(df) > 0:
                analyses[symbol] = self.analyze(df, symbol, "unknown")

        # 找出最佳交易对
        scores = {}
        for symbol, analysis in analyses.items():
            score = 0
            if analysis.get("trend") == "bullish":
                score += 3
            elif analysis.get("trend") == "bearish":
                score -= 3
            score += analysis.get("trend_strength", 0.5) * 2
            if analysis.get("risk_level") == "low":
                score += 2
            elif analysis.get("risk_level") == "high":
                score -= 1
            scores[symbol] = score

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        return {
            "rankings": ranked,
            "analyses": analyses,
            "best_symbol": ranked[0][0] if ranked else None
        }

    def generate_report(self, analysis: Dict[str, Any]) -> str:
        """生成人类可读的报告"""
        lines = [
            f"# {analysis['symbol']} 技术分析报告",
            f"时间周期: {analysis['timeframe']}",
            f"当前价格: ${analysis['current_price']:.4f}",
            "",
            f"## 趋势分析",
            f"趋势: {analysis['trend']}",
            f"趋势强度: {analysis['trend_strength']:.2f}",
            "",
            f"## 技术指标",
            f"RSI: {analysis['indicators'].get('rsi', 'N/A'):.2f} - {analysis.get('rsi_analysis', 'N/A')}",
            f"MACD: {analysis.get('macd_analysis', 'N/A')}",
            "",
            f"## 关键价位",
            f"支撑位: ${analysis.get('support', 0):.4f}",
            f"阻力位: ${analysis.get('resistance', 0):.4f}",
            "",
            f"## 风险等级: {analysis.get('risk_level', 'medium').upper()}",
            "",
            f"## 建议",
            analysis.get("recommendation", "观望"),
            "",
            f"## 总结",
            analysis.get("summary", "无"),
        ]
        return "\n".join(lines)
