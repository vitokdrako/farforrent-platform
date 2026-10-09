/* eslint-disable */
import React from 'react'
import ZoneCard from '../ZoneCard'

/**
 * Zone: Order History - Історія змін замовлення
 * Для статусу: CLOSED (архівні замовлення)
 */
export default function ZoneOrderHistory({
  events = [],
  title = "🕐 Історія статусів",
  hint = "Хронологія змін замовлення"
}) {
  const formatDate = (dateStr) => {
    if (!dateStr) return '—'
    return new Date(dateStr).toLocaleString('uk-UA', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  }
  
  const stageLabels = {
    'created': '📝 Створено',
    'updated': '✏️ Оновлено',
    'accepted': '✅ Прийнято',
    'processing': '⚙️ В обробці',
    'preparation': '📦 Комплектація',
    'ready': '✓ Готово',
    'issued': '🚚 Видано',
    'on_rent': '🏠 В оренді',
    'returned': '↩️ Повернено',
    'completed': '✓ Завершено',
    'archived': '📂 Архівовано',
    'cancelled': '❌ Скасовано'
  }
  
  return (
    <ZoneCard title={title} hint={hint} tone="neutral">
      {events.length === 0 ? (
        <div className="text-center py-4 text-slate-400">Немає записів</div>
      ) : (
        <div className="space-y-3 max-h-80 overflow-y-auto">
          {events.map((event, idx) => (
            <div key={idx} className="flex gap-3 border-l-2 border-blue-200 pl-3 py-1">
              <div className="flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-slate-800">
                    {stageLabels[event.stage] || event.stage}
                  </span>
                  {event.created_by && (
                    <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
                      {event.created_by}
                    </span>
                  )}
                </div>
                <div className="text-xs text-slate-500 mt-0.5">
                  {formatDate(event.created_at)}
                </div>
                {event.notes && (
                  <div className="text-xs text-slate-600 mt-1 bg-slate-50 p-2 rounded">
                    {event.notes}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </ZoneCard>
  )
}
