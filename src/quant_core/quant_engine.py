"""
QuantEngine - 量化交易引擎
"""
import pandas as pd
from typing import Dict, Any, Optional, List

from quant_core.ai.analyzer import MarketAnalyzer
from quant_core.backtest.engine import BacktestEngine, BacktestConfig, run_backtest
from quant_core.data_source import get_data_source
from quant_core.market_data import get_market_data_collector, MarketDataCollector
from quant_core.strategy.compiler import StrategyCompiler
from quant_core.strategy.indicators import calculate_indicator
from quant_core.executor.exchange import OrderExecutor
from quant_core.database import get_database


class QuantEngine:
    """量化交易引擎"""

    def __init__(self, exchange: str = None, testnet: bool = True):
        self.exchange = exchange
        self.testnet = testnet
        self.data_source = get_data_source(exchange=exchange, testnet=testnet)
        self.market_collector = get_market_data_collector(exchange=exchange)
        self.analyzer = MarketAnalyzer()
        self.strategy_compiler = StrategyCompiler()
        self.executor = OrderExecutor(exchange=exchange, testnet=testnet)
        self.db = get_database()

    def analyze(self, symbol: str, timeframe: str = "1h", days: int = 30) -> Dict[str, Any]:
        """
        分析交易对

        Args:
            symbol: 交易对，如 "BTC/USDT"
            timeframe: 时间周期
            days: 分析天数

        Returns:
            分析结果
        """
        df = self.market_collector.collect(symbol, timeframe, days)
        if df.empty:
            return {"error": f"No data for {symbol}"}

        # 获取实时价格
        try:
            ticker = self.data_source.fetch_ticker(symbol)
            live_price = ticker.get("last") if isinstance(ticker, dict) else None
        except Exception:
            live_price = None

        return self.analyzer.analyze(df, symbol, timeframe, live_price=live_price)

    def backtest(self, symbol: str, strategy: Dict[str, Any],
                 timeframe: str = "1h", days: int = 30,
                 initial_balance: float = 10000) -> Dict[str, Any]:
        """
        回测策略

        Args:
            symbol: 交易对
            strategy: 策略配置
            timeframe: 时间周期
            days: 回测天数
            initial_balance: 初始资金

        Returns:
            回测结果
        """
        df = self.market_collector.collect(symbol, timeframe, days)
        if df.empty:
            return {"error": f"No data for {symbol}"}

        # 计算指标
        indicators_df = df.copy()
        for ind in strategy.get("indicators", []):
            indicators_df = calculate_indicator(indicators_df, ind["name"], **ind.get("params", {}))

        # 创建回测配置
        cfg = BacktestConfig(
            initial_balance=initial_balance,
            commission=strategy.get("commission", 0.001),
            slippage=strategy.get("slippage", 0.0005),
            leverage=strategy.get("leverage", 1.0)
        )
        engine = BacktestEngine(config=cfg)
        return engine.run(df, strategy, indicators_df)

    def compile_and_backtest(self, symbol: str, strategy_description: str,
                             timeframe: str = "1h", days: int = 30) -> Dict[str, Any]:
        """编译策略并回测"""
        # 获取市场数据用于编译
        df = self.market_collector.collect(symbol, timeframe, days)
        market_info = self.market_collector.get_market_info(symbol)

        # 编译策略
        strategy = self.strategy_compiler.compile_strategy(
            strategy_description,
            {**market_info, "symbol": symbol}
        )

        # 回测
        return {
            "strategy": strategy,
            "backtest": self.backtest(symbol, strategy, timeframe, days)
        }

    def execute_trade(self, symbol: str, side: str, amount: float,
                      order_type: str = "market", price: float = None) -> Dict[str, Any]:
        """
        执行交易

        Args:
            symbol: 交易对
            side: "buy" 或 "sell"
            amount: 数量
            order_type: "market" 或 "limit"
            price: 价格(限价单需要)

        Returns:
            订单结果
        """
        return self.executor.place_order(symbol, side, order_type, amount, price)

    def get_positions(self, symbol: str = None) -> List[Dict[str, Any]]:
        """获取当前持仓"""
        balance = self.executor.get_balance()
        if "error" in balance:
            return []

        positions = []
        for asset, info in balance.items():
            if isinstance(info, dict) and info.get("total", 0) > 0:
                positions.append({
                    "asset": asset,
                    "total": info["total"],
                    "free": info.get("free", 0),
                    "used": info.get("used", 0)
                })
        return positions

    def get_orders(self, symbol: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """获取订单历史"""
        if symbol:
            return self.data_source.fetch_orders(symbol, limit=limit)
        return []

    def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """取消订单"""
        return self.executor.cancel_order(order_id, symbol)

    # ==================== 回测历史管理 ====================

    def save_backtest(self, symbol: str, timeframe: str, result: Dict[str, Any],
                      strategy_name: str = "", config: Dict = None) -> int:
        """
        保存回测结果到数据库

        Args:
            symbol: 交易对
            timeframe: 时间周期
            result: 回测结果
            strategy_name: 策略名称
            config: 策略配置

        Returns:
            run_id
        """
        return self.db.save_backtest_run(symbol, timeframe, result, strategy_name, config)

    def get_backtest_history(self, symbol: str = None, limit: int = 50) -> List[Dict]:
        """获取回测历史"""
        return self.db.get_backtest_runs(symbol=symbol, limit=limit)

    def get_backtest_detail(self, run_id: int) -> Dict[str, Any]:
        """获取回测详情"""
        return self.db.get_backtest_detail(run_id)

    def delete_backtest(self, run_id: int) -> bool:
        """删除回测记录"""
        return self.db.delete_backtest_run(run_id)

    # ==================== 策略管理 ====================

    def save_strategy(self, name: str, description: str = "",
                     code: str = "", indicators: List = None,
                     risk_management: Dict = None) -> int:
        """保存策略到数据库"""
        return self.db.save_strategy(
            name, description, code,
            indicators or [],
            risk_management or {}
        )

    def get_strategy(self, strategy_id: int) -> Optional[Dict]:
        """获取策略"""
        return self.db.get_strategy(strategy_id)

    def list_strategies(self, limit: int = 50) -> List[Dict]:
        """列出策略"""
        return self.db.list_strategies(limit=limit)

    def delete_strategy(self, strategy_id: int) -> bool:
        """删除策略"""
        return self.db.delete_strategy(strategy_id)
