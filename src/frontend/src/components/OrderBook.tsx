import { useState, useEffect } from 'react'
import { useCurrentAccount } from '@mysten/dapp-kit'
import { useI18n } from '../i18n/I18nProvider'

interface OrderBookEntry {
  price: number
  quantity: number
  total: number
  side: 'bid' | 'ask'
}

interface OrderBookProps {
  onPriceClick?: (price: number) => void
}

// Backend API for cached DeepBook data
// Empty string → relative URL, routed by Vite proxy (dev) or Vercel rewrites (prod)
const API_BASE = ''

function OrderBook({ onPriceClick }: OrderBookProps) {
  const [asks, setAsks] = useState<OrderBookEntry[]>([])
  const [bids, setBids] = useState<OrderBookEntry[]>([])
  const [loading, setLoading] = useState(true)
  const account = useCurrentAccount()
  const { t } = useI18n()

  useEffect(() => {
    const fetchOrderBook = async () => {
      if (!account) {
        setLoading(false)
        return
      }

      try {
        // Use backend cache API
        const response = await fetch(`${API_BASE}/api/v1/cache/orderbook`)
        const result = await response.json()

        if (!result.success || !result.data) {
          setBids([])
          setAsks([])
          setLoading(false)
          return
        }

        const data = result.data
        if (!data.bids || !data.asks) {
          setBids([])
          setAsks([])
          setLoading(false)
          return
        }

        // Parse bids (buy orders) - format: [[price, quantity], ...]
        const parsedBids: OrderBookEntry[] = []
        let bidTotal = 0
        for (const [price, qty] of data.bids.slice(0, 20)) {
          bidTotal += parseFloat(qty)
          parsedBids.push({
            price: parseFloat(price),
            quantity: parseFloat(qty),
            total: bidTotal,
            side: 'bid'
          })
        }

        // Parse asks (sell orders) - format: [[price, quantity], ...]
        const parsedAsks: OrderBookEntry[] = []
        let askTotal = 0
        for (const [price, qty] of data.asks.slice(0, 20)) {
          askTotal += parseFloat(qty)
          parsedAsks.push({
            price: parseFloat(price),
            quantity: parseFloat(qty),
            total: askTotal,
            side: 'ask'
          })
        }

        setBids(parsedBids)
        setAsks(parsedAsks)

      } catch (e) {
        console.error('Failed to fetch orderbook:', e)
      } finally {
        setLoading(false)
      }
    }

    fetchOrderBook()
    const interval = setInterval(fetchOrderBook, 1000) // Update every 1 second
    return () => clearInterval(interval)
  }, [account])

  const maxTotal = Math.max(
    asks.length > 0 ? asks[asks.length - 1].total : 0,
    bids.length > 0 ? bids[bids.length - 1].total : 0
  )

  if (!account) {
    return (
      <div className="orderbook-loading">
        <span>{t('orderbook.connectWallet')}</span>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="orderbook-loading">
        <span>{t('orderbook.loading')}</span>
      </div>
    )
  }

  // If no data, show empty state
  if (asks.length === 0 && bids.length === 0) {
    return (
      <div className="orderbook-loading">
        <span>{t('orderbook.empty')}</span>
      </div>
    )
  }

  return (
    <div className="orderbook">
      {/* Header */}
      <div className="orderbook-header">
        <span>{t('orderbook.col.price')}</span>
        <span>{t('orderbook.col.quantity')}</span>
        <span>{t('orderbook.col.total')}</span>
      </div>

      {/* Asks (Sell orders) - displayed top to bottom, lowest price at bottom */}
      <div className="orderbook-asks">
        {[...asks].reverse().map((ask, i) => (
          <div key={`ask-${i}`} className="orderbook-row ask" onClick={() => onPriceClick?.(ask.price)}>
            <div
              className="orderbook-row-bg ask-bg"
              style={{ width: `${maxTotal > 0 ? (ask.total / maxTotal) * 100 : 0}%` }}
            />
            <span className="price clickable">{ask.price.toFixed(4)}</span>
            <span className="quantity">{ask.quantity.toFixed(4)}</span>
            <span className="total">{ask.total.toFixed(4)}</span>
          </div>
        ))}
      </div>

      {/* Spread */}
      <div className="orderbook-spread">
        <span>{t('orderbook.spread')}</span>
        <span>
          {asks.length > 0 && bids.length > 0
            ? (asks[0].price - bids[0].price).toFixed(4)
            : '--'}
        </span>
      </div>

      {/* Bids (Buy orders) - highest price at top */}
      <div className="orderbook-bids">
        {bids.map((bid, i) => (
          <div key={`bid-${i}`} className="orderbook-row bid" onClick={() => onPriceClick?.(bid.price)}>
            <div
              className="orderbook-row-bg bid-bg"
              style={{ width: `${maxTotal > 0 ? (bid.total / maxTotal) * 100 : 0}%` }}
            />
            <span className="price clickable">{bid.price.toFixed(4)}</span>
            <span className="quantity">{bid.quantity.toFixed(4)}</span>
            <span className="total">{bid.total.toFixed(4)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default OrderBook
