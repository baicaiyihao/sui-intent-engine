"""
数据库模块 - SQLite持久化
"""
import sqlite3
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from contextlib import contextmanager

from quant_core import config


class Database:
    """SQLite数据库管理器"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            # 默认在项目根目录创建
            db_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(db_dir, "quantcore.db")
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute_insert(self, query: str, params: tuple = ()) -> int:
        """执行 INSERT 语句，返回最后插入的 ID"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            return cur.lastrowid

    def execute_query(self, query: str, params: tuple = ()) -> list:
        """执行 SELECT 语句，返回所有行"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            rows = cur.fetchall()
            return [tuple(row) for row in rows]

    def execute_update(self, query: str, params: tuple = ()) -> int:
        """执行 UPDATE/DELETE 语句，返回影响的行数"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            return cur.rowcount

    def _init_db(self):
        """初始化数据库表"""
        with self.get_connection() as conn:
            cur = conn.cursor()

            # 回测运行表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS backtest_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    strategy_name TEXT DEFAULT '',
                    initial_balance REAL DEFAULT 10000,
                    final_balance REAL DEFAULT 10000,
                    total_pnl REAL DEFAULT 0,
                    total_pnl_pct REAL DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    max_drawdown_pct REAL DEFAULT 0,
                    sharpe_ratio REAL DEFAULT 0,
                    sortino_ratio REAL DEFAULT 0,
                    total_trades INTEGER DEFAULT 0,
                    commission REAL DEFAULT 0,
                    slippage REAL DEFAULT 0,
                    config_json TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 回测交易明细表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS backtest_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    entry_time TEXT NOT NULL,
                    exit_time TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    amount REAL NOT NULL,
                    pnl REAL DEFAULT 0,
                    pnl_pct REAL DEFAULT 0,
                    commission REAL DEFAULT 0,
                    slippage REAL DEFAULT 0,
                    reason TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES backtest_runs(id)
                )
            """)

            # 权益曲线表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS equity_curve (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    point_index INTEGER DEFAULT 0,
                    time TEXT NOT NULL,
                    equity REAL NOT NULL,
                    drawdown REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES backtest_runs(id)
                )
            """)

            # K线缓存表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kline_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, timeframe, start_time)
                )
            """)

            # 策略记录表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS strategies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    code TEXT DEFAULT '',
                    indicators_json TEXT DEFAULT '[]',
                    risk_management_json TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 通知表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT DEFAULT 'alert',
                    symbol TEXT DEFAULT '',
                    title TEXT DEFAULT '',
                    message TEXT DEFAULT '',
                    payload TEXT DEFAULT '{}',
                    is_read INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 创建索引
            cur.execute("CREATE INDEX IF NOT EXISTS idx_runs_symbol ON backtest_runs(symbol)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_runs_created ON backtest_runs(created_at)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_trades_run_id ON backtest_trades(run_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_equity_run_id ON equity_curve(run_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_kline_symbol ON kline_cache(symbol, timeframe)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_notifications_created ON notifications(created_at)")

            conn.commit()

    # ==================== 回测相关 ====================

    def save_backtest_run(self, symbol: str, timeframe: str, result: Dict[str, Any],
                          strategy_name: str = "", config: Dict = None) -> int:
        """
        保存回测结果

        Returns:
            run_id
        """
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO backtest_runs (
                    symbol, timeframe, strategy_name, initial_balance, final_balance,
                    total_pnl, total_pnl_pct, win_rate, max_drawdown_pct,
                    sharpe_ratio, sortino_ratio, total_trades, commission, slippage, config_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol, timeframe, strategy_name,
                result.get('initial_balance', 10000),
                result.get('final_balance', 10000),
                result.get('total_pnl', 0),
                result.get('total_pnl_pct', 0),
                result.get('win_rate', 0),
                result.get('max_drawdown_pct', 0),
                result.get('sharpe_ratio', 0),
                result.get('sortino_ratio', 0),
                result.get('total_trades', 0),
                result.get('total_commission', 0),
                result.get('total_slippage', 0),
                json.dumps(config or {})
            ))
            run_id = cur.lastrowid

            # 保存交易明细
            for i, trade in enumerate(result.get('trades', [])):
                cur.execute("""
                    INSERT INTO backtest_trades (
                        run_id, entry_time, exit_time, side, entry_price, exit_price,
                        amount, pnl, pnl_pct, commission, slippage, reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    run_id, trade['entry_time'], trade['exit_time'], trade['side'],
                    trade['entry_price'], trade['exit_price'], trade['amount'],
                    trade['pnl'], trade['pnl_pct'], trade.get('commission', 0),
                    trade.get('slippage', 0), trade['reason']
                ))

            # 保存权益曲线
            for i, point in enumerate(result.get('equity_curve', [])):
                cur.execute("""
                    INSERT INTO equity_curve (run_id, point_index, time, equity, drawdown)
                    VALUES (?, ?, ?, ?, ?)
                """, (run_id, i, point['time'], point['equity'], point['drawdown']))

            conn.commit()
            return run_id

    def get_backtest_runs(self, symbol: str = None, limit: int = 50) -> List[Dict]:
        """获取回测历史"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            if symbol:
                cur.execute("""
                    SELECT * FROM backtest_runs
                    WHERE symbol = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (symbol, limit))
            else:
                cur.execute("""
                    SELECT * FROM backtest_runs
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))

            rows = cur.fetchall()
            return [dict(row) for row in rows]

    def get_backtest_detail(self, run_id: int) -> Dict[str, Any]:
        """获取回测详情"""
        with self.get_connection() as conn:
            cur = conn.cursor()

            # 获取回测基本信息
            cur.execute("SELECT * FROM backtest_runs WHERE id = ?", (run_id,))
            run = cur.fetchone()
            if not run:
                return {}

            result = dict(run)

            # 获取交易明细
            cur.execute("SELECT * FROM backtest_trades WHERE run_id = ? ORDER BY entry_time", (run_id,))
            result['trades'] = [dict(row) for row in cur.fetchall()]

            # 获取权益曲线
            cur.execute("SELECT * FROM equity_curve WHERE run_id = ? ORDER BY point_index", (run_id,))
            result['equity_curve'] = [dict(row) for row in cur.fetchall()]

            return result

    def delete_backtest_run(self, run_id: int) -> bool:
        """删除回测记录"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM equity_curve WHERE run_id = ?", (run_id,))
            cur.execute("DELETE FROM backtest_trades WHERE run_id = ?", (run_id,))
            cur.execute("DELETE FROM backtest_runs WHERE id = ?", (run_id,))
            return True

    # ==================== K线缓存 ====================

    def save_klines(self, symbol: str, timeframe: str, start_time: str,
                    end_time: str, data: List) -> bool:
        """保存K线数据缓存"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO kline_cache
                (symbol, timeframe, start_time, end_time, data_json)
                VALUES (?, ?, ?, ?, ?)
            """, (symbol, timeframe, start_time, end_time, json.dumps(data)))
            return True

    def get_klines(self, symbol: str, timeframe: str,
                    start_time: str = None, end_time: str = None) -> Optional[List]:
        """获取K线缓存"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            if start_time and end_time:
                cur.execute("""
                    SELECT data_json FROM kline_cache
                    WHERE symbol = ? AND timeframe = ?
                    AND start_time >= ? AND end_time <= ?
                """, (symbol, timeframe, start_time, end_time))
            else:
                cur.execute("""
                    SELECT data_json FROM kline_cache
                    WHERE symbol = ? AND timeframe = ?
                    ORDER BY start_time DESC
                    LIMIT 1
                """, (symbol, timeframe))

            row = cur.fetchone()
            if row:
                return json.loads(row['data_json'])
            return None

    # ==================== 策略管理 ====================

    def save_strategy(self, name: str, description: str, code: str,
                       indicators: List, risk_management: Dict) -> int:
        """保存策略"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO strategies (name, description, code, indicators_json, risk_management_json)
                VALUES (?, ?, ?, ?, ?)
            """, (name, description, code, json.dumps(indicators), json.dumps(risk_management)))
            conn.commit()
            return cur.lastrowid

    def get_strategy(self, strategy_id: int) -> Optional[Dict]:
        """获取策略"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM strategies WHERE id = ?", (strategy_id,))
            row = cur.fetchone()
            if row:
                result = dict(row)
                result['indicators'] = json.loads(result.get('indicators_json', '[]'))
                result['risk_management'] = json.loads(result.get('risk_management_json', '{}'))
                return result
            return None

    def list_strategies(self, limit: int = 50) -> List[Dict]:
        """列出策略"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, name, description, created_at, updated_at
                FROM strategies
                ORDER BY updated_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cur.fetchall()]

    def delete_strategy(self, strategy_id: int) -> bool:
        """删除策略"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM strategies WHERE id = ?", (strategy_id,))
            return True

    # ==================== 通知相关 ====================

    def save_notification(self, notification_type: str, symbol: str,
                          title: str, message: str, payload: Dict = None) -> int:
        """保存通知"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO notifications (type, symbol, title, message, payload)
                VALUES (?, ?, ?, ?, ?)
            """, (notification_type, symbol, title, message, json.dumps(payload or {})))
            conn.commit()
            return cur.lastrowid

    def get_notifications(self, limit: int = 20, unread_only: bool = False) -> List[Dict]:
        """获取通知列表"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            if unread_only:
                cur.execute("""
                    SELECT * FROM notifications
                    WHERE is_read = 0
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
            else:
                cur.execute("""
                    SELECT * FROM notifications
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
            return [dict(row) for row in cur.fetchall()]

    def mark_notification_read(self, notification_id: int) -> bool:
        """标记通知为已读"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
            return True

    def mark_all_notifications_read(self) -> bool:
        """标记所有通知为已读"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE notifications SET is_read = 1")
            return True

    def get_unread_count(self) -> int:
        """获取未读通知数量"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as cnt FROM notifications WHERE is_read = 0")
            row = cur.fetchone()
            return row['cnt'] if row else 0

    def clear_notifications(self, before_hours: int = 24) -> int:
        """清理旧通知（保留最近 N 小时）"""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                DELETE FROM notifications
                WHERE is_read = 1
                AND created_at < datetime('now', '-' || ? || ' hours')
            """, (before_hours,))
            return cur.rowcount


# 全局数据库实例
_db_instance: Optional[Database] = None


def get_database() -> Database:
    """获取数据库实例"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
