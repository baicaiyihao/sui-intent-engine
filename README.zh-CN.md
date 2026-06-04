# SUI 意图引擎

> **说出你的交易。看清风险。签名 PTB。**
> 一个 Sui 原生的意图引擎，为 Agentic Web 而生。

[![English](https://img.shields.io/badge/lang-English-blue?style=for-the-badge)](./README.md)
[![Sui Agentic](https://img.shields.io/badge/Sui%20Agentic%20Hackathon-Sub--track%2003%20%C2%B7%20Intent%20Engine-c8ff00?style=for-the-badge)](https://sui.io/hackathon)
[![主网已上线](https://img.shields.io/badge/SUI%20MAINNET-LIVE-00d4aa?style=for-the-badge)](https://suivision.xyz/account/0x5e54f169aa2df2c3fe2a7624170d1c85feb7ebf9b54f57e51cb80fc84578ed91)

[English version](./README.md) | 简体中文

---

## ⚡ 一句话简介

你说一句 *"RSI < 30 时买入 1 个 SUI，滑点 2%"*，引擎就会：

1. **解析 (PARSE)** — LLM 把自然语言编译成结构化意图
2. **守护 (GUARD)** — 跑 6 维风险检查（RSI · MACD · 布林带 · KDJ · 成交量 · ADX），用大白话告诉你哪里有风险
3. **预览 (PREVIEW)** — 人类可读的 PTB 卡片：价格、数量、总成本、过期时间、余额校验
4. **签名 (SIGN)** — 你显式确认，钱包签名，**DeepBook V3 在 Sui 主网执行**

无黑盒，无自动代理乱跑。每一步可见，每一步可逆。

---

## 🎯 为什么是 Sub-track 3（意图引擎）

| 赛道要求 | 我们的实现 |
|---|---|
| 自然语言 → PTB → 执行 | `AIChatPage` + `sui_intent_server.py` LLM 解析器 + `Transaction` 构建器 + dapp-kit `signTransaction` |
| 人类可读的 PTB 预览 | 提案卡片：价格、数量、总成本、过期时间、余额校验，全是大白话 |
| Guardian 覆盖 ≥ 2 类风险 | **6 维**检查（`src/ai/guardian.py`）：RSI、MACD、布林带、KDJ、成交量、ADX |
| 显式确认步骤 | 按钮组：`Confirm` / `Cancel` — 必须钱包签名 |

**这不是一个 swap 聊天机器人。** Guardian 层才是产品。AI 出方案，指标层把关，人类做决策。

---

## 🔁 4 步意图循环

```
  你                    我们                              链上
  ──                    ──                               ─────
 "RSI<30 时     ───►  解析
  买入 1 SUI,           LLM        →  结构化意图
  滑点 2%"                          (动作 / 数量 / 价格 / 条件)

                     守护
                       6 维        →  风险报告
                       Guardian       (risk_level, warnings, can_proceed)

                     预览
                       构建 PTB   →  PTB 卡片
                                     (价格 / 数量 / 总成本 / 过期 / 余额)

  [ 确认 ]    ◄──   签名
  钱包弹窗           signTransaction
  用户授权           ───►  DeepBook V3 在主网执行
```

代码层面：`src/ai/intent_parser.py`、`src/ai/guardian.py`、`src/frontend/src/components/AIChatPage.tsx`。

---

## ✨ 项目亮点

- 🎨 **双语 UI** — `zh` + `en` 一等公民，英文为默认（适配国际评委），27 个落地页 key + 300+ 应用 key
- ⚡ **实时数据** — DeepBook V3 indexer 推送实时 Ticker / K 线，1–3 秒刷新
- 🔐 **无托管风险** — 用户钱包签每个 PTB，我们不碰私钥，BM 生命周期全部上链
- 🧠 **LLM 双语** — 后端 `language` 参数切换 prompt 字典，再也不会"开了英文却回中文"
- 📊 **量化深度** — RSI / MACD / KDJ / 布林带 / 成交量 / ADX + 多周期共识
- 🏗️ **主网可验证** — 已在 SUI/USDC 池子上跑通限价 + 市价单、存款、提现，全部有据可查
- 🌐 **DeFi 原生** — Cetus BM 路径，「创建 BM + 存款 + 下单」一笔 PTB
- 📐 **生产级 UX** — 彭博终端风落地页，实时 Ticker，3 行项目陈述，4 步流程可视化

---

## 💰 商业化（4 层）

### 0. **链上协议费**（新上线 · 主网已发布）

每个意图支付 **0.005 SUI** 到链上 `ProtocolTreasury` 共享对象，由 `sui_intent_fee::protocol_fee` Move 模块收取。协议费作为意图 PTB 的第一步与 DeepBook 交易同笔原子执行。

- **主网 Package**: `0xad95919bbc8e08a36c28bf885fd7e8413296f63979d13b329d8713424157fd90`
- **主网 Treasury** (共享): `0x5e54f169aa2df2c3fe2a7624170d1c85feb7ebf9b54f57e51cb80fc84578ed91`
- **测试网 Package**: `0x9e7d5e8048f44773afede881ebb65422c01f686cfe2f141fb7bf9ef002859465`
- **11/11 单元测试通过** · 发布于 2026-06-03
- **主网已验证** — tx `4jGNB1W56Ehfy73nHEyfrK48XxQmWkzcDePVPxehvG1D`

| 事件 | 触发时机 | 用途 |
|---|---|---|
| `FeePaid { payer, amount, intent_type, intent_number }` | 每次意图 | 分析 / 仪表盘 |
| `FeeWithdrawn { admin, amount }` | 管理员提取 | 资金管理 |
| `FeeUpdated { old_fee, new_fee }` | 管理员调价 | 治理记录 |
| `AdminTransferred { old_admin, new_admin }` | 角色变更 | 角色交接 |

- **默认费率**: 5,000,000 MIST = 0.005 SUI / 意图（管理员可通过 `set_fee` 修改）
- **经济测算**: 1,000 意图 = 5 SUI；10,000 意图 = 50 SUI；100,000 意图 = 500 SUI
- **按 SUI = $3 算**: 100K 意图 ≈ **每月 $1,500** 纯协议收入
- **可提现**: 管理员随时可调用 `withdraw_all`；Treasury 之后也可用于质押 / DAO

代码位置：`move/sui_intent_fee/` · 220 行 Move + 240 行测试。

### 1. 交易手续费返佣（DeepBook）
- DeepBook V3 收取 0.10% taker / 0.05% maker
- 聚合日成交量 → 与 DeepBook / Treasury 谈返佣
- **测算**: 日成交量 $1M × 0.05% 返佣 = $500/天 = **每年 $180K**

### 2. 订阅制 AI 信号

| 等级 | 价格 | 功能 |
|---|---|---|
| 免费 | $0 | 5 次/天快问快答，基础 RSI / MACD 读数 |
| Pro | $29/月 | 无限深度分析、多周期共识、自定义指标 |
| Pro+ | $99/月 | 实时告警、自动交易信号、LLM 优先队列 |

### 3. 策略市场
- 用户把策略发布为 PTB 模板（如"RSI<30 时用 100 USDC 买入 SUI，+5% 止盈，-3% 止损"）
- 其它用户订阅 → **70/30 收益分成**（创作者 / 协议）
- 链上战绩（成交、PnL）沉淀创作者信誉
- 长期玩法 — 需要规模，但高毛利

### 4. B2B / API 接入
- 把 **意图解析器** 当作服务卖给其它 DeFi 前端
- 一个借贷协议想加"自动还贷" → 直接调用我们的解析器
- **定价**: $X/月 基础费 + $0.001 / 解析
- API 接口已就绪（`/api/v1/ai/quick-question`）

### 5.（远期）Token 发行
- `SIT` 治理 Token，用于费用分成 + DAO 风险参数覆盖
- 质押者分享协议费
- **不在 Day-1 路线图** — 等产品市场契合后再启动

---

## 🚀 一键启动

```bash
git clone https://github.com/baicaiyihao/sui-intent-engine.git
cd sui-intent-engine
./start.sh           # 自动装依赖，同时拉起 :3000 / :8000 / :8001
# → http://localhost:3000
```

`./start.sh` 按下面顺序自动检测 Python 环境：
1. **`conda:crawl4ai`** — 如果你有名为 `crawl4ai` 的 conda 环境（推荐，与项目一致）
2. **`.venv`** — 仓库根目录下的虚拟环境
3. **全新 `.venv`** — 用系统 Python 3 自动 `python3 -m venv` 创建

首次启动会自动跑 `npm install`。PID 落在 `.pids/`，日志在 `logs/`。`./stop.sh` 停止。

| 层 | URL | 技术 | 是否自动启动 |
|---|---|---|---|
| 前端 | http://localhost:3000 | Vite + React | ✅ via `./start.sh` |
| 后端 A (QuantCore AI) | http://localhost:8000 | FastAPI :8000, Swagger at `/docs` | ✅ via `./start.sh` |
| 后端 B (SuiIntent) | http://localhost:8001 | FastAPI :8001, Swagger at `/docs` | ✅ via `./start.sh` |

**默认语言**: 英文。顶栏的 `中 / EN` 切换器切换。
**钱包**: Sui 主网。通过 Sui Wallet / Suiet / Ethos 连接。交易打到 DeepBook V3 的真实 SUI/USDC 池子。**每个意图支付 0.005 SUI 协议费**到 `0x5e54f169...8ed91`。

无需任何 API Key 也能演示的功能：

| 功能 | 需要后端？ | 需要 LLM Key？ |
|---|---|---|
| 落地页 + 4 步流程 | ❌ | ❌ |
| 实时 SUI/USDC K 线 | ⚠️ 没 :8001 时显示 "OFFLINE" | ❌ |
| 实时订单簿 | ⚠️ 没 :8001 时显示 "OFFLINE" | ❌ |
| 连接钱包（Sui 主网） | ❌ | ❌ |
| 下 DeepBook 订单 | ❌ | ❌ |
| AI 聊天 / 快捷追问 | ✅ | ✅ |
| AI 信号 + 回测 | ✅ | ✅ |

前端 + 链上合约**完全无需配置**即可工作 — 评委可以直接在 SuiVision 验证主网状态。

---

## 🗺️ 路线图

- [x] 自然语言 → PTB → 钱包签名（主网）
- [x] 6 维 Guardian 风险检查
- [x] 双语 UI（zh + en，英文默认）
- [x] 实时 Ticker + 实时 K 线
- [x] Cetus BM 路径（存款 + 下单一笔 PTB）
- [x] 链上协议费（主网发布 · 0.005 SUI / 意图）
- [ ] **下一步**: 策略市场 MVP — 策略以 PTB 模板发布，其它人订阅
- [ ] **下一步**: B2B API 收费层 — `/api/v1/ai/parse` 加鉴权 + 限流 + 计费
- [ ] **未来**: 接入更多池子（USDC/USDT、SUI/USDT、BTC/USDC via DeepBook V3）
- [ ] **未来**: 引入 Move policy object 适配 Agent-Wallet 子赛道（Sub-track 2 crossover）

---

## 🛠 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 18 · TypeScript · Vite 5 · @mysten/dapp-kit |
| 后端 | Python 3 · FastAPI · Uvicorn |
| AI | LLM（双语 prompt 字典）+ Guardian 规则引擎（6 维风险检查） |
| 量化 | Pandas · NumPy · 自研指标库 |
| 链 | Sui SDK（`@mysten/sui`），SuiJsonRpcClient，TransactionBuilder |
| 链上 | **Move 2024.beta** · `sui_intent_fee::protocol_fee`（主网已发布） |
| CLOB | DeepBook V3 主网 · Cetus utils 用于 BM + 存款 + 下单 |
| 数据 | DeepBook V3 indexer（实时）· CCXT（仅用于量化回测） |
| i18n | 自研 Context（零依赖，27 个落地页 key + 300+ 应用 key） |

---

## 📄 License

MIT

---

[English version](./README.md) | 简体中文
