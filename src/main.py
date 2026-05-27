#!/usr/bin/env python3
"""
QuantCore CLI - 量化分析命令行工具
"""
import argparse
import sys
import json
from typing import Optional

from quant_core import (
    QuantEngine,
    get_market_data_collector,
    calculate_indicator,
    get_llm_service,
    launch_ui,
)
from quant_core.backtest import run_backtest


def cmd_analyze(args):
    """分析命令"""
    engine = QuantEngine(testnet=args.testnet)
    result = engine.analyze(args.symbol, args.timeframe, args.days)

    if "error" in result:
        print(f"Error: {result['error']}")
        return 1

    # 输出分析报告
    report = engine.analyzer.generate_report(result)
    print(report)
    return 0


def cmd_backtest(args):
    """回测命令"""
    engine = QuantEngine(testnet=args.testnet)

    # 构建策略
    strategy = {
        "name": args.strategy_name or "默认策略",
        "indicators": [{"name": "RSI", "params": {"period": 14}}],
        "risk_management": {
            "stop_loss_pct": args.stop_loss or 2.0,
            "take_profit_pct": args.take_profit or 6.0,
            "trailing_stop": args.trailing_stop,
            "trailing_pct": args.trailing_pct or 1.5
        },
        "position_size": {"method": "fixed", "value": args.position_size or 100},
        "commission": args.commission or 0.001,
        "slippage": args.slippage or 0.0005,
        "leverage": args.leverage or 1.0
    }

    result = engine.backtest(args.symbol, strategy, args.timeframe, args.days, args.initial_balance)

    if "error" in result:
        print(f"Error: {result['error']}")
        return 1

    print(f"\n{'='*50}")
    print(f"  Backtest Results - {args.symbol}")
    print(f"{'='*50}")
    print(f"\n📊 基本信息")
    print(f"  交易周期: {args.days} days ({args.timeframe})")
    print(f"  初始资金: ${result['initial_balance']:.2f}")
    print(f"  最终资金: ${result['final_balance']:.2f}")
    print(f"  总收益: ${result['total_pnl']:.2f} ({result['total_pnl_pct']:+.2f}%)")

    print(f"\n📈 交易统计")
    print(f"  总交易次数: {result['total_trades']}")
    print(f"  盈利次数: {result['win_count']}")
    print(f"  亏损次数: {result['loss_count']}")
    print(f"  胜率: {result['win_rate']:.2f}%")
    print(f"  盈亏比: {result['profit_factor']:.2f}")
    print(f"  平均盈利: ${result['avg_win']:.2f}")
    print(f"  平均亏损: ${result['avg_loss']:.2f}")
    print(f"  最大单笔盈利: ${result['best_trade']:.2f}")
    print(f"  最大单笔亏损: ${result['worst_trade']:.2f}")

    print(f"\n📉 风险指标")
    print(f"  最大回撤: ${result['max_drawdown']:.2f} ({result['max_drawdown_pct']:.2f}%)")
    print(f"  夏普比率: {result['sharpe_ratio']:.2f}")
    print(f"  索提诺比率: {result['sortino_ratio']:.2f}")
    print(f"  最大连续盈利: {result['max_consecutive_wins']}次")
    print(f"  最大连续亏损: {result['max_consecutive_losses']}次")

    print(f"\n💰 成本统计")
    print(f"  手续费: ${result['total_commission']:.2f}")
    print(f"  滑点: ${result['total_slippage']:.2f}")

    if args.verbose and result.get("trades"):
        print(f"\n{'='*50}")
        print(f"  Trade History")
        print(f"{'='*50}")
        print(f"{'Entry Time':<20} {'Exit Time':<20} {'Side':<6} {'P&L':>12} {'%':>8}")
        print(f"{'-'*66}")
        for trade in result["trades"]:
            print(f"{trade['entry_time'][:19]:<20} {trade['exit_time'][:19]:<20} {trade['side']:<6} ${trade['pnl']:>10.2f} {trade['pnl_pct']:>7.2f}%")

    # 保存权益曲线
    if args.save_equity and result.get("equity_curve"):
        equity_file = f"equity_{args.symbol.replace('/', '_')}_{args.timeframe}.json"
        with open(equity_file, 'w') as f:
            json.dump(result["equity_curve"], f, indent=2)
        print(f"\n💾 权益曲线已保存: {equity_file}")

    # 保存到数据库
    if args.save_db:
        run_id = engine.save_backtest(
            symbol=args.symbol,
            timeframe=args.timeframe,
            result=result,
            strategy_name=args.strategy_name or "默认策略",
            config={
                "initial_balance": args.initial_balance,
                "commission": args.commission,
                "slippage": args.slippage,
                "leverage": args.leverage
            }
        )
        print(f"\n💾 回测已保存到数据库 (ID: {run_id})")

    return 0


def cmd_strategy(args):
    """策略编译命令"""
    engine = QuantEngine(testnet=args.testnet)

    market_info = engine.market_collector.get_market_info(args.symbol)
    compiler = engine.strategy_compiler

    result = compiler.compile_strategy(args.description, market_info)

    print(f"\n=== Compiled Strategy ===")
    print(f"Name: {result.get('name', 'N/A')}")
    print(f"\nEntry Conditions:")
    for cond in result.get("entry_conditions", []):
        print(f"  - {cond}")
    print(f"\nExit Conditions:")
    for cond in result.get("exit_conditions", []):
        print(f"  - {cond}")
    print(f"\nIndicators:")
    for ind in result.get("indicators", []):
        print(f"  - {ind['name']}: {ind.get('params', {})}")
    print(f"\nRisk Management:")
    rm = result.get("risk_management", {})
    print(f"  Stop Loss: {rm.get('stop_loss_pct', 0)}%")
    print(f"  Take Profit: {rm.get('take_profit_pct', 0)}%")
    print(f"  Trailing Stop: {rm.get('trailing_stop', False)}")

    # 如果指定了--backtest，则运行回测
    if args.backtest:
        bt_result = engine.backtest(args.symbol, result, args.timeframe, args.days, args.initial_balance)
        if "error" not in bt_result:
            print(f"\n=== Backtest Results ===")
            print(f"Win Rate: {bt_result['win_rate']:.2f}%")
            print(f"Total P&L: ${bt_result['total_pnl']:.2f} ({bt_result['total_pnl_pct']:.2f}%)")

    return 0


def cmd_trade(args):
    """交易命令"""
    engine = QuantEngine(testnet=args.testnet)

    if args.action == "balance":
        balance = engine.executor.get_balance()
        print(json.dumps(balance, indent=2))
        return 0

    if args.action == "positions":
        positions = engine.get_positions()
        print(json.dumps(positions, indent=2))
        return 0

    if args.action == "orders":
        orders = engine.get_orders(args.symbol, limit=50)
        print(json.dumps(orders, indent=2, default=str))
        return 0

    # 执行交易
    result = engine.execute_trade(
        args.symbol,
        args.action,
        args.amount,
        args.order_type or "market",
        args.price
    )

    print(json.dumps(result, indent=2))
    return 0 if result.get("success") else 1


def cmd_indicator(args):
    """技术指标命令"""
    collector = get_market_data_collector()
    df = collector.collect(args.symbol, args.timeframe, args.days)

    if df.empty:
        print(f"Error: No data for {args.symbol}")
        return 1

    # 解析params字符串，如 "period=14,fast=12"
    params = {}
    if args.params:
        for pair in args.params.split(","):
            if "=" in pair:
                key, value = pair.split("=", 1)
                try:
                    params[key.strip()] = int(value.strip())
                except ValueError:
                    try:
                        params[key.strip()] = float(value.strip())
                    except ValueError:
                        params[key.strip()] = value.strip()

    result_df = calculate_indicator(df, args.indicator.upper(), **params)

    # 输出最后几行
    print(f"\n=== {args.indicator.upper()} Indicator for {args.symbol} ===")
    print(result_df.tail(10).to_string())

    return 0


def cmd_history(args):
    """回测历史命令"""
    engine = QuantEngine(testnet=args.testnet)

    if args.show_detail:
        # 显示详情
        detail = engine.get_backtest_detail(args.run_id)
        if not detail:
            print(f"Backtest run {args.run_id} not found")
            return 1

        print(f"\n=== Backtest Run #{args.run_id} ===")
        print(f"Symbol: {detail['symbol']}")
        print(f"Timeframe: {detail['timeframe']}")
        print(f"Strategy: {detail['strategy_name']}")
        print(f"Initial: ${detail['initial_balance']:.2f} -> Final: ${detail['final_balance']:.2f}")
        print(f"P&L: ${detail['total_pnl']:.2f} ({detail['total_pnl_pct']:+.2f}%)")
        print(f"Win Rate: {detail['win_rate']:.2f}%")
        print(f"Max Drawdown: {detail['max_drawdown_pct']:.2f}%")
        print(f"Sharpe: {detail['sharpe_ratio']:.2f}")
        print(f"Total Trades: {detail['total_trades']}")

        if detail.get('trades'):
            print(f"\n--- Trades ({len(detail['trades'])}) ---")
            for t in detail['trades']:
                print(f"{t['entry_time'][:19]} -> {t['exit_time'][:19]} | {t['side']:5} | ${t['pnl']:>10.2f} ({t['pnl_pct']:>7.2f}%)")

        return 0

    # 显示列表
    history = engine.get_backtest_history(symbol=args.symbol, limit=args.limit)

    if not history:
        print("No backtest history found")
        return 0

    print(f"\n{'='*80}")
    print(f"  Backtest History")
    print(f"{'='*80}")
    print(f"{'ID':<5} {'Symbol':<12} {'Timeframe':<8} {'Strategy':<20} {'P&L':>12} {'Win%':>8} {'Date':<20}")
    print(f"{'-'*80}")
    for run in history:
        date = run['created_at'][:19] if run.get('created_at') else 'N/A'
        strategy = run.get('strategy_name', '')[:18]
        print(f"{run['id']:<5} {run['symbol']:<12} {run['timeframe']:<8} {strategy:<20} ${run['total_pnl']:>10.2f} {run['win_rate']:>7.2f}% {date:<20}")

    print(f"\nTotal: {len(history)} runs")
    return 0


def cmd_script(args):
    """自定义指标脚本命令"""
    from quant_core.strategy.custom import get_custom_engine, CustomIndicatorEngine
    from quant_core.backtest import BacktestEngine, BacktestConfig

    collector = get_market_data_collector()
    df = collector.collect(args.symbol, args.timeframe, args.days)

    if df.empty:
        print(f"Error: No data for {args.symbol}")
        return 1

    engine = get_custom_engine()

    if args.example:
        # 显示示例代码
        code = CustomIndicatorEngine.get_example_code(args.example)
        print(f"\n=== Example: {args.example.upper()} ===")
        print(code)
        return 0

    if args.validate:
        # 验证代码
        is_valid, error = engine.validate_code(args.code)
        if is_valid:
            print("✅ Code is valid")
        else:
            print(f"❌ Validation failed: {error}")
        return 0 if is_valid else 1

    # 执行指标代码
    result = engine.execute(args.code, df)

    if "error" in result:
        print(f"❌ Error executing code: {result['error']}")
        return 1

    print(f"\n=== Custom Indicator: {result.get('name', 'N/A')} ===")

    # 显示plots
    if result.get("plots"):
        print("\nPlots:")
        for plot in result["plots"]:
            print(f"  - {plot.get('name', 'N/A')}: {len(plot.get('data', []))} points")

    # 显示信号统计
    signals = result.get("signals", [])
    for sig in signals:
        sig_type = sig.get("type", "unknown")
        data = sig.get("data", [])
        count = sum(1 for x in data if x is not None)
        print(f"  {sig_type}: {count} signals")

    # 如果指定了--backtest，运行回测
    if args.backtest:
        print("\n--- Running Backtest ---")

        # 提取信号
        signals_df = engine.extract_signals(result)
        if not signals_df.empty:
            df = df.join(signals_df)

        # 定义信号函数
        def signal_func(kdf, ind_df, i):
            if "buy" in kdf.columns and kdf["buy"].iloc[i]:
                return "buy"
            if "sell" in kdf.columns and kdf["sell"].iloc[i]:
                return "sell"
            return None

        strategy = {
            "name": result.get("name", "Custom"),
            "indicators": [],
            "risk_management": {
                "stop_loss_pct": args.stop_loss or 2.0,
                "take_profit_pct": args.take_profit or 6.0,
                "trailing_stop": args.trailing_stop,
                "trailing_pct": args.trailing_pct or 1.5
            },
            "position_size": {"method": "fixed", "value": args.position_size or 100},
            "commission": args.commission or 0.001,
            "slippage": args.slippage or 0.0005
        }

        cfg = BacktestConfig(
            initial_balance=args.initial_balance or 10000,
            commission=strategy["commission"],
            slippage=strategy["slippage"]
        )
        bt_engine = BacktestEngine(config=cfg)
        bt_result = bt_engine.run(df, strategy, df, signal_func=signal_func)

        print(f"\n=== Backtest Results ===")
        print(f"Total Trades: {bt_result['total_trades']}")
        print(f"Win Rate: {bt_result['win_rate']:.2f}%")
        print(f"P&L: ${bt_result['total_pnl']:.2f} ({bt_result['total_pnl_pct']:+.2f}%)")
        print(f"Max Drawdown: {bt_result['max_drawdown_pct']:.2f}%")

        if args.save_db:
            run_id = engine.save_backtest(
                symbol=args.symbol,
                timeframe=args.timeframe,
                result=bt_result,
                strategy_name=result.get("name", "Custom"),
                config=strategy
            )
            print(f"\n💾 Saved to database (ID: {run_id})")

    return 0


def main():
    parser = argparse.ArgumentParser(description="QuantCore - AI Quantitative Trading")
    parser.add_argument("--testnet", action="store_true", default=True, help="Use testnet (default: True)")
    parser.add_argument("--live", dest="testnet", action="store_false", help="Use live trading")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # analyze command
    p_analyze = subparsers.add_parser("analyze", help="Analyze a trading pair")
    p_analyze.add_argument("-s", "--symbol", required=True, help="Trading pair (e.g., BTC/USDT)")
    p_analyze.add_argument("-t", "--timeframe", default="1h", help="Timeframe (default: 1h)")
    p_analyze.add_argument("-d", "--days", type=int, default=30, help="Analysis period in days (default: 30)")
    p_analyze.set_defaults(func=cmd_analyze)

    # backtest command
    p_backtest = subparsers.add_parser("backtest", help="Backtest a strategy")
    p_backtest.add_argument("-s", "--symbol", required=True, help="Trading pair")
    p_backtest.add_argument("-t", "--timeframe", default="1h", help="Timeframe")
    p_backtest.add_argument("-d", "--days", type=int, default=30, help="Backtest period")
    p_backtest.add_argument("--initial-balance", type=float, default=10000, help="Initial balance")
    p_backtest.add_argument("--stop-loss", type=float, help="Stop loss percentage")
    p_backtest.add_argument("--take-profit", type=float, help="Take profit percentage")
    p_backtest.add_argument("--trailing-stop", action="store_true", help="Enable trailing stop")
    p_backtest.add_argument("--trailing-pct", type=float, help="Trailing stop percentage")
    p_backtest.add_argument("--position-size", type=float, help="Position size in quote currency")
    p_backtest.add_argument("--strategy-name", help="Strategy name")
    p_backtest.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    p_backtest.add_argument("--commission", type=float, default=0.001, help="Commission rate (default: 0.001 = 0.1%%)")
    p_backtest.add_argument("--slippage", type=float, default=0.0005, help="Slippage rate (default: 0.0005 = 0.05%%)")
    p_backtest.add_argument("--leverage", type=float, default=1.0, help="Leverage (default: 1.0)")
    p_backtest.add_argument("--save-equity", action="store_true", help="Save equity curve to JSON")
    p_backtest.add_argument("--save-db", action="store_true", help="Save backtest to database")
    p_backtest.set_defaults(func=cmd_backtest)

    # strategy command
    p_strategy = subparsers.add_parser("strategy", help="Compile and backtest a strategy")
    p_strategy.add_argument("-s", "--symbol", required=True, help="Trading pair")
    p_strategy.add_argument("description", help="Strategy description")
    p_strategy.add_argument("-t", "--timeframe", default="1h", help="Timeframe")
    p_strategy.add_argument("-d", "--days", type=int, default=30, help="Backtest period")
    p_strategy.add_argument("--initial-balance", type=float, default=10000, help="Initial balance")
    p_strategy.add_argument("--backtest", action="store_true", help="Run backtest after compiling")
    p_strategy.set_defaults(func=cmd_strategy)

    # trade command
    p_trade = subparsers.add_parser("trade", help="Execute trades")
    p_trade.add_argument("-s", "--symbol", help="Trading pair")
    p_trade.add_argument("action", choices=["buy", "sell", "balance", "positions", "orders"], help="Trade action")
    p_trade.add_argument("--amount", type=float, help="Amount to trade")
    p_trade.add_argument("--order-type", choices=["market", "limit"], help="Order type")
    p_trade.add_argument("--price", type=float, help="Limit price")
    p_trade.set_defaults(func=cmd_trade)

    # indicator command
    p_indicator = subparsers.add_parser("indicator", help="Calculate technical indicators")
    p_indicator.add_argument("-s", "--symbol", required=True, help="Trading pair")
    p_indicator.add_argument("-i", "--indicator", required=True, help="Indicator name (RSI, MACD, EMA, etc.)")
    p_indicator.add_argument("-t", "--timeframe", default="1h", help="Timeframe")
    p_indicator.add_argument("-d", "--days", type=int, default=30, help="Period")
    p_indicator.add_argument("-p", "--params", help="Indicator parameters (e.g., period=14)")
    p_indicator.set_defaults(func=cmd_indicator)

    # history command
    p_history = subparsers.add_parser("history", help="View backtest history")
    p_history.add_argument("-s", "--symbol", help="Filter by symbol (optional)")
    p_history.add_argument("-l", "--limit", type=int, default=50, help="Limit results")
    p_history.add_argument("--detail", dest="show_detail", action="store_true", help="Show detailed report")
    p_history.add_argument("--id", type=int, dest="run_id", help="Backtest run ID for detail view")
    p_history.set_defaults(func=cmd_history)

    # script command
    p_script = subparsers.add_parser("script", help="Run custom indicator script")
    p_script.add_argument("-s", "--symbol", required=True, help="Trading pair")
    p_script.add_argument("code", help="Python code for custom indicator")
    p_script.add_argument("-t", "--timeframe", default="1h", help="Timeframe")
    p_script.add_argument("-d", "--days", type=int, default=30, help="Period")
    p_script.add_argument("--example", choices=["rsi", "macd", "boll"], help="Show example code")
    p_script.add_argument("--validate", action="store_true", help="Validate code only")
    p_script.add_argument("--backtest", action="store_true", help="Run backtest")
    p_script.add_argument("--initial-balance", type=float, default=10000, help="Initial balance")
    p_script.add_argument("--stop-loss", type=float, help="Stop loss percentage")
    p_script.add_argument("--take-profit", type=float, help="Take profit percentage")
    p_script.add_argument("--trailing-stop", action="store_true", help="Enable trailing stop")
    p_script.add_argument("--trailing-pct", type=float, help="Trailing stop percentage")
    p_script.add_argument("--position-size", type=float, help="Position size")
    p_script.add_argument("--commission", type=float, default=0.001, help="Commission rate")
    p_script.add_argument("--slippage", type=float, default=0.0005, help="Slippage rate")
    p_script.add_argument("--save-db", action="store_true", help="Save to database")
    p_script.set_defaults(func=cmd_script)

    # server command
    p_server = subparsers.add_parser("server", help="Launch API server with web UI")
    p_server.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    p_server.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")

    def cmd_server(args):
        from server import run_server
        print(f"Starting QuantCore server at http://{args.host}:{args.port}")
        print(f"Web UI: http://{args.host}:{args.port}")
        print(f"API Docs: http://{args.host}:{args.port}/docs")
        run_server(host=args.host, port=args.port)

    p_server.set_defaults(func=cmd_server)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
