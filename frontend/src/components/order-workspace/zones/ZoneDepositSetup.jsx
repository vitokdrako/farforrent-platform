/* eslint-disable */
import React, { useState } from 'react'
import ZoneCard from '../ZoneCard'

/**
 * Zone: Deposit Setup - Налаштування застави
 * Для статусу: DRAFT, WAITING_CONFIRMATION
 */
export default function ZoneDepositSetup({
  amount = 0,
  method = 'Картка (холд)',
  releaseCondition = 'Після приймання',
  note = '',
  estimatedAmount,
  onUpdate,
  readOnly = false,
}) {
  const [localAmount, setLocalAmount] = useState(amount)
  const [localMethod, setLocalMethod] = useState(method)
  const [localRelease, setLocalRelease] = useState(releaseCondition)
  const [localNote, setLocalNote] = useState(note)
  
  const fmtUA = (n) => (Number(n) || 0).toLocaleString('uk-UA', { maximumFractionDigits: 0 })
  
  const handleSave = () => {
    onUpdate?.({
      amount: localAmount,
      method: localMethod,
      releaseCondition: localRelease,
      note: localNote,
    })
  }
  
  const methodOptions = [
    'Картка (холд)',
    'Готівка',
    'Безготівковий',
  ]
  
  const releaseOptions = [
    'Після приймання',
    '+24 год',
    '+48 год',
  ]
  
  return (
    <ZoneCard
      title="💰 Застава"
      hint="Розмір • метод • умови звільнення"
      tone="neutral"
      actions={!readOnly && onUpdate ? [
        { label: '💾 Зберегти', onClick: handleSave }
      ] : []}
    >
      <div className="grid grid-cols-2 gap-4">
        {/* Розмір застави */}
        <div>
          <label className="text-xs text-slate-500 block mb-1">Розмір застави</label>
          {readOnly ? (
            <div className="font-bold text-lg text-slate-800">₴ {fmtUA(localAmount)}</div>
          ) : (
            <input
              type="number"
              value={localAmount}
              onChange={(e) => setLocalAmount(parseFloat(e.target.value) || 0)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-right tabular-nums focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
            />
          )}
          {estimatedAmount && estimatedAmount !== localAmount && (
            <div className="text-xs text-slate-500 mt-1">
              Рекомендовано: ₴{fmtUA(estimatedAmount)}
            </div>
          )}
        </div>
        
        {/* Метод */}
        <div>
          <label className="text-xs text-slate-500 block mb-1">Метод</label>
          {readOnly ? (
            <div className="font-medium text-slate-800">{localMethod}</div>
          ) : (
            <select
              value={localMethod}
              onChange={(e) => setLocalMethod(e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
            >
              {methodOptions.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          )}
        </div>
        
        {/* Автозвільнення */}
        <div>
          <label className="text-xs text-slate-500 block mb-1">Автозвільнення</label>
          {readOnly ? (
            <div className="font-medium text-slate-800">{localRelease}</div>
          ) : (
            <select
              value={localRelease}
              onChange={(e) => setLocalRelease(e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
            >
              {releaseOptions.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          )}
        </div>
        
        {/* Примітка */}
        <div>
          <label className="text-xs text-slate-500 block mb-1">Примітка</label>
          {readOnly ? (
            <div className="font-medium text-slate-800">{localNote || '—'}</div>
          ) : (
            <input
              type="text"
              value={localNote}
              onChange={(e) => setLocalNote(e.target.value)}
              placeholder="Напр., підвищений ризик скло"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
            />
          )}
        </div>
      </div>
    </ZoneCard>
  )
}
