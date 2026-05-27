# SUI Intent Engine

> 让 DeFi 交易像对话一样简单

## 项目简介

**SUI Intent Engine** 是一个基于自然语言的 DeFi 交易意图引擎，集成 SUI 原生订单簿 DeepBook V3，提供实时市场数据可视化和 AI 辅助交易功能。

## 核心功能

1. **自然语言交易** - 用日常语言描述交易需求
2. **实时市场数据** - K线图、订单簿、Ticker
3. **DeepBook V3 交易** - SUI 原生订单簿执行
4. **AI 策略分析** - 技术指标和信号分析

## 项目结构

```
sui-intent-engine/
├── docs/                       # 技术文档
│   ├── deepbookv3/            # DeepBook V3 合约文档
│   ├── deepbookv3-sdk/        # DeepBook SDK 文档
│   ├── deepbook-margin/       # Margin 交易文档
│   └── DEEPBOOK_TUTORIAL.md   # DeepBook 入门指南
├── src/
│   ├── frontend/               # React 前端
│   │   └── src/components/    # UI 组件
│   │       ├── MarketChart.tsx    # K线图
│   │       ├── OrderBook.tsx      # 订单簿
│   │       ├── TradingPage.tsx    # 交易页面
│   │       └── AIChatPage.tsx     # AI 对话
│   ├── sui/                   # SUI DeepBook 集成
│   │   ├── deepbook_client.py    # DeepBook 客户端
│   │   ├── deepbook_cache.py     # 市场数据缓存
│   │   └── deepbook_indexer.py   # 数据索引
│   ├── server.py              # FastAPI 服务
│   └── sui_intent_server.py   # SUI Intent API
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React / TypeScript / Vite |
| 后端 | Python FastAPI |
| AI | MiniMax LLM |
| 链交互 | SUI SDK |
| 订单簿 | DeepBook V3 |
| 市场数据 | DeepBook V3 Indexer |

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
