import { useState, useCallback } from 'react'
import { useCurrentAccount, useSignTransaction, useSuiClient } from '@mysten/dapp-kit'
import { Transaction } from '@mysten/sui/transactions'
import { useI18n } from '../i18n/I18nProvider'

const V1_PKG = '0x2c8d603bc51326b8c13cef9dd07031a408a48dddb541963357661df5d3204809'
const SUI_COIN = '0x2::sui::SUI'
const USDC_COIN = '0xdba34672e30cb065b1f93e3ab55318768fd6fef66c15942c9f7cb846e2f900e7::usdc::USDC'
const SUI_USDC_POOL = '0xe05dafb5133bcffb8d59f4e12465dc0e9faeaa05e3e342a08fe135800e3e4407'

interface VaultPanelProps {
  onSuccess?: () => void
}

function VaultPanel({ onSuccess }: VaultPanelProps) {
  const [withdrawing, setWithdrawing] = useState<'sui' | 'usdc' | null>(null)
  const [claiming, setClaiming] = useState(false)
  const account = useCurrentAccount()
  const { mutate: signTransaction } = useSignTransaction()
  const suiClient = useSuiClient()
  const { t } = useI18n()

  const bmId = localStorage.getItem('balanceManagerId') || ''

  // Withdraw from BM to wallet
  const handleWithdraw = useCallback((token: 'sui' | 'usdc') => {
    if (!account || !bmId) return

    setWithdrawing(token)

    const tx = new Transaction()
    tx.setGasBudget(100000000)
    tx.setSender(account.address)

    const coinType = token === 'sui' ? SUI_COIN : USDC_COIN

    const [withdrawn] = tx.moveCall({
      target: `${V1_PKG}::balance_manager::withdraw_all`,
      arguments: [tx.object(bmId)],
      typeArguments: [coinType],
    })

    tx.transferObjects([withdrawn], account.address)

    signTransaction(
      { transaction: tx as any, chain: 'sui:mainnet' } as any,
      {
        onSuccess: async (result: any) => {
          try {
            const execResult = await suiClient.executeTransactionBlock({
              transactionBlock: result.bytes,
              signature: result.signature,
              options: { showEffects: true }
            })
            if (execResult.effects?.status?.status === 'success') {
              alert(t('vault.withdraw.success', { token: token.toUpperCase() }))
              onSuccess?.()
            }
          } catch (e) {
            alert(t('vault.withdraw.failed'))
          } finally {
            setWithdrawing(null)
          }
        },
        onError: () => {
          setWithdrawing(null)
        }
      }
    )
  }, [account, bmId, signTransaction, suiClient])

  // Claim settled funds (for expired/abnormal orders)
  const handleClaim = useCallback(() => {
    if (!account || !bmId) return

    setClaiming(true)

    const tx = new Transaction()
    tx.setGasBudget(100000000)
    tx.setSender(account.address)

    // Generate proof
    const [proof] = tx.moveCall({
      target: `${V1_PKG}::balance_manager::generate_proof_as_owner`,
      arguments: [tx.object(bmId)],
      typeArguments: [],
    })

    // Withdraw settled funds
    tx.moveCall({
      target: `${V1_PKG}::pool::withdraw_settled_amounts`,
      arguments: [
        tx.object(SUI_USDC_POOL),
        tx.object(bmId),
        proof,
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
              alert(t('vault.claim.success'))
              onSuccess?.()
            }
          } catch (e) {
            alert(t('vault.claim.failed'))
          } finally {
            setClaiming(false)
          }
        },
        onError: () => {
          setClaiming(false)
        }
      }
    )
  }, [account, bmId, signTransaction, suiClient])

  return (
    <div className="card">
      <h2>{t('vault.title')}</h2>

      {!bmId ? (
        <div className="no-bm-warning">
          <span>{t('vault.noBm')}</span>
          <small>{t('vault.noBmHint')}</small>
        </div>
      ) : (
        <>
          <div className="vault-info">
            <div className="bm-id-display">
              <label>{t('vault.bmLabel')}</label>
              <span className="bm-id">{bmId}</span>
            </div>
          </div>

          <div className="vault-actions">
            <h3>{t('vault.withdraw.title')}</h3>
            <p className="hint">{t('vault.withdraw.hint')}</p>

            <div className="action-buttons">
              <button
                className="btn btn-primary"
                onClick={() => handleWithdraw('sui')}
                disabled={withdrawing !== null || claiming}
              >
                {withdrawing === 'sui' ? t('vault.withdraw.processing') : t('vault.withdraw.sui')}
              </button>

              <button
                className="btn btn-primary"
                onClick={() => handleWithdraw('usdc')}
                disabled={withdrawing !== null || claiming}
              >
                {withdrawing === 'usdc' ? t('vault.withdraw.processing') : t('vault.withdraw.usdc')}
              </button>
            </div>
          </div>

          <div className="vault-claim">
            <h3>{t('vault.claim.title')}</h3>
            <p className="hint">{t('vault.claim.hint')}</p>

            <button
              className="btn btn-secondary"
              onClick={handleClaim}
              disabled={claiming || withdrawing !== null}
            >
              {claiming ? t('vault.claim.processing') : t('vault.claim.button')}
            </button>
          </div>
        </>
      )}
    </div>
  )
}

export default VaultPanel
