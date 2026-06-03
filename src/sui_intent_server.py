#!/usr/bin/env python3
"""
SuiIntent Engine - FastAPI Server
SUI 意图驱动交易引擎 API
"""
import sys
import os
from pathlib import Path

# Add src to path for imports
_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

# Resolve static dir relative to this file (works regardless of CWD)
_STATIC_DIR = Path(__file__).parent / "static"

import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

# Import SuiIntent modules
from ai.intent_parser import IntentParser, get_intent_parser, Intent
from ai.guardian import Guardian, get_guardian, RiskReport
from quant_core.data_source.exchange import ExchangeDataSource
from sui.deepbook_client import (
    DeepBookClient, get_deepbook_client,
    OrderSide, PTBPreview, OrderResult
)


# ============================================================================
# Request/Response Models
# ============================================================================

class IntentParseRequest(BaseModel):
    """意图解析请求"""
    text: str  # Natural language input
    use_llm: bool = True  # Use LLM for parsing (fallback to rules if False)


class IntentParseResponse(BaseModel):
    """意图解析响应"""
    success: bool
    intent: Optional[Dict[str, Any]] = None
    human_readable: Optional[str] = None
    error: Optional[str] = None


class RiskCheckRequest(BaseModel):
    """风险检查请求"""
    intent: Dict[str, Any]
    indicators: Dict[str, float]


class RiskCheckResponse(BaseModel):
    """风险检查响应"""
    success: bool
    risk_report: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class PTBPreviewRequest(BaseModel):
    """PTB预览请求"""
    intent: Dict[str, Any]
    current_price: float = 2.0  # Default SUI price for mock


class PTBPreviewResponse(BaseModel):
    """PTB预览响应"""
    success: bool
    preview: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ConfirmRequest(BaseModel):
    """确认执行请求"""
    intent: Dict[str, Any]
    risk_report: Optional[Dict[str, Any]] = None  # Optional risk report to validate
    current_price: float = 2.0


class ExecutionResult(BaseModel):
    """执行结果"""
    success: bool
    order_id: Optional[str] = None
    executed_price: Optional[float] = None
    executed_amount: Optional[float] = None
    slippage: Optional[float] = None
    fees: Optional[float] = None
    tx_hash: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


# ============================================================================
# Global State
# ============================================================================

# Global instances
_intent_parser: Optional[IntentParser] = None
_guardian: Optional[Guardian] = None
_deepbook: Optional[DeepBookClient] = None

# WebSocket connections for real-time updates
_websocket_connections: list = []


# ============================================================================
# Lifespan
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    global _intent_parser, _guardian, _deepbook

    # Initialize services
    print("[SuiIntent] Initializing services...")
    _intent_parser = get_intent_parser()
    _guardian = get_guardian()
    _deepbook = get_deepbook_client("testnet")
    print("[SuiIntent] Services initialized")

    # Start background cache refresh task
    import asyncio
    from sui.deepbook_cache import get_deepbook_cache

    async def auto_refresh_cache():
        """Background task to auto-refresh cache every 10 seconds.
        Runs the sync cache.refresh_all() in a thread so it doesn't block
        the event loop (it makes blocking HTTP calls to the deepbook indexer)."""
        while True:
            try:
                cache = get_deepbook_cache()
                # Offload sync I/O to a worker thread so the event loop stays free
                await asyncio.to_thread(cache.refresh_all)
                print(f"[Cache] Auto-refreshed at {datetime.now().isoformat()}")
            except Exception as e:
                print(f"[Cache] Auto-refresh error: {e}")
            await asyncio.sleep(10)

    refresh_task = asyncio.create_task(auto_refresh_cache())

    yield

    # Cleanup
    refresh_task.cancel()
    print("[SuiIntent] Shutting down...")


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="SuiIntent Engine",
    description="SUI Intent-driven Trading Engine API",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Routes
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "SuiIntent Engine",
        "timestamp": datetime.now().isoformat(),
        "version": "0.1.0"
    }


@app.get("/market/price/{symbol}")
async def get_market_price(symbol: str):
    """Get current market price for a symbol"""
    try:
        ds = ExchangeDataSource("binance")
        # Normalize symbol - CCXT expects format like "SUI/USDT".
        # Accept inputs like "SUI", "SUI/USDT", "SUI_USDT", "SUI-USDT", "sui".
        normalized = symbol.upper().replace("_", "/").replace("-", "/")
        # If still no quote currency, assume USDT
        if "/" not in normalized:
            normalized = f"{normalized}/USDT"
        ticker = ds.fetch_ticker(normalized)
        return {
            "success": True,
            "symbol": normalized,
            "price": ticker.get("last"),
            "bid": ticker.get("bid"),
            "ask": ticker.get("ask"),
            "high": ticker.get("high"),
            "low": ticker.get("low"),
            "volume": ticker.get("volume"),
            "change": ticker.get("change_pct")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Market Data Endpoints (for frontend charts)
# ============================================================================

@app.get("/api/v1/market/ticker")
async def get_market_ticker(symbol: str = "SUI/USDT"):
    """获取市场行情 ticker"""
    try:
        from quant_core import get_market_data_collector
        collector = get_market_data_collector()
        ticker = collector.get_market_info(symbol)
        return {"success": True, "data": ticker}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/v1/market/klines")
async def get_market_klines(symbol: str = "SUI/USDT", timeframe: str = "1h", days: int = 7):
    """获取 K 线数据"""
    try:
        from quant_core import get_market_data_collector
        collector = get_market_data_collector()
        df = collector.collect(symbol, timeframe, days)
        df = df.reset_index()
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp']).astype('int64') // 1000
        elif 'index' in df.columns:
            df['timestamp'] = pd.to_datetime(df['index']).astype('int64') // 1000
        return {"success": True, "data": df.to_dict('records')}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# DeepBook K-line Data Endpoints
# ============================================================================

@app.get("/api/v1/deepbook/klines")
async def get_deepbook_klines(
    timeframe: str = "1h",
    hours: int = 0,  # 默认0表示显示所有数据
    pool_id: str = "0xe05dafb5133bcffb8d59f4e12465dc0e9faeaa05e3e342a08fe135800e3e4407"
):
    """获取 DeepBook K 线数据"""
    try:
        from sui.deepbook_db import get_deepbook_db
        db = get_deepbook_db()

        # 计算时间范围（秒）
        end_time = None
        start_time = None
        if hours > 0:
            end_time = int(datetime.now().timestamp())
            start_time = end_time - (hours * 60 * 60)

        klines = db.get_klines(
            pool_id=pool_id,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
            limit=500
        )

        return {
            "success": True,
            "data": klines,
            "timeframe": timeframe,
            "pool_id": pool_id,
            "count": len(klines)
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


@app.get("/api/v1/deepbook/ticker")
async def get_deepbook_ticker(
    pool_id: str = "0xe05dafb5133bcffb8d59f4e12465dc0e9faeaa05e3e342a08fe135800e3e4407",
    hours: int = 24
):
    """获取 DeepBook 当前行情"""
    try:
        from sui.deepbook_db import get_deepbook_db
        db = get_deepbook_db()
        ticker = db.get_ticker(pool_id=pool_id, hours=hours)

        if ticker:
            return {"success": True, "data": ticker}
        return {"success": False, "error": "No data available"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/v1/deepbook/trades")
async def get_deepbook_trades(
    pool_id: str = "0xe05dafb5133bcffb8d59f4e12465dc0e9faeaa05e3e342a08fe135800e3e4407",
    limit: int = 100
):
    """获取 DeepBook 最近成交记录"""
    try:
        from sui.deepbook_db import get_deepbook_db
        db = get_deepbook_db()
        trades = db.get_trades(pool_id=pool_id, limit=limit)

        return {
            "success": True,
            "data": [
                {
                    "time": t.timestamp / 1e6,  # 转换为秒
                    "time_str": datetime.fromtimestamp(t.timestamp / 1e6).isoformat(),
                    "price": t.price,
                    "quantity": t.quantity,
                    "side": t.side,
                    "tx_digest": t.tx_digest
                }
                for t in trades
            ],
            "count": len(trades)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/v1/deepbook/indexer-status")
async def get_deepbook_indexer_status():
    """获取 DeepBook 索引器状态"""
    try:
        from sui.deepbook_indexer import sync_get_state
        from sui.deepbook_db import get_deepbook_db

        db = get_deepbook_db()
        total_trades = db.get_total_trades_count()
        progress = db.get_progress()

        return {
            "success": True,
            "indexer": sync_get_state(),
            "database": {
                "total_trades": total_trades,
                "progress": progress
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/v1/deepbook/start-indexer")
async def start_deepbook_indexer():
    """启动 DeepBook 索引器（后台运行）"""
    try:
        from sui.deepbook_indexer import sync_start_indexer
        from sui.deepbook_db import get_deepbook_db

        db = get_deepbook_db()
        result = sync_start_indexer(db)

        return {"success": True, "message": "Indexer started", "data": result}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


# ============================================================================
# DeepBook 官方索引器缓存数据 API
# ============================================================================

@app.get("/api/v1/cache/refresh")
async def refresh_deepbook_cache():
    """刷新 DeepBook 缓存数据（从官方索引器拉取）"""
    try:
        from sui.deepbook_cache import get_deepbook_cache
        cache = get_deepbook_cache()
        result = cache.refresh_all()
        return {"success": True, "data": result}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


@app.get("/api/v1/cache/klines")
async def get_cached_klines(
    interval: str = "1h",
    limit: int = 100
):
    """获取缓存的 K 线数据"""
    try:
        from sui.deepbook_cache import get_deepbook_cache
        cache = get_deepbook_cache()
        klines = cache.get_cached_klines(interval=interval, limit=limit)
        return {"success": True, "data": klines, "interval": interval}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/v1/cache/ticker")
async def get_cached_ticker():
    """获取缓存的 ticker 数据"""
    try:
        from sui.deepbook_cache import get_deepbook_cache
        cache = get_deepbook_cache()
        ticker = cache.get_cached_ticker()
        if ticker:
            return {"success": True, "data": ticker}
        return {"success": False, "error": "No cached ticker"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/v1/cache/orderbook")
async def get_cached_orderbook():
    """获取缓存的订单簿数据"""
    try:
        from sui.deepbook_cache import get_deepbook_cache
        cache = get_deepbook_cache()
        orderbook = cache.get_cached_orderbook()
        if orderbook:
            return {"success": True, "data": orderbook}
        return {"success": False, "error": "No cached orderbook"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/")
async def root():
    """Root endpoint - serve UI"""
    return FileResponse(_STATIC_DIR / "index.html")


@app.post("/intent/parse", response_model=IntentParseResponse)
async def parse_intent(request: IntentParseRequest):
    """
    解析自然语言意图

    Example:
        "RSI < 30 时买入 100 美金 SUI，止损 2%"
    """
    try:
        # Create parser with or without LLM
        parser = get_intent_parser() if request.use_llm else IntentParser(None)

        # Parse the input
        intent = parser.parse(request.text)

        return IntentParseResponse(
            success=True,
            intent=intent.to_dict(),
            human_readable=parser.to_human_readable(intent)
        )

    except Exception as e:
        return IntentParseResponse(
            success=False,
            error=str(e)
        )


@app.post("/intent/risk-check", response_model=RiskCheckResponse)
async def check_risk(request: RiskCheckRequest):
    """
    执行风险检查

    Requires indicators dict with RSI, MACD, etc.
    """
    try:
        guardian = get_guardian()
        risk_report = guardian.check_risk(
            indicators=request.indicators,
            intent=request.intent
        )

        return RiskCheckResponse(
            success=True,
            risk_report=risk_report.to_dict()
        )

    except Exception as e:
        return RiskCheckResponse(
            success=False,
            error=str(e)
        )


@app.get("/intent/preview", response_model=PTBPreviewResponse)
async def get_ptb_preview(
    action: str = "buy",
    asset: str = "SUI",
    amount_usd: float = 100.0,
    current_price: float = 2.0
):
    """
    获取 PTB 预览

    Shows the PTB commands that would be executed without actually executing
    """
    try:
        deepbook = get_deepbook_client()

        # Build preview
        side = OrderSide.BUY if action.lower() == "buy" else OrderSide.SELL
        preview = deepbook.build_ptb_preview(
            side=side,
            asset=asset,
            amount_usd=amount_usd,
            current_price=current_price
        )

        return PTBPreviewResponse(
            success=True,
            preview=preview.to_dict()
        )

    except Exception as e:
        return PTBPreviewResponse(
            success=False,
            error=str(e)
        )


@app.post("/intent/confirm", response_model=ExecutionResult)
async def confirm_and_execute(request: ConfirmRequest):
    """
    确认并执行交易

    This executes the actual transaction on DeepBook (mock for MVP)
    """
    try:
        deepbook = get_deepbook_client()

        # Convert dict to Intent if needed
        if isinstance(request.intent, dict):
            intent_dict = request.intent
        else:
            intent_dict = request.intent.dict() if hasattr(request.intent, 'dict') else request.intent

        action = intent_dict.get("action", "buy")
        asset = intent_dict.get("asset", "SUI")
        amount_usd = intent_dict.get("amount_usd", 100.0)
        current_price = request.current_price

        # Validate risk if report provided
        if request.risk_report:
            risk_data = request.risk_report
            if isinstance(risk_data, dict) and not risk_data.get("can_proceed", True):
                return ExecutionResult(
                    success=False,
                    error=f"Risk check failed: {risk_data.get('recommendation', 'Please review risk report')}"
                )

        # Execute the order
        side = OrderSide.BUY if action.lower() == "buy" else OrderSide.SELL
        result = await deepbook.place_market_order(
            side=side,
            asset=asset,
            amount_usd=amount_usd,
            current_price=current_price
        )

        return ExecutionResult(
            success=result.success,
            order_id=result.order_id,
            executed_price=result.executed_price,
            executed_amount=result.executed_amount,
            slippage=result.slippage,
            fees=result.fees,
            tx_hash=result.tx_hash,
            message=result.message
        )

    except Exception as e:
        return ExecutionResult(
            success=False,
            error=str(e)
        )


@app.get("/intent/execute-preview")
async def execute_preview_get(
    text: str,
    use_llm: bool = True,
    current_price: float = 2.0
):
    """
    Combined endpoint: Parse -> Risk Check -> Preview (GET version)

    Returns all three steps in one call for convenience
    """
    return await _execute_preview_core(text, use_llm, current_price)


@app.post("/intent/execute-preview")
async def execute_preview_post(request: dict):
    """
    Combined endpoint: Parse -> Risk Check -> Preview (POST version)

    Accepts JSON body with text, use_llm, and current_price
    """
    text = request.get("text", "")
    use_llm = request.get("use_llm", True)
    current_price = request.get("current_price", 2.0)
    return await _execute_preview_core(text, use_llm, current_price)


async def _execute_preview_core(text: str, use_llm: bool, current_price: float):
    """Shared logic for execute-preview"""
    try:
        parser = get_intent_parser() if use_llm else IntentParser(None)
        guardian = get_guardian()
        deepbook = get_deepbook_client()

        # Step 1: Parse intent
        intent = parser.parse(text)
        intent_dict = intent.to_dict()

        # Step 2: Get mock indicators for risk check
        # In production, these would come from real market data
        indicators = {
            "rsi": 25.0,  # Example oversold
            "macd_histogram": 0.5,
            "macd": 0.1,
            "macd_signal": -0.05,
            "boll_position": 0.15,
            "kdj_k": 20.0,
            "kdj_d": 25.0,
            "kdj_j": 10.0,
            "volume_ratio": 1.2,
            "adx": 30.0
        }

        # Step 3: Risk check
        risk_report = guardian.check_risk(indicators=indicators, intent=intent_dict)

        # Step 4: Build PTB preview
        side = OrderSide.BUY if intent.action == "buy" else OrderSide.SELL
        preview = deepbook.build_ptb_preview(
            side=side,
            asset=intent.asset,
            amount_usd=intent.amount_usd,
            current_price=current_price
        )

        return {
            "success": True,
            "intent": intent_dict,
            "human_readable": parser.to_human_readable(intent),
            "risk_report": risk_report.to_dict(),
            "ptb_preview": preview.to_dict()
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================================
# WebSocket for real-time updates
# ============================================================================

@app.websocket("/ws/updates")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    _websocket_connections.append(websocket)

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()

            # Echo back for now (in production, send real updates)
            await websocket.send_json({
                "type": "echo",
                "data": data,
                "timestamp": datetime.now().isoformat()
            })

    except WebSocketDisconnect:
        if websocket in _websocket_connections:
            _websocket_connections.remove(websocket)


# ============================================================================
# Run Server
# ============================================================================

def run_server(host: str = "0.0.0.0", port: int = 8001):
    """Run the FastAPI server"""
    uvicorn.run(
        "sui_intent_server:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    run_server()
