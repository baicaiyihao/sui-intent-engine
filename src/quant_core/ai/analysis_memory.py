"""
Analysis Memory System - 分析历史记忆
基于原仓库 analysis_memory.py 简化，使用 SQLite 存储
"""

import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from quant_core.database import get_database


class AnalysisMemory:
    """
    分析记忆系统
    存储分析决策、市场上下文，支持相似历史模式查找
    """

    def __init__(self):
        self.db = get_database()
        self._ensure_table()

    def _ensure_table(self):
        """创建记忆表（如果不存在）"""
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS analysis_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market TEXT NOT NULL DEFAULT 'Crypto',
                    symbol TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    confidence INT DEFAULT 50,
                    price_at_analysis REAL,
                    summary TEXT,
                    reasons TEXT,
                    scores TEXT,
                    indicators_snapshot TEXT,
                    raw_result TEXT,
                    consensus_score REAL,
                    task_status TEXT DEFAULT 'completed',
                    task_error TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    validated_at TIMESTAMP,
                    actual_outcome TEXT,
                    actual_return_pct REAL,
                    was_correct INTEGER,
                    user_feedback TEXT,
                    feedback_at TIMESTAMP
                )
            """)
            conn.commit()

    def store(
        self,
        symbol: str,
        decision: str,
        confidence: int,
        price_at_analysis: float,
        summary: str,
        reasons: List[str],
        scores: Dict[str, Any],
        indicators_snapshot: Dict[str, Any],
        raw_result: Dict[str, Any],
        consensus_score: float,
        market: str = "Crypto",
        task_status: str = "completed",
        task_error: str = None,
    ) -> int:
        """
        存储分析结果

        Returns:
            记录的 ID
        """
        return self.db.execute_insert(
            """INSERT INTO analysis_memory
               (market, symbol, decision, confidence, price_at_analysis, summary,
                reasons, scores, indicators_snapshot, raw_result, consensus_score,
                task_status, task_error, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                market,
                symbol,
                decision,
                confidence,
                price_at_analysis,
                summary,
                json.dumps(reasons, ensure_ascii=False),
                json.dumps(scores, ensure_ascii=False),
                json.dumps(indicators_snapshot, ensure_ascii=False),
                json.dumps(raw_result, ensure_ascii=False),
                consensus_score,
                task_status,
                task_error,
                datetime.now().isoformat(),
            )
        )

    def get_recent(self, symbol: str = None, days: int = 7, limit: int = 10) -> List[Dict]:
        """获取最近的分析历史"""
        query = """
            SELECT * FROM analysis_memory
            WHERE created_at >= datetime('now', '-' || ? || ' days')
        """
        params = [days]

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self.db.execute_query(query, params)

        result = []
        for row in rows:
            result.append(self._row_to_dict(row))
        return result

    def get_similar_patterns(
        self,
        symbol: str,
        indicators: Dict[str, Any],
        limit: int = 5
    ) -> List[Dict]:
        """
        查找相似的历史形态

        基于 RSI 和 MACD 范围查找相似的历史分析
        """
        rsi = indicators.get("rsi")
        macd = indicators.get("macd")

        # 获取所有历史记录，然后通过 Python 过滤和排序
        query = """
            SELECT * FROM analysis_memory
            WHERE symbol = ? AND task_status = 'completed'
            AND indicators_snapshot IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 100
        """
        rows = self.db.execute_query(query, (symbol,))

        result = []
        scored_rows = []

        for row in rows:
            row_dict = self._row_to_dict(row)
            snapshot = row_dict.get("indicators_snapshot", {})
            if not snapshot:
                continue

            # 计算相似度分数
            score = 0
            if rsi:
                row_rsi = snapshot.get("rsi", 50)
                score += abs(row_rsi - rsi) / 100  # 归一化

            if macd:
                row_macd = snapshot.get("macd", 0)
                score += abs(row_macd - macd) / abs(macd) if macd != 0 else 0

            scored_rows.append((score, row_dict))

        # 按相似度排序
        scored_rows.sort(key=lambda x: x[0])

        # 取前 limit 个
        for score, row in scored_rows[:limit]:
            result.append(row)

        return result

    def record_feedback(self, memory_id: int, feedback: str) -> bool:
        """记录用户反馈"""
        feedback_time = datetime.now().isoformat()
        affected = self.db.execute_update(
            """UPDATE analysis_memory
               SET user_feedback = ?, feedback_at = ?
               WHERE id = ?""",
            (feedback, feedback_time, memory_id)
        )
        return affected > 0

    def update_outcome(
        self,
        memory_id: int,
        actual_outcome: str,
        actual_return_pct: float,
        was_correct: bool
    ) -> bool:
        """更新分析结果（用于回测验证）"""
        validated_at = datetime.now().isoformat()
        affected = self.db.execute_update(
            """UPDATE analysis_memory
               SET actual_outcome = ?, actual_return_pct = ?,
                   was_correct = ?, validated_at = ?
               WHERE id = ?""",
            (actual_outcome, actual_return_pct, was_correct, validated_at, memory_id)
        )
        return affected > 0

    def get_performance_stats(self, symbol: str = None, days: int = 30) -> Dict[str, Any]:
        """获取分析性能统计"""
        query = """
            SELECT
                COUNT(*) as total_analyses,
                SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END) as correct_count,
                SUM(CASE WHEN was_correct = 0 AND was_correct IS NOT NULL THEN 1 ELSE 0 END) as incorrect_count,
                AVG(CASE WHEN was_correct = 1 THEN 100.0 ELSE 0 END) as accuracy,
                COUNT(DISTINCT symbol) as unique_symbols
            FROM analysis_memory
            WHERE created_at >= datetime('now', '-' || ? || ' days')
        """
        params = [days]

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        rows = self.db.execute_query(query, params)
        if not rows:
            return {
                "total_analyses": 0,
                "correct_count": 0,
                "accuracy": 0,
                "unique_symbols": 0
            }

        row = rows[0]
        # SQLite 返回的列按 SELECT 顺序: total_analyses, correct_count, incorrect_count, accuracy, unique_symbols
        return {
            "total_analyses": row[0] if len(row) > 0 else 0,
            "correct_count": row[1] if len(row) > 1 else 0,
            "incorrect_count": row[2] if len(row) > 2 else 0,
            "accuracy": round(row[3] if len(row) > 3 else 0, 2),
            "unique_symbols": row[4] if len(row) > 4 else 0
        }

    def _row_to_dict(self, row: tuple) -> Dict[str, Any]:
        """将数据库行转换为字典"""
        columns = [
            "id", "market", "symbol", "decision", "confidence", "price_at_analysis",
            "summary", "reasons", "scores", "indicators_snapshot", "raw_result",
            "consensus_score", "task_status", "task_error", "updated_at", "created_at",
            "validated_at", "actual_outcome", "actual_return_pct", "was_correct",
            "user_feedback", "feedback_at"
        ]
        result = {}
        for i, col in enumerate(columns):
            if i < len(row):
                val = row[i]
                # 解析 JSON 字段
                if col in ("reasons", "scores", "indicators_snapshot", "raw_result") and val:
                    try:
                        val = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        pass
                result[col] = val
        return result


def get_analysis_memory() -> AnalysisMemory:
    """获取分析记忆实例"""
    return AnalysisMemory()
