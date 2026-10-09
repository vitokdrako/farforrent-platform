/* eslint-disable */
import React, { useState } from 'react'
import ZoneCard from '../ZoneCard'

/**
 * Zone: Client Setup - Налаштування клієнта
 * Для статусу: WAITING_CONFIRMATION
 */
export default function ZoneClientSetup({
  clientName,
  clientPhone,
  clientEmail,
  clientType = 'retail', // retail | wholesale
  manager,
  discount = 0,
  onUpdateDiscount,
  onImportFromCRM,
  readOnly = false,
}) {
  const [localDiscount, setLocalDiscount] = useState(discount)
  
  const handleDiscountSave = () => {
    onUpdateDiscount?.(localDiscount)
  }
  
  return (
    <ZoneCard
      title="👤 Клієнт та умови"
      hint="Інформація про клієнта • тип • менеджер • знижка"
      tone="neutral"
      actions={!readOnly ? [
        { label: '💾 Зберегти знижку', onClick: handleDiscountSave },
        ...(onImportFromCRM ? [{ label: '📥 Імпорт з CRM', onClick: onImportFromCRM }] : [])
      ] : []}
    >
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Ліва колонка - інфо */}
        <div className="space-y-3">
          <div>
            <label className="text-xs text-slate-500">Імʼя клієнта</label>
            <div className="font-medium text-slate-800">{clientName || '—'}</div>
          </div>
          <div>
            <label className="text-xs text-slate-500">Телефон</label>
            <a href={`tel:${clientPhone}`} className="block font-medium text-blue-600 hover:text-blue-800">
              {clientPhone || '—'}
            </a>
          </div>
          <div>
            <label className="text-xs text-slate-500">Email</label>
            <div className="font-medium text-slate-800 text-sm break-words">{clientEmail || 'Не вказано'}</div>
          </div>
        </div>
        
        {/* Права колонка - налаштування */}
        <div className="space-y-3">
          <div>
            <label className="text-xs text-slate-500">Тип клієнта</label>
            <div className="font-medium text-slate-800">
              {clientType === 'wholesale' ? '🏢 Опт' : '👤 Роздріб'}
            </div>
          </div>
          <div>
            <label className="text-xs text-slate-500">Менеджер</label>
            <div className="font-medium text-slate-800">{manager || 'Не призначено'}</div>
          </div>
          <div>
            <label className="text-xs text-slate-500">Знижка (%)</label>
            {readOnly ? (
              <div className="font-medium text-slate-800">{discount}%</div>
            ) : (
              <input
                type="number"
                min="0"
                max="100"
                value={localDiscount}
                onChange={(e) => setLocalDiscount(parseFloat(e.target.value) || 0)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
              />
            )}
          </div>
        </div>
      </div>
    </ZoneCard>
  )
}
