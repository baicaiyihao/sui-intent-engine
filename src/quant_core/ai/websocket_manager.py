"""
WebSocket Manager - 实时信号通知
当 AI 产生明确信号时，通过 WebSocket 推送给前端
"""

import json
import asyncio
from typing import Dict, Any, Set, Callable
from datetime import datetime


class WebSocketManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self._connections: Set[Any] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket):
        """添加新的 WebSocket 连接"""
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket):
        """移除 WebSocket 连接"""
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """广播消息到所有连接"""
        if not self._connections:
            return

        async with self._lock:
            disconnected = set()
            message_str = json.dumps(message, ensure_ascii=False)

            for conn in self._connections:
                try:
                    await conn.send_text(message_str)
                except Exception:
                    disconnected.add(conn)

            # 清理断开的连接
            self._connections -= disconnected

    async def send_signal(self, signal_type: str, data: Dict[str, Any]):
        """发送交易信号通知"""
        message = {
            "type": "signal",
            "signal_type": signal_type,  # "BUY", "SELL", "HOLD"
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast(message)

    @property
    def connection_count(self) -> int:
        """当前连接数"""
        return len(self._connections)


# 全局实例
_ws_manager = WebSocketManager()


def get_websocket_manager() -> WebSocketManager:
    return _ws_manager
