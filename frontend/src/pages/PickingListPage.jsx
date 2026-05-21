/* eslint-disable */
/**
 * PickingListPage — глобальний лист комплектації.
 * Перемикач днів (◂ Сьогодні ▸ / Завтра / Вчора / dd.MMM)
 * + блок Awaiting + блок Preparation + блок Ready
 * Кожна картка: коментар клієнта (жовтий), нотатки реквізитора (сірий), товари по зонах з чекбоксами.
 */
import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import CorporateHeader from '../components/CorporateHeader'
import { getImageUrl, FALLBACK_IMAGE, handleImageError } from '../utils/imageHelper'
import { ChevronLeft, ChevronRight, Printer, Package, AlertTriangle, Phone, Clock, ArrowLeft, RefreshCw } from 'lucide-react'

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

const todayStr = () => new Date().toISOString().slice(0, 10)
const addDaysStr = (offset) => {
  const d = new Date()
  d.setDate(d.getDate() + offset)
  return d.toISOString().slice(0, 10)
}
const formatLabel = (offset) => {
  if (offset === 0) return 'Сьогодні'
  if (offset === 1) return 'Завтра'
  if (offset === -1) return 'Вчора'
  const d = new Date()
  d.setDate(d.getDate() + offset)
  return d.toLocaleDateString('uk-UA', { day: '2-digit', month: 'short', weekday: 'short' })
}

export default function PickingListPage() {
  const navigate = useNavigate()
  const [dayOffset, setDayOffset] = useState(0)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [checked, setChecked] = useState({}) // localStorage-backed { card_id: { product_id: true } }

  // Load checks once
  useEffect(() => {
    try { setChecked(JSON.parse(localStorage.getItem('picking_checks') || '{}')) }
    catch { setChecked({}) }
  }, [])

  // Persist checks
  useEffect(() => {
    localStorage.setItem('picking_checks', JSON.stringify(checked))
  }, [checked])

  const fetchData = async (offset) => {
    setLoading(true)
    try {
      const res = await authFetch(`${BACKEND_URL}/api/manager/picking-list?date=${addDaysStr(offset)}&include_awaiting=true`)
      if (res.ok) setData(await res.json())
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchData(dayOffset) }, [dayOffset])

  const toggleCheck = (cardId, productId) => {
    setChecked(prev => {
      const cardChecks = { ...(prev[cardId] || {}) }
      cardChecks[productId] = !cardChecks[productId]
      return { ...prev, [cardId]: cardChecks }
    })
  }

  const cardProgress = (card) => {
    const c = checked[card.id] || checked[`o-${card.order_id}`] || {}
    let done = 0, total = 0
    card.zones.forEach(z => z.items.forEach(it => {
      total += 1
      if (c[it.product_id]) done += 1
    }))
    return { done, total }
  }

  const summary = data?.summary || {}

  return (
    <div className="min-h-screen bg-corp-bg-page font-montserrat" data-testid="picking-list-page">
      <CorporateHeader cabinetName="Лист комплектації" />

      {/* Toolbar */}
      <div className="bg-white border-b border-corp-border sticky top-0 z-20 print:hidden">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center gap-3">
          <button onClick={() => navigate('/manager')}
            className="p-2 rounded-lg hover:bg-slate-100 text-slate-600" data-testid="back-btn">
            <ArrowLeft className="w-4 h-4" />
          </button>

          {/* Day picker */}
          <div className="flex items-center bg-slate-100 rounded-lg p-1" data-testid="day-picker">
            <button onClick={() => setDayOffset(o => o - 1)} title="День назад"
              className="px-2 py-1.5 rounded-md text-slate-500 hover:bg-slate-200 transition"
              data-testid="day-prev-btn">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button onClick={() => setDayOffset(0)}
              className={`px-3 py-1.5 text-sm font-medium transition rounded-md whitespace-nowrap ${
                dayOffset === 0 ? 'bg-corp-primary text-white shadow-sm' : 'bg-white text-slate-700 hover:bg-slate-50'
              }`}
              data-testid="day-label-btn">
              {formatLabel(dayOffset)}
            </button>
            <button onClick={() => setDayOffset(o => o + 1)} title="День вперед"
              className="px-2 py-1.5 rounded-md text-slate-500 hover:bg-slate-200 transition"
              data-testid="day-next-btn">
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          {/* Summary pills */}
          {data && !loading && (
            <div className="flex items-center gap-3 text-xs">
              <Pill label="Очікують" value={summary.awaiting_count} color="amber" />
              <Pill label="Комплектація" value={summary.preparation_count} color="blue" />
              <Pill label="Готові" value={summary.ready_count} color="emerald" />
              <span className="h-5 w-px bg-slate-200" />
              <Pill label="Позицій збирати" value={summary.total_items_to_pick} color="slate" bold />
            </div>
          )}

          <div className="ml-auto flex items-center gap-2">
            <button onClick={() => fetchData(dayOffset)} disabled={loading}
              className="p-2 rounded-lg border border-slate-200 hover:bg-slate-50" data-testid="refresh-btn">
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <button onClick={() => window.print()}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold" data-testid="print-btn">
              <Printer className="w-3.5 h-3.5" /> Друк
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 py-5 space-y-6 print:px-0 print:py-2">
        {loading ? (
          <div className="text-center py-20 text-slate-400">Завантаження...</div>
        ) : !data || summary.total_orders === 0 ? (
          <div className="text-center py-20 text-slate-400">
            <Package className="w-12 h-12 mx-auto mb-3 opacity-40" />
            <p className="text-sm">На <strong>{formatLabel(dayOffset)}</strong> карток комплектації немає</p>
          </div>
        ) : (
          <>
            {data.awaiting_orders.length > 0 && (
              <Section title="📨 Очікують підтвердження клієнтом" subtitle="Нові ордери, поки що тільки для перегляду" tone="amber">
                {data.awaiting_orders.map(card => (
                  <CardView key={`o-${card.order_id}`} card={card} cardId={`o-${card.order_id}`} kind="awaiting"
                    onOpenCard={() => navigate(`/order/${card.order_id}/view`)}
                    checked={checked[`o-${card.order_id}`] || {}} onToggle={(pid) => toggleCheck(`o-${card.order_id}`, pid)} />
                ))}
              </Section>
            )}
            {data.preparation_cards.length > 0 && (
              <Section title="📦 На комплектації" tone="blue">
                {data.preparation_cards.map(card => {
                  const { done, total } = cardProgress(card)
                  return <CardView key={card.id} card={card} cardId={card.id} kind="prep"
                    progress={{ done, total }}
                    onOpenCard={() => navigate(`/issue/${card.id}`)}
                    checked={checked[card.id] || {}} onToggle={(pid) => toggleCheck(card.id, pid)} />
                })}
              </Section>
            )}
            {data.ready_cards.length > 0 && (
              <Section title="✅ Готові до видачі" tone="emerald">
                {data.ready_cards.map(card => {
                  const { done, total } = cardProgress(card)
                  return <CardView key={card.id} card={card} cardId={card.id} kind="ready"
                    progress={{ done, total }}
                    onOpenCard={() => navigate(`/issue/${card.id}`)}
                    checked={checked[card.id] || {}} onToggle={(pid) => toggleCheck(card.id, pid)} />
                })}
              </Section>
            )}
          </>
        )}
      </main>
    </div>
  )
}

function Pill({ label, value, color, bold }) {
  const c = {
    amber: 'text-amber-700 bg-amber-50 border-amber-200',
    blue: 'text-sky-700 bg-sky-50 border-sky-200',
    emerald: 'text-emerald-700 bg-emerald-50 border-emerald-200',
    slate: 'text-slate-700 bg-slate-100 border-slate-200',
  }[color] || 'text-slate-700 bg-slate-100 border-slate-200'
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 ${c} ${bold ? 'font-bold' : 'font-medium'}`}>
      <span className="opacity-70">{label}:</span>
      <span className="font-bold">{value || 0}</span>
    </span>
  )
}

function Section({ title, subtitle, tone, children }) {
  const tones = {
    amber: 'border-amber-200 bg-amber-50/30',
    blue: 'border-sky-200 bg-sky-50/30',
    emerald: 'border-emerald-200 bg-emerald-50/30',
  }
  return (
    <section className={`rounded-2xl border ${tones[tone] || 'border-slate-200'} p-4 space-y-3 print:border-0 print:bg-transparent print:p-0`}>
      <header>
        <h2 className="text-base font-bold text-slate-800">{title}</h2>
        {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
      </header>
      <div className="space-y-3">{children}</div>
    </section>
  )
}

function CardView({ card, cardId, kind, progress, checked, onToggle, onOpenCard }) {
  return (
    <article className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden break-inside-avoid print:shadow-none print:border print:rounded-none">
      {/* Card header */}
      <header className="px-4 py-3 border-b border-slate-100 bg-slate-50/40 flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={onOpenCard}
              title="Відкрити картку"
              className="font-bold text-slate-800 text-base hover:text-corp-primary hover:underline underline-offset-2 transition print:no-underline print:text-slate-800"
              data-testid={`open-card-${cardId}`}
            >
              {card.order_number}
            </button>
            <span className="text-slate-400">·</span>
            <span className="text-sm text-slate-700 font-medium">{card.customer_name || '—'}</span>
            {card.customer_phone && (
              <a href={`tel:${card.customer_phone}`} className="flex items-center gap-1 text-xs text-slate-500 hover:text-corp-primary">
                <Phone className="w-3 h-3" />{card.customer_phone}
              </a>
            )}
          </div>
          <div className="flex items-center gap-3 text-xs text-slate-500 mt-1 flex-wrap">
            {card.rental_start_date && (
              <span className="flex items-center gap-1"><Clock className="w-3 h-3" />Видача: <strong className="text-slate-700">{card.rental_start_date}</strong></span>
            )}
            {card.rental_end_date && (
              <span>Поверн.: <strong className="text-slate-700">{card.rental_end_date}</strong></span>
            )}
            <span><strong className="text-slate-700">{card.items_count}</strong> поз. · <strong className="text-slate-700">{card.items_total_qty}</strong> шт</span>
          </div>
        </div>
        {progress && progress.total > 0 && (
          <div className="text-right">
            <div className={`text-sm font-bold ${progress.done === progress.total ? 'text-emerald-600' : 'text-slate-600'}`}>
              {progress.done} / {progress.total}
            </div>
            <div className="w-20 h-1.5 bg-slate-100 rounded-full overflow-hidden mt-1">
              <div className={`h-full transition-all ${progress.done === progress.total ? 'bg-emerald-500' : 'bg-corp-primary'}`}
                style={{ width: `${(progress.done / progress.total) * 100}%` }} />
            </div>
          </div>
        )}
      </header>

      {/* Client comment (yellow) */}
      {card.order_notes?.trim() && (
        <div className="px-4 py-2.5 bg-amber-50 border-b border-amber-100 text-sm text-amber-900">
          <strong className="text-xs font-semibold uppercase text-amber-700">💬 Коментар клієнта:</strong>
          <div className="mt-0.5 whitespace-pre-wrap">{card.order_notes}</div>
        </div>
      )}

      {/* Internal prep notes (gray) */}
      {(card.preparation_notes?.trim() || card.issue_notes?.trim()) && (
        <div className="px-4 py-2 bg-slate-50 border-b border-slate-100 text-xs text-slate-600">
          {card.preparation_notes?.trim() && (
            <div><strong className="text-slate-500">Комплектація:</strong> {card.preparation_notes}</div>
          )}
          {card.issue_notes?.trim() && (
            <div><strong className="text-slate-500">Видача:</strong> {card.issue_notes}</div>
          )}
        </div>
      )}

      {/* Zones + items */}
      <div className="divide-y divide-slate-100">
        {card.zones.length === 0 ? (
          <div className="px-4 py-3 text-sm text-slate-400 italic">Товари не визначено</div>
        ) : card.zones.map(zone => (
          <div key={zone.zone} className="px-4 py-3">
            <div className="text-[11px] font-bold uppercase tracking-wide text-slate-500 mb-2">
              Зона: <span className="text-slate-800">{zone.zone}</span>
              <span className="ml-2 text-slate-400 font-normal normal-case">{zone.items.length} поз.</span>
            </div>
            <ul className="space-y-1.5">
              {zone.items.map(it => (
                <li key={`${it.product_id}-${it.sku}`} className="flex items-center gap-3 text-sm group">
                  {/* Checkbox (only for prep/ready, not awaiting) */}
                  {kind !== 'awaiting' && (
                    <input type="checkbox"
                      checked={!!checked[it.product_id]}
                      onChange={() => onToggle(it.product_id)}
                      className="w-4 h-4 rounded text-corp-primary focus:ring-1 focus:ring-corp-primary cursor-pointer print:hidden"
                      data-testid={`check-${cardId}-${it.product_id}`} />
                  )}
                  {/* Image thumb */}
                  <img src={getImageUrl(it.image_url, 'thumb') || FALLBACK_IMAGE} alt={it.name}
                    onError={handleImageError}
                    className="w-10 h-10 object-contain rounded bg-white border border-slate-100 flex-shrink-0 print:w-6 print:h-6" />
                  {/* SKU */}
                  <span className="text-xs text-slate-500 font-mono w-20 flex-shrink-0">{it.sku}</span>
                  {/* Name */}
                  <span className={`flex-1 min-w-0 truncate ${checked[it.product_id] ? 'text-slate-400 line-through' : 'text-slate-800'}`}>
                    {it.name}
                  </span>
                  {/* Damage warning */}
                  {it.has_damage_history && (
                    <span title="Має історію шкоди" className="text-amber-500 flex-shrink-0">
                      <AlertTriangle className="w-4 h-4" />
                    </span>
                  )}
                  {/* Qty */}
                  <span className="font-bold text-slate-800 text-sm w-12 text-right flex-shrink-0">× {it.qty}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </article>
  )
}
