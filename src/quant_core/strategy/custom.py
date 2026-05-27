"""
自定义指标引擎 - 支持用户编写Python代码
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Callable
from dataclasses import dataclass


@dataclass
class IndicatorOutput:
    """指标输出结构"""
    name: str
    plots: list  # [{name, data, color, overlay}]
    signals: list  # [{type, text, data, color}]


class CustomIndicatorEngine:
    """自定义指标引擎"""

    def __init__(self):
        self._builtins = {
            "pd": pd,
            "np": np,
            "df": None,
        }

    def execute(self, code: str, df: pd.DataFrame) -> Dict[str, Any]:
        """
        执行用户指标代码

        Args:
            code: 用户编写的Python代码
            df: K线数据DataFrame

        Returns:
            指标结果 dict
        """
        self._builtins["df"] = df.copy()

        # 创建执行环境
        local_env = self._builtins.copy()

        try:
            # 执行用户代码
            exec(code, local_env)

            # 检查输出
            if "output" not in local_env:
                return self._default_output(df)

            output = local_env["output"]

            # 验证输出格式
            if not isinstance(output, dict):
                return self._default_output(df)

            return output

        except Exception as e:
            return {
                "error": str(e),
                "name": "Error",
                "plots": [],
                "signals": []
            }

    def _default_output(self, df: pd.DataFrame) -> Dict[str, Any]:
        """默认输出（无自定义指标时）"""
        return {
            "name": "No Custom Indicator",
            "plots": [],
            "signals": []
        }

    def extract_signals(self, output: Dict[str, Any]) -> pd.DataFrame:
        """
        从指标输出中提取信号

        Returns:
            DataFrame with buy/sell columns
        """
        if "signals" not in output:
            return pd.DataFrame()

        signals = output["signals"]
        if not signals:
            return pd.DataFrame()

        df_signals = pd.DataFrame()

        for sig in signals:
            sig_type = sig.get("type", "")
            data = sig.get("data", [])

            if not data:
                continue

            col_name = sig_type if sig_type in ("buy", "sell", "cover") else f"signal_{sig_type}"
            df_signals[col_name] = pd.Series(data)

        return df_signals

    def validate_code(self, code: str) -> tuple:
        """
        验证代码语法

        Returns:
            (is_valid, error_message)
        """
        try:
            compile(code, "<indicator>", "exec")
            return True, ""
        except SyntaxError as e:
            return False, f"Syntax error at line {e.lineno}: {e.msg}"

    @staticmethod
    def get_example_code(indicator_type: str = "rsi") -> str:
        """获取示例代码"""
        examples = {
            "rsi": '''# RSI 自定义指标
# 参数可以在代码中使用变量

my_indicator_name = "自定义RSI"
my_indicator_description = "基于RSI的买卖信号"

rsi_len = 14
delta = df['close'].diff()
gain = delta.clip(lower=0)
loss = (-delta).clip(lower=0)
avg_gain = gain.ewm(alpha=1/rsi_len, adjust=False).mean()
avg_loss = loss.ewm(alpha=1/rsi_len, adjust=False).mean()
rs = avg_gain / avg_loss.replace(0, np.nan)
rsi = 100 - (100 / (1 + rs))
rsi = rsi.fillna(50)

# 边缘触发信号（避免重复信号）
raw_buy = rsi < 30
raw_sell = rsi > 70
buy = raw_buy.fillna(False) & (~raw_buy.shift(1).fillna(False))
sell = raw_sell.fillna(False) & (~raw_sell.shift(1).fillna(False))
df['buy'] = buy.astype(bool)
df['sell'] = sell.astype(bool)

# 信号标记
buy_marks = [df['low'].iloc[i] * 0.995 if bool(buy.iloc[i]) else None for i in range(len(df))]
sell_marks = [df['high'].iloc[i] * 1.005 if bool(sell.iloc[i]) else None for i in range(len(df))]

output = {
    'name': my_indicator_name,
    'plots': [
        {'name': 'RSI(14)', 'data': rsi.tolist(), 'color': '#faad14', 'overlay': False}
    ],
    'signals': [
        {'type': 'buy', 'text': 'B', 'data': buy_marks, 'color': '#00E676'},
        {'type': 'sell', 'text': 'S', 'data': sell_marks, 'color': '#FF5252'}
    ]
}
''',
            "macd": '''# MACD 自定义指标

my_indicator_name = "自定义MACD"
my_indicator_description = "MACD金叉死叉信号"

exp12 = df['close'].ewm(span=12, adjust=False).mean()
exp26 = df['close'].ewm(span=26, adjust=False).mean()
dif = exp12 - exp26
dea = dif.ewm(span=9, adjust=False).mean()
hist = dif - dea

# 金叉死叉信号
golden = (dif > dea) & (dif.shift(1) <= dea.shift(1))
death = (dif < dea) & (dif.shift(1) >= dea.shift(1))
df['buy'] = golden.fillna(False).astype(bool)
df['sell'] = death.fillna(False).astype(bool)

buy_marks = [df['low'].iloc[i] * 0.995 if bool(df['buy'].iloc[i]) else None for i in range(len(df))]
sell_marks = [df['high'].iloc[i] * 1.005 if bool(df['sell'].iloc[i]) else None for i in range(len(df))]

output = {
    'name': my_indicator_name,
    'plots': [
        {'name': 'DIF', 'data': dif.tolist(), 'color': '#1890ff', 'overlay': False},
        {'name': 'DEA', 'data': dea.tolist(), 'color': '#ff7a45', 'overlay': False},
        {'name': 'Hist', 'data': hist.tolist(), 'color': '#888888', 'overlay': False}
    ],
    'signals': [
        {'type': 'buy', 'text': 'B', 'data': buy_marks, 'color': '#00E676'},
        {'type': 'sell', 'text': 'S', 'data': sell_marks, 'color': '#FF5252'}
    ]
}
''',
            "boll": '''# 布林带自定义指标

my_indicator_name = "自定义布林带"
my_indicator_description = "布林带突破策略"

period = 20
mult = 2.0
mid = df['close'].rolling(period, min_periods=1).mean()
std = df['close'].rolling(period, min_periods=1).std()
upper = mid + mult * std
lower = mid - mult * std

# 突破信号
raw_buy = df['close'] < lower
raw_sell = df['close'] > upper
buy = raw_buy.fillna(False) & (~raw_buy.shift(1).fillna(False))
sell = raw_sell.fillna(False) & (~raw_sell.shift(1).fillna(False))
df['buy'] = buy.astype(bool)
df['sell'] = sell.astype(bool)

buy_marks = [df['low'].iloc[i] * 0.995 if bool(buy.iloc[i]) else None for i in range(len(df))]
sell_marks = [df['high'].iloc[i] * 1.005 if bool(sell.iloc[i]) else None for i in range(len(df))]

output = {
    'name': my_indicator_name,
    'plots': [
        {'name': 'Upper', 'data': upper.tolist(), 'color': '#69c0ff', 'overlay': True},
        {'name': 'Middle', 'data': mid.tolist(), 'color': '#d9d9d9', 'overlay': True},
        {'name': 'Lower', 'data': lower.tolist(), 'color': '#69c0ff', 'overlay': True}
    ],
    'signals': [
        {'type': 'buy', 'text': 'B', 'data': buy_marks, 'color': '#00E676'},
        {'type': 'sell', 'text': 'S', 'data': sell_marks, 'color': '#FF5252'}
    ]
}
'''
        }
        return examples.get(indicator_type, examples["rsi"])


class BacktestWithCustomIndicator:
    """使用自定义指标的回测"""

    def __init__(self, engine: CustomIndicatorEngine):
        self.engine = engine

    def run(self, df: pd.DataFrame, indicator_code: str,
            strategy: Dict[str, Any]) -> Dict[str, Any]:
        """
        使用自定义指标运行回测

        Args:
            df: K线数据
            indicator_code: 自定义指标代码
            strategy: 策略配置

        Returns:
            回测结果
        """
        from quant_core.backtest import BacktestEngine, BacktestConfig

        # 执行自定义指标
        result = self.engine.execute(indicator_code, df)

        if "error" in result:
            return {"error": result["error"]}

        # 提取信号
        signals_df = self.engine.extract_signals(result)

        # 将信号合并到主数据
        if not signals_df.empty:
            df = df.join(signals_df)

        # 定义信号函数
        def signal_func(kdf, ind_df, i):
            if "buy" in kdf.columns and kdf["buy"].iloc[i]:
                return "buy"
            if "sell" in kdf.columns and kdf["sell"].iloc[i]:
                return "sell"
            return None

        # 运行回测
        cfg = BacktestConfig(
            initial_balance=strategy.get("initial_balance", 10000),
            commission=strategy.get("commission", 0.001),
            slippage=strategy.get("slippage", 0.0005)
        )
        bt_engine = BacktestEngine(config=cfg)

        return bt_engine.run(df, strategy, df, signal_func=signal_func)


def get_custom_engine() -> CustomIndicatorEngine:
    return CustomIndicatorEngine()
