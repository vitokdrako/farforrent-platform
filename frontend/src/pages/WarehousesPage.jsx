/* eslint-disable */
/**
 * WarehousesPage — CRUD списку складів.
 * Доступ: super_admin.
 */
import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import CorporateHeader from '../components/CorporateHeader'
import { Plus, Edit3, Archive, X, Package, Users, ShoppingCart, ArrowLeftRight } from 'lucide-react'

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

const FLAGS = { UA: '🇺🇦', PL: '🇵🇱', ES: '🇪🇸', DE: '🇩🇪', FR: '🇫🇷' }
const COUNTRIES = [
  { code: 'UA', name: 'Україна' },
  { code: 'PL', name: 'Польща' },
  { code: 'ES', name: 'Іспанія' },
  { code: 'DE', name: 'Німеччина' },
  { code: 'FR', name: 'Франція' },
  { code: 'IT', name: 'Італія' },
  { code: 'CZ', name: 'Чехія' },
]
const CURRENCIES = ['UAH', 'EUR', 'USD', 'PLN']
const TIMEZONES = [
  'Europe/Kyiv', 'Europe/Warsaw', 'Europe/Madrid', 'Europe/Berlin',
  'Europe/Paris', 'Europe/Rome', 'Europe/Prague',
]

export default function WarehousesPage() {
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)
  const [modal, setModal] = useState(null) // null | 'new' | warehouse_obj

  const load = async () => {
    setLoading(true)
    try {
      const res = await authFetch(`${BACKEND_URL}/api/admin/warehouses?include_inactive=true`)
      if (res.ok) setList(await res.json())
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const handleArchive = async (w) => {
    if (!window.confirm(`Архівувати склад "${w.name}"?`)) return
    const res = await authFetch(`${BACKEND_URL}/api/admin/warehouses/${w.id}`, { method: 'DELETE' })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Помилка' }))
      alert(err.detail || 'Не вдалось архівувати')
      return
    }
    load()
  }

  return (
    <div className="min-h-screen bg-slate-50 font-montserrat" data-testid="warehouses-page">
      <CorporateHeader cabinetName="Склади" showBackButton />

      <main className="max-w-6xl mx-auto px-4 py-6">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-slate-800">Склади та філії</h1>
          <div className="flex gap-2">
            <Link
              to="/admin/warehouses/transfers"
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold shadow-sm"
              data-testid="open-transfers-btn"
            >
              <ArrowLeftRight className="w-4 h-4" /> Переміщення
            </Link>
            <button
              onClick={() => setModal('new')}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-700 text-white font-semibold shadow-sm"
              data-testid="new-warehouse-btn"
            >
              <Plus className="w-4 h-4" /> Новий склад
            </button>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-20 text-slate-400">Завантаження...</div>
        ) : (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr className="text-slate-600 text-xs uppercase tracking-wider">
                  <th className="px-4 py-3 text-left">Код</th>
                  <th className="px-4 py-3 text-left">Назва</th>
                  <th className="px-4 py-3 text-left">Країна/Місто</th>
                  <th className="px-4 py-3 text-left">Валюта</th>
                  <th className="px-4 py-3 text-center" title="Товари"><Package className="w-4 h-4 inline" /></th>
                  <th className="px-4 py-3 text-center" title="Замовлення"><ShoppingCart className="w-4 h-4 inline" /></th>
                  <th className="px-4 py-3 text-center" title="Клієнти"><Users className="w-4 h-4 inline" /></th>
                  <th className="px-4 py-3 text-center">Статус</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {list.map(w => (
                  <tr key={w.id} className={w.is_active ? '' : 'opacity-50'} data-testid={`warehouse-row-${w.code}`}>
                    <td className="px-4 py-3 font-mono text-base">
                      <span className="mr-1">{FLAGS[w.country] || '📦'}</span>
                      <span className="font-bold">{w.code}</span>
                      {w.is_default && (
                        <span className="ml-2 text-[10px] uppercase font-bold text-sky-600 bg-sky-100 px-1.5 py-0.5 rounded">default</span>
                      )}
                    </td>
                    <td className="px-4 py-3 font-medium">{w.name}</td>
                    <td className="px-4 py-3 text-slate-600">{w.country} · {w.city || '—'}</td>
                    <td className="px-4 py-3 font-mono">{w.currency}</td>
                    <td className="px-4 py-3 text-center font-semibold">{w.stats?.products || 0}</td>
                    <td className="px-4 py-3 text-center font-semibold">{w.stats?.orders || 0}</td>
                    <td className="px-4 py-3 text-center font-semibold">{w.stats?.clients || 0}</td>
                    <td className="px-4 py-3 text-center">
                      {w.is_active ? <span className="text-emerald-600">✅</span> : <span className="text-slate-400">🔴</span>}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button onClick={() => setModal(w)} className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-600" title="Редагувати" data-testid={`edit-${w.code}`}>
                          <Edit3 className="w-4 h-4" />
                        </button>
                        {w.is_active && !w.is_default && (
                          <button onClick={() => handleArchive(w)} className="p-1.5 hover:bg-rose-50 rounded-lg text-rose-600" title="Архівувати" data-testid={`archive-${w.code}`}>
                            <Archive className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {list.length === 0 && (
                  <tr><td colSpan="9" className="text-center py-10 text-slate-400">Складів ще немає</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </main>

      {modal && (
        <WarehouseModal
          data={modal === 'new' ? null : modal}
          onClose={() => setModal(null)}
          onSaved={() => { setModal(null); load() }}
        />
      )}
    </div>
  )
}

function WarehouseModal({ data, onClose, onSaved }) {
  const isNew = !data
  const [form, setForm] = useState(() => data ? { ...data } : {
    code: '', name: '', country: 'UA', city: '', address: '',
    currency: 'UAH', timezone: 'Europe/Kyiv', phone: '', email: '',
    is_default: false, is_active: true,
  })
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const submit = async () => {
    if (!form.code.trim() || !form.name.trim() || !form.country) {
      setErr('Заповни код, назву, країну')
      return
    }
    setSaving(true); setErr('')
    try {
      const url = isNew
        ? `${BACKEND_URL}/api/admin/warehouses`
        : `${BACKEND_URL}/api/admin/warehouses/${data.id}`
      const res = await authFetch(url, {
        method: isNew ? 'POST' : 'PUT',
        body: JSON.stringify(form),
      })
      if (!res.ok) {
        const e = await res.json().catch(() => ({ detail: 'Помилка' }))
        setErr(e.detail || 'Помилка збереження')
        return
      }
      onSaved()
    } finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" data-testid="warehouse-modal">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-2xl w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col shadow-xl">
        <header className="flex items-center justify-between px-5 py-3 border-b bg-slate-50">
          <h3 className="text-base font-bold">{isNew ? 'Новий склад' : `Редагувати ${data.code}`}</h3>
          <button onClick={onClose} className="p-1.5 hover:bg-slate-100 rounded-lg" data-testid="warehouse-modal-close">
            <X className="w-5 h-5" />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {err && <div className="p-3 rounded-lg bg-rose-50 text-rose-700 text-sm">{err}</div>}
          <div className="grid grid-cols-2 gap-3">
            <Field label="Код *">
              <input value={form.code} onChange={e => set('code', e.target.value.toUpperCase())}
                disabled={!isNew} placeholder="UA, EU, ES..."
                className="w-full rounded-lg border px-3 py-2 text-sm uppercase font-mono disabled:bg-slate-50"
                data-testid="wh-code" />
            </Field>
            <Field label="Назва *">
              <input value={form.name} onChange={e => set('name', e.target.value)}
                placeholder="Київ (основний)"
                className="w-full rounded-lg border px-3 py-2 text-sm" data-testid="wh-name" />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Країна *">
              <select value={form.country} onChange={e => set('country', e.target.value)}
                className="w-full rounded-lg border px-3 py-2 text-sm" data-testid="wh-country">
                {COUNTRIES.map(c => <option key={c.code} value={c.code}>{c.code} · {c.name}</option>)}
              </select>
            </Field>
            <Field label="Місто">
              <input value={form.city || ''} onChange={e => set('city', e.target.value)}
                className="w-full rounded-lg border px-3 py-2 text-sm" data-testid="wh-city" />
            </Field>
          </div>
          <Field label="Адреса">
            <input value={form.address || ''} onChange={e => set('address', e.target.value)}
              className="w-full rounded-lg border px-3 py-2 text-sm" data-testid="wh-address" />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Валюта *">
              <select value={form.currency} onChange={e => set('currency', e.target.value)}
                className="w-full rounded-lg border px-3 py-2 text-sm" data-testid="wh-currency">
                {CURRENCIES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </Field>
            <Field label="Часовий пояс">
              <select value={form.timezone} onChange={e => set('timezone', e.target.value)}
                className="w-full rounded-lg border px-3 py-2 text-sm" data-testid="wh-timezone">
                {TIMEZONES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Телефон">
              <input value={form.phone || ''} onChange={e => set('phone', e.target.value)}
                className="w-full rounded-lg border px-3 py-2 text-sm" data-testid="wh-phone" />
            </Field>
            <Field label="Email">
              <input value={form.email || ''} onChange={e => set('email', e.target.value)}
                className="w-full rounded-lg border px-3 py-2 text-sm" data-testid="wh-email" />
            </Field>
          </div>
          <div className="space-y-2">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={!!form.is_default} onChange={e => set('is_default', e.target.checked)} data-testid="wh-default" />
              <span>Склад за замовчуванням</span>
            </label>
            {!isNew && (
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={!!form.is_active} onChange={e => set('is_active', e.target.checked)} data-testid="wh-active" />
                <span>Активний</span>
              </label>
            )}
          </div>
        </div>
        <footer className="flex items-center justify-end gap-2 px-5 py-3 border-t bg-slate-50">
          <button onClick={onClose} className="px-4 py-2 rounded-lg text-sm text-slate-600 hover:bg-slate-100">
            Скасувати
          </button>
          <button onClick={submit} disabled={saving}
            className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-700 text-white text-sm font-semibold disabled:opacity-50"
            data-testid="wh-save">
            {saving ? 'Збереження...' : (isNew ? 'Створити' : 'Зберегти')}
          </button>
        </footer>
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="block text-xs font-medium text-slate-600 mb-1">{label}</span>
      {children}
    </label>
  )
}
