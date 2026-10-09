/* eslint-disable */
import React, { useState } from 'react'
import ZoneCard from '../ZoneCard'
import TonePill from '../TonePill'
import { ChevronDown, ChevronUp, Package, Clock, AlertTriangle, Wrench, Droplets, Sparkles } from 'lucide-react'

/**
 * Zone: Availability Gate - Перевірка доступності
 * Для статусу: WAITING_CONFIRMATION
 * 
 * Показує детальну інформацію про конфлікти:
 * - Номер замовлення в якому товар
 * - Статус товару (в оренді, в чистці, ремонт)
 * - Дати оренди конфліктуючих замовлень
 * - ⚠️ НОВЕ: Попередження про товари на обробці (мийка/прання/хімчистка/реставрація)
 */
export default function ZoneAvailabilityGate({
  conflicts = [],    // [{ sku, name, type, level, available, requested, nearbyOrders, processingWarnings }]
  isChecking = false,
  hasItems = false,
  hasDates = false,
  onCheckConflicts,
}) {
  const [expandedConflicts, setExpandedConflicts] = useState(new Set())
  
  const hasConflicts = conflicts.length > 0
  const hasErrors = conflicts.some(c => c.level === 'error')
  
  const tone = isChecking ? 'info' : hasErrors ? 'danger' : hasConflicts ? 'warn' : 'ok'
  
  const toggleExpand = (idx) => {
    setExpandedConflicts(prev => {
      const next = new Set(prev)
      if (next.has(idx)) {
        next.delete(idx)
      } else {
        next.add(idx)
      }
      return next
    })
  }
  
  const getConflictLabel = (type) => {
    const labels = {
      'out_of_stock': '🔴 Немає на складі',
      'insufficient': '❌ Недостатньо',
      'tight_schedule': '⚠️ Щільний графік',
      'low_stock': '📦 Малий запас',
      'partial_return_risk': '🚨 Не повернуто з оренди',
      'processing_rush': '⏰ Потрібно поторопитися з обробкою',
      'on_processing': '🧼 Товар на обробці',
    }
    return labels[type] || type
  }
  
  const getStatusLabel = (status) => {
    const labels = {
      'processing': 'В обробці',
      'ready_for_issue': 'Готово до видачі',
      'issued': 'Видано',
      'on_rent': 'В оренді',
      'cleaning': 'В чистці',
      'repair': 'На ремонті',
      'damaged': 'Пошкоджено',
    }
    return labels[status] || status
  }
  
  const getStatusIcon = (status) => {
    switch(status) {
      case 'issued':
      case 'on_rent':
        return <Package className="h-3.5 w-3.5 text-blue-500" />
      case 'cleaning':
        return <Clock className="h-3.5 w-3.5 text-cyan-500" />
      case 'repair':
      case 'damaged':
        return <Wrench className="h-3.5 w-3.5 text-orange-500" />
      default:
        return <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
    }
  }
  
  const getProcessingIcon = (type) => {
    switch(type) {
      case 'on_wash':
        return <Droplets className="h-3.5 w-3.5 text-blue-500" />
      case 'on_laundry':
        return <Sparkles className="h-3.5 w-3.5 text-purple-500" />
      case 'on_restoration':
        return <Wrench className="h-3.5 w-3.5 text-orange-500" />
      case 'awaiting_assignment':
        return <Clock className="h-3.5 w-3.5 text-amber-500" />
      default:
        return <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
    }
  }
  
  const formatDate = (dateStr) => {
    if (!dateStr) return '—'
    const date = new Date(dateStr)
    return date.toLocaleDateString('uk-UA', { day: 'numeric', month: 'short' })
  }
  
  return (
    <ZoneCard
      title="📊 Доступність товарів"
      hint="Перевірка конфліктів та доступності на вказані дати"
      tone={tone}
      actions={onCheckConflicts ? [
        { label: '🔄 Перевірити', onClick: onCheckConflicts, disabled: isChecking }
      ] : []}
    >
      {isChecking ? (
        <div className="text-center py-4 text-blue-600">
          <span className="animate-pulse">Перевірка доступності...</span>
        </div>
      ) : !hasItems ? (
        <div className="text-center py-4 text-slate-400">
          Додайте товари для перевірки
        </div>
      ) : !hasDates ? (
        <div className="text-center py-4 text-slate-400">
          Вкажіть дати оренди
        </div>
      ) : hasConflicts ? (
        <div className="space-y-2">
          {conflicts.map((conflict, idx) => {
            const isExpanded = expandedConflicts.has(idx)
            const hasDetails = conflict.nearbyOrders && conflict.nearbyOrders.length > 0
            const hasPartialReturns = conflict.partialReturnWarnings && conflict.partialReturnWarnings.length > 0
            const hasProcessingWarnings = conflict.processingWarnings && conflict.processingWarnings.length > 0
            const isPartialReturnRisk = conflict.type === 'partial_return_risk'
            const isProcessingType = conflict.type === 'processing_rush' || conflict.type === 'on_processing'
            
            return (
              <div 
                key={idx}
                className={`rounded-lg border text-sm overflow-hidden ${
                  conflict.level === 'error' ? 'bg-rose-50 border-rose-200' : 
                  isPartialReturnRisk ? 'bg-orange-50 border-orange-300' :
                  isProcessingType ? 'bg-cyan-50 border-cyan-300' :
                  'bg-amber-50 border-amber-200'
                }`}
              >
                {/* Заголовок конфлікту */}
                <div 
                  className={`p-3 ${(hasDetails || hasPartialReturns || hasProcessingWarnings) ? 'cursor-pointer hover:bg-black/5' : ''}`}
                  onClick={() => (hasDetails || hasPartialReturns || hasProcessingWarnings) && toggleExpand(idx)}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1">
                      <div className="font-medium text-slate-800 flex items-center gap-2">
                        {conflict.sku} — {conflict.name}
                        {(hasDetails || hasPartialReturns || hasProcessingWarnings) && (
                          <span className="text-slate-400">
                            {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                          </span>
                        )}
                      </div>
                      <div className="text-xs mt-1 flex items-center gap-2 flex-wrap">
                        <TonePill tone={conflict.level === 'error' ? 'danger' : isPartialReturnRisk ? 'danger' : isProcessingType ? 'info' : 'warn'}>
                          {getConflictLabel(conflict.type)}
                        </TonePill>
                        {hasDetails && !isExpanded && (
                          <span className="text-slate-500">
                            ({conflict.nearbyOrders.length} замовлень)
                          </span>
                        )}
                        {hasPartialReturns && !isExpanded && (
                          <span className="text-orange-600 font-medium">
                            ({conflict.partialReturnQty} шт. ще у клієнта)
                          </span>
                        )}
                        {hasProcessingWarnings && !isExpanded && (
                          <span className="text-cyan-600 font-medium">
                            ({conflict.onProcessing} шт. на обробці)
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="text-right text-xs shrink-0">
                      <div>Доступно: <b className={conflict.available === 0 ? 'text-red-600' : ''}>{conflict.available || 0}</b></div>
                      {conflict.ready !== undefined && conflict.ready !== conflict.available && (
                        <div>Готово: <b className="text-emerald-600">{conflict.ready || 0}</b></div>
                      )}
                      {conflict.onProcessing > 0 && (
                        <div>На обробці: <b className="text-cyan-600">{conflict.onProcessing}</b></div>
                      )}
                      <div>Запитано: <b>{conflict.requested || 0}</b></div>
                    </div>
                  </div>
                </div>
                
                {/* ⚠️ НОВЕ: Деталі товарів на обробці */}
                {isExpanded && hasProcessingWarnings && (
                  <div className="border-t border-cyan-200 bg-cyan-50/50">
                    <div className="px-3 py-2 text-xs text-cyan-700 font-medium border-b border-cyan-200 flex items-center gap-1">
                      <Droplets className="h-3.5 w-3.5" />
                      Товари на обробці:
                    </div>
                    <div className="divide-y divide-cyan-100">
                      {conflict.processingWarnings.map((pw, pwIdx) => (
                        <div 
                          key={pwIdx} 
                          className="px-3 py-2 flex items-center justify-between gap-3 hover:bg-cyan-100/50"
                        >
                          <div className="flex items-center gap-2">
                            {getProcessingIcon(pw.type)}
                            <div>
                              <div className="font-medium text-slate-700">
                                {pw.qty} шт.
                              </div>
                              <div className="text-xs text-cyan-600">
                                {pw.type === 'on_wash' && 'На мийці/пранні/хімчистці'}
                                {pw.type === 'on_laundry' && 'На хімчистці/пранні'}
                                {pw.type === 'on_restoration' && 'На реставрації'}
                                {pw.type === 'awaiting_assignment' && 'Очікує розподілу'}
                                {pw.type === 'frozen' && 'Заморожено'}
                              </div>
                            </div>
                          </div>
                          <div className="text-right text-xs text-cyan-600 font-medium">
                            ⏰ Потрібно поторопитися!
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="px-3 py-2 bg-cyan-100/50 text-xs text-cyan-700 border-t border-cyan-200">
                      💡 <b>Увага:</b> Товар на обробці (мийка/прання/хімчистка/реставрація). 
                      Видача можлива, але потрібно терміново завершити обробку!
                    </div>
                  </div>
                )}
                
                {/* ⚠️ Деталі часткових повернень */}
                {isExpanded && hasPartialReturns && (
                  <div className="border-t border-orange-200 bg-orange-50/50">
                    <div className="px-3 py-2 text-xs text-orange-700 font-medium border-b border-orange-200 flex items-center gap-1">
                      <AlertTriangle className="h-3.5 w-3.5" />
                      Незавершені часткові повернення:
                    </div>
                    <div className="divide-y divide-orange-100">
                      {conflict.partialReturnWarnings.map((pr, prIdx) => (
                        <div 
                          key={prIdx} 
                          className="px-3 py-2 flex items-center justify-between gap-3 hover:bg-orange-100/50"
                        >
                          <div className="flex items-center gap-2">
                            <AlertTriangle className="h-4 w-4 text-orange-500" />
                            <div>
                              <div className="font-medium text-slate-700">
                                Замовлення #{pr.order_number || pr.order_id}
                              </div>
                              <div className="text-xs text-orange-600 font-medium">
                                {pr.qty} шт. • Прострочка {pr.days_overdue} днів
                              </div>
                            </div>
                          </div>
                          <div className="text-right text-xs">
                            <div className="text-slate-500">Мав повернути: {formatDate(pr.original_end_date)}</div>
                            <div className="text-orange-600 font-bold">
                              ⚠️ Дата повернення невідома!
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="px-3 py-2 bg-orange-100/50 text-xs text-orange-700 border-t border-orange-200">
                      💡 <b>Увага:</b> Товар числиться доступним, але фактично ще не повернувся від клієнта. 
                      Підтвердження замовлення несе ризик невиконання.
                    </div>
                  </div>
                )}
                
                {/* Деталі конфліктів - розгорнуті */}
                {isExpanded && hasDetails && (
                  <div className="border-t border-current/10 bg-white/50">
                    <div className="px-3 py-2 text-xs text-slate-500 font-medium border-b border-slate-100">
                      Конфліктуючі замовлення:
                    </div>
                    <div className="divide-y divide-slate-100">
                      {conflict.nearbyOrders.map((order, orderIdx) => (
                        <div 
                          key={orderIdx} 
                          className="px-3 py-2 flex items-center justify-between gap-3 hover:bg-slate-50"
                        >
                          <div className="flex items-center gap-2">
                            {getStatusIcon(order.status)}
                            <div>
                              <div className="font-medium text-slate-700">
                                Замовлення #{order.order_number || order.order_id}
                              </div>
                              <div className="text-xs text-slate-500">
                                {getStatusLabel(order.status)}
                                {order.quantity && order.quantity > 1 && (
                                  <span className="ml-1">• {order.quantity} шт.</span>
                                )}
                              </div>
                            </div>
                          </div>
                          <div className="text-right text-xs text-slate-500">
                            <div>{formatDate(order.rental_start_date)} — {formatDate(order.rental_end_date)}</div>
                            {order.days_gap !== null && order.days_gap !== undefined && order.days_gap >= 0 && order.days_gap <= 1 && (
                              <div className="text-amber-600 font-medium">
                                ⚠️ Тільки {order.days_gap} дн. до вашої оренди
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      ) : (
        <div className="text-center py-4 text-emerald-600">
          ✅ Всі товари доступні на вказані дати
        </div>
      )}
    </ZoneCard>
  )
}
