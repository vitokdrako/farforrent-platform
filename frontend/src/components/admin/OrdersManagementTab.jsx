/* eslint-disable */
import React, { useState, useEffect, useMemo } from 'react'
import { ChevronUp, ChevronDown, Search, X, Pencil, Trash2, Plus, Check, Save, Banknote, Building2, RefreshCw, Shield, AlertTriangle, Clock } from 'lucide-react'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''
const authFetch = async (url, opts = {}) => {
  const token = localStorage.getItem('token')
  return fetch(url, { ...opts, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...opts.headers } })
}
const fmtUA = (n) => (Number(n) || 0).toLocaleString('uk-UA', { maximumFractionDigits: 0 })
const fmtDate = (d) => d ? new Date(d).toLocaleDateString('uk-UA', { day: '2-digit', month: '2-digit', year: '2-digit' }) : '—'

const STATUS_LABELS = {
  awaiting_customer: 'Очікує клієнта', processing: 'В обробці', ready_for_issue: 'Готовий',
  issued: 'Видано', returned: 'Повернено', partial_return: 'Частковий',
  completed: 'Завершений', cancelled: 'Скасований',
}
const STATUS_COLORS = {
  awaiting_customer: 'bg-gray-100 text-gray-600', processing: 'bg-blue-100 text-blue-700',
  ready_for_issue: 'bg-cyan-100 text-cyan-700', issued: 'bg-amber-100 text-amber-700',
  returned: 'bg-purple-100 text-purple-700', partial_return: 'bg-orange-100 text-orange-700',
  completed: 'bg-emerald-100 text-emerald-700', cancelled: 'bg-red-100 text-red-600',
}
const PAYMENT_TYPE_LABELS = { rent: 'Оренда', additional: 'Допослуга', deposit: 'Застава', damage: 'Збиток', late: 'Прострочення', deposit_refund: 'Повернення', loss: 'Втрата', discount: 'Знижка' }
const DEPOSIT_STATUS_LABELS = { held: 'Утримано', holding: 'Утримано', refunded: 'Повернено', partial: 'Частково', partially_used: 'Частково', fully_used: 'Використано', closed: 'Закрито' }

export default function OrdersManagementTab() {
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [sortKey, setSortKey] = useState('order_id')
  const [sortDir, setSortDir] = useState('desc')
  const [expandedId, setExpandedId] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [editData, setEditData] = useState({})
  const [payments, setPayments] = useState([])
  const [loadingPayments, setLoadingPayments] = useState(false)
  const [addPayment, setAddPayment] = useState(null)
  const [editPaymentId, setEditPaymentId] = useState(null)
  const [editPaymentData, setEditPaymentData] = useState({})
  const [editDeposit, setEditDeposit] = useState(null)
  const [recalculating, setRecalculating] = useState(null)
  const [toast, setToast] = useState(null)

  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 2500) }

  const load = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (search) params.set('search', search)
      if (statusFilter !== 'all') params.set('status', statusFilter)
      const res = await authFetch(`${BACKEND_URL}/api/admin/orders-management?${params}`)
      const data = await res.json()
      setOrders(data.orders || [])
    } catch (e) { console.error(e) }
    setLoading(false)
  }

  useEffect(() => { load() }, [statusFilter])

  const sorted = useMemo(() => {
    const arr = [...orders]
    arr.sort((a, b) => {
      let va = a[sortKey], vb = b[sortKey]
      if (va == null) va = ''; if (vb == null) vb = ''
      if (typeof va === 'number' && typeof vb === 'number') return sortDir === 'asc' ? va - vb : vb - va
      return sortDir === 'asc' ? String(va).localeCompare(String(vb), 'uk') : String(vb).localeCompare(String(va), 'uk')
    })
    return arr
  }, [orders, sortKey, sortDir])

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }
  const SortIcon = ({ col }) => {
    if (sortKey !== col) return <ChevronDown className="w-3 h-3 opacity-30" />
    return sortDir === 'asc' ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />
  }

  // Expand
  const toggleExpand = async (oid) => {
    if (expandedId === oid) { setExpandedId(null); return }
    setExpandedId(oid); setEditingId(null); setAddPayment(null); setEditPaymentId(null); setEditDeposit(null)
    setLoadingPayments(true)
    try {
      const res = await authFetch(`${BACKEND_URL}/api/admin/orders-management/${oid}/payments`)
      setPayments((await res.json()).payments || [])
    } catch { setPayments([]) }
    setLoadingPayments(false)
  }

  // Edit order
  const startEdit = (o) => {
    setEditingId(o.order_id)
    setEditData({ total_price: o.total_price, discount_percent: o.discount_percent, discount_amount: o.discount_amount, service_fee: o.service_fee, deposit_amount: o.deposit_amount, status: o.status })
  }
  const saveEdit = async (oid) => {
    try {
      await authFetch(`${BACKEND_URL}/api/admin/orders-management/${oid}`, { method: 'PUT', body: JSON.stringify(editData) })
      setEditingId(null); showToast('Збережено'); load()
    } catch { showToast('Помилка', 'error') }
  }

  // Payments
  const handleAddPayment = async (oid) => {
    if (!addPayment?.amount || addPayment.amount <= 0) return
    try {
      await authFetch(`${BACKEND_URL}/api/admin/orders-management/${oid}/payments`, { method: 'POST', body: JSON.stringify(addPayment) })
      setAddPayment(null); showToast('Платіж додано'); toggleExpand(oid); load()
    } catch { showToast('Помилка', 'error') }
  }
  const handleDeletePayment = async (oid, pid) => {
    if (!window.confirm('Видалити цей платіж?')) return
    try {
      await authFetch(`${BACKEND_URL}/api/admin/orders-management/${oid}/payments/${pid}`, { method: 'DELETE' })
      showToast('Видалено'); toggleExpand(oid); load()
    } catch { showToast('Помилка', 'error') }
  }
  const handleSavePayment = async (oid, pid) => {
    try {
      await authFetch(`${BACKEND_URL}/api/admin/orders-management/${oid}/payments/${pid}`, { method: 'PUT', body: JSON.stringify(editPaymentData) })
      setEditPaymentId(null); showToast('Оновлено'); toggleExpand(oid); load()
    } catch { showToast('Помилка', 'error') }
  }

  // Deposit
  const handleSaveDeposit = async (oid) => {
    try {
      await authFetch(`${BACKEND_URL}/api/admin/orders-management/${oid}/deposit`, { method: 'PUT', body: JSON.stringify(editDeposit) })
      setEditDeposit(null); showToast('Заставу оновлено'); load()
    } catch { showToast('Помилка', 'error') }
  }

  // Recalculate
  const handleRecalculate = async (oid) => {
    setRecalculating(oid)
    try {
      const res = await authFetch(`${BACKEND_URL}/api/admin/orders-management/${oid}/recalculate`, { method: 'POST' })
      const data = await res.json()
      showToast(`Перераховано: ₴${fmtUA(data.total_price)}, застава: ₴${fmtUA(data.deposit_amount)}`)
      load()
    } catch { showToast('Помилка', 'error') }
    setRecalculating(null)
  }

  const cols = [
    { key: 'order_number', label: '№', w: 'w-20' },
    { key: 'customer_name', label: 'Клієнт', w: 'w-32' },
    { key: 'manager_name', label: 'Менеджер', w: 'w-24' },
    { key: 'status', label: 'Статус', w: 'w-24' },
    { key: 'rental_start', label: 'Дати', w: 'w-20' },
    { key: 'total_price', label: 'Вартість', w: 'w-18' },
    { key: 'discount_amount', label: 'Знижка', w: 'w-14' },
    { key: 'total_to_pay', label: 'До сплати', w: 'w-18' },
    { key: 'paid_rent', label: 'Сплачено', w: 'w-18' },
    { key: 'debt', label: 'Борг', w: 'w-18' },
    { key: 'deposit_status', label: 'Застава', w: 'w-20' },
    { key: 'paid_late', label: 'Простр.', w: 'w-14' },
    { key: 'paid_damage', label: 'Шкода', w: 'w-14' },
    { key: 'is_event_manager_client', label: 'Тип', w: 'w-12' },
  ]

  return (
    <div data-testid="orders-management-tab">
      {toast && <div className={`fixed top-4 right-4 z-[999] px-4 py-3 rounded-xl text-white text-sm font-medium shadow-lg ${toast.type === 'error' ? 'bg-red-600' : 'bg-emerald-600'}`}>{toast.msg}</div>}

      <div className="flex items-center gap-3 mb-4">
        <form onSubmit={e => { e.preventDefault(); load() }} className="flex-1 flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Пошук по номеру, клієнту, телефону..."
              className="w-full pl-10 pr-8 py-2 text-sm border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500" data-testid="orders-search-input" />
            {search && <button type="button" onClick={() => { setSearch(''); setTimeout(load, 50) }} className="absolute right-2 top-1/2 -translate-y-1/2"><X className="w-4 h-4 text-slate-400" /></button>}
          </div>
          <button type="submit" className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700" data-testid="orders-search-btn">Знайти</button>
        </form>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="px-3 py-2 text-sm border border-slate-200 rounded-lg" data-testid="orders-status-filter">
          <option value="all">Всі статуси</option>
          {Object.entries(STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <div className="text-xs text-slate-500">{orders.length} замовлень</div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs" data-testid="orders-management-table">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                {cols.map(c => (
                  <th key={c.key} className={`px-2 py-2.5 text-left font-semibold text-slate-600 cursor-pointer hover:bg-slate-100 select-none whitespace-nowrap`}
                    onClick={() => toggleSort(c.key)} data-testid={`sort-${c.key}`}>
                    <div className="flex items-center gap-1">{c.label} <SortIcon col={c.key} /></div>
                  </th>
                ))}
                <th className="px-2 py-2.5 w-16"></th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={cols.length + 1} className="py-12 text-center text-slate-400">Завантаження...</td></tr>
              ) : sorted.length === 0 ? (
                <tr><td colSpan={cols.length + 1} className="py-12 text-center text-slate-400">Не знайдено</td></tr>
              ) : sorted.map(o => (
                <React.Fragment key={o.order_id}>
                  <tr className={`border-b border-slate-100 hover:bg-blue-50/30 cursor-pointer transition-colors ${expandedId === o.order_id ? 'bg-blue-50/50' : ''} ${o.debt > 0 ? 'bg-red-50/20' : ''}`}
                    onClick={() => toggleExpand(o.order_id)} data-testid={`order-row-${o.order_id}`}>
                    <td className="px-2 py-2 font-mono font-semibold text-blue-700">{o.order_number}</td>
                    <td className="px-2 py-2 truncate max-w-[130px]" title={o.customer_name}>{o.customer_name}</td>
                    <td className="px-2 py-2 truncate max-w-[100px] text-slate-600">{o.manager_name || '—'}</td>
                    <td className="px-2 py-2">
                      {editingId === o.order_id ? (
                        <select value={editData.status} onChange={e => setEditData(d => ({...d, status: e.target.value}))}
                          onClick={e => e.stopPropagation()} className="px-1 py-0.5 text-[10px] border rounded w-full">
                          {Object.entries(STATUS_LABELS).map(([k,v]) => <option key={k} value={k}>{v}</option>)}
                        </select>
                      ) : (
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${STATUS_COLORS[o.status] || 'bg-gray-100'}`}>
                          {STATUS_LABELS[o.status] || o.status}
                        </span>
                      )}
                    </td>
                    <td className="px-2 py-2 text-slate-600 whitespace-nowrap">{fmtDate(o.rental_start)}</td>
                    {editingId === o.order_id ? (
                      <>
                        <td className="px-1 py-1" onClick={e => e.stopPropagation()}>
                          <input type="number" value={editData.total_price} onChange={e => setEditData(d => ({...d, total_price: +e.target.value}))} className="w-full px-1 py-0.5 text-xs border rounded" />
                        </td>
                        <td className="px-1 py-1" onClick={e => e.stopPropagation()}>
                          <input type="number" value={editData.discount_amount} onChange={e => setEditData(d => ({...d, discount_amount: +e.target.value}))} className="w-full px-1 py-0.5 text-xs border rounded" />
                        </td>
                        <td className="px-2 py-2 font-semibold">₴{fmtUA(Math.max(0, (editData.total_price||0)-(editData.discount_amount||0)+(editData.service_fee||0)))}</td>
                      </>
                    ) : (
                      <>
                        <td className="px-2 py-2">₴{fmtUA(o.total_price)}</td>
                        <td className="px-2 py-2 text-slate-500">{o.discount_amount > 0 ? `-₴${fmtUA(o.discount_amount)}` : '—'}</td>
                        <td className="px-2 py-2 font-semibold">₴{fmtUA(o.total_to_pay)}</td>
                      </>
                    )}
                    <td className="px-2 py-2 text-emerald-600 font-medium">{o.paid_rent > 0 ? `₴${fmtUA(o.paid_rent)}` : '—'}</td>
                    <td className={`px-2 py-2 font-bold ${o.debt > 0 ? 'text-red-600' : 'text-emerald-600'}`}>{o.debt > 0 ? `₴${fmtUA(o.debt)}` : <Check className="w-3.5 h-3.5" />}</td>
                    <td className="px-2 py-2">
                      <span className={`px-1 py-0.5 rounded text-[10px] ${o.deposit_status === 'refunded' ? 'bg-emerald-100 text-emerald-700' : ['held','holding','partially_used'].includes(o.deposit_status) ? 'bg-amber-100 text-amber-700' : o.deposit_status === 'fully_used' ? 'bg-rose-100 text-rose-700' : 'bg-slate-100 text-slate-500'}`}>
                        {o.deposit_held > 0 ? `₴${fmtUA(o.deposit_held)}` : '—'} {DEPOSIT_STATUS_LABELS[o.deposit_status] || ''}
                      </span>
                    </td>
                    <td className="px-2 py-2">{o.paid_late > 0 ? <span className="text-orange-600 font-medium">₴{fmtUA(o.paid_late)}</span> : '—'}</td>
                    <td className="px-2 py-2">{o.paid_damage > 0 ? <span className="text-rose-600 font-medium">₴{fmtUA(o.paid_damage)}</span> : '—'}</td>
                    <td className="px-2 py-2">
                      <span className={`px-1 py-0.5 rounded text-[10px] font-medium ${o.is_event_manager_client ? 'bg-violet-100 text-violet-700' : 'bg-slate-100 text-slate-500'}`}>
                        {o.is_event_manager_client ? 'IM' : 'Прямий'}
                      </span>
                    </td>
                    <td className="px-2 py-2" onClick={e => e.stopPropagation()}>
                      {editingId === o.order_id ? (
                        <div className="flex gap-1">
                          <button onClick={() => saveEdit(o.order_id)} className="p-1 rounded bg-emerald-100 hover:bg-emerald-200 text-emerald-700"><Check className="w-3.5 h-3.5" /></button>
                          <button onClick={() => setEditingId(null)} className="p-1 rounded bg-slate-100 hover:bg-slate-200"><X className="w-3.5 h-3.5" /></button>
                        </div>
                      ) : (
                        <div className="flex gap-0.5">
                          <button onClick={() => startEdit(o)} className="p-1 rounded hover:bg-slate-100" title="Редагувати"><Pencil className="w-3.5 h-3.5 text-slate-400" /></button>
                          <button onClick={() => handleRecalculate(o.order_id)} disabled={recalculating === o.order_id}
                            className="p-1 rounded hover:bg-blue-100" title="Перерахувати з товарів">
                            <RefreshCw className={`w-3.5 h-3.5 text-blue-400 ${recalculating === o.order_id ? 'animate-spin' : ''}`} />
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>

                  {/* ── EXPANDED ROW ── */}
                  {expandedId === o.order_id && (
                    <tr><td colSpan={cols.length + 1} className="bg-slate-50 px-4 py-3">
                      <div className="grid grid-cols-3 gap-4">

                        {/* ── COL 1: Payments ── */}
                        <div className="col-span-2">
                          <div className="flex items-center justify-between mb-2">
                            <div className="text-xs font-semibold text-slate-700">Платежі — {o.order_number}</div>
                            <button onClick={() => setAddPayment({ payment_type: 'rent', method: 'cash', amount: o.debt > 0 ? o.debt : 0, note: '', occurred_at: new Date().toISOString().substring(0,10) })}
                              className="flex items-center gap-1 px-2 py-1 text-xs bg-emerald-600 text-white rounded hover:bg-emerald-700" data-testid={`add-payment-btn-${o.order_id}`}>
                              <Plus className="w-3 h-3" /> Додати
                            </button>
                          </div>
                          {loadingPayments ? <div className="text-xs text-slate-400 py-4 text-center">...</div> : (
                            <table className="w-full text-xs">
                              <thead><tr className="text-left text-slate-500 border-b border-slate-200">
                                <th className="pb-1 pr-2">Тип</th><th className="pb-1 pr-2">Метод</th><th className="pb-1 pr-2">Сума</th>
                                <th className="pb-1 pr-2">Дата</th><th className="pb-1 pr-2">Примітка</th><th className="pb-1 w-16"></th>
                              </tr></thead>
                              <tbody>
                                {payments.map(p => (
                                  editPaymentId === p.id ? (
                                    <tr key={p.id} className="border-t border-slate-200">
                                      <td className="py-1.5 pr-1"><select value={editPaymentData.payment_type ?? p.payment_type} onChange={e => setEditPaymentData(d => ({...d, payment_type: e.target.value}))} className="px-1 py-0.5 border rounded text-xs w-full">
                                        {Object.entries(PAYMENT_TYPE_LABELS).filter(([k]) => ['rent','additional','deposit','damage','late'].includes(k)).map(([k,v]) => <option key={k} value={k}>{v}</option>)}
                                      </select></td>
                                      <td className="py-1.5 pr-1"><select value={editPaymentData.method ?? p.method} onChange={e => setEditPaymentData(d => ({...d, method: e.target.value}))} className="px-1 py-0.5 border rounded text-xs w-full">
                                        <option value="cash">Готівка</option><option value="bank">Безготівка</option>
                                      </select></td>
                                      <td className="py-1.5 pr-1"><input type="number" value={editPaymentData.amount ?? p.amount} onChange={e => setEditPaymentData(d => ({...d, amount: +e.target.value}))} className="w-16 px-1 py-0.5 border rounded text-xs" /></td>
                                      <td className="py-1.5 pr-1"><input type="date" value={(editPaymentData.occurred_at ?? p.occurred_at ?? '').substring(0,10)} onChange={e => setEditPaymentData(d => ({...d, occurred_at: e.target.value}))} className="px-1 py-0.5 border rounded text-xs" /></td>
                                      <td className="py-1.5 pr-1"><input value={editPaymentData.note ?? (p.note||'')} onChange={e => setEditPaymentData(d => ({...d, note: e.target.value}))} className="w-full px-1 py-0.5 border rounded text-xs" /></td>
                                      <td className="py-1.5 flex gap-1">
                                        <button onClick={() => handleSavePayment(o.order_id, p.id)} className="p-1 bg-emerald-100 rounded hover:bg-emerald-200 text-emerald-700"><Check className="w-3 h-3" /></button>
                                        <button onClick={() => setEditPaymentId(null)} className="p-1 bg-slate-100 rounded hover:bg-slate-200"><X className="w-3 h-3" /></button>
                                      </td>
                                    </tr>
                                  ) : (
                                    <tr key={p.id} className="border-t border-slate-200 hover:bg-white">
                                      <td className="py-1.5 pr-2">
                                        <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                                          p.payment_type === 'rent' ? 'bg-blue-100 text-blue-700' :
                                          p.payment_type === 'deposit' ? 'bg-amber-100 text-amber-700' :
                                          p.payment_type === 'damage' ? 'bg-rose-100 text-rose-700' :
                                          p.payment_type === 'late' ? 'bg-orange-100 text-orange-700' :
                                          'bg-slate-100 text-slate-600'}`}>
                                          {PAYMENT_TYPE_LABELS[p.payment_type] || p.payment_type}
                                        </span>
                                      </td>
                                      <td className="py-1.5 pr-2 flex items-center gap-1">
                                        {p.method === 'cash' ? <Banknote className="w-3 h-3 text-green-600" /> : <Building2 className="w-3 h-3 text-blue-600" />}
                                        <span>{p.method === 'cash' ? 'Готівка' : 'Безготівка'}</span>
                                      </td>
                                      <td className="py-1.5 pr-2 font-semibold text-emerald-700">₴{fmtUA(p.amount)}</td>
                                      <td className="py-1.5 pr-2 text-slate-500">{fmtDate(p.occurred_at)}</td>
                                      <td className="py-1.5 pr-2 text-slate-500 truncate max-w-[160px]">{p.note || '—'}</td>
                                      <td className="py-1.5 flex gap-1">
                                        <button onClick={() => { setEditPaymentId(p.id); setEditPaymentData({}) }} className="p-1 rounded hover:bg-blue-100"><Pencil className="w-3 h-3 text-blue-500" /></button>
                                        <button onClick={() => handleDeletePayment(o.order_id, p.id)} className="p-1 rounded hover:bg-red-100"><Trash2 className="w-3 h-3 text-red-500" /></button>
                                      </td>
                                    </tr>
                                  )
                                ))}
                                {payments.length === 0 && !addPayment && <tr><td colSpan={6} className="py-3 text-center text-slate-400">Платежів немає</td></tr>}

                                {/* Add payment */}
                                {addPayment && (
                                  <tr className="border-t-2 border-emerald-200 bg-emerald-50/50">
                                    <td className="py-1.5 pr-1"><select value={addPayment.payment_type} onChange={e => setAddPayment(d => ({...d, payment_type: e.target.value}))} className="px-1 py-0.5 border rounded text-xs w-full">
                                      {Object.entries(PAYMENT_TYPE_LABELS).filter(([k]) => ['rent','additional','deposit','damage','late'].includes(k)).map(([k,v]) => <option key={k} value={k}>{v}</option>)}
                                    </select></td>
                                    <td className="py-1.5 pr-1"><select value={addPayment.method} onChange={e => setAddPayment(d => ({...d, method: e.target.value}))} className="px-1 py-0.5 border rounded text-xs w-full">
                                      <option value="cash">Готівка</option><option value="bank">Безготівка</option>
                                    </select></td>
                                    <td className="py-1.5 pr-1"><input type="number" value={addPayment.amount} onChange={e => setAddPayment(d => ({...d, amount: +e.target.value}))} className="w-16 px-1 py-0.5 border rounded text-xs" data-testid="new-payment-amount" /></td>
                                    <td className="py-1.5 pr-1"><input type="date" value={addPayment.occurred_at} onChange={e => setAddPayment(d => ({...d, occurred_at: e.target.value}))} className="px-1 py-0.5 border rounded text-xs" /></td>
                                    <td className="py-1.5 pr-1"><input value={addPayment.note} onChange={e => setAddPayment(d => ({...d, note: e.target.value}))} placeholder="Примітка" className="w-full px-1 py-0.5 border rounded text-xs" /></td>
                                    <td className="py-1.5 flex gap-1">
                                      <button onClick={() => handleAddPayment(o.order_id)} className="p-1 bg-emerald-600 rounded text-white hover:bg-emerald-700"><Check className="w-3 h-3" /></button>
                                      <button onClick={() => setAddPayment(null)} className="p-1 bg-slate-100 rounded hover:bg-slate-200"><X className="w-3 h-3" /></button>
                                    </td>
                                  </tr>
                                )}
                              </tbody>
                            </table>
                          )}
                        </div>

                        {/* ── COL 2: Deposit + Summary ── */}
                        <div className="space-y-3">
                          {/* Deposit card */}
                          <div className="bg-white rounded-lg p-3 border border-amber-200">
                            <div className="flex items-center justify-between mb-2">
                              <div className="text-xs font-semibold text-amber-700 flex items-center gap-1"><Shield className="w-3.5 h-3.5" /> Застава</div>
                              {!editDeposit && (
                                <button onClick={() => setEditDeposit({ status: o.deposit_status || 'held', held_amount: o.deposit_held, used_amount: o.deposit_used || 0, refunded_amount: o.deposit_refunded || 0, expected_amount: o.deposit_expected || o.deposit_amount, note: '' })}
                                  className="p-1 rounded hover:bg-amber-100"><Pencil className="w-3 h-3 text-amber-600" /></button>
                              )}
                            </div>
                            {editDeposit ? (
                              <div className="space-y-2">
                                <div className="grid grid-cols-2 gap-2">
                                  <div><label className="text-[10px] text-slate-500">Статус</label>
                                    <select value={editDeposit.status} onChange={e => setEditDeposit(d => ({...d, status: e.target.value}))} className="w-full px-1 py-1 text-xs border rounded">
                                      <option value="held">Утримано</option><option value="refunded">Повернено</option><option value="partial">Частково</option><option value="closed">Закрито</option>
                                    </select></div>
                                  <div><label className="text-[10px] text-slate-500">Утримано</label>
                                    <input type="number" value={editDeposit.held_amount} onChange={e => setEditDeposit(d => ({...d, held_amount: +e.target.value}))} className="w-full px-1 py-1 text-xs border rounded" /></div>
                                  <div><label className="text-[10px] text-slate-500">Використано</label>
                                    <input type="number" value={editDeposit.used_amount} onChange={e => setEditDeposit(d => ({...d, used_amount: +e.target.value}))} className="w-full px-1 py-1 text-xs border rounded" /></div>
                                  <div><label className="text-[10px] text-slate-500">Повернено</label>
                                    <input type="number" value={editDeposit.refunded_amount} onChange={e => setEditDeposit(d => ({...d, refunded_amount: +e.target.value}))} className="w-full px-1 py-1 text-xs border rounded" /></div>
                                </div>
                                <input value={editDeposit.note} onChange={e => setEditDeposit(d => ({...d, note: e.target.value}))} placeholder="Примітка" className="w-full px-1 py-1 text-xs border rounded" />
                                <div className="flex gap-2">
                                  <button onClick={() => handleSaveDeposit(o.order_id)} className="flex-1 py-1 text-xs bg-amber-600 text-white rounded hover:bg-amber-700">Зберегти</button>
                                  <button onClick={() => setEditDeposit(null)} className="px-3 py-1 text-xs bg-slate-100 rounded">Скасувати</button>
                                </div>
                              </div>
                            ) : (
                              <div className="space-y-1 text-xs">
                                <div className="flex justify-between"><span className="text-slate-500">Очікувана:</span><span>₴{fmtUA(o.deposit_expected || o.deposit_amount)}</span></div>
                                <div className="flex justify-between"><span className="text-slate-500">Утримано:</span><span className="font-semibold text-amber-700">₴{fmtUA(o.deposit_held)}</span></div>
                                {o.deposit_used > 0 && <div className="flex justify-between"><span className="text-slate-500">Використано:</span><span className="text-rose-600">₴{fmtUA(o.deposit_used)}</span></div>}
                                <div className="flex justify-between"><span className="text-slate-500">Повернено:</span><span className="text-emerald-600">₴{fmtUA(o.deposit_refunded)}</span></div>
                                <div className="flex justify-between"><span className="text-slate-500">Статус:</span>
                                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${o.deposit_status === 'refunded' ? 'bg-emerald-100 text-emerald-700' : ['held','holding','partially_used'].includes(o.deposit_status) ? 'bg-amber-100 text-amber-700' : o.deposit_status === 'fully_used' ? 'bg-rose-100 text-rose-700' : 'bg-slate-100 text-slate-600'}`}>
                                    {DEPOSIT_STATUS_LABELS[o.deposit_status] || o.deposit_status || '—'}
                                  </span></div>
                              </div>
                            )}
                          </div>

                          {/* Summary card */}
                          <div className="bg-white rounded-lg p-3 border border-slate-200 text-xs space-y-1">
                            <div className="flex justify-between"><span className="text-slate-500">Вартість:</span><span className="font-semibold">₴{fmtUA(o.total_price)}</span></div>
                            {o.discount_amount > 0 && <div className="flex justify-between"><span className="text-slate-500">Знижка ({o.discount_percent}%):</span><span className="text-orange-600">-₴{fmtUA(o.discount_amount)}</span></div>}
                            {o.service_fee > 0 && <div className="flex justify-between"><span className="text-slate-500">Послуга:</span><span>+₴{fmtUA(o.service_fee)}</span></div>}
                            <div className="flex justify-between border-t border-slate-100 pt-1"><span className="text-slate-700 font-medium">До сплати:</span><span className="font-bold">₴{fmtUA(o.total_to_pay)}</span></div>
                            <div className="flex justify-between"><span className="text-slate-500">Оренда:</span><span className="text-emerald-600">₴{fmtUA(o.paid_rent)}</span></div>
                            {o.paid_late > 0 && <div className="flex justify-between"><span className="text-slate-500 flex items-center gap-1"><Clock className="w-3 h-3" />Прострочення:</span><span className="text-orange-600">₴{fmtUA(o.paid_late)}</span></div>}
                            {o.paid_damage > 0 && <div className="flex justify-between"><span className="text-slate-500 flex items-center gap-1"><AlertTriangle className="w-3 h-3" />Шкода:</span><span className="text-rose-600">₴{fmtUA(o.paid_damage)}</span></div>}
                            {o.debt > 0 && <div className="flex justify-between border-t border-red-100 pt-1"><span className="text-red-600 font-medium">Борг:</span><span className="font-bold text-red-600">₴{fmtUA(o.debt)}</span></div>}
                          </div>
                        </div>
                      </div>
                    </td></tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
