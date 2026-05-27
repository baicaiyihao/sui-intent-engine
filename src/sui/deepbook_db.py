"""
DeepBook Trade Database
存储 DeepBook 订单成交历史，提供 K 线数据查询
"""
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import json

DB_PATH = os.path.join(os.path.dirname(__file__), "deepbook_trades.db")

# DeepBook constants
USDC_DECIMALS = 1e6
SUI_DECIMALS = 1e9
SUI_USDC_POOL = "0xe05dafb5133bcffb8d59f4e12465dc0e9faeaa05e3e342a08fe135800e3e4407"


@dataclass
class Trade:
    """单笔成交记录"""
    tx_digest: str
    event_seq: int
    timestamp: int  # microseconds
    price: float  # USDC
    quantity: float  # SUI
    side: str  # 'buy' or 'sell'
    pool_id: str


class DeepBookDB:
    """DeepBook 成交数据库"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """初始化数据库表"""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tx_digest TEXT NOT NULL,
                    event_seq INTEGER NOT NULL,
                    timestamp INTEGER NOT NULL,
                    price REAL NOT NULL,
                    quantity REAL NOT NULL,
                    side TEXT NOT NULL,
                    pool_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(tx_digest, event_seq)
                )
            """)

            # 索引加速查询
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_pool ON trades(pool_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_side ON trades(side)")

            # 索引进度表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS index_progress (
                    pool_id TEXT PRIMARY KEY,
                    last_cursor TEXT,
                    last_timestamp INTEGER,
                    total_trades INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()

    def insert_trades(self, trades: List[Trade]) -> int:
        """批量插入成交记录"""
        if not trades:
            return 0

        inserted = 0
        with self._get_conn() as conn:
            for trade in trades:
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO trades
                        (tx_digest, event_seq, timestamp, price, quantity, side, pool_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        trade.tx_digest,
                        trade.event_seq,
                        trade.timestamp,
                        trade.price,
                        trade.quantity,
                        trade.side,
                        trade.pool_id
                    ))
                    inserted += 1
                except Exception as e:
                    print(f"Error inserting trade: {e}")
            conn.commit()
        return inserted

    def update_progress(self, pool_id: str, cursor: str, timestamp: int, total_trades: int):
        """更新索引进度"""
        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO index_progress
                (pool_id, last_cursor, last_timestamp, total_trades, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (pool_id, cursor, timestamp, total_trades))
            conn.commit()

    def get_progress(self, pool_id: str = SUI_USDC_POOL) -> Optional[Dict]:
        """获取索引进度"""
        with self._get_conn() as conn:
            row = conn.execute("""
                SELECT pool_id, last_cursor, last_timestamp, total_trades, updated_at
                FROM index_progress WHERE pool_id = ?
            """, (pool_id,)).fetchone()

            if row:
                return {
                    "pool_id": row[0],
                    "last_cursor": row[1],
                    "last_timestamp": row[2],
                    "total_trades": row[3],
                    "updated_at": row[4]
                }
        return None

    def get_trades(self, pool_id: str = SUI_USDC_POOL, limit: int = 1000) -> List[Trade]:
        """获取最近的成交记录"""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT tx_digest, event_seq, timestamp, price, quantity, side, pool_id
                FROM trades
                WHERE pool_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (pool_id, limit)).fetchall()

            return [Trade(
                tx_digest=row[0],
                event_seq=row[1],
                timestamp=row[2],
                price=row[3],
                quantity=row[4],
                side=row[5],
                pool_id=row[6]
            ) for row in rows]

    def get_klines(self, pool_id: str = SUI_USDC_POOL, timeframe: str = '1h',
                   start_time: int = None, end_time: int = None, limit: int = 500) -> List[Dict]:
        """
        获取 K 线数据

        timeframe: '1m', '5m', '15m', '1h', '4h', '1d'
        返回: [{time, open, high, low, close, volume}, ...]
        """
        interval_ms = {
            '1m': 60 * 1000,
            '5m': 5 * 60 * 1000,
            '15m': 15 * 60 * 1000,
            '1h': 60 * 60 * 1000,
            '4h': 4 * 60 * 60 * 1000,
            '1d': 24 * 60 * 60 * 1000
        }.get(timeframe, 60 * 60 * 1000)

        # timestamp is stored in microseconds, convert to seconds for grouping
        # ts_sec = timestamp / 1000000
        sql = """
            SELECT
                (timestamp / 1000000 / ?) * ? as key,
                MIN(timestamp / 1000000) as open_time,
                MIN(price) as low,
                MAX(price) as high,
                (SELECT price FROM trades t2
                 WHERE t2.pool_id = trades.pool_id
                 AND t2.timestamp / 1000000 >= (timestamp / 1000000 / ?) * ?
                 AND t2.timestamp / 1000000 < ((timestamp / 1000000 / ?) * ? + ?)
                 ORDER BY timestamp ASC LIMIT 1) as open_price,
                (SELECT price FROM trades t2
                 WHERE t2.pool_id = trades.pool_id
                 AND t2.timestamp / 1000000 >= (timestamp / 1000000 / ?) * ?
                 AND t2.timestamp / 1000000 < ((timestamp / 1000000 / ?) * ? + ?)
                 ORDER BY timestamp DESC LIMIT 1) as close_price,
                SUM(quantity) as volume,
                COUNT(*) as trade_count
            FROM trades
            WHERE pool_id = ?
        """
        params = [interval_ms, interval_ms, interval_ms, interval_ms, interval_ms, interval_ms,
                  interval_ms, interval_ms, interval_ms, interval_ms, interval_ms, interval_ms,
                  pool_id]

        if start_time:
            sql += " AND timestamp / 1000000 >= ?"
            params.append(start_time)
        if end_time:
            sql += " AND timestamp / 1000000 <= ?"
            params.append(end_time)

        sql += " GROUP BY key ORDER BY key DESC LIMIT ?"
        params.append(limit)

        with self._get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()

            klines = []
            for row in rows:
                open_time = row[1]
                klines.append({
                    "time": open_time,  # Already in seconds after dividing by 1000
                    "open": row[4] if row[4] else row[3],
                    "high": row[3],
                    "low": row[2],
                    "close": row[5] if row[5] else row[4],
                    "volume": row[6],
                    "trade_count": row[7]
                })

            return list(reversed(klines))  # Return oldest first for charting

    def get_ticker(self, pool_id: str = SUI_USDC_POOL, hours: int = 24) -> Optional[Dict]:
        """获取当前行情（24小时统计）"""
        cutoff = datetime.now().timestamp() * 1e6 - hours * 60 * 60 * 1000

        with self._get_conn() as conn:
            row = conn.execute("""
                SELECT
                    COUNT(*) as trade_count,
                    SUM(quantity) as total_volume,
                    MIN(price) as low,
                    MAX(price) as high,
                    (SELECT price FROM trades WHERE pool_id = ? AND timestamp >= ? ORDER BY timestamp DESC LIMIT 1) as last_price,
                    (SELECT price FROM trades WHERE pool_id = ? AND timestamp < ? ORDER BY timestamp DESC LIMIT 1) as open_price
                FROM trades
                WHERE pool_id = ? AND timestamp >= ?
            """, (pool_id, cutoff, pool_id, cutoff, pool_id, cutoff)).fetchone()

            if row and row[0] > 0:
                last = row[4] or 0
                open_price = row[5] or last
                change = ((last - open_price) / open_price * 100) if open_price > 0 else 0

                return {
                    "last_price": last,
                    "price_change_percent": change,
                    "high": row[3],
                    "low": row[2],
                    "volume": row[1],
                    "trade_count": row[0]
                }
        return None

    def get_total_trades_count(self, pool_id: str = SUI_USDC_POOL) -> int:
        """获取总成交记录数"""
        with self._get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) FROM trades WHERE pool_id = ?", (pool_id,)).fetchone()
            return row[0] if row else 0


# 全局实例
_db_instance: Optional[DeepBookDB] = None


def get_deepbook_db() -> DeepBookDB:
    global _db_instance
    if _db_instance is None:
        _db_instance = DeepBookDB()
    return _db_instance
