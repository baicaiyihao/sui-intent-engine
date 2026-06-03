import { useState, useEffect, useCallback } from 'react'
import { useCurrentAccount, useSuiClient } from '@mysten/dapp-kit'
import { useI18n } from '../i18n/I18nProvider'

const USDC_COIN = '0xdba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC'

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
  const [bmSuiBalance, setBmSuiBalance] = useState<number>(0)
  const [bmUsdcBalance, setBmUsdcBalance] = useState<number>(0)
  const [walletSuiBalance, setWalletSuiBalance] = useState<number>(0)
  const [walletUsdcBalance, setWalletUsdcBalance] = useState<number>(0)
  const [loading, setLoading] = useState(false)
  const account = useCurrentAccount()
  const suiClient = useSuiClient()
  const { t } = useI18n()

  const bmId = localStorage.getItem('balanceManagerId') || ''

  // Fetch wallet SUI and USDC balances
  const fetchWalletBalances = useCallback(async () => {
    if (!account?.address) return

    try {
      const [suiBalance, usdcBalance] = await Promise.all([
        suiClient.getBalance({
          owner: account.address,
          coinType: '0x2::sui::SUI'
        }),
        suiClient.getBalance({
          owner: account.address,
          coinType: USDC_COIN
        })
      ])
      setWalletSuiBalance(Number(suiBalance.totalBalance) / 1e9)
      setWalletUsdcBalance(Number(usdcBalance.totalBalance) / 1e6)
    } catch (e) {
      console.error('Failed to fetch wallet balances:', e)
    }
  }, [account?.address, suiClient])

  // Fetch BalanceManager SUI and USDC balances
  const fetchBMBalances = useCallback(async () => {
    if (!bmId) return

    setLoading(true)
    try {
      const [suiBalance, usdcBalance] = await Promise.all([
        suiClient.getBalance({
          owner: bmId,
          coinType: '0x2::sui::SUI'
        }),
        suiClient.getBalance({
          owner: bmId,
          coinType: USDC_COIN
        })
      ])
      const suiBal = Number(suiBalance.totalBalance) / 1e9
      const usdcBal = Number(usdcBalance.totalBalance) / 1e6
      console.log('BM Balances fetched - SUI:', suiBal, 'USDC:', usdcBal)
      setBmSuiBalance(suiBal)
      setBmUsdcBalance(usdcBal)
    } catch (e) {
      console.error('Failed to fetch BM balances:', e)
      setBmSuiBalance(0)
      setBmUsdcBalance(0)
    } finally {
      setLoading(false)
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

    // Fetch real on-chain balances
    fetchWalletBalances()
    fetchBMBalances()
  }, [fetchWalletBalances, fetchBMBalances])

  const handleRefresh = useCallback(() => {
    fetchWalletBalances()
    fetchBMBalances()
  }, [fetchWalletBalances, fetchBMBalances])

  return (
    <div className="card">
      <div className="card-header">
        <h2>{t('position.title')}</h2>
        <button
          className="btn btn-small"
          onClick={handleRefresh}
          disabled={loading}
        >
          {loading ? t('position.refreshing') : t('position.refresh')}
        </button>
      </div>

      <div className="balance-section">
        <h3>{t('position.walletBalances')}</h3>
        <div className="balance-grid">
          <div className="balance-item">
            <label>SUI</label>
            <span className="balance-value">{walletSuiBalance.toFixed(4)}</span>
          </div>
          <div className="balance-item">
            <label>USDC</label>
            <span className="balance-value">{walletUsdcBalance.toFixed(4)}</span>
          </div>
        </div>
      </div>

      <div className="balance-section">
        <h3>{t('position.bm')}</h3>
        <div className="bm-info">
          <span className="bm-id">{bmId ? bmId.slice(0, 10) + '...' : t('position.bmNotSet')}</span>
        </div>
        <div className="balance-grid">
          <div className="balance-item">
            <label>SUI</label>
            <span className="balance-value highlight">{bmSuiBalance.toFixed(4)}</span>
          </div>
          <div className="balance-item">
            <label>USDC</label>
            <span className="balance-value highlight">{bmUsdcBalance.toFixed(4)}</span>
          </div>
        </div>
      </div>

      <div className="position-stats">
        <div className="stat-card">
          <div className="stat-label">{t('position.totalDeposited')}</div>
          <div className="stat-value">{position.totalDeposited.toFixed(4)} SUI</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">{t('position.totalWithdrawn')}</div>
          <div className="stat-value">{position.totalWithdrawn.toFixed(4)} SUI</div>
        </div>
        <div className="stat-card highlight">
          <div className="stat-label">{t('position.currentBalance')}</div>
          <div className="stat-value">{position.currentBalance.toFixed(4)} SUI</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">{t('position.openOrdersValue')}</div>
          <div className="stat-value">{position.openOrdersValue.toFixed(4)} SUI</div>
        </div>
      </div>

      <div className="pnl-section">
        <h3>{t('position.tradeStats')}</h3>
        <div className="pnl-stats">
          <div className="pnl-item">
            <label>{t('position.tradeCount')}</label>
            <span>{position.trades.length}{t('position.tradeCountUnit')}</span>
          </div>
          <div className="pnl-item">
            <label>{t('position.buyCount')}</label>
            <span>{position.trades.filter(t => t.type === 'buy').length}{t('position.tradeCountUnit')}</span>
          </div>
          <div className="pnl-item">
            <label>{t('position.sellCount')}</label>
            <span>{position.trades.filter(t => t.type === 'sell').length}{t('position.tradeCountUnit')}</span>
          </div>
        </div>

        <div className="realized-pnl">
          <label>{t('position.realizedPnL')}</label>
          <span className={position.realizedPnL >= 0 ? 'profit' : 'loss'}>
            {position.realizedPnL >= 0 ? '+' : ''}{position.realizedPnL.toFixed(4)} USDC
          </span>
        </div>
      </div>

      <div className="hint-text">
        <small>{t('position.withdrawHint')}</small>
      </div>
    </div>
  )
}

export default PositionPanel
