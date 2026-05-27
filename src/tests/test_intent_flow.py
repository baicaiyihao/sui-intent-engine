#!/usr/bin/env python3
"""
Test Intent Flow - 测试完整流程
测试从自然语言解析到 PTB 预览的完整流程
"""
import sys
import os

# Add src to path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.dirname(_current_dir)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

import asyncio
from datetime import datetime


def test_intent_parsing():
    """Test 1: 意图解析"""
    print("\n" + "=" * 60)
    print("TEST 1: Intent Parsing")
    print("=" * 60)

    from ai.intent_parser import IntentParser, get_intent_parser

    test_cases = [
        "RSI < 30 时买入 100 美金 SUI，止损 2%",
        "MACD 金叉时买入 50 USD SUI",
        "当 KDJ > 80 时卖出 SUI，止盈 5%",
        "RSI 超卖时买入 200 美金 SUI，止损 3%，止盈 8%",
        "买入 100 美元的 SUI",
    ]

    parser = IntentParser(None)  # Use rule-based parsing

    for i, text in enumerate(test_cases, 1):
        print(f"\n[Test {i}] Input: {text}")
        intent = parser.parse(text)
        print(f"  -> Action: {intent.action}")
        print(f"  -> Asset: {intent.asset}")
        print(f"  -> Amount: ${intent.amount_usd}")
        print(f"  -> Stop Loss: {intent.stop_loss_pct}%")
        print(f"  -> Take Profit: {intent.take_profit_pct}%")
        if intent.trigger:
            print(f"  -> Trigger: {intent.trigger.indicator} {intent.trigger.condition} {intent.trigger.threshold}")
        else:
            print(f"  -> Trigger: None")

    print("\n[PASS] Intent parsing tests completed")


def test_guardian_risk_check():
    """Test 2: 风险检查"""
    print("\n" + "=" * 60)
    print("TEST 2: Guardian Risk Check")
    print("=" * 60)

    from ai.guardian import Guardian, get_guardian

    guardian = get_guardian()

    # Test case 1: Buy when RSI is oversold (low risk)
    print("\n[Test A] Buy intent with RSI oversold...")
    indicators_oversold = {
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

    buy_intent = {
        "action": "buy",
        "asset": "SUI",
        "amount_usd": 100.0
    }

    report = guardian.check_risk(indicators_oversold, buy_intent)
    print(f"  Risk Level: {report.risk_level}")
    print(f"  Risk Score: {report.risk_score}")
    print(f"  Can Proceed: {report.can_proceed}")
    print(f"  Recommendation: {report.recommendation}")

    assert report.risk_level in ["low", "medium"], f"Expected low/medium risk, got {report.risk_level}"
    print("  [PASS] Oversold RSI correctly assessed as low/medium risk")

    # Test case 2: Buy when RSI is overbought (high risk)
    print("\n[Test B] Buy intent with RSI overbought...")
    indicators_overbought = {
        "rsi": 85.0,
        "macd_histogram": -0.5,
        "macd": -0.1,
        "macd_signal": 0.05,
        "boll_position": 0.85,
        "kdj_k": 85.0,
        "kdj_d": 80.0,
        "kdj_j": 95.0,
        "volume_ratio": 0.4,
        "adx": 15.0
    }

    report = guardian.check_risk(indicators_overbought, buy_intent)
    print(f"  Risk Level: {report.risk_level}")
    print(f"  Risk Score: {report.risk_score}")
    print(f"  Can Proceed: {report.can_proceed}")
    print(f"  Recommendation: {report.recommendation}")

    assert report.risk_level in ["high", "critical"], f"Expected high/critical risk, got {report.risk_level}"
    print("  [PASS] Overbought RSI correctly assessed as high/critical risk")

    print("\n[PASS] Guardian risk check tests completed")


def test_deepbook_ptb():
    """Test 3: DeepBook PTB 预览"""
    print("\n" + "=" * 60)
    print("TEST 3: DeepBook PTB Preview")
    print("=" * 60)

    from sui.deepbook_client import DeepBookClient, get_deepbook_client, OrderSide

    deepbook = get_deepbook_client()

    # Test case: Buy SUI
    print("\n[Test] Buy 100 USD SUI at ~$2.0")
    preview = deepbook.build_ptb_preview(
        side=OrderSide.BUY,
        asset="SUI",
        amount_usd=100.0,
        current_price=2.0
    )

    print(f"  Estimated Amount: {preview.estimated_amount:.6f} {preview.asset}")
    print(f"  Estimated Price: ${preview.estimated_price:.4f}")
    print(f"  Slippage: {preview.estimated_slippage}")
    print(f"  Fees: {preview.estimated_fees}")
    print(f"  Warnings: {preview.warnings}")
    print(f"  PTB Commands: {len(preview.ptb_commands)}")

    for cmd in preview.ptb_commands:
        print(f"    {cmd['index']}. {cmd['command']}: {cmd['description']}")

    assert preview.estimated_amount > 0, "Estimated amount should be positive"
    assert len(preview.ptb_commands) > 0, "Should have PTB commands"
    print("\n[PASS] DeepBook PTB preview test completed")


async def test_deepbook_execution():
    """Test 4: DeepBook 执行 (Mock)"""
    print("\n" + "=" * 60)
    print("TEST 4: DeepBook Order Execution (Mock)")
    print("=" * 60)

    from sui.deepbook_client import get_deepbook_client, OrderSide

    deepbook = get_deepbook_client()

    print("\n[Test] Execute Buy order for 100 USD SUI")
    result = await deepbook.place_market_order(
        side=OrderSide.BUY,
        asset="SUI",
        amount_usd=100.0,
        current_price=2.0
    )

    print(f"  Success: {result.success}")
    print(f"  Order ID: {result.order_id}")
    print(f"  Executed Price: ${result.executed_price:.4f}")
    print(f"  Executed Amount: {result.executed_amount:.6f} SUI")
    print(f"  Slippage: {result.slippage:.4f}%")
    print(f"  Fees: ${result.fees:.4f}")
    print(f"  TX Hash: {result.tx_hash[:16]}..." if result.tx_hash else "  TX Hash: None")
    print(f"  Message: {result.message}")

    assert result.success, "Order should succeed in mock mode"
    assert result.order_id, "Order ID should be generated"
    assert result.executed_amount > 0, "Executed amount should be positive"
    print("\n[PASS] DeepBook execution test completed")


def test_full_flow():
    """Test 5: 完整流程测试"""
    print("\n" + "=" * 60)
    print("TEST 5: Full Intent Flow")
    print("=" * 60)

    from ai.intent_parser import IntentParser
    from ai.guardian import Guardian
    from sui.deepbook_client import DeepBookClient, OrderSide

    parser = IntentParser(None)
    guardian = Guardian()
    deepbook = DeepBookClient()

    # Step 1: Parse
    print("\n[Step 1] Parse: 'RSI < 30 时买入 100 美金 SUI，止损 2%'")
    text = "RSI < 30 时买入 100 美金 SUI，止损 2%"
    intent = parser.parse(text)
    print(f"  Parsed: {intent.action} {intent.amount_usd} {intent.asset}")
    if intent.trigger:
        print(f"  Trigger: {intent.trigger.indicator} {intent.trigger.condition} {intent.trigger.threshold}")

    # Step 2: Risk check
    print("\n[Step 2] Risk Check")
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
    risk_report = guardian.check_risk(indicators, intent.to_dict())
    print(f"  Risk Level: {risk_report.risk_level}")
    print(f"  Can Proceed: {risk_report.can_proceed}")

    # Step 3: PTB Preview
    print("\n[Step 3] PTB Preview")
    preview = deepbook.build_ptb_preview(
        side=OrderSide.BUY,
        asset=intent.asset,
        amount_usd=intent.amount_usd,
        current_price=2.0
    )
    print(f"  Est. Amount: {preview.estimated_amount:.6f} {preview.asset}")
    print(f"  PTB Commands: {len(preview.ptb_commands)}")

    print("\n[PASS] Full flow test completed")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "#" * 60)
    print("# SuiIntent Engine - Intent Flow Tests")
    print("#" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")

    try:
        test_intent_parsing()
        test_guardian_risk_check()
        test_deepbook_ptb()
        asyncio.run(test_deepbook_execution())
        test_full_flow()

        print("\n" + "#" * 60)
        print("# ALL TESTS PASSED!")
        print("#" * 60)
        return 0

    except Exception as e:
        print(f"\n[FAIL] Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
