"""
QuantCore Gradio Web界面
"""
import gradio as gr
import json
from typing import Dict, Any

from quant_core import (
    QuantEngine,
    get_market_data_collector,
    calculate_indicator,
    get_database,
)
from quant_core.strategy.custom import get_custom_engine, CustomIndicatorEngine


def analyze_token(symbol: str, timeframe: str, days: int) -> tuple:
    """分析交易对"""
    try:
        engine = QuantEngine(testnet=True)
        result = engine.analyze(symbol, timeframe, days)

        if "error" in result:
            return f"Error: {result['error']}", "", "", ""

        report = engine.analyzer.generate_report(result)
        indicators = result.get("indicators", {})

        # 格式化指标
        ind_str = f"RSI: {indicators.get('rsi', 'N/A'):.2f}\n" if indicators.get('rsi') else ""
        ind_str += f"MACD: {indicators.get('macd', 'N/A'):.4f}\n" if indicators.get('macd') else ""
        ind_str += f"BOLL: {indicators.get('boll_middle', 'N/A'):.2f}\n" if indicators.get('boll_middle') else ""
        ind_str += f"ATR: {indicators.get('atr', 'N/A'):.4f}\n" if indicators.get('atr') else ""

        summary = f"**Trend**: {result.get('trend', 'N/A')} ({result.get('trend_strength', 0)*100:.0f}%)\n"
        summary += f"**Risk**: {result.get('risk_level', 'N/A').upper()}\n"
        summary += f"**Recommendation**: {result.get('recommendation', 'N/A')}"

        return report, ind_str, summary, ""
    except Exception as e:
        return f"Error: {str(e)}", "", "", ""


def run_backtest_ui(symbol: str, timeframe: str, days: int,
                    initial_balance: float, stop_loss: float, take_profit: float,
                    commission: float, use_rsi: bool, use_macd: bool) -> str:
    """运行回测"""
    try:
        engine = QuantEngine(testnet=True)

        # 构建策略
        indicators = []
        if use_rsi:
            indicators.append({"name": "RSI", "params": {"period": 14}})
        if use_macd:
            indicators.append({"name": "MACD", "params": {}})

        strategy = {
            "name": "UI Strategy",
            "indicators": indicators,
            "risk_management": {
                "stop_loss_pct": stop_loss,
                "take_profit_pct": take_profit,
            },
            "position_size": {"method": "fixed", "value": 100},
            "commission": commission,
        }

        result = engine.backtest(symbol, strategy, timeframe, days, initial_balance)

        if "error" in result:
            return f"Error: {result['error']}"

        # 格式化输出
        output = f"""## 回测结果

| 指标 | 值 |
|------|-----|
| 总交易次数 | {result['total_trades']} |
| 胜率 | {result['win_rate']:.2f}% |
| 总收益 | ${result['total_pnl']:.2f} ({result['total_pnl_pct']:+.2f}%) |
| 最终资金 | ${result['final_balance']:.2f} |
| 最大回撤 | {result['max_drawdown_pct']:.2f}% |
| 夏普比率 | {result['sharpe_ratio']:.2f} |
| 索提诺比率 | {result['sortino_ratio']:.2f} |
"""
        return output
    except Exception as e:
        return f"Error: {str(e)}"


def get_indicator_data(symbol: str, timeframe: str, days: int, indicator: str) -> Any:
    """获取指标数据"""
    try:
        collector = get_market_data_collector()
        df = collector.collect(symbol, timeframe, days)

        if df.empty:
            return None

        result_df = calculate_indicator(df, indicator.upper())

        # 返回最后20行
        return result_df.tail(20)
    except Exception as e:
        return None


def get_backtest_history_ui(limit: int = 10):
    """获取回测历史"""
    try:
        db = get_database()
        history = db.get_backtest_runs(limit=limit)

        if not history:
            return "暂无回测历史"

        output = "## 回测历史\n\n"
        output += "| ID | 交易对 | 周期 | 策略 | 收益 | 胜率 | 日期 |\n"
        output += "|---|---|---|---|---|---|---|\n"

        for run in history:
            date = run.get('created_at', '')[:10]
            output += f"| {run['id']} | {run['symbol']} | {run['timeframe']} | {run.get('strategy_name', 'N/A')[:15]} | ${run['total_pnl']:.2f} | {run['win_rate']:.1f}% | {date} |\n"

        return output
    except Exception as e:
        return f"Error: {str(e)}"


def get_example_code(indicator_type: str) -> str:
    """获取示例代码"""
    engine = get_custom_engine()
    return CustomIndicatorEngine.get_example_code(indicator_type)


def run_custom_backtest(symbol: str, timeframe: str, days: int,
                       code: str, initial_balance: float,
                       stop_loss: float, take_profit: float,
                       commission: float) -> tuple:
    """运行自定义指标回测"""
    try:
        collector = get_market_data_collector()
        df = collector.collect(symbol, timeframe, days)

        if df.empty:
            return "", f"Error: No data for {symbol}"

        engine = get_custom_engine()

        # 执行指标
        result = engine.execute(code, df)

        if "error" in result:
            return "", f"Error: {result['error']}"

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

        # 策略配置
        from quant_core.backtest import BacktestEngine, BacktestConfig

        strategy = {
            "name": result.get("name", "Custom"),
            "risk_management": {
                "stop_loss_pct": stop_loss,
                "take_profit_pct": take_profit,
            },
            "position_size": {"method": "fixed", "value": 100},
            "commission": commission,
        }

        cfg = BacktestConfig(
            initial_balance=initial_balance,
            commission=commission
        )
        bt_engine = BacktestEngine(config=cfg)
        bt_result = bt_engine.run(df, strategy, df, signal_func=signal_func)

        output = f"""## 自定义指标回测结果

**指标**: {result.get('name', 'N/A')}

| 指标 | 值 |
|------|-----|
| 总交易次数 | {bt_result['total_trades']} |
| 胜率 | {bt_result['win_rate']:.2f}% |
| 总收益 | ${bt_result['total_pnl']:.2f} ({bt_result['total_pnl_pct']:+.2f}%) |
| 最大回撤 | {bt_result['max_drawdown_pct']:.2f}% |
| 夏普比率 | {bt_result['sharpe_ratio']:.2f} |

**信号统计**:
"""
        for sig in result.get("signals", []):
            sig_type = sig.get("type", "unknown")
            data = sig.get("data", [])
            count = sum(1 for x in data if x is not None)
            output += f"- {sig_type}: {count} signals\n"

        return output, ""
    except Exception as e:
        return "", f"Error: {str(e)}"


def build_ui():
    """构建Gradio界面"""
    with gr.Blocks(title="QuantCore", theme=gr.themes.Soft()) as app:
        gr.Markdown("# QuantCore - AI量化分析平台")

        with gr.Tabs():
            # Tab 1: AI分析
            with gr.TabItem("AI分析"):
                with gr.Row():
                    with gr.Column():
                        symbol = gr.Textbox(label="交易对", value="BTC/USDT")
                        timeframe = gr.Dropdown(
                            label="时间周期",
                            choices=["1m", "5m", "15m", "30m", "1H", "4H", "1D"],
                            value="1D"
                        )
                        days = gr.Slider(label="分析天数", minimum=7, maximum=365, value=30)
                        analyze_btn = gr.Button("分析", variant="primary")

                    with gr.Column():
                        report_output = gr.Markdown(label="分析报告")
                        indicators_output = gr.Textbox(label="技术指标", lines=5)
                        summary_output = gr.Textbox(label="摘要", lines=3)

                analyze_btn.click(
                    analyze_token,
                    inputs=[symbol, timeframe, days],
                    outputs=[report_output, indicators_output, summary_output, gr.Textbox()]
                )

            # Tab 2: 回测
            with gr.TabItem("回测"):
                with gr.Row():
                    with gr.Column():
                        symbol_bt = gr.Textbox(label="交易对", value="BTC/USDT")
                        timeframe_bt = gr.Dropdown(
                            label="时间周期",
                            choices=["1m", "5m", "15m", "30m", "1H", "4H", "1D"],
                            value="1D"
                        )
                        days_bt = gr.Slider(label="回测天数", minimum=7, maximum=365, value=30)
                        initial_balance = gr.Number(label="初始资金", value=10000)

                    with gr.Column():
                        stop_loss = gr.Slider(label="止损%", minimum=0.5, maximum=10, value=2.0, step=0.5)
                        take_profit = gr.Slider(label="止盈%", minimum=1, maximum=20, value=6.0, step=0.5)
                        commission = gr.Slider(label="手续费%", minimum=0.01, maximum=1, value=0.1, step=0.01)
                        use_rsi = gr.Checkbox(label="使用RSI", value=True)
                        use_macd = gr.Checkbox(label="使用MACD", value=False)

                backtest_btn = gr.Button("运行回测", variant="primary")
                backtest_output = gr.Markdown()

                backtest_btn.click(
                    run_backtest_ui,
                    inputs=[symbol_bt, timeframe_bt, days_bt, initial_balance,
                           stop_loss, take_profit, commission, use_rsi, use_macd],
                    outputs=[backtest_output]
                )

            # Tab 3: 自定义指标
            with gr.TabItem("自定义指标"):
                with gr.Row():
                    with gr.Column():
                        symbol_ci = gr.Textbox(label="交易对", value="BTC/USDT")
                        timeframe_ci = gr.Dropdown(
                            label="时间周期",
                            choices=["1m", "5m", "15m", "30m", "1H", "4H", "1D"],
                            value="1D"
                        )
                        days_ci = gr.Slider(label="天数", minimum=7, maximum=365, value=30)
                        example_dropdown = gr.Dropdown(
                            label="选择示例",
                            choices=["rsi", "macd", "boll"],
                            value=None
                        )
                        show_example_btn = gr.Button("显示示例代码")

                    with gr.Column():
                        initial_balance_ci = gr.Number(label="初始资金", value=10000)
                        stop_loss_ci = gr.Slider(label="止损%", minimum=0.5, maximum=10, value=2.0, step=0.5)
                        take_profit_ci = gr.Slider(label="止盈%", minimum=1, maximum=20, value=6.0, step=0.5)
                        commission_ci = gr.Slider(label="手续费%", minimum=0.01, maximum=1, value=0.1, step=0.01)

                code_input = gr.Textbox(
                    label="指标代码 (Python)",
                    lines=15,
                    value="# 在下方编写你的指标代码\n# 必须定义 output 变量\ndf['buy'] = df['close'].pct_change() > 0.01\ndf['sell'] = df['close'].pct_change() < -0.01\noutput = {\n    'name': 'My Indicator',\n    'plots': [],\n    'signals': [\n        {'type': 'buy', 'text': 'B', 'data': df['buy'].tolist(), 'color': 'green'},\n        {'type': 'sell', 'text': 'S', 'data': df['sell'].tolist(), 'color': 'red'}\n    ]\n}"
                )

                example_output = gr.Textbox(label="示例代码", lines=10, visible=False)
                show_example_btn.click(
                    get_example_code,
                    inputs=[example_dropdown],
                    outputs=[example_output]
                )
                show_example_btn.click(
                    lambda x: gr.update(visible=True),
                    inputs=[example_output],
                    outputs=[example_output]
                )

                custom_backtest_btn = gr.Button("运行自定义回测", variant="primary")
                custom_output = gr.Markdown()

                custom_backtest_btn.click(
                    run_custom_backtest,
                    inputs=[symbol_ci, timeframe_ci, days_ci, code_input,
                           initial_balance_ci, stop_loss_ci, take_profit_ci, commission_ci],
                    outputs=[custom_output, gr.Textbox()]
                )

            # Tab 4: 回测历史
            with gr.TabItem("回测历史"):
                history_limit = gr.Slider(label="显示数量", minimum=5, maximum=100, value=20, step=5)
                refresh_btn = gr.Button("刷新")
                history_output = gr.Markdown()

                refresh_btn.click(
                    get_backtest_history_ui,
                    inputs=[history_limit],
                    outputs=[history_output]
                )

                # 初始加载
                app.load(
                    get_backtest_history_ui,
                    inputs=[history_limit],
                    outputs=[history_output]
                )

        gr.Markdown("""
        ---
        **QuantCore** - 轻量级AI量化框架

        支持: Binance | OKX | Bybit | Kucoin | Gate.io

        AI Provider: MiniMax | DeepSeek | OpenAI | Claude
        """)

    return app


def launch_ui(**kwargs):
    """启动界面"""
    app = build_ui()
    app.launch(**kwargs)


if __name__ == "__main__":
    launch_ui(server_name="0.0.0.0", server_port=7860, share=False)
