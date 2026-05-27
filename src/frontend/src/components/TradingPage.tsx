import { useState, useEffect, useCallback } from 'react'
import { useCurrentAccount, useSuiClient } from '@mysten/dapp-kit'
import DepositPanel from './DepositPanel'
import OrdersPanel from './OrdersPanel'
import HistoryPanel from './HistoryPanel'
import MarketChart from './MarketChart'
import OrderBook from './OrderBook'

type BottomTab = 'open' | 'history' | 'trades'

const API_BASE = 'http://localhost:8001'

function TradingPage() {
  const [bottomTab, setBottomTab] = useState<BottomTab>('open')
  const [bmBalance, setBmBalance] = useState(0)
  const [walletBalance, setWalletBalance] = useState(0)
  const [ticker, setTicker] = useState<{lastPrice: number, priceChangePercent: number} | null>(null)
  const account = useCurrentAccount()
  const suiClient = useSuiClient()

  const fetchTicker = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/cache/ticker`)
      const result = await response.json()
      if (result.success && result.data) {
        setTicker({
          lastPrice: result.data.last_price,
          priceChangePercent: result.data.price_change_percent
        })
      }
    } catch (e) {
      console.error('Failed to fetch ticker:', e)
    }
  }, [])

  useEffect(() => {
    if (account) {
      fetchTicker()
      const interval = setInterval(fetchTicker, 10000)
      return () => clearInterval(interval)
    }
  }, [account, fetchTicker])

  // Scan for BalanceManagers from transaction history
  const scanForBM = useCallback(async () => {
    if (!account?.address) return

    try {
      // Query recent transactions
      const txResp = await fetch('https://fullnode.mainnet.sui.io:443', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jsonrpc: '2.0',
          id: 1,
          method: 'suix_queryTransactionBlocks',
          params: { query: { sender: account.address }, limit: 50, order: 'descending' }
        })
      })
      const txData = await txResp.json()

      const bms = new Set<string>()

      for (const tx of txData.result?.data || []) {
        const txResp2 = await fetch('https://fullnode.mainnet.sui.io:443', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            jsonrpc: '2.0',
            id: 1,
            method: 'sui_getTransactionBlock',
            params: { digest: tx.digest, options: { showEvents: true } }
          })
        })
        const txDetail = await txResp2.json()

        for (const event of txDetail.result?.events || []) {
          const json = event.parsedJson || {}
          if (json.balance_manager_id) bms.add(json.balance_manager_id)
          if (json.deepbook_balance_manager_id) bms.add(json.deepbook_balance_manager_id)
        }
      }

      // Update stored BM ID if we found one
      const bmArray = [...bms]
      if (bmArray.length > 0) {
        localStorage.setItem('balanceManagerId', bmArray[0])
        console.log('Found and updated BM ID:', bmArray[0])
        return bmArray[0]
      }
    } catch (e) {
      console.error('Error scanning for BMs:', e)
    }
    return null
  }, [account?.address])

  // Scan for BMs on mount
  useEffect(() => {
    if (account?.address) {
      const storedBmId = localStorage.getItem('balanceManagerId')
      if (!storedBmId) {
        console.log('No BM ID stored, scanning...')
        scanForBM()
      }
    }
  }, [account?.address, scanForBM])

  const fetchBalances = useCallback(async () => {
    const storedBmId = localStorage.getItem('balanceManagerId') || ''

    if (account?.address) {
      try {
        const balance = await suiClient.getBalance({
          owner: account.address,
          coinType: '0x2::sui::SUI'
        })
        setWalletBalance(Number(balance.totalBalance) / 1e9)
      } catch (e) {
        console.error('Failed to fetch wallet balance:', e)
      }
    }

    // Fetch BM balance using direct RPC call (BM uses Bag, not Coin objects)
    if (storedBmId) {
      try {
        const response = await fetch('https://fullnode.mainnet.sui.io:443', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            jsonrpc: '2.0',
            id: 1,
            method: 'sui_getObject',
            params: [storedBmId, { showContent: true }]
          })
        })
        const data = await response.json()

        if (data.result?.data) {
          const fields = data.result.data.content?.fields
          const bagSize = parseInt(fields?.balances?.fields?.size || '0')

          if (bagSize > 0) {
            const bagId = fields.balances.fields.id.id

            // Get first dynamic field to get SUI balance
            const fieldsResp = await fetch('https://fullnode.mainnet.sui.io:443', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                jsonrpc: '2.0',
                id: 1,
                method: 'suix_getDynamicFields',
                params: [bagId, null, 10]
              })
            })
            const fieldsData = await fieldsResp.json()

            let bmSuiBalance = 0
            for (const field of fieldsData.result?.data || []) {
              if (field.objectId) {
                const valResp = await fetch('https://fullnode.mainnet.sui.io:443', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                    jsonrpc: '2.0',
                    id: 1,
                    method: 'sui_getObject',
                    params: [field.objectId, { showContent: true }]
                  })
                })
                const valData = await valResp.json()
                const value = valData.result?.data?.content?.fields?.value || '0'
                bmSuiBalance += parseInt(value) / 1e9
              }
            }
            setBmBalance(bmSuiBalance)
          } else {
            setBmBalance(0)
          }
        } else {
          setBmBalance(0)
        }
      } catch (e) {
        console.error('Failed to fetch BM balance:', e)
        setBmBalance(0)
      }
    } else {
      setBmBalance(0)
    }
  }, [account?.address, suiClient])

  useEffect(() => {
    fetchBalances()
    const interval = setInterval(fetchBalances, 30000)
    return () => clearInterval(interval)
  }, [fetchBalances])

  if (!account) {
    return (
      <div className="card" style={{ margin: '2rem' }}>
        <h2>请先连接钱包</h2>
        <p>使用 Sui Wallet 扩展程序连接后即可进行交易</p>
      </div>
    )
  }

  const fmt = (n: number | undefined | null, d = 4) => n != null && !isNaN(n) ? n.toFixed(d) : '--'

  return (
    <div className="trading-terminal">
      {/* Header Bar - Compact */}
      <div className="terminal-header">
        <div className="header-left">
          <span className="pair-name">SUI - USDC</span>
          <span className="pair-price">{ticker ? fmt(ticker.lastPrice) : '--'}</span>
          <span className={`pair-change ${ticker && ticker.priceChangePercent >= 0 ? 'positive' : 'negative'}`}>
            {ticker ? (ticker.priceChangePercent >= 0 ? '+' : '') + ticker.priceChangePercent.toFixed(2) + '%' : '--'}
          </span>
        </div>
        <div className="header-stats">
          <div className="stat">
            <span className="stat-label">24h Change</span>
            <span className="stat-value">{ticker ? (ticker.priceChangePercent >= 0 ? '+' : '') + ticker.priceChangePercent.toFixed(2) + '%' : '--'}</span>
          </div>
        </div>
      </div>

      {/* Main Content - Left (Chart+OrderBook+Table) | Right (Trade Panel full height) */}
      <div className="main-content">
        {/* Left Side */}
        <div className="left-content">
          {/* Top: Chart + Order Book */}
          <div className="left-top">
            <div className="panel chart-panel">
              <MarketChart />
            </div>
            <div className="panel orderbook-panel">
              <div className="panel-header">
                <span>Order Book</span>
                <span className="panel-subtitle">Recent Trades</span>
              </div>
              <OrderBook />
            </div>
          </div>

          {/* Bottom: Order Table */}
          <div className="left-bottom">
            <div className="bottom-tabs">
              <button
                className={`bottom-tab ${bottomTab === 'open' ? 'active' : ''}`}
                onClick={() => setBottomTab('open')}
              >
                Open Orders
              </button>
              <button
                className={`bottom-tab ${bottomTab === 'history' ? 'active' : ''}`}
                onClick={() => setBottomTab('history')}
              >
                Order History
              </button>
              <button
                className={`bottom-tab ${bottomTab === 'trades' ? 'active' : ''}`}
                onClick={() => setBottomTab('trades')}
              >
                Trade History
              </button>
            </div>
            <div className="bottom-content">
              {bottomTab === 'open' && <OrdersPanel />}
              {bottomTab === 'history' && <HistoryPanel />}
              {bottomTab === 'trades' && <HistoryPanel />}
            </div>
          </div>
        </div>

        {/* Right Side - Trade Panel (full height) */}
        <div className="right-content">
          <div className="trade-panel">
            <DepositPanel onDepositSuccess={fetchBalances} />

            <div className="portfolio-section">
              <div className="portfolio-header">可用余额</div>
              <div className="portfolio-item">
                <span className="asset-name">钱包 SUI</span>
                <span className="asset-balance">{walletBalance.toFixed(4)}</span>
              </div>
              <div className="portfolio-item bm">
                <span className="asset-name">BM SUI</span>
                <span className="asset-balance">{bmBalance.toFixed(4)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default TradingPage
