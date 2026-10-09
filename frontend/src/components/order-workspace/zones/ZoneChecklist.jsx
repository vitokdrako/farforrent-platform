/* eslint-disable */
import React from 'react'
import ZoneCard from '../ZoneCard'
import TonePill from '../TonePill'

/**
 * Zone: Checklist - Чеклист дій
 * Універсальний для різних статусів
 */
export default function ZoneChecklist({
  items = [],   // [{ id, label, checked, required }]
  onToggle,
  title = '✅ Чеклист',
  hint = 'Перевірка перед дією',
  readOnly = false,
}) {
  const checkedCount = items.filter(i => i.checked).length
  const requiredCount = items.filter(i => i.required).length
  const requiredChecked = items.filter(i => i.required && i.checked).length
  const allRequiredDone = requiredChecked === requiredCount
  const allDone = checkedCount === items.length
  
  const tone = allDone ? 'ok' : allRequiredDone ? 'info' : 'warn'
  
  return (
    <ZoneCard
      title={title}
      hint={hint}
      tone={tone}
      rightContent={
        <span className="text-sm text-slate-500">
          {checkedCount}/{items.length}
        </span>
      }
    >
      {items.length === 0 ? (
        <div className="text-center py-4 text-slate-400">
          Немає пунктів
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <label 
              key={item.id}
              className={`
                flex items-center gap-3 rounded-lg border p-3 cursor-pointer transition-colors
                ${item.checked 
                  ? 'bg-emerald-50 border-emerald-200' 
                  : item.required 
                  ? 'bg-amber-50 border-amber-200'
                  : 'bg-white border-slate-200 hover:bg-slate-50'
                }
                ${readOnly ? 'pointer-events-none' : ''}
              `}
            >
              <input
                type="checkbox"
                checked={item.checked}
                onChange={() => !readOnly && onToggle?.(item.id)}
                disabled={readOnly}
                className="w-5 h-5 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
              />
              <span className={`flex-1 text-sm ${item.checked ? 'line-through text-slate-500' : 'text-slate-800'}`}>
                {item.label}
              </span>
              {item.required && !item.checked && (
                <TonePill tone="warn">Обов'язково</TonePill>
              )}
            </label>
          ))}
        </div>
      )}
      
      {/* Підсумок */}
      {!allRequiredDone && requiredCount > 0 && (
        <div className="mt-3 text-xs text-amber-600 bg-amber-50 rounded-lg px-3 py-2">
          ⚠️ Залишилось обов'язкових: {requiredCount - requiredChecked}
        </div>
      )}
    </ZoneCard>
  )
}
