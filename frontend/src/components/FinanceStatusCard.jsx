/* eslint-disable */
import React, { useState, useEffect } from 'react'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''

const cls = (...a) => a.filter(Boolean).join(' ')
const fmtUA = (n) => (Number(n) || 0).toLocaleString('uk-UA', { maximumFractionDigits: 2 })

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

/******************** Badge ********************/
function Badge({ tone = 'slate', children }) {
  const tones = {
    slate: 'bg-slate-100 text-slate-700 border-slate-200',
    green: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    amber: 'bg-amber-100 text-amber-800 border-amber-200',
    red: 'bg-rose-100 text-rose-700 border-rose-200',
    blue: 'bg-blue-100 text-blue-700 border-blue-200',
  }
  return <span className={cls('inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium', tones[tone])}>{children}</span>
}

/******************** FinanceStatusCard ********************/
export default function FinanceStatusCard({ orderId, expectedDeposit = 0, expectedRent = 0 }) {
  const [payments, setPayments] = useState([])
  const [deposit, setDeposit] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!orderId) return

    // Завантажити реальні дані з фінансової системи
    Promise.all([
      authFetch(`${BACKEND_URL}/api/finance/payments?order_id=${orderId}`).then(r => r.json()),
      authFetch(`${BACKEND_URL}/api/finance/deposits?status=holding,partially_used`).then(r => r.json())
    ])
    .then(([paymentsData, depositsData]) => {
      setPayments(paymentsData.payments || [])
      // Знайти депозит для цього замовлення
      const orderDeposit = (depositsData || []).find(d => d.order_id === orderId)
      setDeposit(orderDeposit || null)
      setLoading(false)
    })
    .catch(err => {
      console.error('Failed to load finance data:', err)
      setLoading(false)
    })
  }, [orderId])

  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="text-sm text-slate-500">⏳ Завантаження...</div>
      </div>
    )
  }

  // Розрахунок реального статусу з payments та deposit
  const rentPayments = payments.filter(p => p.payment_type === 'rent')
  const depositPayments = payments.filter(p => p.payment_type === 'deposit')
  
  const rentPaid = rentPayments.reduce((sum, p) => sum + (p.amount || 0), 0)
  const depositReceived = deposit?.held_amount || 0
  
  // Статуси
  const rentStatus = rentPaid > 0 ? 'paid' : expectedRent > 0 ? 'pending' : 'not_required'
  const depositStatus = depositReceived > 0 ? 'received' : expectedDeposit > 0 ? 'pending' : 'not_required'
  
  // Валюта застави
  const depositCurrency = deposit?.currency || 'UAH'
  const depositActual = deposit?.actual_amount || depositReceived
  const depositDisplay = depositCurrency === 'UAH' 
    ? `₴ ${fmtUA(depositActual)}` 
    : `${depositActual} ${depositCurrency}`

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-base font-semibold text-slate-800">💰 Фінансовий статус</h3>
      </div>

      <div className="space-y-3">
        {/* Оплата оренди */}
        <div className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50 p-3">
          <div>
            <div className="text-sm font-medium text-slate-700">Оренда</div>
            <div className="text-xs text-slate-500">
              {rentStatus === 'paid' && '✅ Оплачено'}
              {rentStatus === 'pending' && '⏳ Очікується'}
              {rentStatus === 'not_required' && '—'}
            </div>
          </div>
          <div className="text-right">
            <div className="text-lg font-bold text-slate-900">₴ {fmtUA(rentPaid || expectedRent)}</div>
            {rentStatus === 'paid' && <Badge tone="green">Оплачено</Badge>}
            {rentStatus === 'pending' && <Badge tone="red">Не оплачено</Badge>}
          </div>
        </div>

        {/* Застава */}
        <div className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50 p-3">
          <div>
            <div className="text-sm font-medium text-slate-700">Застава</div>
            <div className="text-xs text-slate-500">
              {depositStatus === 'received' && '✅ Прийнято'}
              {depositStatus === 'pending' && '⏳ Очікується'}
              {depositStatus === 'not_required' && '—'}
            </div>
          </div>
          <div className="text-right">
            <div className="text-lg font-bold text-slate-900">
              {depositStatus === 'received' ? depositDisplay : `₴ ${fmtUA(expectedDeposit)}`}
            </div>
            {depositStatus === 'received' && <Badge tone="green">Прийнято</Badge>}
            {depositStatus === 'pending' && <Badge tone="amber">Очікується</Badge>}
          </div>
        </div>

        {/* Хто прийняв */}
        {(rentPayments.length > 0 || depositPayments.length > 0) && (
          <details className="mt-2">
            <summary className="cursor-pointer text-xs font-medium text-slate-600 hover:text-slate-800">
              📋 Деталі оплат ({payments.length})
            </summary>
            <div className="mt-2 space-y-1 text-xs">
              {payments.map((p, idx) => (
                <div key={idx} className="flex items-center justify-between border-l-2 border-slate-200 pl-2 py-1">
                  <div>
                    <span className="font-medium">{p.payment_type === 'rent' ? 'Оренда' : 'Застава'}</span>
                    {p.accepted_by_name && <span className="text-slate-500 ml-1">• {p.accepted_by_name}</span>}
                  </div>
                  <div className="font-mono">₴ {fmtUA(p.amount)}</div>
                </div>
              ))}
            </div>
          </details>
        )}

        {/* Загальний статус */}
        <div className="mt-3 border-t border-slate-200 pt-3">
          {depositStatus === 'received' && rentStatus === 'paid' ? (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-xl">✅</span>
              <span className="font-medium text-green-700">Всі оплати отримано</span>
            </div>
          ) : depositStatus === 'received' && rentStatus === 'pending' ? (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-xl">⚠️</span>
              <span className="font-medium text-amber-700">Очікується оплата оренди</span>
            </div>
          ) : depositStatus === 'pending' && rentStatus === 'paid' ? (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-xl">⚠️</span>
              <span className="font-medium text-amber-700">Очікується застава</span>
            </div>
          ) : depositStatus === 'pending' && rentStatus === 'pending' ? (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-xl">⚠️</span>
              <span className="font-medium text-amber-700">Очікується оплата та застава</span>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
