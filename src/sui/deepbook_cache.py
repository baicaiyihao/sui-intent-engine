"""
DeepBook 数据缓存服务
从官方 DeepBook Indexer 获取数据，本地缓存后提供给前端
"""
import requests
import time
from datetime import datetime
from typing import Dict, List, Optional
import sqlite3
import os

# DeepBook 官方索引器
DEEPBOOK_INDEXER = "https://deepbook-indexer.mainnet.mystenlabs.com"
DB_PATH = os.path.join(os.path.dirname(__file__), "deepbook_cache.db")


class DeepBookCache:
    """DeepBook 数据缓存"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """初始化缓存表"""
        with self._get_conn() as conn:
            # K 线缓存表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS klines_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interval TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    fetched_at INTEGER NOT NULL,
                    UNIQUE(interval, timestamp)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_klines_interval ON klines_cache(interval, timestamp)")

            # Ticker 缓存表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ticker_cache (
                    id INTEGER PRIMARY KEY,
                    trading_pairs TEXT NOT NULL,
                    last_price REAL,
                    price_change_percent REAL,
                    highest_price_24h REAL,
                    lowest_price_24h REAL,
                    base_volume REAL,
                    quote_volume REAL,
                    highest_bid REAL,
                    lowest_ask REAL,
                    base_currency TEXT,
                    quote_currency TEXT,
                    fetched_at INTEGER NOT NULL
                )
            """)

            # 订单簿缓存表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS orderbook_cache (
                    id INTEGER PRIMARY KEY,
                    bids TEXT NOT NULL,
                    asks TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    fetched_at INTEGER NOT NULL
                )
            """)

            conn.commit()

    def fetch_ohlcv(self, interval: str = '1h', limit: int = 100) -> List[Dict]:
        """从官方索引器获取 K 线数据"""
        try:
            url = f"{DEEPBOOK_INDEXER}/ohclv/SUI_USDC"
            params = {"interval": interval, "limit": limit}
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            candles = []
            if data.get("candles"):
                for c in data["candles"]:
                    candles.append({
                        "time": c[0] // 1000,  # 转换为秒
                        "open": c[1],
                        "high": c[2],
                        "low": c[3],
                        "close": c[4],
                        "volume": c[5]
                    })

            # 按时间升序排列
            candles.sort(key=lambda x: x["time"])
            return candles

        except Exception as e:
            print(f"Failed to fetch OHLCV: {e}")
            return []

    def fetch_ticker(self) -> Optional[Dict]:
        """从官方索引器获取 ticker 数据"""
        try:
            url = f"{DEEPBOOK_INDEXER}/summary"
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            # 找到 SUI_USDC
            for item in data:
                if item.get("trading_pairs") == "SUI_USDC":
                    return {
                        "last_price": item.get("last_price"),
                        "price_change_percent": item.get("price_change_percent_24h"),
                        "high": item.get("highest_price_24h"),
                        "low": item.get("lowest_price_24h"),
                        "base_volume": item.get("base_volume"),
                        "quote_volume": item.get("quote_volume"),
                        "bid": item.get("highest_bid"),
                        "ask": item.get("lowest_ask")
                    }
            return None

        except Exception as e:
            print(f"Failed to fetch ticker: {e}")
            return None

    def fetch_orderbook(self, depth: int = 20) -> Optional[Dict]:
        """从官方索引器获取订单簿数据"""
        try:
            url = f"{DEEPBOOK_INDEXER}/orderbook/SUI_USDC"
            params = {"level": 2, "depth": depth}
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()

        except Exception as e:
            print(f"Failed to fetch orderbook: {e}")
            return None

    def cache_ohlcv(self, interval: str, candles: List[Dict]):
        """缓存 K 线数据"""
        if not candles:
            return

        now = int(time.time() * 1000)
        with self._get_conn() as conn:
            for c in candles:
                conn.execute("""
                    INSERT OR REPLACE INTO klines_cache
                    (interval, timestamp, open, high, low, close, volume, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (interval, c["time"], c["open"], c["high"], c["low"], c["close"], c["volume"], now))
            conn.commit()

    def cache_ticker(self, ticker: Dict):
        """缓存 ticker 数据"""
        if not ticker:
            return

        now = int(time.time() * 1000)
        with self._get_conn() as conn:
            conn.execute("DELETE FROM ticker_cache")
            conn.execute("""
                INSERT INTO ticker_cache
                (id, trading_pairs, last_price, price_change_percent, highest_price_24h, lowest_price_24h, base_volume, quote_volume, highest_bid, lowest_ask, base_currency, quote_currency, fetched_at)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "SUI_USDC",
                ticker.get("last_price"),
                ticker.get("price_change_percent"),
                ticker.get("high"),
                ticker.get("low"),
                ticker.get("base_volume"),
                ticker.get("quote_volume"),
                ticker.get("bid"),
                ticker.get("ask"),
                "SUI",
                "USDC",
                now
            ))
            conn.commit()

    def cache_orderbook(self, orderbook: Dict):
        """缓存订单簿数据"""
        if not orderbook:
            return

        now = int(time.time() * 1000)
        with self._get_conn() as conn:
            conn.execute("DELETE FROM orderbook_cache")
            conn.execute("""
                INSERT INTO orderbook_cache (id, bids, asks, timestamp, fetched_at)
                VALUES (1, ?, ?, ?, ?)
            """, (
                str(orderbook.get("bids", [])),
                str(orderbook.get("asks", [])),
                orderbook.get("timestamp", 0),
                now
            ))
            conn.commit()

    def get_cached_klines(self, interval: str, limit: int = 100) -> List[Dict]:
        """获取缓存的 K 线数据（最新的 limit 条）"""
        with self._get_conn() as conn:
            # 先获取最新的 limit 条，再按时间正序排列返回
            rows = conn.execute("""
                SELECT timestamp, open, high, low, close, volume
                FROM klines_cache
                WHERE interval = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (interval, limit)).fetchall()

            # 反转数组使其按时间升序排列（图表需要）
            rows = list(reversed(rows))

            return [
                {
                    "time": row[0],
                    "open": row[1],
                    "high": row[2],
                    "low": row[3],
                    "close": row[4],
                    "volume": row[5]
                }
                for row in rows
            ]

    def get_cached_ticker(self) -> Optional[Dict]:
        """获取缓存的 ticker 数据"""
        with self._get_conn() as conn:
            row = conn.execute("""
                SELECT last_price, price_change_percent, highest_price_24h, lowest_price_24h, base_volume, quote_volume, highest_bid, lowest_ask, fetched_at
                FROM ticker_cache WHERE id = 1
            """).fetchone()

            if row:
                return {
                    "last_price": row[0],
                    "price_change_percent": row[1],
                    "high": row[2],
                    "low": row[3],
                    "volume": row[4],
                    "bid": row[6],  # highest_bid
                    "ask": row[7],  # lowest_ask
                    "cached_at": row[8]
                }
            return None

    def get_cached_orderbook(self) -> Optional[Dict]:
        """获取缓存的订单簿数据"""
        with self._get_conn() as conn:
            row = conn.execute("SELECT bids, asks, timestamp, fetched_at FROM orderbook_cache WHERE id = 1").fetchone()

            if row:
                return {
                    "bids": eval(row[0]),  # 安全问题：生产环境应该用 json.parse
                    "asks": eval(row[1]),
                    "timestamp": row[2],
                    "cached_at": row[3]
                }
            return None

    def refresh_all(self) -> Dict:
        """刷新所有缓存数据"""
        result = {
            "ohlcv": {"fetched": 0, "cached": 0},
            "ticker": {"fetched": False, "cached": False},
            "orderbook": {"fetched": False, "cached": False}
        }

        # 刷新各 timeframe 的 K 线
        for interval in ['1m', '5m', '15m', '1h', '4h', '1d']:
            candles = self.fetch_ohlcv(interval=interval, limit=100)
            if candles:
                self.cache_ohlcv(interval, candles)
                result["ohlcv"]["fetched"] += len(candles)
                result["ohlcv"]["cached"] += 1

        # 刷新 ticker
        ticker = self.fetch_ticker()
        if ticker:
            self.cache_ticker(ticker)
            result["ticker"] = {"fetched": True, "cached": True}

        # 刷新订单簿
        orderbook = self.fetch_orderbook()
        if orderbook:
            self.cache_orderbook(orderbook)
            result["orderbook"] = {"fetched": True, "cached": True}

        return result


# 全局实例
_cache: Optional[DeepBookCache] = None


def get_deepbook_cache() -> DeepBookCache:
    global _cache
    if _cache is None:
        _cache = DeepBookCache()
    return _cache
