import { useState, useCallback } from 'react'
import { useCurrentAccount, useSignTransaction, useSuiClient } from '@mysten/dapp-kit'
import { Transaction } from '@mysten/sui/transactions'

// Constants
const UTILS_PKG = '0x600138d3179e2fc746f6774f360a6e1fa68e90d66d082af66399adabe46f22a4'
const GLOBAL_CONFIG = '0xff1141ef80e7baf206c7930c274b465600e64884d8167f90d4cdb60197925163'
const CETUS_BM_INDEXER = '0x5c1a039f97ed1cbd84d54b5d633bdffd681086acc38961b1d366c4ecf680d150'
const SUI_USDC_POOL = '0xe05dafb5133bcffb8d59f4e12465dc0e9faeaa05e3e342a08fe135800e3e4407'
const USDC_COIN = '0xdba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC'
const SUI_COIN = '0x2::sui::SUI'
const DEEP_COIN = '0xdeeb7a4662eec9f2f3def03fb937a663dddaa2e215b8078a284d026b7946c270::deep::DEEP'

interface Message {
  role: 'user' | 'ai'
  content: string
  timestamp: number
}

interface OrderProposal {
  action: 'buy' | 'sell'
  price: number
  quantity: number
  reason: string
  totalCost?: number
  estimatedReceive?: number
}

function AIChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [proposal, setProposal] = useState<OrderProposal | null>(null)
  const [executing, setExecuting] = useState(false)
  const [txResult, setTxResult] = useState<string | null>(null)
  const account = useCurrentAccount()
  const { mutate: signTransaction } = useSignTransaction()
  const suiClient = useSuiClient()

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
      // 获取当前市场价格
      const priceResponse = await fetch('/market/price/SUI')
      const priceData = await priceResponse.json()
      const currentPrice = priceData.success ? priceData.price : 1.27

      // 获取钱包 SUI 余额
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

      // 调用后端 API 解析意图
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
        throw new Error(data.error || '获取策略失败')
      }

      // 从用户输入中提取目标价格
      const priceMatch = input.match(/(\d+\.?\d*)\s*[Uu]/)
      const targetPrice = priceMatch ? parseFloat(priceMatch[1]) : currentPrice * 0.95

      // 从用户输入中解析数量（优先使用用户明确说的数量）
      // 用户说"1个SUI" -> quantity = 1
      const quantityMatch = input.match(/(\d+\.?\d*)\s*[个]?[Ss][Uu][Ii]/i)
      let quantity = 1
      if (quantityMatch) {
        quantity = parseFloat(quantityMatch[1])
      }

      // 判断买入还是卖出
      const isBuy = input.includes('买') || input.includes('买入') || (!input.includes('卖') && !input.includes('出售'))

      // 卖出时检查钱包 SUI 余额是否足够
      if (!isBuy && walletBalance < quantity) {
        const errorMsg: Message = {
          role: 'ai',
          content: `余额不足！你钱包只有 ${walletBalance.toFixed(4)} SUI，无法卖出 ${quantity} SUI。`,
          timestamp: Date.now()
        }
        setMessages(prev => [...prev, errorMsg])
        setLoading(false)
        return
      }

      // 生成订单提案
      const orderProposal: OrderProposal = {
        action: isBuy ? 'buy' : 'sell',
        price: targetPrice,
        quantity: typeof quantity === 'number' ? quantity : parseFloat(quantity) || 1,
        reason: isBuy
          ? `当前 SUI 价格 ${currentPrice.toFixed(4)} USDT，你想以 ${targetPrice.toFixed(4)} USDT 买入`
          : `当前 SUI 价格 ${currentPrice.toFixed(4)} USDT，你想以 ${targetPrice.toFixed(4)} USDT 卖出 (钱包余额: ${walletBalance.toFixed(4)} SUI)`,
        totalCost: isBuy ? targetPrice * quantity : undefined,
        estimatedReceive: isBuy ? undefined : targetPrice * quantity
      }

      setProposal(orderProposal)

      let aiContent = `${orderProposal.reason}\n\n`
      aiContent += `📋 **订单确认**\n`
      aiContent += `- 操作: ${isBuy ? '买入' : '卖出'} SUI\n`
      aiContent += `- 价格: ${targetPrice.toFixed(4)} USDC\n`
      aiContent += `- 数量: ${orderProposal.quantity} SUI\n`
      aiContent += `- 钱包余额: ${walletBalance.toFixed(4)} SUI\n`
      if (orderProposal.totalCost) {
        aiContent += `- 预计花费: ${orderProposal.totalCost.toFixed(4)} USDC\n`
      }
      if (orderProposal.estimatedReceive) {
        aiContent += `- 预计获得: ${orderProposal.estimatedReceive.toFixed(4)} USDC\n`
      }
      aiContent += `\n是否执行此操作？`

      const aiMessage: Message = {
        role: 'ai',
        content: aiContent,
        timestamp: Date.now()
      }
      setMessages(prev => [...prev, aiMessage])

    } catch (error) {
      const errorMessage: Message = {
        role: 'ai',
        content: `抱歉，处理你的请求时出现错误：${(error as Error).message}`,
        timestamp: Date.now()
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }, [input, account])

  const handleExecute = useCallback(() => {
    if (!proposal || !account) return

    const existingBmId = localStorage.getItem('balanceManagerId')
    const isNewBM = !existingBmId

    setExecuting(true)

    const tx = new Transaction()
    tx.setGasBudget(50000000)
    tx.setSender(account.address)

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
      // 没有 BM 时，使用 create_deposit_then_place_limit_order 创建并下单
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
      // 有 BM 时，使用 deposit_then_place_limit_order_by_owner
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
              // 如果是新创建的 BM，从事件中提取 ID 并保存
              if (isNewBM && execResult.events) {
                for (const event of execResult.events) {
                  // BalanceManager 创建事件
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
              setTxResult(`✅ 订单已提交！交易哈希: ${execResult.digest}`)
              setProposal(null)
            } else {
              setTxResult(`❌ 订单失败`)
            }
          } catch (e) {
            setTxResult(`❌ 执行失败: ${(e as Error).message}`)
          } finally {
            setExecuting(false)
          }
        },
        onError: () => {
          setTxResult(`❌ 签名被拒绝`)
          setExecuting(false)
        }
      }
    )
  }, [proposal, account, signTransaction, suiClient])

  const handleReject = useCallback(() => {
    setProposal(null)
    setTxResult(null)
    setMessages(prev => [...prev, {
      role: 'ai',
      content: '好的，你可以继续描述你的交易需求。',
      timestamp: Date.now()
    }])
  }, [])

  return (
    <div className="ai-chat-page">
      <div className="chat-container">
        <div className="chat-messages">
          {messages.length === 0 && (
            <div className="chat-empty">
              <p>👋 你好！告诉我你想如何交易</p>
              <p>例如："SUI价格低于1.5U时买入1个SUI"</p>
            </div>
          )}
          {messages.map((msg, i) => (
            <div key={i} className={`message ${msg.role}`}>
              <div className="message-content">{msg.content}</div>
            </div>
          ))}
          {loading && (
            <div className="message ai">
              <div className="message-content">思考中...</div>
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
            <h3>📋 订单确认</h3>
            <div className="proposal-details">
              <p><strong>操作:</strong> {proposal.action === 'buy' ? '买入' : '卖出'}</p>
              <p><strong>价格:</strong> {proposal.price.toFixed(4)} USDC</p>
              <p><strong>数量:</strong> {proposal.quantity} SUI</p>
              {proposal.totalCost && <p><strong>预计花费:</strong> {proposal.totalCost.toFixed(4)} USDC</p>}
              {proposal.estimatedReceive && <p><strong>预计获得:</strong> {proposal.estimatedReceive.toFixed(4)} USDC</p>}
            </div>
            <div className="proposal-actions">
              <button
                className="btn btn-primary"
                onClick={handleExecute}
                disabled={executing}
              >
                {executing ? '执行中...' : '✅ 确认执行'}
              </button>
              <button
                className="btn btn-secondary"
                onClick={handleReject}
                disabled={executing}
              >
                ❌ 拒绝
              </button>
            </div>
          </div>
        )}

        <div className="chat-input">
          <input
            type="text"
            placeholder="描述你的交易需求..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            disabled={!account || loading || executing}
          />
          <button onClick={handleSend} disabled={!account || loading || !input.trim() || executing}>
            发送
          </button>
        </div>
      </div>
    </div>
  )
}

export default AIChatPage
