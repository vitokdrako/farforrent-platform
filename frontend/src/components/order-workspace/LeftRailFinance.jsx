/* eslint-disable */
import React, { useState, useEffect, useCallback, useRef } from 'react'
import TonePill from './TonePill'
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
 * LeftRailFinance - Фінансовий блок в лівій панелі
 * Читає РЕАЛЬНІ дані з фінансової системи
 * 
 * ОПТИМІЗОВАНО:
 * - Використовує новий endpoint /api/finance/deposit-hold?order_id={id} замість /api/finance/deposits
 * - Debounce для EventBus (300ms) щоб уникнути "шторму" рефетчів
 */
export default function LeftRailFinance({
  orderId,             // ID замовлення для завантаження реальних даних
  rentAmount = 0,      // Очікувана сума оренди (після знижки)
  depositAmount = 0,   // Очікувана сума застави (fallback)
  discountPercent = 0, // Відсоток знижки
  discountAmount = 0,  // Сума знижки
  rentBeforeDiscount = 0, // Сума оренди до знижки
  serviceFee = 0,      // Додаткова послуга (мінімальне замовлення)
  serviceFeeName = "", // Назва послуги
  onServiceFeeChange,  // Callback для зміни додаткової послуги
  isEditable = true,   // Завжди редагується
}) {
  const [loading, setLoading] = useState(true)
  const [payments, setPayments] = useState([])
  const [deposit, setDeposit] = useState(null)
  const [refreshKey, setRefreshKey] = useState(0)
  
  // Multiple additional services
  const [services, setServices] = useState([])
  const [showAddForm, setShowAddForm] = useState(false)
  const [newServiceName, setNewServiceName] = useState('')
  const [newServiceAmount, setNewServiceAmount] = useState('')
  const [savingService, setSavingService] = useState(null)
  
  // Ref для debounced функції
  const debouncedRefreshRef = useRef(null)

  // Функція завантаження даних - ОПТИМІЗОВАНА
  const fetchData = useCallback(() => {
    if (!orderId) {
      setLoading(false)
      return
    }

    setLoading(true)
    
    // ОПТИМІЗАЦІЯ P0.1: Використовуємо новий endpoint для одного депозиту
    Promise.all([
      authFetch(`${BACKEND_URL}/api/finance/payments?order_id=${orderId}`).then(r => r.json()),
      authFetch(`${BACKEND_URL}/api/finance/deposit-hold?order_id=${orderId}`).then(r => r.json()),
      authFetch(`${BACKEND_URL}/api/orders/${orderId}/additional-services`).then(r => r.json()).catch(() => [])
    ])
    .then(([paymentsData, depositData, servicesData]) => {
      setPayments(paymentsData.payments || [])
      setDeposit(depositData || null)
      setServices(Array.isArray(servicesData) ? servicesData : [])
      setLoading(false)
    })
    .catch(err => {
      console.error('Failed to load finance data:', err)
      setLoading(false)
    })
  }, [orderId])

  // Початкове завантаження
  useEffect(() => {
    fetchData()
  }, [fetchData, refreshKey])

  // ОПТИМІЗАЦІЯ P0.3: Debounced refresh для EventBus
  useEffect(() => {
    // Створюємо debounced функцію
    debouncedRefreshRef.current = debounce(() => {
      setRefreshKey(k => k + 1)
    }, 300)
    
    return () => {
      // Cleanup debounce при unmount
      if (debouncedRefreshRef.current?.cancel) {
        debouncedRefreshRef.current.cancel()
      }
    }
  }, [])

  // Підписка на події оновлення з DEBOUNCE
  useEffect(() => {
    const handleFinanceUpdate = (data) => {
      // Оновлюємо тільки якщо це наше замовлення або глобальне оновлення
      if (!data || !data.orderId || data.orderId === orderId) {
        // ОПТИМІЗАЦІЯ P0.3: Використовуємо debounced refresh
        if (debouncedRefreshRef.current) {
          debouncedRefreshRef.current()
        }
      }
    }

    const unsubFinance = eventBus.on(EVENTS.FINANCE_UPDATED, handleFinanceUpdate)
    const unsubPayment = eventBus.on(EVENTS.PAYMENT_CREATED, handleFinanceUpdate)
    const unsubDeposit = eventBus.on(EVENTS.DEPOSIT_CREATED, handleFinanceUpdate)
    const unsubRefund = eventBus.on(EVENTS.DEPOSIT_REFUNDED, handleFinanceUpdate)
    const unsubGlobal = eventBus.on(EVENTS.REFETCH_ALL, handleFinanceUpdate)

    return () => {
      unsubFinance()
      unsubPayment()
      unsubDeposit()
      unsubRefund()
      unsubGlobal()
    }
  }, [orderId])

  // Розрахунок реального статусу
  const rentPayments = payments.filter(p => p.payment_type === 'rent')
  const rentPaid = rentPayments.reduce((sum, p) => sum + (p.amount || 0), 0)
  
  // Фактична застава - ТІЛЬКИ якщо є запис у fin_deposit_holds
  const hasDeposit = deposit !== null && deposit !== undefined
  const depositHeld = hasDeposit ? (deposit.held_amount || 0) : 0
  const depositCurrency = hasDeposit ? (deposit.currency || 'UAH') : 'UAH'
  const depositActual = hasDeposit ? (deposit.actual_amount || depositHeld) : 0
  
  // Статуси
  const servicesTotal = services.reduce((s, sv) => s + (sv.amount || 0), 0)
  const totalWithServices = rentAmount + servicesTotal
  const rentStatus = rentPaid >= totalWithServices ? 'paid' : rentPaid > 0 ? 'partial' : 'pending'
  const depositStatus = hasDeposit && depositHeld > 0 ? 'received' : 'pending'
  
  // Загальний статус
  const isFullyPaid = rentStatus === 'paid' && depositStatus === 'received'
  const rentDue = Math.max(0, totalWithServices - rentPaid)
  
  // Форматування застави у валюті
  const depositDisplay = depositCurrency === 'UAH' 
    ? `₴ ${fmtUA(depositActual)}` 
    : `${depositActual} ${depositCurrency}`

  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="text-sm text-slate-500">⏳ Завантаження...</div>
      </div>
    )
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-slate-800">💰 Фінансовий статус</h3>
        <TonePill tone={isFullyPaid ? 'ok' : 'warn'}>
          {isFullyPaid ? '✅ Все оплачено' : rentDue > 0 ? `До сплати ₴${fmtUA(rentDue)}` : 'Очікується застава'}
        </TonePill>
      </div>
      
      <div className="space-y-3 text-sm">
        {/* Вартість ордеру */}
        <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
          <div className="flex items-center justify-between">
            <span className="text-slate-600">Вартість ордеру</span>
            <span className="font-semibold text-slate-800">₴ {fmtUA(rentBeforeDiscount || rentAmount)}</span>
          </div>
          
          {/* Знижка */}
          {(discountPercent > 0 || discountAmount > 0) && (
            <div className="mt-1 flex items-center justify-between text-xs">
              <span className="text-green-600">
                Знижка {discountPercent > 0 ? `${Math.round(discountPercent * 10) / 10}%` : ''}
              </span>
              <span className="text-green-600 font-medium">
                -₴ {fmtUA(discountAmount)}
              </span>
            </div>
          )}
          
          {/* До сплати (після знижки) */}
          <div className="mt-2 pt-2 border-t border-slate-200 flex items-center justify-between">
            <span className="text-slate-700 font-medium">До сплати</span>
            <span className="font-bold text-slate-900">₴ {fmtUA(rentAmount + servicesTotal)}</span>
          </div>
          
          <div className="mt-1 flex items-center justify-between">
            <span className="text-xs text-slate-500">
              {rentStatus === 'paid' && 'Оплачено'}
              {rentStatus === 'partial' && `Сплачено ₴${fmtUA(rentPaid)}`}
              {rentStatus === 'pending' && 'Не оплачено'}
            </span>
            {rentStatus === 'paid' && <TonePill tone="ok" size="sm">Оплачено</TonePill>}
            {rentStatus === 'partial' && <TonePill tone="warn" size="sm">Частково</TonePill>}
            {rentStatus === 'pending' && <TonePill tone="danger" size="sm">Не оплачено</TonePill>}
          </div>
        </div>
        
        {/* Застава */}
        <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
          <div className="flex items-center justify-between">
            <span className="text-slate-600">Застава</span>
            <span className="font-semibold text-slate-800">
              {depositStatus === 'received' ? depositDisplay : `₴ ${fmtUA(depositAmount)}`}
            </span>
          </div>
          <div className="mt-1 flex items-center justify-between">
            <span className="text-xs text-slate-500">
              {depositStatus === 'received' && '✅ Прийнято'}
              {depositStatus === 'pending' && depositAmount > 0 ? '⏳ Очікується' : '—'}
            </span>
            {depositStatus === 'received' && <TonePill tone="ok" size="sm">Прийнято</TonePill>}
            {depositStatus === 'pending' && depositAmount > 0 && <TonePill tone="warn" size="sm">Очікується</TonePill>}
          </div>
          {depositStatus === 'received' && depositCurrency !== 'UAH' && (
            <div className="mt-1 text-xs text-slate-400">≈ ₴ {fmtUA(depositHeld)}</div>
          )}
        </div>
        
        {/* Додаткові послуги (множинні) */}
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3" data-testid="additional-services-block">
          <div className="flex items-center justify-between mb-2">
            <span className="text-slate-600 text-sm font-medium">Додаткові послуги</span>
            {isEditable && (
              <button
                onClick={() => setShowAddForm(true)}
                className="text-xs text-amber-700 hover:text-amber-900 font-medium"
                data-testid="add-service-btn"
              >
                + Додати
              </button>
            )}
          </div>
          
          {/* Список послуг */}
          {services.length > 0 ? (
            <div className="space-y-1.5 mb-2">
              {services.map(svc => (
                <div key={svc.id} className="flex items-center justify-between bg-white rounded-lg px-2 py-1.5 border border-amber-100" data-testid={`service-${svc.id}`}>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-slate-700 truncate">{svc.name}</div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-semibold text-amber-700">₴{fmtUA(svc.amount)}</span>
                    {isEditable && (
                      <button
                        onClick={async () => {
                          if (!confirm(`Видалити "${svc.name}"?`)) return
                          setSavingService(svc.id)
                          try {
                            const token = localStorage.getItem('token')
                            await fetch(`${BACKEND_URL}/api/orders/${orderId}/additional-services/${svc.id}`, {
                              method: 'DELETE',
                              headers: { 'Authorization': `Bearer ${token}` }
                            })
                            setServices(prev => prev.filter(s => s.id !== svc.id))
                            if (onServiceFeeChange) onServiceFeeChange()
                          } catch (e) { console.error(e) }
                          finally { setSavingService(null) }
                        }}
                        disabled={savingService === svc.id}
                        className="p-0.5 text-slate-400 hover:text-red-500 transition-colors"
                        data-testid={`delete-service-${svc.id}`}
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                      </button>
                    )}
                  </div>
                </div>
              ))}
              <div className="text-xs text-amber-600 font-medium pt-1">
                Всього: ₴{fmtUA(services.reduce((sum, s) => sum + (s.amount || 0), 0))}
              </div>
            </div>
          ) : !showAddForm && (
            <div className="text-xs text-amber-600 mb-1">Немає додаткових послуг</div>
          )}
          
          {/* Форма додавання */}
          {showAddForm && (
            <div className="mt-2 space-y-2 bg-white p-2 rounded border border-amber-300" data-testid="add-service-form">
              <div>
                <label className="text-xs text-slate-500 block mb-1">Назва послуги</label>
                <input
                  type="text"
                  value={newServiceName}
                  onChange={(e) => setNewServiceName(e.target.value)}
                  placeholder="Напр. Мінімальне замовлення"
                  className="w-full px-2 py-1.5 text-sm border rounded focus:ring-1 focus:ring-amber-400 focus:border-amber-400"
                  autoFocus
                  data-testid="new-service-name"
                />
              </div>
              <div>
                <label className="text-xs text-slate-500 block mb-1">Сума (грн)</label>
                <input
                  type="number"
                  value={newServiceAmount}
                  onChange={(e) => setNewServiceAmount(e.target.value)}
                  className="w-full px-2 py-1.5 text-sm border rounded focus:ring-1 focus:ring-amber-400 focus:border-amber-400"
                  min="0"
                  step="100"
                  placeholder="0"
                  data-testid="new-service-amount"
                />
              </div>
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => { setShowAddForm(false); setNewServiceName(''); setNewServiceAmount(''); }}
                  className="px-3 py-1.5 text-xs bg-slate-200 text-slate-700 rounded hover:bg-slate-300"
                  data-testid="cancel-add-service"
                >
                  Скасувати
                </button>
                <button
                  onClick={async () => {
                    if (!newServiceName.trim() || !newServiceAmount || Number(newServiceAmount) <= 0) return
                    setSavingService('new')
                    try {
                      const token = localStorage.getItem('token')
                      const res = await fetch(`${BACKEND_URL}/api/orders/${orderId}/additional-services`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                        body: JSON.stringify({ name: newServiceName.trim(), amount: Number(newServiceAmount) })
                      })
                      if (res.ok) {
                        const data = await res.json()
                        setServices(prev => [...prev, { id: data.id, name: newServiceName.trim(), amount: Number(newServiceAmount) }])
                        setNewServiceName(''); setNewServiceAmount(''); setShowAddForm(false)
                        if (onServiceFeeChange) onServiceFeeChange()
                      }
                    } catch (e) { console.error(e) }
                    finally { setSavingService(null) }
                  }}
                  disabled={savingService === 'new' || !newServiceName.trim() || !newServiceAmount || Number(newServiceAmount) <= 0}
                  className="px-3 py-1.5 text-xs bg-green-500 text-white rounded hover:bg-green-600 disabled:opacity-50 font-medium"
                  data-testid="save-service-btn"
                >
                  {savingService === 'new' ? '...' : 'Зберегти'}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Загальний підсумок оренди */}
        {(serviceFee > 0 || services.length > 0) && (
          <div className="rounded-lg border-2 border-slate-300 bg-white p-3">
            <div className="flex items-center justify-between">
              <span className="text-slate-700 font-semibold text-sm">Разом до сплати</span>
              <span className="font-bold text-lg text-slate-900">₴ {fmtUA(totalWithServices)}</span>
            </div>
            {rentPaid > 0 && rentPaid < totalWithServices && (
              <div className="mt-1 flex items-center justify-between text-xs">
                <span className="text-amber-600">Залишок:</span>
                <span className="font-semibold text-amber-700">₴ {fmtUA(rentDue)}</span>
              </div>
            )}
          </div>
        )}

        {/* Деталі оплат */}
        {payments.length > 0 && (
          <details className="mt-2">
            <summary className="cursor-pointer text-xs font-medium text-slate-600 hover:text-slate-800">
              📋 Деталі оплат ({payments.length})
            </summary>
            <div className="mt-2 space-y-1 text-xs border-l-2 border-slate-200 pl-2">
              {payments.map((p, idx) => (
                <div key={idx} className="flex items-center justify-between py-1">
                  <div>
                    <span className="font-medium">{p.payment_type === 'rent' ? 'Оренда' : 'Застава'}</span>
                    {p.accepted_by_name && <span className="text-slate-400 ml-1">• {p.accepted_by_name}</span>}
                  </div>
                  <div className="font-mono text-slate-700">
                    {p.currency && p.currency !== 'UAH' ? `${p.amount} ${p.currency}` : `₴ ${fmtUA(p.amount)}`}
                  </div>
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  )
}
