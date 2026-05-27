"""
数据源模块 - 支持CCXT统一接口
"""
from quant_core.data_source.exchange import ExchangeDataSource

def get_data_source(exchange: str = None, **kwargs):
    return ExchangeDataSource(exchange=exchange, **kwargs)

__all__ = ["ExchangeDataSource", "get_data_source"]
