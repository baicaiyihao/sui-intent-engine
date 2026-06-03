import { useState } from 'react'
import './App.css'
import TradingPage from './components/TradingPage'
import AIChatPage from './components/AIChatPage'
import AIStrategyPage from './components/AIStrategyPage'
import { LandingPage } from './components/LandingPage'
import { WalletProvider, useCurrentAccount, useDisconnectWallet, ConnectButton } from '@mysten/dapp-kit'
import { SuiClientProvider } from '@mysten/dapp-kit'
import { useI18n } from './i18n/I18nProvider'

type Tab = 'ai' | 'strategy' | 'trading'
type View = 'landing' | 'app'

function LangToggle() {
  const { locale, setLocale } = useI18n()
  return (
    <div className="lang-toggle" role="group" aria-label="Language">
      <button
        className={`lang-segment ${locale === 'zh' ? 'active' : ''}`}
        onClick={() => setLocale('zh')}
        aria-pressed={locale === 'zh'}
      >
        ZH
      </button>
      <button
        className={`lang-segment ${locale === 'en' ? 'active' : ''}`}
        onClick={() => setLocale('en')}
        aria-pressed={locale === 'en'}
      >
        EN
      </button>
    </div>
  )
}

function AppContent() {
  const [view, setView] = useState<View>('landing')
  const [activeTab, setActiveTab] = useState<Tab>('trading')
  const account = useCurrentAccount()
  const { mutate: disconnect } = useDisconnectWallet()
  const { t } = useI18n()

  const formatAddress = (addr: string) => {
    return `${addr.slice(0, 6)}...${addr.slice(-4)}`
  }

  if (view === 'landing') {
    return <LandingPage onEnterApp={() => setView('app')} />
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <button
            className="header-home-btn"
            onClick={() => setView('landing')}
            type="button"
            aria-label={t('landing.nav.home')}
          >
            <h1>{t('app.title')}</h1>
            <p>{t('app.subtitle')}</p>
          </button>
        </div>
        <div className="header-right">
          <LangToggle />
          {account ? (
            <div className="wallet-info">
              <span className="wallet-address">{formatAddress(account.address)}</span>
              <button className="btn btn-small" onClick={() => disconnect()}>
                {t('app.disconnect')}
              </button>
            </div>
          ) : (
            <ConnectButton />
          )}
        </div>
      </header>

      <nav className="nav-tabs">
        <button
          className={`tab ${activeTab === 'ai' ? 'active' : ''}`}
          onClick={() => setActiveTab('ai')}
        >
          {t('nav.ai')}
        </button>
        <button
          className={`tab ${activeTab === 'strategy' ? 'active' : ''}`}
          onClick={() => setActiveTab('strategy')}
        >
          {t('nav.strategy')}
        </button>
        <button
          className={`tab ${activeTab === 'trading' ? 'active' : ''}`}
          onClick={() => setActiveTab('trading')}
        >
          {t('nav.trading')}
        </button>
      </nav>

      <main className="main">
        {activeTab === 'ai' && <AIChatPage />}
        {activeTab === 'strategy' && <AIStrategyPage />}
        {activeTab === 'trading' && <TradingPage />}
      </main>

      <footer className="footer">
        <p>{t('app.footer')}</p>
      </footer>
    </div>
  )
}

function App() {
  return (
    <SuiClientProvider
      networks={{
        mainnet: { url: 'https://fullnode.mainnet.sui.io:443' },
        testnet: { url: 'https://fullnode.testnet.sui.io:443' },
      }}
      defaultNetwork="mainnet"
    >
      <WalletProvider autoConnect={true}>
        <AppContent />
      </WalletProvider>
    </SuiClientProvider>
  )
}

export default App
