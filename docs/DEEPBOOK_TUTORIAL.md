# DeepBook V3 交易指南

## 概述

DeepBook V3 是 Sui 上的去中心化订单簿，支持 AMM 风格的 swap 交易。

## 核心概念

### 1. BalanceManager (余额管理器)
- 用于存储交易资金的核心合约
- 需要先存入资金才能进行交易
- 支持 SUI、DBUSDC、DEEP 等代币

### 2. Pool (资金池)
- 存储订单簿流动性的池子
- 包含订单簿和 AMM 曲线
- Vault 存储实际的代币余额

### 3. Account (账户)
- 每个 BalanceManager 在每个 Pool 中都有一个账户
- 账户记录该 BalanceManager 在该池中的挂单

## 交易流程

### 方法一：使用 BalanceManager 交易（推荐）

**步骤 1: 存入资金到 BalanceManager**

```typescript
import { DeepBookClient } from '@mysten/deepbook-v3'

const client = new DeepBookClient({...})

// 存入 SUI 到 BalanceManager
const tx = new Transaction()
tx.setGasBudget(10000000)

client.balanceManager.depositIntoManager({
  managerKey: 'myManager',
  coinKey: 'SUI',
  amountToDeposit: 1, // 1 SUI
})(tx)
```

**步骤 2: 注册 BalanceManager 到 Pool**

```typescript
// 使用 SDK 注册
client.balanceManager.registerBalanceManager('myManager')(tx)
```

**步骤 3: 使用 BalanceManager 资金交易**

```typescript
// 交易需要 capabilites (tradeCap, depositCap, withdrawCap)
// 这些需要先 mint
const tx = new Transaction()

// Mint capabilities
const tradeCap = tx.add(client.balanceManager.mintTradeCap('myManager'))
const depositCap = tx.add(client.balanceManager.mintDepositCap('myManager'))
const withdrawCap = tx.add(client.balanceManager.mintWithdrawalCap('myManager'))

// 使用 swapExactBaseForQuoteWithManager
const [baseOut, quoteOut] = client.deepBook.swapExactBaseForQuoteWithManager({
  poolKey: 'SUI_DBUSDC',
  balanceManagerKey: 'myManager',
  amount: 0.1, // 0.1 SUI
  minOut: 0.1, // 最小获得 0.1 DBUSDC
  tradeCap,
  depositCap,
  withdrawCap,
})(tx)
```

### 方法二：直接使用钱包交易（有问题）

**警告**: SDK 的 `swapExactBaseForQuote` 使用 `coinWithBalance` 创建虚拟币，不会消耗实际资金。

```typescript
// 这个方法有 bug - swap 成功了但没有实际交易
const tx = new Transaction()
const [baseOut, quoteOut, deepOut] = client.deepBook.swapExactBaseForQuote({
  poolKey: 'SUI_DBUSDC',
  amount: 0.1,
  deepAmount: 0.01,
  minOut: 0.1,
})(tx)
```

**问题**: `coinWithBalance` 创建的币是"虚拟"的，不会消耗钱包里的实际代币。

## 已知问题

### 1. Testnet Package 版本不匹配

**发现**: Testnet 上存在两个 DeepBook V3 包版本：

| 版本 | Package ID | 用途 |
|------|------------|------|
| 旧包 | `0xfb28c4cbc6865bd1c897d26aecbe1f8792d1509a20ffec692c800660cbec6982` | Pool 创建于此版本 |
| 新包 | `0x22be4cade64bf2d02412c7e8d0e8beea2f78828b948118d46735315409371a3c` | deposit/withdraw 可用 |

**问题**:
- Pool (`0x1c19362ca52b8ffd7a33cee805a67d40f31e6ba303753fd3a4cfdfacea7163a5`) 类型为 `0xfb28c4...::pool::Pool`，用旧包创建
- BalanceManager 存款使用新包的 `deposit` 函数
- 两个包的 storage 隔离，不能直接互通

**验证的可用函数**:
- ✅ `balance_manager::deposit` (新包)
- ✅ `balance_manager::withdraw` (旧包)
- ✅ `pool::swap_exact_base_for_quote` (旧包，但有问题)
- ❌ `pool::register_balance_manager` (不存在)
- ❌ `pool::create_account` (不存在)

### 2. Swap 执行成功但不改变余额

**现象**: 调用 `pool::swap_exact_base_for_quote` 返回成功，但钱包余额不变。

**可能原因**:
1. Pool 的 vault 余额只是记账数据，不是实际代币
2. Testnet 包的 swap 逻辑有缺陷
3. 需要先调用其他初始化函数

**验证**:
- SDK 的 `getQuoteQuantityOut(0.1 SUI)` 正确返回 `0.1284 DBUSDC`
- 直接调用 `swap_exact_base_for_quote` 返回成功
- 但 `getQuoteQuantityOut` 可能是只读查询，不依赖实际合约状态

**严重**: Testnet 部署的 DeepBook V3 合约缺少 SDK 期望的多个函数：

| 函数 | 状态 |
|------|------|
| `register_balance_manager` | ❌ 不存在 |
| `create_account` | ❌ 不存在 |
| `add_balance_to_pool` | ❌ 不存在 |
| `mint_deposit_cap` | ❌ 不存在 |
| `mint_withdrawal_cap` | ❌ 不存在 |
| `account_exists` | ❌ 不存在 |

这导致 BalanceManager 无法在 testnet 上正常使用。

### 2. Swap 不消耗实际资金

调用 `swapExactBaseForQuote` 交易成功但余额不变。

**原因**: SDK 内部使用 `coinWithBalance` 创建输入币，而不是从钱包获取。

**解决**: 需要使用真实硬币作为输入，或者使用 BalanceManager（但需要上述函数支持）。

### 3. Gas Coin 冲突

在交易中使用 `setGasPayment` 和 `splitCoins` 时，不能使用同一硬币对象。

```
Error: Mutable object cannot appear more than one in one transaction
```

**解决**: 需要两个独立的硬币 - 一个用于 gas，一个用于 swap 输入。

### 4. 订单验证失败

即使使用 `placeLimitOrder`，也会因验证失败被拒绝：

```
MoveAbort(order_info::validate_inputs, 1)
```

可能原因：
- BalanceManager 未在池中注册账户
- Testnet 包的验证逻辑与 SDK 不兼容

## 建议解决方案

1. **等待 testnet 更新** - Mysten 可能需要更新 testnet 合约以匹配 SDK
2. **使用 Devnet** - Devnet可能有更新的合约
3. **直接调用合约** - 需要自己实现缺少的函数
4. **联系 DeepBook 团队** - 确认 testnet 合约状态

## 配置

```json
{
  "network": "testnet",
  "wallet": {
    "address": "0x...",
    "privateKey": "suiprivkey1..."
  },
  "balanceManager": {
    "address": "0x224c3c4f2ab69d3d13e22db653ade2f3efd301b50363c2a7c286ca1876bff504"
  },
  "deepbook": {
    "packageId": "0xfb28c4cbc6865bd1c897d26aecbe1f8792d1509a20ffec692c800660cbec6982",
    "registryId": "0x7c256edbda983a2cd6f946655f4bf3f00a41043993781f8674a7046e8c0e11d1",
    "pools": {
      "SUI_DBUSDC": "0x1c19362ca52b8ffd7a33cee805a67d40f31e6ba303753fd3a4cfdfacea7163a5"
    }
  }
}
```

## 池子状态

Pool: SUI_DBUSDC
- Vault 余额: 4141.8 SUI, 2590.7 DBUSDC
- 中间价: 1.29
- 订单簿:
  - Bids: [1.284, 1.277]
  - Asks: [1.296, 1.303, ...]

## 测试网络资源

- DeepBook Package: `0xfb28c4cbc6865bd1c897d26aecbe1f8792d1509a20ffec692c800660cbec6982`
- Registry: `0x7c256edbda983a2cd6f946655f4bf3f00a41043993781f8674a7046e8c0e11d1`
- Pool (SUI_DBUSDC): `0x1c19362ca52b8ffd7a33cee805a67d40f31e6ba303753fd3a4cfdfacea7163a5`
- DEEP Token: `0x36dbef866a1d62bf7328989a10fb2f07d769f4ee587c0de4a0a256e57e0a58a8`
- DBUSDC: `0xf7152c05930480cd740d7311b5b8b45c6f488e3a53a11c3f74a6fac36a52e0d7`
