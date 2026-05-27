"""
QuantCore API Server - FastAPI后端
"""
import asyncio
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import uvicorn
import os
import json
import numpy as np
import pandas as pd

from quant_core import QuantEngine, get_database
from quant_core.strategy.custom import get_custom_engine, CustomIndicatorEngine
from quant_core.ai.websocket_manager import get_websocket_manager
from quant_core.backtest.simulator import SimulatedExecutor
from quant_core.strategy.snapshot import get_strategy_snapshot


# 自定义JSON序列化器
class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def _clean_nan(obj):
    """递归清理NaN值"""
    if isinstance(obj, dict):
        return {k: _clean_nan(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_clean_nan(v) for v in obj]
    elif isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return obj
    elif isinstance(obj, np.floating):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def safe_json(data):
    """安全序列化JSON，处理NaN/Inf"""
    cleaned = _clean_nan(data)
    return json.loads(json.dumps(cleaned, ensure_ascii=False))


app = FastAPI(title="QuantCore API", version="1.0.0")

# 获取模板目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


app = FastAPI(title="QuantCore API", version="1.0.0")

# CORS配置 - WebSocket 需要特殊处理
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # WebSocket 不支持 credentials
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 前端 ====================

@app.get("/")
def root():
    """前端页面"""
    return FileResponse(os.path.join(BASE_DIR, "templates", "index.html"))


# ==================== 请求模型 ====================

class AnalyzeRequest(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: str = "1D"
    days: int = 30


class BacktestRequest(BaseModel):
    symbol: str
    timeframe: str = "1D"
    days: int = 30
    initial_balance: float = 10000
    stop_loss: float = 2.0
    take_profit: float = 6.0
    trailing_stop: bool = False
    trailing_pct: float = 1.5
    commission: float = 0.001
    slippage: float = 0.0005
    leverage: float = 1.0
    use_rsi: bool = True
    use_macd: bool = False


class StrategyRequest(BaseModel):
    symbol: str
    description: str
    timeframe: str = "1D"
    days: int = 30
    initial_balance: float = 10000


class CustomScriptRequest(BaseModel):
    symbol: str
    code: str
    timeframe: str = "1D"
    days: int = 30
    initial_balance: float = 10000
    stop_loss: float = 2.0
    take_profit: float = 6.0
    commission: float = 0.001


class IndicatorRequest(BaseModel):
    symbol: str
    indicator: str
    timeframe: str = "1D"
    days: int = 30
    params: Optional[str] = None  # e.g., "period=14,fast=12"


# ==================== API端点 ====================

@app.get("/")
def root():
    return {"message": "QuantCore API", "version": "1.0.0", "status": "running"}


@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# ==================== 分析相关 ====================

@app.post("/api/v1/analyze")
def analyze(request: AnalyzeRequest):
    """AI技术分析"""
    try:
        engine = QuantEngine(testnet=True)
        result = engine.analyze(request.symbol, request.timeframe, request.days)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return {
            "success": True,
            "data": safe_json(result),
            "report": engine.analyzer.generate_report(result)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 回测相关 ====================

@app.post("/api/v1/backtest")
def backtest(request: BacktestRequest):
    """运行回测"""
    try:
        engine = QuantEngine(testnet=True)

        indicators = []
        if request.use_rsi:
            indicators.append({"name": "RSI", "params": {"period": 14}})
        if request.use_macd:
            indicators.append({"name": "MACD", "params": {}})

        strategy = {
            "name": "API Strategy",
            "indicators": indicators,
            "risk_management": {
                "stop_loss_pct": request.stop_loss,
                "take_profit_pct": request.take_profit,
                "trailing_stop": request.trailing_stop,
                "trailing_pct": request.trailing_pct
            },
            "position_size": {"method": "fixed", "value": 100},
            "commission": request.commission,
            "slippage": request.slippage,
            "leverage": request.leverage
        }

        result = engine.backtest(
            request.symbol, strategy,
            request.timeframe, request.days,
            request.initial_balance
        )

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        # 保存到数据库
        run_id = engine.save_backtest(
            symbol=request.symbol,
            timeframe=request.timeframe,
            result=result,
            strategy_name=strategy["name"],
            config=strategy
        )

        return {
            "success": True,
            "run_id": run_id,
            "data": safe_json(result)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/backtest/history")
def get_backtest_history(symbol: Optional[str] = None, limit: int = 50):
    """获取回测历史"""
    try:
        engine = QuantEngine()
        history = engine.get_backtest_history(symbol=symbol, limit=limit)
        return {"success": True, "data": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/backtest/{run_id}")
def get_backtest_detail(run_id: int):
    """获取回测详情"""
    try:
        engine = QuantEngine()
        detail = engine.get_backtest_detail(run_id)
        if not detail:
            raise HTTPException(status_code=404, detail="Backtest not found")
        return {"success": True, "data": detail}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 策略相关 ====================

@app.post("/api/v1/strategy")
def compile_strategy(request: StrategyRequest):
    """编译自然语言策略"""
    try:
        engine = QuantEngine(testnet=True)
        market_info = engine.market_collector.get_market_info(request.symbol)

        result = engine.strategy_compiler.compile_strategy(
            request.description,
            {**market_info, "symbol": request.symbol}
        )

        return {"success": True, "data": safe_json(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/ai/signal")
async def get_ai_signal(symbol: str = "BTC/USDT", timeframe: str = "1H", days: int = 7, language: str = "zh-CN"):
    """AI实时交易信号 - 获取当前市场的AI交易建议"""
    try:
        engine = QuantEngine(testnet=True)

        # 获取K线数据
        df = engine.market_collector.collect(symbol, timeframe, days=days)
        if df.empty:
            raise HTTPException(status_code=400, detail=f"No data for {symbol}")

        # 获取实时价格
        ticker = engine.data_source.fetch_ticker(symbol)
        current_price = ticker.get("last") if isinstance(ticker, dict) else df["close"].iloc[-1]

        # AI生成信号
        from quant_core.ai.trading_signal import get_ai_signal_service
        ai_service = get_ai_signal_service()
        signal = ai_service.generate_signal(df, symbol, current_price, timeframe, language)

        result = {
            "success": True,
            "symbol": symbol,
            "timeframe": timeframe,
            "days": days,
            "current_price": current_price,
            "signal": signal
        }

        # WebSocket广播信号
        ws_manager = get_websocket_manager()
        if ws_manager.connection_count > 0:
            signal_type = signal.get("action", "HOLD")
            await ws_manager.send_signal(signal_type, result)

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/strategy/backtest")
def strategy_backtest(request: StrategyRequest):
    """编译策略并回测"""
    try:
        engine = QuantEngine(testnet=True)
        market_info = engine.market_collector.get_market_info(request.symbol)

        strategy = engine.strategy_compiler.compile_strategy(
            request.description,
            {**market_info, "symbol": request.symbol}
        )

        result = engine.backtest(
            request.symbol, strategy,
            request.timeframe, request.days,
            request.initial_balance
        )

        run_id = engine.save_backtest(
            symbol=request.symbol,
            timeframe=request.timeframe,
            result=result,
            strategy_name=strategy.get("name", "Compiled Strategy"),
            config=strategy
        )

        return {
            "success": True,
            "strategy": strategy,
            "backtest": result,
            "run_id": run_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 自定义指标相关 ====================

@app.get("/api/v1/indicator/examples")
def get_indicator_examples():
    """获取示例代码"""
    engine = get_custom_engine()
    return {
        "success": True,
        "data": {
            "rsi": CustomIndicatorEngine.get_example_code("rsi"),
            "macd": CustomIndicatorEngine.get_example_code("macd"),
            "boll": CustomIndicatorEngine.get_example_code("boll")
        }
    }


@app.post("/api/v1/indicator/validate")
def validate_code(code: str):
    """验证代码"""
    engine = get_custom_engine()
    is_valid, error = engine.validate_code(code)
    return {"success": True, "valid": is_valid, "error": error}


@app.post("/api/v1/indicator/run")
def run_indicator(request: IndicatorRequest):
    """运行指标计算"""
    try:
        from quant_core import get_market_data_collector, calculate_indicator

        collector = get_market_data_collector()
        df = collector.collect(request.symbol, request.timeframe, request.days)

        if df.empty:
            raise HTTPException(status_code=400, detail=f"No data for {request.symbol}")

        params = {}
        if request.params:
            for pair in request.params.split(","):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    try:
                        params[key.strip()] = int(value.strip())
                    except ValueError:
                        try:
                            params[key.strip()] = float(value.strip())
                        except ValueError:
                            params[key.strip()] = value.strip()

        result_df = calculate_indicator(df, request.indicator.upper(), **params)

        return {
            "success": True,
            "data": safe_json(result_df.tail(20).to_dict(orient="records"))
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/script/backtest")
def custom_script_backtest(request: CustomScriptRequest):
    """自定义指标脚本回测"""
    try:
        from quant_core import get_market_data_collector
        from quant_core.backtest import BacktestEngine, BacktestConfig

        collector = get_market_data_collector()
        df = collector.collect(request.symbol, request.timeframe, request.days)

        if df.empty:
            raise HTTPException(status_code=400, detail=f"No data for {request.symbol}")

        engine = get_custom_engine()
        result = engine.execute(request.code, df)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        # 提取信号
        signals_df = engine.extract_signals(result)
        if not signals_df.empty:
            df = df.join(signals_df)

        # 信号函数
        def signal_func(kdf, ind_df, i):
            if "buy" in kdf.columns and kdf["buy"].iloc[i]:
                return "buy"
            if "sell" in kdf.columns and kdf["sell"].iloc[i]:
                return "sell"
            return None

        strategy = {
            "name": result.get("name", "Custom"),
            "risk_management": {
                "stop_loss_pct": request.stop_loss,
                "take_profit_pct": request.take_profit,
            },
            "position_size": {"method": "fixed", "value": 100},
            "commission": request.commission,
        }

        cfg = BacktestConfig(
            initial_balance=request.initial_balance,
            commission=request.commission
        )
        bt_engine = BacktestEngine(config=cfg)
        bt_result = bt_engine.run(df, strategy, df, signal_func=signal_func)

        return {
            "success": True,
            "indicator": safe_json(result),
            "backtest": safe_json(bt_result)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 策略管理 ====================

@app.get("/api/v1/strategies")
def list_strategies(limit: int = 50):
    """列出策略"""
    try:
        engine = QuantEngine()
        strategies = engine.list_strategies(limit=limit)
        return {"success": True, "data": strategies}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/strategies")
def save_strategy(name: str, description: str = "", code: str = "",
                  indicators: List = None, risk_management: Dict = None):
    """保存策略"""
    try:
        engine = QuantEngine()
        strategy_id = engine.save_strategy(
            name=name,
            description=description,
            code=code,
            indicators=indicators or [],
            risk_management=risk_management or {}
        )
        return {"success": True, "id": strategy_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== AI 代码质量审查 ====================

class CodeQualityRequest(BaseModel):
    code: str

@app.post("/api/v1/indicator/quality")
def analyze_code_quality(request: CodeQualityRequest):
    """分析指标代码质量"""
    try:
        from quant_core.ai.indicator_quality import analyze_indicator_code_quality
        hints = analyze_indicator_code_quality(request.code)
        return {"success": True, "hints": hints}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== AI 分析历史 ====================

@app.get("/api/v1/ai/history")
def get_ai_history(symbol: str = None, days: int = 7, limit: int = 10):
    """获取 AI 分析历史"""
    try:
        from quant_core.ai.analysis_memory import get_analysis_memory
        memory = get_analysis_memory()
        history = memory.get_recent(symbol=symbol, days=days, limit=limit)
        return {"success": True, "data": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/ai/similar-patterns")
def get_similar_patterns(symbol: str, rsi: float = None, macd: float = None):
    """查找相似的历史形态"""
    try:
        from quant_core.ai.analysis_memory import get_analysis_memory
        memory = get_analysis_memory()
        indicators = {}
        if rsi is not None:
            indicators["rsi"] = rsi
        if macd is not None:
            indicators["macd"] = macd
        patterns = memory.get_similar_patterns(symbol, indicators)
        return {"success": True, "data": patterns}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/ai/performance")
def get_ai_performance(symbol: str = None, days: int = 30):
    """获取 AI 分析性能统计"""
    try:
        from quant_core.ai.analysis_memory import get_analysis_memory
        memory = get_analysis_memory()
        stats = memory.get_performance_stats(symbol=symbol, days=days)
        return {"success": True, "data": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/ai/feedback")
def submit_ai_feedback(memory_id: int, feedback: str):
    """提交 AI 分析反馈"""
    try:
        from quant_core.ai.analysis_memory import get_analysis_memory
        memory = get_analysis_memory()
        success = memory.record_feedback(memory_id, feedback)
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 模拟交易 ====================

# 全局模拟交易执行器实例
_simulated_executor = None

def get_simulator() -> SimulatedExecutor:
    """获取模拟交易执行器实例"""
    global _simulated_executor
    if _simulated_executor is None:
        _simulated_executor = SimulatedExecutor()
    return _simulated_executor


class SimulatedOrderRequest(BaseModel):
    symbol: str
    side: str  # "buy" or "sell"
    amount: float
    current_price: float
    order_type: str = "market"  # "market" or "limit"
    limit_price: Optional[float] = None


class SimulatedCloseRequest(BaseModel):
    symbol: str
    current_price: float
    reason: str = ""


class AutoTradingRequest(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: str = "1H"
    confidence_threshold: float = 70.0
    position_size_pct: float = 10.0
    stop_loss_pct: float = 2.0
    take_profit_pct: float = 6.0
    strategy_config: Optional[Dict[str, Any]] = None
    use_atr_stop: bool = False
    atr_multiplier: float = 2.0
    trailing_stop_pct: float = 0.0
    max_drawdown_pct: float = 10.0
    max_daily_loss_pct: float = 5.0


@app.post("/api/v1/simulator/order")
def create_simulated_order(request: SimulatedOrderRequest):
    """创建模拟订单"""
    try:
        simulator = get_simulator()

        if request.order_type == "market":
            order = simulator.create_market_order(
                symbol=request.symbol,
                side=request.side,
                amount=request.amount,
                current_price=request.current_price
            )
        else:
            if request.limit_price is None:
                raise HTTPException(status_code=400, detail="limit_price required for limit orders")
            order = simulator.create_limit_order(
                symbol=request.symbol,
                side=request.side,
                amount=request.amount,
                limit_price=request.limit_price,
                current_price=request.current_price
            )

        return {
            "success": True,
            "order": {
                "id": order.id,
                "symbol": order.symbol,
                "side": order.side,
                "order_type": order.order_type,
                "price": order.price,
                "amount": order.amount,
                "filled_price": order.filled_price,
                "status": order.status,
                "commission": order.commission,
                "slippage": order.slippage,
                "created_at": order.created_at,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/simulator/close")
def close_simulated_position(request: SimulatedCloseRequest):
    """平仓"""
    try:
        simulator = get_simulator()
        trade = simulator.close_position(
            symbol=request.symbol,
            current_price=request.current_price,
            reason=request.reason
        )

        if trade is None:
            raise HTTPException(status_code=400, detail=f"No position for {request.symbol}")

        return {"success": True, "trade": trade}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/simulator/status")
def get_simulator_status():
    """获取模拟交易状态"""
    try:
        simulator = get_simulator()
        return {"success": True, "status": simulator.get_status()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/simulator/reset")
def reset_simulator(initial_balance: float = 10000.0):
    """重置模拟交易"""
    global _simulated_executor
    _simulated_executor = SimulatedExecutor(initial_balance=initial_balance)
    return {"success": True, "message": f"Simulator reset with balance {initial_balance}"}


@app.get("/api/v1/simulator/indicators")
def get_simulator_indicators(symbol: str = "BTC/USDT", timeframe: str = "1H"):
    """获取模拟交易的实时指标"""
    try:
        simulator = get_simulator()
        indicators = simulator.get_indicators(symbol, timeframe)
        if indicators is None:
            raise HTTPException(status_code=400, detail=f"Failed to get indicators for {symbol}")
        return {"success": True, "data": indicators}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/simulator/ai-signal")
def get_simulator_ai_signal(symbol: str = "BTC/USDT", timeframe: str = "1H"):
    """获取AI交易信号"""
    try:
        simulator = get_simulator()
        signal = simulator.generate_ai_signal(symbol, timeframe)
        if signal is None:
            return {"success": True, "signal": None, "message": "No signal generated"}
        return {
            "success": True,
            "signal": {
                "symbol": signal.symbol,
                "action": signal.action,
                "confidence": signal.confidence,
                "entry_price": signal.entry_price,
                "stop_loss": signal.stop_loss,
                "take_profit": signal.take_profit,
                "reason": signal.reason,
                "timeframe": signal.timeframe,
                "timestamp": signal.timestamp,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/simulator/auto-trading/start")
def start_auto_trading(request: AutoTradingRequest):
    """启动自动交易（支持策略配置 + 风控）

    Args:
        symbol: 交易对
        timeframe: 周期
        confidence_threshold: 置信度阈值 (50-95)
        position_size_pct: 仓位比例 (1-100%)
        stop_loss_pct: 止损比例 (%)
        take_profit_pct: 止盈比例 (%)
        strategy_config: 策略配置（可选）
        use_atr_stop: 是否使用ATR动态止损
        atr_multiplier: ATR倍数
        trailing_stop_pct: 追踪止盈比例
        max_drawdown_pct: 最大回撤保护比例
        max_daily_loss_pct: 单日最大亏损比例
    """
    try:
        simulator = get_simulator()
        simulator.start_auto_trading(
            request.symbol,
            request.timeframe,
            request.confidence_threshold,
            request.position_size_pct,
            request.stop_loss_pct,
            request.take_profit_pct,
            request.strategy_config,
            request.use_atr_stop,
            request.atr_multiplier,
            request.trailing_stop_pct,
            request.max_drawdown_pct,
            request.max_daily_loss_pct
        )
        return {"success": True, "message": f"Auto trading started for {request.symbol}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/simulator/auto-trading/stop")
def stop_auto_trading(symbol: str = None):
    """停止自动交易"""
    try:
        simulator = get_simulator()
        simulator.stop_auto_trading(symbol)
        return {"success": True, "message": f"Auto trading stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/simulator/auto-trading/status")
def get_auto_trading_status():
    """获取自动交易状态"""
    try:
        simulator = get_simulator()
        status = simulator.get_status()
        return {
            "success": True,
            "enabled": status.get("auto_trading_enabled", False),
            "symbol": list(simulator._strategy_configs.keys())[0] if simulator._strategy_configs else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/simulator/auto-trading/detail")
def get_auto_trading_detail():
    """获取自动交易详细状态"""
    try:
        simulator = get_simulator()

        # 获取所有策略配置
        configs = {}
        for symbol, config in simulator._strategy_configs.items():
            # 获取当前持仓
            position = simulator.positions.get(symbol)
            current_price = simulator.fetch_latest_price(symbol) if simulator._auto_trading_enabled else 0

            # 计算持仓盈亏
            unrealized_pnl = 0
            if position and config.get("entry_price"):
                entry = config["entry_price"]
                if current_price and current_price > 0:
                    unrealized_pnl = (current_price - entry) / entry * 100

            # 获取交易历史
            trade_history = getattr(simulator, '_trade_history', [])
            symbol_trades = [t for t in trade_history if t.get("symbol") == symbol]

            # 计算统计数据
            wins = sum(1 for t in symbol_trades if t.get("pnl_pct", 0) > 0)
            losses = sum(1 for t in symbol_trades if t.get("pnl_pct", 0) < 0)
            total_pnl = sum(t.get("pnl_pct", 0) for t in symbol_trades)
            win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0

            configs[symbol] = {
                "symbol": symbol,
                "enabled": simulator._auto_trading_enabled,
                "timeframe": config.get("timeframe", "1H"),
                "position_opened": config.get("position_opened", False),
                "entry_price": config.get("entry_price"),
                "current_price": current_price,
                "highest_price": config.get("highest_price_since_entry"),
                "unrealized_pnl_pct": round(unrealized_pnl, 2),
                "strategy_config": config.get("strategy_config", {}),
                "risk_management": {
                    "confidence_threshold": config.get("confidence_threshold", 70),
                    "position_size_pct": config.get("position_size_pct", 10),
                    "stop_loss_pct": config.get("stop_loss_pct", 2),
                    "take_profit_pct": config.get("take_profit_pct", 6),
                    "use_atr_stop": config.get("use_atr_stop", False),
                    "atr_multiplier": config.get("atr_multiplier", 2.0),
                    "trailing_stop_pct": config.get("trailing_stop_pct", 0),
                    "max_drawdown_pct": config.get("max_drawdown_pct", 10),
                    "max_daily_loss_pct": config.get("max_daily_loss_pct", 5),
                },
                "stats": {
                    "total_trades": wins + losses,
                    "wins": wins,
                    "losses": losses,
                    "win_rate": round(win_rate, 2),
                    "total_pnl_pct": round(total_pnl, 2),
                    "daily_pnl": round(config.get("daily_pnl", 0), 2),
                    "total_pnl": round(config.get("total_pnl", 0), 2),
                },
                "recent_trades": symbol_trades[-10:] if symbol_trades else [],  # 最近10笔
            }

        return {
            "success": True,
            "enabled": simulator._auto_trading_enabled,
            "balance": simulator.balance,
            "initial_balance": simulator.initial_balance,
            "equity": simulator.balance,  # 简化计算
            "strategies": configs,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class StrategyDescriptionRequest(BaseModel):
    description: str
    symbol: str = "BTC/USDT"
    timeframe: str = "1H"


class StrategyBacktestRequest(BaseModel):
    """AI策略回测请求"""
    symbol: str = "BTC/USDT"
    timeframe: str = "1H"
    days: int = 30
    initial_balance: float = 10000
    strategy_config: Optional[Dict[str, Any]] = None
    confidence_threshold: float = 70.0
    position_size_pct: float = 10.0
    stop_loss_pct: float = 2.0
    take_profit_pct: float = 6.0
    trailing_stop_pct: float = 0.0
    commission: float = 0.001
    slippage: float = 0.0005


@app.post("/api/v1/strategy/describe")
def describe_strategy(request: StrategyDescriptionRequest):
    """自然语言策略描述转配置 - AI分析描述并推荐阈值"""
    try:
        from quant_core.llm import get_llm_service
        llm = get_llm_service()

        system_prompt = """你是一个专业的量化交易策略分析师。用户用自然语言描述他们的交易策略，你需要分析并返回具体的策略配置参数。

输出格式必须是有效的JSON（不带markdown代码块）：
{
    "indicators": ["rsi", "macd", "boll"],  // 使用的指标列表：rsi, macd, boll, ma, kdj, volume
    "rsi_oversold": 30,    // RSI超卖值（10-40）
    "rsi_overbought": 70,  // RSI超买值（60-90）
    "boll_position_low": 0.2,   // 布林带低位比例（0.05-0.4）
    "boll_position_high": 0.8,  // 布林带高位比例（0.6-0.95）
    "macd_confirm": true,   // 是否需要MACD确认
    "ma_confirmation": true,  // 是否需要均线确认
    "kdj_confirm": false,   // 是否需要KDJ确认
    "volume_confirm": false,  // 是否需要成交量确认
    "confidence_threshold": 70,  // 置信度阈值（50-95）
    "stop_loss_pct": 2.0,   // 止损比例（0.5-10）
    "take_profit_pct": 6.0,  // 止盈比例（1-20）
    "use_atr_stop": false,   // 是否使用ATR动态止损
    "atr_multiplier": 2.0,  // ATR倍数（1-5）
    "trailing_stop_pct": 0,  // 追踪止盈比例（0-10）
    "max_drawdown_pct": 10,  // 最大回撤保护（5-50）
    "max_daily_loss_pct": 5,  // 单日最大亏损（2-20）
    "position_size_pct": 10,  // 仓位比例（1-100）
    "explanation": "解释为什么这样配置"  // 配置理由说明
}

注意：
- 只返回JSON，不要有其他文字
- indicators数组至少包含1个指标
- 所有数值要在合理范围内"""


        user_prompt = f"""请分析以下交易策略描述，并给出具体的策略配置：

交易对: {request.symbol}
周期: {request.timeframe}
策略描述: {request.description}

请根据描述分析并返回配置参数："""

        default_config = {
            "indicators": ["rsi", "macd", "boll"],
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "boll_position_low": 0.2,
            "boll_position_high": 0.8,
            "macd_confirm": True,
            "ma_confirmation": True,
            "kdj_confirm": False,
            "volume_confirm": False,
            "confidence_threshold": 70,
            "stop_loss_pct": 2.0,
            "take_profit_pct": 6.0,
            "use_atr_stop": False,
            "atr_multiplier": 2.0,
            "trailing_stop_pct": 0,
            "max_drawdown_pct": 10,
            "max_daily_loss_pct": 5,
            "position_size_pct": 10,
            "explanation": "使用默认配置"
        }

        result = llm.safe_call_llm(system_prompt, user_prompt, default_config)

        # 确保结果是字典
        if isinstance(result, str):
            import json
            try:
                result = json.loads(result)
            except:
                result = default_config

        return {"success": True, "data": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/strategy/backtest-ai")
def backtest_ai_strategy(request: StrategyBacktestRequest):
    """AI策略回测验证 - 在历史数据上测试AI策略配置"""
    try:
        from quant_core import get_market_data_collector
        import pandas as pd
        import numpy as np

        collector = get_market_data_collector()

        # 获取历史K线数据
        df = collector.collect(request.symbol, request.timeframe, request.days)
        if df.empty or len(df) < 20:
            raise HTTPException(status_code=400, detail=f"Insufficient data for {request.symbol}")

        # 使用客观评分算法（不调用LLM，直接基于指标计算信号）
        strategy_config = request.strategy_config or {}
        rsi_oversold = strategy_config.get("rsi_oversold", 30)
        rsi_overbought = strategy_config.get("rsi_overbought", 70)
        boll_pos_low = strategy_config.get("boll_position_low", 0.2)
        boll_pos_high = strategy_config.get("boll_position_high", 0.8)
        use_macd_confirm = strategy_config.get("macd_confirm", True)

        # 模拟交易
        balance = request.initial_balance
        position = None
        position_size = request.position_size_pct
        trades = []
        equity_curve = []
        wins = 0
        losses = 0

        commission_rate = request.commission
        slippage_rate = request.slippage

        # 逐根K线回测
        for i in range(20, len(df)):
            current_df = df.iloc[:i+1].copy()
            current_price = float(df['close'].iloc[i])

            # 计算当前K线的指标
            close = df['close'].values
            high = df['high'].values
            low = df['low'].values
            volume = df['volume'].values if 'volume' in df else [0] * len(df)

            # RSI
            delta = pd.Series(close).diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
            rs = gain / loss
            rsi = float((100 - (100 / (1 + rs))).iloc[-1]) if len(df) >= 14 else 50

            # MACD
            ema12 = pd.Series(close).ewm(span=12, adjust=False).mean().iloc[-1]
            ema26 = pd.Series(close).ewm(span=26, adjust=False).mean().iloc[-1]
            macd = float(ema12 - ema26)
            macd_ema = pd.Series(close).ewm(span=9, adjust=False).mean().iloc[-1]
            macd_signal = float(macd_ema - ema26)
            macd_histogram = macd - macd_signal

            # 布林带
            boll_mid = float(pd.Series(close).rolling(20).mean().iloc[-1]) if len(df) >= 20 else current_price
            boll_std = float(pd.Series(close).rolling(20).std().iloc[-1]) if len(df) >= 20 else current_price * 0.02
            boll_upper = boll_mid + 2 * boll_std
            boll_lower = boll_mid - 2 * boll_std
            boll_pos = (current_price - boll_lower) / (boll_upper - boll_lower) if boll_upper != boll_lower else 0.5

            # ATR
            close_shift = pd.Series(close).shift(1)
            tr1 = pd.Series(high) - pd.Series(low)
            tr2 = abs(pd.Series(high) - close_shift)
            tr3 = abs(pd.Series(low) - close_shift)
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = float(tr.rolling(14).mean().iloc[-1]) if len(df) >= 14 else boll_std

            # ADX (趋势强度)
            high_diff = pd.Series(high) - pd.Series(high).shift(1)
            low_diff = pd.Series(low).shift(1) - pd.Series(low)
            plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
            minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)
            plus_di = 100 * (plus_dm.ewm(alpha=1/14).mean() / atr) if atr > 0 else 0
            minus_di = 100 * (minus_dm.ewm(alpha=1/14).mean() / atr) if atr > 0 else 0
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di).iloc[-1] > 0 else 0
            adx = float(dx.ewm(alpha=1/14).mean().iloc[-1]) if len(df) >= 14 else 25

            # 波动率
            volatility = boll_std / boll_mid * 100 if boll_mid > 0 else 2

            # KDJ
            lowest_low = pd.Series(low).rolling(9).min().iloc[-1] if len(df) >= 9 else current_price
            highest_high = pd.Series(high).rolling(9).max().iloc[-1] if len(df) >= 9 else current_price
            rsv = 100 * (close[-1] - lowest_low) / (highest_high - lowest_low) if highest_high != lowest_low else 50
            kdj_k = float(rsv * 2/3 + 50 * 1/3) if len(df) >= 9 else 50
            kdj_d = float(kdj_k * 2/3 + 50 * 1/3) if len(df) >= 9 else 50
            kdj_j = float(3 * kdj_k - 2 * kdj_d) if len(df) >= 9 else 50

            # 成交量
            volume_ma = float(pd.Series(volume).rolling(20).mean().iloc[-1]) if len(df) >= 20 else float(volume[-1])
            volume_ratio = float(volume[-1] / volume_ma) if volume_ma > 0 else 1

            # === 市场状态感知 ===
            is_strong_trend = adx > 25
            is_very_strong_trend = adx > 40

            # 波动率自适应 RSI 阈值
            vol_adjustment = min(max((volatility - 2) * 2, 0), 15)
            adj_rsi_oversold = max(rsi_oversold - vol_adjustment, 20)
            adj_rsi_overbought = min(rsi_overbought + vol_adjustment, 80)

            # 根据趋势强度调整权重
            if is_very_strong_trend:
                rsi_weight, macd_weight, boll_weight, kdj_weight = 10, 30, 7, 3
            elif is_strong_trend:
                rsi_weight, macd_weight, boll_weight, kdj_weight = 20, 25, 12, 8
            else:
                rsi_weight, macd_weight, boll_weight, kdj_weight = 30, 15, 20, 15

            # 计算客观评分
            score = 0
            weight = 0

            # RSI评分
            if rsi < adj_rsi_oversold:
                oversold_depth = (adj_rsi_oversold - rsi) / adj_rsi_oversold
                score += 20 * (1 + oversold_depth * 2)
            elif rsi > adj_rsi_overbought:
                overbought_depth = (rsi - adj_rsi_overbought) / (100 - adj_rsi_overbought)
                score -= 20 * (1 + overbought_depth * 2)
            else:
                mid_rsi = (adj_rsi_oversold + adj_rsi_overbought) / 2
                normalized = (rsi - mid_rsi) / (adj_rsi_overbought - adj_rsi_oversold)
                score += (1 / (1 + 2.718 ** (-normalized * 5)) - 0.5) * 10
            weight += rsi_weight

            # MACD评分
            if use_macd_confirm:
                macd_on_zero = 1 if (macd > 0 and macd_signal > 0) else 0.5 if macd > 0 else 0
                if macd_histogram > 0:
                    score += 15 * (1 + macd_on_zero * 0.5)
                else:
                    score -= 15 * (1 + (1 - macd_on_zero) * 0.5)
                weight += macd_weight
            else:
                if macd_histogram > 0:
                    score += 8
                else:
                    score -= 8
                weight += macd_weight * 0.6

            # 布林带评分
            if boll_pos < boll_pos_low:
                depth = (boll_pos_low - boll_pos) / boll_pos_low
                boll_score = 10 * (1 + depth)
                if not is_strong_trend:
                    boll_score *= 1.2
                score += boll_score
            elif boll_pos > boll_pos_high:
                depth = (boll_pos - boll_pos_high) / (1 - boll_pos_high)
                boll_score = 10 * (1 + depth)
                if not is_strong_trend:
                    boll_score *= 1.2
                score -= boll_score
            weight += boll_weight

            # KDJ评分
            kdj_score = 0
            if kdj_k > kdj_d and kdj_j < 30:
                kdj_score = 8
            elif kdj_k < kdj_d and kdj_j > 70:
                kdj_score = -8
            elif kdj_k > kdj_d:
                kdj_score = 3
            elif kdj_k < kdj_d:
                kdj_score = -3
            if is_very_strong_trend:
                kdj_score *= 0.3
            elif is_strong_trend:
                kdj_score *= 0.6
            score += kdj_score
            weight += kdj_weight

            # 成交量评分
            if volume_ratio >= 1.5:
                if score > 0:
                    score += 5
                elif score < 0:
                    score -= 5
                else:
                    score += 2
            elif volume_ratio < 0.5:
                score -= 2
            weight += 10

            final_score = (score / weight * 100) if weight > 0 else 0
            confidence = min(95, max(50, 50 + final_score * 0.5))

            # 更新持仓盈亏
            if position:
                if position['side'] == 'long':
                    position['unrealized_pnl'] = (current_price - position['entry_price']) / position['entry_price'] * 100
                else:
                    position['unrealized_pnl'] = (position['entry_price'] - current_price) / position['entry_price'] * 100

            # 止损/止盈检查
            if position:
                pnl_pct = position['unrealized_pnl']
                sl = request.stop_loss_pct
                tp = request.take_profit_pct

                # 追踪止盈
                trailing_triggered = False
                if request.trailing_stop_pct > 0 and position.get('highest_price'):
                    trail_price = position['highest_price'] * (1 - request.trailing_stop_pct / 100)
                    if current_price <= trail_price and pnl_pct > tp:
                        trailing_triggered = True

                if pnl_pct <= -sl or pnl_pct >= tp or trailing_triggered:
                    # 平仓
                    reason = "stop_loss" if pnl_pct <= -sl else ("trailing_stop" if trailing_triggered else "take_profit")
                    pnl = balance * (position_size / 100) * (pnl_pct / 100)
                    commission = balance * (position_size / 100) * commission_rate
                    net_pnl = pnl - commission

                    balance += net_pnl
                    trades.append({
                        "entry_price": position['entry_price'],
                        "exit_price": current_price,
                        "pnl_pct": pnl_pct,
                        "pnl": net_pnl,
                        "reason": reason,
                        "exit_time": df.index[i].isoformat() if hasattr(df.index[i], 'isoformat') else str(df.index[i])
                    })

                    if net_pnl > 0:
                        wins += 1
                    else:
                        losses += 1

                    position = None

            # 追踪最高价（用于追踪止盈）
            if position:
                if not position.get('highest_price') or current_price > position['highest_price']:
                    position['highest_price'] = current_price

            # 信号检查并执行交易
            if not position and confidence >= request.confidence_threshold:
                if final_score > 10:  # 买入信号
                    entry_price = current_price * (1 + slippage_rate)
                    commission = balance * (position_size / 100) * commission_rate
                    balance -= commission

                    position = {
                        'side': 'long',
                        'entry_price': entry_price,
                        'highest_price': entry_price,
                        'unrealized_pnl': 0
                    }

            # 记录权益
            equity = balance
            if position:
                equity += balance * (position_size / 100) * (position['unrealized_pnl'] / 100)
            equity_curve.append({
                "time": df.index[i].isoformat() if hasattr(df.index[i], 'isoformat') else str(df.index[i]),
                "equity": round(equity, 2)
            })

        # 计算统计结果
        total_trades = wins + losses
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

        total_pnl = balance - request.initial_balance
        total_pnl_pct = (total_pnl / request.initial_balance * 100)

        # 计算最大回撤
        max_drawdown = 0
        peak = request.initial_balance
        for e in equity_curve:
            if e['equity'] > peak:
                peak = e['equity']
            drawdown = (peak - e['equity']) / peak * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # 计算夏普比率
        if len(equity_curve) > 1:
            returns = []
            for i in range(1, len(equity_curve)):
                ret = (equity_curve[i]['equity'] - equity_curve[i-1]['equity']) / equity_curve[i-1]['equity']
                returns.append(ret)
            if returns:
                avg_return = np.mean(returns) * 100
                std_return = np.std(returns) * 100
                sharpe_ratio = (avg_return / std_return * 10) if std_return > 0 else 0
            else:
                sharpe_ratio = 0
        else:
            sharpe_ratio = 0

        # 盈利/亏损交易
        profitable_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] <= 0]
        avg_win = sum(t['pnl'] for t in profitable_trades) / len(profitable_trades) if profitable_trades else 0
        avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0

        result = {
            "summary": {
                "total_trades": total_trades,
                "wins": wins,
                "losses": losses,
                "win_rate": round(win_rate, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_pct": round(total_pnl_pct, 2),
                "max_drawdown": round(max_drawdown, 2),
                "sharpe_ratio": round(sharpe_ratio, 2),
                "final_balance": round(balance, 2),
                "avg_win": round(avg_win, 2),
                "avg_loss": round(avg_loss, 2),
            },
            "trades": trades[-20:],
            "equity_curve": equity_curve[-100:],
        }

        return {"success": True, "data": result}

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 策略快照 ====================

@app.post("/api/v1/strategy/snapshot")
def get_strategy_snapshot_resolved(strategy: Dict[str, Any]):
    """将策略配置解析为回测就绪格式"""
    try:
        snapshot = get_strategy_snapshot()
        resolved = snapshot.resolve(strategy)
        return {"success": True, "data": resolved}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== WebSocket 通知 ====================

@app.websocket("/ws/signals")
async def websocket_signals(websocket: WebSocket):
    """WebSocket 实时信号推送"""
    ws_manager = get_websocket_manager()

    await websocket.accept()
    await ws_manager.connect(websocket)

    try:
        while True:
            # 每 30 秒发送一次 ping 保持连接
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # 收到消息可以处理，如订阅特定 symbol
            except asyncio.TimeoutError:
                # 发送 ping 保持连接
                await websocket.send_json({"type": "ping"})
    except Exception:
        pass
    finally:
        await ws_manager.disconnect(websocket)


# ==================== 通知相关 ====================

@app.get("/api/v1/notifications")
def get_notifications(limit: int = 20, unread_only: bool = False):
    """获取通知列表"""
    try:
        db = get_database()
        notifications = db.get_notifications(limit=limit, unread_only=unread_only)
        unread_count = db.get_unread_count()
        return {
            "success": True,
            "data": notifications,
            "unread_count": unread_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int):
    """标记通知为已读"""
    try:
        db = get_database()
        db.mark_notification_read(notification_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/notifications/read-all")
def mark_all_read():
    """标记所有通知为已读"""
    try:
        db = get_database()
        db.mark_all_notifications_read()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/notifications/clear")
def clear_old_notifications(before_hours: int = 24):
    """清理旧通知"""
    try:
        db = get_database()
        deleted = db.clear_notifications(before_hours=before_hours)
        return {"success": True, "deleted": deleted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/notifications/test")
def create_test_notification():
    """创建测试通知"""
    try:
        db = get_database()
        notification_id = db.save_notification(
            notification_type="test",
            symbol="BTC/USDT",
            title="测试通知",
            message="这是一条测试通知，用于验证通知功能是否正常。",
            payload={"test": True}
        )
        return {"success": True, "id": notification_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 持仓监控 ====================

@app.post("/api/v1/monitor/start")
def start_portfolio_monitor():
    """启动持仓监控服务"""
    try:
        from quant_core.services import start_monitor
        start_monitor()
        return {"success": True, "message": "监控服务已启动"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/monitor/stop")
def stop_portfolio_monitor():
    """停止持仓监控服务"""
    try:
        from quant_core.services import stop_monitor
        stop_monitor()
        return {"success": True, "message": "监控服务已停止"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/monitor/add")
def add_monitor(symbol: str, entry_price: float, side: str,
                stop_loss_pct: float = 2.0, take_profit_pct: float = 6.0):
    """添加监控持仓"""
    try:
        from quant_core.services import get_portfolio_monitor
        monitor = get_portfolio_monitor()
        monitor.add_monitor(symbol, entry_price, side, stop_loss_pct, take_profit_pct)
        return {"success": True, "message": f"已添加 {symbol} 监控"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/monitor/{symbol}")
def remove_monitor(symbol: str):
    """移除监控持仓"""
    try:
        from quant_core.services import get_portfolio_monitor
        monitor = get_portfolio_monitor()
        monitor.remove_monitor(symbol)
        return {"success": True, "message": f"已移除 {symbol} 监控"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 数据相关 ====================

@app.get("/api/v1/market/ticker")
def get_ticker(symbol: str):
    """获取行情"""
    try:
        from quant_core import get_market_data_collector
        collector = get_market_data_collector()
        ticker = collector.get_market_info(symbol)
        return {"success": True, "data": ticker}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/market/klines")
def get_klines(symbol: str, timeframe: str = "1D", days: int = 30):
    """获取K线数据"""
    try:
        from quant_core import get_market_data_collector
        collector = get_market_data_collector()
        df = collector.collect(symbol, timeframe, days)

        # 重置索引，确保时间戳在字段里
        df = df.reset_index()

        # 转换时间戳为毫秒 (pandas使用microseconds，需要//1000)
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp']).astype('int64') // 1000
        elif 'index' in df.columns:
            df['timestamp'] = pd.to_datetime(df['index']).astype('int64') // 1000

        return {
            "success": True,
            "data": safe_json(df.tail(100).to_dict(orient="records"))
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 启动函数 ====================

def run_server(host: str = "0.0.0.0", port: int = 8000):
    """启动服务器"""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
