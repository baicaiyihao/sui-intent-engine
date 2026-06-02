import { useState, useEffect, useCallback, useRef } from 'react'
import { useCurrentAccount, useSignTransaction, useSuiClient } from '@mysten/dapp-kit'
import { Transaction } from '@mysten/sui/transactions'
import DepositPanel from './DepositPanel'
import OrdersPanel from './OrdersPanel'
import HistoryPanel from './HistoryPanel'
import MarketChart from './MarketChart'
import OrderBook from './OrderBook'
import { useI18n } from '../i18n/I18nProvider'
import './TradingPage.css'

type BottomTab = 'open' | 'history' | 'trades'

const API_BASE = 'http://localhost:8001'
const V1_PKG = '0x2c8d603bc51326b8c13cef9dd07031a408a48dddb541963357661df5d3204809'
const SUI_COIN = '0x2::sui::SUI'
const USDC_COIN = '0xdba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC'
const SUI_USDC_POOL = '0xe05dafb5133bcffb8d59f4e12465dc0e9faeaa05e3e342a08fe135800e3e4407'

function TradingPage() {
  const [bottomTab, setBottomTab] = useState<BottomTab>('open')
  const [bmSuiBalance, setBmSuiBalance] = useState(0)
  const [bmUsdcBalance, setBmUsdcBalance] = useState(0)
  const [poolSuiBalance, setPoolSuiBalance] = useState(0)
  const [poolUsdcBalance, setPoolUsdcBalance] = useState(0)
  const [walletSuiBalance, setWalletSuiBalance] = useState(0)
  const [walletUsdcBalance, setWalletUsdcBalance] = useState(0)
  const [withdrawing, setWithdrawing] = useState<'sui' | 'usdc' | null>(null)
  const [claiming, setClaiming] = useState(false)
  const [ticker, setTicker] = useState<{lastPrice: number, priceChangePercent: number, high: number, low: number, volume: number, bid: number, ask: number} | null>(null)
  const [selectedPrice, setSelectedPrice] = useState<number | null>(null)
  const [priceFlash, setPriceFlash] = useState<'up' | 'down' | null>(null)
  const prevPriceRef = useRef<number | null>(null)
  const account = useCurrentAccount()
  const { mutate: signTransaction } = useSignTransaction()
  const suiClient = useSuiClient()
  const { t } = useI18n()

  const fetchTicker = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/cache/ticker`)
      const result = await response.json()
      if (result.success && result.data) {
        const newPrice = result.data.last_price
        // Trigger price flash effect
        if (prevPriceRef.current != null && newPrice !== prevPriceRef.current) {
          setPriceFlash(newPrice > prevPriceRef.current ? 'up' : 'down')
          setTimeout(() => setPriceFlash(null), 600)
        }
        prevPriceRef.current = newPrice
        setTicker({
          lastPrice: newPrice,
          priceChangePercent: result.data.price_change_percent,
          high: result.data.high,
          low: result.data.low,
          volume: result.data.volume,
          bid: result.data.bid,
          ask: result.data.ask,
        })
      }
    } catch (e) {
      console.error('Failed to fetch ticker:', e)
    }
  }, [])

  useEffect(() => {
    if (account) {
      fetchTicker()
      const interval = setInterval(fetchTicker, 1000)
      return () => clearInterval(interval)
    }
  }, [account, fetchTicker])

  const scanForBM = useCallback(async () => {
    if (!account?.address) return
    try {
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
      const bmArray = [...bms]
      if (bmArray.length > 0) {
        localStorage.setItem('balanceManagerId', bmArray[0])
        return bmArray[0]
      }
    } catch (e) {
      console.error('Error scanning for BMs:', e)
    }
    return null
  }, [account?.address])

  useEffect(() => {
    if (account?.address) {
      const storedBmId = localStorage.getItem('balanceManagerId')
      if (!storedBmId) scanForBM()
    }
  }, [account?.address, scanForBM])

  const fetchBalances = useCallback(async () => {
    const storedBmId = localStorage.getItem('balanceManagerId') || ''

    if (account?.address) {
      try {
        const [suiBalance, usdcBalance] = await Promise.all([
          suiClient.getBalance({ owner: account.address, coinType: SUI_COIN }),
          suiClient.getBalance({ owner: account.address, coinType: USDC_COIN })
        ])
        setWalletSuiBalance(Number(suiBalance.totalBalance) / 1e9)
        setWalletUsdcBalance(Number(usdcBalance.totalBalance) / 1e6)
      } catch (e) {
        console.error('Failed to fetch wallet balance:', e)
      }
    }

    if (storedBmId) {
      try {
        const [suiBalance, usdcBalance] = await Promise.all([
          suiClient.getBalance({ owner: storedBmId, coinType: SUI_COIN }),
          suiClient.getBalance({ owner: storedBmId, coinType: USDC_COIN })
        ])
        setBmSuiBalance(Number(suiBalance.totalBalance) / 1e9)
        setBmUsdcBalance(Number(usdcBalance.totalBalance) / 1e6)
      } catch (e) {
        setBmSuiBalance(0)
        setBmUsdcBalance(0)
      }
    } else {
      setBmSuiBalance(0)
      setBmUsdcBalance(0)
    }

    if (storedBmId) {
      try {
        const poolResp = await fetch('https://fullnode.mainnet.sui.io:443', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            jsonrpc: '2.0',
            id: 1,
            method: 'sui_getObject',
            params: [SUI_USDC_POOL, { showContent: true }]
          })
        })
        const poolData = await poolResp.json()
        const innerId = poolData.result?.data?.content?.fields?.inner?.fields?.id?.id
        if (innerId) {
          const poolInnerResp = await fetch('https://fullnode.mainnet.sui.io:443', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              jsonrpc: '2.0',
              id: 1,
              method: 'suix_getDynamicFieldObject',
              params: [innerId, { type: 'u64', value: '1' }]
            })
          })
          const poolInnerData = await poolInnerResp.json()
          const poolInnerFields = poolInnerData.result?.data?.content?.fields?.value?.fields
          const accountsTableId = poolInnerFields?.state?.fields?.accounts?.fields?.id?.id
          if (accountsTableId) {
            const accountResp = await fetch('https://fullnode.mainnet.sui.io:443', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                jsonrpc: '2.0',
                id: 1,
                method: 'suix_getDynamicFieldObject',
                params: [accountsTableId, { type: '0x2::object::ID', value: storedBmId }]
              })
            })
            const accountData = await accountResp.json()
            const acc = accountData.result?.data?.content?.fields?.value?.fields
            if (acc) {
              const owedBase = Number(acc.owed_balances?.fields?.base || 0) / 1e9
              const owedQuote = Number(acc.owed_balances?.fields?.quote || 0) / 1e6
              const settledBase = Number(acc.settled_balances?.fields?.base || 0) / 1e9
              const settledQuote = Number(acc.settled_balances?.fields?.quote || 0) / 1e6
              setPoolSuiBalance(owedBase + settledBase)
              setPoolUsdcBalance(owedQuote + settledQuote)
            } else {
              setPoolSuiBalance(0)
              setPoolUsdcBalance(0)
            }
          }
        }
      } catch (e) {
        setPoolSuiBalance(0)
        setPoolUsdcBalance(0)
      }
    }
  }, [account?.address, suiClient])

  const handleWithdraw = useCallback((token: 'sui' | 'usdc') => {
    const bmId = localStorage.getItem('balanceManagerId') || ''
    if (!account || !bmId) return
    setWithdrawing(token)
    const tx = new Transaction()
    tx.setGasBudget(100000000)
    tx.setSender(account.address)
    const coinType = token === 'sui' ? SUI_COIN : USDC_COIN
    const [withdrawn] = tx.moveCall({
      target: `${V1_PKG}::balance_manager::withdraw_all`,
      arguments: [tx.object(bmId)],
      typeArguments: [coinType],
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
              fetchBalances()
            }
          } catch (e) {
            console.error('Withdraw failed:', e)
          } finally {
            setWithdrawing(null)
          }
        },
        onError: () => setWithdrawing(null)
      }
    )
  }, [account, signTransaction, suiClient, fetchBalances])

  const handleClaim = useCallback(() => {
    const bmId = localStorage.getItem('balanceManagerId') || ''
    if (!account || !bmId) return
    setClaiming(true)
    const tx = new Transaction()
    tx.setGasBudget(100000000)
    tx.setSender(account.address)
    const [proof] = tx.moveCall({
      target: `${V1_PKG}::balance_manager::generate_proof_as_owner`,
      arguments: [tx.object(bmId)],
      typeArguments: [],
    })
    tx.moveCall({
      target: `${V1_PKG}::pool::withdraw_settled_amounts`,
      arguments: [tx.object(SUI_USDC_POOL), tx.object(bmId), proof],
      typeArguments: [SUI_COIN, USDC_COIN],
    })
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
              fetchBalances()
            }
          } catch (e) {
            console.error('Claim failed:', e)
          } finally {
            setClaiming(false)
          }
        },
        onError: () => setClaiming(false)
      }
    )
  }, [account, signTransaction, suiClient, fetchBalances])

  useEffect(() => {
    fetchBalances()
    const interval = setInterval(fetchBalances, 30000)
    return () => clearInterval(interval)
  }, [fetchBalances])

  if (!account) {
    return (
      <div className="connect-prompt">
        <div className="connect-prompt-inner">
          <div className="connect-prompt-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M21 12V7a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-3"/>
              <path d="M16 12h6M19 9l3 3-3 3"/>
            </svg>
          </div>
          <h2>{t('trading.connectWallet.title')}</h2>
          <p>{t('trading.connectWallet.desc')}</p>
        </div>
      </div>
    )
  }

  const fmt = (n: number | undefined | null, d = 4) => n != null && !isNaN(n) ? n.toFixed(d) : '--'
  const fmtVol = (n: number | undefined | null) => {
    if (n == null || isNaN(n)) return '--'
    if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`
    if (n >= 1e3) return `${(n / 1e3).toFixed(2)}K`
    return n.toFixed(2)
  }
  const isPositive = ticker ? ticker.priceChangePercent >= 0 : true
  const changePrefix = isPositive ? '+' : ''

  return (
    <div className="bnx-terminal">
      {/* ===== Symbol Info Bar ===== */}
      <div className="bnx-symbol-bar">
        <div className="bnx-symbol-left">
          <div className="bnx-pair-block">
            <span className="bnx-pair-name">SUI</span>
            <span className="bnx-pair-sep">/</span>
            <span className="bnx-pair-quote">USDC</span>
            <span className="bnx-pair-badge">SPOT</span>
          </div>
          <div className="bnx-price-block">
            <span className={`bnx-price-main ${priceFlash ? `flash-${priceFlash}` : ''}`}>
              {ticker ? fmt(ticker.lastPrice) : '--'}
            </span>
            <span className={`bnx-price-change ${isPositive ? 'up' : 'down'}`}>
              {ticker ? `${changePrefix}${ticker.priceChangePercent.toFixed(2)}%` : '--'}
            </span>
          </div>
        </div>
        <div className="bnx-symbol-stats">
          <div className="bnx-stat">
            <span className="bnx-stat-label">{t('trading.stat.high24h')}</span>
            <span className="bnx-stat-val up">{ticker ? fmt(ticker.high) : '--'}</span>
          </div>
          <div className="bnx-stat">
            <span className="bnx-stat-label">{t('trading.stat.low24h')}</span>
            <span className="bnx-stat-val down">{ticker ? fmt(ticker.low) : '--'}</span>
          </div>
          <div className="bnx-stat">
            <span className="bnx-stat-label">{t('trading.stat.vol24h')}</span>
            <span className="bnx-stat-val">{ticker ? fmtVol(ticker.volume) : '--'}</span>
          </div>
          <div className="bnx-stat">
            <span className="bnx-stat-label">{t('trading.stat.bid')}</span>
            <span className="bnx-stat-val up">{ticker ? fmt(ticker.bid) : '--'}</span>
          </div>
          <div className="bnx-stat">
            <span className="bnx-stat-label">{t('trading.stat.ask')}</span>
            <span className="bnx-stat-val down">{ticker ? fmt(ticker.ask) : '--'}</span>
          </div>
        </div>
        <div className="bnx-symbol-pulse">
          <span className="bnx-pulse-dot" />
          <span className="bnx-pulse-text">LIVE</span>
        </div>
      </div>

      {/* ===== Main Grid: Chart | Order Book | Trade Form ===== */}
      <div className="bnx-grid">
        {/* --- Chart Panel --- */}
        <div className="bnx-panel bnx-chart-panel">
          <MarketChart />
        </div>

        {/* --- Order Book Panel --- */}
        <div className="bnx-panel bnx-orderbook-panel">
          <div className="bnx-panel-header">
            <span>{t('trading.orderBook')}</span>
            <span className="bnx-panel-meta">0.01 group</span>
          </div>
          <OrderBook onPriceClick={setSelectedPrice} />
        </div>

        {/* --- Trade Form Panel --- */}
        <div className="bnx-panel bnx-trade-panel">
          <DepositPanel
            onDepositSuccess={fetchBalances}
            selectedPrice={selectedPrice}
            marketPrice={ticker?.lastPrice || null}
            onPriceUsed={() => setSelectedPrice(null)}
          />
        </div>
      </div>

      {/* ===== Account + Bottom Tabs Section ===== */}
      <div className="bnx-bottom">
        {/* Account Balance Strip */}
        <div className="bnx-account-strip">
          <div className="bnx-account-block">
            <span className="bnx-account-label">{t('trading.wallet')}</span>
            <div className="bnx-account-vals">
              <span className="bnx-account-val">
                <em className="bnx-token sui">SUI</em>
                {walletSuiBalance.toFixed(4)}
              </span>
              <span className="bnx-account-val">
                <em className="bnx-token usdc">USDC</em>
                {walletUsdcBalance.toFixed(2)}
              </span>
            </div>
          </div>
          <div className="bnx-account-block">
            <span className="bnx-account-label">{t('trading.vault')}</span>
            <div className="bnx-account-vals">
              <span className="bnx-account-val">
                <em className="bnx-token sui">SUI</em>
                {bmSuiBalance.toFixed(4)}
              </span>
              <span className="bnx-account-val">
                <em className="bnx-token usdc">USDC</em>
                {bmUsdcBalance.toFixed(2)}
              </span>
            </div>
            <div className="bnx-account-actions">
              <button
                className="bnx-mini-btn"
                onClick={() => handleWithdraw('sui')}
                disabled={withdrawing !== null}
              >
                {withdrawing === 'sui' ? '...' : t('trading.withdrawSui')}
              </button>
              <button
                className="bnx-mini-btn"
                onClick={() => handleWithdraw('usdc')}
                disabled={withdrawing !== null}
              >
                {withdrawing === 'usdc' ? '...' : t('trading.withdrawUsdc')}
              </button>
            </div>
          </div>
          <div className="bnx-account-block bnx-account-pool">
            <span className="bnx-account-label">{t('trading.inPool')}</span>
            <div className="bnx-account-vals">
              <span className="bnx-account-val">
                <em className="bnx-token sui">SUI</em>
                {poolSuiBalance.toFixed(4)}
              </span>
              <span className="bnx-account-val">
                <em className="bnx-token usdc">USDC</em>
                {poolUsdcBalance.toFixed(2)}
              </span>
            </div>
            <button
              className="bnx-claim-btn"
              onClick={handleClaim}
              disabled={claiming}
            >
              {claiming ? t('trading.claiming') : t('trading.claim')}
            </button>
          </div>
        </div>

        {/* Bottom Tabs */}
        <div className="bnx-bottom-tabs">
          <button
            className={`bnx-bottom-tab ${bottomTab === 'open' ? 'active' : ''}`}
            onClick={() => setBottomTab('open')}
          >
            {t('trading.tab.open')}
            <span className="bnx-tab-count">Open Orders</span>
          </button>
          <button
            className={`bnx-bottom-tab ${bottomTab === 'history' ? 'active' : ''}`}
            onClick={() => setBottomTab('history')}
          >
            {t('trading.tab.history')}
            <span className="bnx-tab-count">Order History</span>
          </button>
          <button
            className={`bnx-bottom-tab ${bottomTab === 'trades' ? 'active' : ''}`}
            onClick={() => setBottomTab('trades')}
          >
            {t('trading.tab.trades')}
            <span className="bnx-tab-count">Trade History</span>
          </button>
          <div className="bnx-bottom-tabs-strip" />
        </div>
        <div className="bnx-bottom-content">
          {bottomTab === 'open' && <OrdersPanel />}
          {bottomTab === 'history' && <HistoryPanel />}
          {bottomTab === 'trades' && <HistoryPanel />}
        </div>
      </div>
    </div>
  )
}

export default TradingPage
