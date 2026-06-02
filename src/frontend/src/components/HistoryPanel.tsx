import { useState, useEffect } from 'react'
import { useCurrentAccount, useSuiClient } from '@mysten/dapp-kit'
import { useI18n } from '../i18n/I18nProvider'

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
  const { t } = useI18n()

  // Query order history from chain
  const fetchOnChainHistory = async () => {
    if (!account) return

    try {
      const txs = await suiClient.queryTransactionBlocks({
        filter: { FromAddress: account.address },
        options: { showEffects: true, showEvents: true },
        limit: 100,
      })

      const ordersMap = new Map<string, HistoryItem>()

      // Process in chronological order
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

          // OrderPlaced event - create order
          if (eventType.includes('OrderPlaced')) {
            if (!ordersMap.has(orderId)) {
              const poolId = parsed.pool_id || ''
              // Determine trading pair from poolId
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
                status: 'open' as const, // Default: open order
                timestamp: txTime,
                txDigest: tx.digest,
                poolId,
              })
            }
          }

          // OrderInfo - update status (status: 0=open, 1=filled, 2=cancelled)
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

          // OrderCanceled event
          if (eventType.includes('OrderCanceled') || eventType.includes('OrderCancelled')) {
            const order = ordersMap.get(orderId)
            if (order) {
              order.status = 'cancelled'
            }
          }
        }
      }

      // Show all orders (open, filled, cancelled)
      const historyOrders = Array.from(ordersMap.values())
        .sort((a, b) => b.timestamp - a.timestamp)

      setHistory(historyOrders)

    } catch (e) {
      console.error('Failed to fetch history:', e)
    }
  }

  useEffect(() => {
    // Auto-query on component mount
    if (account) {
      fetchOnChainHistory()
    }
  }, [account])

  // USDC precision is 6 decimals
  const formatPrice = (price: number) => (price / 1e6).toFixed(4)
  const formatTime = (ts: number) => {
    const d = new Date(ts)
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
  }
  const formatTotal = (price: number, filled: number) => {
    const p = price / 1e6
    return (p * filled).toFixed(4)
  }

  return (
    <div className="orders-panel">
      {history.length === 0 ? (
        <div className="orders-empty">
          <span>{t('history.empty')}</span>
        </div>
      ) : (
        <table className="detail-table">
          <thead>
            <tr>
              <th>{t('history.col.time')}</th>
              <th>{t('history.col.type')}</th>
              <th>{t('history.col.price')}</th>
              <th>{t('history.col.amount')}</th>
              <th>{t('history.col.filled')}</th>
              <th>{t('history.col.total')}</th>
              <th>{t('history.col.status')}</th>
            </tr>
          </thead>
          <tbody>
            {history.map(item => (
              <tr key={item.id}>
                <td className="time-cell">{formatTime(item.timestamp)}</td>
                <td>
                  <span className={`side-badge ${item.type}`}>
                    {item.type === 'buy' ? t('history.side.buy') : t('history.side.sell')}
                  </span>
                </td>
                <td>{formatPrice(item.price)}</td>
                <td>{item.quantity.toFixed(4)}</td>
                <td>{item.filled.toFixed(4)}</td>
                <td>{formatTotal(item.price, item.filled)}</td>
                <td>
                  <span className={`status-badge ${item.status}`}>
                    {item.status === 'open' ? t('history.status.open') : item.status === 'filled' ? t('history.status.filled') : t('history.status.cancelled')}
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
