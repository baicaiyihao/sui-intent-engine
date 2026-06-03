import { useState, useCallback, useMemo, useEffect } from 'react'
import { useCurrentAccount, useSignTransaction, useSuiClient } from '@mysten/dapp-kit'
import { Transaction } from '@mysten/sui/transactions'
import { useI18n } from '../i18n/I18nProvider'

const UTILS_PKG = '0x600138d3179e2fc746f6774f360a6e1fa68e90d66d082af66399adabe46f22a4'
const GLOBAL_CONFIG = '0xff1141ef80e7baf206c7930c274b465600e64884d8167f90d4cdb60197925163'
const CETUS_BM_INDEXER = '0x5c1a039f97ed1cbd84d54b5d633bdffd681086acc38961b1d366c4ecf680d150'
const SUI_USDC_POOL = '0xe05dafb5133bcffb8d59f4e12465dc0e9faeaa05e3e342a08fe135800e3e4407'
const USDC_COIN = '0xdba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC'
const SUI_COIN = '0x2::sui::SUI'
const DEEP_COIN = '0xdeeb7a4662eec9f2f3def03fb937a663dddaa2e215b8078a284d026b7946c270::deep::DEEP'

// 1 year in nanoseconds = 365 days * 24 hours * 60 min * 60 sec * 1e9
const ONE_YEAR_NANOS = BigInt(365 * 24 * 60 * 60) * BigInt(1e9)

interface DepositPanelProps {
  onDepositSuccess?: () => void
  selectedPrice?: number | null
  marketPrice?: number | null
  onPriceUsed?: () => void
}

type OrderType = 'limit' | 'market'
type FeeToken = 'SUI' | 'DEEP'

// DeepBook fee rates
const MAKER_FEE_RATE = 0.0001 // 0.01% maker fee
const TAKER_FEE_RATE = 0.001 // 0.1% taker fee

function DepositPanel({ onDepositSuccess, selectedPrice, marketPrice, onPriceUsed }: DepositPanelProps) {
  const [orderType, setOrderType] = useState<OrderType>('limit')
  const [amount, setAmount] = useState('')
  const [price, setPrice] = useState('')
  const [isBid, setIsBid] = useState(true) // true = buy, false = sell
  const [feeToken, setFeeToken] = useState<FeeToken>('SUI')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [walletCoins, setWalletCoins] = useState<{sui: string[], usdc: { id: string, balance: string }[]}>({ sui: [], usdc: [] })
  const account = useCurrentAccount()
  const { mutate: signTransaction } = useSignTransaction()
  const suiClient = useSuiClient()
  const { t } = useI18n()

  const bmId = localStorage.getItem('balanceManagerId') || ''

  // Fetch wallet coins for BUY orders
  useEffect(() => {
    if (!account?.address) return

    const fetchCoins = async () => {
      try {
        // Fetch SUI coins
        const suiResp = await fetch('https://fullnode.mainnet.sui.io:443', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            jsonrpc: '2.0',
            id: 1,
            method: 'suix_getCoins',
            params: [account.address]
          })
        })
        const suiData = await suiResp.json()
        const suiCoins = suiData.result?.data
          ?.filter((c: any) => c.coinType === '0x2::sui::SUI')
          ?.map((c: any) => c.coinObjectId) || []

        // Fetch USDC coins
        const usdcResp = await fetch('https://fullnode.mainnet.sui.io:443', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            jsonrpc: '2.0',
            id: 1,
            method: 'suix_getCoins',
            params: [account.address, USDC_COIN]
          })
        })
        const usdcData = await usdcResp.json()
        const usdcCoins = usdcData.result?.data
          ?.map((c: any) => ({ id: c.coinObjectId, balance: c.balance })) || []

        setWalletCoins({ sui: suiCoins, usdc: usdcCoins })
      } catch (e) {
        console.error('Failed to fetch coins:', e)
      }
    }

    fetchCoins()
  }, [account?.address, result]) // Refresh after successful order

  // Handle price selection from order book
  useEffect(() => {
    if (selectedPrice != null) {
      setPrice(selectedPrice.toFixed(4))
      setOrderType('limit')
      onPriceUsed?.()
    }
  }, [selectedPrice, onPriceUsed])

  // Calculate order value and fees
  const orderValue = useMemo(() => {
    const qty = parseFloat(amount) || 0
    const px = parseFloat(price) || 0
    return qty * px
  }, [amount, price])

  const feeRate = orderType === 'limit' ? MAKER_FEE_RATE : TAKER_FEE_RATE
  const fee = useMemo(() => {
    if (orderType === 'market') {
      return (parseFloat(amount) || 0) * feeRate
    }
    return orderValue * feeRate
  }, [amount, price, orderType, orderValue, feeRate])

  const handleSliderChange = (percent: number) => {
    // Calculate based on available balance
    // For simplicity, use a max of 10 SUI
    const maxAmount = 10
    setAmount((maxAmount * percent / 100).toFixed(2))
  }

  const handlePlaceOrder = useCallback(() => {
    if (!account || !amount) return

    const quantity = parseFloat(amount)
    const priceInUSDC = parseFloat(price) || 0

    if (isNaN(quantity) || quantity <= 0) {
      setError(t('deposit.err.invalidAmount'))
      return
    }

    if (orderType === 'limit' && (isNaN(priceInUSDC) || priceInUSDC <= 0)) {
      setError(t('deposit.err.invalidPrice'))
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)

    const tx = new Transaction()
    tx.setGasBudget(100000000)
    tx.setSender(account.address)

    const quantityMIST = BigInt(Math.floor(quantity * 1e9))
    const priceU64 = BigInt(Math.floor(priceInUSDC * 1e6))

    if (!isBid) {
      // SELL: Split gas coin for SUI
      const splitAmount = quantityMIST + BigInt(0.02 * 1e9) // quantity + gas
      const [suiCoin] = tx.splitCoins(tx.gas, [splitAmount])

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

      if (orderType === 'limit') {
        // Limit sell
        const expireTime = (BigInt(Date.now()) * BigInt(1e6)) + ONE_YEAR_NANOS
        tx.moveCall({
          target: `${UTILS_PKG}::deepbookv3_utils::deposit_then_place_limit_order_by_owner`,
          arguments: [
            tx.object(GLOBAL_CONFIG),
            tx.object(CETUS_BM_INDEXER),
            tx.object(SUI_USDC_POOL),
            tx.object(bmId),
            suiCoin,
            usdcZero,
            deepZero,
            tx.pure.u8(0), // self_matching
            tx.pure.u8(0), // order_type (NO_RESTRICTION)
            tx.pure.u64(priceU64),
            tx.pure.u64(quantityMIST),
            tx.pure.bool(false), // is_bid = false (sell)
            tx.pure.bool(feeToken === 'DEEP'),
            tx.pure.u64(expireTime),
            tx.object.clock(),
          ],
          typeArguments: [SUI_COIN, USDC_COIN],
        })
      } else {
        // Market sell
        tx.moveCall({
          target: `${UTILS_PKG}::deepbookv3_utils::deposit_then_place_market_order_by_owner_v2`,
          arguments: [
            tx.object(GLOBAL_CONFIG),
            tx.object(CETUS_BM_INDEXER),
            tx.object(SUI_USDC_POOL),
            tx.object(bmId),
            suiCoin,
            usdcZero,
            deepZero,
            tx.pure.u8(0), // self_matching
            tx.pure.u64(quantityMIST),
            tx.pure.bool(false), // is_bid = false (sell)
            tx.pure.bool(feeToken === 'DEEP'),
            tx.pure.u64(priceU64),
            tx.object.clock(),
          ],
          typeArguments: [SUI_COIN, USDC_COIN],
        })
      }
    } else {
      // BUY: Need to use USDC coins (MergeCoins + SplitCoins)
      const usdcCoins = walletCoins.usdc
      if (usdcCoins.length === 0) {
        setError(t('deposit.err.noUsdc'))
        setLoading(false)
        return
      }

      const usdcNeeded = BigInt(Math.ceil(quantity * priceInUSDC * 1e6))
      const [usdcCoin1, ...otherUsdcCoins] = usdcCoins

      // Merge all USDC coins first
      if (otherUsdcCoins.length > 0) {
        tx.mergeCoins(tx.object(usdcCoin1.id), otherUsdcCoins.map(c => tx.object(c.id)))
      }

      // Split the needed amount
      const [usdcSplit] = tx.splitCoins(tx.object(usdcCoin1.id), [usdcNeeded])

      const [suiZero] = tx.moveCall({
        target: '0x2::coin::zero',
        arguments: [],
        typeArguments: [SUI_COIN],
      })

      const [deepZero] = tx.moveCall({
        target: '0x2::coin::zero',
        arguments: [],
        typeArguments: [DEEP_COIN],
      })

      if (orderType === 'limit') {
        // Limit buy
        const expireTime = (BigInt(Date.now()) * BigInt(1e6)) + ONE_YEAR_NANOS
        tx.moveCall({
          target: `${UTILS_PKG}::deepbookv3_utils::deposit_then_place_limit_order_by_owner`,
          arguments: [
            tx.object(GLOBAL_CONFIG),
            tx.object(CETUS_BM_INDEXER),
            tx.object(SUI_USDC_POOL),
            tx.object(bmId),
            suiZero,
            usdcSplit,
            deepZero,
            tx.pure.u8(0), // self_matching
            tx.pure.u8(0), // order_type (NO_RESTRICTION)
            tx.pure.u64(priceU64),
            tx.pure.u64(quantityMIST),
            tx.pure.bool(true), // is_bid = true (buy)
            tx.pure.bool(feeToken === 'DEEP'),
            tx.pure.u64(expireTime),
            tx.object.clock(),
          ],
          typeArguments: [SUI_COIN, USDC_COIN],
        })
      } else {
        // Market buy
        tx.moveCall({
          target: `${UTILS_PKG}::deepbookv3_utils::deposit_then_place_market_order_by_owner_v2`,
          arguments: [
            tx.object(GLOBAL_CONFIG),
            tx.object(CETUS_BM_INDEXER),
            tx.object(SUI_USDC_POOL),
            tx.object(bmId),
            suiZero,
            usdcSplit,
            deepZero,
            tx.pure.u8(0), // self_matching
            tx.pure.u64(quantityMIST),
            tx.pure.bool(true), // is_bid = true (buy)
            tx.pure.bool(feeToken === 'DEEP'),
            tx.pure.u64(priceU64),
            tx.object.clock(),
          ],
          typeArguments: [SUI_COIN, USDC_COIN],
        })
      }
    }

    signTransaction(
      { transaction: tx as any, chain: 'sui:mainnet' } as any,
      {
        onSuccess: async (signResult: any) => {
          try {
            const execResult = await suiClient.executeTransactionBlock({
              transactionBlock: signResult.bytes,
              signature: signResult.signature,
              options: { showEffects: true, showEvents: true }
            })
            if (execResult.effects?.status?.status === 'success') {
              setResult(t('deposit.success', { digest: execResult.digest.slice(0, 10) + '...' }))
              onDepositSuccess?.()
              if (execResult.events) {
                const orderEvent = execResult.events.find((e: any) =>
                  e.type?.includes('OrderPlaced') || e.type?.includes('PlaceLimitOrderEvent')
                )
                const parsedJson = orderEvent?.parsedJson as any
                if (parsedJson?.order_id) {
                  localStorage.setItem('lastOrderId', parsedJson.order_id.toString())
                }
              }
            } else {
              setError(t('deposit.failed', { reason: execResult.effects?.status?.error || t('deposit.err.unknown') }))
            }
          } catch (e) {
            setError((e as Error).message)
          } finally {
            setLoading(false)
          }
        },
        onError: (err: any) => {
          setError(t('deposit.signRejected', { reason: err }))
          setLoading(false)
        }
      }
    )
  }, [account, amount, price, isBid, feeToken, bmId, walletCoins, orderType, signTransaction, suiClient, onDepositSuccess])

  const total = (parseFloat(amount) || 0) * (parseFloat(price) || 0)

  return (
    <div className="deposit-panel">
      {!bmId && (
        <div className="no-bm-warning">
          <span>{t('deposit.noBm')}</span>
          <small>{t('deposit.noBmHint')}</small>
        </div>
      )}

      {/* Order Type Tabs */}
      <div className="order-tabs">
        <button
          className={`order-tab ${orderType === 'limit' ? 'active' : ''}`}
          onClick={() => setOrderType('limit')}
        >
          {t('deposit.tab.limit')}
        </button>
        <button
          className={`order-tab ${orderType === 'market' ? 'active' : ''}`}
          onClick={() => setOrderType('market')}
        >
          {t('deposit.tab.market')}
        </button>
      </div>

      {/* Buy/Sell Toggle */}
      <div className="side-toggle">
        <button
          className={`side-btn ${isBid ? 'active buy' : ''}`}
          onClick={() => setIsBid(true)}
        >
          {t('deposit.side.buy')}
        </button>
        <button
          className={`side-btn ${!isBid ? 'active sell' : ''}`}
          onClick={() => setIsBid(false)}
        >
          {t('deposit.side.sell')}
        </button>
      </div>

      {/* Form Fields */}
      <div className="order-form">
        <div className="form-row">
          <label>{orderType === 'limit' ? t('deposit.field.price') : t('deposit.field.market')}</label>
          {orderType === 'market' ? (
            <div className="market-price">
              {marketPrice ? marketPrice.toFixed(4) : '--'}
              <span className="market-label">{t('deposit.field.marketLabel')}</span>
            </div>
          ) : (
            <div className="input-with-suffix">
              <input
                type="number"
                step="0.0001"
                min="0.0001"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder={t('deposit.pricePlaceholder')}
              />
              <span className="suffix">USDC</span>
            </div>
          )}
        </div>

        <div className="form-row">
          <label>{t('deposit.field.amount')}</label>
          <div className="input-with-suffix">
            <input
              type="number"
              step="0.1"
              min="0.1"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.00"
            />
            <span className="suffix">SUI</span>
          </div>
        </div>

        {/* Percentage Slider */}
        <div className="percent-slider">
          {[25, 50, 75, 100].map((p) => (
            <button
              key={p}
              className="percent-btn"
              onClick={() => handleSliderChange(p)}
            >
              {p}%
            </button>
          ))}
        </div>

        {/* Fee Row */}
        <div className="fee-row">
          <div className="fee-info">
            <span className="fee-label">{t('deposit.fee')}</span>
            <span className="fee-value">
              ≈ {fee.toFixed(4)} {feeToken}
            </span>
          </div>
          <div className="fee-token-toggle">
            <button
              className={`fee-token-btn ${feeToken === 'SUI' ? 'active' : ''}`}
              onClick={() => setFeeToken('SUI')}
            >
              SUI
            </button>
            <button
              className={`fee-token-btn ${feeToken === 'DEEP' ? 'active' : ''}`}
              onClick={() => setFeeToken('DEEP')}
            >
              DEEP
            </button>
          </div>
        </div>

        {orderType === 'limit' && (
          <div className="form-row total-row">
            <label>{t('deposit.total')}</label>
            <div className="total-value">{total.toFixed(2)} USDC</div>
          </div>
        )}

        {orderType === 'limit' && (
          <div className="form-row expire-row">
            <label>{t('deposit.expire')}</label>
            <div className="expire-value">{t('deposit.expireValue')}</div>
          </div>
        )}

        {error && <div className="error-message">{error}</div>}
        {result && <div className="success-message">{result}</div>}

        <button
          className={`btn-submit ${isBid ? 'buy' : 'sell'}`}
          onClick={handlePlaceOrder}
          disabled={loading || !account || !amount || !bmId || (isBid && walletCoins.usdc.length === 0)}
        >
          {loading ? t('deposit.submit.processing') : isBid ? t('deposit.submit.buy') : t('deposit.submit.sell')}
        </button>

        {isBid && walletCoins.usdc.length === 0 && (
          <div className="hint-message">{t('deposit.hint.usdc')}</div>
        )}
      </div>
    </div>
  )
}

export default DepositPanel
