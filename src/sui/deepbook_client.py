"""
DeepBook Client - SUI 原生订单簿交互 (Mock版本)
用于演示和测试，实际部署时需要接入真实 SDK
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from enum import Enum
import random
import time
import uuid


class OrderSide(Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"
    LIMIT = "limit"
    IOC = "ioc"
    FOK = "fok"


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL_FILLED = "partial_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class MarketData:
    """市场数据"""
    symbol: str
    bid_price: float
    ask_price: float
    last_price: float
    volume_24h: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class OrderResult:
    """订单执行结果"""
    success: bool
    order_id: str
    executed_price: float
    executed_amount: float
    slippage: float
    fees: float
    message: str
    tx_hash: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "order_id": self.order_id,
            "executed_price": self.executed_price,
            "executed_amount": self.executed_amount,
            "slippage": self.slippage,
            "fees": self.fees,
            "message": self.message,
            "tx_hash": self.tx_hash,
            "timestamp": self.timestamp,
        }


@dataclass
class PTBCommand:
    """PTB 命令"""
    index: int
    command: str
    description: str
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "command": self.command,
            "description": self.description,
            "details": self.details,
        }


@dataclass
class PTBPreview:
    """PTB 预览"""
    type: str = "PTB Preview"
    side: str = ""
    asset: str = ""
    amount_usd: float = 0.0
    estimated_amount: float = 0.0
    estimated_price: float = 0.0
    estimated_slippage: str = ""
    estimated_fees: str = ""
    warnings: List[str] = field(default_factory=list)
    ptb_commands: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "side": self.side,
            "asset": self.asset,
            "amount_usd": self.amount_usd,
            "estimated_amount": self.estimated_amount,
            "estimated_price": self.estimated_price,
            "estimated_slippage": self.estimated_slippage,
            "estimated_fees": self.estimated_fees,
            "warnings": self.warnings,
            "ptb_commands": self.ptb_commands,
        }


@dataclass
class OrderStatusResult:
    """订单状态查询结果"""
    order_id: str
    status: str
    filled_amount: float
    remaining_amount: float
    avg_fill_price: float
    fees: float
    tx_hash: Optional[str] = None
    updated_at: float = field(default_factory=time.time)


class DeepBookClient:
    """
    DeepBook Mock 客户端
    模拟市价单执行，用于 MVP 演示
    """

    # DeepBook 合约地址 (testnet mock)
    DEEPBOOK_PACKAGE_ID = "0xDEPRECATED000000000000000000000000000000000000000000"
    SUI_COIN_TYPE = "0x2::sui::SUI"

    # 手续费率 (basis points)
    FEE_RATE_BP = 30  # 0.3%

    def __init__(self, network: str = "testnet"):
        self.network = network
        self.order_count = 0
        self.orders: Dict[str, Dict] = {}  # Mock order storage

    async def place_market_order(
        self,
        side: OrderSide,
        asset: str,
        amount_usd: float,
        current_price: float
    ) -> OrderResult:
        """
        模拟市价单执行

        Args:
            side: 买卖方向
            asset: 资产符号 (e.g., "SUI")
            amount_usd: USD 金额
            current_price: 当前价格

        Returns:
            OrderResult: 订单结果
        """
        # 模拟滑点 (0.1% - 0.5%)
        slippage_pct = random.uniform(0.001, 0.005)
        if side == OrderSide.BUY:
            executed_price = current_price * (1 + slippage_pct)
        else:
            executed_price = current_price * (1 - slippage_pct)

        amount = amount_usd / executed_price
        fees = amount_usd * (self.FEE_RATE_BP / 10000)

        self.order_count += 1
        order_id = f"MOCK_{int(time.time())}_{self.order_count}"

        # Mock order record
        self.orders[order_id] = {
            "side": side.value,
            "asset": asset,
            "amount": amount,
            "price": executed_price,
            "status": "filled",
            "tx_hash": f"0x{''.join(random.choices('0123456789abcdef', k=64))}",
        }

        return OrderResult(
            success=True,
            order_id=order_id,
            executed_price=executed_price,
            executed_amount=amount,
            slippage=slippage_pct * 100,  # as percentage
            fees=fees,
            message=f"Mock {side.value.upper()} order executed successfully",
            tx_hash=f"0x{''.join(random.choices('0123456789abcdef', k=64))}"
        )

    def build_ptb_preview(
        self,
        side: OrderSide,
        asset: str,
        amount_usd: float,
        current_price: float
    ) -> PTBPreview:
        """
        构建 PTB 预览 (不执行交易)

        Args:
            side: 买卖方向
            asset: 资产符号
            amount_usd: USD 金额
            current_price: 当前价格

        Returns:
            PTBPreview: PTB 结构预览
        """
        amount = amount_usd / current_price

        # 预估滑点
        slippage_estimate = amount_usd * 0.003
        slippage_str = f"~${slippage_estimate:.2f} (~0.3%)"

        # 预估手续费
        fees_estimate = amount_usd * (self.FEE_RATE_BP / 10000)
        fees_str = f"~${fees_estimate:.4f} ({self.FEE_RATE_BP}bp)"

        # 警告
        warnings = []
        if amount_usd > 5000:
            warnings.append("大额订单，可能有较大滑点")
        if amount > 10000:
            warnings.append("订单量较大，请确认钱包余额")

        # PTB 命令列表
        ptb_commands = self._build_ptb_commands(side, asset, amount, current_price)

        return PTBPreview(
            type="PTB Preview",
            side=side.value,
            asset=asset,
            amount_usd=amount_usd,
            estimated_amount=amount,
            estimated_price=current_price,
            estimated_slippage=slippage_str,
            estimated_fees=fees_str,
            warnings=warnings,
            ptb_commands=[c.to_dict() for c in ptb_commands]
        )

    def _build_ptb_commands(
        self,
        side: OrderSide,
        asset: str,
        amount: float,
        current_price: float
    ) -> List[PTBCommand]:
        """构建 PTB 命令列表"""
        commands = []
        gas_budget = 0.002  # SUI for gas

        # 1. SplitCoins - 分割 SUI coin 用于交易和 gas
        commands.append(PTBCommand(
            index=1,
            command="SplitCoins",
            description="分割 SUI coin 获取交易金额和 gas",
            details={
                "source": "user_sui_coins",
                "outputs": [
                    {"name": "trade_amount", "amount": f"{amount:.6f} SUI"},
                    {"name": "gas_budget", "amount": f"{gas_budget} SUI"}
                ]
            }
        ))

        # 2. MakeMoveVec - 创建交易对向量
        commands.append(PTBCommand(
            index=2,
            command="MakeMoveVec",
            description="创建交易对向量 [base, quote]",
            details={
                "type": f"{self.SUI_COIN_TYPE}, {self._get_coin_type(asset)}",
                "elements": [
                    f"{amount:.6f} SUI",  # base
                    f"${amount * current_price:.2f} USDC"  # quote (estimated)
                ]
            }
        ))

        # 3. DeepBook.PlaceMarketOrder - 下市价单
        commands.append(PTBCommand(
            index=3,
            command="DeepBook.PlaceMarketOrder",
            description="在 DeepBook 放置市价单",
            details={
                "package": self.DEEPBOOK_PACKAGE_ID,
                "module": "deepbook",
                "function": "place_market_order",
                "side": side.value.upper(),
                "quantity": f"{amount:.6f} {asset}",
                "self_beneficiary": "user_wallet"
            }
        ))

        # 4. TransferObjects - 转账 (如果需要)
        if side == OrderSide.BUY:
            commands.append(PTBCommand(
                index=4,
                command="TransferObjects",
                description="接收买入的资产",
                details={
                    "objects": [f"{amount:.6f} {asset}"],
                    "recipient": "user_wallet"
                }
            ))

        return commands

    def _get_coin_type(self, asset: str) -> str:
        """获取资产 coin type"""
        coin_types = {
            "SUI": "0x2::sui::SUI",
            "USDC": "0x5d4b302506645c37ff133b98c4ee50a0000000000000000000000000000000000::usdc::USDC",
            "BTC": "0x0000000000000000000000000000000000000000000000000000000000000000::btc::BTC",
            "ETH": "0x0000000000000000000000000000000000000000000000000000000000000000::eth::ETH",
        }
        return coin_types.get(asset, f"0xunknown::{asset.lower()}::{asset}")

    async def get_order_status(self, order_id: str) -> OrderStatusResult:
        """
        查询订单状态

        Args:
            order_id: 订单 ID

        Returns:
            OrderStatusResult: 订单状态
        """
        if order_id in self.orders:
            order = self.orders[order_id]
            return OrderStatusResult(
                order_id=order_id,
                status="filled",
                filled_amount=order["amount"],
                remaining_amount=0,
                avg_fill_price=order["price"],
                fees=order["amount"] * order["price"] * (self.FEE_RATE_BP / 10000),
                tx_hash=order.get("tx_hash")
            )

        return OrderStatusResult(
            order_id=order_id,
            status="not_found",
            filled_amount=0,
            remaining_amount=0,
            avg_fill_price=0,
            fees=0
        )

    def to_human_readable(self, preview: PTBPreview) -> str:
        """生成人类可读的 PTB 预览"""
        lines = [
            "=" * 50,
            f"Transaction Preview ({preview.type})",
            "=" * 50,
            f"Action: {preview.side.upper()} {preview.asset}",
            f"Amount: ${preview.amount_usd:.2f} ({preview.estimated_amount:.6f} {preview.asset})",
            f"Est. Price: ${preview.estimated_price:.4f}",
            "",
            "-- PTB Commands --",
        ]

        for cmd in preview.ptb_commands:
            lines.append(f"  {cmd['index']}. {cmd['command']}")
            lines.append(f"     {cmd['description']}")

        lines.append("")
        lines.append(f"Est. Slippage: {preview.estimated_slippage}")
        lines.append(f"Est. Fees: {preview.estimated_fees}")

        if preview.warnings:
            lines.append("")
            lines.append("Warnings:")
            for w in preview.warnings:
                lines.append(f"  ! {w}")

        lines.append("=" * 50)
        return "\n".join(lines)


def get_deepbook_client(network: str = "testnet") -> DeepBookClient:
    """获取 DeepBookClient 实例"""
    return DeepBookClient(network)