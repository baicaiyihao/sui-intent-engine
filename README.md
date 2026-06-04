# SUI Intent Engine

> **Say your trade. Read the risks. Sign the PTB.**
> A Sui-native intent engine for the Agentic Web.

[![Track](https://img.shields.io/badge/Sui%20Agentic%20Hackathon-Sub--track%2003%20%C2%B7%20Intent%20Engine-c8ff00?style=for-the-badge)](#why-this-sub-track)
[![Live](https://img.shields.io/badge/SUI%20MAINNET-LIVE-00d4aa?style=for-the-badge)](#-demo)
[![Bilingual](https://img.shields.io/badge/i18n-EN%20%C2%B7%20ZH-4da2ff?style=for-the-badge)](README.zh-CN.md)

---

## 🎬 Demo

<div align="center">
  <a href="https://www.youtube.com/watch?v=WVW8DdnqkXY">
    <img src="https://img.youtube.com/vi/WVW8DdnqkXY/maxresdefault.jpg" alt="SUI Intent Engine — 2:35 demo" width="800" />
  </a>
  <br />
  <sub>2:35 — problem · one-command start · landing · AI chat · on-chain SuiVision · roadmap</sub>
</div>

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
- `recommendation`: "Buy" / "Hold" / etc.

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

## 💰 Business Model / Monetization

We plan to monetize in four layered ways. None require changing the core engine.

### 0. **On-Chain Protocol Fee** (live on mainnet)

Every user Intent pays **0.005 SUI** to an on-chain `ProtocolTreasury` shared object via the `sui_intent_fee::protocol_fee` Move module. The fee is charged as the first step of the intent PTB, before the DeepBook trade — same tx, atomic.

- **Mainnet Package**: `0xad95919bbc8e08a36c28bf885fd7e8413296f63979d13b329d8713424157fd90`
- **Mainnet Treasury** (shared): `0x5e54f169aa2df2c3fe2a7624170d1c85feb7ebf9b54f57e51cb80fc84578ed91`
- **Testnet Package**: `0x9e7d5e8048f44773afede881ebb65422c01f686cfe2f141fb7bf9ef002859465`
- **11/11 unit tests passing** · published 2026-06-03
- **Verified on mainnet** — tx `4jGNB1W56Ehfy73nHEyfrK48XxQmWkzcDePVPxehvG1D`

| Event | When | Use |
|---|---|---|
| `FeePaid { payer, amount, intent_type, intent_number }` | every intent | analytics / dashboards |
| `FeeWithdrawn { admin, amount }` | admin sweep | treasury management |
| `FeeUpdated { old_fee, new_fee }` | admin repricing | governance log |
| `AdminTransferred { old_admin, new_admin }` | role change | role handoff |

- **Default fee**: 5,000,000 MIST = 0.005 SUI / intent (admin can change via `set_fee`)
- **Fee-per-intent economics**: 1,000 intents = 5 SUI; 10,000 intents = 50 SUI; 100,000 intents = 500 SUI
- **At SUI = $3**: 100K intents = **~$1,500/month** pure protocol revenue
- **Withdrawable**: admin can call `withdraw_all` at any time; treasury can also be repurposed for staking/DAO later

Source: `move/sui_intent_fee/` · 220 lines Move + 240 lines tests.

### 1. Transaction Fee Rebate (DeepBook)
- DeepBook V3 charges 0.10% taker / 0.05% maker.
- Aggregate daily volume through the intent engine → negotiate fee rebate with DeepBook/treasury.
- **Projection**: $1M daily volume at 0.05% rebate = $500/day = **$180K/year** at scale.

### 2. Premium AI Signals
| Tier | Price | Features |
|---|---|---|
| Free | $0 | 5 quick questions/day, basic RSI/MACD readouts |
| Pro | $29/mo | Unlimited deep analysis, multi-TF consensus, custom indicators |
| Pro+ | $99/mo | Real-time alerts, auto-trade signals, priority LLM |

### 3. Strategy Marketplace
- Users publish strategies as PTB templates (e.g. "RSI < 30, buy 100 USDC SUI, +5% TP, -3% SL")
- Others subscribe → **70/30 revenue split** (creator / protocol)
- On-chain track record (fills, PnL) builds creator reputation
- Long-term play — requires scale, but high-margin

### 4. B2B / API Access
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
| On-chain | **Move 2024.beta** · `sui_intent_fee::protocol_fee` (published mainnet) |
| CLOB | DeepBook V3 mainnet · Cetus utils for BM + deposit + place order |
| Data | DeepBook V3 indexer (live) · CCXT (quant backtest only) |
| i18n | Custom Context (zero deps, 27 landing keys + 300+ app keys) |

---

## 📁 Project Structure

```
sui-intent-engine/
├── move/
│   └── sui_intent_fee/          # ⛓️ Move 2024.beta — protocol fee contract
│       ├── sources/protocol_fee.move   # ProtocolTreasury shared object + pay_fee
│       └── tests/protocol_fee_tests.move  # 11/11 unit tests
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

The fastest path — **one command** brings up the whole stack:

```bash
git clone https://github.com/baicaiyihao/sui-intent-engine.git
cd sui-intent-engine
./start.sh           # auto-installs deps, starts :3000 / :8000 / :8001
# → http://localhost:3000
```

`./start.sh` auto-detects your Python env in this order:
1. **`conda:crawl4ai`** if you have a conda env named `crawl4ai` (recommended — match the project)
2. **`.venv`** at repo root if you have one
3. **fresh `.venv`** auto-created with `python3 -m venv` if you have system Python 3

It also runs `npm install` on first boot. PIDs land in `.pids/`, logs in `logs/`. Shut down with `./stop.sh`.

### What gets started

| Layer | URL | Tech | Auto-starts? |
|---|---|---|---|
| Frontend | http://localhost:3000 | Vite + React | ✅ via `./start.sh` |
| Backend A (QuantCore AI) | http://localhost:8000 | FastAPI :8000, Swagger at `/docs` | ✅ via `./start.sh` |
| Backend B (SuiIntent) | http://localhost:8001 | FastAPI :8001, Swagger at `/docs` | ✅ via `./start.sh` |

### Manual start (per layer)

If you prefer to start each layer by hand — useful for debugging — the project has three independent layers:

#### Layer 1 — Frontend only (always works)
```bash
git clone https://github.com/baicaiyihao/sui-intent-engine.git
cd sui-intent-engine/src/frontend
npm install
npm run dev
# → http://localhost:3000
```

The landing page, Trading UI, K-line chart, and order book all load against **live Sui mainnet** public endpoints. No env, no API key, no backend needed to see the UI.

#### Layer 2 — Intent backend (port 8001, market data + intent parsing)
```bash
cd sui-intent-engine
pip install -r requirements.txt
cp src/.env.example src/.env       # then fill in LLM_API_KEY (optional for market data)
python -m uvicorn src.sui_intent_server:app --host 0.0.0.0 --port 8001
```

#### Layer 3 — Quant/AI backend (port 8000, AI chat + signals)
```bash
# Same env as Layer 2 + needs an LLM API key
python -m uvicorn src.server:app --host 0.0.0.0 --port 8000
```

Needed for AI chat, signal generation, backtest.

### Open <http://localhost:3000>

Default language: **English**. Toggle language in the header (`EN` / `中文`).

**Wallet**: Sui mainnet required. Connect via Sui Wallet / Suiet / Ethos. Trades hit the real SUI/USDC pool on DeepBook V3. **Every intent pays 0.005 SUI protocol fee** to `0x5e54f169...8ed91`.

### What you can demo without any API key

| Feature | Needs backend? | Needs LLM key? |
|---|---|---|
| Landing page + 4-step flow | ❌ | ❌ |
| Live SUI/USDC chart (TradingPage) | ⚠️ shows "OFFLINE" without :8001 | ❌ |
| Live order book (OrderBook) | ⚠️ shows "OFFLINE" without :8001 | ❌ |
| Connect wallet (Sui mainnet) | ❌ | ❌ |
| Place a DeepBook order | ❌ | ❌ |
| AI chat / quick questions | ✅ | ✅ |
| AI signal + backtest | ✅ | ✅ |

The frontend and on-chain contract work **without any setup** — judges can verify the live mainnet state on SuiVision.

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

## 🌐 Other Languages

- [Simplified Chinese (简体中文)](./README.zh-CN.md) — full Chinese translation

---

## 📄 License

MIT
