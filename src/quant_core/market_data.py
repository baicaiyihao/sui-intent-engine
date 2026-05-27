"""
市场数据收集器
"""
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from quant_core.data_source import get_data_source


class MarketDataCollector:
    """市场数据收集器"""

    def __init__(self, exchange: str = None):
        self.data_source = get_data_source(exchange=exchange)

    def collect(self, symbol: str, timeframe: str, days: int = 30) -> pd.DataFrame:
        """
        收集历史数据

        Args:
            symbol: 交易对
            timeframe: 时间周期
            days: 收集天数（仅用于参考，实际受限于1000根K线）

        Returns:
            K线数据DataFrame
        """
        from quant_core import config

        # 获取最近的数据，不使用since限制（返回最近1000根K线）
        limit = min(1000, config.MAX_BACKTEST_KLINES)
        df = self.data_source.fetch_ohlcv(symbol, timeframe, since=None, limit=limit)
        return df

    def collect_multiple(self, symbols: List[str], timeframe: str, days: int = 30) -> Dict[str, pd.DataFrame]:
        """收集多个交易对的数据"""
        result = {}
        for symbol in symbols:
            try:
                result[symbol] = self.collect(symbol, timeframe, days)
            except Exception as e:
                print(f"Failed to collect {symbol}: {e}")
        return result

    def get_current_price(self, symbol: str) -> float:
        """获取当前价格"""
        ticker = self.data_source.fetch_ticker(symbol)
        return ticker.get("last", 0)

    def get_market_info(self, symbol: str) -> Dict[str, Any]:
        """获取市场信息"""
        return self.data_source.fetch_ticker(symbol)

    def get_order_book(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        """获取订单簿"""
        return self.data_source.fetch_order_book(symbol, limit=limit)


def get_market_data_collector(exchange: str = None) -> MarketDataCollector:
    return MarketDataCollector(exchange=exchange)
