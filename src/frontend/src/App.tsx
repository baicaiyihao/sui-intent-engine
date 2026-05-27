import { useState } from 'react'
import './App.css'
import TradingPage from './components/TradingPage'
import AIChatPage from './components/AIChatPage'
import { WalletProvider, useCurrentAccount, useDisconnectWallet, ConnectButton } from '@mysten/dapp-kit'
import { SuiClientProvider } from '@mysten/dapp-kit'

type Tab = 'ai' | 'trading'

function AppContent() {
  const [activeTab, setActiveTab] = useState<Tab>('trading')
  const account = useCurrentAccount()
  const { mutate: disconnect } = useDisconnectWallet()

  const formatAddress = (addr: string) => {
    return `${addr.slice(0, 6)}...${addr.slice(-4)}`
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <h1>SUI Intent Engine</h1>
          <p>DeepBook V3</p>
        </div>
        <div className="header-right">
          {account ? (
            <div className="wallet-info">
              <span className="wallet-address">{formatAddress(account.address)}</span>
              <button className="btn btn-small" onClick={() => disconnect()}>
                断开
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
          AI 策略
        </button>
        <button
          className={`tab ${activeTab === 'trading' ? 'active' : ''}`}
          onClick={() => setActiveTab('trading')}
        >
          交易
        </button>
      </nav>

      <main className="main">
        {activeTab === 'ai' && <AIChatPage />}
        {activeTab === 'trading' && <TradingPage />}
      </main>

      <footer className="footer">
        <p>SUI Intent Engine | Powered by DeepBook V3</p>
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
