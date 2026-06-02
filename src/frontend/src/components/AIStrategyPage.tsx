import { useState, useEffect, useCallback } from 'react'
import { useCurrentAccount, useSignTransaction, useSuiClient } from '@mysten/dapp-kit'
import { Transaction } from '@mysten/sui/transactions'
import { useI18n, TranslationKey } from '../i18n/I18nProvider'
import './AIStrategyPage.css'

// Backend APIs
const QUANT_API = 'http://localhost:8000'     // quant_core: AI signals, performance, indicators
const DEEPBOOK_API = 'http://localhost:8001'  // DeepBook: live ticker cache

// DeepBook V3 contract addresses
const UTILS_PKG = '0x600138d3179e2fc746f6774f360a6e1fa68e90d66d082af66399adabe46f22a4'
const GLOBAL_CONFIG = '0xff1141ef80e7baf206c7930c274b465600e64884d8167f90d4cdb60197925163'
const CETUS_BM_INDEXER = '0x5c1a039f97ed1cbd84d54b5d633bdffd681086acc38961b1d366c4ecf680d150'
const SUI_USDC_POOL = '0xe05dafb5133bcffb8d59f4e12465dc0e9faeaa05e3e342a08fe135800e3e4407'
const USDC_COIN = '0xdba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC'
const SUI_COIN = '0x2::sui::SUI'
const DEEP_COIN = '0xdeeb7a4662eec9f2f3def03fb937a663dddaa2e215b8078a284d026b7946c270::deep::DEEP'

// 1 year in nanoseconds for order expiration
const ONE_YEAR_NANOS = BigInt(365 * 24 * 3600) * BigInt(1e9)

interface TickerData {
  lastPrice: number
  priceChangePercent: number
  high24h: number
  low24h: number
  volume24h: number
}

interface Indicators {
  rsi?: number
  macd?: number
  macd_signal?: number
  macd_hist?: number
  boll_upper?: number
  boll_middle?: number
  boll_lower?: number
  atr?: number
}

interface AnalysisResult {
  trend?: string
  trend_strength?: number
  support?: number
  resistance?: number
  rsi_analysis?: string
  macd_analysis?: string
  signals?: string[]
  risk_level?: string
  recommendation?: string
  summary?: string
  current_price?: number
  indicators: Indicators
}

interface AISignal {
  decision: 'BUY' | 'SELL' | 'HOLD'
  confidence: number
  action_recommendation?: string
  summary: string
  entry_price: number
  stop_loss: number
  take_profit: number
  position_size_pct: number
  timeframe: string
  key_reasons: string[]
  risks: string[]
  technical_score: number
  fundamental_score: number
  sentiment_score: number
}

interface PerformanceStats {
  total_analyses?: number
  correct_count?: number
  incorrect_count?: number
  accuracy?: number
  unique_symbols?: number
}

interface QAEntry {
  id: string
  type: string
  question: string
  answer: string | null
  loading: boolean
  error: string | null
  ts: number
}

interface QuickQuestion {
  type: string
  labelKey: TranslationKey
  icon: string
  hint?: string
  // Visible in the default row based on decision
  decisions: Array<'BUY' | 'SELL' | 'HOLD'>
}

const QUICK_QUESTIONS: QuickQuestion[] = [
  // Default 4 (dynamically by decision)
  { type: 'limit_price', labelKey: 'aiStrategy.qq.limitPrice', icon: '🎯', decisions: ['BUY', 'SELL'] },
  { type: 'maker_vs_taker', labelKey: 'aiStrategy.qq.makerVsTaker', icon: '⚖️', decisions: ['BUY', 'SELL'] },
  { type: 'bm_allocation', labelKey: 'aiStrategy.qq.bmAllocation', icon: '💼', decisions: ['BUY', 'SELL'] },
  { type: 'expired_order', labelKey: 'aiStrategy.qq.expiredOrder', icon: '⏰', decisions: ['BUY', 'SELL'] },
  // Secondary (shown when "more" is expanded)
  { type: 'depth_check', labelKey: 'aiStrategy.qq.depthCheck', icon: '🌊', decisions: ['BUY', 'SELL'] },
  { type: 'liquidity_trend', labelKey: 'aiStrategy.qq.liquidityTrend', icon: '📈', decisions: ['BUY', 'SELL', 'HOLD'] },
  { type: 'reasoning', labelKey: 'aiStrategy.qq.reasoning', icon: '🤔', decisions: ['BUY', 'SELL', 'HOLD'] },
  { type: 'multi_timeframe', labelKey: 'aiStrategy.qq.multiTimeframe', icon: '🔄', decisions: ['BUY', 'SELL', 'HOLD'] },
]

function AIStrategyPage() {
  const [ticker, setTicker] = useState<TickerData | null>(null)
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null)
  const [aiSignal, setAiSignal] = useState<AISignal | null>(null)
  const [performance, setPerformance] = useState<PerformanceStats | null>(null)

  const [loadingData, setLoadingData] = useState(true)
  const [loadingAI, setLoadingAI] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [quantity, setQuantity] = useState('')
  const [walletSui, setWalletSui] = useState(0)
  const [walletUsdc, setWalletUsdc] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [orderResult, setOrderResult] = useState<string | null>(null)

  // Quick question state
  const [qaHistory, setQaHistory] = useState<QAEntry[]>([])
  const [qaExpanded, setQaExpanded] = useState(true)
  const [showMore, setShowMore] = useState(false)
  const [askingType, setAskingType] = useState<string | null>(null)

  const account = useCurrentAccount()
  const { mutate: signTransaction } = useSignTransaction()
  const suiClient = useSuiClient()
  const { t, locale } = useI18n()

  // ========== Data fetchers ==========

  // Live ticker from DeepBook cache
  const fetchTicker = useCallback(async () => {
    try {
      const resp = await fetch(`${DEEPBOOK_API}/api/v1/cache/ticker`)
      const data = await resp.json()
      if (data.success && data.data) {
        setTicker({
          lastPrice: data.data.last_price,
          priceChangePercent: data.data.price_change_percent,
          high24h: data.data.high,
          low24h: data.data.low,
          volume24h: data.data.volume
        })
      }
    } catch (e) {
      console.error('Ticker fetch error:', e)
    }
  }, [])

  // Technical analysis (RSI/MACD/Bollinger/ATR) from quant_core
  const fetchAnalysis = useCallback(async () => {
    try {
      const resp = await fetch(`${QUANT_API}/api/v1/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: 'SUI/USDT', timeframe: '1h', days: 7, language: locale === 'zh' ? 'zh-CN' : 'en' })
      })
      const data = await resp.json()
      if (data.success && data.data) {
        setAnalysis(data.data)
      }
    } catch (e) {
      console.error('Analysis fetch error:', e)
    }
  }, [])

  // Wallet balances
  const fetchBalance = useCallback(async () => {
    if (!account?.address) return
    try {
      const [sui, usdc] = await Promise.all([
        suiClient.getBalance({ owner: account.address, coinType: SUI_COIN }),
        suiClient.getBalance({ owner: account.address, coinType: USDC_COIN })
      ])
      setWalletSui(Number(sui.totalBalance) / 1e9)
      setWalletUsdc(Number(usdc.totalBalance) / 1e6)
    } catch (e) {
      console.error('Balance fetch error:', e)
    }
  }, [account?.address, suiClient])

  // AI signal + performance track record
  const runAIAnalysis = useCallback(async () => {
    setLoadingAI(true)
    setError(null)
    setOrderResult(null)
    // LLM can take 60-90s on MiniMax — abort and show clear error if it overruns
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 110000)
    try {
      const [signalResp, perfResp] = await Promise.all([
        fetch(`${QUANT_API}/api/v1/ai/signal?symbol=SUI/USDT&timeframe=1h&days=7&language=${locale === 'zh' ? 'zh-CN' : 'en'}`, { signal: controller.signal }),
        fetch(`${QUANT_API}/api/v1/ai/performance?symbol=SUI/USDT&days=30`, { signal: controller.signal })
      ])
      clearTimeout(timeoutId)
      const signalData = await signalResp.json()
      const perfData = await perfResp.json()

      if (signalData.success && signalData.signal) {
        setAiSignal(signalData.signal)
      } else {
        setError(t('aiStrategy.err.ai', { reason: signalData.error || t('deposit.err.unknown') }))
      }
      if (perfData.success && perfData.data) {
        setPerformance(perfData.data)
      }
    } catch (e) {
      if ((e as Error).name === 'AbortError') {
        setError(t('aiStrategy.err.aiTimeout'))
      } else {
        setError(t('aiStrategy.err.aiError', { reason: (e as Error).message }))
      }
    } finally {
      setLoadingAI(false)
    }
  }, [locale])

  // Quick question handler
  const askQuestion = useCallback(async (q: QuickQuestion) => {
    if (!aiSignal) return
    if (askingType) return  // Prevent multiple concurrent requests

    const id = `${q.type}-${Date.now()}`
    const entry: QAEntry = {
      id,
      type: q.type,
      question: t(q.labelKey),
      answer: null,
      loading: true,
      error: null,
      ts: Date.now(),
    }
    setQaHistory(prev => [entry, ...prev].slice(0, 5))  // Keep at most 5 entries
    setAskingType(q.type)
    setQaExpanded(true)

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 100000)  // 100s timeout

    try {
      // Build context
      const ctx: Record<string, any> = {
        decision: aiSignal.decision,
        confidence: aiSignal.confidence,
        entry_price: aiSignal.entry_price,
        stop_loss: aiSignal.stop_loss,
        take_profit: aiSignal.take_profit,
        position_pct: aiSignal.position_size_pct,
        quantity,
        wallet_sui: walletSui.toFixed(4),
        wallet_usdc: walletUsdc.toFixed(2),
        key_reasons: aiSignal.key_reasons,
        rsi: analysis?.indicators.rsi,
        macd: analysis?.indicators.macd,
        atr: analysis?.indicators.atr,
        best_bid: ticker ? (ticker.lastPrice * 0.9995).toFixed(4) : t('aiChat.ctx.unknown'),
        best_ask: ticker ? (ticker.lastPrice * 1.0005).toFixed(4) : t('aiChat.ctx.unknown'),
        bid_depth: `${t('aiChat.ctx.depthPrefix')}${ticker ? Math.round(ticker.volume24h * 0.005) : 0}${t('aiChat.ctx.depthSuffix')}`,
        ask_depth: `${t('aiChat.ctx.depthPrefix')}${ticker ? Math.round(ticker.volume24h * 0.005) : 0}${t('aiChat.ctx.depthSuffix')}`,
        spread_bps: t('aiChat.ctx.spread'),
        ask_levels: t('aiChat.ctx.askLevels'),
        volume_24h: ticker?.volume24h || 0,
        change_24h: ticker?.priceChangePercent || 0,
      }

      const resp = await fetch(`${QUANT_API}/api/v1/ai/quick-question`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question_type: q.type,
          symbol: 'SUI/USDT',
          language: locale === 'zh' ? 'zh-CN' : 'en',
          context: ctx,
        }),
        signal: controller.signal,
      })
      clearTimeout(timeoutId)
      const data = await resp.json()
      if (data.success) {
        setQaHistory(prev => prev.map(e => e.id === id ? { ...e, answer: data.answer, loading: false } : e))
      } else {
        setQaHistory(prev => prev.map(e => e.id === id ? { ...e, error: data.detail || t('aiStrategy.qqUnknown'), loading: false } : e))
      }
    } catch (e) {
      if ((e as Error).name === 'AbortError') {
        setQaHistory(prev => prev.map(en => en.id === id ? { ...en, error: t('aiStrategy.qqTimeout'), loading: false } : en))
      } else {
        setQaHistory(prev => prev.map(en => en.id === id ? { ...en, error: (e as Error).message, loading: false } : en))
      }
    } finally {
      setAskingType(null)
    }
  }, [aiSignal, analysis, ticker, quantity, walletSui, walletUsdc, askingType, locale, t])

  // Initial data load + ticker polling
  useEffect(() => {
    let mounted = true
    const init = async () => {
      setLoadingData(true)
      await Promise.all([fetchTicker(), fetchAnalysis()])
      if (mounted) setLoadingData(false)
    }
    init()
    const interval = setInterval(fetchTicker, 5000)
    return () => {
      mounted = false
      clearInterval(interval)
    }
  }, [fetchTicker, fetchAnalysis])

  // Balance polling
  useEffect(() => {
    if (account) {
      fetchBalance()
      const interval = setInterval(fetchBalance, 30000)
      return () => clearInterval(interval)
    }
  }, [account, fetchBalance])

  // ========== One-click order ==========

  const handleOrder = useCallback(async () => {
    if (!aiSignal || !account) return
    const qty = parseFloat(quantity)
    if (isNaN(qty) || qty <= 0) {
      setError(t('aiStrategy.err.invalidAmount'))
      return
    }

    const bmId = localStorage.getItem('balanceManagerId') || ''
    if (!bmId) {
      setError(t('aiStrategy.err.noBm'))
      return
    }

    setSubmitting(true)
    setError(null)
    setOrderResult(null)

    const tx = new Transaction()
    tx.setGasBudget(250000000)
    tx.setSender(account.address)

    const isBuy = aiSignal.decision === 'BUY'
    const price = aiSignal.entry_price
    const quantityMIST = BigInt(Math.floor(qty * 1e9))
    const priceU64 = BigInt(Math.floor(price * 1e6))
    const expireTime = BigInt(Date.now()) * BigInt(1e6) + ONE_YEAR_NANOS

    try {
      if (isBuy) {
        // BUY: use USDC. Need MergeCoins + SplitCoins.
        const usdcNeeded = BigInt(Math.ceil(qty * price * 1e6))

        const usdcResp = await fetch('https://fullnode.mainnet.sui.io:443', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            jsonrpc: '2.0', id: 1, method: 'suix_getCoins',
            params: [account.address, USDC_COIN]
          })
        })
        const usdcData = await usdcResp.json()
        const usdcCoins: any[] = usdcData.result?.data || []

        if (usdcCoins.length === 0) {
          setError(t('aiStrategy.err.noUsdc'))
          setSubmitting(false)
          return
        }

        const [usdcCoin1, ...others] = usdcCoins
        if (others.length > 0) {
          tx.mergeCoins(
            tx.object(usdcCoin1.coinObjectId),
            others.map((c: any) => tx.object(c.coinObjectId))
          )
        }
        const [usdcSplit] = tx.splitCoins(tx.object(usdcCoin1.coinObjectId), [usdcNeeded])
        const [suiZero] = tx.moveCall({ target: '0x2::coin::zero', arguments: [], typeArguments: [SUI_COIN] })
        const [deepZero] = tx.moveCall({ target: '0x2::coin::zero', arguments: [], typeArguments: [DEEP_COIN] })

        tx.moveCall({
          target: `${UTILS_PKG}::deepbookv3_utils::deposit_then_place_limit_order_by_owner`,
          arguments: [
            tx.object(GLOBAL_CONFIG), tx.object(CETUS_BM_INDEXER), tx.object(SUI_USDC_POOL), tx.object(bmId),
            suiZero, usdcSplit, deepZero,
            tx.pure.u8(0), tx.pure.u8(0), priceU64, quantityMIST,
            tx.pure.bool(true), tx.pure.bool(false), expireTime, tx.object.clock()
          ],
          typeArguments: [SUI_COIN, USDC_COIN]
        })
      } else {
        // SELL: split SUI from gas coin
        const splitAmount = quantityMIST + BigInt(0.02 * 1e9) // qty + gas buffer
        const [suiCoin] = tx.splitCoins(tx.gas, [splitAmount])
        const [usdcZero] = tx.moveCall({ target: '0x2::coin::zero', arguments: [], typeArguments: [USDC_COIN] })
        const [deepZero] = tx.moveCall({ target: '0x2::coin::zero', arguments: [], typeArguments: [DEEP_COIN] })

        tx.moveCall({
          target: `${UTILS_PKG}::deepbookv3_utils::deposit_then_place_limit_order_by_owner`,
          arguments: [
            tx.object(GLOBAL_CONFIG), tx.object(CETUS_BM_INDEXER), tx.object(SUI_USDC_POOL), tx.object(bmId),
            suiCoin, usdcZero, deepZero,
            tx.pure.u8(0), tx.pure.u8(0), priceU64, quantityMIST,
            tx.pure.bool(false), tx.pure.bool(false), expireTime, tx.object.clock()
          ],
          typeArguments: [SUI_COIN, USDC_COIN]
        })
      }

      signTransaction(
        { transaction: tx as any, chain: 'sui:mainnet' } as any,
        {
          onSuccess: async (result: any) => {
            try {
              const exec = await suiClient.executeTransactionBlock({
                transactionBlock: result.bytes,
                signature: result.signature,
                options: { showEffects: true, showEvents: true }
              })
              if (exec.effects?.status?.status === 'success') {
                setOrderResult(t('aiStrategy.orderOk', { digest: exec.digest.slice(0, 18) + '...' }))
                setQuantity('')
              } else {
                setError(t('aiStrategy.err.chainFailed', { reason: exec.effects?.status?.error || t('deposit.err.unknown') }))
              }
            } catch (e) {
              setError(t('aiStrategy.err.exec', { reason: (e as Error).message }))
            } finally {
              setSubmitting(false)
            }
          },
          onError: (err: any) => {
            setError(t('aiStrategy.err.signRejected', { reason: err?.message || err }))
            setSubmitting(false)
          }
        }
      )
    } catch (e) {
      setError(t('aiStrategy.err.orderFailed', { reason: (e as Error).message }))
      setSubmitting(false)
    }
  }, [aiSignal, account, quantity, signTransaction, suiClient, t])

  // ========== Render ==========

  const fmt = (n: number | undefined | null, d = 4) =>
    n != null && !isNaN(n) ? n.toFixed(d) : '--'

  const fmtPct = (n: number | undefined | null) =>
    n != null && !isNaN(n) ? (n >= 0 ? '+' : '') + n.toFixed(2) + '%' : '--'

  const decision = aiSignal?.decision || 'HOLD'
  const decisionLabel = decision === 'BUY' ? t('aiStrategy.decision.buy') : decision === 'SELL' ? t('aiStrategy.decision.sell') : t('aiStrategy.decision.hold')
  const decisionClass = decision.toLowerCase()
  const bmId = localStorage.getItem('balanceManagerId') || ''

  if (!account) {
    return (
      <div className="ai-strategy-page">
        <div className="empty-state">
          <div className="empty-icon">🔌</div>
          <h2>{t('aiStrategy.connectWallet')}</h2>
          <p>{t('aiStrategy.connectWalletHint')}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="ai-strategy-page">
      {/* ========== Section 01: Live Data ========== */}
      <section className="ai-section data-section">
        <div className="section-header">
          <h2 className="section-title">
            <span className="title-mono">01</span>
            <span>{t('aiStrategy.section.liveData')}</span>
            <span className="title-sub">SUI / USDC</span>
          </h2>
          <div className="live-badge">
            <span className="pulse-dot" />
            LIVE
          </div>
        </div>

        <div className="data-grid">
          <div className={`data-card price-card ${ticker && ticker.priceChangePercent >= 0 ? 'positive' : 'negative'}`}>
            <div className="data-label">{t('aiStrategy.lastPrice')}</div>
            <div className="data-value-large">{ticker ? fmt(ticker.lastPrice) : (loadingData ? '...' : '--')}</div>
            <div className="data-change">
              {ticker ? fmtPct(ticker.priceChangePercent) : '--'}
              <span className="change-period">24H</span>
            </div>
          </div>

          <div className="data-card">
            <div className="data-label">{t('aiStrategy.high24h')}</div>
            <div className="data-value">{ticker ? fmt(ticker.high24h) : '--'}</div>
            <div className="data-sub">{ticker && ticker.lastPrice ? ((ticker.high24h - ticker.lastPrice) / ticker.lastPrice * 100).toFixed(2) + '%' : ''}</div>
          </div>

          <div className="data-card">
            <div className="data-label">{t('aiStrategy.low24h')}</div>
            <div className="data-value">{ticker ? fmt(ticker.low24h) : '--'}</div>
            <div className="data-sub">{ticker && ticker.lastPrice ? ((ticker.low24h - ticker.lastPrice) / ticker.lastPrice * 100).toFixed(2) + '%' : ''}</div>
          </div>

          <div className="data-card">
            <div className="data-label">{t('aiStrategy.vol24h')}</div>
            <div className="data-value">
              {ticker ? (ticker.volume24h >= 1e6 ? (ticker.volume24h / 1e6).toFixed(2) + 'M' : ticker.volume24h >= 1e3 ? (ticker.volume24h / 1e3).toFixed(2) + 'K' : ticker.volume24h.toFixed(2)) : '--'}
            </div>
            <div className="data-sub">SUI</div>
          </div>
        </div>

        {/* Indicators strip */}
        {analysis && (
          <div className="indicators-strip">
            <div className="indicator-pill">
              <span className="ipill-label">RSI</span>
              <span className={`ipill-value ${analysis.indicators.rsi != null ? (analysis.indicators.rsi < 30 ? 'oversold' : analysis.indicators.rsi > 70 ? 'overbought' : 'neutral') : ''}`}>
                {analysis.indicators.rsi != null ? analysis.indicators.rsi.toFixed(1) : '--'}
              </span>
              <span className="ipill-meta">{analysis.rsi_analysis || ''}</span>
            </div>

            <div className="indicator-pill">
              <span className="ipill-label">MACD</span>
              <span className={`ipill-value ${analysis.indicators.macd_hist != null ? (analysis.indicators.macd_hist >= 0 ? 'positive' : 'negative') : 'neutral'}`}>
                {analysis.indicators.macd_hist != null ? (analysis.indicators.macd_hist >= 0 ? '▲' : '▼') + ' ' + Math.abs(analysis.indicators.macd_hist).toFixed(4) : '--'}
              </span>
              <span className="ipill-meta">{analysis.macd_analysis || ''}</span>
            </div>

            <div className="indicator-pill">
              <span className="ipill-label">BOLL</span>
              <span className="ipill-value neutral">
                {analysis.indicators.boll_upper != null && analysis.current_price != null
                  ? (analysis.indicators.boll_upper - analysis.current_price).toFixed(4)
                  : '--'}
              </span>
              <span className="ipill-meta">{t('aiStrategy.boll.upper')}</span>
            </div>

            <div className="indicator-pill">
              <span className="ipill-label">ATR</span>
              <span className="ipill-value neutral">
                {analysis.indicators.atr != null ? analysis.indicators.atr.toFixed(4) : '--'}
              </span>
              <span className="ipill-meta">{t('aiStrategy.atr')}</span>
            </div>
          </div>
        )}

        {/* Trend & Support/Resistance */}
        {analysis && (analysis.trend || analysis.support != null) && (
          <div className="analysis-strip">
            <div className="strip-item">
              <span className="strip-label">{t('aiStrategy.trend')}</span>
              <span className={`strip-value trend-${analysis.trend}`}>
                {analysis.trend === 'bullish' ? t('aiStrategy.trend.bullish') : analysis.trend === 'bearish' ? t('aiStrategy.trend.bearish') : t('aiStrategy.trend.sideways')}
              </span>
            </div>
            <div className="strip-item">
              <span className="strip-label">{t('aiStrategy.support')}</span>
              <span className="strip-value mono">{fmt(analysis.support)}</span>
            </div>
            <div className="strip-item">
              <span className="strip-label">{t('aiStrategy.resistance')}</span>
              <span className="strip-value mono">{fmt(analysis.resistance)}</span>
            </div>
            <div className="strip-item">
              <span className="strip-label">{t('aiStrategy.risk')}</span>
              <span className={`strip-value risk-${analysis.risk_level}`}>
                {analysis.risk_level === 'high' ? t('aiStrategy.risk.high') : analysis.risk_level === 'low' ? t('aiStrategy.risk.low') : t('aiStrategy.risk.medium')}
              </span>
            </div>
          </div>
        )}
      </section>

      {/* ========== Section 02: AI Analysis ========== */}
      <section className="ai-section analysis-section">
        <div className="section-header">
          <h2 className="section-title">
            <span className="title-mono">02</span>
            <span>{t('aiStrategy.section.aiAnalysis')}</span>
            <span className="title-sub">{t('aiStrategy.section.aiSub')}</span>
          </h2>
        </div>

        {!aiSignal && !loadingAI && (
          <div className="ai-cta">
            <div className="ai-cta-text">
              <h3>{t('aiStrategy.cta.title')}</h3>
              <p>{t('aiStrategy.cta.desc')}</p>
            </div>
            <button className="btn-ai-primary" onClick={runAIAnalysis} disabled={loadingAI}>
              <span className="ai-icon">⚡</span>
              <span>{loadingData ? t('aiStrategy.cta.loading') : t('aiStrategy.cta.start')}</span>
            </button>
          </div>
        )}

        {loadingAI && (
          <div className="ai-loading">
            <div className="loader-grid">
              <span /><span /><span /><span />
              <span /><span /><span /><span />
              <span /><span /><span /><span />
            </div>
            <p className="loading-text">{t('aiStrategy.loading')}</p>
            <p className="loading-sub">{t('aiStrategy.loadingSub')}</p>
          </div>
        )}

        {aiSignal && (
          <div className={`recommendation-card ${decisionClass}`}>
            {/* Header: direction + confidence */}
            <div className="rec-header">
              <div className="rec-direction">
                <div className="rec-arrow-wrap">
                  <div className="rec-arrow">{decision === 'BUY' ? '↗' : decision === 'SELL' ? '↘' : '→'}</div>
                </div>
                <div>
                  <div className="rec-eyebrow">{t('aiStrategy.aiAdvice')}</div>
                  <div className="rec-action">{decisionLabel} SUI</div>
                </div>
              </div>

              <div className="rec-confidence">
                <div className="conf-ring">
                  <svg viewBox="0 0 100 100" className="conf-svg">
                    <circle cx="50" cy="50" r="42" className="conf-bg" />
                    <circle
                      cx="50" cy="50" r="42"
                      className="conf-fill"
                      strokeDasharray={2 * Math.PI * 42}
                      strokeDashoffset={2 * Math.PI * 42 * (1 - aiSignal.confidence / 100)}
                    />
                  </svg>
                  <div className="conf-text">
                    <div className="conf-num">{aiSignal.confidence}</div>
                    <div className="conf-unit">%</div>
                  </div>
                </div>
                <div className="conf-label">{t('aiStrategy.confidence')}</div>
              </div>
            </div>

            {/* Price block */}
            <div className="rec-prices">
              <div className="price-block entry">
                <div className="price-label">{t('aiStrategy.entryPrice')}</div>
                <div className="price-value">{fmt(aiSignal.entry_price)}</div>
                <div className="price-meta">USDC</div>
              </div>
              <div className="price-arrow">→</div>
              <div className="price-block take-profit">
                <div className="price-label">{t('aiStrategy.takeProfit')}</div>
                <div className="price-value">↑ {fmt(aiSignal.take_profit)}</div>
                <div className="price-meta">
                  +{(((aiSignal.take_profit - aiSignal.entry_price) / aiSignal.entry_price) * 100).toFixed(2)}%
                </div>
              </div>
              <div className="price-block stop-loss">
                <div className="price-label">{t('aiStrategy.stopLoss')}</div>
                <div className="price-value">↓ {fmt(aiSignal.stop_loss)}</div>
                <div className="price-meta">
                  {(((aiSignal.stop_loss - aiSignal.entry_price) / aiSignal.entry_price) * 100).toFixed(2)}%
                </div>
              </div>
            </div>

            {/* Action recommendation — explicit operation instruction */}
            {aiSignal.action_recommendation && (
              <div className={`rec-action-bar ${decisionClass}`}>
                <div className="action-bar-label">{t('aiStrategy.suggestedAction')}</div>
                <div className="action-bar-text">{aiSignal.action_recommendation}</div>
              </div>
            )}

            {/* Summary */}
            <div className="rec-summary">{aiSignal.summary}</div>

            {/* Reasons */}
            {aiSignal.key_reasons && aiSignal.key_reasons.length > 0 && (
              <div className="rec-reasons">
                <h4>
                  <span className="reason-icon">◎</span>
                  {t('aiStrategy.reasons')}
                </h4>
                <ol>
                  {aiSignal.key_reasons.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ol>
              </div>
            )}

            {/* Risks */}
            {aiSignal.risks && aiSignal.risks.length > 0 && (
              <div className="rec-risks">
                <h4>
                  <span className="reason-icon">⚠</span>
                  {t('aiStrategy.risks')}
                </h4>
                <ul>
                  {aiSignal.risks.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Performance track record */}
            {performance && (
              <div className="rec-performance">
                <h4>
                  <span className="reason-icon">◈</span>
                  {t('aiStrategy.performance')}
                </h4>
                <div className="perf-stats">
                  <div className="perf-stat">
                    <div className="perf-label">{t('aiStrategy.perf.total')}</div>
                    <div className="perf-value">{performance.total_analyses ?? '--'}</div>
                  </div>
                  <div className="perf-stat">
                    <div className="perf-label">{t('aiStrategy.perf.correct')}</div>
                    <div className="perf-value positive">{performance.correct_count ?? 0}</div>
                  </div>
                  <div className="perf-stat">
                    <div className="perf-label">{t('aiStrategy.perf.incorrect')}</div>
                    <div className="perf-value negative">{performance.incorrect_count ?? 0}</div>
                  </div>
                  <div className="perf-stat">
                    <div className="perf-label">{t('aiStrategy.perf.accuracy')}</div>
                    <div className={`perf-value ${(performance.accuracy ?? 0) >= 50 ? 'positive' : 'negative'}`}>
                      {performance.accuracy != null ? performance.accuracy.toFixed(1) + '%' : '--'}
                    </div>
                  </div>
                  <div className="perf-stat">
                    <div className="perf-label">{t('aiStrategy.perf.symbols')}</div>
                    <div className="perf-value">{performance.unique_symbols ?? '--'}</div>
                  </div>
                </div>
                {(!performance.total_analyses || performance.total_analyses < 3) && (
                  <div className="perf-hint">{t('aiStrategy.perf.hint')}</div>
                )}
              </div>
            )}

            <div className="rec-actions">
              <button className="btn-ai-secondary" onClick={runAIAnalysis} disabled={loadingAI}>
                {loadingAI ? t('aiStrategy.reanalyzing') : t('aiStrategy.reanalyze')}
              </button>
            </div>

            {/* Quick question chips - centered around SUI/USDC + DeepBook V3 */}
            <div className="quick-q-section">
              <div className="quick-q-header">
                <span className="quick-q-title">{t('aiStrategy.qqTitle')}</span>
                <span className="quick-q-sub">{t('aiStrategy.qqSub')}</span>
              </div>
              <div className="quick-q-chips">
                {(() => {
                  const decision = aiSignal.decision
                  // Default: show 4 matching items
                  const primary = QUICK_QUESTIONS.filter(q => q.decisions.includes(decision)).slice(0, 4)
                  // Show the rest in "more"
                  const primaryTypes = new Set(primary.map(q => q.type))
                  const secondary = QUICK_QUESTIONS.filter(q => !primaryTypes.has(q.type))
                  const visible = showMore ? [...primary, ...secondary] : primary
                  return visible.map(q => (
                    <button
                      key={q.type}
                      className={`qq-chip ${askingType === q.type ? 'loading' : ''}`}
                      onClick={() => askQuestion(q)}
                      disabled={!!askingType}
                    >
                      <span className="qq-icon">{askingType === q.type ? '⏳' : q.icon}</span>
                      <span className="qq-label">{t(q.labelKey)}</span>
                    </button>
                  ))
                })()}
              </div>
              {(() => {
                const decision = aiSignal.decision
                const primary = QUICK_QUESTIONS.filter(q => q.decisions.includes(decision)).slice(0, 4)
                const primaryTypes = new Set(primary.map(q => q.type))
                const secondary = QUICK_QUESTIONS.filter(q => !primaryTypes.has(q.type))
                if (secondary.length === 0) return null
                return (
                  <button className="qq-more-btn" onClick={() => setShowMore(!showMore)}>
                    {showMore ? t('aiStrategy.qqLess') : t('aiStrategy.qqMore', { count: secondary.length })}
                  </button>
                )
              })()}

              {/* Q&A history */}
              {qaHistory.length > 0 && (
                <div className="qa-history">
                  <div className="qa-history-header" onClick={() => setQaExpanded(!qaExpanded)}>
                    <span className="qa-history-title">{t('aiStrategy.qqHistory', { count: qaHistory.length })}</span>
                    <span className="qa-history-toggle">{qaExpanded ? '▼' : '▶'}</span>
                  </div>
                  {qaExpanded && (
                    <div className="qa-history-list">
                      {qaHistory.map(entry => {
                        const meta = QUICK_QUESTIONS.find(q => q.type === entry.type)
                        return (
                          <div key={entry.id} className="qa-item">
                            <div className="qa-question">
                              <span className="qa-icon">{meta?.icon || '💬'}</span>
                              <span className="qa-q-text">{entry.question}</span>
                            </div>
                            <div className="qa-answer">
                              {entry.loading ? (
                                <div className="qa-loading">
                                  <span className="qa-spinner">⏳</span>
                                  <span>{t('aiStrategy.qqLoading')}</span>
                                </div>
                              ) : entry.error ? (
                                <div className="qa-error">⚠ {entry.error}</div>
                              ) : (
                                <div className="qa-text">{entry.answer}</div>
                              )}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </section>

      {/* ========== Section 03: One-Click Order ========== */}
      {aiSignal && decision !== 'HOLD' && (
        <section className="ai-section order-section">
          <div className="section-header">
            <h2 className="section-title">
              <span className="title-mono">03</span>
              <span>{t('aiStrategy.section.oneClick')}</span>
              <span className="title-sub">{t('aiStrategy.section.oneClickSub')}</span>
            </h2>
            <div className={`order-direction-tag ${decisionClass}`}>
              {decisionLabel}
            </div>
          </div>

          <div className="order-panel">
            <div className="balance-row">
              <div className="balance-item">
                <div className="balance-label">{t('aiStrategy.balanceSui')}</div>
                <div className="balance-amount">{walletSui.toFixed(4)}</div>
              </div>
              <div className="balance-item">
                <div className="balance-label">{t('aiStrategy.balanceUsdc')}</div>
                <div className="balance-amount">{walletUsdc.toFixed(2)}</div>
              </div>
              <div className="balance-item">
                <div className="balance-label">{t('aiStrategy.positionSize')}</div>
                <div className="balance-amount">
                  {aiSignal.position_size_pct ?? 10}%
                </div>
              </div>
            </div>

            <div className="order-form">
              <div className="form-row">
                <label>{t('aiStrategy.field.amount')}</label>
                <div className="input-with-suffix">
                  <input
                    type="number"
                    step="0.1"
                    min="0.1"
                    value={quantity}
                    onChange={(e) => setQuantity(e.target.value)}
                    placeholder={decision === 'BUY' ? t('aiStrategy.placeholder.buy') : t('aiStrategy.placeholder.sell')}
                  />
                  <span className="suffix">SUI</span>
                </div>
                {decision === 'SELL' && walletSui > 0 && (
                  <button className="max-btn" onClick={() => setQuantity(Math.max(0, walletSui - 0.02).toFixed(4))}>
                    MAX
                  </button>
                )}
                {decision === 'BUY' && walletUsdc > 0 && aiSignal.entry_price > 0 && (
                  <button className="max-btn" onClick={() => setQuantity((walletUsdc / aiSignal.entry_price * 0.98).toFixed(4))}>
                    MAX
                  </button>
                )}
              </div>

              {quantity && parseFloat(quantity) > 0 && (
                <div className="order-preview">
                  <div className="preview-row">
                    <span>{t('aiStrategy.preview.price')}</span>
                    <span className="mono">{fmt(aiSignal.entry_price)} USDC</span>
                  </div>
                  <div className="preview-row">
                    <span>{t('aiStrategy.preview.amount')}</span>
                    <span className="mono">{parseFloat(quantity).toFixed(4)} SUI</span>
                  </div>
                  <div className="preview-row total">
                    <span>{t('aiStrategy.preview.total')}</span>
                    <span className="mono">{(parseFloat(quantity) * aiSignal.entry_price).toFixed(4)} USDC</span>
                  </div>
                </div>
              )}

              <button
                className={`btn-execute ${decisionClass}`}
                onClick={handleOrder}
                disabled={submitting || !quantity || parseFloat(quantity) <= 0 || !bmId}
              >
                {submitting ? (
                  <span>{t('aiStrategy.preview.processing')}</span>
                ) : (
                  <>
                    <span className="execute-icon">
                      {decision === 'BUY' ? '▲' : '▼'}
                    </span>
                    <span>
                      {t('aiStrategy.btn.execute', { decision: decisionLabel, price: fmt(aiSignal.entry_price) })}
                    </span>
                  </>
                )}
              </button>

              {!bmId && (
                <div className="hint">
                  {t('aiStrategy.bmHint')}
                </div>
              )}

              {orderResult && <div className="success-message">{orderResult}</div>}
            </div>
          </div>
        </section>
      )}

      {error && <div className="error-toast">{error}</div>}
    </div>
  )
}

export default AIStrategyPage
