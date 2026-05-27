"""
技术指标计算
"""
import pandas as pd
import numpy as np
from typing import Union, Tuple


def calculate_indicator(df: pd.DataFrame, indicator: str, **params) -> pd.DataFrame:
    """
    计算技术指标

    支持指标:
    - RSI: 相对强弱指数
    - MACD: 移动平均收敛散度
    - EMA: 指数移动平均
    - SMA: 简单移动平均
    - BOLL: 布林带
    - KDJ: KDJ指标
    - ATR: 平均真实波幅
    - SuperTrend: 超趋势
    """
    indicator = indicator.upper()

    if indicator == "RSI":
        return _rsi(df, params.get("period", 14))
    elif indicator == "MACD":
        return _macd(df,
                     params.get("fast", 12),
                     params.get("slow", 26),
                     params.get("signal", 9))
    elif indicator == "EMA":
        return _ema(df, params.get("period", 20))
    elif indicator == "SMA":
        return _sma(df, params.get("period", 20))
    elif indicator == "BOLL":
        return _boll(df,
                     params.get("period", 20),
                     params.get("std", 2))
    elif indicator == "KDJ":
        return _kdj(df,
                    params.get("n", 9),
                    params.get("m1", 3),
                    params.get("m2", 3))
    elif indicator == "ATR":
        return _atr(df, params.get("period", 14))
    elif indicator == "SUPERTREND":
        return _supertrend(df,
                          params.get("period", 10),
                          params.get("multiplier", 3))
    else:
        raise ValueError(f"Unknown indicator: {indicator}")


def _rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """RSI指标"""
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return df.assign(rsi=rsi)


def _macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD指标"""
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    return df.assign(macd=macd, macd_signal=signal_line, macd_hist=histogram)


def _ema(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """指数移动平均"""
    ema = df["close"].ewm(span=period, adjust=False).mean()
    return df.assign(ema=ema)


def _sma(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """简单移动平均"""
    sma = df["close"].rolling(window=period).mean()
    return df.assign(sma=sma)


def _boll(df: pd.DataFrame, period: int = 20, std: float = 2) -> pd.DataFrame:
    """布林带"""
    middle = df["close"].rolling(window=period).mean()
    std_dev = df["close"].rolling(window=period).std()
    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)
    return df.assign(boll_upper=upper, boll_middle=middle, boll_lower=lower)


def _kdj(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
    """KDJ指标"""
    low_n = df["low"].rolling(window=n).min()
    high_n = df["high"].rolling(window=n).max()
    rsv = (df["close"] - low_n) / (high_n - low_n) * 100
    k = rsv.ewm(com=m1 - 1, adjust=False).mean()
    d = k.ewm(com=m2 - 1, adjust=False).mean()
    j = 3 * k - 2 * d
    return df.assign(kdj_k=k, kdj_d=d, kdj_j=j)


def _atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """ATR指标"""
    high_low = df["high"] - df["low"]
    high_close = np.abs(df["high"] - df["close"].shift())
    low_close = np.abs(df["low"] - df["close"].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return df.assign(atr=atr)


def _supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3) -> pd.DataFrame:
    """SuperTrend指标"""
    atr = _atr(df, period)["atr"]
    hl2 = (df["high"] + df["low"]) / 2
    upper = hl2 + multiplier * atr
    lower = hl2 - multiplier * atr
    close = df["close"]

    # 计算SuperTrend
    trend = pd.Series(True, index=df.index)
    supertrend = pd.Series(upper.values, index=df.index)

    for i in range(1, len(df)):
        if close.iloc[i] > upper.iloc[i - 1]:
            trend.iloc[i] = True
        elif close.iloc[i] < lower.iloc[i - 1]:
            trend.iloc[i] = False
        else:
            trend.iloc[i] = trend.iloc[i - 1]

        if trend.iloc[i]:
            supertrend.iloc[i] = lower.iloc[i]
        else:
            supertrend.iloc[i] = upper.iloc[i]

    return df.assign(supertrend=supertrend, supertrend_trend=trend.astype(int))
