/* eslint-disable */
import React, { useState } from 'react'
import ZoneCard from '../ZoneCard'

/**
 * Zone: Notes - Нотатки
 * Універсальний для всіх статусів
 */
export default function ZoneNotes({
  notes = '',
  clientComment = '',
  onUpdateNotes,
  readOnly = false,
  title = '📝 Нотатки менеджера',
  hint = 'Внутрішні нотатки для команди',
}) {
  const [localNotes, setLocalNotes] = useState(notes)
  
  const handleSave = () => {
    onUpdateNotes?.(localNotes)
  }
  
  return (
    <ZoneCard
      title={title}
      hint={hint}
      tone="neutral"
      actions={!readOnly && onUpdateNotes ? [
        { label: '💾 Зберегти', onClick: handleSave }
      ] : []}
    >
      {/* Коментар клієнта */}
      {clientComment && (
        <div className="mb-3 rounded-lg bg-blue-50 border border-blue-200 p-3">
          <div className="text-xs text-blue-600 mb-1">💬 Коментар клієнта</div>
          <div className="text-sm text-slate-800">{clientComment}</div>
        </div>
      )}
      
      {/* Нотатки менеджера */}
      {readOnly ? (
        <div className="text-sm text-slate-700">
          {localNotes || <span className="text-slate-400">Немає нотаток</span>}
        </div>
      ) : (
        <textarea
          value={localNotes}
          onChange={(e) => setLocalNotes(e.target.value)}
          placeholder="Внутрішні нотатки для команди..."
          rows={3}
          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none resize-none"
        />
      )}
    </ZoneCard>
  )
}
