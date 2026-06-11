import { useState, useCallback, useEffect, useRef } from 'react'
import { useCurrentAccount, useSignTransaction, useSuiClient } from '@mysten/dapp-kit'
import { Transaction } from '@mysten/sui/transactions'
import { useI18n, TranslationKey } from '../i18n/I18nProvider'
import './AIChatPage.css'

// Constants
const UTILS_PKG = '0x600138d3179e2fc746f6774f360a6e1fa68e90d66d082af66399adabe46f22a4'
const GLOBAL_CONFIG = '0xff1141ef80e7baf206c7930c274b465600e64884d8167f90d4cdb60197925163'
const CETUS_BM_INDEXER = '0x5c1a039f97ed1cbd84d54b5d633bdffd681086acc38961b1d366c4ecf680d150'
const SUI_USDC_POOL = '0xe05dafb5133bcffb8d59f4e12465dc0e9faeaa05e3e342a08fe135800e3e4407'
const USDC_COIN = '0xdba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC'
const SUI_COIN = '0x2::sui::SUI'
const DEEP_COIN = '0xdeeb7a4662eec9f2f3def03fb937a663dddaa2e215b8078a284d026b7946c270::deep::DEEP'

// Protocol fee (sui_intent_fee::protocol_fee) — 0.005 SUI per intent
// Package & Treasury published 2026-06-03 to Sui mainnet.
const FEE_PKG = '0xad95919bbc8e08a36c28bf885fd7e8413296f63979d13b329d8713424157fd90'
const FEE_TREASURY = '0x5e54f169aa2df2c3fe2a7624170d1c85feb7ebf9b54f57e51cb80fc84578ed91'
const FEE_MIST = 5_000_000 // 0.005 SUI per intent (must match on-chain fee_per_intent)

// Backend endpoints — empty string means relative URL
// (Vite proxy in dev, Vercel rewrites in prod) will route them to the right backend.
const QUANT_API = ''
const DEEPBOOK_API = ''

interface Message {
  id?: string
  role: 'user' | 'ai'
  content: string
  timestamp: number
  loading?: boolean
  error?: string
  questionType?: string
  questionLabel?: string
  recommendedPrice?: number  // LLM recommended price (used for the order button in limit_price type)
}

interface OrderProposal {
  action: 'buy' | 'sell'
  price: number
  quantity: number
  reason: string
  totalCost?: number
  estimatedReceive?: number
  // Editable order form context
  availableBalance?: number     // Available balance (BUY=USDC, SELL=SUI)
  balanceCurrency?: 'SUI' | 'USDC'
  maxQuantity?: number          // Maximum buyable/sellable quantity calculated from balance
}

interface QuickQuestion {
  type: string
  labelKey: TranslationKey
  icon: string
}

const QUICK_QUESTIONS: QuickQuestion[] = [
  { type: 'limit_price', labelKey: 'aiChat.qq.limitPrice', icon: '🎯' },
  { type: 'maker_vs_taker', labelKey: 'aiChat.qq.makerVsTaker', icon: '⚖️' },
  { type: 'bm_allocation', labelKey: 'aiChat.qq.bmAllocation', icon: '💼' },
  { type: 'expired_order', labelKey: 'aiChat.qq.expiredOrder', icon: '⏰' },
  { type: 'depth_check', labelKey: 'aiChat.qq.depthCheck', icon: '🌊' },
  { type: 'liquidity_trend', labelKey: 'aiChat.qq.liquidityTrend', icon: '📈' },
  { type: 'reasoning', labelKey: 'aiChat.qq.reasoning', icon: '🤔' },
  { type: 'multi_timeframe', labelKey: 'aiChat.qq.multiTimeframe', icon: '🔄' },
]

/**
 * Extract recommended price from LLM response
 * - Match $X.XXXX pattern
 * - Filter candidates within 3% of currentPrice (excludes stop-loss/take-profit and other distant prices)
 * - Return the median (more robust, handles multiple batched limit orders)
 */
function extractRecommendedPrice(answer: string, currentPrice: number | null): number | undefined {
  if (!currentPrice) return undefined
  const priceRegex = /\$?(\d+\.\d{2,6})/g
  const priceMatches: RegExpExecArray[] = []
  let pm: RegExpExecArray | null
  while ((pm = priceRegex.exec(answer)) !== null) {
    priceMatches.push(pm)
  }
  const candidates: number[] = []
  for (const m of priceMatches) {
    const p = parseFloat(m[1])
    if (p > 0 && Math.abs(p - currentPrice) / currentPrice < 0.03) {
      candidates.push(p)
    }
  }
  if (candidates.length === 0) return undefined
  candidates.sort((a, b) => a - b)
  return candidates[Math.floor(candidates.length / 2)]
}

function AIChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [proposal, setProposal] = useState<OrderProposal | null>(null)
  const [executing, setExecuting] = useState(false)
  const [txResult, setTxResult] = useState<string | null>(null)
  const [askingType, setAskingType] = useState<string | null>(null)
  // Wallet balance cache (used directly when clicking "Buy at recommended price", no waiting)
  const [walletBalances, setWalletBalances] = useState<{ usdc: number; sui: number; ts: number } | null>(null)
  const balanceRef = useRef(walletBalances)
  balanceRef.current = walletBalances
  const account = useCurrentAccount()
  const { mutate: signTransaction } = useSignTransaction()
  const suiClient = useSuiClient()
  const { t, locale } = useI18n()

  // Fetch and cache wallet balance (USDC + SUI)
  const refreshWalletBalance = useCallback(async (silent = true) => {
    const addr = account?.address
    if (!addr) {
      setWalletBalances(null)
      return
    }
    try {
      const [usdcData, suiData] = await Promise.all([
        suiClient.getBalance({ owner: addr, coinType: USDC_COIN }),
        suiClient.getBalance({ owner: addr, coinType: SUI_COIN }),
      ])
      setWalletBalances({
        usdc: Number(usdcData.totalBalance) / 1e6,
        sui: Number(suiData.totalBalance) / 1e9,
        ts: Date.now(),
      })
    } catch (e) {
      if (!silent) console.error('Balance fetch error:', e)
    }
  }, [account?.address, suiClient])

  // Wallet switch / first mount: pull once immediately
  useEffect(() => {
    refreshWalletBalance(false)
  }, [refreshWalletBalance])

  // Silent refresh every 30 seconds (keep data fresh)
  useEffect(() => {
    if (!account?.address) return
    const timer = setInterval(() => refreshWalletBalance(true), 30000)
    return () => clearInterval(timer)
  }, [account?.address, refreshWalletBalance])

  // Collect real-time data for question context
  const fetchContextData = useCallback(async () => {
    const ctx: Record<string, any> = {}

    try {
      // 1) Market ticker
      const tickerResp = await fetch(`${DEEPBOOK_API}/api/v1/cache/ticker`)
      const tickerData = await tickerResp.json()
      if (tickerData.success && tickerData.data) {
        const tk = tickerData.data
        ctx.last_price = tk.last_price
        ctx.best_bid = (tk.last_price * 0.9995).toFixed(4)
        ctx.best_ask = (tk.last_price * 1.0005).toFixed(4)
        ctx.spread_bps = t('aiChat.ctx.spread')
        ctx.high_24h = tk.high
        ctx.low_24h = tk.low
        ctx.volume_24h = tk.volume
        ctx.change_24h = tk.price_change_percent
        ctx.bid_depth = `${t('aiChat.ctx.depthPrefix')}${Math.round(tk.volume * 0.005)}${t('aiChat.ctx.depthSuffix')}`
        ctx.ask_depth = `${t('aiChat.ctx.depthPrefix')}${Math.round(tk.volume * 0.005)}${t('aiChat.ctx.depthSuffix')}`
        ctx.ask_levels = t('aiChat.ctx.askLevels')
      }
    } catch (e) {
      console.error('Ticker fetch error:', e)
    }

    try {
      // 2) Technical indicators
      const analysisResp = await fetch(`${QUANT_API}/api/v1/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: 'SUI/USDT', timeframe: '1h', days: 7, language: locale === 'zh' ? 'zh-CN' : 'en' })
      })
      const analysisData = await analysisResp.json()
      if (analysisData.success && analysisData.data) {
        const ind = analysisData.data.indicators || {}
        ctx.rsi = ind.rsi?.toFixed(1)
        ctx.macd = ind.macd?.toFixed(4)
        ctx.macd_hist = ind.macd_hist?.toFixed(4)
        ctx.boll_upper = ind.boll_upper?.toFixed(4)
        ctx.boll_lower = ind.boll_lower?.toFixed(4)
        ctx.atr = ind.atr?.toFixed(4)
        ctx.trend = analysisData.data.trend
        ctx.support = analysisData.data.support?.toFixed(4)
        ctx.resistance = analysisData.data.resistance?.toFixed(4)
        ctx.rsi_analysis = analysisData.data.rsi_analysis
        ctx.macd_analysis = analysisData.data.macd_analysis
      }
    } catch (e) {
      console.error('Analysis fetch error:', e)
    }

    // 3) Wallet balance
    if (account?.address) {
      try {
        const [sui, usdc] = await Promise.all([
          suiClient.getBalance({ owner: account.address, coinType: SUI_COIN }),
          suiClient.getBalance({ owner: account.address, coinType: USDC_COIN })
        ])
        ctx.wallet_sui = (Number(sui.totalBalance) / 1e9).toFixed(4)
        ctx.wallet_usdc = (Number(usdc.totalBalance) / 1e6).toFixed(2)
      } catch (e) {
        console.error('Balance fetch error:', e)
      }
    }

    return ctx
  }, [account?.address, suiClient, t])

  // Click preset question
  const askQuestion = useCallback(async (q: QuickQuestion) => {
    if (askingType) return

    setAskingType(q.type)
    const userMsgId = `user-${Date.now()}`
    const aiMsgId = `ai-${Date.now()}`

    // User message
    const userMsg: Message = {
      id: userMsgId,
      role: 'user',
      content: `${q.icon} ${t(q.labelKey)}`,
      timestamp: Date.now(),
      questionType: q.type,
      questionLabel: t(q.labelKey),
    }
    // AI loading placeholder
    const aiMsg: Message = {
      id: aiMsgId,
      role: 'ai',
      content: '',
      timestamp: Date.now(),
      loading: true,
      questionType: q.type,
    }
    setMessages(prev => [...prev, userMsg, aiMsg])

    try {
      // Auto-fetch data (user doesn't need to analyze manually)
      const ctx = await fetchContextData()
      ctx.question_type = q.type

      const resp = await fetch(`${QUANT_API}/api/v1/ai/quick-question`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question_type: q.type,
          symbol: 'SUI/USDT',
          language: locale === 'zh' ? 'zh-CN' : 'en',
          context: ctx,
        }),
      })
      const data = await resp.json()

      if (data.success) {
        // Limit price question: auto-extract recommended price from LLM response for the "Order at this price" button
        let recommendedPrice: number | undefined
        if (q.type === 'limit_price') {
          recommendedPrice = extractRecommendedPrice(data.answer, ctx.last_price)
        }

        setMessages(prev => prev.map(m =>
          m.id === aiMsgId
            ? { ...m, content: data.answer, loading: false, recommendedPrice }
            : m
        ))
      } else {
        setMessages(prev => prev.map(m =>
          m.id === aiMsgId
            ? { ...m, content: '', loading: false, error: data.detail || t('aiChat.error.unknown') }
            : m
        ))
      }
    } catch (e) {
      setMessages(prev => prev.map(m =>
        m.id === aiMsgId
          ? { ...m, content: '', loading: false, error: (e as Error).message }
          : m
      ))
    } finally {
      setAskingType(null)
    }
  }, [askingType, fetchContextData, locale, t])

  const handleSend = useCallback(async () => {
    if (!input.trim() || !account) return

    const userMessage: Message = {
      role: 'user',
      content: input,
      timestamp: Date.now()
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)
    setProposal(null)
    setTxResult(null)

    try {
      // Fetch current market price
      const priceResponse = await fetch('/market/price/SUI')
      const priceData = await priceResponse.json()
      const currentPrice = priceData.success ? priceData.price : 1.27

      // Fetch wallet SUI balance
      let walletBalance = 0
      try {
        const balanceData = await suiClient.getBalance({
          owner: account.address,
          coinType: '0x2::sui::SUI'
        })
        walletBalance = Number(balanceData.totalBalance) / 1e9
      } catch (e) {
        console.error('Failed to fetch wallet balance:', e)
      }

      // Call backend API to parse intent
      const response = await fetch('/intent/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: input,
          use_llm: true
        })
      })

      const data = await response.json()

      if (!data.success) {
        throw new Error(data.error || t('aiChat.error.getStrategy'))
      }

      // Extract target price from user input
      const priceMatch = input.match(/(\d+\.?\d*)\s*[Uu]/)
      let targetPrice: number | null = priceMatch ? parseFloat(priceMatch[1]) : null

      // Parse quantity from user input (prefer user-stated quantity)
      // User says "1个SUI" or "1 SUI" -> quantity = 1
      const quantityMatch = input.match(/(\d+\.?\d*)\s*[个]?[Ss][Uu][Ii]/i)
      let quantity = 1
      if (quantityMatch) {
        quantity = parseFloat(quantityMatch[1])
      }

      // Determine buy or sell (supports both Chinese and English; defaults to buy)
      const hasBuyKw = /买|买入|做多|\bbuy\b|\blong\b|\bbull\b/i.test(input)
      const hasSellKw = /卖|卖出|做空|\bsell\b|\bshort\b|\bbear\b/i.test(input)
      const isBuy = hasBuyKw || !hasSellKw

      // Detect whether the user is asking for a price recommendation (supports both Chinese and English keywords)
      const isAskingForRecommendation = !targetPrice && /推荐|建议|什么价|怎么挂|多少钱|帮我挂|挂个|挂一|recommend|suggest|best price|what price|how (to|should)|what's the best|good price|optimal price/i.test(input)

      // When the user has not specified a price, let LLM recommend based on market analysis
      let llmReasoning = ''
      if (isAskingForRecommendation) {
        try {
          const ctx = await fetchContextData()
          const llmResp = await fetch(`${QUANT_API}/api/v1/ai/quick-question`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              question_type: 'limit_price',
              symbol: 'SUI/USDT',
              language: locale === 'zh' ? 'zh-CN' : 'en',
              context: {
                ...ctx,
                decision: isBuy ? 'BUY' : 'SELL',
                entry_price: currentPrice,
                stop_loss: currentPrice * 0.97,
                take_profit: currentPrice * 1.05,
                best_bid: (currentPrice * 0.9995).toFixed(4),
                best_ask: (currentPrice * 1.0005).toFixed(4),
              }
            })
          })
          const llmData = await llmResp.json()
          if (llmData.success && llmData.answer) {
            llmReasoning = llmData.answer
            // Extract price from LLM response (match $X.XXXX pattern, pick closest to current price with < 3% deviation)
            const priceRegex = /\$?(\d+\.\d{2,6})/g
            const priceMatches: RegExpExecArray[] = []
            let pm: RegExpExecArray | null
            while ((pm = priceRegex.exec(llmData.answer)) !== null) {
              priceMatches.push(pm)
            }
            const candidates: number[] = []
            for (const m of priceMatches) {
              const p = parseFloat(m[1])
              if (p > 0 && Math.abs(p - currentPrice) / currentPrice < 0.03) {
                candidates.push(p)
              }
            }
            if (candidates.length > 0) {
              // Take the median (more robust)
              candidates.sort((a, b) => a - b)
              targetPrice = candidates[Math.floor(candidates.length / 2)]
            }
          }
        } catch (e) {
          console.error('LLM price recommendation failed:', e)
        }
      }

      // Final fallback: if LLM didn't give a price either, use market price ±0.5% (much more reasonable than the previous -5%)
      if (targetPrice == null) {
        targetPrice = isBuy ? currentPrice * 0.995 : currentPrice * 1.005
      }

      // When selling, check if wallet SUI balance is sufficient
      if (!isBuy && walletBalance < quantity) {
        const errorMsg: Message = {
          role: 'ai',
          content: t('aiChat.insufficientSui', { available: walletBalance.toFixed(4), requested: quantity }),
          timestamp: Date.now()
        }
        setMessages(prev => [...prev, errorMsg])
        setLoading(false)
        return
      }

      // Generate order proposal
      const orderProposal: OrderProposal = {
        action: isBuy ? 'buy' : 'sell',
        price: targetPrice,
        quantity: typeof quantity === 'number' ? quantity : parseFloat(quantity) || 1,
        reason: isBuy
          ? t('aiChat.reason.buy', { current: currentPrice.toFixed(4), target: targetPrice.toFixed(4) })
          : t('aiChat.reason.sell', { current: currentPrice.toFixed(4), target: targetPrice.toFixed(4), balance: walletBalance.toFixed(4) }),
        totalCost: isBuy ? targetPrice * quantity : undefined,
        estimatedReceive: isBuy ? undefined : targetPrice * quantity
      }

      setProposal(orderProposal)

      let aiContent = t('aiChat.aiResponse', {
        basis: isAskingForRecommendation ? t('aiChat.basis.marketAndLlm') : t('aiChat.basis.userInput'),
        action: isBuy ? t('aiChat.action.buy') : t('aiChat.action.sell'),
        currentPrice: currentPrice.toFixed(4),
        suggestedPrice: targetPrice.toFixed(4),
        deviationPct: (((targetPrice - currentPrice) / currentPrice) * 100).toFixed(2),
        belowOrAbove: targetPrice < currentPrice ? t('aiChat.below') : t('aiChat.above'),
        quantity: String(orderProposal.quantity),
        walletBalance: walletBalance.toFixed(4),
        totalCostLine: orderProposal.totalCost ? t('aiChat.line.totalCost', { amount: orderProposal.totalCost.toFixed(4) }) : '',
        estimatedReceiveLine: orderProposal.estimatedReceive ? t('aiChat.line.estimatedReceive', { amount: orderProposal.estimatedReceive.toFixed(4) }) : '',
        llmReasoningBlock: llmReasoning ? t('aiChat.line.llmReasoning', { reasoning: llmReasoning }) : '',
      })

      const aiMessage: Message = {
        role: 'ai',
        content: aiContent,
        timestamp: Date.now()
      }
      setMessages(prev => [...prev, aiMessage])

    } catch (error) {
      const errorMessage: Message = {
        role: 'ai',
        content: t('aiChat.error.generic', { message: (error as Error).message }),
        timestamp: Date.now()
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }, [input, account, fetchContextData, locale, t])

  const handleExecute = useCallback(() => {
    if (!proposal || !account) return

    const existingBmId = localStorage.getItem('balanceManagerId')
    const isNewBM = !existingBmId

    setExecuting(true)

    const tx = new Transaction()
    tx.setGasBudget(55000000) // 50M base + 5M for protocol fee
    tx.setSender(account.address)

    // 1. Pay the protocol fee first (0.005 SUI per intent).
    //    Split a fee coin from gas, then call pay_fee which puts the fee
    //    in the shared ProtocolTreasury and returns any overpay to sender.
    const [feeCoin] = tx.splitCoins(tx.gas, [BigInt(FEE_MIST)])
    const intentTypeBytes = Array.from(new TextEncoder().encode('intent'))
    tx.moveCall({
      target: `${FEE_PKG}::protocol_fee::pay_fee`,
      arguments: [
        tx.object(FEE_TREASURY),
        feeCoin,
        tx.pure.vector('u8', intentTypeBytes),
      ],
    })

    // 2. Then split the trade coin from the (now reduced) gas.
    const [suiCoin] = tx.splitCoins(tx.gas, [BigInt(Math.floor(proposal.quantity * 1e9))])

    const [usdcZero] = tx.moveCall({
      target: '0x2::coin::zero',
      arguments: [],
      typeArguments: [USDC_COIN],
    })

    const [deepZero] = tx.moveCall({
      target: '0x2::coin::zero',
      arguments: [],
      typeArguments: [DEEP_COIN],
    })

    if (isNewBM) {
      // When no BM exists, use create_deposit_then_place_limit_order to create and place order
      tx.moveCall({
        target: `${UTILS_PKG}::deepbookv3_utils::create_deposit_then_place_limit_order`,
        arguments: [
          tx.object(GLOBAL_CONFIG),
          tx.object(CETUS_BM_INDEXER),
          tx.object(SUI_USDC_POOL),
          suiCoin,
          usdcZero,
          deepZero,
          tx.pure.u8(0),
          tx.pure.u8(0),
          tx.pure.u64(Math.floor(proposal.price * 1e6)),
          tx.pure.u64(BigInt(Math.floor(proposal.quantity * 1e9))),
          tx.pure.bool(proposal.action === 'sell'),
          tx.pure.bool(false),
          tx.pure.u64(Date.now() * 1e6 + 3600 * 1e6),
          tx.object.clock(),
        ],
        typeArguments: [SUI_COIN, USDC_COIN],
      })
    } else {
      // When BM exists, use deposit_then_place_limit_order_by_owner
      tx.moveCall({
        target: `${UTILS_PKG}::deepbookv3_utils::deposit_then_place_limit_order_by_owner`,
        arguments: [
          tx.object(GLOBAL_CONFIG),
          tx.object(CETUS_BM_INDEXER),
          tx.object(SUI_USDC_POOL),
          tx.object(existingBmId),
          suiCoin,
          usdcZero,
          deepZero,
          tx.pure.u8(0),
          tx.pure.u8(0),
          tx.pure.u64(Math.floor(proposal.price * 1e6)),
          tx.pure.u64(BigInt(Math.floor(proposal.quantity * 1e9))),
          tx.pure.bool(proposal.action === 'sell'),
          tx.pure.bool(false),
          tx.pure.u64(Date.now() * 1e6 + 3600 * 1e6),
          tx.object.clock(),
        ],
        typeArguments: [SUI_COIN, USDC_COIN],
      })
    }

    signTransaction(
      { transaction: tx as any, chain: 'sui:mainnet' } as any,
      {
        onSuccess: async (result: any) => {
          try {
            const execResult = await suiClient.executeTransactionBlock({
              transactionBlock: result.bytes,
              signature: result.signature,
              options: { showEffects: true, showEvents: true }
            })
            if (execResult.effects?.status?.status === 'success') {
              // If a new BM was created, extract ID from event and save
              if (isNewBM && execResult.events) {
                for (const event of execResult.events) {
                  // BalanceManager creation event
                  if (event.type?.includes('BalanceManagerEvent') || event.type?.includes('NewBalanceManager')) {
                    const parsed = event.parsedJson as any
                    const bmId = parsed?.balance_manager_id || parsed?.object_id
                    if (bmId) {
                      localStorage.setItem('balanceManagerId', bmId)
                      break
                    }
                  }
                }
              }
              // Look for the FeePaid event emitted by sui_intent_fee::protocol_fee
              const feeEvent = (execResult.events || []).find(
                (e: any) => typeof e?.type === 'string' && e.type.endsWith('::protocol_fee::FeePaid')
              )
              const feeNote = feeEvent
                ? ` · fee 0.005 SUI (#${(feeEvent.parsedJson as any)?.intent_number ?? '?'})`
                : ''
              setTxResult(t('aiChat.orderOk', { digest: execResult.digest }) + feeNote)
              setProposal(null)
            } else {
              setTxResult(t('aiChat.orderFailed'))
            }
          } catch (e) {
            setTxResult(t('aiChat.execFailed', { message: (e as Error).message }))
          } finally {
            setExecuting(false)
          }
        },
        onError: () => {
          setTxResult(t('aiChat.signRejected'))
          setExecuting(false)
        }
      }
    )
  }, [proposal, account, signTransaction, suiClient, t])

  const handleReject = useCallback(() => {
    setProposal(null)
    setTxResult(null)
    setMessages(prev => [...prev, {
      role: 'ai',
      content: t('aiChat.continuePrompt'),
      timestamp: Date.now()
    }])
  }, [t])

  // Generate order proposal directly from LLM recommended price
  const handleCreateOrderFromRecommendation = useCallback(async (price: number) => {
    if (!account) return
    try {
      // Prefer cached balance (zero-delay form popup)
      // If cache doesn't exist (rare: just mounted, not fetched yet), silently fetch once
      let usdcBalance = balanceRef.current?.usdc ?? 0
      let suiBalance = balanceRef.current?.sui ?? 0
      if (!balanceRef.current) {
        const [usdcData, suiData] = await Promise.all([
          suiClient.getBalance({ owner: account.address, coinType: USDC_COIN }),
          suiClient.getBalance({ owner: account.address, coinType: SUI_COIN }),
        ])
        usdcBalance = Number(usdcData.totalBalance) / 1e6
        suiBalance = Number(suiData.totalBalance) / 1e9
        setWalletBalances({ usdc: usdcBalance, sui: suiBalance, ts: Date.now() })
      }

      // Fetch latest market price (not in cache range, prices change fast)
      let currentPrice = price
      try {
        const priceResp = await fetch('/market/price/SUI')
        const priceData = await priceResp.json()
        if (priceData.success && priceData.price) currentPrice = priceData.price
      } catch (e) {
        console.error('Price fetch error:', e)
      }

      // BUY: use USDC to buy SUI
      // Max buyable = USDC balance * 0.98 / price (reserve 2% for fees + gas)
      const maxBuyQuantity = price > 0 ? (usdcBalance * 0.98) / price : 0

      const ageStr = balanceRef.current
        ? t('aiChat.ageSuffix', { seconds: Math.round((Date.now() - balanceRef.current.ts) / 1000) })
        : ''

      const orderProposal: OrderProposal = {
        action: 'buy',
        price,
        quantity: 1,  // Default 1 SUI
        reason: t('aiChat.reasonFromLlm', {
          price: price.toFixed(4),
          current: currentPrice.toFixed(4),
          deviation: (((price - currentPrice) / currentPrice) * 100).toFixed(2),
          usdc: usdcBalance.toFixed(2),
          sui: suiBalance.toFixed(4),
          age: ageStr,
        }),
        totalCost: price,
        availableBalance: usdcBalance,
        balanceCurrency: 'USDC',
        maxQuantity: maxBuyQuantity,
      }
      setProposal(orderProposal)
      setTxResult(null)
    } catch (e) {
      console.error('Create order from recommendation error:', e)
    }
  }, [account, suiClient, t])

  return (
    <div className="ai-chat-page">
      {/* ========== Quick questions panel (persistent) ========== */}
      <div className="quick-questions-panel">
        <div className="qq-header">
          <div className="qq-title">{t('aiChat.qqTitle')}</div>
          <div className="qq-subtitle">{t('aiChat.qqSub')}</div>
        </div>
        <div className="qq-chips-grid">
          {QUICK_QUESTIONS.map(q => (
            <button
              key={q.type}
              className={`qq-chip ${askingType === q.type ? 'loading' : ''}`}
              onClick={() => askQuestion(q)}
              disabled={!!askingType || !account}
              title={!account ? t('aiChat.connectWallet') : ''}
            >
              <span className="qq-icon">{askingType === q.type ? '⏳' : q.icon}</span>
              <span className="qq-label">{t(q.labelKey)}</span>
            </button>
          ))}
        </div>
      </div>

      {/* ========== Chat area ========== */}
      <div className="chat-container">
        <div className="chat-messages">
          {messages.length === 0 && (
            <div className="chat-empty">
              <p>{t('aiChat.greeting')}</p>
              <p style={{ fontSize: '0.8rem', opacity: 0.6 }}>{t('aiChat.greeting.example')}</p>
              <p style={{ fontSize: '0.8rem', opacity: 0.6, marginTop: '0.5rem' }}>{t('aiChat.greeting.hint')}</p>
            </div>
          )}
          {messages.map((msg, i) => (
            <div key={msg.id || i} className={`message ${msg.role} ${msg.questionType ? 'qa-message' : ''}`}>
              <div className="message-content">
                {msg.loading ? (
                  <div className="qa-loading">
                    <span className="qa-spinner">⏳</span>
                    <span>{t('aiChat.loading')}</span>
                  </div>
                ) : msg.error ? (
                  <div className="qa-error">⚠ {msg.error}</div>
                ) : (
                  <div className="qa-text">{msg.content}</div>
                )}
              </div>
              {/* limit_price type: show "Order at recommended price" button after LLM returns */}
              {!msg.loading && !msg.error && msg.recommendedPrice && msg.questionType === 'limit_price' && (
                <div className="qa-action-row">
                  <button
                    className="qa-action-btn buy"
                    onClick={() => handleCreateOrderFromRecommendation(msg.recommendedPrice!)}
                    disabled={!account || executing}
                    title={!account ? t('aiChat.connectWallet') : ''}
                  >
                    {t('aiChat.buyAt', { price: msg.recommendedPrice.toFixed(4) })}
                  </button>
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div className="message ai">
              <div className="message-content">{t('aiChat.thinking')}</div>
            </div>
          )}
          {txResult && (
            <div className="message ai">
              <div className="message-content tx-result">{txResult}</div>
            </div>
          )}
        </div>

        {proposal && !txResult && (
          <div className="proposal-panel">
            <h3>{t('aiChat.proposal.title', { action: proposal.action === 'buy' ? t('aiChat.action.buy') : t('aiChat.action.sell') })}</h3>

            {/* AI recommendation reason */}
            {proposal.reason && (
              <div className="proposal-reason">{proposal.reason}</div>
            )}

            {/* Editable order form */}
            <div className="proposal-form">
              {/* Price input */}
              <div className="form-field">
                <label>{t('aiChat.proposal.field.price')}</label>
                <div className="input-with-suffix">
                  <input
                    type="number"
                    step="0.0001"
                    min="0.0001"
                    value={proposal.price}
                    onChange={(e) => {
                      const v = parseFloat(e.target.value)
                      if (!isNaN(v) && v > 0) {
                        const newMax = proposal.balanceCurrency === 'USDC'
                          ? (proposal.availableBalance || 0) * 0.98 / v
                          : (proposal.availableBalance || 0) - 0.02
                        setProposal({ ...proposal, price: v, maxQuantity: newMax })
                      }
                    }}
                  />
                  <span className="suffix">USDC</span>
                </div>
              </div>

              {/* Quantity input */}
              <div className="form-field">
                <label>{t('aiChat.proposal.field.amount')}</label>
                <div className="input-with-suffix">
                  <input
                    type="number"
                    step="0.1"
                    min="0.0001"
                    max={proposal.maxQuantity}
                    value={proposal.quantity}
                    onChange={(e) => {
                      const v = parseFloat(e.target.value)
                      if (!isNaN(v) && v > 0) {
                        setProposal({ ...proposal, quantity: v })
                      }
                    }}
                  />
                  <span className="suffix">SUI</span>
                </div>
              </div>

              {/* Percentage quick-buttons */}
              {proposal.availableBalance != null && proposal.maxQuantity != null && (
                <div className="form-field">
                  <label>{t('aiChat.proposal.field.position')}</label>
                  <div className="pct-buttons">
                    {[0.25, 0.5, 0.75, 1.0].map(pct => {
                      const qty = proposal.maxQuantity! * pct
                      return (
                        <button
                          key={pct}
                          className="pct-btn"
                          onClick={() => setProposal({ ...proposal, quantity: parseFloat(qty.toFixed(4)) })}
                          type="button"
                        >
                          {(pct * 100).toFixed(0)}%
                          <span className="pct-qty">≈ {qty.toFixed(2)}</span>
                        </button>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Balance and total info */}
              <div className="form-info">
                {proposal.availableBalance != null && (
                  <div className="info-row">
                    <span>{t('aiChat.proposal.available', { currency: proposal.balanceCurrency ?? '' })}</span>
                    <span className="mono">{(proposal.availableBalance || 0).toFixed(2)} {proposal.balanceCurrency}</span>
                  </div>
                )}
                {proposal.maxQuantity != null && proposal.maxQuantity > 0 && (
                  <div className="info-row">
                    <span>{proposal.action === 'buy' ? t('aiChat.proposal.max.buy') : t('aiChat.proposal.max.sell')}</span>
                    <span className="mono">{proposal.maxQuantity.toFixed(4)} SUI</span>
                  </div>
                )}
                <div className="info-row total">
                  <span>{proposal.action === 'buy' ? t('aiChat.proposal.estimate.buy') : t('aiChat.proposal.estimate.sell')}</span>
                  <span className="mono">{(proposal.price * proposal.quantity).toFixed(4)} {proposal.action === 'buy' ? 'USDC' : 'SUI'}</span>
                </div>
                <div className="info-row fee">
                  <span>{t('aiChat.proposal.field.fee')}</span>
                  <span className="mono">0.005 SUI</span>
                </div>
                {proposal.action === 'buy' && proposal.maxQuantity != null && proposal.price * proposal.quantity > (proposal.availableBalance || 0) * 0.98 && (
                  <div className="info-warn">{t('aiChat.proposal.warn')}</div>
                )}
              </div>
            </div>

            <div className="proposal-actions">
              <button
                className="btn btn-primary"
                onClick={handleExecute}
                disabled={
                  executing ||
                  proposal.quantity <= 0 ||
                  (proposal.maxQuantity != null && proposal.quantity > proposal.maxQuantity) ||
                  proposal.price <= 0
                }
              >
                {executing ? t('aiChat.proposal.executing') : t('aiChat.proposal.confirm')}
              </button>
              <button
                className="btn btn-secondary"
                onClick={handleReject}
                disabled={executing}
              >
                {t('aiChat.proposal.cancel')}
              </button>
            </div>
          </div>
        )}

        <div className="chat-input">
          <input
            type="text"
            placeholder={t('aiChat.placeholder')}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            disabled={!account || loading || executing}
          />
          <button onClick={handleSend} disabled={!account || loading || !input.trim() || executing}>
            {t('aiChat.send')}
          </button>
        </div>
      </div>
    </div>
  )
}

export default AIChatPage
