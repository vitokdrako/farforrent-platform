/* eslint-disable */
import React, { useState, useEffect } from 'react'
import ZoneCard from '../ZoneCard'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''
const authFetch = (url, opts = {}) => {
  const token = localStorage.getItem('token')
  return fetch(url, { ...opts, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...opts.headers } })
}

const PACKAGING_ITEMS = [
  { key: 'bag_s', label: 'Сумка S', price: 150 },
  { key: 'bag_m', label: 'Сумка M', price: 200 },
  { key: 'bag_l', label: 'Сумка L', price: 300 },
  { key: 'cover', label: 'Чохол', price: 250 },
  { key: 'black_box', label: 'Чорний ящик', price: 500 },
]

/**
 * ZonePackagingReturn - Перевірка повернення тари
 * Показує що було видано і дозволяє відмітити що повернулось
 */
export default function ZonePackagingReturn({ orderId, onChargeChange, readOnly = false }) {
  const [issued, setIssued] = useState({})       // Що видали
  const [returned, setReturned] = useState({})    // Що повернули
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (!orderId) return
    // Load issued packaging
    authFetch(`${BACKEND_URL}/api/orders/${orderId}/packaging`)
      .then(r => r.ok ? r.json() : {})
      .then(data => {
        const qty = data.quantities || {}
        setIssued(qty)
        // Load returned quantities
        return authFetch(`${BACKEND_URL}/api/orders/${orderId}/packaging-return`)
      })
      .then(r => r.ok ? r.json() : {})
      .then(data => {
        if (data.returned) setReturned(data.returned)
      })
      .catch(() => {})
  }, [orderId])

  // Calculate charges whenever returned changes
  useEffect(() => {
    const charges = calculateCharges()
    if (onChargeChange) onChargeChange(charges.total, charges.items)
  }, [returned, issued])

  const setReturnedQty = (key, val) => {
    const max = issued[key] || 0
    const num = Math.max(0, Math.min(max, parseInt(val) || 0))
    setReturned(prev => ({ ...prev, [key]: num }))
    setSaved(false)
  }

  const calculateCharges = () => {
    let total = 0
    const items = []
    for (const item of PACKAGING_ITEMS) {
      const issuedQty = issued[item.key] || 0
      const returnedQty = returned[item.key] || 0
      const missing = issuedQty - returnedQty
      if (missing > 0) {
        const charge = missing * item.price
        total += charge
        items.push({ key: item.key, label: item.label, missing, price: item.price, charge })
      }
    }
    return { total, items }
  }

  const save = async () => {
    if (!orderId) return
    setSaving(true)
    try {
      const res = await authFetch(`${BACKEND_URL}/api/orders/${orderId}/packaging-return`, {
        method: 'POST',
        body: JSON.stringify({ returned })
      })
      if (res.ok) setSaved(true)
    } catch (e) { console.error(e) }
    finally { setSaving(false) }
  }

  const charges = calculateCharges()
  const hasIssued = Object.values(issued).some(v => v > 0)

  if (!hasIssued) return null // Не показувати якщо тари не видавали

  const tone = charges.total > 0 ? 'warn' : 'ok'

  return (
    <ZoneCard
      title="Повернення тари"
      hint="Перевірте чи повернулась вся тара"
      tone={tone}
      rightContent={
        charges.total > 0 
          ? <span className="text-sm font-bold text-red-600">Нестача: {charges.total} грн</span>
          : <span className="text-sm text-emerald-600 font-medium">Все повернуто</span>
      }
    >
      <div className="space-y-2" data-testid="packaging-return-zone">
        {PACKAGING_ITEMS.filter(item => (issued[item.key] || 0) > 0).map(item => {
          const issuedQty = issued[item.key] || 0
          const returnedQty = returned[item.key] || 0
          const missing = issuedQty - returnedQty
          const isComplete = returnedQty >= issuedQty

          return (
            <div key={item.key}
              className={`flex items-center gap-3 rounded-lg border p-2.5 transition-colors ${
                isComplete ? 'bg-emerald-50 border-emerald-200' : 
                missing > 0 ? 'bg-red-50 border-red-200' : 'bg-white border-slate-200'
              }`}
              data-testid={`return-pkg-${item.key}`}
            >
              <div className="flex-1 min-w-0">
                <span className="text-sm font-medium text-slate-800">{item.label}</span>
                <span className="text-xs text-slate-500 ml-2">Видано: {issuedQty}</span>
              </div>

              {readOnly ? (
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold">{returnedQty}/{issuedQty}</span>
                  {missing > 0 && <span className="text-xs text-red-600 font-medium">-{missing} ({missing * item.price} грн)</span>}
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setReturnedQty(item.key, returnedQty - 1)}
                      disabled={returnedQty <= 0}
                      className="w-7 h-7 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-600 font-bold text-sm flex items-center justify-center disabled:opacity-30"
                      data-testid={`ret-dec-${item.key}`}
                    >-</button>
                    <input
                      type="number"
                      value={returnedQty}
                      onChange={e => setReturnedQty(item.key, e.target.value)}
                      className="w-10 h-7 text-center text-sm font-bold border border-slate-200 rounded-md"
                      min="0"
                      max={issuedQty}
                      data-testid={`ret-qty-${item.key}`}
                    />
                    <button
                      onClick={() => setReturnedQty(item.key, returnedQty + 1)}
                      disabled={returnedQty >= issuedQty}
                      className="w-7 h-7 rounded-md bg-emerald-100 hover:bg-emerald-200 text-emerald-700 font-bold text-sm flex items-center justify-center disabled:opacity-30"
                      data-testid={`ret-inc-${item.key}`}
                    >+</button>
                  </div>
                  
                  {missing > 0 && (
                    <span className="text-xs text-red-600 font-semibold whitespace-nowrap">
                      -{missing} = {missing * item.price} грн
                    </span>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Підсумок нестачі */}
      {charges.total > 0 && (
        <div className="mt-3 p-2.5 rounded-lg bg-red-50 border border-red-200" data-testid="packaging-charges-summary">
          <div className="text-sm font-semibold text-red-700 mb-1">Нестача тари:</div>
          {charges.items.map(ch => (
            <div key={ch.key} className="flex justify-between text-xs text-red-600">
              <span>{ch.label} x {ch.missing}</span>
              <span>{ch.charge} грн</span>
            </div>
          ))}
          <div className="flex justify-between text-sm font-bold text-red-700 mt-1 pt-1 border-t border-red-200">
            <span>Всього до сплати:</span>
            <span>{charges.total} грн</span>
          </div>
        </div>
      )}

      {!readOnly && (
        <button
          onClick={save}
          disabled={saving}
          className={`mt-3 w-full py-2 rounded-lg text-sm font-semibold transition-colors ${
            saved ? 'bg-emerald-100 text-emerald-700 border border-emerald-200'
                  : 'bg-emerald-600 hover:bg-emerald-700 text-white'
          } disabled:opacity-50`}
          data-testid="save-packaging-return-btn"
        >
          {saving ? 'Зберігаю...' : saved ? 'Збережено' : 'Зберегти повернення тари'}
        </button>
      )}
    </ZoneCard>
  )
}
