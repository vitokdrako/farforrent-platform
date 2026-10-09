/* eslint-disable */
import React from 'react'
import ZoneCard from '../ZoneCard'

/**
 * Zone: Issued Snapshot - Факт видачі (read-only)
 * Для статусу: ISSUED
 */
export default function ZoneIssuedSnapshot({
  issuedAt,
  issuedBy,
  itemsCount,
  rentAmount,
  depositAmount,
  onPrintInvoice,
}) {
  const fmtUA = (n) => (Number(n) || 0).toLocaleString('uk-UA', { maximumFractionDigits: 0 })
  
  const formatDateTime = (dateStr) => {
    if (!dateStr) return '—'
    const date = new Date(dateStr)
    return date.toLocaleString('uk-UA', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }
  
  return (
    <ZoneCard
      title="📤 Факт видачі"
      hint="Що видано • коли • ким (read-only)"
      tone="info"
      actions={onPrintInvoice ? [
        { label: '🖨️ Друк накладної', onClick: onPrintInvoice }
      ] : []}
    >
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="rounded-xl bg-slate-50 p-3">
          <div className="text-xs text-slate-500">Дата видачі</div>
          <div className="font-medium text-slate-800">{formatDateTime(issuedAt)}</div>
        </div>
        
        <div className="rounded-xl bg-slate-50 p-3">
          <div className="text-xs text-slate-500">Видав</div>
          <div className="font-medium text-slate-800">{issuedBy || '—'}</div>
        </div>
        
        <div className="rounded-xl bg-slate-50 p-3">
          <div className="text-xs text-slate-500">Позицій</div>
          <div className="font-medium text-slate-800">{itemsCount || 0} шт.</div>
        </div>
        
        <div className="rounded-xl bg-blue-50 p-3">
          <div className="text-xs text-blue-600">Сума</div>
          <div className="font-bold text-blue-800">₴ {fmtUA(rentAmount)}</div>
        </div>
      </div>
      
      <div className="mt-3 pt-3 border-t border-slate-100 text-sm text-slate-600">
        💰 Застава у холді: <b>₴{fmtUA(depositAmount)}</b>
      </div>
    </ZoneCard>
  )
}
