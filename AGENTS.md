# AGENTS.md — SUI Intent Engine

**Project**: SUI Intent Engine (AI-powered natural language DeFi trading on DeepBook V3)  
**Primary Stack**: Python FastAPI (intent + quant) + React + TypeScript + @mysten/dapp-kit (real on-chain execution)  
**Last Major Context Sync**: 2026-05 (this file created after full project scan)

This file exists so that after context compaction, new sessions, or when a subagent joins, anyone can quickly regain deep, accurate understanding of the project.

---

## 1. Project in One Sentence

A system that lets users say things like *"RSI below 30, buy 100 USD of SUI with 2% stop loss"* → parses the intent with LLM + quant analysis → runs multi-factor risk checks (Guardian) → builds a real SUI PTB → executes on **DeepBook V3** (SUI's native central limit order book) with the user's wallet signing.

Core promise: **Intent + Human-in-the-loop + Strong risk guardrails**, not black-box autonomous trading.

---

## 2. Critical Architectural Reality (Must Understand)

This project has **two distinct execution paths** that evolved differently:

### Path A — Python Intent & Analysis Layer (MVP / Product Vision)
- `src/sui_intent_server.py` (FastAPI, port 8001 or 8080)
- `src/ai/` — lightweight `IntentParser` + `Guardian` (risk scoring with RSI/MACD/KDJ/BOLL etc.)
- `src/quant_core/` — full-featured quant engine (analyzer, backtest, strategy compiler, data sources, executors)
- Currently provides: intent parsing, technical analysis, market data proxy, some risk reports
- **DeepBook execution here is mostly mocked** (`src/sui/deepbook_client.py` is a simulation)

### Path B — Frontend Real On-Chain Execution (Where the actual mainnet trading knowledge lives)
- `src/frontend/` (React + Vite + TypeScript)
- Uses `@mysten/dapp-kit` for wallet connection + signing
- Real PTB construction using Cetus DeepBook utils + direct pool calls
- **This is where 90%+ of the painful DeepBook V3 mainnet learning happened**
- AIChatPage.tsx can parse user text, propose orders, and execute real limit/market orders via wallet
- TradingPage.tsx shows live charts, orderbook, positions (data comes from DeepBook indexer + cache)

**Important**: When someone says "make it trade on mainnet", the real work has historically happened in the frontend + the hundreds of test scripts in `src/frontend/scripts/`.

The Python side is stronger at **understanding + analysis**. The frontend is currently stronger at **actual execution**.

---

## 3. How to Run the Project

```bash
# Backend (intent server + quant data)
python -m src.sui_intent_server
# or
python src/sui_intent_server.py

# Frontend (dev)
cd src/frontend
npm run dev

# Full experience: both must be running. Frontend calls backend at /intent/parse etc.
```

Key ports / endpoints (see `sui_intent_server.py` for full list):
- Intent parsing: `POST /intent/parse`
- Risk check: `POST /risk/check`
- Market data proxy to quant_core and DeepBook indexer cache

Frontend talks to both its own backend routes and directly to SUI full nodes + DeepBook indexer for live trading.

---

## 4. Key Directories & What Lives Where

| Path                        | Purpose                                                                 |
|-----------------------------|-------------------------------------------------------------------------|
| `src/ai/`                   | Lightweight intent parser + Guardian risk engine (used by FastAPI)     |
| `src/quant_core/`           | Heavy quant system: analyzer, backtest, indicators, strategy compiler, data collectors, executors |
| `src/sui/`                  | SUI + DeepBook integration (mostly indexer/cache + mock client today)  |
| `src/sui_intent_server.py`  | Main FastAPI surface (intent + risk + market data)                      |
| `src/multi_agent/`          | Experimental internal agent system (Architect PM, Product PM, Engineer) |
| `src/frontend/src/`         | Production UI (AIChatPage + TradingPage + panels)                       |
| `src/frontend/scripts/`     | **Goldmine of DeepBook debugging history** (100+ test scripts)          |
| `docs/`                     | Old architecture/product docs + massive DeepBook V3 contract docs       |
| `CLAUDE.md`                 | Previous long-running DeepBook war log (very valuable raw material)     |

---

## 5. DeepBook V3 Integration — Status & Hard Lessons

This is the hardest part of the project. Do **not** ignore history.

### Current Mainnet Addresses (as of last successful work)
- SUI_USDC Pool: `0xe05dafb5133bcffb8d59f4e12465dc0e9faeaa05e3e342a08fe135800e3e4407`
- Cetus Utils (recommended path): `0x600138d3179e2fc746f6774f360a6e1fa68e90d66d082af66399adabe46f22a4`
- GLOBAL_CONFIG, CETUS_BM_INDEXER, Registry, etc. — see CLAUDE.md for the full table

### Key Hard-Won Truths (preserve these)

1. **BalanceManager (BM) is the center of everything** on DeepBook V3.
   - You must create a BM, deposit assets into it, then trade from it.
   - After `withdraw_all`, the BM often can no longer be used for new orders on the same pool (account registration gets cleared).

2. **`pay_with_deep` matters enormously** on this specific SUI_USDC pool:
   - `false` → whitelist check fails (abort 8)
   - `true` → requires the BM to actually be registered in the pool's accounts map (validate_inputs abort 1)

3. **Cetus BM Indexer registration is not the same as pool account registration.**

4. **Most successful real trades** used patterns like `create_deposit_then_place_limit_order` or direct `pool::place_limit_order` with proper proof + `pay_with_deep=true`.

5. The hundreds of scripts in `frontend/scripts/` contain the actual successful/failed transaction patterns. When in doubt, look there before writing new code.

6. Real execution today lives in `AIChatPage.tsx` and `TradingPage.tsx` + the various `mainnet-*.ts` scripts.

**Never assume "we can just call the Python DeepBookClient for real trades"** — it is still mock.

---

## 6. AI / Quant Systems (Two Layers)

- **Lightweight layer** (`src/ai/`): Fast intent parsing + Guardian risk scoring. Good for the chat → proposal flow.
- **Heavy quant layer** (`src/quant_core/`): Real technical analysis, backtesting, strategy compilation, custom indicators, data collection from exchanges + DeepBook indexer.

The `MarketAnalyzer`, backtest engine, and strategy system in quant_core are quite complete and under-used relative to their capability.

---

## 7. Frontend Structure

- `App.tsx` — simple tab switcher between "AI 策略" (AIChatPage) and "交易" (TradingPage)
- `AIChatPage.tsx` — natural language → proposal → real wallet-signed execution
- `TradingPage.tsx` — professional trading terminal (chart, orderbook, positions, orders, history)
- Uses `lightweight-charts`, real-time ticker/klines from DeepBook indexer cache
- Wallet state via dapp-kit; BalanceManager IDs often stored in localStorage

---

## 8. Multi-Agent System (Internal Tooling)

`src/multi_agent/` contains an experimental orchestrator + specialized agents (Architect PM, Product PM, Engineer).

It was built to let AI agents collaborate on building features inside this repo. It is **not** part of the user-facing product.

Useful when you want to simulate a small team working on a task.

---

## 9. Development Conventions & Practical Rules

- For any non-trivial coding task (3+ distinct steps), use the `todo_write` tool.
- Prefer Plan Mode (`enter_plan_mode`) when architecture or DeepBook integration is ambiguous.
- When doing real on-chain work, expect to look at both:
  - The production components (`AIChatPage.tsx`, `TradingPage.tsx`, panels)
  - The historical scripts in `frontend/scripts/` for proven PTB patterns
- Keep the most important constants (pools, packages, Cetus utils) in one place and reference CLAUDE.md + this file.
- Python backend is primarily for analysis + intent understanding. Don't fight to put real execution there unless the goal is explicitly "move execution to backend".

---

## 10. Common Tasks & Where to Start

| Goal                                    | Best Starting Points |
|-----------------------------------------|----------------------|
| Add new natural language capability     | `src/ai/intent_parser.py` + frontend AIChatPage |
| Improve risk / Guardian logic           | `src/ai/guardian.py` + `src/quant_core/ai/` |
| Add a new technical indicator / strategy| `src/quant_core/strategy/` + `src/quant_core/ai/analyzer.py` |
| Build a new real trading feature        | Study `AIChatPage.tsx` + relevant scripts in `frontend/scripts/` first |
| Debug why an order fails on mainnet     | CLAUDE.md + search the scripts for the exact abort code / function |
| Run backtests or deep quant analysis    | `src/quant_core/` (QuantEngine, BacktestEngine) |
| Understand historical decisions         | `docs/`, old CLAUDE.md, `frontend/SUI_DEEPBOOK_KB.md` |

---

## 11. DeepBook V3 Execution Reference (High Fidelity — Do Not Lose)

This section contains the most important concrete knowledge from months of mainnet debugging. Treat it as ground truth until proven otherwise.

### Core Addresses (Mainnet SUI_USDC)

```typescript
const UTILS_PKG       = '0x600138d3179e2fc746f6774f360a6e1fa68e90d66d082af66399adabe46f22a4'  // Cetus (recommended)
const GLOBAL_CONFIG   = '0xff1141ef80e7baf206c7930c274b465600e64884d8167f90d4cdb60197925163'
const CETUS_BM_INDEXER= '0x5c1a039f97ed1cbd84d54b5d633bdffd681086acc38961b1d366c4ecf680d150'
const SUI_USDC_POOL   = '0xe05dafb5133bcffb8d59f4e12465dc0e9faeaa05e3e342a08fe135800e3e4407'
const USDC_COIN       = '0xdba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC'
const SUI_COIN        = '0x2::sui::SUI'
const DEEP_COIN       = '0xdeeb7a4662eec9f2f3def03fb937a663dddaa2e215b8078a284d026b7946c270::deep::DEEP'
const V1_PKG          = '0x2c8d603bc51326b8c13cef9dd07031a408a48dddb541963357661df5d3204809'  // DeepBook V1
```

**Critical parameters**:
- Tick Size: 0.00001 USDC
- Lot Size: 0.1 SUI
- Min Size: 1 SUI

### The Two Hard Rules (Memorize These)

1. **On this specific SUI_USDC pool**:
   - `pay_with_deep = false` → almost always fails with **abort code 8** (whitelist check)
   - `pay_with_deep = true` → usually fails with **abort code 1** (`order_info::validate_inputs`) because the BM is not registered in the pool's `accounts` dynamic field.

2. **BalanceManager Lifecycle Trap** (the most expensive lesson):
   - After calling `withdraw_all` on a BM, that BM can **no longer be used** for new `place_limit_order` / `place_market_order` on the same pool.
   - `pool::account` is a **view function** — it does not create the account entry.
   - There is currently **no known public entry function** to re-register a BM into a pool's accounts after withdrawal.
   - **Practical rule**: For real user trading, prefer creating a **new BM per trade** (using `create_deposit_then_place...` style) or carefully manage BM lifetime.

### Abort Codes (Most Important)

| Code | Location                        | Meaning                                      | Common Cause |
|------|---------------------------------|----------------------------------------------|--------------|
| 1    | `order_info::validate_inputs`   | `original_quantity < lot_size` **or** BM not registered in pool accounts | Wrong quantity or unregistered BM |
| 8    | `pool::place_order_int`         | Whitelist check failed                       | `pay_with_deep=false` on non-whitelisted pool |

### Current Working Patterns (as of last successful work)

**Frontend (AIChatPage + TradingPage) approach** (this is what actually ships to users):
- Check `localStorage.getItem('balanceManagerId')`
- If none → use Cetus `create_deposit_then_place_limit_order`
- If exists → use `deposit_then_place_limit_order_by_owner`
- User signs with `useSignTransaction` (dapp-kit)
- Note: Frontend currently uses `pay_with_deep = false` in some flows (relies on Cetus utils)

**Direct V1 pattern that has succeeded**:
```typescript
// 1. New BM
const [newBM] = tx.moveCall({ target: `${V1_PKG}::balance_manager::new` });

// 2. Deposit
tx.moveCall({ target: `${V1_PKG}::balance_manager::deposit`, ... });

// 3. Generate proof + place (pay_with_deep = true is mandatory)
const [proof] = tx.moveCall({ target: `${V1_PKG}::balance_manager::generate_proof_as_owner` });
tx.moveCall({
  target: `${V1_PKG}::pool::place_limit_order`,
  arguments: [pool, bm, proof, clientOrderId, 0, 0, price, qty, isBid, true /*pay_with_deep*/, expiration, clock],
  typeArguments: [SUI_COIN, USDC_COIN]
});
```

**After any withdraw_all**: You should generally create a fresh BM for the next trade.

### Recommended References When Working on Trading Features

- Old `CLAUDE.md` (especially sections after "2026-05-27 最新测试结果")
- `src/frontend/src/components/AIChatPage.tsx` (current user-facing execution path)
- `src/frontend/scripts/mainnet-*.ts` and `cetus-*.ts` (proven patterns)
- `frontend/SUI_DEEPBOOK_KB.md`

---

## 12. Known Major Gotchas

- DeepBook V1 vs V6 vs Cetus utils confusion is constant. Always verify which package/pool version a piece of code is talking to.
- BalanceManager lifecycle is subtle — creation + deposit + trade + withdraw has state side effects on the pool.
- The Python mock DeepBook client will lie to you during development.
- Frontend uses localStorage for BM IDs; this can get out of sync with on-chain reality.
- Many "working" patterns only worked for a specific window of time on mainnet.

---

## 13. For Rapid Re-Orientation After Compaction

When you return to this project after context loss, read these in order:

1. **This `AGENTS.md`** (especially sections 2 + 11) — this is now the highest-signal orientation.
2. **Section 11 of this file** (DeepBook V3 Execution Reference) — contains the concrete addresses, abort codes, and BM lifecycle rules.
3. `src/frontend/src/components/AIChatPage.tsx` — current real execution path that users actually use.
4. Old `CLAUDE.md` (the later sections from May 27 onward) — only if you need the full debugging narrative.
5. `src/sui_intent_server.py` + `src/quant_core/` if the task is analysis/quant/intent related.

**First question you should always ask yourself after compaction**:
> "Is the task mostly about **intent parsing + quant analysis + risk** (Python side) **or real on-chain order placement + wallet signing** (frontend + DeepBook PTB)?"

This single distinction will prevent 80% of wasted time on this project.

---

**Maintain this file aggressively.** 

The biggest risk on this project is losing the hard-won DeepBook knowledge. When you learn something new about BM lifecycle, new abort codes, working PTB patterns, or changes in the Cetus utils / pool behavior, update **Section 11** immediately.

This file (especially Section 11) is now the primary artifact for fast recovery after compaction and for any subagent working on trading features.

---

*Full project initialization scan + high-fidelity DeepBook reference added — May 2026.*