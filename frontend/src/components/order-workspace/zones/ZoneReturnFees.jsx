/* eslint-disable */
import React from 'react'
import ZoneCard from '../ZoneCard'

/**
 * Zone: Return Fees - Нарахування штрафів при поверненні
 * Для статусу: INTAKE
 */
export default function ZoneReturnFees({
  lateFee = 0,
  cleaningFee = 0,
  damageFee = 0,
  onSetLateFee,
  onSetCleaningFee,
  onSetDamageFee,
  readOnly = false,
}) {
  const totalFees = lateFee + cleaningFee + damageFee
  const fmtUA = (n) => (Number(n) || 0).toLocaleString('uk-UA', { maximumFractionDigits: 0 })
  
  const tone = totalFees > 0 ? 'warn' : 'ok'
  
  return (
    <ZoneCard
      title="💰 Нарахування"
      hint={totalFees > 0 ? `До доплати ₴${fmtUA(totalFees)}` : 'Без штрафів'}
      tone={tone}
    >
      <div className="space-y-3">
        {/* Пеня за прострочку */}
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-medium text-slate-700">Пеня за прострочку</div>
            <div className="text-xs text-slate-500">За несвоєчасне повернення</div>
          </div>
          {readOnly ? (
            <div className="text-lg font-semibold text-slate-800">₴{fmtUA(lateFee)}</div>
          ) : (
            <input
              type="number"
              min="0"
              value={lateFee}
              onChange={(e) => onSetLateFee?.(Number(e.target.value) || 0)}
              className="w-28 rounded-lg border border-slate-200 px-3 py-2 text-right font-medium focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
            />
          )}
        </div>
        
        {/* Миття/чистка */}
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-medium text-slate-700">Миття/сушка/чистка</div>
            <div className="text-xs text-slate-500">Додаткове обслуговування</div>
          </div>
          {readOnly ? (
            <div className="text-lg font-semibold text-slate-800">₴{fmtUA(cleaningFee)}</div>
          ) : (
            <input
              type="number"
              min="0"
              value={cleaningFee}
              onChange={(e) => onSetCleaningFee?.(Number(e.target.value) || 0)}
              className="w-28 rounded-lg border border-slate-200 px-3 py-2 text-right font-medium focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
            />
          )}
        </div>
        
        {/* Збитки */}
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-medium text-slate-700">Збитки (пошкодження)</div>
            <div className="text-xs text-slate-500">Компенсація за пошкодження</div>
          </div>
          {readOnly ? (
            <div className="text-lg font-semibold text-slate-800">₴{fmtUA(damageFee)}</div>
          ) : (
            <input
              type="number"
              min="0"
              value={damageFee}
              onChange={(e) => onSetDamageFee?.(Number(e.target.value) || 0)}
              className="w-28 rounded-lg border border-slate-200 px-3 py-2 text-right font-medium focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
            />
          )}
        </div>
        
        {/* Разом */}
        <div className="flex items-center justify-between pt-3 border-t border-slate-200">
          <div className="text-sm font-semibold text-slate-800">Разом до доплати</div>
          <div className={`text-xl font-bold ${totalFees > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>
            ₴{fmtUA(totalFees)}
          </div>
        </div>
        
        {/* Інформаційне повідомлення */}
        {totalFees > 0 && (
          <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-sm">
            <div className="font-medium text-amber-800 mb-1">💰 Інформація</div>
            <div className="text-amber-700">
              Після завершення приймання дані про доплату будуть передані у фінансовий кабінет.
            </div>
          </div>
        )}
      </div>
    </ZoneCard>
  )
}
