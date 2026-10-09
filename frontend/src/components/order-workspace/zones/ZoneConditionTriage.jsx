/* eslint-disable */
import React from 'react'
import ZoneCard from '../ZoneCard'
import TonePill from '../TonePill'

/**
 * Zone: Condition Triage - Оцінка стану при поверненні
 * Для статусу: INTAKE
 */
export default function ZoneConditionTriage({
  items = [],    // [{ id, name, sku, status, findings }]
  onSetStatus,   // (itemId, status) => void
  onOpenFinding, // (itemId) => void
}) {
  const statusConfig = {
    ok: { label: 'OK', color: 'bg-emerald-500', tone: 'ok' },
    dirty: { label: 'Бруд', color: 'bg-amber-500', tone: 'warn' },
    damaged: { label: 'Пошкоджено', color: 'bg-rose-500', tone: 'danger' },
    missing: { label: 'Нестача', color: 'bg-slate-500', tone: 'neutral' },
  }
  
  const counts = {
    ok: items.filter(i => i.status === 'ok').length,
    dirty: items.filter(i => i.status === 'dirty').length,
    damaged: items.filter(i => i.status === 'damaged').length,
    missing: items.filter(i => i.status === 'missing').length,
    pending: items.filter(i => !i.status).length,
  }
  
  const hasIssues = counts.dirty > 0 || counts.damaged > 0 || counts.missing > 0
  const allChecked = counts.pending === 0
  
  const tone = !allChecked ? 'info' : hasIssues ? 'warn' : 'ok'
  
  return (
    <ZoneCard
      title="🔍 Оцінка стану"
      hint="OK / бруд / пошкодження / нестача"
      tone={tone}
      rightContent={
        <div className="flex gap-2 text-xs">
          {counts.ok > 0 && <TonePill tone="ok">{counts.ok} OK</TonePill>}
          {counts.dirty > 0 && <TonePill tone="warn">{counts.dirty} Бруд</TonePill>}
          {counts.damaged > 0 && <TonePill tone="danger">{counts.damaged} Пошк.</TonePill>}
          {counts.missing > 0 && <TonePill tone="neutral">{counts.missing} Нест.</TonePill>}
        </div>
      }
    >
      {items.length === 0 ? (
        <div className="text-center py-4 text-slate-400">
          Немає позицій для перевірки
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <div 
              key={item.id}
              className={`
                rounded-xl border p-3
                ${item.status === 'ok' ? 'bg-emerald-50 border-emerald-200' :
                  item.status === 'dirty' ? 'bg-amber-50 border-amber-200' :
                  item.status === 'damaged' ? 'bg-rose-50 border-rose-200' :
                  item.status === 'missing' ? 'bg-slate-100 border-slate-300' :
                  'bg-white border-slate-200'}
              `}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="font-medium text-sm text-slate-800 truncate">{item.name}</div>
                  <div className="text-xs text-slate-500">{item.sku}</div>
                </div>
                
                {/* Кнопки статусу */}
                <div className="flex gap-1 flex-shrink-0">
                  {Object.entries(statusConfig).map(([status, config]) => (
                    <button
                      key={status}
                      onClick={() => onSetStatus?.(item.id, status)}
                      className={`
                        w-8 h-8 rounded-lg text-xs font-medium transition-all
                        ${item.status === status 
                          ? `${config.color} text-white` 
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                        }
                      `}
                      title={config.label}
                    >
                      {status === 'ok' ? '✓' : status === 'dirty' ? '💧' : status === 'damaged' ? '🔨' : '❓'}
                    </button>
                  ))}
                  
                  {/* Кнопка знахідки */}
                  {(item.status === 'dirty' || item.status === 'damaged') && (
                    <button
                      onClick={() => onOpenFinding?.(item.id)}
                      className="px-2 h-8 rounded-lg bg-amber-100 text-amber-700 text-xs hover:bg-amber-200"
                    >
                      📝
                    </button>
                  )}
                </div>
              </div>
              
              {/* Знахідки */}
              {item.findings && item.findings.length > 0 && (
                <div className="mt-2 pt-2 border-t border-slate-200">
                  <div className="text-xs text-slate-500 mb-1">Знахідки:</div>
                  {item.findings.map((f, idx) => (
                    <div key={idx} className="text-xs text-slate-700">
                      • {f.type}: {f.description} (₴{f.amount || 0})
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      
      {/* Підсумок */}
      {counts.pending > 0 && (
        <div className="mt-3 text-xs text-blue-600 bg-blue-50 rounded-lg px-3 py-2">
          ℹ️ Залишилось перевірити: {counts.pending} позицій
        </div>
      )}
    </ZoneCard>
  )
}
