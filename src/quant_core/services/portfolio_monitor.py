"""
Portfolio Monitor Service - 持仓监控服务
后台定时检查持仓状态，发送通知
"""
import threading
import time
import traceback
from typing import Dict, Any, Optional, List
from datetime import datetime

from quant_core import get_database


class PortfolioMonitor:
    """持仓监控服务"""

    def __init__(self, check_interval: int = 60):
        """
        Args:
            check_interval: 检查间隔（秒），默认60秒
        """
        self.check_interval = check_interval
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_running = False

        # 监控配置
        self._monitors: Dict[str, Dict[str, Any]] = {}

    def add_monitor(
        self,
        symbol: str,
        entry_price: float,
        side: str,
        stop_loss_pct: float = 2.0,
        take_profit_pct: float = 6.0,
        alert_enabled: bool = True
    ):
        """添加监控"""
        self._monitors[symbol] = {
            "symbol": symbol,
            "entry_price": entry_price,
            "side": side,
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct,
            "alert_enabled": alert_enabled,
            "last_alert_at": None
        }

    def remove_monitor(self, symbol: str):
        """移除监控"""
        self._monitors.pop(symbol, None)

    def clear_monitors(self):
        """清空所有监控"""
        self._monitors.clear()

    def check_position(self, symbol: str, current_price: float) -> Optional[Dict[str, Any]]:
        """检查持仓状态，返回警报信息"""
        if symbol not in self._monitors:
            return None

        monitor = self._monitors[symbol]
        if not monitor.get("alert_enabled", True):
            return None

        entry_price = monitor["entry_price"]
        side = monitor["side"]
        stop_loss_pct = monitor.get("stop_loss_pct", 2.0)
        take_profit_pct = monitor.get("take_profit_pct", 6.0)

        # 计算盈亏
        if side == "long":
            pnl_pct = (current_price - entry_price) / entry_price * 100
        else:
            pnl_pct = (entry_price - current_price) / entry_price * 100

        pnl_pct = round(pnl_pct, 2)

        alert = None

        # 检查止盈
        if pnl_pct >= take_profit_pct:
            alert = {
                "type": "take_profit",
                "symbol": symbol,
                "side": side,
                "action": "close",
                "message": f"🎉 止盈信号: {symbol} 盈亏 {pnl_pct}% 达到 {take_profit_pct}% 目标",
                "current_price": current_price,
                "entry_price": entry_price,
                "pnl_pct": pnl_pct,
                "threshold": take_profit_pct
            }
        # 检查止损
        elif pnl_pct <= -stop_loss_pct:
            alert = {
                "type": "stop_loss",
                "symbol": symbol,
                "side": side,
                "action": "close",
                "message": f"⚠️ 止损信号: {symbol} 盈亏 {pnl_pct}% 触及 {-stop_loss_pct}% 止损线",
                "current_price": current_price,
                "entry_price": entry_price,
                "pnl_pct": pnl_pct,
                "threshold": -stop_loss_pct
            }

        return alert

    def save_notification(self, alert: Dict[str, Any]) -> bool:
        """保存通知到数据库"""
        try:
            db = get_database()
            db.execute_insert(
                """
                INSERT INTO notifications (type, symbol, message, payload, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    alert.get("type", "alert"),
                    alert.get("symbol", ""),
                    alert.get("message", ""),
                    str(alert),
                    datetime.utcnow().isoformat() + "Z"  # UTC 时间
                )
            )
            return True
        except Exception as e:
            print(f"保存通知失败: {e}")
            return False

    def start(self):
        """启动监控线程"""
        if self._is_running:
            return

        self._stop_event.clear()
        self._is_running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print(f"PortfolioMonitor started, monitoring {len(self._monitors)} positions")

    def stop(self):
        """停止监控线程"""
        if not self._is_running:
            return

        self._stop_event.set()
        self._is_running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("PortfolioMonitor stopped")

    def _run(self):
        """监控主循环"""
        while not self._stop_event.is_set():
            try:
                self._check_all()
            except Exception as e:
                print(f"监控检查失败: {e}")
                traceback.print_exc()

            # 等待下次检查
            self._stop_event.wait(self.check_interval)

    def _check_all(self):
        """检查所有持仓"""
        from quant_core import QuantEngine

        if not self._monitors:
            return

        engine = QuantEngine(testnet=True)

        for symbol in list(self._monitors.keys()):
            try:
                ticker = engine.data_source.fetch_ticker(symbol)
                current_price = ticker.get("last") if isinstance(ticker, dict) else None

                if current_price and current_price > 0:
                    alert = self.check_position(symbol, current_price)
                    if alert:
                        # 保存通知
                        self.save_notification(alert)
                        print(f"警报: {alert['message']}")
            except Exception as e:
                print(f"检查 {symbol} 失败: {e}")


# 全局实例
_portfolio_monitor: Optional[PortfolioMonitor] = None


def get_portfolio_monitor() -> PortfolioMonitor:
    """获取全局监控实例"""
    global _portfolio_monitor
    if _portfolio_monitor is None:
        _portfolio_monitor = PortfolioMonitor(check_interval=60)
    return _portfolio_monitor


def start_monitor():
    """启动监控服务"""
    get_portfolio_monitor().start()


def stop_monitor():
    """停止监控服务"""
    global _portfolio_monitor
    if _portfolio_monitor:
        _portfolio_monitor.stop()
