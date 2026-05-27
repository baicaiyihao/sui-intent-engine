"""
Simulated Trading Executor - 模拟交易执行器
支持自动获取K线数据、AI信号生成、自动交易执行
"""

import time
import threading
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
import asyncio


@dataclass
class Order:
    """订单"""
    id: str
    symbol: str
    side: str  # "buy" or "sell"
    order_type: str  # "market" or "limit"
    price: float
    amount: float
    filled_price: Optional[float] = None
    status: str = "pending"  # pending, filled, cancelled, rejected
    filled_at: Optional[str] = None
    commission: float = 0.0
    slippage: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class Position:
    """持仓"""
    symbol: str
    side: str  # "long" or "short"
    amount: float
    entry_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    entry_time: Optional[str] = None


@dataclass
class TradingSignal:
    """交易信号"""
    symbol: str
    action: str  # "BUY", "SELL", "HOLD"
    confidence: float = 0.0
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    reason: str = ""
    timeframe: str = "1H"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class SimulatedExecutor:
    """
    模拟交易执行器
    支持：
    - 市价单/限价单
    - 自动获取K线数据
    - AI信号自动交易
    - 持仓监控和通知
    """

    def __init__(
        self,
        initial_balance: float = 10000.0,
        commission_rate: float = 0.001,
        slippage_rate: float = 0.0005,
    ):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate

        self.orders: List[Order] = []
        self.positions: Dict[str, Position] = {}  # symbol -> Position
        self.trades: List[Dict[str, Any]] = []
        self.order_id_counter = 0

        # K线数据缓存
        self._kline_cache: Dict[str, Dict[str, Any]] = {}
        self._kline_cache_lock = threading.Lock()

        # 自动交易相关
        self._auto_trading_enabled = False
        self._auto_trading_thread: Optional[threading.Thread] = None
        self._stop_auto_trading = threading.Event()

        # 策略配置
        self._strategy_configs: Dict[str, Dict[str, Any]] = {}

        # 回调函数
        self._on_signal_callback: Optional[Callable] = None
        self._on_trade_callback: Optional[Callable] = None
        self._on_notification_callback: Optional[Callable] = None

    def set_signal_callback(self, callback: Callable):
        """设置信号回调"""
        self._on_signal_callback = callback

    def set_trade_callback(self, callback: Callable):
        """设置交易回调"""
        self._on_trade_callback = callback

    def set_notification_callback(self, callback: Callable):
        """设置通知回调"""
        self._on_notification_callback = callback

    def fetch_latest_price(self, symbol: str) -> Optional[float]:
        """获取最新价格"""
        try:
            from quant_core import QuantEngine
            engine = QuantEngine(testnet=True)
            ticker = engine.data_source.fetch_ticker(symbol)
            if isinstance(ticker, dict):
                return ticker.get("last")
            return None
        except Exception as e:
            print(f"获取价格失败 {symbol}: {e}")
            return None

    def fetch_klines(self, symbol: str, timeframe: str = "1H", days: int = 7) -> Optional[Dict]:
        """获取K线数据"""
        cache_key = f"{symbol}_{timeframe}"
        try:
            from quant_core import QuantEngine
            engine = QuantEngine(testnet=True)
            df = engine.market_collector.collect(symbol, timeframe, days=days)

            if df is None or df.empty:
                return None

            # 缓存最新数据
            last_row = df.iloc[-1]
            data = {
                "symbol": symbol,
                "timeframe": timeframe,
                "open": float(df["open"].iloc[-1]),
                "high": float(df["high"].iloc[-1]),
                "low": float(df["low"].iloc[-1]),
                "close": float(df["close"].iloc[-1]),
                "volume": float(df["volume"].iloc[-1]) if "volume" in df.columns else 0,
                "timestamp": df.index[-1] if hasattr(df.index[-1], 'isoformat') else str(df.index[-1]),
            }

            with self._kline_cache_lock:
                self._kline_cache[cache_key] = data

            return data
        except Exception as e:
            print(f"获取K线失败 {symbol} {timeframe}: {e}")
            return None

    def get_cached_kline(self, symbol: str, timeframe: str = "1H") -> Optional[Dict]:
        """获取缓存的K线数据"""
        cache_key = f"{symbol}_{timeframe}"
        with self._kline_cache_lock:
            return self._kline_cache.get(cache_key)

    def generate_ai_signal(self, symbol: str, timeframe: str = "1H", strategy_config: Dict[str, Any] = None) -> Optional[TradingSignal]:
        """生成AI交易信号（支持策略配置）"""
        try:
            from quant_core import QuantEngine
            from quant_core.ai.trading_signal import get_ai_signal_service

            engine = QuantEngine(testnet=True)

            # 获取K线数据
            days = 30 if timeframe in ["1D", "4H"] else 7
            df = engine.market_collector.collect(symbol, timeframe, days=days)
            if df.empty:
                return None

            # 获取实时价格
            ticker = engine.data_source.fetch_ticker(symbol)
            current_price = ticker.get("last") if isinstance(ticker, dict) else df["close"].iloc[-1]

            # AI生成信号（带策略配置）
            ai_service = get_ai_signal_service()
            signal_data = ai_service.generate_signal(df, symbol, current_price, timeframe, "zh-CN", strategy_config)

            if not signal_data:
                return None

            signal = TradingSignal(
                symbol=symbol,
                action=signal_data.get("decision", "HOLD"),
                confidence=signal_data.get("confidence", 0),
                entry_price=signal_data.get("entry_price", current_price),
                stop_loss=signal_data.get("stop_loss", 0),
                take_profit=signal_data.get("take_profit", 0),
                reason=signal_data.get("reason", ""),
                timeframe=timeframe,
            )

            return signal

        except Exception as e:
            print(f"生成AI信号失败 {symbol}: {e}")
            return None

    def start_auto_trading(
        self,
        symbol: str,
        timeframe: str = "1H",
        confidence_threshold: float = 70.0,
        position_size_pct: float = 10.0,
        stop_loss_pct: float = 2.0,
        take_profit_pct: float = 6.0,
        strategy_config: Dict[str, Any] = None,
        use_atr_stop: bool = False,
        atr_multiplier: float = 2.0,
        trailing_stop_pct: float = 0.0,
        max_drawdown_pct: float = 10.0,
        max_daily_loss_pct: float = 5.0
    ):
        """启动自动交易

        Args:
            symbol: 交易对
            timeframe: 周期
            confidence_threshold: 置信度阈值 (50-95)
            position_size_pct: 仓位比例 (1-100%)
            stop_loss_pct: 止损比例 (%)
            take_profit_pct: 止盈比例 (%)
            strategy_config: 策略配置，包含指标和阈值
            use_atr_stop: 是否使用ATR动态止损
            atr_multiplier: ATR倍数
            trailing_stop_pct: 追踪止盈比例 (0=不启用)
            max_drawdown_pct: 最大回撤暂停交易比例
            max_daily_loss_pct: 单日最大亏损比例
        """
        if self._auto_trading_enabled:
            return

        self._auto_trading_enabled = True
        self._stop_auto_trading.clear()

        # 默认策略配置
        if strategy_config is None:
            strategy_config = {
                "indicators": ["rsi", "macd", "boll"],
                "rsi_oversold": 30,
                "rsi_overbought": 70,
                "boll_position_low": 0.2,
                "boll_position_high": 0.8,
                "macd_confirm": True,
                "ma_confirmation": True,
            }

        config = {
            "symbol": symbol,
            "timeframe": timeframe,
            "confidence_threshold": confidence_threshold,
            "position_size_pct": position_size_pct,
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": take_profit_pct,
            "strategy_config": strategy_config,
            "use_atr_stop": use_atr_stop,
            "atr_multiplier": atr_multiplier,
            "trailing_stop_pct": trailing_stop_pct,
            "max_drawdown_pct": max_drawdown_pct,
            "max_daily_loss_pct": max_daily_loss_pct,
            "last_signal_time": 0,
            "position_opened": False,
            "entry_price": None,
            "highest_price_since_entry": None,
            "trailing_stop_triggered": False,
            "daily_loss_reset": datetime.now().strftime("%Y-%m-%d"),
            "daily_pnl": 0.0,
            "total_pnl": 0.0,
        }
        self._strategy_configs[symbol] = config

        # 初始化交易记录
        if not hasattr(self, '_trade_history'):
            self._trade_history = []

        self._auto_trading_thread = threading.Thread(
            target=self._auto_trading_loop,
            args=(symbol,),
            daemon=True
        )
        self._auto_trading_thread.start()
        print(f"自动交易已启动: {symbol} {timeframe} 仓位:{position_size_pct}% 止损:{stop_loss_pct}% ATR:{use_atr_stop} 追踪:{trailing_stop_pct}%")

    def stop_auto_trading(self, symbol: str = None):
        """停止自动交易"""
        if symbol:
            self._strategy_configs.pop(symbol, None)
            if not self._strategy_configs:
                self._auto_trading_enabled = False
                self._stop_auto_trading.set()
                if self._auto_trading_thread:
                    self._auto_trading_thread.join(timeout=5)
        else:
            self._auto_trading_enabled = False
            self._stop_auto_trading.set()
            self._strategy_configs.clear()
            if self._auto_trading_thread:
                self._auto_trading_thread.join(timeout=5)

    def _auto_trading_loop(self, symbol: str):
        """自动交易主循环"""
        while not self._stop_auto_trading.is_set():
            try:
                config = self._strategy_configs.get(symbol)
                if not config:
                    break

                # 检查日期是否变化，重置日亏损计数
                today = datetime.now().strftime("%Y-%m-%d")
                if config.get("daily_loss_reset") != today:
                    config["daily_pnl"] = 0.0
                    config["daily_loss_reset"] = today

                current_price = self.fetch_latest_price(symbol)
                if current_price and current_price > 0:
                    pos_pct = config.get("position_size_pct", 10)
                    sl_pct = config.get("stop_loss_pct", 2)
                    tp_pct = config.get("take_profit_pct", 6)
                    use_atr_stop = config.get("use_atr_stop", False)
                    atr_multiplier = config.get("atr_multiplier", 2.0)
                    trailing_pct = config.get("trailing_stop_pct", 0)
                    max_drawdown = config.get("max_drawdown_pct", 10)
                    max_daily_loss = config.get("max_daily_loss_pct", 5)

                    # 检查风控：日亏损/最大回撤
                    total_pnl = config.get("total_pnl", 0)
                    if total_pnl <= -max_drawdown:
                        self._send_notification(f"⚠️ 触发最大回撤保护 {max_drawdown}%，停止交易")
                        self.stop_auto_trading(symbol)
                        break

                    daily_pnl = config.get("daily_pnl", 0)
                    if daily_pnl <= -max_daily_loss:
                        self._send_notification(f"⚠️ 触发日亏损保护 {max_daily_loss}%，停止交易")
                        self.stop_auto_trading(symbol)
                        break

                    # 获取ATR用于动态止损
                    atr = None
                    if use_atr_stop:
                        indicators = self.get_indicators(symbol, config["timeframe"])
                        if indicators:
                            atr = indicators.get("atr")

                    # 检查持仓止损/止盈
                    if config.get("position_opened") and config.get("entry_price"):
                        entry_price = config["entry_price"]
                        pnl_pct = (current_price - entry_price) / entry_price * 100

                        # 计算止损价（固定或ATR动态）
                        if use_atr_stop and atr:
                            stop_price = entry_price * (1 - sl_pct / 100)  # 基础止损
                            atr_stop_price = entry_price - atr * atr_multiplier
                            dynamic_sl = max(stop_price, atr_stop_price)  # 取更保守的
                        else:
                            dynamic_sl = entry_price * (1 - sl_pct / 100)

                        # 计算止盈价
                        tp_price = entry_price * (1 + tp_pct / 100)

                        # 追踪止盈逻辑
                        highest_price = config.get("highest_price_since_entry", entry_price)
                        if current_price > highest_price:
                            highest_price = current_price
                            config["highest_price_since_entry"] = highest_price

                        # 止损检查
                        stop_triggered = current_price <= dynamic_sl
                        if stop_triggered:
                            trade = self.close_position(symbol, current_price, "stop_loss")
                            if trade:
                                self._add_trade_history(config, "止损", entry_price, current_price, pnl_pct)
                                config["position_opened"] = False
                                config["entry_price"] = None
                                config["highest_price_since_entry"] = None
                                config["trailing_stop_triggered"] = False
                                config["total_pnl"] = total_pnl + pnl_pct
                                config["daily_pnl"] = daily_pnl + pnl_pct
                                self._send_notification(f"触发止损 {symbol} @ {current_price}, 亏损 {pnl_pct:.2f}%")

                        # 追踪止盈检查
                        elif trailing_pct > 0:
                            # 追踪止盈：价格从最高点回落超过trailing_pct时触发
                            trail_trigger_price = highest_price * (1 - trailing_pct / 100)
                            if pnl_pct > tp_pct and current_price <= trail_trigger_price:
                                trade = self.close_position(symbol, current_price, "trailing_stop")
                                if trade:
                                    self._add_trade_history(config, "追踪止盈", entry_price, current_price, pnl_pct)
                                    config["position_opened"] = False
                                    config["entry_price"] = None
                                    config["highest_price_since_entry"] = None
                                    config["trailing_stop_triggered"] = False
                                    config["total_pnl"] = total_pnl + pnl_pct
                                    config["daily_pnl"] = daily_pnl + pnl_pct
                                    self._send_notification(f"触发追踪止盈 {symbol} @ {current_price}, 盈利 {pnl_pct:.2f}%")

                        # 普通止盈检查
                        elif pnl_pct >= tp_pct:
                            trade = self.close_position(symbol, current_price, "take_profit")
                            if trade:
                                self._add_trade_history(config, "止盈", entry_price, current_price, pnl_pct)
                                config["position_opened"] = False
                                config["entry_price"] = None
                                config["highest_price_since_entry"] = None
                                config["trailing_stop_triggered"] = False
                                config["total_pnl"] = total_pnl + pnl_pct
                                config["daily_pnl"] = daily_pnl + pnl_pct
                                self._send_notification(f"触发止盈 {symbol} @ {current_price}, 盈利 {pnl_pct:.2f}%")

                    # AI信号检查（使用策略配置）
                    signal = self.generate_ai_signal(symbol, config["timeframe"], config.get("strategy_config"))
                    if signal and signal.confidence >= config["confidence_threshold"]:
                        # 发送信号通知
                        if self._on_signal_callback:
                            self._on_signal_callback(signal)

                        # 执行交易
                        if signal.action == "BUY" and symbol not in self.positions and not config.get("position_opened"):
                            # 开多
                            amount = (self.balance * 0.95) / current_price * (pos_pct / 100)
                            if amount > 0:
                                order = self.create_market_order(symbol, "buy", amount, current_price)
                                if order.status == "filled":
                                    config["position_opened"] = True
                                    config["entry_price"] = current_price
                                    config["highest_price_since_entry"] = current_price
                                    self._add_trade_history(config, "买入", current_price, None, 0)
                                    self._send_notification(f"自动开多 {symbol} @ {current_price}, 置信度 {signal.confidence}%")

                        elif signal.action == "SELL" and symbol in self.positions:
                            # 平多
                            trade = self.close_position(symbol, current_price, "ai_signal")
                            if trade:
                                pnl_pct = trade.get("pnl_pct", 0)
                                self._add_trade_history(config, "卖出", current_price, current_price, pnl_pct)
                                config["position_opened"] = False
                                config["entry_price"] = None
                                self._send_notification(f"自动平多 {symbol} @ {current_price}, 盈亏 {pnl_pct:.2f}%")

                # 每分钟检查一次
                self._stop_auto_trading.wait(60)

            except Exception as e:
                print(f"自动交易异常 {symbol}: {e}")
                self._stop_auto_trading.wait(10)

    def _add_trade_history(self, config: dict, action: str, price: float, close_price: float, pnl_pct: float):
        """添加交易记录"""
        if not hasattr(self, '_trade_history'):
            self._trade_history = []
        self._trade_history.append({
            "time": datetime.now().isoformat(),
            "symbol": config["symbol"],
            "action": action,
            "entry_price": config.get("entry_price") or price,
            "exit_price": close_price,
            "pnl_pct": pnl_pct,
            "confidence": config.get("confidence_threshold", 0),
        })
        # 只保留最近100条记录
        if len(self._trade_history) > 100:
            self._trade_history = self._trade_history[-100:]

    def _send_notification(self, message: str):
        """发送通知"""
        if self._on_notification_callback:
            self._on_notification_callback(message)

    def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        current_price: float
    ) -> Order:
        """创建市价单"""
        self.order_id_counter += 1
        order_id = f"M{self.order_id_counter}_{int(time.time())}"

        # 计算滑点
        slippage = current_price * self.slippage_rate
        if side == "buy":
            filled_price = current_price * (1 + self.slippage_rate)
        else:
            filled_price = current_price * (1 - self.slippage_rate)

        commission = filled_price * amount * self.commission_rate

        order = Order(
            id=order_id,
            symbol=symbol,
            side=side,
            order_type="market",
            price=current_price,
            amount=amount,
            filled_price=filled_price,
            status="filled",
            filled_at=datetime.utcnow().isoformat(),
            commission=commission,
            slippage=slippage * amount,
        )

        self.orders.append(order)
        self._execute_order(order)

        # 触发交易回调
        if order.status == "filled" and self._on_trade_callback:
            self._on_trade_callback(order)

        return order

    def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        limit_price: float,
        current_price: float
    ) -> Order:
        """创建限价单"""
        self.order_id_counter += 1
        order_id = f"L{self.order_id_counter}_{int(time.time())}"

        # 限价单：如果当前价格触发了限价，则成交
        triggered = False
        if side == "buy" and current_price <= limit_price:
            triggered = True
        elif side == "sell" and current_price >= limit_price:
            triggered = True

        if triggered:
            slippage = limit_price * self.slippage_rate
            filled_price = limit_price * (1 + self.slippage_rate) if side == "buy" else limit_price * (1 - self.slippage_rate)
            commission = filled_price * amount * self.commission_rate

            order = Order(
                id=order_id,
                symbol=symbol,
                side=side,
                order_type="limit",
                price=limit_price,
                amount=amount,
                filled_price=filled_price,
                status="filled",
                filled_at=datetime.utcnow().isoformat(),
                commission=commission,
                slippage=slippage * amount,
            )
        else:
            order = Order(
                id=order_id,
                symbol=symbol,
                side=side,
                order_type="limit",
                price=limit_price,
                amount=amount,
                status="pending",
            )

        self.orders.append(order)
        if order.status == "filled":
            self._execute_order(order)
            if self._on_trade_callback:
                self._on_trade_callback(order)
        return order

    def cancel_order(self, order_id: str) -> bool:
        """取消订单"""
        for order in self.orders:
            if order.id == order_id and order.status == "pending":
                order.status = "cancelled"
                return True
        return False

    def update_prices(self, prices: Dict[str, float]):
        """更新持仓的当前价格"""
        for symbol, current_price in prices.items():
            if symbol in self.positions:
                pos = self.positions[symbol]
                pos.current_price = current_price
                if pos.side == "long":
                    pos.unrealized_pnl = (current_price - pos.entry_price) * pos.amount
                else:
                    pos.unrealized_pnl = (pos.entry_price - current_price) * pos.amount

    def update_position_from_latest(self, symbol: str) -> bool:
        """从最新价格更新持仓"""
        if symbol not in self.positions:
            return False

        price = self.fetch_latest_price(symbol)
        if price and price > 0:
            self.update_prices({symbol: price})
            return True
        return False

    def close_position(self, symbol: str, current_price: float, reason: str = "") -> Optional[Dict]:
        """平仓"""
        if symbol not in self.positions:
            return None

        pos = self.positions[symbol]
        side = "sell" if pos.side == "long" else "buy"

        slippage = current_price * self.slippage_rate
        if side == "sell":
            filled_price = current_price * (1 - self.slippage_rate)
        else:
            filled_price = current_price * (1 + self.slippage_rate)

        commission = filled_price * pos.amount * self.commission_rate

        trade = {
            "symbol": symbol,
            "side": pos.side,
            "entry_price": pos.entry_price,
            "exit_price": filled_price,
            "amount": pos.amount,
            "pnl": pos.unrealized_pnl - commission,
            "pnl_pct": pos.unrealized_pnl / (pos.entry_price * pos.amount) * 100 if pos.entry_price * pos.amount > 0 else 0,
            "commission": commission,
            "reason": reason,
            "closed_at": datetime.utcnow().isoformat(),
        }

        self.trades.append(trade)

        # 更新余额
        if pos.side == "long":
            self.balance += pos.amount * filled_price - commission
        else:
            self.balance += pos.entry_price * pos.amount - pos.amount * filled_price - commission

        del self.positions[symbol]
        return trade

    def get_equity(self, current_prices: Dict[str, float] = None) -> float:
        """计算当前权益"""
        if current_prices:
            self.update_prices(current_prices)
        position_value = sum(
            pos.amount * pos.current_price if pos.side == "long"
            else pos.amount * (2 * pos.entry_price - pos.current_price)
            for pos in self.positions.values()
        )
        return self.balance + position_value

    def get_equity_from_latest(self) -> float:
        """从最新价格计算当前权益"""
        prices = {}
        for symbol in self.positions:
            price = self.fetch_latest_price(symbol)
            if price:
                prices[symbol] = price
        return self.get_equity(prices)

    def _execute_order(self, order: Order):
        """执行订单"""
        if order.status != "filled" or order.filled_price is None:
            return

        symbol = order.symbol

        if order.side == "buy":
            cost = order.filled_price * order.amount + order.commission
            if symbol in self.positions:
                pos = self.positions[symbol]
                if pos.side == "long":
                    total_amount = pos.amount + order.amount
                    pos.entry_price = (pos.entry_price * pos.amount + order.filled_price * order.amount) / total_amount
                    pos.amount = total_amount
                else:
                    self.balance += pos.entry_price * pos.amount - order.filled_price * order.amount - order.commission
                    pos.side = "long"
                    pos.amount = order.amount
                    pos.entry_price = order.filled_price
                    pos.current_price = order.filled_price
                    pos.entry_time = datetime.utcnow().isoformat()
            else:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    side="long",
                    amount=order.amount,
                    entry_price=order.filled_price,
                    current_price=order.filled_price,
                    entry_time=datetime.utcnow().isoformat(),
                )
            self.balance -= cost

        elif order.side == "sell":
            if symbol in self.positions:
                pos = self.positions[symbol]
                if pos.side == "long":
                    pnl = (order.filled_price - pos.entry_price) * order.amount - order.commission
                    self.balance += order.amount * order.filled_price - order.commission
                    pos.amount -= order.amount
                    if pos.amount <= 0:
                        del self.positions[symbol]
                    else:
                        pos.entry_price = order.filled_price
                else:
                    pos.amount += order.amount
                    pos.entry_price = (pos.entry_price * (pos.amount - order.amount) + order.filled_price * order.amount) / pos.amount
            else:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    side="short",
                    amount=order.amount,
                    entry_price=order.filled_price,
                    current_price=order.filled_price,
                    entry_time=datetime.utcnow().isoformat(),
                )
            self.balance += order.amount * order.filled_price - order.commission

    def get_status(self) -> Dict[str, Any]:
        """获取执行器状态"""
        # 更新持仓价格
        for symbol in list(self.positions.keys()):
            self.update_position_from_latest(symbol)

        return {
            "balance": round(self.balance, 2),
            "initial_balance": self.initial_balance,
            "equity": round(self.get_equity(), 2),
            "open_positions": len(self.positions),
            "total_orders": len(self.orders),
            "filled_orders": len([o for o in self.orders if o.status == "filled"]),
            "pending_orders": len([o for o in self.orders if o.status == "pending"]),
            "total_trades": len(self.trades),
            "total_commission": round(sum(o.commission for o in self.orders if o.status == "filled"), 4),
            "total_pnl": round(sum(t.get("pnl", 0) for t in self.trades), 2),
            "auto_trading_enabled": self._auto_trading_enabled,
            "positions": [
                {
                    "symbol": p.symbol,
                    "side": p.side,
                    "amount": round(p.amount, 6),
                    "entry_price": round(p.entry_price, 4),
                    "current_price": round(p.current_price, 4),
                    "unrealized_pnl": round(p.unrealized_pnl, 2),
                    "unrealized_pnl_pct": round((p.current_price - p.entry_price) / p.entry_price * 100, 2) if p.side == "long" else round((p.entry_price - p.current_price) / p.entry_price * 100, 2),
                    "entry_time": p.entry_time,
                }
                for p in self.positions.values()
            ],
            "recent_trades": [
                {
                    "symbol": t["symbol"],
                    "side": t["side"],
                    "pnl": round(t.get("pnl", 0), 2),
                    "pnl_pct": round(t.get("pnl_pct", 0), 2),
                    "closed_at": t.get("closed_at", ""),
                }
                for t in self.trades[-10:]
            ],
            "auto_trading_config": self._strategy_configs.get("BTC/USDT", {}) if self._auto_trading_enabled else None,
            "auto_trade_history": getattr(self, '_trade_history', [])[-20:],
        }

    def get_indicators(self, symbol: str, timeframe: str = "1H") -> Optional[Dict[str, Any]]:
        """获取指标数据"""
        try:
            from quant_core import QuantEngine

            engine = QuantEngine(testnet=True)
            days = 30 if timeframe in ["1D", "4H"] else 7
            df = engine.market_collector.collect(symbol, timeframe, days=days)

            if df is None or df.empty:
                return None

            # 计算常用指标
            close = df["close"]

            # RSI
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1] if not rsi.empty else None

            # MACD
            exp1 = close.ewm(span=12, adjust=False).mean()
            exp2 = close.ewm(span=26, adjust=False).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=9, adjust=False).mean()
            current_macd = macd.iloc[-1] if not macd.empty else None
            current_signal = signal.iloc[-1] if not signal.empty else None

            # MA
            ma5 = close.rolling(window=5).mean().iloc[-1] if len(close) >= 5 else None
            ma20 = close.rolling(window=20).mean().iloc[-1] if len(close) >= 20 else None
            ma60 = close.rolling(window=60).mean().iloc[-1] if len(close) >= 60 else None

            # 布林带
            sma20 = close.rolling(window=20).mean().iloc[-1] if len(close) >= 20 else None
            std20 = close.rolling(window=20).std().iloc[-1] if len(close) >= 20 else None
            upper_band = sma20 + 2 * std20 if sma20 and std20 else None
            lower_band = sma20 - 2 * std20 if sma20 and std20 else None

            current_price = close.iloc[-1]

            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "current_price": round(current_price, 4),
                "rsi": round(current_rsi, 2) if current_rsi else None,
                "macd": round(current_macd, 4) if current_macd else None,
                "macd_signal": round(current_signal, 4) if current_signal else None,
                "macd_histogram": round((current_macd - current_signal), 4) if current_macd and current_signal else None,
                "ma5": round(ma5, 4) if ma5 else None,
                "ma20": round(ma20, 4) if ma20 else None,
                "ma60": round(ma60, 4) if ma60 else None,
                "bollinger_upper": round(upper_band, 4) if upper_band else None,
                "bollinger_lower": round(lower_band, 4) if lower_band else None,
                "ma5_diff_pct": round((current_price - ma5) / ma5 * 100, 2) if ma5 else None,
                "ma20_diff_pct": round((current_price - ma20) / ma20 * 100, 2) if ma20 else None,
                "trend": "bullish" if ma5 > ma20 else "bearish" if ma5 < ma20 else "neutral",
            }

        except Exception as e:
            print(f"获取指标失败 {symbol}: {e}")
            return None

    def reset(self, initial_balance: float = None):
        """重置模拟交易"""
        if initial_balance:
            self.initial_balance = initial_balance
        self.balance = self.initial_balance
        self.orders.clear()
        self.positions.clear()
        self.trades.clear()
        self.order_id_counter = 0
        self.stop_auto_trading()
        print(f"模拟交易已重置，余额: {self.balance}")
