# SUI Intent Engine Architecture

> **Document Version**: 2.0
> **Last Updated**: 2026-05-11
> **Project**: SUI Intent Engine
> **Track**: The Agentic Web - Sub-track 3: Intent Engine

---

## Table of Contents

1. [Sub-track 3: Intent Engine 赛道分析](#1-sub-track-3-intent-engine-赛道分析)
2. [系统架构图](#2-系统架构图)
3. [组件设计](#3-组件设计)
4. [10步数据流](#4-10步数据流)
5. [API规范](#5-api规范)
6. [6周实现路线图](#6-6周实现路线图)

---

## 1. Sub-track 3: Intent Engine 赛道分析

### 赛道要求

| 要求项 | 规格 | 本引擎实现 |
|--------|------|-----------|
| Text→PTB→execution | 自然语言转换为 Programmable Transaction Block | IntentParser + LLM |
| Human-readable preview | 执行前预览交易意图 | Guardian 生成预览 |
| Guardian≥2类风险 | 风险识别与拦截 | Price, Liquidity, Signature, MEV, Counterparty (5类) |
| Explicit confirmation | 明确用户确认机制 | 双重确认流程 |

### 技术挑战

1. **自然语言歧义**: "买入BTC"可能指BTC/USDT或BTC/USD，需上下文推断
2. **PTB复杂性**: 跨池交换、多跳路由、尾随止损等复杂操作
3. **实时风险**: DeepBook订单簿流动性监控、价格冲击估算
4. **状态同步**: SUI网络状态、DeepBook订单簿、Walrus状态三者一致性

### 风险类别详解

| 风险类别 | 检测方法 | 阈值配置 |
|----------|----------|----------|
| **Price Risk** | Pyth价格源偏离检测 | 偏离>5%触发 |
| **Liquidity Risk** | DeepBook订单簿深度检测 | 深度<$1000触发 |
| **Signature Risk** | 多签/异常签名模式检测 | 多于5个签名者 |
| **MEV Risk** | 交易模式分析、frontrunning检测 | MEV分数>0.3 |
| **Counterparty Risk** | 地址黑名单、流动性池健康度 | 黑名单地址或池健康度<0.5 |

---

## 2. 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SUI Intent Engine                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │   Client     │───▶│   Gateway    │───▶│   Router      │                   │
│  │  (Wallet)    │◀───│   (REST/WS)  │◀───│               │                   │
│  └──────────────┘    └──────────────┘    └───────┬──────┘                   │
│                                                   │                           │
│         ┌────────────────────────────────────────┼───────────────────────┐   │
│         │                                        │                        │   │
│         ▼                                        ▼                        ▼   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────┐ │
│  │IntentParser  │───▶│  Guardian    │───▶│ PTBBuilder   │───▶│ Executor  │ │
│  │  (LLM/MiniMax│◀───│  (Risk)      │◀───│              │◀───│           │ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └────────────┘ │
│         │                   │                   │                        │   │
│         │                   │                   │                        │   │
│         ▼                   ▼                   ▼                        ▼   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────┐ │
│  │  LLM Client  │    │ Risk Policies│    │ DeepBook     │    │  SUI      │ │
│  │  (MiniMax)   │    │ (5 Layers)   │    │ Client       │    │  Network  │ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └────────────┘ │
│                                                     │                        │
│                                                     ▼                        │
│                                              ┌──────────────┐               │
│                                              │ WalrusClient │               │
│                                              │  (Storage)   │               │
│                                              └──────────────┘               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

                         ┌─────────────────────────────────┐
                         │        External Services         │
                         ├─────────────────────────────────┤
                         │  • SUI Full Node (RPC)           │
                         │  • DeepBook Protocol (Orderbook) │
                         │  • Walrus Storage (Blob)         │
                         │  • MiniMax LLM API              │
                         │  • Price Oracle (Pyth)           │
                         └─────────────────────────────────┘
```

### 分层职责

| 层 | 组件 | 职责 |
|----|------|------|
| Gateway | REST API, WebSocket | 请求路由、协议转换、连接管理 |
| Router | Request Router | 意图分发、限流、熔断 |
| Core | IntentParser | 自然语言解析、结构化意图 |
| Core | Guardian | 五类风险检查、预览生成 |
| Core | PTBBuilder | PTB构建、签名编排 |
| Core | Executor | 交易执行、状态追踪 |
| Client | DeepBookClient | 订单簿查询、流动性分析 |
| Client | WalrusClient | 意图状态存储、缓存 |
| Client | LLM Client | MiniMax API 调用 |

---

## 3. 组件设计

### 3.1 IntentParser

```python
class IntentParser:
    """
    自然语言意图解析器
    输入: "我想在SUI上买入1000美元的SUI，限价单，价格低于0.5美元"
    输出: StructuredIntent
    """

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self.prompt_template = """
        将用户意图解析为结构化交易指令。

        支持操作:
        - swap: 交换资产 (e.g., "买入SUI" → swap USDT to SUI)
        - limit_order: 限价单 (e.g., "限价买入SUI，价格低于$0.5")
        - deposit: 存入流动性池
        - withdraw: 从流动性池提取

        资产识别:
        - SUI, USDC, USDT, BTC, ETH 为标准符号
        - "美元" → USDC, "人民币" → CNY (需转换)

        输出JSON格式:
        {
            "action": "swap|limit_order|deposit|withdraw",
            "baseAsset": "asset symbol",
            "quoteAsset": "quote symbol",
            "amount": "number as string",
            "priceLimit": "number as string or null",
            "orderType": "limit|market|stop_limit",
            "slippageTolerance": "0.01",
            "timeInForce": "GTC|IOC|FOK",
            "confidence": 0.0-1.0,
            "ambiguities": ["需确认项列表"]
        }

        用户输入: {user_input}
        """

    async def parse(self, user_input: str, context: dict = None) -> StructuredIntent:
        """解析用户输入为结构化意图"""
        response = await self.llm.complete(
            prompt=self.prompt_template.format(user_input=user_input),
            schema=StructuredIntent,
            temperature=0.1  # 低温度确保确定性
        )
        intent = StructuredIntent(**response)
        if intent.ambiguities:
            intent = await self._resolve_ambiguities(intent, context)
        return intent

    async def _resolve_ambiguities(self, intent: AmbiguousIntent, context: dict) -> StructuredIntent:
        """通过上下文或反问解决歧义"""
        if context and "recent_trades" in context:
            last_trade = context["recent_trades"][0]
            if intent.baseAsset is None:
                intent.baseAsset = last_trade["baseAsset"]
        return intent
```

### 3.2 Guardian

```python
class Guardian:
    """
    五类风险守护器
    职责: 风险识别、预览生成、交易拦截
    """

    RISK_CATEGORIES = {
        "price": PriceRiskDetector,           # 价格异常
        "liquidity": LiquidityRiskDetector,   # 流动性不足
        "signature": SignatureRiskDetector,   # 签名滥用
        "mev": MEVRiskDetector,               # MEV攻击
        "counterparty": CounterpartyRiskDetector  # 交易对手风险
    }

    def __init__(self, deepbook_client: DeepBookClient, pyth_client: PythClient):
        self.detectors = {name: cls(pyth_client) for name, cls in self.RISK_CATEGORIES.items()}
        self.deepbook = deepbook_client

    async def check(self, intent: StructuredIntent, preview: TransactionPreview) -> RiskReport:
        """
        执行五类风险检查
        返回: RiskReport { passed: bool, risks: [], actions: [] }
        """
        tasks = [
            detector.detect(intent, preview)
            for detector in self.detectors.values()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        risk_report = RiskReport(passed=True, risks=[], actions=[])
        for name, result in zip(self.RISK_CATEGORIES.keys(), results):
            if isinstance(result, Exception):
                risk_report.risks.append(RiskItem(category=name, severity="unknown", message=str(result)))
            else:
                risk_report.risks.extend(result.risks)
                risk_report.actions.extend(result.actions)

        # 任一高风险项则不通过
        high_severity = [r for r in risk_report.risks if r.severity == "high"]
        if high_severity:
            risk_report.passed = False

        return risk_report

    async def generate_preview(self, intent: StructuredIntent, ptb: PTB) -> TransactionPreview:
        """生成人类可读的交易预览"""
        return TransactionPreview(
            summary=f"Swap {intent.amount} {intent.quoteAsset} to {intent.baseAsset}",
            details=[
                f"预计成交价格: {preview.estimated_price}",
                f"价格影响: {preview.price_impact}%",
                f"最大滑点: {intent.slippageTolerance * 100}%",
                f"预计执行时间: {preview.estimated_time}",
                f"Gas费用估算: {preview.gas_estimate} SUI",
                f"DeepBook流动性: {preview.liquidity_available}"
            ],
            warnings=preview.warnings,
            safe_confirmation=f"确认执行此交易? 输入 'CONFIRM-{intent.id}' 确认"
        )
```

### 3.3 PTBBuilder

```python
class PTBBuilder:
    """
    Programmable Transaction Block 构建器
    支持: 单一Swap、多跳路由、尾随止损、批量操作
    """

    def __init__(self, deepbook_client: DeepBookClient):
        self.deepbook = deepbook_client
        self.registry = CommandRegistry()

    async def build(self, intent: StructuredIntent, account: SuiAddress) -> PTB:
        """根据意图构建PTB"""
        builder_map = {
            "swap": self._build_swap_ptb,
            "limit_order": self._build_limit_order_ptb,
            "deposit": self._build_deposit_ptb,
            "withdraw": self._build_withdraw_ptb,
        }
        builder = builder_map.get(intent.action)
        if not builder:
            raise ValueError(f"Unsupported action: {intent.action}")

        ptb = await builder(intent, account)
        ptb.set_gas_budget(intent.gas_budget or 10_000_000)
        ptb.set_gas_price(await self._fetch_gas_price())

        return ptb

    async def _build_swap_ptb(self, intent: StructuredIntent, account: SuiAddress) -> PTB:
        """
        构建Swap PTB:
        1. 获取Quote (DeepBook)
        2. 发起PlaceMarketOrder 或 PlaceLimitOrder
        3. 转账结算
        """
        quote = await self.deepbook.get_quote(
            base_asset=intent.baseAsset,
            quote_asset=intent.quoteAsset,
            amount=intent.amount,
            side="buy" if intent.action == "swap" else "sell"
        )

        ptb = ProgrammableTransactionBlock()

        if intent.orderType == "market":
            ptb.add_command(
                self.registry.deepbook.place_market_order(
                    pool_id=quote.pool_id,
                    owner=account,
                    base_asset=intent.baseAsset,
                    quote_asset=intent.quoteAsset,
                    quantity=quote.quantity,
                    side=quote.side
                )
            )
        else:
            ptb.add_command(
                self.registry.deepbook.place_limit_order(
                    pool_id=quote.pool_id,
                    owner=account,
                    base_asset=intent.baseAsset,
                    quote_asset=intent.quoteAsset,
                    quantity=quote.quantity,
                    price=intent.priceLimit,
                    side=quote.side
                )
            )

        return ptb

    async def _build_multi_hop_swap(self, intent: StructuredIntent, account: SuiAddress) -> PTB:
        """
        多跳Swap构建 (e.g., USDT → USDC → SUI)
        通过DeepBook多个池子路由
        """
        routes = await self.deepbook.find_best_route(
            from_asset=intent.quoteAsset,
            to_asset=intent.baseAsset,
            amount=intent.amount
        )

        ptb = ProgrammableTransactionBlock()
        for i, hop in enumerate(routes.hops):
            sub_ptb = ProgrammableTransactionBlock()
            sub_ptb.add_command(
                self.registry.deepbook.place_market_order(
                    pool_id=hop.pool_id,
                    owner=account,
                    base_asset=hop.base,
                    quote_asset=hop.quote,
                    quantity=hop.amount,
                    side=hop.side
                )
            )
            if i < len(routes.hops) - 1:
                ptb.add_nested_transaction(sub_ptb, hop.output)
            else:
                ptb.add_command(sub_ptb)

        return ptb
```

### 3.4 DeepBookClient

```python
class DeepBookClient:
    """
    DeepBook Protocol 客户端
    职责: 订单簿查询、流动性分析、订单管理
    """

    DEEPBOOK_CONTRACT = "0xdee9..."

    def __init__(self, rpc_client: RpcClient):
        self.rpc = rpc_client

    async def get_order_book(self, pool_id: str) -> OrderBook:
        """获取指定池的订单簿"""
        result = await self.rpc.get_dynamic_fields(pool_id)
        bids = await self._fetch_orders(result, "bids")
        asks = await self._fetch_orders(result, "asks")
        return OrderBook(bids=bids, asks=asks)

    async def get_quote(
        self,
        base_asset: str,
        quote_asset: str,
        amount: Decimal,
        side: str  # "buy" | "sell"
    ) -> Quote:
        """
        获取交易报价 (模拟聚合器)
        返回: 最佳可用价格及数量
        """
        pool_id = self._get_pool_id(base_asset, quote_asset)
        order_book = await self.get_order_book(pool_id)

        if side == "buy":
            orders = order_book.asks
        else:
            orders = order_book.bids

        filled, avg_price = self._calculate_fill(orders, amount)
        return Quote(
            pool_id=pool_id,
            base=base_asset,
            quote=quote_asset,
            quantity=amount,
            side=side,
            average_price=avg_price,
            slippage=self._calculate_slippage(avg_price, orders[0].price if orders else None)
        )

    async def analyze_liquidity(self, base_asset: str, quote_asset: str) -> LiquidityAnalysis:
        """流动性分析"""
        pool_id = self._get_pool_id(base_asset, quote_asset)
        order_book = await self.get_order_book(pool_id)

        total_bid_volume = sum(o.quantity * o.price for o in order_book.bids)
        total_ask_volume = sum(o.quantity * o.price for o in order_book.asks)

        price_impact_1pct = self._calculate_price_impact(order_book, Decimal("0.01"))
        price_impact_5pct = self._calculate_price_impact(order_book, Decimal("0.05"))

        return LiquidityAnalysis(
            pool_id=pool_id,
            total_bid_volume=total_bid_volume,
            total_ask_volume=total_ask_volume,
            spread=order_book.spread,
            price_impact_1pct=price_impact_1pct,
            price_impact_5pct=price_impact_5pct,
            recommendation="high" if total_bid_volume > 100_000 else "medium" if total_bid_volume > 10_000 else "low"
        )

    def _get_pool_id(self, base: str, quote: str) -> str:
        """计算Pool ID"""
        return f"{base}_{quote}_pool"

    def _calculate_fill(self, orders: list[Order], amount: Decimal) -> tuple[Decimal, Decimal]:
        """计算订单成交情况"""
        remaining = amount
        total_cost = Decimal("0")
        for order in sorted(orders, key=lambda x: x.price):
            if remaining <= 0:
                break
            fill_qty = min(remaining, order.quantity)
            total_cost += fill_qty * order.price
            remaining -= fill_qty
        avg_price = total_cost / (amount - remaining) if remaining < amount else 0
        return amount - remaining, avg_price
```

### 3.5 WalrusClient

```python
class WalrusClient:
    """
    Walrus Storage 客户端
    职责: 意图状态存储、意图历史、缓存管理
    """

    WALRUS_CONTRACT = "0xwalrus..."

    def __init__(self, rpc_client: RpcClient, storage_client: BlobClient):
        self.rpc = rpc_client
        self.storage = storage_client
        self.cache = TTLCache(maxsize=1000, ttl=300)  # 5分钟缓存

    async def store_intent(self, intent: StructuredIntent, status: IntentStatus) -> str:
        """
        存储意图到Walrus
        返回: Blob ID
        """
        intent_data = IntentState(
            intent=intent,
            status=status,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        ).model_dump_json()

        blob_id = await self.storage.write(intent_data.encode())
        return blob_id

    async def get_intent(self, intent_id: str) -> Optional[IntentState]:
        """从缓存或存储获取意图"""
        if intent_id in self.cache:
            return self.cache[intent_id]

        data = await self.storage.read(intent_id)
        if data:
            state = IntentState.model_validate_json(data)
            self.cache[intent_id] = state
            return state
        return None

    async def update_intent_status(self, intent_id: str, status: IntentStatus, result: dict = None):
        """更新意图状态"""
        state = await self.get_intent(intent_id)
        if state:
            state.status = status
            state.updated_at = datetime.utcnow()
            if result:
                state.result = result
            await self.storage.write(state.model_dump_json().encode(), key=intent_id)
            self.cache[intent_id] = state

    async def list_intents_by_status(self, address: SuiAddress, status: IntentStatus, limit: int = 50) -> list[IntentState]:
        """列出用户指定状态的意图"""
        query = f"owner:{address} AND status:{status.value}"
        results = await self.storage.query(query, limit=limit)
        return [IntentState.model_validate_json(r) for r in results]
```

---

## 4. 10步数据流

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Intent Engine 10-Step Data Flow                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Step 1: Intent Input                                                       │
│  ┌──────────────┐                                                           │
│  │   User       │──"我想买入1000 USDT的SUI，价格低于$0.5"                     │
│  │   Wallet     │                                                            │
│  └──────────────┘                                                            │
│         │                                                                    │
│         ▼                                                                    │
│  Step 2: Gateway Routing                                                    │
│  ┌──────────────┐     ┌──────────────┐                                      │
│  │   Gateway    │────▶│   Router      │──▶ Rate Limit                        │
│  │   (REST)     │     │               │──▶ Auth Check                        │
│  └──────────────┘     └──────────────┘                                      │
│         │                                                                    │
│         ▼                                                                    │
│  Step 3: Intent Parsing (IntentParser)                                       │
│  ┌──────────────┐     ┌──────────────┐                                      │
│  │ IntentParser  │────▶│   LLM API     │──"MiniMax"                          │
│  │              │     │   (MiniMax)   │                                      │
│  └──────────────┘     └──────────────┘                                      │
│         │                   │                                                │
│         │   StructuredIntent {                                            │
│         │     action: "swap",                                              │
│         │     baseAsset: "SUI",                                            │
│         │     quoteAsset: "USDT",                                         │
│         │     amount: 1000,                                                │
│         │     priceLimit: 0.5                                              │
│         │   }                                                               │
│         ▼                                                                    │
│  Step 4: Preview Generation (Guardian)                                       │
│  ┌──────────────┐     ┌──────────────┐                                      │
│  │  Guardian    │────▶│  DeepBook     │── Query Order Book                   │
│  │              │     │  Client       │                                      │
│  └──────────────┘     └──────────────┘                                      │
│         │                                                                    │
│         │   TransactionPreview {                                           │
│         │     estimated_price: 0.498,                                      │
│         │     price_impact: 0.4%,                                          │
│         │     gas_estimate: 0.002 SUI                                       │
│         │   }                                                               │
│         ▼                                                                    │
│  Step 5: Risk Assessment (Guardian)                                          │
│  ┌──────────────┐     ┌──────────────┐                                      │
│  │   Guardian   │────▶│ Risk Engines │                                      │
│  │              │     │ • PriceRisk   │                                      │
│  │              │     │ • Liquidity   │                                      │
│  │              │     │ • Signature   │                                      │
│  │              │     │ • MEV         │                                      │
│  │              │     │ • Counterparty│                                      │
│  └──────────────┘     └──────────────┘                                      │
│         │                                                                    │
│         ▼                                                                    │
│  Step 6: Human-Readable Confirmation                                         │
│  ┌──────────────┐                                                           │
│  │   Preview    │──▶ "Swap 1000 USDT to SUI"                                │
│  │   UI         │    "Estimated: 2007.2 SUI @ $0.498"                       │
│  └──────────────┘    "Price Impact: 0.4%"                                  │
│                      "Gas: 0.002 SUI"                                       │
│                      "Type CONFIRM-abc123 to execute"                       │
│         │                                                                    │
│         │ [User Confirmation: "CONFIRM-abc123"]                             │
│         ▼                                                                    │
│  Step 7: PTB Construction (PTBBuilder)                                      │
│  ┌──────────────┐     ┌──────────────┐                                      │
│  │  PTBBuilder  │────▶│  DeepBook     │── Fetch Latest Quote                 │
│  │              │     │  Client       │                                      │
│  └──────────────┘     └──────────────┘                                      │
│         │                                                                    │
│         ▼                                                                    │
│  Step 8: Transaction Signing                                                │
│  ┌──────────────┐     ┌──────────────┐                                      │
│  │  Executor    │────▶│   Wallet     │── Sui Wallet (zkLogin/signature)    │
│  │              │     │   Provider   │                                      │
│  └──────────────┘     └──────────────┘                                      │
│         │                                                                    │
│         ▼                                                                    │
│  Step 9: Execution & Monitoring                                             │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                  │
│  │  Executor    │────▶│ SUI Network  │────▶│   Finality   │                  │
│  │              │     │              │     │   (2-3 sec)  │                  │
│  └──────────────┘     └──────────────┘     └──────────────┘                  │
│         │                                                                    │
│         ▼                                                                    │
│  Step 10: State Persistence                                                  │
│  ┌──────────────┐     ┌──────────────┐                                      │
│  │ WalrusClient │────▶│   Walrus     │── Store Intent + Result              │
│  │              │     │   Storage    │── Update Cache                       │
│  └──────────────┘     └──────────────┘                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 详细步骤说明

| Step | 组件 | 输入 | 输出 | 异常处理 |
|------|------|------|------|----------|
| 1 | User | 自然语言意图 | - | - |
| 2 | Gateway | HTTP Request | Authenticated Request | 429 Rate Limit, 401 Unauthorized |
| 3 | IntentParser | text | StructuredIntent | AmbiguousIntent (需确认) |
| 4 | Guardian | intent | TransactionPreview | - |
| 5 | Guardian | preview | RiskReport | Block if high risk |
| 6 | Gateway | preview | User Confirmation | Timeout 5min |
| 7 | PTBBuilder | intent | PTB (unsigned) | InvalidIntent |
| 8 | Wallet | tx_bytes | Signed tx_bytes | UserRejected, LedgerError |
| 9 | Executor | signed_tx | TxDigest, Status | Pending → Confirmed/Failed |
| 10 | WalrusClient | intent + result | BlobId | Retry 3x |

---

## 5. API规范

### 5.1 REST API

```
POST /api/v1/intent/parse
Description: 解析自然语言意图
Request:
{
    "text": "我想买入1000 USDT的SUI，价格低于0.5美元",
    "context": {
        "recent_trades": [{"baseAsset": "SUI", "quoteAsset": "USDT"}]
    }
}
Response (200):
{
    "intent_id": "intent_abc123",
    "action": "swap",
    "base_asset": "SUI",
    "quote_asset": "USDT",
    "amount": "1000",
    "price_limit": "0.5",
    "order_type": "limit",
    "confidence": 0.95,
    "ambiguities": [],
    "preview": {
        "estimated_price": "0.498",
        "price_impact": "0.4%",
        "gas_estimate": "0.002 SUI",
        "max_slippage": "1%"
    },
    "risk_report": {
        "passed": true,
        "risks": [
            {"category": "price", "severity": "low", "message": "价格正常"}
        ]
    },
    "confirmation_token": "CONFIRM-abc123"
}

POST /api/v1/intent/confirm
Description: 确认执行意图
Request:
{
    "intent_id": "intent_abc123",
    "confirmation_token": "CONFIRM-abc123"
}
Response (200):
{
    "tx_digest": "0x...",
    "status": "pending",
    "block_time": 1715400000
}

GET /api/v1/intent/{intent_id}
Description: 查询意图状态
Response (200):
{
    "intent_id": "intent_abc123",
    "status": "confirmed",
    "result": {
        "sui_amount": "2007.2",
        "avg_price": "0.498",
        "gas_used": "1500000"
    }
}

POST /api/v1/intent/cancel
Description: 取消意图
Request:
{
    "intent_id": "intent_abc123"
}
Response (200):
{
    "success": true,
    "cancelled_tx": "0x..."
}
```

### 5.2 WebSocket API

```
WS /ws/intent/{intent_id}
Description: 实时意图状态推送
Messages:
{
    "type": "status_update",
    "intent_id": "intent_abc123",
    "status": "confirmed",
    "timestamp": 1715400000
}
{
    "type": "price_alert",
    "intent_id": "intent_abc123",
    "message": "SUI价格已达到$0.5，您的限价单将成交"
}
{
    "type": "risk_warning",
    "intent_id": "intent_abc123",
    "risk": {"category": "liquidity", "severity": "medium", "message": "流动性骤降"}
}
```

### 5.3 错误码

| Code | Message | 说明 |
|------|---------|------|
| 40001 | INVALID_INTENT | 意图格式错误 |
| 40002 | AMBIGUOUS_INTENT | 意图有歧义，需确认 |
| 40003 | RISK_BLOCKED | 风险评估不通过 |
| 40004 | CONFIRMATION_TIMEOUT | 确认超时 |
| 40005 | INVALID_CONFIRMATION_TOKEN | 确认令牌错误 |
| 40101 | WALLET_NOT_CONNECTED | 钱包未连接 |
| 40102 | SIGNATURE_REJECTED | 用户拒绝签名 |
| 50301 | DEEPBOOK_UNAVAILABLE | DeepBook服务不可用 |
| 50302 | SUI_NETWORK_SLOW | SUI网络繁忙 |

---

## 6. 6周实现路线图

```
Week 1: 核心框架与IntentParser
─────────────────────────────────────────────────────────────────────────────
  Day 1-2: 项目初始化
    • 搭建Rust/TypeScript项目结构
    • 配置SUI开发环境 (devnet/testnet)
    • 集成MiniMax LLM SDK
    • 实现基础Gateway (REST + WebSocket)

  Day 3-4: IntentParser MVP
    • 设计StructuredIntent数据模型
    • 实现LLM提示词模板
    • 实现基础解析逻辑
    • 单元测试: 10+主流意图场景

  Day 5-7: 基础Guardian框架
    • 定义RiskReport接口
    • 实现PriceRiskDetector (Pyth价格源)
    • 实现Guardian接口
    • 集成预览生成

  Milestone: 端到端解析流程可运行

Week 2: DeepBook集成与PTBBuilder
─────────────────────────────────────────────────────────────────────────────
  Day 8-9: DeepBookClient
    • 集成SUI SDK (Rust/TypeScript)
    • 实现订单簿查询 (get_order_book)
    • 实现Quote计算 (get_quote)
    • 本地测试网验证

  Day 10-11: PTBBuilder基础
    • 实现单一Swap PTB构建
    • 实现Gas配置
    • 测试PTB序列化/反序列化
    • SUI devnet部署测试

  Day 12-14: Guardian完善
    • 实现LiquidityRiskDetector
    • 实现SignatureRiskDetector
    • 实现预览UI组件
    • 端到端确认流程

  Milestone: 可执行完整Swap交易

Week 3: 高级风险检测
─────────────────────────────────────────────────────────────────────────────
  Day 15-17: MEV & Counterparty检测
    • 研究SUI MEV特性
    • 实现MEVRiskDetector
    • 实现CounterpartyRiskDetector
    • 交易模式识别

  Day 18-19: 复杂订单类型
    • 尾随止损 (Trailing Stop)
    • 冰山订单 (Iceberg)
    • 多跳Swap路由
    • PTBBuilder扩展

  Day 20-21: 集成测试
    • 全链路测试 (devnet)
    • 风险检测覆盖率测试
    • 并发测试
    • 性能基准测试

  Milestone: 5类风险检测完成

Week 4: Walrus集成与状态管理
─────────────────────────────────────────────────────────────────────────────
  Day 22-24: WalrusClient
    • Walrus SDK集成
    • 意图状态序列化
    • 存储读写实现
    • 缓存策略 (TTLCache)

  Day 25-26: 意图生命周期
    • 意图状态机设计
    • 超时/取消逻辑
    • 状态持久化
    • 历史查询API

  Day 27-28: WebSocket增强
    • 实时状态推送
    • 价格预警
    • 风险通知
    • 断线重连

  Milestone: 意图完整生命周期管理

Week 5: API完善与监控
─────────────────────────────────────────────────────────────────────────────
  Day 29-31: API完善
    • 完整REST API实现
    • 错误码体系
    • 请求验证
    • API文档 (OpenAPI)

  Day 32-33: 监控告警
    • Prometheus指标
    • 日志结构化
    • 告警规则
    • Dashboard

  Day 34-35: 安全加固
    • 输入验证
    • 防重放攻击
    • 限流熔断
    • 审计日志

  Milestone: 生产级API就绪

Week 6: 测试网验证与优化
─────────────────────────────────────────────────────────────────────────────
  Day 36-38: Testnet验证
    • Testnet完整流程
    • 与DeepBook交互
    • 与Walrus交互
    • 真实交易测试

  Day 39-40: 性能优化
    • LLM调用缓存
    • PTB构建优化
    • 并发优化
    • 延迟优化

  Day 41-42: 文档与发布
    • 开发者文档
    • API Reference
    • 示例代码
    • 版本发布

  Milestone: Testnet Ready
```

### 关键里程碑

| Week | Milestone | 验收标准 |
|------|-----------|----------|
| 1 | IntentParser可用 | 10个意图解析成功率>90% |
| 2 | Swap可执行 | Devnet完成100次Swap |
| 3 | 5类风险检测 | 风险检测覆盖率100% |
| 4 | 状态管理完整 | 意图全生命周期可追踪 |
| 5 | 生产级API | 所有端点通过压力测试 |
| 6 | Testnet Ready | Testnet稳定运行7天 |

### 依赖关系

```
IntentParser ──────┬──▶ Guardian ────▶ PTBBuilder ───▶ Executor
                   │        │                │
                   │        │                │
                   ▼        ▼                ▼
               LLM API  DeepBookClient   DeepBookClient
                                                     │
                                                     ▼
                                                  WalrusClient
```

### 技术栈

| 组件 | 技术选型 | 理由 |
|------|----------|------|
| 后端框架 | Rust / TypeScript | SUI官方SDK支持、性能 |
| API层 | Axum (Rust) / Express (TS) | 成熟生态 |
| LLM | MiniMax | MEMORY指定、已有配置 |
| 存储 | Walrus | SUI原生存储 |
| 订单簿 | DeepBook | SUI原生DEX |
| 钱包 | Sui Wallet / zkLogin | Web3Auth集成 |
| 价格源 | Pyth | SUI生态标准Oracle |

---

## Appendix A: 数据模型

```rust
// StructuredIntent
struct StructuredIntent {
    id: String,
    action: IntentAction,  // swap, limit_order, deposit, withdraw
    base_asset: Asset,
    quote_asset: Asset,
    amount: Decimal,
    price_limit: Option<Decimal>,
    order_type: OrderType,  // market, limit, stop_limit
    slippage_tolerance: Decimal,
    time_in_force: TimeInForce,  // GTC, IOC, FOK
    gas_budget: Option<u64>,
    created_at: Timestamp,
}

// TransactionPreview
struct TransactionPreview {
    summary: String,
    estimated_price: Decimal,
    price_impact: Decimal,  // percentage
    gas_estimate: Decimal,
    liquidity_available: Decimal,
    max_slippage: Decimal,
    estimated_time: Duration,
    warnings: Vec<String>,
}

// RiskReport
struct RiskReport {
    passed: bool,
    risks: Vec<RiskItem>,
    actions: Vec<RiskAction>,
}

struct RiskItem {
    category: RiskCategory,  // price, liquidity, signature, mev, counterparty
    severity: Severity,      // low, medium, high, critical
    message: String,
    details: Option<Value>,
}
```

## Appendix B: 配置参考

```yaml
# config.yaml
intent_engine:
  host: "0.0.0.0"
  port: 8080
  env: "testnet"

llm:
  provider: "minimax"
  api_key: "${MINIMAX_API_KEY}"
  model: "MiniMax-Text-01"
  temperature: 0.1
  max_tokens: 2048

sui:
  network: "testnet"
  rpc_url: "https://rpc.testnet.sui.io"
  ws_url: "wss://ws.testnet.sui.io"

deepbook:
  contract: "0xdee9..."
  orderbook_refresh_ms: 1000

walrus:
  contract: "0xwalrus..."
  storage_refresh_ms: 5000

guardian:
  risk_threshold:
    price_deviation: 0.05
    liquidity_min: 1000
    mev_score_max: 0.3
  confirmation_timeout_seconds: 300

risk_engines:
  price:
    enabled: true
    price_sources: ["pyth"]
    deviation_threshold: 0.05
  liquidity:
    enabled: true
    min_volume_24h: 10000
    min_order_book_depth: 1000
  signature:
    enabled: true
    max_signers: 5
  mev:
    enabled: true
    mev_detection_threshold: 0.3
  counterparty:
    enabled: true
    blacklist: []
```

---

*Document End*
