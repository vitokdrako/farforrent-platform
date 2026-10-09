/* eslint-disable */
import React, { useState } from 'react'
import ZoneCard from '../ZoneCard'

/**
 * Zone: Delivery Setup - Налаштування доставки
 * Для статусу: DRAFT, WAITING_CONFIRMATION
 */
export default function ZoneDeliverySetup({
  deliveryType = 'pickup',  // pickup | delivery
  address = '',
  instructions = '',
  onUpdate,
  readOnly = false,
}) {
  const [localType, setLocalType] = useState(deliveryType)
  const [localAddress, setLocalAddress] = useState(address)
  const [localInstructions, setLocalInstructions] = useState(instructions)
  
  const handleSave = () => {
    onUpdate?.({
      deliveryType: localType,
      address: localAddress,
      instructions: localInstructions,
    })
  }
  
  return (
    <ZoneCard
      title="🚚 Доставка / самовивіз"
      hint="Спосіб отримання • адреса • інструкції"
      tone="neutral"
      actions={!readOnly && onUpdate ? [
        { label: '💾 Зберегти', onClick: handleSave }
      ] : []}
    >
      <div className="space-y-4">
        {/* Тип доставки */}
        <div className="flex gap-4">
          <label className={`
            flex-1 rounded-xl border p-3 cursor-pointer transition-colors
            ${localType === 'pickup' ? 'bg-blue-50 border-blue-300' : 'bg-white border-slate-200 hover:bg-slate-50'}
            ${readOnly ? 'pointer-events-none' : ''}
          `}>
            <input
              type="radio"
              name="deliveryType"
              checked={localType === 'pickup'}
              onChange={() => !readOnly && setLocalType('pickup')}
              className="sr-only"
            />
            <div className="flex items-center gap-2">
              <span className="text-lg">🏠</span>
              <div>
                <div className="font-medium text-slate-800">Самовивіз</div>
                <div className="text-xs text-slate-500">Клієнт забирає сам</div>
              </div>
            </div>
          </label>
          
          <label className={`
            flex-1 rounded-xl border p-3 cursor-pointer transition-colors
            ${localType === 'delivery' ? 'bg-blue-50 border-blue-300' : 'bg-white border-slate-200 hover:bg-slate-50'}
            ${readOnly ? 'pointer-events-none' : ''}
          `}>
            <input
              type="radio"
              name="deliveryType"
              checked={localType === 'delivery'}
              onChange={() => !readOnly && setLocalType('delivery')}
              className="sr-only"
            />
            <div className="flex items-center gap-2">
              <span className="text-lg">🚚</span>
              <div>
                <div className="font-medium text-slate-800">Доставка</div>
                <div className="text-xs text-slate-500">Нова Пошта / кур'єр</div>
              </div>
            </div>
          </label>
        </div>
        
        {/* Адреса */}
        {localType === 'delivery' && (
          <div className="space-y-3">
            <div>
              <label className="text-xs text-slate-500 block mb-1">Адреса / відділення</label>
              {readOnly ? (
                <div className="font-medium text-slate-800">{localAddress || '—'}</div>
              ) : (
                <input
                  type="text"
                  value={localAddress}
                  onChange={(e) => setLocalAddress(e.target.value)}
                  placeholder="вул. Прикладна, 1 / ВП №..."
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
                />
              )}
            </div>
            <div>
              <label className="text-xs text-slate-500 block mb-1">Інструкції для складу</label>
              {readOnly ? (
                <div className="font-medium text-slate-800">{localInstructions || '—'}</div>
              ) : (
                <input
                  type="text"
                  value={localInstructions}
                  onChange={(e) => setLocalInstructions(e.target.value)}
                  placeholder="Ліфт/рампа/контакти..."
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
                />
              )}
            </div>
          </div>
        )}
      </div>
    </ZoneCard>
  )
}
