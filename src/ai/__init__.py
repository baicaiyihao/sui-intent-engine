"""
SuiIntent Guardian - AI 模块
包含:
- Guardian: 风险检查 (来自原有系统)
- IntentParser: 意图解析 (新功能)
"""
from .guardian import Guardian, get_guardian
from .intent_parser import IntentParser, get_intent_parser

# 从 quant_core 导入的核心 AI 模块
try:
    from quant_core.ai import (
        get_ai_signal_service,
        AITradingSignal,
        MarketAnalyzer,
    )
except ImportError:
    # 如果 quant_core 不在路径中，尝试添加父目录到路径
    import sys
    from pathlib import Path
    parent = Path(__file__).parent.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))
    from quant_core.ai import (
        get_ai_signal_service,
        AITradingSignal,
        MarketAnalyzer,
    )

__all__ = [
    # 原有 AI 模块
    "get_ai_signal_service",
    "AITradingSignal",
    "MarketAnalyzer",
    # SUI Intent 新模块
    "Guardian",
    "get_guardian",
    "IntentParser",
    "get_intent_parser",
]
