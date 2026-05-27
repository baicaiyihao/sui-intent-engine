"""
QuantCore 配置
"""
import os
from dotenv import load_dotenv

# 明确指定.env路径
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(env_path)

# ========== AI LLM 配置 ==========
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "minimax").lower()

# MiniMax (默认)
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_MODEL = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7-highspeed")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.io/v1")

# OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# DeepSeek
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# Google
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-1.5-flash")

# Grok
GROK_API_KEY = os.getenv("GROK_API_KEY", "")

# ========== 交易配置 ==========
DEFAULT_EXCHANGE = os.getenv("DEFAULT_EXCHANGE", "binance")
TESTNET = os.getenv("TESTNET", "true").lower() in ("true", "1", "yes")

EXCHANGE_API_KEY = os.getenv("EXCHANGE_API_KEY", "")
EXCHANGE_SECRET = os.getenv("EXCHANGE_SECRET", "")
EXCHANGE_PASSWORD = os.getenv("EXCHANGE_PASSWORD", "")

# ========== 数据源配置 ==========
CCXT_TIMEOUT = int(os.getenv("CCXT_TIMEOUT", "30000"))
CCXT_ENABLE_RATE_LIMIT = os.getenv("CCXT_ENABLE_RATE_LIMIT", "true").lower() in ("true", "1", "yes")
CCXT_PROXY = os.getenv("CCXT_PROXY") or os.getenv("PROXY_URL", "")

TIMEFRAME_SECONDS = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1H": 3600, "2H": 7200, "4H": 14400, "6H": 21600, "8H": 28800,
    "12H": 43200, "1D": 86400, "3D": 259200, "1W": 604800
}

# ========== 回测配置 ==========
MAX_BACKTEST_KLINES = int(os.getenv("MAX_BACKTEST_KLINES", "100000"))

MAX_BACKTEST_DAYS = {
    "1m": 15, "5m": 365, "15m": 365, "30m": 365,
    "1H": 365, "4H": 730, "1D": 3650,
}

CACHE_TTL = {
    "1m": 60, "3m": 120, "5m": 300, "15m": 600, "30m": 900,
    "1H": 1800, "2H": 3600, "4H": 3600, "6H": 7200, "8H": 7200,
    "12H": 7200, "1D": 7200, "3D": 14400, "1W": 86400
}

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY", "")
