# SuiIntent Guardian

> 让 DeFi 像对话一样简单，保留机构和散户级别的风控

## 项目简介

**SuiIntent Guardian** 是一个基于自然语言的 DeFi 交易意图引擎，用户用日常语言描述交易目标，系统解析为 SUI PTB 交易，在执行前进行多维度风险检查，并以人类可读的方式展示预览，确保用户始终掌控交易决策。

## 参赛信息

- **赛道**: The Agentic Web - Sub-track 3: Intent Engine
- **奖金**: 一等奖 $30,000 | 二等奖 $15,000 | 三等奖 $10,000
- **时间**: 2026-05-07 ~ 2026-06-21

## 核心功能

1. **自然语言意图解析** - "RSI 低于 30 的时候买入 100 美金 SUI"
2. **Guardian 风险检查** - RSI/MACD/KDJ/布林带多维度检查
3. **人类可读预览** - 执行前完整展示交易细节
4. **DeepBook 执行** - SUI 原生订单簿
5. **Walrus 存证** - 策略快照可追溯

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
| 前端 | React / HTML |
| 后端 | Python FastAPI |
| AI | MiniMax LLM |
| 链交互 | SUI SDK |
| 数据源 | Binance API |
| 存储 | Walrus |

## 联系方式

[团队联系方式]

## License

MIT
