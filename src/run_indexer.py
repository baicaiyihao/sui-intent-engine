#!/usr/bin/env python3
"""
DeepBook 索引器 - 从最新数据开始，倒序爬取历史数据
"""
import asyncio
import aiohttp
import time
import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sui.deepbook_db import DeepBookDB, Trade, get_deepbook_db

# DeepBook constants
# NOTE: OrderFilled events come from the ORIGINAL package (v1), not v6!
DEEPBOOK_PKG_V1 = "0x2c8d603bc51326b8c13cef9dd07031a408a48dddb541963357661df5d3204809"
DEEPBOOK_PKG_V6 = "0x337f4f4f6567fcd778d5454f27c16c70e2f274cc6377ea6249ddf491482ef497"
SUI_USDC_POOL = "0xe05dafb5133bcffb8d59f4e12465dc0e9faeaa05e3e342a08fe135800e3e4407"
USDC_DECIMALS = 1e6
SUI_DECIMALS = 1e9

RPC_URL = "https://fullnode.mainnet.sui.io:443"

# Event types for OrderFilled (from different packages)
ORDER_FILLED_EVENT_V1 = f"{DEEPBOOK_PKG_V1}::order_info::OrderFilled"
ORDER_FILLED_EVENT_V6 = f"{DEEPBOOK_PKG_V6}::pool::OrderFilled"

class ProgressTracker:
    def __init__(self):
        self.total_indexed = 0
        self.last_timestamp = 0
        self.start_time = time.time()
        self.batch_count = 0
        self.errors = 0

    def print_status(self, msg=""):
        elapsed = time.time() - self.start_time
        rate = self.batch_count / elapsed if elapsed > 0 else 0
        ts_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.last_timestamp / 1e6)) if self.last_timestamp else 'N/A'
        print(f"[{time.strftime('%H:%M:%S')}] {msg} | Total: {self.total_indexed} | Last ts: {ts_str} | Rate: {rate:.1f} batch/s | Errors: {self.errors}")


async def fetch_json_rpc(method: str, params: dict) -> dict:
    """发送 JSON-RPC 请求"""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": [params]  # Note: params must be an array!
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(RPC_URL, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            if resp.status == 200:
                result = await resp.json()
                if "error" in result:
                    print(f"RPC Error: {result['error']}")
                    return None
                return result.get("result")
            else:
                text = await resp.text()
                print(f"HTTP Error {resp.status}: {text[:200]}")
                return None


def parse_order_filled_event(event: dict, pool_id: str = SUI_USDC_POOL) -> Trade:
    """解析单个 OrderFilled 事件"""
    parsed = event.get("parsedJson", {})
    if not parsed:
        return None

    # 检查是否是目标池子
    if parsed.get("pool_id") != pool_id:
        return None

    try:
        price = int(parsed.get("price", 0)) / USDC_DECIMALS
        quantity = int(parsed.get("base_quantity", 0)) / SUI_DECIMALS
        # timestamp 可以是毫秒或微秒，检测一下大小
        timestamp_val = int(parsed.get("timestamp", 0))
        # 如果大于 1e15 说明是微秒，小于则是毫秒
        timestamp = timestamp_val * 1000 if timestamp_val < 1e15 else timestamp_val
        taker_is_bid = parsed.get("taker_is_bid", True)

        if price > 0 and quantity > 0 and timestamp > 0:
            return Trade(
                tx_digest=event.get("id", {}).get("txDigest", ""),
                event_seq=int(event.get("id", {}).get("eventSeq", 0)),
                timestamp=timestamp,
                price=price,
                quantity=quantity,
                side="buy" if taker_is_bid else "sell",
                pool_id=pool_id
            )
    except Exception as e:
        print(f"Error parsing event: {e}")
    return None


async def query_events(cursor: str = None, limit: int = 100, descending: bool = True) -> dict:
    """查询 OrderFilled 事件"""
    params = {
        "query": {
            "MoveEventType": ORDER_FILLED_EVENT_V1
        },
        "descendingOrder": descending,
        "limit": limit
    }

    if cursor:
        params["cursor"] = cursor

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "suix_queryEvents",
        "params": params  # Note: suix_queryEvents uses object params, not array
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(RPC_URL, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            if resp.status == 200:
                result = await resp.json()
                if "error" in result:
                    print(f"RPC Error: {result['error']}")
                    return None
                return result.get("result")
            else:
                text = await resp.text()
                print(f"HTTP Error {resp.status}: {text[:200]}")
                return None


async def index_batch(db: DeepBookDB, cursor: str = None, limit: int = 100) -> tuple:
    """处理一批事件"""
    result = await query_events(cursor, limit)

    if not result:
        return None, cursor, False

    has_next = result.get("hasNextPage", False)
    next_cursor = result.get("nextCursor")

    all_trades = []

    for event in result.get("data", []):
        trade = parse_order_filled_event(event)
        if trade:
            all_trades.append(trade)

    return all_trades, next_cursor, has_next


async def run_indexer():
    """运行索引器 - 从最新开始倒序爬取"""
    db = get_deepbook_db()
    tracker = ProgressTracker()

    # 尝试获取上次进度
    progress = db.get_progress()
    if progress and progress.get("last_cursor"):
        cursor = progress["last_cursor"]
        print(f"Resuming from cursor: {cursor[:30]}...")
    else:
        cursor = None
        print("Starting fresh indexing...")

    print(f"Target pool: {SUI_USDC_POOL}")
    print("=" * 60)

    consecutive_errors = 0
    max_consecutive_errors = 5

    while True:
        try:
            # 获取一批
            trades, new_cursor, has_next = await index_batch(db, cursor, limit=100)

            if trades is None:
                consecutive_errors += 1
                tracker.errors += 1
                print(f"Request failed (attempt {consecutive_errors}/{max_consecutive_errors})")

                if consecutive_errors >= max_consecutive_errors:
                    print("Too many consecutive errors, stopping")
                    break

                # 指数退避
                wait_time = min(30, 2 ** consecutive_errors)
                print(f"Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
                continue

            consecutive_errors = 0

            # 插入数据库
            if trades:
                inserted = db.insert_trades(trades)
                tracker.total_indexed += inserted
                tracker.last_timestamp = max(t.timestamp for t in trades)

                # 更新进度
                db.update_progress(
                    SUI_USDC_POOL,
                    new_cursor or "",
                    tracker.last_timestamp,
                    tracker.total_indexed
                )

            cursor = new_cursor
            tracker.batch_count += 1

            # 每5批打印状态
            if tracker.batch_count % 5 == 0:
                tracker.print_status(f"Batch {tracker.batch_count}: +{len(trades)} trades")

            # 检查是否完成
            if not has_next or not cursor:
                print("\nReached end of data!")
                break

            # 避免请求过快 - 根据数据量动态调整
            await asyncio.sleep(0.3)

        except Exception as e:
            print(f"Error: {e}")
            tracker.errors += 1
            await asyncio.sleep(5)

    tracker.print_status("FINAL")
    print(f"\nIndexing complete! Total trades: {tracker.total_indexed}")
    print(f"Time elapsed: {time.time() - tracker.start_time:.1f}s")


if __name__ == "__main__":
    print("DeepBook Indexer - Starting...")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    asyncio.run(run_indexer())
