"""
订单执行器
"""
from typing import Dict, Any, Optional
from enum import Enum

from quant_core.data_source import get_data_source


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderExecutor:
    """订单执行器"""

    def __init__(self, exchange: str = None, testnet: bool = True):
        self.data_source = get_data_source(exchange=exchange, testnet=testnet)
        self.testnet = testnet

    def place_order(self, symbol: str, side: str, order_type: str,
                    amount: float, price: float = None, params: Dict = None) -> Dict[str, Any]:
        """
        下单

        Args:
            symbol: 交易对，如 "BTC/USDT"
            side: "buy" 或 "sell"
            order_type: "market", "limit", "stop_loss"
            amount: 数量
            price: 价格(市价单不需要)
            params: 额外参数

        Returns:
            订单信息
        """
        if self.testnet:
            return self._simulate_order(symbol, side, order_type, amount, price)

        try:
            if order_type == "market":
                order = self.data_source.create_order(symbol, "market", side, amount)
            elif order_type == "limit":
                order = self.data_source.create_order(symbol, "limit", side, amount, price=price)
            elif order_type == "stop_loss":
                stop_params = params or {}
                if price:
                    stop_params["stopPrice"] = price
                order = self.data_source.create_order(symbol, "stop", side, amount, price=price, params=stop_params)
            else:
                raise ValueError(f"Unknown order type: {order_type}")

            return {
                "success": True,
                "order_id": order.get("id"),
                "symbol": symbol,
                "side": side,
                "type": order_type,
                "amount": amount,
                "price": price or order.get("average", 0),
                "status": order.get("status"),
                "filled": order.get("filled", 0),
                "remaining": order.get("remaining", amount)
            }
        except Exception as e:
            return {
                "success": False,
                "symbol": symbol,
                "error": str(e)
            }

    def _simulate_order(self, symbol: str, side: str, order_type: str,
                        amount: float, price: float = None) -> Dict[str, Any]:
        """模拟订单(测试网)"""
        import time
        import random

        current_price = price or self.data_source.fetch_ticker(symbol).get("last", 0)
        if price is None and order_type == "market":
            slippage = random.uniform(0.001, 0.005)
            if side == "buy":
                current_price *= (1 + slippage)
            else:
                current_price *= (1 - slippage)

        return {
            "success": True,
            "order_id": f"TEST_{int(time.time())}_{random.randint(1000, 9999)}",
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "amount": amount,
            "price": current_price,
            "status": "filled",
            "filled": amount,
            "remaining": 0,
            "testnet": True
        }

    def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """取消订单"""
        if self.testnet:
            return {
                "success": True,
                "order_id": order_id,
                "status": "cancelled",
                "testnet": True
            }

        try:
            result = self.data_source.cancel_order(order_id, symbol)
            return {
                "success": True,
                "order_id": order_id,
                "result": result
            }
        except Exception as e:
            return {
                "success": False,
                "order_id": order_id,
                "error": str(e)
            }

    def get_order_status(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """查询订单状态"""
        if self.testnet:
            return {
                "order_id": order_id,
                "status": "filled",
                "testnet": True
            }

        try:
            orders = self.data_source.fetch_orders(symbol)
            for order in orders:
                if order.get("id") == order_id:
                    return {
                        "order_id": order_id,
                        "status": order.get("status"),
                        "filled": order.get("filled", 0),
                        "remaining": order.get("remaining", 0),
                        "price": order.get("price"),
                        "average": order.get("average")
                    }
            return {
                "order_id": order_id,
                "status": "not_found"
            }
        except Exception as e:
            return {
                "order_id": order_id,
                "error": str(e)
            }

    def get_balance(self) -> Dict[str, Any]:
        """获取账户余额"""
        return self.data_source.fetch_balance()
