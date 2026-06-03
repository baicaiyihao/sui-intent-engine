# SUI Intent Engine

> **Say your trade. Read the risks. Sign the PTB.**
> A Sui-native intent engine for the Agentic Web.

[![Track](https://img.shields.io/badge/Sui%20Agentic%20Hackathon-Sub--track%2003%20%C2%B7%20Intent%20Engine-c8ff00?style=for-the-badge)](#why-this-sub-track)
[![Live](https://img.shields.io/badge/SUI%20MAINNET-LIVE-00d4aa?style=for-the-badge)](#demo)
[![Bilingual](https://img.shields.io/badge/i18n-EN%20%C2%B7%20ZH-4da2ff?style=for-the-badge)](#)

---

## ⚡ TL;DR

You say *"buy 1 SUI if RSI < 30 with 2% slippage"* in plain English. The engine:

1. **PARSE** — compiles it into a structured intent with LLM
2. **GUARD** — runs a 6-dimension risk check (RSI · MACD · Bollinger · KDJ · Volume · ADX) and surfaces slippage / concentration / weak trends / low liquidity in plain language
3. **PREVIEW** — shows you the human-readable PTB card: price, size, total cost, expiry, balance check
4. **SIGN** — you confirm, your wallet signs, **DeepBook V3 executes on Sui mainnet**

No black boxes. No autonomous agents running wild. The user stays in the loop — every step visible, every step reversible.

---

## 🎯 Why This Sub-track

**Track**: [Sui Agentic Hackathon — Agentic Web → Sub-track 3: Intent Engine](https://sui.io/hackathon)

| Sub-track 3 "must have" | How we deliver |
|---|---|
| Text → PTB → execution flow | `AIChatPage` + `sui_intent_server.py` LLM parser + `Transaction` builder + dapp-kit `signTransaction` |
| Human-readable PTB preview | `proposal` card: price, size, total, expiry, balance check, all in plain language |
| Guardian catching ≥ 2 risk classes | **6 checks** in `src/ai/guardian.py`: RSI, MACD, Bollinger Bands, KDJ, Volume ratio, ADX |
| Explicit confirmation step | `proposal-actions` button group: `Confirm` / `Cancel` — wallet signature required |

**This is not a swap chatbot.** The Guardian layer is the product. The AI proposes, the indicators veto, the human decides.

---

## 🌊 Why Sui (not "Sui as a payment rail")

We use Sui as the AI substrate, not a bolt-on:

- **PTB (Programmable Transaction Blocks)** — one atomic transaction composes `deposit + place_limit_order` (via Cetus BM path) or `withdraw + sign + execute`. No multi-tx fragility.
- **DeepBook V3** — Sui's native CLOB. We hit it with real limit + market orders. **Not a mock.**
- **dapp-kit wallet signing** — every user-facing action is an explicit `useSignTransaction` call. Intent engine ≠ autonomous agent. The human owns the keys.
- **Mainnet verifiable** — balance, order book, ticker all live from `https://fullnode.mainnet.sui.io:443` and the DeepBook V3 indexer. No sim.

---

## 🔁 The Intent Flow (4 steps)

```
  you                    us                              chain
  ───                    ──                              ─────
  "Buy 1 SUI     ───►  PARSE     ───►  structured intent
   if RSI<30,            LLM          (action, size, price, condition)
   2% slip"
                       GUARD     ───►  risk_report
                         6-dim       (risk_level: low/med/high/critical,
                         Guardian     warnings: [...], can_proceed: bool)

                       PREVIEW   ───►  PTB card
                         build PTB    (price, qty, total, expiry,
                                       balance check, est. gas)

   [ Confirm ]    ◄──  SIGN
   wallet popup          signTransaction
   user approves         ───►  DeepBook V3 execute on mainnet
```

Every step lives in code: `src/ai/intent_parser.py`, `src/ai/guardian.py`, `src/frontend/src/components/AIChatPage.tsx`.

---

## 🛡️ Guardian — 6-Dimension Risk Check

`src/ai/guardian.py` — the differentiator.

| # | Check | What it catches | Configurable threshold |
|---|---|---|---|
| 1 | **RSI** | Overbought / oversold reversals | `rsi_oversold=30, rsi_overbought=70` |
| 2 | **MACD** | Golden / death cross trend flips | `histogram > 0 = bullish` |
| 3 | **Bollinger** | Price at band extremes (volatility squeeze) | `boll_low=0.2, boll_high=0.8` |
| 4 | **KDJ** | Short-term stochastic reversal | `kdj_oversold=20, kdj_overbought=80` |
| 5 | **Volume** | Abnormal liquidity / low conviction moves | `volume_ratio_low=0.5, _high=1.5` |
| 6 | **ADX** | Trend strength (chop vs. real move) | `adx_weak=20, adx_strong=25` |

Each check returns a `RiskCheck` with `status` (pass / warn / fail) and a human-readable `message`. The aggregate `RiskReport` includes:
- `risk_level`: `low | medium | high | critical`
- `risk_score`: weighted sum (-100 to +100)
- `can_proceed`: `bool` — `false` for `high`/`critical` levels
- `warnings`: list of plain-language risks
- `recommendation`: "建议买入" / "建议暂缓" / etc.

The frontend's `proposal-actions` step refuses to enable the **Confirm** button if `can_proceed == false` and shows the warnings inline.

---

## ✨ Project Highlights

| | |
|---|---|
| 🎨 **Bilingual UI** | First-class `zh` + `en` i18n. 27 landing keys + 300+ app keys, EN default for international judges |
| ⚡ **Real-time data** | Live ticker / K-lines from DeepBook V3 indexer, polled every 1–3s |
| 🔐 **No custodial risk** | User wallet signs every PTB. We never hold keys. The BalanceManager lifecycle is on-chain. |
| 🧠 **LLM bilingual** | Backend `language` param switches prompt dicts — no more "answer in Chinese despite English toggle" |
| 📊 **Quant depth** | RSI / MACD / KDJ / Bollinger / Volume / ADX + multi-timeframe consensus |
| 🏗️ **Mainnet-verified** | Documented working transactions on SUI/USDC pool (limit + market orders, deposit, withdraw) |
| 🌐 **DeFi-native** | Cetus BM path for BM creation + deposit + order in one PTB |
| 📐 **Production UX** | Bloomberg-terminal landing page with live ticker, 3-line statement, 4-step flow visualization |

---

## 💰 Business Model / Monetization (盈利方向)

We plan to monetize in four layered ways. None require changing the core engine.

### 1. Transaction Fee Rebate (核心收入)
- DeepBook V3 charges 0.10% taker / 0.05% maker.
- Aggregate daily volume through the intent engine → negotiate fee rebate with DeepBook/treasury.
- **Projection**: $1M daily volume at 0.05% rebate = $500/day = **$180K/year** at scale.

### 2. Premium AI Signals (订阅制)
| Tier | Price | Features |
|---|---|---|
| Free | $0 | 5 quick questions/day, basic RSI/MACD readouts |
| Pro | $29/mo | Unlimited deep analysis, multi-TF consensus, custom indicators |
| Pro+ | $99/mo | Real-time alerts, auto-trade signals, priority LLM |

### 3. Strategy Marketplace (策略市场)
- Users publish strategies as PTB templates (e.g. "RSI < 30, buy 100 USDC SUI, +5% TP, -3% SL")
- Others subscribe → **70/30 revenue split** (creator / protocol)
- On-chain track record (fills, PnL) builds creator reputation
- Long-term play — requires scale, but high-margin

### 4. B2B / API Access (白标)
- Sell the **intent parser** as a service to other DeFi frontends
- A lending protocol wants "repay my loan" → use our parser
- **Pricing**: $X/month base + $0.001 per parse
- We already have the multi-tenant-ready API surface (`/api/v1/ai/quick-question`)

### 5. (Long-term) Token Launch
- `SIT` governance token for fee-sharing + DAO override of risk parameters
- Stakers receive share of protocol fees
- **Not on day-1 roadmap** — only after product-market fit

---

## 🏗️ Tech Stack

| Layer | Tech |
|---|---|
| Frontend | React 18 · TypeScript · Vite 5 · @mysten/dapp-kit |
| Backend | Python 3 · FastAPI · Uvicorn |
| AI | LLM (bilingual prompt dicts) + Guardian rule engine (6 risk checks) |
| Quant | Pandas · NumPy · custom indicator library |
| Chain | Sui SDK (`@mysten/sui`), SuiJsonRpcClient, TransactionBuilder |
| CLOB | DeepBook V3 mainnet · Cetus utils for BM + deposit + place order |
| Data | DeepBook V3 indexer (live) · CCXT (quant backtest only) |
| i18n | Custom Context (zero deps, 27 landing keys + 300+ app keys) |

---

## 📁 Project Structure

```
sui-intent-engine/
├── docs/                        # Technical documentation
│   ├── ARCHITECTURE.md
│   ├── PRODUCT.md
│   ├── deepbookv3/              # DeepBook V3 contract docs
│   └── deepbookv3-sdk/          # SDK docs
├── src/
│   ├── frontend/                # React + TypeScript UI
│   │   └── src/
│   │       ├── components/
│   │       │   ├── LandingPage.tsx     # Entry: track badge + 4-step flow + live ticker
│   │       │   ├── AIChatPage.tsx      # Natural language → PTB → sign
│   │       │   ├── AIStrategyPage.tsx  # Multi-TF consensus + AI signal
│   │       │   ├── TradingPage.tsx     # Live CLOB + charts
│   │       │   ├── OrderBook.tsx
│   │       │   ├── MarketChart.tsx
│   │       │   ├── DepositPanel.tsx    # Cetus BM deposit
│   │       │   ├── OrdersPanel.tsx
│   │       │   ├── HistoryPanel.tsx
│   │       │   ├── PositionPanel.tsx
│   │       │   ├── VaultPanel.tsx
│   │       │   └── i18n/I18nProvider.tsx
│   ├── ai/                      # Intent + Guardian
│   │   ├── intent_parser.py
│   │   └── guardian.py          # 6-dimension risk engine
│   ├── quant_core/              # Quant engine (analyzer, backtest, strategy compiler)
│   ├── sui/                     # DeepBook integration
│   ├── multi_agent/             # Internal: multi-agent dev tooling
│   ├── sui_intent_server.py     # FastAPI :8001 — intent + market data
│   └── server.py                # FastAPI :8000 — quant + AI analysis
├── AGENTS.md                    # Project orientation (canonical)
└── README.md                    # ← you are here
```

---

## 🚀 Quick Start

```bash
# Backend (intent server, port 8001)
cd /Users/stom698/git/QuantDinger/sui-intent-engine
python -m src.sui_intent_server

# Quant / AI server (port 8000) — needed for AI signals + backtest
python -m uvicorn server:app --host 0.0.0.0 --port 8000

# Frontend (dev, port 3000)
cd src/frontend
npm install
npm run dev
```

Open <http://localhost:3000>. Default language is **English**. Toggle `中 / EN` in the header.

**Test wallet**: Sui mainnet required. Connect via Sui Wallet / Suiet / Ethos. Trades hit the real SUI/USDC pool on DeepBook V3.

---

## 🗺️ Roadmap

- [x] Natural language → PTB → wallet sign (mainnet)
- [x] 6-dimension Guardian risk check
- [x] Bilingual UI (zh + en, EN default)
- [x] Live ticker + live K-lines
- [x] Cetus BM path (deposit + place order in one PTB)
- [ ] **Next**: Strategy marketplace MVP — publish a strategy as a PTB template, others subscribe
- [ ] **Next**: B2B API tier — `/api/v1/ai/parse` with auth + rate limit + billing
- [ ] **Future**: More pools (USDC/USDT, SUI/USDT, BTC/USDC via DeepBook V3)
- [ ] **Future**: Move policy object for agent-wallet sub-track (Sub-track 2 crossover)

---

## 🇨🇳 中文版简介

**SUI Intent Engine** 是一款基于 Sui 原生 CLOB (DeepBook V3) 的 **意图引擎**，专为 [Sui Agentic Hackathon · 赛道三 · 意图引擎] 而构建。

**核心循环（4 步）**：

1. **解析 (PARSE)** — 你用自然语言描述交易意图。LLM 将其编译为结构化意图（动作 / 金额 / 价格 / 触发条件）。
2. **守护 (GUARD)** — Guardian 跑 6 维风险检查：RSI · MACD · 布林带 · KDJ · 成交量 · ADX。用大白话告诉你哪里有风险：滑点、弱趋势、低流动性、趋势反转。
3. **预览 (PREVIEW)** — 人类可读的 PTB 卡片：价格、数量、总成本、过期时间、余额校验。无黑盒。
4. **签名 (SIGN)** — 你显式确认。钱包签名。DeepBook V3 在 Sui 主网执行 PTB。

**为什么是 Sub-track 3**：
- ✅ 自然语言 → PTB → 执行
- ✅ 人类可读的 PTB 预览
- ✅ Guardian 覆盖 **6 维风险**（远超 2 维要求）
- ✅ 用户显式确认，钱包签名

**商业化**（4 层）：
1. 交易手续费返佣 — DeepBook V3 收取 0.05–0.10% 手续费，聚合流量可谈返佣
2. 订阅制 AI 信号 — Free / Pro $29 / Pro+ $99
3. 策略市场 — 用户发布 PTB 模板，订阅分成 70/30
4. B2B / API 接入 — 卖给其他 DeFi 前端

详见上方英文版各章节。

---

## 📄 License

MIT
