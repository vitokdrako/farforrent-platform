/* eslint-disable */
import React, { useState, useEffect } from 'react'
import ZoneCard from '../ZoneCard'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''
const authFetch = (url, opts = {}) => {
  const token = localStorage.getItem('token')
  return fetch(url, { ...opts, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...opts.headers } })
}

const PACKAGING_ITEMS = [
  { key: 'bag_s', label: 'Сумка S' },
  { key: 'bag_m', label: 'Сумка M' },
  { key: 'bag_l', label: 'Сумка L' },
  { key: 'cover', label: 'Чохол' },
  { key: 'black_box', label: 'Чорний ящик' },
]

/**
 * ZonePackaging - Додаткове пакування
 * Замість чекліста перед видачею — облік тари
 */
export default function ZonePackaging({ orderId, readOnly = false }) {
  const [quantities, setQuantities] = useState({})
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  // Load existing data
  useEffect(() => {
    if (!orderId) return
    authFetch(`${BACKEND_URL}/api/orders/${orderId}/packaging`)
      .then(r => r.ok ? r.json() : {})
      .then(data => { if (data.quantities) setQuantities(data.quantities) })
      .catch(() => {})
  }, [orderId])

  const setQty = (key, val) => {
    const num = Math.max(0, parseInt(val) || 0)
    setQuantities(prev => ({ ...prev, [key]: num }))
    setSaved(false)
  }

  const increment = (key) => setQty(key, (quantities[key] || 0) + 1)
  const decrement = (key) => setQty(key, (quantities[key] || 0) - 1)

  const totalItems = Object.values(quantities).reduce((s, v) => s + (v || 0), 0)

  const save = async () => {
    if (!orderId) return
    setSaving(true)
    try {
      const res = await authFetch(`${BACKEND_URL}/api/orders/${orderId}/packaging`, {
        method: 'POST',
        body: JSON.stringify({ quantities })
      })
      if (res.ok) setSaved(true)
    } catch (e) { console.error(e) }
    finally { setSaving(false) }
  }

  const tone = totalItems > 0 ? 'ok' : 'info'

  return (
    <ZoneCard
      title="Додаткове пакування"
      hint="Тара та пакування видані з ордером"
      tone={tone}
      rightContent={
        <span className="text-sm text-slate-500">
          {totalItems} од.
        </span>
      }
    >
      <div className="space-y-2" data-testid="packaging-zone">
        {PACKAGING_ITEMS.map(item => {
          const qty = quantities[item.key] || 0
          return (
            <div key={item.key}
              className={`flex items-center gap-3 rounded-lg border p-2.5 transition-colors ${
                qty > 0 ? 'bg-emerald-50 border-emerald-200' : 'bg-white border-slate-200'
              }`}
              data-testid={`packaging-${item.key}`}
            >
              <span className="flex-1 text-sm text-slate-800 font-medium">{item.label}</span>
              
              {readOnly ? (
                <span className="text-sm font-bold text-slate-700 w-8 text-center">{qty}</span>
              ) : (
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => decrement(item.key)}
                    disabled={qty <= 0}
                    className="w-7 h-7 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-600 font-bold text-sm flex items-center justify-center disabled:opacity-30 transition-colors"
                    data-testid={`dec-${item.key}`}
                  >
                    -
                  </button>
                  <input
                    type="number"
                    value={qty}
                    onChange={e => setQty(item.key, e.target.value)}
                    className="w-10 h-7 text-center text-sm font-bold border border-slate-200 rounded-md focus:ring-1 focus:ring-emerald-400 focus:border-emerald-400"
                    min="0"
                    data-testid={`qty-${item.key}`}
                  />
                  <button
                    onClick={() => increment(item.key)}
                    className="w-7 h-7 rounded-md bg-emerald-100 hover:bg-emerald-200 text-emerald-700 font-bold text-sm flex items-center justify-center transition-colors"
                    data-testid={`inc-${item.key}`}
                  >
                    +
                  </button>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {!readOnly && (
        <button
          onClick={save}
          disabled={saving}
          className={`mt-3 w-full py-2 rounded-lg text-sm font-semibold transition-colors ${
            saved
              ? 'bg-emerald-100 text-emerald-700 border border-emerald-200'
              : 'bg-emerald-600 hover:bg-emerald-700 text-white'
          } disabled:opacity-50`}
          data-testid="save-packaging-btn"
        >
          {saving ? 'Зберігаю...' : saved ? 'Збережено' : 'Зберегти пакування'}
        </button>
      )}
    </ZoneCard>
  )
}
