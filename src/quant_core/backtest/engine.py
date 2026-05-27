"""
增强版回测引擎 - 支持权益曲线、多维度分析、可配置手续费/滑点
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
import json

from quant_core import config


@dataclass
class Trade:
    """交易记录"""
    entry_time: str
    exit_time: str
    side: str  # long, short
    entry_price: float
    exit_price: float
    amount: float
    commission: float
    slippage: float
    pnl: float
    pnl_pct: float
    reason: str
    stop_loss: float = 0
    take_profit: float = 0
    trailing_stop_price: float = 0


@dataclass
class EquityPoint:
    """权益曲线点"""
    time: str
    equity: float
    drawdown: float
    position_value: float = 0


@dataclass
class BacktestConfig:
    """回测配置"""
    initial_balance: float = 10000.0
    commission: float = 0.001  # 0.1% 默认
    slippage: float = 0.0005   # 0.05% 默认滑点
    leverage: float = 1.0
    stop_loss_pct: float = 2.0
    take_profit_pct: float = 6.0
    trailing_stop: bool = False
    trailing_pct: float = 1.5
    risk_free_rate: float = 0.02  # 年化无风险利率 (2%)


class BacktestEngine:
    """增强版回测引擎"""

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.reset()

    def reset(self):
        """重置状态"""
        self.balance = self.config.initial_balance
        self.initial_balance = self.config.initial_balance
        self.positions: List[Dict] = []
        self.trades: List[Trade] = []
        self.equity_curve: List[EquityPoint] = []
        self.position = None
        self.entry_price = 0
        self.stop_loss = 0
        self.take_profit = 0
        self.trailing_stop_price = 0
        self.win_count = 0
        self.loss_count = 0
        self.best_trade = 0
        self.worst_trade = 0
        self.total_commission = 0
        self.total_slippage = 0

    def run(self, df: pd.DataFrame, strategy: Dict[str, Any],
            indicators_df: pd.DataFrame = None, signal_func: Callable = None) -> Dict[str, Any]:
        """
        运行回测

        Args:
            df: K线数据
            strategy: 策略配置
            indicators_df: 指标数据
            signal_func: 自定义信号函数 (df, indicators_df, i) -> 'buy'|'sell'|None
        """
        self.reset()

        risk = strategy.get("risk_management", {})
        self.config.stop_loss_pct = risk.get("stop_loss_pct", self.config.stop_loss_pct) / 100
        self.config.take_profit_pct = risk.get("take_profit_pct", self.config.take_profit_pct) / 100
        self.config.trailing_stop = risk.get("trailing_stop", self.config.trailing_stop)
        self.config.trailing_pct = risk.get("trailing_pct", self.config.trailing_pct) / 100

        commission = self.config.commission
        slippage = self.config.slippage
        leverage = self.config.leverage

        use_indicators = indicators_df is not None and len(indicators_df) == len(df)

        # 获取手续费配置
        custom_commission = strategy.get("commission")
        custom_slippage = strategy.get("slippage")
        if custom_commission is not None:
            commission = custom_commission
        if custom_slippage is not None:
            slippage = custom_slippage

        position = None
        peak_equity = self.initial_balance

        for i in range(1, len(df)):
            current_price = df["close"].iloc[i]
            current_low = df["low"].iloc[i]
            current_high = df["high"].iloc[i]
            current_time = str(df.index[i])

            # 计算持仓价值
            position_value = 0
            if position:
                if position["side"] == "long":
                    position_value = position["amount"] * current_price
                else:  # short
                    position_value = position["amount"] * position["entry_price"] - position["amount"] * (position["entry_price"] - current_price)

            current_equity = self.balance + position_value

            # 更新峰值和回撤
            if current_equity > peak_equity:
                peak_equity = current_equity
            drawdown = (peak_equity - current_equity) / peak_equity * 100 if peak_equity > 0 else 0

            # 记录权益曲线
            self.equity_curve.append(EquityPoint(
                time=current_time,
                equity=current_equity,
                drawdown=drawdown,
                position_value=position_value
            ))

            if position is None:
                # 无持仓，检查买入/做空信号
                if signal_func:
                    signal = signal_func(df, indicators_df, i)
                else:
                    signal = self._check_entry(i, df, use_indicators, indicators_df)

                if signal in ("buy", "short"):
                    side = "long" if signal == "buy" else "short"
                    entry_price = current_price * (1 + slippage if side == "long" else -slippage)
                    stop_loss_price = entry_price * (1 - self.config.stop_loss_pct if side == "long" else 1 + self.config.stop_loss_pct)
                    take_profit_price = entry_price * (1 + self.config.take_profit_pct if side == "long" else 1 - self.config.take_profit_pct)
                    trailing_stop_price = entry_price

                    # 计算仓位大小
                    pos_size = self._calculate_position_size(strategy, entry_price)
                    amount = pos_size / entry_price * leverage

                    # 入场手续费
                    entry_commission = entry_price * amount * commission
                    self.total_commission += entry_commission

                    position = {
                        "side": side,
                        "entry_price": entry_price,
                        "entry_time": current_time,
                        "amount": amount,
                        "stop_loss": stop_loss_price,
                        "take_profit": take_profit_price,
                        "trailing_stop_price": trailing_stop_price
                    }

                    self.trades.append(Trade(
                        entry_time=current_time,
                        exit_time="",
                        side=side,
                        entry_price=entry_price,
                        exit_price=0,
                        amount=amount,
                        commission=entry_commission,
                        slippage=entry_price * amount * slippage,
                        pnl=0,
                        pnl_pct=0,
                        reason=f"entry_{signal}"
                    ))

            else:
                # 有持仓，检查止损/止盈/出场信号
                should_exit = False
                exit_reason = ""

                if position["side"] == "long":
                    # 更新追踪止损
                    if self.config.trailing_stop and current_high > position["trailing_stop_price"]:
                        position["trailing_stop_price"] = current_high * (1 - self.config.trailing_pct)

                    # 检查止损/止盈
                    if current_low <= position["stop_loss"]:
                        should_exit = True
                        exit_reason = "stop_loss"
                        exit_price = position["stop_loss"]
                    elif current_high >= position["take_profit"]:
                        should_exit = True
                        exit_reason = "take_profit"
                        exit_price = position["take_profit"]
                    elif self.config.trailing_stop and current_low <= position["trailing_stop_price"]:
                        should_exit = True
                        exit_reason = "trailing_stop"
                        exit_price = position["trailing_stop_price"]
                else:  # short
                    # 更新追踪止损
                    if self.config.trailing_stop and current_low < position["trailing_stop_price"]:
                        position["trailing_stop_price"] = current_low * (1 + self.config.trailing_pct)

                    # 检查止损/止盈
                    if current_high >= position["stop_loss"]:
                        should_exit = True
                        exit_reason = "stop_loss"
                        exit_price = position["stop_loss"]
                    elif current_low <= position["take_profit"]:
                        should_exit = True
                        exit_reason = "take_profit"
                        exit_price = position["take_profit"]
                    elif self.config.trailing_stop and current_high >= position["trailing_stop_price"]:
                        should_exit = True
                        exit_reason = "trailing_stop"
                        exit_price = position["trailing_stop_price"]

                # 检查信号出场
                if signal_func:
                    signal = signal_func(df, indicators_df, i)
                else:
                    signal = self._check_exit(i, df, use_indicators, indicators_df)

                if signal and signal in ("sell", "cover"):
                    if (position["side"] == "long" and signal == "sell") or \
                       (position["side"] == "short" and signal == "cover"):
                        should_exit = True
                        exit_reason = f"signal_{signal}"
                        exit_price = current_price

                if should_exit:
                    exit_price = exit_price * (1 - slippage if position["side"] == "long" else 1 + slippage)
                    exit_commission = exit_price * position["amount"] * commission
                    exit_slippage = exit_price * position["amount"] * slippage
                    self.total_commission += exit_commission
                    self.total_slippage += exit_slippage

                    if position["side"] == "long":
                        pnl = (exit_price - position["entry_price"]) * position["amount"]
                    else:
                        pnl = (position["entry_price"] - exit_price) * position["amount"]

                    pnl -= (exit_commission + exit_slippage)
                    pnl_pct = pnl / (position["entry_price"] * position["amount"]) * 100

                    self.balance += pnl

                    if pnl > 0:
                        self.win_count += 1
                    else:
                        self.loss_count += 1

                    self.best_trade = max(self.best_trade, pnl)
                    self.worst_trade = min(self.worst_trade, pnl)

                    # 更新最后一笔交易
                    if self.trades and self.trades[-1].exit_time == "":
                        self.trades[-1].exit_time = current_time
                        self.trades[-1].exit_price = exit_price
                        self.trades[-1].pnl = pnl
                        self.trades[-1].pnl_pct = pnl_pct
                        self.trades[-1].commission += exit_commission
                        self.trades[-1].slippage += exit_slippage
                        self.trades[-1].reason = exit_reason
                    else:
                        self.trades.append(Trade(
                            entry_time=position["entry_time"],
                            exit_time=current_time,
                            side=position["side"],
                            entry_price=position["entry_price"],
                            exit_price=exit_price,
                            amount=position["amount"],
                            commission=exit_commission,
                            slippage=exit_slippage,
                            pnl=pnl,
                            pnl_pct=pnl_pct,
                            reason=exit_reason
                        ))

                    position = None

        # 如果还有持仓，平仓
        if position is not None:
            exit_price = df["close"].iloc[-1]
            exit_price = exit_price * (1 - slippage if position["side"] == "long" else 1 + slippage)
            exit_commission = exit_price * position["amount"] * commission
            self.total_commission += exit_commission

            if position["side"] == "long":
                pnl = (exit_price - position["entry_price"]) * position["amount"]
            else:
                pnl = (position["entry_price"] - exit_price) * position["amount"]

            pnl -= exit_commission
            pnl_pct = pnl / (position["entry_price"] * position["amount"]) * 100

            self.balance += pnl

            if pnl > 0:
                self.win_count += 1
            else:
                self.loss_count += 1

            self.best_trade = max(self.best_trade, pnl)
            self.worst_trade = min(self.worst_trade, pnl)

            if self.trades and self.trades[-1].exit_time == "":
                self.trades[-1].exit_time = str(df.index[-1])
                self.trades[-1].exit_price = exit_price
                self.trades[-1].pnl = pnl
                self.trades[-1].pnl_pct = pnl_pct
                self.trades[-1].commission += exit_commission
                self.trades[-1].reason = "end_of_data"
            else:
                self.trades.append(Trade(
                    entry_time=position["entry_time"],
                    exit_time=str(df.index[-1]),
                    side=position["side"],
                    entry_price=position["entry_price"],
                    exit_price=exit_price,
                    amount=position["amount"],
                    commission=exit_commission,
                    slippage=0,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    reason="end_of_data"
                ))

        return self._generate_report()

    def _check_entry(self, i: int, df: pd.DataFrame, use_indicators: bool, indicators_df: pd.DataFrame) -> Optional[str]:
        """检查入场信号"""
        if use_indicators:
            if "rsi" in indicators_df.columns:
                rsi = indicators_df["rsi"].iloc[i]
                if rsi and rsi < 30:
                    return "buy"
            if "macd" in indicators_df.columns and "macd_signal" in indicators_df.columns:
                if indicators_df["macd"].iloc[i] > indicators_df["macd_signal"].iloc[i]:
                    if indicators_df["macd"].iloc[i-1] <= indicators_df["macd_signal"].iloc[i-1]:
                        return "buy"
        else:
            if df["close"].iloc[i] > df["open"].iloc[i]:
                return "buy"
        return None

    def _check_exit(self, i: int, df: pd.DataFrame, use_indicators: bool, indicators_df: pd.DataFrame) -> Optional[str]:
        """检查出场信号"""
        if use_indicators:
            if "rsi" in indicators_df.columns:
                rsi = indicators_df["rsi"].iloc[i]
                if rsi and rsi > 70:
                    return "sell"
        return None

    def _calculate_position_size(self, strategy: Dict[str, Any], price: float) -> float:
        """计算仓位大小"""
        pos = strategy.get("position_size", {})
        method = pos.get("method", "fixed")

        if method == "fixed":
            return pos.get("value", 100)
        elif method == "percent":
            return self.balance * (pos.get("value", 10) / 100)
        elif method == "kelly":
            # Kelly Criterion简化版
            win_rate = self.win_count / (self.win_count + self.loss_count) if (self.win_count + self.loss_count) > 0 else 0.5
            avg_win = self.best_trade if self.win_count > 0 else 0
            avg_loss = abs(self.worst_trade) if self.loss_count > 0 else 1
            if avg_loss > 0:
                kelly = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
                kelly = max(0.1, min(kelly, 1.0))  # 限制在10%-100%
                return self.balance * kelly * 0.1  # 用10%的Kelly
            return self.balance * 0.1
        else:
            return 100

    def _generate_report(self) -> Dict[str, Any]:
        """生成回测报告"""
        if not self.equity_curve:
            return self._empty_report()

        sells = [t for t in self.trades if t.exit_time]
        total_trades = len(sells)
        win_rate = self.win_count / total_trades * 100 if total_trades > 0 else 0

        total_pnl = self.balance - self.initial_balance
        total_pnl_pct = (self.balance - self.initial_balance) / self.initial_balance * 100

        # 计算各种指标
        equity_values = [e.equity for e in self.equity_curve]
        max_dd, max_dd_pct = self._calculate_max_drawdown(equity_values)
        sharpe = self._calculate_sharpe_ratio(equity_values)
        sortino = self._calculate_sortino_ratio(equity_values)

        # 盈亏比
        avg_win = 0
        avg_loss = 0
        if self.win_count > 0:
            winning_trades = [t.pnl for t in sells if t.pnl > 0]
            avg_win = sum(winning_trades) / len(winning_trades) if winning_trades else 0
        if self.loss_count > 0:
            losing_trades = [abs(t.pnl) for t in sells if t.pnl < 0]
            avg_loss = sum(losing_trades) / len(losing_trades) if losing_trades else 0

        profit_factor = avg_win / avg_loss if avg_loss > 0 else 0

        # 连续盈利/亏损
        consecutive_wins = 0
        consecutive_losses = 0
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        for t in sells:
            if t.pnl > 0:
                consecutive_wins += 1
                consecutive_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, consecutive_wins)
            else:
                consecutive_losses += 1
                consecutive_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)

        return {
            # 基本信息
            "total_trades": total_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl_pct,
            "final_balance": self.balance,
            "initial_balance": self.initial_balance,

            # 盈亏统计
            "profit_factor": profit_factor,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "best_trade": self.best_trade,
            "worst_trade": self.worst_trade,
            "win_count": self.win_count,
            "loss_count": self.loss_count,

            # 风险指标
            "max_drawdown": max_dd,
            "max_drawdown_pct": max_dd_pct,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,

            # 连续性
            "max_consecutive_wins": max_consecutive_wins,
            "max_consecutive_losses": max_consecutive_losses,

            # 成本
            "total_commission": self.total_commission,
            "total_slippage": self.total_slippage,

            # 权益曲线
            "equity_curve": [
                {"time": e.time, "equity": e.equity, "drawdown": e.drawdown}
                for e in self.equity_curve
            ],

            # 交易明细
            "trades": [
                {
                    "entry_time": t.entry_time,
                    "exit_time": t.exit_time,
                    "side": t.side,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "amount": t.amount,
                    "pnl": t.pnl,
                    "pnl_pct": t.pnl_pct,
                    "commission": t.commission,
                    "reason": t.reason
                }
                for t in sells
            ]
        }

    def _empty_report(self) -> Dict[str, Any]:
        return {
            "total_trades": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "total_pnl_pct": 0,
            "final_balance": self.initial_balance,
            "initial_balance": self.initial_balance,
            "profit_factor": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "best_trade": 0,
            "worst_trade": 0,
            "win_count": 0,
            "loss_count": 0,
            "max_drawdown": 0,
            "max_drawdown_pct": 0,
            "sharpe_ratio": 0,
            "sortino_ratio": 0,
            "max_consecutive_wins": 0,
            "max_consecutive_losses": 0,
            "total_commission": 0,
            "total_slippage": 0,
            "equity_curve": [],
            "trades": []
        }

    def _calculate_max_drawdown(self, equity: List[float]) -> tuple:
        """计算最大回撤"""
        peak = equity[0]
        max_dd = 0
        max_dd_pct = 0
        for e in equity:
            if e > peak:
                peak = e
            dd = peak - e
            dd_pct = dd / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct
        return max_dd, max_dd_pct

    def _calculate_sharpe_ratio(self, equity: List[float], periods_per_year: int = 365) -> float:
        """计算夏普比率"""
        if len(equity) < 2:
            return 0

        returns = pd.Series(equity).pct_change().dropna()
        if len(returns) == 0 or returns.std() == 0:
            return 0

        excess_returns = returns - (self.config.risk_free_rate / periods_per_year)
        sharpe = excess_returns.mean() / returns.std() * np.sqrt(periods_per_year)
        return sharpe if not np.isnan(sharpe) else 0

    def _calculate_sortino_ratio(self, equity: List[float], periods_per_year: int = 365) -> float:
        """计算索提诺比率"""
        if len(equity) < 2:
            return 0

        returns = pd.Series(equity).pct_change().dropna()
        if len(returns) == 0 or returns.std() == 0:
            return 0

        excess_returns = returns - (self.config.risk_free_rate / periods_per_year)
        downside_returns = returns[returns < 0]
        if len(downside_returns) == 0:
            return float('inf') if excess_returns.mean() > 0 else 0

        downside_std = downside_returns.std()
        if downside_std == 0:
            return 0

        sortino = excess_returns.mean() / downside_std * np.sqrt(periods_per_year)
        return sortino if not np.isnan(sortino) else 0


def run_backtest(df: pd.DataFrame, strategy: Dict[str, Any],
                 initial_balance: float = 10000,
                 commission: float = 0.001,
                 slippage: float = 0.0005) -> Dict[str, Any]:
    """
    快速回测函数

    Args:
        df: K线数据
        strategy: 策略配置
        initial_balance: 初始资金
        commission: 手续费率
        slippage: 滑点率

    Returns:
        回测结果
    """
    cfg = BacktestConfig(
        initial_balance=initial_balance,
        commission=commission,
        slippage=slippage
    )
    engine = BacktestEngine(config=cfg)
    return engine.run(df, strategy)
