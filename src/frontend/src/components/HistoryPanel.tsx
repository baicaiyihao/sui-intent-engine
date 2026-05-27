import { useState, useEffect } from 'react'
import { useCurrentAccount, useSuiClient } from '@mysten/dapp-kit'

interface HistoryItem {
  id: string
  pair: string
  type: 'buy' | 'sell'
  price: number
  quantity: number
  filled: number
  status: 'open' | 'filled' | 'cancelled'
  timestamp: number
  txDigest: string
  poolId?: string
}

function HistoryPanel() {
  const [history, setHistory] = useState<HistoryItem[]>([])
  const account = useCurrentAccount()
  const suiClient = useSuiClient()

  // 从链上查询订单历史
  const fetchOnChainHistory = async () => {
    if (!account) return

    try {
      const txs = await suiClient.queryTransactionBlocks({
        filter: { FromAddress: account.address },
        options: { showEffects: true, showEvents: true },
        limit: 100,
      })

      const ordersMap = new Map<string, HistoryItem>()

      // 按时间顺序处理
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

          const orderId = String(parsed.order_id || '')
          if (!orderId || orderId === '0' || orderId === 'undefined') continue

          // OrderPlaced 事件 - 创建订单
          if (eventType.includes('OrderPlaced')) {
            if (!ordersMap.has(orderId)) {
              const poolId = parsed.pool_id || ''
              // 从 poolId 判断交易对
              let pair = 'SUI/USDC'
              if (poolId.includes('1c19362') || poolId.includes('e05dafb')) {
                pair = 'SUI/USDC'
              }

              ordersMap.set(orderId, {
                id: orderId,
                pair,
                type: parsed.is_bid ? 'buy' : 'sell',
                price: Number(parsed.price) || 0,
                quantity: Number(parsed.placed_quantity || parsed.original_quantity || 0) / 1e9 || 0,
                filled: Number(parsed.executed_quantity || 0) / 1e9 || 0,
                status: 'open' as const, // 默认挂单
                timestamp: txTime,
                txDigest: tx.digest,
                poolId,
              })
            }
          }

          // OrderInfo - 更新状态 (status: 0=open, 1=filled, 2=cancelled)
          if (eventType.includes('OrderInfo') && parsed.status !== undefined) {
            const order = ordersMap.get(orderId)
            if (order) {
              if (parsed.status === 0) {
                order.status = 'open'
              } else if (parsed.status === 1) {
                order.status = 'filled'
                order.filled = Number(parsed.executed_quantity || 0) / 1e9 || 0
              } else if (parsed.status === 2) {
                order.status = 'cancelled'
              }
            }
          }

          // OrderCanceled 事件
          if (eventType.includes('OrderCanceled') || eventType.includes('OrderCancelled')) {
            const order = ordersMap.get(orderId)
            if (order) {
              order.status = 'cancelled'
            }
          }
        }
      }

      // 显示所有订单（挂单中、已成交、已取消）
      const historyOrders = Array.from(ordersMap.values())
        .sort((a, b) => b.timestamp - a.timestamp)

      setHistory(historyOrders)

    } catch (e) {
      console.error('Failed to fetch history:', e)
    }
  }

  useEffect(() => {
    // 组件挂载时自动查询
    if (account) {
      fetchOnChainHistory()
    }
  }, [account])

  const formatPrice = (price: number) => price >= 1e6 ? (price / 1e6).toFixed(4) : price.toFixed(4)
  const formatTime = (ts: number) => {
    const d = new Date(ts)
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
  }
  const formatTotal = (price: number, filled: number) => {
    const p = price >= 1e6 ? price / 1e6 : price
    return (p * filled).toFixed(4)
  }

  return (
    <div className="orders-panel">
      {history.length === 0 ? (
        <div className="orders-empty">
          <span>暂无订单历史</span>
          <small>所有订单会显示在这里</small>
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
              <th>总额 (USDC)</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            {history.map(item => (
              <tr key={item.id}>
                <td className="time-cell">{formatTime(item.timestamp)}</td>
                <td>
                  <span className={`side-badge ${item.type}`}>
                    {item.type === 'buy' ? '买入' : '卖出'}
                  </span>
                </td>
                <td>{formatPrice(item.price)}</td>
                <td>{item.quantity.toFixed(4)}</td>
                <td>{item.filled.toFixed(4)}</td>
                <td>{formatTotal(item.price, item.filled)}</td>
                <td>
                  <span className={`status-badge ${item.status}`}>
                    {item.status === 'open' ? '挂单' : item.status === 'filled' ? '成交' : '取消'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default HistoryPanel
