/* eslint-disable */
import React from 'react'
import ZoneCard from '../ZoneCard'
import TonePill from '../TonePill'

/**
 * Zone: Payment Gate - Перевірка оплати
 * Для статусу: READY_FOR_ISSUE
 */
export default function ZonePaymentGate({
  rentPaid = false,
  depositPaid = false,
  rentAmount = 0,
  depositAmount = 0,
  onMarkRentPaid,
  onMarkDepositPaid,
}) {
  const fmtUA = (n) => (Number(n) || 0).toLocaleString('uk-UA', { maximumFractionDigits: 0 })
  
  const allPaid = rentPaid && depositPaid
  const tone = allPaid ? 'ok' : 'warn'
  
  return (
    <ZoneCard
      title="💳 Оплата"
      hint="Перевірка оплати перед видачею"
      tone={tone}
    >
      <div className="space-y-3">
        {/* Оренда */}
        <div className={`
          rounded-xl border p-4 flex items-center justify-between
          ${rentPaid ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'}
        `}>
          <div>
            <div className="text-sm text-slate-600">Оренда</div>
            <div className="text-lg font-bold text-slate-800">₴ {fmtUA(rentAmount)}</div>
          </div>
          <div className="flex items-center gap-2">
            <TonePill tone={rentPaid ? 'ok' : 'warn'}>
              {rentPaid ? 'Оплачено' : 'Не оплачено'}
            </TonePill>
            {!rentPaid && onMarkRentPaid && (
              <button
                onClick={onMarkRentPaid}
                className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-sm hover:bg-emerald-700"
              >
                ✓ Підтвердити
              </button>
            )}
          </div>
        </div>
        
        {/* Застава */}
        <div className={`
          rounded-xl border p-4 flex items-center justify-between
          ${depositPaid ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'}
        `}>
          <div>
            <div className="text-sm text-slate-600">Застава</div>
            <div className="text-lg font-bold text-slate-800">₴ {fmtUA(depositAmount)}</div>
          </div>
          <div className="flex items-center gap-2">
            <TonePill tone={depositPaid ? 'ok' : 'warn'}>
              {depositPaid ? 'Оплачено' : 'Не оплачено'}
            </TonePill>
            {!depositPaid && onMarkDepositPaid && (
              <button
                onClick={onMarkDepositPaid}
                className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-sm hover:bg-emerald-700"
              >
                ✓ Підтвердити
              </button>
            )}
          </div>
        </div>
        
        {/* Gate message */}
        {!allPaid && (
          <div className="text-sm text-amber-700 bg-amber-50 rounded-lg p-3 border border-amber-200">
            ⚠️ <b>UI Gate:</b> Видача заблокована до повної оплати
          </div>
        )}
      </div>
    </ZoneCard>
  )
}
