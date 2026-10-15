/* eslint-disable */
/**
 * WarehouseTransfersPage — список переміщень між складами + модалка створення.
 *
 * Flow:
 *   draft (створено) → in_transit (ship) → received (receive)
 *                    ↓
 *                 cancelled
 */
import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import CorporateHeader from '../components/CorporateHeader'
import {
  ArrowLeftRight,
  Plus,
  Package,
  Send,
  CheckCircle2,
  XCircle,
  Clock,
  Truck,
  Trash2,
  X,
  Search,
} from 'lucide-react'

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

const FLAGS = { UA: '🇺🇦', PL: '🇵🇱', ES: '🇪🇸', DE: '🇩🇪', FR: '🇫🇷', IT: '🇮🇹', CZ: '🇨🇿' }

const STATUS_META = {
  draft:      { label: 'Чернетка',     color: 'bg-slate-100 text-slate-700', Icon: Clock },
  in_transit: { label: 'В дорозі',     color: 'bg-amber-100 text-amber-700', Icon: Truck },
  received:   { label: 'Прийнято',     color: 'bg-emerald-100 text-emerald-700', Icon: CheckCircle2 },
  cancelled:  { label: 'Скасовано',    color: 'bg-rose-100 text-rose-700', Icon: XCircle },
}

const formatDateTime = (iso) => {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('uk-UA', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}


export default function WarehouseTransfersPage() {
  const navigate = useNavigate()
  const [list, setList] = useState([])
  const [warehouses, setWarehouses] = useState([])
  const [loading, setLoading] = useState(true)
  const [filterStatus, setFilterStatus] = useState('')
  const [filterWh, setFilterWh] = useState('')
  const [modal, setModal] = useState(null) // null | 'new' | transfer
  const [actioning, setActioning] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (filterStatus) params.set('status', filterStatus)
      if (filterWh) params.set('warehouse_id', filterWh)
      const [tRes, wRes] = await Promise.all([
        authFetch(`${BACKEND_URL}/api/admin/warehouse-transfers?${params}`),
        authFetch(`${BACKEND_URL}/api/admin/warehouses?include_inactive=true`),
      ])
      if (tRes.ok) setList(await tRes.json())
      if (wRes.ok) setWarehouses(await wRes.json())
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [filterStatus, filterWh])

  const doAction = async (transferId, action) => {
    const confirmMap = {
      ship: 'Відвантажити товари зі складу? Запаси будуть одразу списано.',
      receive: 'Підтвердити отримання товарів на склад?',
      cancel: 'Скасувати цю чернетку переміщення?',
      delete: 'Видалити цю чернетку? Відновити не можна.',
    }
    if (!window.confirm(confirmMap[action])) return
    setActioning(true)
    try {
      const method = action === 'delete' ? 'DELETE' : 'POST'
      const url = action === 'delete'
        ? `${BACKEND_URL}/api/admin/warehouse-transfers/${transferId}`
        : `${BACKEND_URL}/api/admin/warehouse-transfers/${transferId}/${action}`
      const res = await authFetch(url, { method })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Помилка' }))
        alert(err.detail || 'Не вдалось виконати дію')
        return
      }
      await load()
      // if we were viewing details, close/reload modal
      if (modal && typeof modal === 'object' && modal.id === transferId) {
        if (action === 'delete') setModal(null)
        else {
          const fresh = await authFetch(`${BACKEND_URL}/api/admin/warehouse-transfers/${transferId}`).then(r => r.json())
          setModal(fresh)
        }
      }
    } finally {
      setActioning(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <CorporateHeader />
      <div className="max-w-7xl mx-auto px-6 py-10">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <ArrowLeftRight className="w-7 h-7 text-indigo-600" />
            <div>
              <h1 className="text-2xl font-bold text-slate-900">Переміщення між складами</h1>
              <p className="text-sm text-slate-500">Створюйте, відправляйте та приймайте товари між складами</p>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => navigate('/admin/warehouses')}
              className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900"
              data-testid="back-to-warehouses-btn"
            >
              ← До складів
            </button>
            <button
              onClick={() => setModal('new')}
              className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 shadow"
              data-testid="new-transfer-btn"
            >
              <Plus className="w-4 h-4" /> Нове переміщення
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-xl shadow-sm p-4 mb-6 flex gap-3 flex-wrap">
          <div>
            <label className="text-xs text-slate-500 block mb-1">Статус</label>
            <select
              value={filterStatus}
              onChange={e => setFilterStatus(e.target.value)}
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm"
              data-testid="filter-status-select"
            >
              <option value="">Усі статуси</option>
              <option value="draft">Чернетка</option>
              <option value="in_transit">В дорозі</option>
              <option value="received">Прийнято</option>
              <option value="cancelled">Скасовано</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-500 block mb-1">Склад (від або до)</label>
            <select
              value={filterWh}
              onChange={e => setFilterWh(e.target.value)}
              className="px-3 py-2 border border-slate-300 rounded-lg text-sm"
              data-testid="filter-warehouse-select"
            >
              <option value="">Усі склади</option>
              {warehouses.map(w => (
                <option key={w.id} value={w.id}>{FLAGS[w.country] || '📦'} {w.code} — {w.name}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Transfer list */}
        {loading ? (
          <div className="text-center py-12 text-slate-500">Завантаження...</div>
        ) : list.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm p-12 text-center text-slate-500">
            <Package className="w-12 h-12 mx-auto mb-3 opacity-40" />
            <p>Поки що немає переміщень. Створіть перше натисканням кнопки «Нове переміщення».</p>
          </div>
        ) : (
          <div className="bg-white rounded-xl shadow-sm overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3 text-left">№</th>
                  <th className="px-4 py-3 text-left">Маршрут</th>
                  <th className="px-4 py-3 text-left">Статус</th>
                  <th className="px-4 py-3 text-right">Позицій</th>
                  <th className="px-4 py-3 text-right">Всього шт</th>
                  <th className="px-4 py-3 text-left">Створено</th>
                  <th className="px-4 py-3 text-right">Дія</th>
                </tr>
              </thead>
              <tbody>
                {list.map(t => {
                  const meta = STATUS_META[t.status] || STATUS_META.draft
                  const Icon = meta.Icon
                  return (
                    <tr
                      key={t.id}
                      className="border-t hover:bg-slate-50 cursor-pointer"
                      onClick={async () => {
                        const fresh = await authFetch(`${BACKEND_URL}/api/admin/warehouse-transfers/${t.id}`).then(r => r.json())
                        setModal(fresh)
                      }}
                      data-testid={`transfer-row-${t.id}`}
                    >
                      <td className="px-4 py-3 font-mono text-sm">{t.transfer_number}</td>
                      <td className="px-4 py-3 text-sm">
                        <span className="inline-flex items-center gap-1">
                          <span>{FLAGS[t.from_warehouse?.name?.slice(0, 2)] || '📦'}</span>
                          <span className="font-medium">{t.from_warehouse?.code}</span>
                          <ArrowLeftRight className="w-3 h-3 mx-1 text-slate-400" />
                          <span className="font-medium">{t.to_warehouse?.code}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${meta.color}`}>
                          <Icon className="w-3 h-3" /> {meta.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right text-sm">{t.item_count}</td>
                      <td className="px-4 py-3 text-right text-sm font-semibold">{t.total_quantity}</td>
                      <td className="px-4 py-3 text-sm text-slate-600">{formatDateTime(t.created_at)}</td>
                      <td className="px-4 py-3 text-right text-sm">
                        <span className="text-xs text-slate-400">Деталі →</span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {modal === 'new' && (
        <NewTransferModal
          warehouses={warehouses}
          onClose={() => setModal(null)}
          onCreated={async (newT) => {
            await load()
            setModal(newT)
          }}
        />
      )}

      {modal && typeof modal === 'object' && (
        <TransferDetailsModal
          transfer={modal}
          onClose={() => setModal(null)}
          onAction={doAction}
          actioning={actioning}
        />
      )}
    </div>
  )
}


function NewTransferModal({ warehouses, onClose, onCreated }) {
  const [fromWh, setFromWh] = useState('')
  const [toWh, setToWh] = useState('')
  const [note, setNote] = useState('')
  const [items, setItems] = useState([]) // {product_id, sku, name, quantity}
  const [productSearch, setProductSearch] = useState('')
  const [products, setProducts] = useState([])
  const [searching, setSearching] = useState(false)
  const [saving, setSaving] = useState(false)

  // Search products on from_warehouse
  useEffect(() => {
    if (!productSearch || productSearch.length < 2 || !fromWh) {
      setProducts([])
      return
    }
    const t = setTimeout(async () => {
      setSearching(true)
      try {
        const res = await authFetch(
          `${BACKEND_URL}/api/products/search?q=${encodeURIComponent(productSearch)}&limit=15&warehouse_id=${fromWh}`
        )
        if (res.ok) {
          const data = await res.json()
          setProducts(Array.isArray(data) ? data : (data.products || data.items || []))
        } else {
          // Fallback: use catalog search without warehouse filter
          const r2 = await authFetch(`${BACKEND_URL}/api/catalog/search?q=${encodeURIComponent(productSearch)}&limit=15`)
          if (r2.ok) {
            const d2 = await r2.json()
            setProducts(Array.isArray(d2) ? d2 : (d2.products || d2.items || []))
          }
        }
      } finally {
        setSearching(false)
      }
    }, 350)
    return () => clearTimeout(t)
  }, [productSearch, fromWh])

  const addItem = (p) => {
    if (items.find(i => i.product_id === p.product_id)) return
    setItems([...items, { product_id: p.product_id, sku: p.sku, name: p.name, image_url: p.image_url, quantity: 1 }])
    setProductSearch('')
    setProducts([])
  }

  const updateQty = (pid, qty) => {
    setItems(items.map(i => i.product_id === pid ? { ...i, quantity: Math.max(1, parseInt(qty) || 1) } : i))
  }

  const removeItem = (pid) => setItems(items.filter(i => i.product_id !== pid))

  const submit = async () => {
    if (!fromWh || !toWh) return alert('Оберіть обидва склади')
    if (fromWh === toWh) return alert('Склади мають відрізнятися')
    if (items.length === 0) return alert('Додайте хоча б один товар')
    setSaving(true)
    try {
      const res = await authFetch(`${BACKEND_URL}/api/admin/warehouse-transfers`, {
        method: 'POST',
        body: JSON.stringify({
          from_warehouse_id: parseInt(fromWh),
          to_warehouse_id: parseInt(toWh),
          note: note || null,
          items: items.map(i => ({ product_id: i.product_id, quantity: i.quantity, note: null })),
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Помилка' }))
        alert(err.detail || 'Не вдалось створити')
        return
      }
      const created = await res.json()
      onCreated(created)
    } finally {
      setSaving(false)
    }
  }

  const activeWarehouses = warehouses.filter(w => w.is_active)

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
        data-testid="new-transfer-modal"
      >
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-bold">Нове переміщення</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-900"><X className="w-5 h-5" /></button>
        </div>

        <div className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-slate-700 block mb-1">Зі складу</label>
              <select
                value={fromWh}
                onChange={e => { setFromWh(e.target.value); setItems([]) }}
                className="w-full px-3 py-2 border rounded-lg"
                data-testid="from-warehouse-select"
              >
                <option value="">— оберіть —</option>
                {activeWarehouses.map(w => (
                  <option key={w.id} value={w.id}>{FLAGS[w.country] || '📦'} {w.code} — {w.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 block mb-1">На склад</label>
              <select
                value={toWh}
                onChange={e => setToWh(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg"
                data-testid="to-warehouse-select"
              >
                <option value="">— оберіть —</option>
                {activeWarehouses.filter(w => String(w.id) !== fromWh).map(w => (
                  <option key={w.id} value={w.id}>{FLAGS[w.country] || '📦'} {w.code} — {w.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="text-sm font-medium text-slate-700 block mb-1">Коментар (опціонально)</label>
            <textarea
              value={note}
              onChange={e => setNote(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg text-sm"
              rows={2}
              placeholder="Напр.: Переброс до EU-філії на весільний сезон"
              data-testid="transfer-note-input"
            />
          </div>

          <div>
            <label className="text-sm font-medium text-slate-700 block mb-2">Товари</label>
            {!fromWh ? (
              <div className="text-sm text-slate-500 bg-slate-50 rounded p-3">
                Спочатку оберіть склад-джерело, щоб шукати товари на ньому.
              </div>
            ) : (
              <div className="relative">
                <div className="relative">
                  <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    type="text"
                    value={productSearch}
                    onChange={e => setProductSearch(e.target.value)}
                    placeholder="Пошук за SKU або назвою..."
                    className="w-full pl-10 pr-3 py-2 border rounded-lg text-sm"
                    data-testid="product-search-input"
                  />
                </div>
                {productSearch.length >= 2 && products.length > 0 && (
                  <div className="absolute z-10 top-full left-0 right-0 mt-1 bg-white border rounded-lg shadow-lg max-h-60 overflow-y-auto">
                    {products.map(p => (
                      <button
                        key={p.product_id}
                        type="button"
                        onClick={() => addItem(p)}
                        className="w-full text-left px-3 py-2 hover:bg-indigo-50 border-b last:border-0 flex items-center gap-2 text-sm"
                        data-testid={`product-option-${p.product_id}`}
                      >
                        <span className="font-mono text-xs text-slate-500 w-24 truncate">{p.sku}</span>
                        <span className="flex-1 truncate">{p.name}</span>
                      </button>
                    ))}
                  </div>
                )}
                {searching && <div className="text-xs text-slate-500 mt-1">Пошук...</div>}
              </div>
            )}

            {items.length > 0 && (
              <div className="mt-3 border rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-xs text-slate-500">
                    <tr>
                      <th className="px-3 py-2 text-left">SKU</th>
                      <th className="px-3 py-2 text-left">Назва</th>
                      <th className="px-3 py-2 w-28 text-right">Кількість</th>
                      <th className="px-3 py-2 w-10"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map(i => (
                      <tr key={i.product_id} className="border-t">
                        <td className="px-3 py-2 font-mono text-xs">{i.sku}</td>
                        <td className="px-3 py-2 truncate">{i.name}</td>
                        <td className="px-3 py-2">
                          <input
                            type="number"
                            min="1"
                            value={i.quantity}
                            onChange={e => updateQty(i.product_id, e.target.value)}
                            className="w-20 px-2 py-1 border rounded text-right"
                            data-testid={`item-qty-${i.product_id}`}
                          />
                        </td>
                        <td className="px-3 py-2 text-right">
                          <button onClick={() => removeItem(i.product_id)} className="text-slate-400 hover:text-rose-600">
                            <X className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        <div className="flex justify-end gap-3 px-6 py-4 border-t bg-slate-50">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-slate-600 hover:text-slate-900"
            data-testid="cancel-transfer-btn"
          >
            Скасувати
          </button>
          <button
            onClick={submit}
            disabled={saving || !fromWh || !toWh || items.length === 0}
            className="px-5 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 text-sm font-medium"
            data-testid="save-transfer-btn"
          >
            {saving ? 'Створюється...' : 'Створити чернетку'}
          </button>
        </div>
      </div>
    </div>
  )
}


function TransferDetailsModal({ transfer, onClose, onAction, actioning }) {
  const meta = STATUS_META[transfer.status] || STATUS_META.draft
  const Icon = meta.Icon
  const canShip = transfer.status === 'draft' && (transfer.items?.length || 0) > 0
  const canReceive = transfer.status === 'in_transit'
  const canCancel = transfer.status === 'draft'
  const canDelete = transfer.status === 'draft'

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
        data-testid="transfer-details-modal"
      >
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div>
            <h2 className="text-lg font-bold font-mono">{transfer.transfer_number}</h2>
            <div className="text-xs text-slate-500">
              {transfer.from_warehouse?.code} → {transfer.to_warehouse?.code} · створено {formatDateTime(transfer.created_at)}
            </div>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-900"><X className="w-5 h-5" /></button>
        </div>

        <div className="p-6 space-y-4">
          <div className="flex items-center gap-2">
            <span className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium ${meta.color}`}>
              <Icon className="w-4 h-4" /> {meta.label}
            </span>
            {transfer.shipped_at && <span className="text-xs text-slate-500">· відвантажено {formatDateTime(transfer.shipped_at)}</span>}
            {transfer.received_at && <span className="text-xs text-slate-500">· отримано {formatDateTime(transfer.received_at)}</span>}
            {transfer.cancelled_at && <span className="text-xs text-slate-500">· скасовано {formatDateTime(transfer.cancelled_at)}</span>}
          </div>

          {transfer.note && (
            <div className="bg-slate-50 rounded-lg p-3 text-sm">
              <div className="text-xs text-slate-500 mb-1">Коментар</div>
              {transfer.note}
            </div>
          )}

          <div>
            <h3 className="font-semibold text-slate-700 mb-2 text-sm">Товари ({transfer.items?.length || 0})</h3>
            <div className="border rounded-lg overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-xs text-slate-500">
                  <tr>
                    <th className="px-3 py-2 text-left">SKU</th>
                    <th className="px-3 py-2 text-left">Назва</th>
                    <th className="px-3 py-2 w-20 text-right">К-сть</th>
                  </tr>
                </thead>
                <tbody>
                  {(transfer.items || []).map(i => (
                    <tr key={i.id} className="border-t">
                      <td className="px-3 py-2 font-mono text-xs">{i.sku}</td>
                      <td className="px-3 py-2">{i.name}</td>
                      <td className="px-3 py-2 text-right font-semibold">{i.quantity}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="flex justify-between gap-3 px-6 py-4 border-t bg-slate-50">
          <div className="flex gap-2">
            {canDelete && (
              <button
                onClick={() => onAction(transfer.id, 'delete')}
                disabled={actioning}
                className="inline-flex items-center gap-1 px-3 py-2 text-sm text-rose-600 hover:bg-rose-50 rounded-lg"
                data-testid="delete-transfer-btn"
              >
                <Trash2 className="w-4 h-4" /> Видалити
              </button>
            )}
            {canCancel && (
              <button
                onClick={() => onAction(transfer.id, 'cancel')}
                disabled={actioning}
                className="inline-flex items-center gap-1 px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg"
                data-testid="cancel-transfer-action-btn"
              >
                <XCircle className="w-4 h-4" /> Скасувати
              </button>
            )}
          </div>
          <div className="flex gap-2">
            {canShip && (
              <button
                onClick={() => onAction(transfer.id, 'ship')}
                disabled={actioning}
                className="inline-flex items-center gap-2 px-4 py-2 bg-amber-500 text-white rounded-lg hover:bg-amber-600 text-sm font-medium disabled:opacity-50"
                data-testid="ship-transfer-btn"
              >
                <Send className="w-4 h-4" /> Відвантажити
              </button>
            )}
            {canReceive && (
              <button
                onClick={() => onAction(transfer.id, 'receive')}
                disabled={actioning}
                className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 text-sm font-medium disabled:opacity-50"
                data-testid="receive-transfer-btn"
              >
                <CheckCircle2 className="w-4 h-4" /> Прийняти
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
