/* eslint-disable */
/**
 * WarehouseStockEditor — редактор залишків товару по складах.
 * Монтується як вкладка на картці товару.
 *
 * Props:
 *   productId — ID товару (int)
 */
import React, { useState, useEffect } from 'react'
import { Package, Plus, X, Loader2 } from 'lucide-react'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''

const authFetch = (url, opts = {}) => {
  const token = localStorage.getItem('token')
  return fetch(url, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...opts.headers,
    },
  })
}

const FLAGS = { UA: '🇺🇦', PL: '🇵🇱', ES: '🇪🇸', DE: '🇩🇪', FR: '🇫🇷', IT: '🇮🇹' }

export default function WarehouseStockEditor({ productId }) {
  const [data, setData] = useState(null)
  const [allWarehouses, setAllWarehouses] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState({})
  const [addModal, setAddModal] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [stockRes, whRes] = await Promise.all([
        authFetch(`${BACKEND_URL}/api/admin/products/${productId}/stock`),
        authFetch(`${BACKEND_URL}/api/admin/warehouses`),
      ])
      if (stockRes.ok) setData(await stockRes.json())
      if (whRes.ok) setAllWarehouses(await whRes.json())
    } finally { setLoading(false) }
  }

  useEffect(() => { if (productId) load() }, [productId])

  if (loading || !data) {
    return (
      <div className="p-10 text-center text-slate-400" data-testid="stock-editor-loading">
        <Loader2 className="w-6 h-6 animate-spin inline" />
      </div>
    )
  }

  const assignedIds = new Set(data.warehouses.map(w => w.warehouse_id))
  const availableToAdd = allWarehouses.filter(w => !assignedIds.has(w.id) && w.is_active)

  const updateField = async (whId, field, value) => {
    setSaving(prev => ({ ...prev, [whId]: true }))
    try {
      const res = await authFetch(`${BACKEND_URL}/api/admin/products/${productId}/stock/${whId}`, {
        method: 'PUT',
        body: JSON.stringify({ [field]: value }),
      })
      if (res.ok) setData(await res.json())
    } finally { setSaving(prev => ({ ...prev, [whId]: false })) }
  }

  const removeFromWarehouse = async (whId) => {
    if (!window.confirm('Прибрати товар з цього складу? (залишок буде видалено)')) return
    const res = await authFetch(`${BACKEND_URL}/api/admin/products/${productId}/stock/${whId}`, {
      method: 'DELETE',
    })
    if (res.ok) load()
  }

  const addToWarehouse = async (whId) => {
    const res = await authFetch(`${BACKEND_URL}/api/admin/products/${productId}/stock/${whId}`, {
      method: 'PUT',
      body: JSON.stringify({ quantity: 0, is_available: true }),
    })
    if (res.ok) {
      setAddModal(false)
      load()
    }
  }

  return (
    <div className="space-y-4" data-testid="warehouse-stock-editor">
      {/* Header summary */}
      <div className="flex items-center justify-between bg-slate-50 rounded-lg p-3 border border-slate-200">
        <div className="flex items-center gap-3">
          <Package className="w-5 h-5 text-slate-600" />
          <div>
            <div className="text-sm font-semibold text-slate-800">
              Усього на {data.warehouses.length} складах
            </div>
            <div className="text-xs text-slate-500">
              <strong>{data.total_stock}</strong> шт · Доступно: <strong>{data.available_stock}</strong>
            </div>
          </div>
        </div>
        <div className="text-xs text-slate-400">
          Базова ціна: <strong className="text-slate-700 font-mono">{data.base_price} ₴</strong>
        </div>
      </div>

      {/* List of warehouse rows */}
      {data.warehouses.map(w => (
        <WarehouseRow
          key={w.warehouse_id}
          wh={w}
          saving={saving[w.warehouse_id]}
          basePrice={data.base_price}
          onUpdate={(field, value) => updateField(w.warehouse_id, field, value)}
          onRemove={() => removeFromWarehouse(w.warehouse_id)}
        />
      ))}

      {/* Add new warehouse */}
      {availableToAdd.length > 0 && (
        <button
          onClick={() => setAddModal(true)}
          className="w-full flex items-center justify-center gap-2 py-3 border-2 border-dashed border-slate-300 hover:border-sky-400 hover:bg-sky-50 rounded-lg text-slate-600 hover:text-sky-700 font-medium transition"
          data-testid="add-to-warehouse-btn"
        >
          <Plus className="w-4 h-4" />
          Додати на ще один склад
        </button>
      )}

      {addModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" data-testid="add-warehouse-modal">
          <div className="absolute inset-0 bg-black/40" onClick={() => setAddModal(false)} />
          <div className="relative bg-white rounded-2xl w-full max-w-md shadow-xl">
            <header className="flex items-center justify-between px-5 py-3 border-b bg-slate-50">
              <h3 className="font-bold">Виберіть склад</h3>
              <button onClick={() => setAddModal(false)} className="p-1.5 hover:bg-slate-100 rounded-lg"><X className="w-5 h-5" /></button>
            </header>
            <div className="p-5 space-y-2 max-h-[60vh] overflow-y-auto">
              {availableToAdd.map(w => (
                <button
                  key={w.id}
                  onClick={() => addToWarehouse(w.id)}
                  className="w-full flex items-center gap-3 p-3 rounded-lg border border-slate-200 hover:bg-sky-50 hover:border-sky-300 text-left"
                  data-testid={`add-wh-${w.code}`}
                >
                  <span className="text-2xl">{FLAGS[w.country] || '📦'}</span>
                  <div className="flex-1">
                    <div className="font-bold">{w.code} · {w.name}</div>
                    <div className="text-xs text-slate-500">{w.country} · {w.currency}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function WarehouseRow({ wh, saving, basePrice, onUpdate, onRemove }) {
  const [local, setLocal] = useState({
    quantity: wh.quantity,
    reserved_qty: wh.reserved_qty,
    min_quantity: wh.min_quantity,
    price_override: wh.price_override,
    cost_override: wh.cost_override,
    is_available: wh.is_available,
  })

  useEffect(() => {
    setLocal({
      quantity: wh.quantity,
      reserved_qty: wh.reserved_qty,
      min_quantity: wh.min_quantity,
      price_override: wh.price_override,
      cost_override: wh.cost_override,
      is_available: wh.is_available,
    })
  }, [wh])

  const commit = (field) => {
    if (local[field] !== wh[field]) {
      onUpdate(field, local[field])
    }
  }

  const [usePriceOverride, setUsePriceOverride] = useState(wh.price_override !== null)

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3" data-testid={`wh-row-${wh.code}`}>
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{FLAGS[wh.code?.slice(0, 2)] || '📦'}</span>
          <div>
            <div className="font-bold text-slate-800">{wh.code} · {wh.name}</div>
            <div className="text-xs text-slate-500">{wh.city || ''} · {wh.currency}</div>
          </div>
          {saving && <Loader2 className="w-4 h-4 animate-spin text-slate-400 ml-2" />}
        </div>
        <button
          onClick={onRemove}
          className="text-xs text-rose-500 hover:text-rose-700 hover:underline"
          data-testid={`remove-${wh.code}`}
        >
          Прибрати
        </button>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <NumField label="Залишок" value={local.quantity}
          onChange={v => setLocal(l => ({ ...l, quantity: v }))}
          onBlur={() => commit('quantity')}
          testid={`qty-${wh.code}`} />
        <NumField label="Броня" value={local.reserved_qty}
          onChange={v => setLocal(l => ({ ...l, reserved_qty: v }))}
          onBlur={() => commit('reserved_qty')}
          testid={`reserved-${wh.code}`} />
        <NumField label="Мін." value={local.min_quantity}
          onChange={v => setLocal(l => ({ ...l, min_quantity: v }))}
          onBlur={() => commit('min_quantity')}
          testid={`min-${wh.code}`} />
      </div>

      <div className="space-y-2 pt-2 border-t border-slate-100">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={usePriceOverride}
            onChange={e => {
              setUsePriceOverride(e.target.checked)
              if (!e.target.checked) onUpdate('price_override', null)
            }}
            data-testid={`use-price-override-${wh.code}`} />
          <span className="text-slate-700">Інша ціна для цього складу</span>
          <span className="text-slate-400 text-xs ml-auto">(стандартна: {basePrice} ₴)</span>
        </label>
        {usePriceOverride && (
          <div className="grid grid-cols-2 gap-3">
            <NumField label={`Ціна (${wh.currency})`} value={local.price_override || ''}
              step="0.01"
              onChange={v => setLocal(l => ({ ...l, price_override: v }))}
              onBlur={() => commit('price_override')}
              testid={`price-${wh.code}`} />
            <NumField label={`Собівартість (${wh.currency})`} value={local.cost_override || ''}
              step="0.01"
              onChange={v => setLocal(l => ({ ...l, cost_override: v }))}
              onBlur={() => commit('cost_override')}
              testid={`cost-${wh.code}`} />
          </div>
        )}
      </div>

      <label className="flex items-center gap-2 text-sm pt-2 border-t border-slate-100">
        <input type="checkbox" checked={local.is_available}
          onChange={e => { setLocal(l => ({ ...l, is_available: e.target.checked })); onUpdate('is_available', e.target.checked) }}
          data-testid={`available-${wh.code}`} />
        <span className="text-slate-700">Доступний на вітрині</span>
      </label>
    </div>
  )
}

function NumField({ label, value, onChange, onBlur, step = '1', testid }) {
  return (
    <label className="block">
      <span className="block text-xs font-medium text-slate-500 mb-1">{label}</span>
      <input
        type="number"
        step={step}
        value={value ?? ''}
        onChange={e => onChange(e.target.value === '' ? null : (step === '1' ? parseInt(e.target.value, 10) : parseFloat(e.target.value)))}
        onBlur={onBlur}
        className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-mono"
        data-testid={testid}
      />
    </label>
  )
}
