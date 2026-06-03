"""
QuantCore - Core AI modules for trading analysis
"""
from .llm import get_llm_service
from .quant_engine import QuantEngine
from .market_data import get_market_data_collector
from .database import get_database
from .strategy.indicators import calculate_indicator

# Gradio-based UI is optional — only import if gradio is installed
try:
    from .web import launch_ui
    _HAS_UI = True
except ImportError:
    launch_ui = None
    _HAS_UI = False

__all__ = [
    "get_llm_service",
    "QuantEngine",
    "get_market_data_collector",
    "get_database",
    "calculate_indicator",
    "launch_ui",
]
