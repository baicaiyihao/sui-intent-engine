import { useState, useEffect, useRef, useCallback } from 'react'
import { useCurrentAccount } from '@mysten/dapp-kit'
import { createChart, IChartApi, ISeriesApi, CandlestickData, Time, ColorType, CandlestickSeries, HistogramSeries } from 'lightweight-charts'

interface KLine {
  time: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

interface TickerData {
  lastPrice: number
  priceChangePercent: number
  high: number
  low: number
  volume: number
  bid: number
  ask: number
}

// Backend API for cached DeepBook data
const API_BASE = 'http://localhost:8001'

const TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d'] as const
type Timeframe = typeof TIMEFRAMES[number]

// Map timeframe to indexer interval format
const INTERVAL_MAP: Record<Timeframe, string> = {
  '1m': '1m',
  '5m': '5m',
  '15m': '15m',
  '1h': '1h',
  '4h': '4h',
  '1d': '1d'
}

function MarketChart() {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)

  const [klines, setKlines] = useState<KLine[]>([])
  const [ticker, setTicker] = useState<TickerData | null>(null)
  const [loading, setLoading] = useState(true)
  const [timeframe, setTimeframe] = useState<Timeframe>('1h')

  const account = useCurrentAccount()

  // Fetch K-line data from backend cache
  const fetchKlines = useCallback(async () => {
    try {
      const response = await fetch(
        `${API_BASE}/api/v1/cache/klines?interval=${INTERVAL_MAP[timeframe]}&limit=100`
      )
      const result = await response.json()

      if (result.success && result.data) {
        setKlines(result.data)
        setLoading(false)
      } else {
        console.error('Failed to fetch klines:', result.error)
        setLoading(false)
      }
    } catch (e) {
      console.error('Failed to fetch klines:', e)
      setLoading(false)
    }
  }, [timeframe])

  // Fetch ticker data from backend cache
  const fetchTicker = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/cache/ticker`)
      const result = await response.json()

      if (result.success && result.data) {
        const t = result.data
        setTicker({
          lastPrice: t.last_price,
          priceChangePercent: t.price_change_percent,
          high: t.high,
          low: t.low,
          volume: t.volume,
          bid: t.bid,
          ask: t.ask
        })
      }
    } catch (e) {
      console.error('Failed to fetch ticker:', e)
    }
  }, [])

  // Poll for updates
  useEffect(() => {
    if (!account) return

    fetchKlines()
    fetchTicker()
    const interval = setInterval(() => {
      fetchKlines()
      fetchTicker()
    }, 1000) // Poll every 1 second (same as OrderBook)

    return () => clearInterval(interval)
  }, [account, fetchKlines, fetchTicker])

  // Initialize chart
  useEffect(() => {
    if (!containerRef.current || !account) return

    const container = containerRef.current
    const chart = createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight,
      layout: {
        background: { type: ColorType.Solid, color: '#131722' },
        textColor: '#9ca3af',
        fontFamily: 'Inter, sans-serif',
      },
      grid: {
        vertLines: { color: '#1e1f26' },
        horzLines: { color: '#1e1f26' },
      },
      crosshair: {
        mode: 1,
        vertLine: { color: '#6366f1', width: 1, style: 2 },
        horzLine: { color: '#6366f1', width: 1, style: 2 },
      },
      rightPriceScale: {
        borderColor: '#2a2a3a',
        scaleMargins: { top: 0.1, bottom: 0.2 },
      },
      timeScale: {
        borderColor: '#2a2a3a',
        timeVisible: true,
        secondsVisible: false,
      },
      handleScale: { axisPressedMouseMove: true },
      handleScroll: { vertTouchDrag: false },
    })

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#00d4aa',
      downColor: '#ff4757',
      borderUpColor: '#00d4aa',
      borderDownColor: '#ff4757',
      wickUpColor: '#00d4aa',
      wickDownColor: '#ff4757',
      priceFormat: { type: 'price', precision: 4, minMove: 0.0001 },
    })

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    })

    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.85, bottom: 0 },
    })

    chartRef.current = chart
    candleSeriesRef.current = candleSeries as ISeriesApi<'Candlestick'>
    volumeSeriesRef.current = volumeSeries as ISeriesApi<'Histogram'>

    // Handle resize
    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        })
      }
    }

    const resizeObserver = new ResizeObserver(handleResize)
    resizeObserver.observe(containerRef.current)

    return () => {
      resizeObserver.disconnect()
      chart.remove()
      chartRef.current = null
      candleSeriesRef.current = null
      volumeSeriesRef.current = null
    }
  }, [account])

  // Update chart when klines change
  useEffect(() => {
    if (!candleSeriesRef.current || !volumeSeriesRef.current) return

    if (klines.length > 0) {
      // Filter out invalid candles with null/zero values
      const validCandles = klines.filter(k =>
        k.time > 0 &&
        k.open != null && k.open > 0 &&
        k.high != null && k.high > 0 &&
        k.low != null && k.low > 0 &&
        k.close != null && k.close > 0 &&
        k.volume != null && k.volume > 0
      )

      const candleData: CandlestickData[] = validCandles.map(k => ({
        time: k.time as Time,
        open: k.open,
        high: k.high,
        low: k.low,
        close: k.close,
      }))

      const volumeData = validCandles.map(k => ({
        time: k.time as Time,
        value: k.volume,
        color: k.close >= k.open ? 'rgba(0, 212, 170, 0.5)' : 'rgba(255, 71, 87, 0.5)',
      }))

      candleSeriesRef.current.setData(candleData)
      volumeSeriesRef.current.setData(volumeData)
    }
  }, [klines])

  // Update latest candle with real-time price from ticker
  useEffect(() => {
    if (!candleSeriesRef.current || !ticker || klines.length === 0) return

    const latestCandle = klines[klines.length - 1]
    if (!latestCandle) return

    const realtimePrice = ticker.lastPrice

    // Update the latest candle with real-time price using update
    candleSeriesRef.current.update({
      time: latestCandle.time as Time,
      open: latestCandle.open,
      high: Math.max(latestCandle.high, realtimePrice),
      low: Math.min(latestCandle.low, realtimePrice),
      close: realtimePrice,
    })
  }, [ticker, klines])

  const fmt = (n: number | undefined | null, d = 4) => n != null && !isNaN(n) ? n.toFixed(d) : '--'
  const fmtVol = (n: number | undefined | null) => n != null && !isNaN(n) ? (n >= 1e6 ? `${(n / 1e6).toFixed(2)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(2)}K` : n.toFixed(2)) : '--'

  if (!account) {
    return (
      <div className="market-chart">
        <div className="chart-loading">
          <span>请先连接钱包</span>
        </div>
      </div>
    )
  }

  return (
    <div className="market-chart">
      {/* Price Header */}
      <div className="chart-header">
        <div className="price-info">
          <span className="current-price">{ticker ? fmt(ticker.lastPrice) : '--'}</span>
          <span className={`price-change ${ticker && ticker.priceChangePercent >= 0 ? 'positive' : 'negative'}`}>
            {ticker ? (ticker.priceChangePercent >= 0 ? '+' : '') + (ticker.priceChangePercent?.toFixed(2) || '--') : '--'}%
          </span>
        </div>
        <div className="price-stats">
          <div className="price-stat">
            <span className="stat-label">High</span>
            <span className="stat-value high">{ticker ? fmt(ticker.high) : '--'}</span>
          </div>
          <div className="price-stat">
            <span className="stat-label">Low</span>
            <span className="stat-value low">{ticker ? fmt(ticker.low) : '--'}</span>
          </div>
          <div className="price-stat">
            <span className="stat-label">Vol</span>
            <span className="stat-value">{ticker ? fmtVol(ticker.volume) : '--'}</span>
          </div>
          <div className="price-stat">
            <span className="stat-label">Bid</span>
            <span className="stat-value high">{ticker ? fmt(ticker.bid) : '--'}</span>
          </div>
          <div className="price-stat">
            <span className="stat-label">Ask</span>
            <span className="stat-value low">{ticker ? fmt(ticker.ask) : '--'}</span>
          </div>
        </div>
      </div>

      {/* Timeframe Selector */}
      <div className="timeframe-selector">
        {TIMEFRAMES.map(tf => (
          <button
            key={tf}
            className={`timeframe-btn ${timeframe === tf ? 'active' : ''}`}
            onClick={() => setTimeframe(tf)}
          >
            {tf}
          </button>
        ))}
        {klines.length === 0 && (
          <span className="chart-note">加载中...</span>
        )}
      </div>

      {/* Chart Area */}
      <div className="chart-area" ref={containerRef}>
        {loading && (
          <div className="chart-loading">
            <span>加载K线数据...</span>
          </div>
        )}
      </div>
    </div>
  )
}

export default MarketChart
