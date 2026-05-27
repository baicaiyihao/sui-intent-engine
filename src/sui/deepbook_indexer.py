"""
DeepBook 交易索引器
从 Sui RPC 遍历所有 DeepBook 交易，提取 OrderFilled 事件
"""
import asyncio
import aiohttp
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
import time

# DeepBook constants
DEEPBOOK_PKG = "0x337f4f4f6567fcd778d5454f27c16c70e2f274cc6377ea6249ddf491482ef497"
SUI_USDC_POOL = "0xe05dafb5133bcffb8d59f4e12465dc0e9faeaa05e3e342a08fe135800e3e4407"
USDC_DECIMALS = 1e6
SUI_DECIMALS = 1e9

RPC_URL = "https://fullnode.mainnet.sui.io:443"

# Indexing state
class IndexerState:
    """索引进度状态"""
    is_running: bool = False
    is_paused: bool = False
    current_cursor: Optional[str] = None
    last_timestamp: int = 0
    total_indexed: int = 0
    errors: List[str] = []
    last_error_time: Optional[float] = None


state = IndexerState()


async def fetch_json_rpc(method: str, params: Dict) -> Optional[Dict]:
    """发送 JSON-RPC 请求"""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(RPC_URL, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if "error" in result:
                        print(f"RPC Error: {result['error']}")
                        return None
                    return result.get("result")
                else:
                    print(f"HTTP Error: {resp.status}")
                    return None
    except Exception as e:
        print(f"Request failed: {e}")
        return None


async def query_transactions(cursor: Optional[str] = None, limit: int = 50) -> Optional[Dict]:
    """查询交易块"""
    params = {
        "filter": {
            "MoveFunction": {
                "package": DEEPBOOK_PKG,
                "module": "pool",
                "function": "place_market_order"
            }
        },
        "options": {"showEvents": True},
        "limit": limit
    }

    if cursor:
        params["cursor"] = cursor

    result = await fetch_json_rpc("suix_queryTransactionBlocks", params)
    return result


def parse_order_filled_events(tx: Dict, pool_id: str = SUI_USDC_POOL) -> List[Dict]:
    """从交易中解析 OrderFilled 事件"""
    trades = []

    for event in tx.get("events", []):
        event_type = event.get("type", "")

        if "OrderFilled" in event_type or "order_filled" in event_type.lower():
            parsed = event.get("parsedJson", {})
            if not parsed:
                continue

            # 检查是否是目标池子
            if parsed.get("pool_id") != pool_id:
                continue

            try:
                price = int(parsed.get("price", 0)) / USDC_DECIMALS
                quantity = int(parsed.get("base_quantity", 0)) / SUI_DECIMALS
                timestamp = int(parsed.get("timestamp", 0))
                taker_is_bid = parsed.get("taker_is_bid", True)

                if price > 0 and quantity > 0 and timestamp > 0:
                    trades.append({
                        "tx_digest": tx.get("digest"),
                        "event_seq": int(event.get("id", {}).get("eventSeq", 0)),
                        "timestamp": timestamp,
                        "price": price,
                        "quantity": quantity,
                        "side": "buy" if taker_is_bid else "sell",
                        "pool_id": pool_id
                    })
            except Exception as e:
                print(f"Error parsing event: {e}")
                continue

    return trades


async def index_batch(db, cursor: Optional[str] = None) -> tuple:
    """处理一批交易"""
    result = await query_transactions(cursor)

    if not result:
        return None, cursor, False

    has_next = result.get("hasNextPage", False)
    next_cursor = result.get("nextCursor")

    all_trades = []

    for tx in result.get("data", []):
        trades = parse_order_filled_events(tx)
        all_trades.extend(trades)

    return all_trades, next_cursor, has_next


async def run_indexer(db, batch_size: int = 100, max_batches: int = 0):
    """
    运行索引器

    batch_size: 每批处理的交易数 (RPC limit 最大 250)
    max_batches: 最大批次数，0 表示无限直到全部索引完
    """
    global state

    if state.is_running:
        print("Indexer already running")
        return

    state.is_running = True
    state.errors = []

    cursor = state.current_cursor
    batch_count = 0

    print(f"[DeepBook Indexer] Starting... cursor: {cursor}")
    print(f"[DeepBook Indexer] Target pool: {SUI_USDC_POOL}")

    start_time = time.time()

    try:
        while True:
            if state.is_paused:
                await asyncio.sleep(1)
                continue

            # 获取一批
            trades, new_cursor, has_next = await index_batch(db, cursor)

            if trades is None:
                # 请求失败，指数退避
                print("[DeepBook Indexer] Request failed, retrying in 5s...")
                await asyncio.sleep(5)
                continue

            # 插入数据库
            if trades:
                inserted = db.insert_trades([
                    type('Trade', (), t) for t in [trades[0]]  # 单条测试
                ] if len(trades) == 0 else [type('Trade', (), t) for t in trades])
                state.total_indexed += len(trades)

            cursor = new_cursor
            state.current_cursor = cursor

            batch_count += 1

            # 更新进度
            if trades:
                latest_ts = max(t["timestamp"] for t in trades)
                state.last_timestamp = latest_ts
                db.update_progress(
                    SUI_USDC_POOL,
                    cursor or "",
                    latest_ts,
                    state.total_indexed
                )

            elapsed = time.time() - start_time
            rate = batch_count / elapsed if elapsed > 0 else 0

            print(f"[DeepBook Indexer] Batch {batch_count}: +{len(trades)} trades, "
                  f"total: {state.total_indexed}, cursor: {str(cursor)[:20]}..., "
                  f"rate: {rate:.1f} batches/s")

            # 检查是否完成
            if not has_next or not cursor:
                print("[DeepBook Indexer] Reached end of data")
                break

            if max_batches > 0 and batch_count >= max_batches:
                print(f"[DeepBook Indexer] Reached max batches ({max_batches})")
                break

            # 避免请求过快
            await asyncio.sleep(0.5)

    except Exception as e:
        print(f"[DeepBook Indexer] Error: {e}")
        state.errors.append(str(e))
        state.last_error_time = time.time()

    finally:
        state.is_running = False
        print(f"[DeepBook Indexer] Stopped. Total indexed: {state.total_indexed}")


def get_indexer_state() -> Dict:
    """获取索引进度状态"""
    return {
        "is_running": state.is_running,
        "is_paused": state.is_paused,
        "current_cursor": state.current_cursor[:20] + "..." if state.current_cursor else None,
        "last_timestamp": state.last_timestamp,
        "last_timestamp_str": datetime.fromtimestamp(state.last_timestamp / 1e6).isoformat() if state.last_timestamp else None,
        "total_indexed": state.total_indexed,
        "errors": state.errors[-5:]  # 最近5个错误
    }


async def start_indexing(db, batch_size: int = 100):
    """启动后台索引任务"""
    loop = asyncio.get_event_loop()
    # 在后台运行索引
    asyncio.create_task(run_indexer(db, batch_size))


# 同步包装器（用于 FastAPI）
def sync_get_state():
    """同步获取状态"""
    return get_indexer_state()


def sync_start_indexer(db):
    """启动索引器（异步转同步）"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_indexing(db))
    return {"status": "started"}
