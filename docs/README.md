# SUI Intent Engine

> 让 DeFi 交易像对话一样简单

## 项目简介

**SUI Intent Engine** 是一个基于自然语言的 DeFi 交易意图引擎，结合 AI 量化分析和 SUI 原生订单簿 DeepBook V3，提供智能交易体验。

## 核心功能

1. **自然语言交易** - "RSI 低于 30 时买入 100 美金 SUI"
2. **AI 量化分析** - RSI/MACD/KDJ/布林带多维度技术分析
3. **实时市场数据** - K线图、订单簿、Ticker
4. **DeepBook V3 交易** - SUI 原生订单簿执行
5. **策略回测** - 自定义指标和回测验证

## 项目结构

```
sui-intent-engine/
├── docs/                       # 技术文档
│   ├── deepbookv3/            # DeepBook V3 合约文档
│   ├── deepbookv3-sdk/        # DeepBook SDK 文档
│   └── DEEPBOOK_TUTORIAL.md   # DeepBook 入门指南
├── src/
│   ├── frontend/               # React 前端
│   │   └── src/components/    # UI 组件
│   │       ├── MarketChart.tsx    # K线图
│   │       ├── OrderBook.tsx      # 订单簿
│   │       ├── TradingPage.tsx    # 交易页面
│   │       └── AIChatPage.tsx     # AI 对话
│   ├── quant_core/            # AI 量化引擎
│   │   ├── ai/                    # AI 分析模块
│   │   │   ├── analyzer.py         # 市场分析器
│   │   │   ├── trading_signal.py   # 交易信号
│   │   │   └── indicator_quality.py # 指标质量分析
│   │   ├── strategy/              # 策略模块
│   │   │   ├── compiler.py         # 策略编译
│   │   │   └── indicators.py      # 技术指标
│   │   └── backtest/              # 回测引擎
│   ├── sui/                   # SUI DeepBook 集成
│   │   ├── deepbook_client.py     # DeepBook 客户端
│   │   └── deepbook_cache.py     # 市场数据缓存
│   ├── server.py              # FastAPI 服务
│   └── sui_intent_server.py   # SUI Intent API
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React / TypeScript / Vite |
| 后端 | Python FastAPI |
| AI | MiniMax LLM |
| 量化分析 | 技术指标、信号生成、回测 |
| 链交互 | SUI SDK |
| 订单簿 | DeepBook V3 |
| 市场数据 | DeepBook V3 Indexer |

## AI 量化引擎 (QuantCore)

**功能模块**：
- `analyzer.py` - 市场技术分析（RSI/MACD/KDJ/布林带）
- `trading_signal.py` - AI 交易信号生成
- `indicator_quality.py` - 自定义指标质量分析
- `backtest/` - 策略回测引擎

**分析维度**：
- 价格趋势识别
- 超买超卖判断
- 支撑阻力位
- 成交量分析

## DeepBook V3 主网配置

| 参数 | 值 |
|------|-----|
| Package | `0x2c8d603bc51326b8c13cef9dd07031a408a48dddb541963357661df5d3204809` |
| Registry | `0xaf16199a2dff736e9f07a845f23c5da6df6f756eddb631aed9d24a93efc4549d` |
| SUI_USDC Pool | `0xe05dafb5133bcffb8d59f4e12465dc0e9faeaa05e3e342a08fe135800e3e4407` |

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 启动后端
python -m src.sui_intent_server

# 启动前端
cd src/frontend
npm install
npm run dev
```

## License

MIT
