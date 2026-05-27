import { useState, useEffect, useCallback } from 'react'
import { useCurrentAccount, useSignTransaction, useSuiClient } from '@mysten/dapp-kit'
import { Transaction } from '@mysten/sui/transactions'

const MAINNET_PKG = '0x337f4f4f6567fcd778d5454f27c16c70e2f274cc6377ea6249ddf491482ef497'
const SUI_COIN = '0x2::sui::SUI'

interface Position {
  totalDeposited: number
  totalWithdrawn: number
  currentBalance: number
  openOrdersValue: number
  realizedPnL: number
  trades: TradeRecord[]
}

interface TradeRecord {
  type: 'buy' | 'sell'
  price: number
  quantity: number
  timestamp: number
}

function PositionPanel() {
  const [position, setPosition] = useState<Position>({
    totalDeposited: 0,
    totalWithdrawn: 0,
    currentBalance: 0,
    openOrdersValue: 0,
    realizedPnL: 0,
    trades: []
  })
  const [bmBalance, setBmBalance] = useState<number>(0)
  const [walletBalance, setWalletBalance] = useState<number>(0)
  const [withdrawing, setWithdrawing] = useState(false)
  const account = useCurrentAccount()
  const { mutate: signTransaction } = useSignTransaction()
  const suiClient = useSuiClient()

  const bmId = localStorage.getItem('balanceManagerId') || ''

  // 获取钱包 SUI 余额
  const fetchWalletBalance = useCallback(async () => {
    if (!account?.address) return

    try {
      const balance = await suiClient.getBalance({
        owner: account.address,
        coinType: '0x2::sui::SUI'
      })
      setWalletBalance(Number(balance.totalBalance) / 1e9) // 转换为 SUI
    } catch (e) {
      console.error('Failed to fetch wallet balance:', e)
    }
  }, [account?.address, suiClient])

  // 获取 BalanceManager SUI 余额
  const fetchBMBalance = useCallback(async () => {
    if (!bmId) return

    try {
      // 直接用 getBalance 查询 BM 的 SUI 余额
      const balance = await suiClient.getBalance({
        owner: bmId,
        coinType: '0x2::sui::SUI'
      })
      const suiBalance = Number(balance.totalBalance) / 1e9
      console.log('BM Balance fetched:', suiBalance, 'Raw:', balance.totalBalance)
      setBmBalance(suiBalance)
    } catch (e) {
      console.error('Failed to fetch BM balance:', e)
      setBmBalance(0)
    }
  }, [bmId, suiClient])

  useEffect(() => {
    const deposited = parseFloat(localStorage.getItem('totalDeposited') || '0')
    const withdrawn = parseFloat(localStorage.getItem('totalWithdrawn') || '0')
    const tradesStr = localStorage.getItem('filledTrades')
    const trades: TradeRecord[] = tradesStr ? JSON.parse(tradesStr) : []

    let realizedPnL = 0
    const buys = trades.filter(t => t.type === 'buy')
    const sells = trades.filter(t => t.type === 'sell')

    sells.forEach(sell => {
      const matchingBuy = buys.find(b => b.timestamp < sell.timestamp)
      if (matchingBuy) {
        realizedPnL += (sell.price - matchingBuy.price) * sell.quantity
      }
    })

    setPosition({
      totalDeposited: deposited,
      totalWithdrawn: withdrawn,
      currentBalance: deposited - withdrawn,
      openOrdersValue: parseFloat(localStorage.getItem('openOrdersValue') || '0'),
      realizedPnL,
      trades
    })

    // 获取链上真实余额
    fetchWalletBalance()
    fetchBMBalance()
  }, [fetchWalletBalance, fetchBMBalance])

  const handleWithdrawAll = useCallback(() => {
    if (!account || !bmId) return

    setWithdrawing(true)

    const tx = new Transaction()
    tx.setGasBudget(10000000)
    tx.setSender(account.address)

    const [withdrawn] = tx.moveCall({
      target: `${MAINNET_PKG}::balance_manager::withdraw_all`,
      arguments: [tx.object(bmId)],
      typeArguments: [SUI_COIN],
    })

    tx.transferObjects([withdrawn], account.address)

    signTransaction(
      { transaction: tx as any, chain: 'sui:mainnet' } as any,
      {
        onSuccess: async (result: any) => {
          try {
            const execResult = await suiClient.executeTransactionBlock({
              transactionBlock: result.bytes,
              signature: result.signature,
              options: { showEffects: true }
            })
            if (execResult.effects?.status?.status === 'success') {
              const currentWithdrawn = parseFloat(localStorage.getItem('totalWithdrawn') || '0')
              const currentBalance = position.currentBalance
              localStorage.setItem('totalWithdrawn', (currentWithdrawn + currentBalance).toString())
              setPosition(prev => ({
                ...prev,
                totalWithdrawn: currentWithdrawn + currentBalance,
                currentBalance: 0
              }))
              alert('提取成功！')
            }
          } catch (e) {
            alert('提取失败')
          } finally {
            setWithdrawing(false)
          }
        },
        onError: () => {
          setWithdrawing(false)
        }
      }
    )
  }, [account, bmId, position.currentBalance, signTransaction, suiClient])

  return (
    <div className="card">
      <h2>持仓 & P&L</h2>

      <div className="position-summary">
        <div className="position-item">
          <label>钱包余额 (链上):</label>
          <span className="value">{walletBalance.toFixed(4)} SUI</span>
          <button className="btn btn-small" onClick={fetchWalletBalance}>刷新</button>
        </div>
        <div className="position-item">
          <label>BalanceManager:</label>
          <span className="value">{bmId ? `${bmId.slice(0, 10)}...` : '未设置'}</span>
        </div>
        <div className="position-item">
          <label>BM 余额 (链上):</label>
          <span className="value">{bmBalance.toFixed(4)} SUI</span>
          <button className="btn btn-small" onClick={fetchBMBalance}>刷新</button>
        </div>
      </div>

      <div className="position-stats">
        <div className="stat-card">
          <div className="stat-label">总充值</div>
          <div className="stat-value">{position.totalDeposited.toFixed(4)} SUI</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">已提取</div>
          <div className="stat-value">{position.totalWithdrawn.toFixed(4)} SUI</div>
        </div>
        <div className="stat-card highlight">
          <div className="stat-label">当前余额</div>
          <div className="stat-value">{position.currentBalance.toFixed(4)} SUI</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">挂单中</div>
          <div className="stat-value">{position.openOrdersValue.toFixed(4)} SUI</div>
        </div>
      </div>

      <div className="pnl-section">
        <h3>交易统计</h3>
        <div className="pnl-stats">
          <div className="pnl-item">
            <label>成交次数:</label>
            <span>{position.trades.length} 次</span>
          </div>
          <div className="pnl-item">
            <label>买入:</label>
            <span>{position.trades.filter(t => t.type === 'buy').length} 次</span>
          </div>
          <div className="pnl-item">
            <label>卖出:</label>
            <span>{position.trades.filter(t => t.type === 'sell').length} 次</span>
          </div>
        </div>

        <div className="realized-pnl">
          <label>实现盈亏:</label>
          <span className={position.realizedPnL >= 0 ? 'profit' : 'loss'}>
            {position.realizedPnL >= 0 ? '+' : ''}{position.realizedPnL.toFixed(4)} USDC
          </span>
        </div>
      </div>

      {position.currentBalance > 0 && (
        <button
          className="btn btn-primary"
          onClick={handleWithdrawAll}
          disabled={withdrawing || !account || !bmId}
        >
          {withdrawing ? '提取中...' : '全部提取到钱包'}
        </button>
      )}
    </div>
  )
}

export default PositionPanel
