#!/usr/bin/env python3
"""
SuiIntent Engine - Main Entry Point
SUI 意图驱动交易引擎
"""
import sys
import os

# Add src to path
_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

import argparse


def main():
    parser = argparse.ArgumentParser(
        description="SuiIntent Engine - SUI Intent-driven Trading Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start the API server
  python sui_intent_main.py server --port 8080

  # Run tests
  python sui_intent_main.py test

  # Parse an intent
  python sui_intent_main.py parse "RSI < 30 时买入 100 美金 SUI"
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Server command
    p_server = subparsers.add_parser("server", help="Start the SuiIntent API server")
    p_server.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    p_server.add_argument("--port", type=int, default=8080, help="Port to bind (default: 8080)")
    p_server.set_defaults(func=run_server)

    # Test command
    p_test = subparsers.add_parser("test", help="Run the intent flow test")
    p_test.add_argument("--text", default="RSI < 30 时买入 100 美金 SUI，止损 2%", help="Intent text to test")
    p_test.set_defaults(func=run_test)

    # Parse command (CLI only, no execution)
    p_parse = subparsers.add_parser("parse", help="Parse an intent (CLI mode)")
    p_parse.add_argument("text", help="Intent text to parse")
    p_parse.add_argument("--no-llm", dest="use_llm", action="store_false", default=True, help="Disable LLM parsing")
    p_parse.set_defaults(func=run_parse)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


def run_server(args):
    """Start the API server"""
    from sui_intent_server import run_server
    print(f"Starting SuiIntent Engine API server at http://{args.host}:{args.port}")
    print(f"API docs: http://{args.host}:{args.port}/docs")
    run_server(host=args.host, port=args.port)
    return 0


def run_test(args):
    """Run the intent flow test"""
    from ai.intent_parser import get_intent_parser, IntentParser
    from ai.guardian import get_guardian
    from sui.deepbook_client import get_deepbook_client, OrderSide

    print("=" * 60)
    print("SuiIntent Engine - Intent Flow Test")
    print("=" * 60)

    test_text = args.text
    print(f"\n[1] Input: {test_text}")

    # Step 1: Parse intent
    print("\n[2] Parsing intent...")
    parser = get_intent_parser()
    intent = parser.parse(test_text)
    print(f"    Action: {intent.action}")
    print(f"    Asset: {intent.asset}")
    print(f"    Amount: ${intent.amount_usd}")
    print(f"    Stop Loss: {intent.stop_loss_pct}%")
    print(f"    Take Profit: {intent.take_profit_pct}%")
    if intent.trigger:
        print(f"    Trigger: {intent.trigger.indicator} {intent.trigger.condition} {intent.trigger.threshold}")

    # Step 2: Mock indicators for risk check
    print("\n[3] Risk check...")
    indicators = {
        "rsi": 25.0,
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
    print(f"    Indicators: RSI={indicators['rsi']}, MACD_hist={indicators['macd_histogram']}")

    guardian = get_guardian()
    risk_report = guardian.check_risk(indicators=indicators, intent=intent.to_dict())

    print(f"    Risk Level: {risk_report.risk_level}")
    print(f"    Risk Score: {risk_report.risk_score}")
    print(f"    Can Proceed: {risk_report.can_proceed}")
    print(f"    Recommendation: {risk_report.recommendation}")

    # Step 3: PTB Preview
    print("\n[4] PTB Preview...")
    deepbook = get_deepbook_client()
    side = OrderSide.BUY if intent.action == "buy" else OrderSide.SELL
    preview = deepbook.build_ptb_preview(
        side=side,
        asset=intent.asset,
        amount_usd=intent.amount_usd,
        current_price=2.0  # Mock SUI price
    )

    print(f"    Estimated Amount: {preview.estimated_amount:.6f} {preview.asset}")
    print(f"    Estimated Price: ${preview.estimated_price:.4f}")
    print(f"    Estimated Slippage: {preview.estimated_slippage}")
    print(f"    Estimated Fees: {preview.estimated_fees}")
    print(f"    PTB Commands: {len(preview.ptb_commands)}")

    for cmd in preview.ptb_commands:
        print(f"      {cmd['index']}. {cmd['command']}: {cmd['description']}")

    # Summary
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)

    return 0


def run_parse(args):
    """Parse an intent without executing"""
    from ai.intent_parser import get_intent_parser, IntentParser

    parser = get_intent_parser() if args.use_llm else IntentParser(None)
    intent = parser.parse(args.text)

    print(f"Parsed Intent:")
    print(f"  Action: {intent.action}")
    print(f"  Asset: {intent.asset}")
    print(f"  Amount: ${intent.amount_usd}")
    print(f"  Stop Loss: {intent.stop_loss_pct}%")
    print(f"  Take Profit: {intent.take_profit_pct}%")
    print(f"  Timeframe: {intent.timeframe}")
    if intent.trigger:
        print(f"  Trigger: {intent.trigger.indicator} {intent.trigger.condition} {intent.trigger.threshold}")

    print("\nHuman Readable:")
    print(parser.to_human_readable(intent))

    return 0


if __name__ == "__main__":
    sys.exit(main())
