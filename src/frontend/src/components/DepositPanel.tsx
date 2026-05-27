import { useState, useCallback, useMemo } from 'react'
import { useCurrentAccount, useSignTransaction, useSuiClient } from '@mysten/dapp-kit'
import { Transaction } from '@mysten/sui/transactions'

const UTILS_PKG = '0x600138d3179e2fc746f6774f360a6e1fa68e90d66d082af66399adabe46f22a4'
const GLOBAL_CONFIG = '0xff1141ef80e7baf206c7930c274b465600e64884d8167f90d4cdb60197925163'
const CETUS_BM_INDEXER = '0x5c1a039f97ed1cbd84d54b5d633bdffd681086acc38961b1d366c4ecf680d150'
const SUI_USDC_POOL = '0xe05dafb5133bcffb8d59f4e12465dc0e9faeaa05e3e342a08fe135800e3e4407'
const USDC_COIN = '0xdba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC'
const SUI_COIN = '0x2::sui::SUI'
const DEEP_COIN = '0xdeeb7a4662eec9f2f3def03fb937a663dddaa2e215b8078a284d026b7946c270::deep::DEEP'

interface DepositPanelProps {
  onDepositSuccess?: () => void
}

type OrderType = 'limit' | 'market'
type FeeToken = 'SUI' | 'DEEP'

// DeepBook fee rates
const MAKER_FEE_RATE = 0.0001 // 0.01% maker fee
const TAKER_FEE_RATE = 0.001 // 0.1% taker fee

function DepositPanel({ onDepositSuccess }: DepositPanelProps) {
  const [orderType, setOrderType] = useState<OrderType>('limit')
  const [amount, setAmount] = useState('')
  const [price, setPrice] = useState('')
  const [isBid, setIsBid] = useState(true) // true = buy, false = sell
  const [feeToken, setFeeToken] = useState<FeeToken>('SUI')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const account = useCurrentAccount()
  const { mutate: signTransaction } = useSignTransaction()
  const suiClient = useSuiClient()

  const bmId = localStorage.getItem('balanceManagerId') || ''

  // Calculate order value and fees
  const orderValue = useMemo(() => {
    const qty = parseFloat(amount) || 0
    const px = parseFloat(price) || 0
    return qty * px
  }, [amount, price])

  const feeRate = orderType === 'limit' ? MAKER_FEE_RATE : TAKER_FEE_RATE
  const fee = useMemo(() => {
    if (orderType === 'market') {
      // For market orders, fee is based on SUI quantity
      return (parseFloat(amount) || 0) * feeRate
    }
    // For limit orders, fee is based on the order value in USDC
    return orderValue * feeRate
  }, [amount, price, orderType, orderValue, feeRate])

  const handleSliderChange = (percent: number) => {
    // This would be connected to wallet/BalanceManager balance
    // For now, just set a placeholder amount
    const maxAmount = 10 // Example max
    setAmount((maxAmount * percent / 100).toFixed(2))
  }

  const handleDepositAndOrder = useCallback(() => {
    if (!account || !amount) return

    const quantity = parseFloat(amount)
    const priceInUSDC = parseFloat(price) || 0

    if (isNaN(quantity) || quantity <= 0) {
      setError('请输入有效的数量')
      return
    }

    if (orderType === 'limit' && (isNaN(priceInUSDC) || priceInUSDC <= 0)) {
      setError('请输入有效的价格')
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)

    const tx = new Transaction()
    tx.setGasBudget(50000000)
    tx.setSender(account.address)

    const [suiCoin] = tx.splitCoins(tx.gas, [BigInt(Math.floor(quantity * 1e9))])

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
        tx.pure.u8(0),
        tx.pure.u8(0),
        tx.pure.u64(Math.floor(priceInUSDC * 1e6)),
        tx.pure.u64(BigInt(Math.floor(quantity * 1e9))),
        tx.pure.bool(isBid),
        tx.pure.bool(feeToken === 'DEEP'), // payWithDeep
        tx.pure.u64(Date.now() * 1e6 + 3600 * 1e6),
        tx.object.clock(),
      ],
      typeArguments: [SUI_COIN, USDC_COIN],
    })

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
              setResult(`成功！交易: ${execResult.digest.slice(0, 10)}...`)
              const deposited = parseFloat(localStorage.getItem('totalDeposited') || '0')
              localStorage.setItem('totalDeposited', (deposited + parseFloat(amount)).toString())
              onDepositSuccess?.()
              if (execResult.events) {
                const orderEvent = execResult.events.find((e: any) => e.type?.includes('OrderPlaced'))
                const parsedJson = orderEvent?.parsedJson as any
                if (parsedJson?.order_id) {
                  localStorage.setItem('lastOrderId', parsedJson.order_id.toString())
                }
              }
            } else {
              setError(`失败`)
            }
          } catch (e) {
            setError((e as Error).message)
          } finally {
            setLoading(false)
          }
        },
        onError: (err: any) => {
          setError(`签名被拒绝: ${err}`)
          setLoading(false)
        }
      }
    )
  }, [account, amount, price, isBid, feeToken, bmId, signTransaction, suiClient, onDepositSuccess, orderType])

  const total = (parseFloat(amount) || 0) * (parseFloat(price) || 0)

  return (
    <div className="deposit-panel">
      {!bmId && (
        <div className="no-bm-warning">
          <span>需要先创建 BalanceManager</span>
          <small>请使用 AI 策略页面创建</small>
        </div>
      )}

      {/* Order Type Tabs */}
      <div className="order-tabs">
        <button
          className={`order-tab ${orderType === 'limit' ? 'active' : ''}`}
          onClick={() => setOrderType('limit')}
        >
          限价
        </button>
        <button
          className={`order-tab ${orderType === 'market' ? 'active' : ''}`}
          onClick={() => setOrderType('market')}
        >
          市价
        </button>
      </div>

      {/* Buy/Sell Toggle */}
      <div className="side-toggle">
        <button
          className={`side-btn ${isBid ? 'active buy' : ''}`}
          onClick={() => setIsBid(true)}
        >
          买入
        </button>
        <button
          className={`side-btn ${!isBid ? 'active sell' : ''}`}
          onClick={() => setIsBid(false)}
        >
          卖出
        </button>
      </div>

      {/* Form Fields */}
      <div className="order-form">
        {orderType === 'limit' && (
          <div className="form-row">
            <label>价格</label>
            <div className="input-with-suffix">
              <input
                type="number"
                step="0.0001"
                min="0.0001"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder="0.00"
              />
              <span className="suffix">USDC</span>
            </div>
          </div>
        )}

        <div className="form-row">
          <label>数量</label>
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
            <span className="fee-label">手续费</span>
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
            <label>总计</label>
            <div className="total-value">{total.toFixed(2)} USDC</div>
          </div>
        )}

        {error && <div className="error-message">{error}</div>}
        {result && <div className="success-message">{result}</div>}

        <button
          className={`btn-submit ${isBid ? 'buy' : 'sell'}`}
          onClick={handleDepositAndOrder}
          disabled={loading || !account || !amount || !bmId}
        >
          {loading ? '处理中...' : isBid ? `买入 SUI` : `卖出 SUI`}
        </button>
      </div>
    </div>
  )
}

export default DepositPanel
