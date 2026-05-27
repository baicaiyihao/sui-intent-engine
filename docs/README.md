# SUI Intent Engine

> 让 DeFi 交易像对话一样简单

## 项目简介

**SUI Intent Engine** 是一个基于自然语言的 DeFi 交易意图引擎，用户用日常语言描述交易目标，系统解析为 SUI PTB 交易，在 DeepBook V3 订单簿上执行。

## 核心功能

1. **自然语言意图解析** - "RSI 低于 30 的时候买入 100 美金 SUI"
2. **Guardian 风险检查** - RSI/MACD/KDJ/布林带多维度检查
3. **人类可读预览** - 执行前完整展示交易细节
4. **DeepBook V3 执行** - SUI 原生订单簿
5. **实时市场数据** - K线、订单簿、Ticker

## 技术架构

```
用户输入 → Intent Parser → Guardian → PTB Builder → User Confirm → DeepBook → Walrus
```

## 快速开始

```bash
# 克隆项目
git clone <repo-url>
cd sui-intent-engine

# 安装依赖
pip install -r requirements.txt

# 运行服务
python -m src.api
```

## 项目结构

```
sui-intent-engine/
├── docs/
│   ├── PROJECT_PLAN.md      # 项目计划书
│   └── README.md            # 本文件
├── src/
│   ├── intent_parser.py      # 意图解析
│   ├── guardian.py           # 风险检查
│   ├── ptb_builder.py       # PTB 构建
│   ├── deepbook_client.py   # DeepBook 交互
│   ├── walrus_client.py     # Walrus 存证
│   └── api.py               # API 接口
├── tests/
└── config/
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
| 存储 | Walrus |

## 联系方式

[团队联系方式]

## License

MIT
