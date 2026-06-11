import { useEffect, useRef, useState } from 'react'
import { useI18n } from '../i18n/I18nProvider'
import './LandingPage.css'

const DEEPBOOK_API = 'https://sui-intent.duckdns.org'

interface TickerData {
  last_price: number
  price_change_percent: number
  high: number
  low: number
  volume: number
  bid: number
  ask: number
}

type FeedStatus = 'connecting' | 'live' | 'offline'

function formatPrice(p: number | undefined): string {
  if (p === undefined || Number.isNaN(p)) return '— — — —'
  return p.toFixed(4)
}

function formatVolume(v: number | undefined): string {
  if (v === undefined || Number.isNaN(v)) return '— —'
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`
  if (v >= 1_000) return `${(v / 1_000).toFixed(2)}K`
  return v.toFixed(2)
}

function formatPct(p: number | undefined): string {
  if (p === undefined || Number.isNaN(p)) return '— —'
  const sign = (p ?? 0) >= 0 ? '+' : ''
  return `${sign}${p.toFixed(2)}%`
}

export function LandingPage({ onEnterApp }: { onEnterApp: () => void }) {
  const { t } = useI18n()
  const [ticker, setTicker] = useState<TickerData | null>(null)
  const [feed, setFeed] = useState<FeedStatus>('connecting')
  const [priceFlash, setPriceFlash] = useState<'up' | 'down' | null>(null)
  const lastPriceRef = useRef<number | null>(null)
  const flashTimerRef = useRef<number | null>(null)

  // Poll ticker from cached backend (sui_intent_server on :8001)
  useEffect(() => {
    let cancelled = false
    const fetchTicker = async () => {
      try {
        const res = await fetch(`${DEEPBOOK_API}/api/v1/cache/ticker`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const json = await res.json()
        if (cancelled) return
        if (json?.success && json.data) {
          const next = json.data as TickerData
          const prev = lastPriceRef.current
          if (prev !== null && next.last_price !== prev) {
            setPriceFlash(next.last_price > prev ? 'up' : 'down')
            if (flashTimerRef.current) window.clearTimeout(flashTimerRef.current)
            flashTimerRef.current = window.setTimeout(() => setPriceFlash(null), 600)
          }
          lastPriceRef.current = next.last_price
          setTicker(next)
          setFeed('live')
        }
      } catch {
        if (!cancelled) setFeed('offline')
      }
    }
    fetchTicker()
    const id = window.setInterval(fetchTicker, 3000)
    return () => {
      cancelled = true
      window.clearInterval(id)
      if (flashTimerRef.current) window.clearTimeout(flashTimerRef.current)
    }
  }, [])

  const lastPrice = ticker?.last_price
  const change = ticker?.price_change_percent
  const isUp = (change ?? 0) >= 0
  const bid = ticker?.bid
  const ask = ticker?.ask
  const spread = bid !== undefined && ask !== undefined ? ask - bid : undefined

  return (
    <div className="landing">
      <div className="landing-grain" aria-hidden="true" />

      {/* Status bar — track badge front and center */}
      <div className="landing-statusbar">
        <span className="landing-tag">{t('landing.tag')}</span>
        <span className="landing-track-badge">{t('landing.track.badge')}</span>
        <span className={`landing-feed landing-feed--${feed}`}>
          <span className="landing-feed-dot" />
          {feed === 'live' ? t('landing.badge.live') : feed === 'connecting' ? t('landing.ticker.connecting') : t('landing.ticker.offline')}
        </span>
        <span className="landing-netbadge">{t('landing.badge.mainnet')}</span>
      </div>
      <div className="landing-track-tagline">{t('landing.track.tagline')}</div>

      {/* Hero: 3-line statement + live ticker */}
      <section className="landing-hero">
        <div className="landing-hero-left">
          <h1 className="landing-headline">
            <span className="landing-headline-1">{t('landing.hero.line1')}</span>
            <span className="landing-headline-2"><em>{t('landing.hero.line2')}</em></span>
            <span className="landing-headline-3">{t('landing.hero.line3')}</span>
          </h1>
          <p className="landing-subtitle">{t('landing.hero.subtitle')}</p>
        </div>

        <aside className="landing-ticker" aria-label="SUI USDC live ticker">
          <div className="landing-ticker-head">
            <span className="landing-ticker-pair">{t('landing.ticker.pair')}</span>
            <span className="landing-ticker-meta">DEEPBOOK V3 · CLOB</span>
          </div>

          <div className={`landing-ticker-price ${priceFlash ? `flash-${priceFlash}` : ''}`}>
            <span className="landing-ticker-price-value">{formatPrice(lastPrice)}</span>
            <span className="landing-ticker-price-unit">USDC</span>
          </div>

          <div className={`landing-ticker-change ${isUp ? 'is-up' : 'is-down'}`}>
            <span className="landing-ticker-arrow">{isUp ? '▲' : '▼'}</span>
            <span>{formatPct(change)}</span>
            <span className="landing-ticker-change-label">{t('landing.ticker.change24h')}</span>
          </div>

          <div className="landing-ticker-grid">
            <div className="landing-ticker-cell">
              <span className="landing-ticker-cell-label">{t('landing.ticker.bid')}</span>
              <span className="landing-ticker-cell-value bid">{formatPrice(bid)}</span>
            </div>
            <div className="landing-ticker-cell">
              <span className="landing-ticker-cell-label">{t('landing.ticker.ask')}</span>
              <span className="landing-ticker-cell-value ask">{formatPrice(ask)}</span>
            </div>
            <div className="landing-ticker-cell">
              <span className="landing-ticker-cell-label">{t('landing.ticker.spread')}</span>
              <span className="landing-ticker-cell-value">{formatPrice(spread)}</span>
            </div>
            <div className="landing-ticker-cell">
              <span className="landing-ticker-cell-label">{t('landing.ticker.vol24h')}</span>
              <span className="landing-ticker-cell-value">{formatVolume(ticker?.volume)}</span>
            </div>
          </div>

          <div className="landing-ticker-foot">
            <span className="landing-ticker-foot-dot" />
            <span>{feed === 'live' ? 'STREAMING' : feed === 'connecting' ? 'CONNECTING' : 'OFFLINE'}</span>
          </div>
        </aside>
      </section>

      {/* Intent Flow: 4 steps, the core of Sub-track 3 positioning */}
      <section className="landing-flow">
        <div className="landing-flow-header">
          <h2 className="landing-flow-title">{t('landing.flow.title')}</h2>
          <p className="landing-flow-subtitle">{t('landing.flow.subtitle')}</p>
        </div>
        <div className="landing-flow-grid">
          <FlowStep
            idx={t('landing.flow.parse.idx')}
            title={t('landing.flow.parse.title')}
            desc={t('landing.flow.parse.desc')}
            kind="parse"
          />
          <FlowStep
            idx={t('landing.flow.guard.idx')}
            title={t('landing.flow.guard.title')}
            desc={t('landing.flow.guard.desc')}
            kind="guard"
            highlight
          />
          <FlowStep
            idx={t('landing.flow.preview.idx')}
            title={t('landing.flow.preview.title')}
            desc={t('landing.flow.preview.desc')}
            kind="preview"
          />
          <FlowStep
            idx={t('landing.flow.sign.idx')}
            title={t('landing.flow.sign.title')}
            desc={t('landing.flow.sign.desc')}
            kind="sign"
          />
        </div>
      </section>

      {/* CTA */}
      <section className="landing-cta-wrap">
        <button className="landing-cta" onClick={onEnterApp} type="button">
          <span className="landing-cta-bracket landing-cta-bracket--tl">╔</span>
          <span className="landing-cta-bracket landing-cta-bracket--tr">╗</span>
          <span className="landing-cta-bracket landing-cta-bracket--bl">╚</span>
          <span className="landing-cta-bracket landing-cta-bracket--br">╝</span>
          <span className="landing-cta-label">{t('landing.cta.enter')}</span>
        </button>
        <div className="landing-cta-subline">{t('landing.cta.subline')}</div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <span>{t('landing.footer.status')}</span>
      </footer>
    </div>
  )
}

function FlowStep({
  idx,
  title,
  desc,
  kind,
  highlight,
}: {
  idx: string
  title: string
  desc: string
  kind: 'parse' | 'guard' | 'preview' | 'sign'
  highlight?: boolean
}) {
  return (
    <article className={`flow-step flow-step--${kind} ${highlight ? 'flow-step--highlight' : ''}`}>
      <div className="flow-step-head">
        <span className="flow-step-idx">{idx}</span>
        <span className="flow-step-arrow">→</span>
      </div>
      <h3 className="flow-step-title">{title}</h3>
      <p className="flow-step-desc">{desc}</p>
    </article>
  )
}
