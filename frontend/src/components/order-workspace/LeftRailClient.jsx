/* eslint-disable */
import React from 'react'

/**
 * LeftRailClient - Блок клієнта в лівій панелі
 */
export default function LeftRailClient({
  name,
  phone,
  email,
  tier,           // 'new' | 'regular' | 'vip'
  orderCount,     // Кількість попередніх замовлень
}) {
  const tierConfig = {
    new: { label: 'Новий', color: 'bg-blue-100 text-blue-800' },
    regular: { label: 'Постійний', color: 'bg-emerald-100 text-emerald-800' },
    vip: { label: 'VIP', color: 'bg-amber-100 text-amber-800' },
  }
  
  const tierInfo = tierConfig[tier] || tierConfig.new
  
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-slate-800">Клієнт</h3>
        {tier && (
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${tierInfo.color}`}>
            {tierInfo.label}
            {orderCount > 0 && ` (${orderCount})`}
          </span>
        )}
      </div>
      
      <div className="space-y-3 text-sm">
        {/* Ім'я */}
        <div>
          <div className="text-xs text-slate-500 mb-0.5">Імʼя</div>
          <div className="font-medium text-slate-800">{name || '—'}</div>
        </div>
        
        {/* Телефон */}
        <div>
          <div className="text-xs text-slate-500 mb-0.5">Телефон</div>
          <a 
            href={`tel:${phone}`} 
            className="font-medium text-blue-600 hover:text-blue-800 flex items-center gap-1"
          >
            📞 {phone || '—'}
          </a>
        </div>
        
        {/* Email */}
        <div>
          <div className="text-xs text-slate-500 mb-0.5">Email</div>
          <div className="font-medium text-slate-800 break-words text-xs">
            {email || 'Не вказано'}
          </div>
        </div>
      </div>
    </div>
  )
}
