/* eslint-disable */
import React from 'react'
import ZoneCard from '../ZoneCard'

/**
 * Zone: Finance History - Фінансова історія замовлення
 * Для статусу: CLOSED (архівні замовлення)
 */
export default function ZoneFinanceHistory({
  transactions = [],
  title = "💰 Фінансова історія",
  hint = "Усі платежі та транзакції"
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
  
  const typeLabels = {
    'payment': '💵 Оплата',
    'deposit_hold': '🔒 Застава',
    'deposit_release': '↩️ Повернення застави',
    'damage': '⚠️ Збитки',
    'refund': '↩️ Повернення',
    'adjustment': '✏️ Коригування'
  }
  
  const methodLabels = {
    'cash': 'Готівка',
    'card': 'Картка',
    'bank_transfer': 'Переказ',
    'terminal': 'Термінал'
  }
  
  // Підрахунки
  const totalPayments = transactions
    .filter(t => t.type === 'payment')
    .reduce((sum, t) => sum + (t.credit || 0), 0)
  
  const totalDeposit = transactions
    .filter(t => t.type === 'deposit_hold')
    .reduce((sum, t) => sum + (t.credit || 0), 0)
  
  const totalReturned = transactions
    .filter(t => t.type === 'deposit_release' || t.type === 'refund')
    .reduce((sum, t) => sum + (t.debit || t.credit || 0), 0)
  
  const totalDamage = transactions
    .filter(t => t.type === 'damage')
    .reduce((sum, t) => sum + (t.debit || 0), 0)
  
  return (
    <ZoneCard title={title} hint={hint} tone="neutral">
      {transactions.length === 0 ? (
        <div className="text-center py-4 text-slate-400">Немає транзакцій</div>
      ) : (
        <>
          <div className="space-y-3 max-h-64 overflow-y-auto mb-4">
            {transactions.map((tx, idx) => (
              <div key={idx} className="flex gap-3 border-l-2 border-emerald-200 pl-3 py-1">
                <div className="flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-slate-800">
                      {typeLabels[tx.type] || tx.type}
                    </span>
                    <span className={`text-sm font-semibold ${
                      tx.credit > 0 ? 'text-emerald-600' : 'text-rose-600'
                    }`}>
                      {tx.credit > 0 ? '+' : '-'}₴{Math.abs(tx.credit || tx.debit || 0).toFixed(0)}
                    </span>
                  </div>
                  <div className="text-xs text-slate-500 mt-0.5 flex items-center gap-2 flex-wrap">
                    <span>{formatDate(tx.date || tx.created_at)}</span>
                    {tx.payment_method && (
                      <span className="bg-slate-100 px-1.5 py-0.5 rounded">
                        {methodLabels[tx.payment_method] || tx.payment_method}
                      </span>
                    )}
                    {tx.created_by && (
                      <span className="bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full">
                        {tx.created_by}
                      </span>
                    )}
                  </div>
                  {tx.notes && (
                    <div className="text-xs text-slate-600 mt-1">{tx.notes}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
          
          {/* Підсумки */}
          <div className="border-t border-slate-200 pt-3 space-y-1">
            <div className="flex justify-between text-sm">
              <span className="text-slate-600">Оплачено:</span>
              <span className="font-semibold text-emerald-600">₴{totalPayments.toFixed(0)}</span>
            </div>
            {totalDeposit > 0 && (
              <div className="flex justify-between text-sm">
                <span className="text-slate-600">Застава:</span>
                <span className="font-semibold text-blue-600">₴{totalDeposit.toFixed(0)}</span>
              </div>
            )}
            {totalReturned > 0 && (
              <div className="flex justify-between text-sm">
                <span className="text-slate-600">Повернено:</span>
                <span className="font-semibold text-amber-600">₴{totalReturned.toFixed(0)}</span>
              </div>
            )}
            {totalDamage > 0 && (
              <div className="flex justify-between text-sm">
                <span className="text-slate-600">Збитки:</span>
                <span className="font-semibold text-rose-600">₴{totalDamage.toFixed(0)}</span>
              </div>
            )}
          </div>
        </>
      )}
    </ZoneCard>
  )
}
