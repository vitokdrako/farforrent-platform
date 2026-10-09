/* eslint-disable */
import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import eventBus, { EVENTS } from '../../utils/eventBus'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''

// Auth fetch helper
const authFetch = (url) => {
  const token = localStorage.getItem('token');
  return fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
  });
};

const fmtUA = (n) => (Number(n) || 0).toLocaleString('uk-UA', { maximumFractionDigits: 0 })

// Debounce utility
const debounce = (fn, delay) => {
  let timeoutId;
  const debouncedFn = (...args) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn(...args), delay);
  };
  debouncedFn.cancel = () => clearTimeout(timeoutId);
  return debouncedFn;
};

/**
 * LeftRailTimeline - Таймлайн подій в лівій панелі
 * Завантажує реальні дані з фінансової системи
 * 
 * ОПТИМІЗАЦІЯ Phase 2:
 * - useMemo для dedupe та сортування events
 * - Debounce для EventBus (300ms)
 */
export default function LeftRailTimeline({
  orderId,            // ID замовлення для завантаження реальних даних
  events: externalEvents = [],  // Зовнішні події (fallback)
  maxVisible = 5,
}) {
  const [showAll, setShowAll] = useState(false)
  const [financeEvents, setFinanceEvents] = useState([])
  const [loading, setLoading] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  
  // Ref для debounced функції
  const debouncedRefreshRef = useRef(null)

  // Функція завантаження даних
  const fetchData = useCallback(() => {
    if (!orderId) return

    setLoading(true)
    
    // Завантажити реальні дані з фінансової системи та lifecycle
    Promise.all([
      authFetch(`${BACKEND_URL}/api/finance/payments?order_id=${orderId}`).then(r => r.json()),
      authFetch(`${BACKEND_URL}/api/orders/${orderId}/lifecycle`).then(r => r.json())
    ])
      .then(([paymentsData, lifecycleData]) => {
        const payments = paymentsData.payments || []
        const lifecycle = Array.isArray(lifecycleData) ? lifecycleData : []
        
        // Перетворити платежі в події
        const paymentEvents = payments.map(p => {
          const paymentTypes = {
            'rent': { text: 'Оплата оренди', tone: 'green', icon: '💵' },
            'deposit': { text: 'Прийом застави', tone: 'blue', icon: '🔒' },
            'damage': { text: 'Оплата шкоди', tone: 'amber', icon: '⚠️' },
            'refund': { text: 'Повернення застави', tone: 'slate', icon: '↩️' },
          }
          
          const typeInfo = paymentTypes[p.payment_type] || { text: 'Платіж', tone: 'slate', icon: '💰' }
          
          // Форматування суми
          const amountDisplay = p.currency && p.currency !== 'UAH' 
            ? `${p.amount} ${p.currency}` 
            : `₴ ${fmtUA(p.amount)}`
          
          return {
            id: `payment_${p.id}`,  // Унікальний ID для dedupe
            text: `${typeInfo.icon} ${typeInfo.text}: ${amountDisplay}`,
            at: p.occurred_at ? new Date(p.occurred_at).toLocaleString('uk-UA', { 
              day: '2-digit', 
              month: '2-digit', 
              hour: '2-digit', 
              minute: '2-digit' 
            }) : '',
            timestamp: p.occurred_at ? new Date(p.occurred_at).getTime() : 0,
            tone: typeInfo.tone,
            user: p.accepted_by_name || null,
          }
        })
        
        // Перетворити lifecycle в події
        const lifecycleStages = {
          'created': { text: 'Замовлення створено', tone: 'slate', icon: '📝' },
          'updated': { text: 'Замовлення оновлено', tone: 'slate', icon: '✏️' },
          'accepted': { text: 'Замовлення прийнято', tone: 'blue', icon: '✅' },
          'preparation': { text: 'Відправлено на збір', tone: 'amber', icon: '📦' },
          'ready_for_issue': { text: 'Готово до видачі', tone: 'green', icon: '✨' },
          'issued': { text: 'Видано клієнту', tone: 'green', icon: '🚀' },
          'on_rent': { text: 'На прокаті', tone: 'blue', icon: '🏠' },
          'returned': { text: 'Повернено', tone: 'green', icon: '↩️' },
          'completed': { text: 'Завершено', tone: 'green', icon: '🎉' },
          'cancelled': { text: 'Скасовано', tone: 'red', icon: '❌' },
          'cancelled_by_client': { text: 'Скасовано клієнтом', tone: 'red', icon: '❌' },
          'declined': { text: 'Відхилено', tone: 'red', icon: '⛔' },
          'archived': { text: 'Архівовано', tone: 'slate', icon: '📁' },
          'unarchived': { text: 'Розархівовано', tone: 'slate', icon: '📂' },
          'calendar_update': { text: 'Оновлено з календаря', tone: 'slate', icon: '📅' },
        }
        
        const lifecycleEvents = lifecycle.map(l => {
          const stageInfo = lifecycleStages[l.stage] || { text: l.stage, tone: 'slate', icon: '📌' }
          
          return {
            id: `lifecycle_${l.id}`,  // Унікальний ID для dedupe
            text: `${stageInfo.icon} ${stageInfo.text}`,
            at: l.created_at ? new Date(l.created_at).toLocaleString('uk-UA', { 
              day: '2-digit', 
              month: '2-digit', 
              hour: '2-digit', 
              minute: '2-digit' 
            }) : '',
            timestamp: l.created_at ? new Date(l.created_at).getTime() : 0,
            tone: stageInfo.tone,
            user: l.created_by_name || l.created_by || null,
            notes: l.notes || null,
          }
        })
        
        // Зберігаємо несортовані - сортування в useMemo
        setFinanceEvents([...paymentEvents, ...lifecycleEvents])
        setLoading(false)
      })
      .catch(err => {
        console.error('Failed to load events:', err)
        setLoading(false)
      })
  }, [orderId])

  // ОПТИМІЗАЦІЯ Phase 2: Debounce для EventBus
  useEffect(() => {
    debouncedRefreshRef.current = debounce(() => {
      setRefreshKey(k => k + 1)
    }, 300)
    
    return () => {
      if (debouncedRefreshRef.current?.cancel) {
        debouncedRefreshRef.current.cancel()
      }
    }
  }, [])

  // Початкове завантаження
  useEffect(() => {
    fetchData()
  }, [fetchData, refreshKey])

  // Підписка на події оновлення з DEBOUNCE
  useEffect(() => {
    const handleUpdate = (data) => {
      if (!data || !data.orderId || data.orderId === orderId) {
        if (debouncedRefreshRef.current) {
          debouncedRefreshRef.current()
        }
      }
    }

    const unsubFinance = eventBus.on(EVENTS.FINANCE_UPDATED, handleUpdate)
    const unsubPayment = eventBus.on(EVENTS.PAYMENT_CREATED, handleUpdate)
    const unsubDeposit = eventBus.on(EVENTS.DEPOSIT_CREATED, handleUpdate)
    const unsubOrder = eventBus.on(EVENTS.ORDER_UPDATED, handleUpdate)
    const unsubStatus = eventBus.on(EVENTS.ORDER_STATUS_CHANGED, handleUpdate)
    const unsubGlobal = eventBus.on(EVENTS.REFETCH_ALL, handleUpdate)

    return () => {
      unsubFinance()
      unsubPayment()
      unsubDeposit()
      unsubOrder()
      unsubStatus()
      unsubGlobal()
    }
  }, [orderId])

  // ОПТИМІЗАЦІЯ Phase 2: useMemo для dedupe та сортування
  const allEvents = useMemo(() => {
    const combined = [...financeEvents, ...externalEvents]
    
    // Dedupe по id (якщо є) або по text+timestamp
    const seen = new Set()
    const unique = combined.filter(event => {
      const key = event.id || `${event.text}_${event.timestamp}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    
    // Сортуємо за часом (найновіші зверху)
    return unique.sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0))
  }, [financeEvents, externalEvents])
  
  // ОПТИМІЗАЦІЯ Phase 2: useMemo для visible events
  const visibleEvents = useMemo(() => {
    return showAll ? allEvents : allEvents.slice(0, maxVisible)
  }, [allEvents, showAll, maxVisible])
  
  const hasMore = allEvents.length > maxVisible
  
  const toneColors = {
    green: 'bg-emerald-500',
    red: 'bg-rose-500',
    blue: 'bg-blue-500',
    amber: 'bg-amber-500',
    slate: 'bg-slate-400',
  }
  
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="font-semibold text-slate-800 mb-3">📋 Журнал операцій</h3>
      
      {loading ? (
        <div className="text-sm text-slate-400 text-center py-4">
          ⏳ Завантаження...
        </div>
      ) : allEvents.length === 0 ? (
        <div className="text-sm text-slate-400 text-center py-4">
          Немає записів
        </div>
      ) : (
        <>
          <ol className="space-y-3 text-sm max-h-60 overflow-auto">
            {visibleEvents.map((event, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <div 
                  className={`mt-1.5 h-2 w-2 rounded-full flex-shrink-0 ${toneColors[event.tone] || toneColors.slate}`} 
                />
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-slate-800">{event.text}</div>
                  <div className="text-xs text-slate-500 flex items-center gap-2 flex-wrap">
                    {event.at && <span>{event.at}</span>}
                    {event.user && <span className="text-slate-600">• {event.user}</span>}
                  </div>
                </div>
              </li>
            ))}
          </ol>
          
          {hasMore && (
            <button 
              onClick={() => setShowAll(!showAll)}
              className="mt-3 w-full text-sm text-blue-600 hover:text-blue-800 font-medium"
            >
              {showAll ? 'Згорнути' : `Показати ще ${allEvents.length - maxVisible}`}
            </button>
          )}
        </>
      )}
    </div>
  )
}
