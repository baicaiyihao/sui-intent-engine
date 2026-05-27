# DeepBook V3 SDK Documentation

## Overview
DeepBook is a decentralized orderbook on Sui blockchain. This document covers the DeepBook V3 SDK usage.

## Core Components

### 1. DeepBookClient
```typescript
const deepbookClient = new DeepBookClient({
  client: suiClient,
  address: address,
  network: 'testnet' | 'mainnet',
  packageIds: {
    DEEPBOOK_PACKAGE_ID: packageId,
    REGISTRY_ID: registryId,
  },
  coins: {
    SUI: { address, type, scalar },
    DBUSDC: { address, type, scalar },
  },
  pools: {
    SUI_DBUSDC: { address, baseCoin, quoteCoin },
  },
  balanceManagers: {
    'myManager': { address: managerAddress },
  },
})
```

### 2. BalanceManager
BalanceManager is a shared object that holds user funds for trading.

**Key Operations:**
- `generate_proof_as_owner` - Generate proof of ownership for trading
- `deposit` - Deposit coins into BalanceManager
- `withdraw` - Withdraw coins from BalanceManager
- `register_balance_manager` - Register with registry (if needed)

### 3. Pool Operations

#### Market Orders
```typescript
pool.placeMarketOrder({
  poolKey: 'SUI_DBUSDC',
  balanceManagerKey: 'myManager',
  clientOrderId: String(Date.now() % 1000000),
  quantity: BigInt(100000000), // 0.1 SUI
  isBid: false, // false = SELL, true = BUY
  payWithDeep: false,
})(tx)
```

#### Swap Functions
**swap_exact_base_for_quote** - Sell base coin for quote coin
**swap_exact_quote_for_base** - Buy base coin with quote coin
**swapExactBaseForQuote** / **swapExactQuoteForBase** - SDK helpers

### 4. Orderbook Account
Before placing orders, the BalanceManager must be registered with the pool's account system. This causes MoveAbort code 8 if not done.

## Common Errors
- MoveAbort code 8: BalanceManager not registered with pool account
- Missing transaction sender: Use `tx.setSender(address)`
- Insufficient gas: Ensure wallet has enough SUI

## Testnet Configuration
- Network: https://fullnode.testnet.sui.io:443
- Registry: 0xaf16199a2dff736e9f07a845f23c5da6df6f756eddb631aed9d24a93efc4549d
- Pool (SUI_DBUSDC): 0x1c19362ca52b8ffd7a33cee805a67d40f31e6ba303753fd3a4cfdfacea7163a5
