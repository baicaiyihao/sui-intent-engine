import { useState, useEffect, useCallback } from 'react'
import { useCurrentAccount, useSignTransaction, useSuiClient } from '@mysten/dapp-kit'
import { Transaction } from '@mysten/sui/transactions'

const UTILS_PKG = '0x600138d3179e2fc746f6774f360a6e1fa68e90d66d082af66399adabe46f22a4'
const GLOBAL_CONFIG = '0xff1141ef80e7baf206c7930c274b465600e64884d8167f90d4cdb60197925163'
const SUI_USDC_POOL = '0xe05dafb5133bcffb8d59f4e12465dc0e9faeaa05e3e342a08fe135800e3e4407'
const USDC_COIN = '0xdba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC'
const SUI_COIN = '0x2::sui::SUI'

interface Order {
  id: string
  side: 'buy' | 'sell'
  price: number
  quantity: number
  filled: number
  status: 'open' | 'partial' | 'filled' | 'cancelled'
  timestamp: number
  client_order_id?: number
}

function OrdersPanel() {
  const [orders, setOrders] = useState<Order[]>([])
  const [cancelingId, setCancelingId] = useState<string | null>(null)
  const account = useCurrentAccount()
  const { mutate: signTransaction } = useSignTransaction()
  const suiClient = useSuiClient()

  const bmId = localStorage.getItem('balanceManagerId') || ''

  // 从区块链查询订单 - DeepBook 合约事件
  const fetchOrdersFromChain = useCallback(async () => {
    if (!account) return

    try {
      console.log('Querying transactions for:', account.address)

      const txs = await suiClient.queryTransactionBlocks({
        filter: { FromAddress: account.address },
        options: { showEffects: true, showEvents: true },
        limit: 100,
      })

      console.log('Transactions found:', txs.data?.length || 0)

      // 用 Map 存储订单，key 是 order_id (string)
      const ordersMap = new Map<string, {
        id: string
        client_order_id?: number
        side: 'buy' | 'sell'
        price: number
        quantity: number
        filled: number
        status: 'open' | 'filled' | 'cancelled'
        timestamp: number
        txDigest: string
        balance_manager_id?: string
      }>()

      // 按时间顺序处理所有交易（从旧到新）
      const sortedTxs = [...(txs.data || [])].sort(
        (a, b) => Number(a.timestampMs || 0) - Number(b.timestampMs || 0)
      )

      for (const tx of sortedTxs) {
        const txTime = Number(tx.timestampMs) || Date.now()
        const events = tx.events || []

        for (const event of events) {
          const eventType = event.type || ''
          if (!eventType) continue

          const parsed = event.parsedJson as any
          if (!parsed) continue

          // 提取 order_id - 可能是 string 或 number
          const orderId = String(parsed.order_id || '')

          // 跳过无效 order_id
          if (!orderId || orderId === '0' || orderId === 'undefined') continue

          // 1. OrderPlaced 事件 - 创建新订单
          if (eventType.includes('OrderPlaced')) {
            // 只有不存在的订单才创建
            if (!ordersMap.has(orderId)) {
              ordersMap.set(orderId, {
                id: orderId,
                client_order_id: parsed.client_order_id,
                side: parsed.is_bid ? 'buy' : 'sell',
                price: Number(parsed.price) || 0,
                quantity: Number(parsed.placed_quantity || parsed.original_quantity || 0) / 1e9 || 0,
                filled: Number(parsed.executed_quantity || 0) / 1e9 || 0,
                status: 'open', // 默认挂单
                timestamp: txTime,
                txDigest: tx.digest,
                balance_manager_id: parsed.balance_manager_id,
              })
              console.log('OrderPlaced:', orderId.slice(-20), 'price:', parsed.price)
            }
          }

          // OrderInfo 事件 - 这是最终状态
          if (eventType.includes('OrderInfo')) {
            const order = ordersMap.get(orderId)
            if (order) {
              // status: 0=open, 1=filled, 2=cancelled
              if (parsed.status === 1) {
                order.status = 'filled'
                order.filled = Number(parsed.executed_quantity || 0) / 1e9 || 0
              } else if (parsed.status === 2) {
                order.status = 'cancelled'
              } else {
                order.status = 'open'
              }
              console.log('OrderInfo:', orderId.slice(-20), '-> status:', order.status)
            }
          }

          // OrderCanceled 事件 - 明确取消
          if (eventType.includes('OrderCanceled')) {
            const order = ordersMap.get(orderId)
            if (order) {
              order.status = 'cancelled'
              console.log('OrderCanceled:', orderId.slice(-20))
            }
          }
        }
      }

      // 分离挂单和历史
      const openOrders: Order[] = []
      const orderHistory: Order[] = []

      for (const order of ordersMap.values()) {
        if (order.status === 'open') {
          openOrders.push(order as Order)
        } else {
          orderHistory.push(order as Order)
        }
      }

      // 按时间倒序
      openOrders.sort((a, b) => b.timestamp - a.timestamp)
      orderHistory.sort((a, b) => b.timestamp - a.timestamp)

      console.log('=== RESULT ===')
      console.log('Open orders:', openOrders.length)
      openOrders.forEach(o => console.log('  OPEN:', o.id.slice(-20), 'price:', o.price, 'qty:', o.quantity))
      console.log('History:', orderHistory.length)
      orderHistory.forEach(o => console.log('  HIST:', o.id.slice(-20), 'status:', o.status, 'price:', o.price))

      setOrders(openOrders)
      localStorage.setItem('openOrders', JSON.stringify(openOrders))

    } catch (e) {
      console.error('Failed to fetch orders:', e)
    }
  }, [account, suiClient])

  useEffect(() => {
    // 先从 localStorage 加载
    const storedOrders = localStorage.getItem('openOrders')
    if (storedOrders) {
      try { setOrders(JSON.parse(storedOrders)) } catch (e) { console.error('Failed to parse stored orders:', e) }
    }

    // 然后从链上刷新
    if (account) {
      fetchOrdersFromChain()
    }
  }, [account, fetchOrdersFromChain])

  const handleCancelOrder = useCallback((order: Order) => {
    if (!account) return

    const orderId = order.id || order.client_order_id?.toString()
    if (!orderId) {
      alert('无效的订单ID')
      return
    }

    // 优先使用订单事件中的 balance_manager_id，否则用 localStorage 的
    const cancelBmId = (order as any).balance_manager_id || bmId
    if (!cancelBmId) {
      alert('未找到 BalanceManager ID，请先下一笔订单创建 BM')
      return
    }

    setCancelingId(order.id)

    const tx = new Transaction()
    tx.setGasBudget(10000000)
    tx.setSender(account.address)

    tx.moveCall({
      target: `${UTILS_PKG}::deepbookv3_utils::cancel_order`,
      arguments: [
        tx.object(GLOBAL_CONFIG),
        tx.object(cancelBmId),
        tx.object(SUI_USDC_POOL),
        tx.pure.u128(orderId),
        tx.object.clock(),
      ],
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
              options: { showEffects: true, showEvents: true }
            })
            if (execResult.effects?.status?.status === 'success') {
              // 更新本地状态
              setOrders(prev => {
                const updated = prev.map(o =>
                  o.id === order.id ? { ...o, status: 'cancelled' as const } : o
                )
                localStorage.setItem('openOrders', JSON.stringify(updated))
                return updated
              })
            }
          } catch (e) {
            console.error('Cancel failed:', e)
            alert('取消失败')
          } finally {
            setCancelingId(null)
          }
        },
        onError: () => {
          setCancelingId(null)
        }
      }
    )
  }, [account, signTransaction, suiClient, bmId])

  const formatPrice = (price: number) => (price / 1e6).toFixed(4)
  const formatTime = (ts: number) => {
    const d = new Date(ts)
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
  }

  return (
    <div className="orders-panel">
      {orders.length === 0 ? (
        <div className="orders-empty">
          <span>暂无挂单</span>
          <small>在 AI 策略页面下单</small>
        </div>
      ) : (
        <table className="detail-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>类型</th>
              <th>价格 (USDC)</th>
              <th>数量 (SUI)</th>
              <th>已成交</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {orders.map(order => (
              <tr key={order.id}>
                <td className="time-cell">{formatTime(order.timestamp)}</td>
                <td>
                  <span className={`side-badge ${order.side}`}>
                    {order.side === 'buy' ? '买入' : '卖出'}
                  </span>
                </td>
                <td>{formatPrice(order.price)}</td>
                <td>{order.quantity.toFixed(4)}</td>
                <td>{order.filled.toFixed(4)}</td>
                <td>
                  <span className="status-text">挂单中</span>
                </td>
                <td>
                  <button
                    className="btn-cancel"
                    onClick={() => handleCancelOrder(order)}
                    disabled={cancelingId === order.id || order.status !== 'open'}
                  >
                    {cancelingId === order.id ? '取消中...' : '取消'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default OrdersPanel
