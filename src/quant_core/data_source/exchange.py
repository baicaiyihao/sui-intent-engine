"""
交易所数据源 - 使用CCXT统一接口
"""
import ccxt
import pandas as pd
import os
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from quant_core import config


class ExchangeDataSource:
    """统一交易所数据源"""

    def __init__(self, exchange: str = None, testnet: bool = True):
        self.exchange_name = exchange or config.DEFAULT_EXCHANGE
        self.testnet = testnet
        self.exchange = self._init_exchange()

    def _init_exchange(self):
        """初始化交易所连接"""
        exchange_id = self.exchange_name.lower()

        # 交易所映射
        exchange_map = {
            "binance": ccxt.binance,
            "okx": ccxt.okx,
            "bybit": ccxt.bybit,
            "huobi": ccxt.huobi,
            "kucoin": ccxt.kucoin,
            "gate": ccxt.gate,
        }

        if exchange_id not in exchange_map:
            raise ValueError(f"Unsupported exchange: {self.exchange_name}")

        exchange_class = exchange_map[exchange_id]

        # 构建初始化参数
        params = {
            "enableRateLimit": config.CCXT_ENABLE_RATE_LIMIT,
            "timeout": config.CCXT_TIMEOUT,
        }

        # 添加API密钥(如果配置)
        if config.EXCHANGE_API_KEY:
            params["apiKey"] = config.EXCHANGE_API_KEY
            params["secret"] = config.EXCHANGE_SECRET
            if config.EXCHANGE_PASSWORD:
                params["password"] = config.EXCHANGE_PASSWORD

        # Binance现货市场配置 - 确保使用现货API
        if exchange_id == "binance":
            params["options"] = {
                "defaultType": "spot",
                "fetchMarkets": {"types": ["spot"]},  # 只加载现货市场，不访问期货API
            }
            # testnet 必须作为顶层参数传递
            params["testnet"] = self.testnet

        exchange = exchange_class(params)

        # 设置代理 - 使用 session.proxies 方式
        proxy = config.CCXT_PROXY or getattr(config, 'PROXY_URL', None) or os.getenv("http_proxy") or os.getenv("HTTP_PROXY")
        if proxy:
            session = requests.Session()
            # 确保proxy URL格式正确（不以/结尾）
            proxy_url = proxy.rstrip('/')
            session.proxies = {
                "http": proxy_url,
                "https": proxy_url,
            }
            exchange.session = session

        return exchange

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", since: int = None, limit: int = None) -> pd.DataFrame:
        """获取K线数据"""
        # CCXT timeframe映射
        tf_map = {
            "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1H": "1h", "2H": "2h", "4H": "4h", "6H": "6h", "8H": "8h",
            "12H": "12h", "1D": "1d", "3D": "3d", "1W": "1w"
        }
        tf = tf_map.get(timeframe, timeframe)

        # 计算limit
        if limit is None and since is None:
            limit = 1000
        elif limit is None:
            seconds = config.TIMEFRAME_SECONDS.get(timeframe, 3600)
            limit = min(1000, int((datetime.now().timestamp() * 1000 - since) / (seconds * 1000)) + 1)

        data = self.exchange.fetch_ohlcv(symbol, tf, since=since, limit=limit)

        df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        return df

    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """获取当前行情"""
        ticker = self.exchange.fetch_ticker(symbol)
        return {
            "symbol": symbol,
            "last": ticker["last"],
            "high": ticker["high"],
            "low": ticker["low"],
            "volume": ticker["baseVolume"],
            "change": ticker["change"],
            "change_pct": ticker["percentage"],
            "bid": ticker["bid"],
            "ask": ticker["ask"],
        }

    def fetch_order_book(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        """获取订单簿"""
        return self.exchange.fetch_order_book(symbol, limit=limit)

    def fetch_balance(self) -> Dict[str, Any]:
        """获取账户余额"""
        if not config.EXCHANGE_API_KEY:
            return {"error": "API key not configured"}
        return self.exchange.fetch_balance()

    def create_order(self, symbol: str, type_: str, side: str, amount: float, price: float = None, params: Dict = None) -> Dict:
        """创建订单"""
        return self.exchange.create_order(symbol, type_, side, amount, price=price, params=params or {})

    def cancel_order(self, order_id: str, symbol: str) -> Dict:
        """取消订单"""
        return self.exchange.cancel_order(order_id, symbol)

    def fetch_orders(self, symbol: str, since: int = None, limit: int = 100) -> List[Dict]:
        """获取订单历史"""
        return self.exchange.fetch_orders(symbol, since=since, limit=limit)

    @staticmethod
    def get_supported_exchanges() -> List[str]:
        return ["binance", "okx", "bybit", "huobi", "kucoin", "gate"]
