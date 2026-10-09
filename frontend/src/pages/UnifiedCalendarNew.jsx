/* eslint-disable */
/**
 * UnifiedCalendar - Єдиний гнучкий календар
 * Corp design system + Cabinet integration
 */
import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import CorporateHeader from '../components/CorporateHeader'
import { CalendarDays, ChevronLeft, ChevronRight, Search, Plus, Package, AlertTriangle, Wrench, Wallet, CheckSquare, X, Clock, Phone } from 'lucide-react'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''
const KYIV_TZ = 'Europe/Kyiv'
const cls = (...a) => a.filter(Boolean).join(' ')

// ============================================================
// DATE HELPERS (Kyiv-safe)
// ============================================================
const getKyivTodayISO = () =>
  new Intl.DateTimeFormat('en-CA', { timeZone: KYIV_TZ, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())

const isoToSafe = (iso) => { const [y, m, d] = iso.split('-').map(Number); return new Date(Date.UTC(y, m - 1, d, 12)) }
const safeToISO = (d) => `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')}`
const addDays = (iso, n) => { const d = isoToSafe(iso); d.setUTCDate(d.getUTCDate() + n); return safeToISO(d) }

const fmtDateUA = (iso) => isoToSafe(iso).toLocaleDateString('uk-UA', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' })
const fmtMonthUA = (iso) => isoToSafe(iso).toLocaleDateString('uk-UA', { month: 'long', year: 'numeric', timeZone: 'UTC' })

const getWeekDays = (baseISO) => {
  const d = isoToSafe(baseISO); const day = d.getUTCDay(); d.setUTCDate(d.getUTCDate() + (day === 0 ? -6 : 1 - day))
  return Array.from({ length: 7 }, (_, i) => { const c = new Date(d); c.setUTCDate(c.getUTCDate() + i); return safeToISO(c) })
}

const getMonthDays = (baseISO) => {
  const [y, m] = baseISO.split('-').map(Number)
  const first = new Date(Date.UTC(y, m - 1, 1, 12)); const dow = first.getUTCDay()
  first.setUTCDate(first.getUTCDate() + (dow === 0 ? -6 : 1 - dow))
  return Array.from({ length: 42 }, (_, i) => { const c = new Date(first); c.setUTCDate(c.getUTCDate() + i); return safeToISO(c) })
}

// ============================================================
// AUTH
// ============================================================
const authFetch = async (url, opts = {}) => {
  const token = localStorage.getItem('token')
  return fetch(url, { ...opts, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...opts.headers } })
}

// ============================================================
// EVENT CONFIG
// ============================================================
const EVENT_COLORS = {
  issue_awaiting:   { bg: 'bg-violet-50',  border: 'border-violet-200', text: 'text-violet-700', dot: 'bg-violet-500' },
  issue_processing: { bg: 'bg-orange-50',  border: 'border-orange-200', text: 'text-orange-700', dot: 'bg-orange-500' },
  issue_ready:      { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-700', dot: 'bg-emerald-500' },
  return_issued:    { bg: 'bg-amber-50',   border: 'border-amber-200', text: 'text-amber-700', dot: 'bg-amber-500' },
  return_processing:{ bg: 'bg-orange-50',  border: 'border-orange-200', text: 'text-orange-700', dot: 'bg-orange-500' },
  return_overdue:   { bg: 'bg-red-50',     border: 'border-red-300',   text: 'text-red-700',    dot: 'bg-red-500' },
  cleaning:         { bg: 'bg-cyan-50',    border: 'border-cyan-200',  text: 'text-cyan-700',   dot: 'bg-cyan-500' },
  laundry:          { bg: 'bg-sky-50',     border: 'border-sky-200',   text: 'text-sky-700',    dot: 'bg-sky-500' },
  repair:           { bg: 'bg-orange-50',  border: 'border-orange-200', text: 'text-orange-700', dot: 'bg-orange-500' },
  damage:           { bg: 'bg-red-50',     border: 'border-red-200',   text: 'text-red-700',    dot: 'bg-red-500' },
  payment_due:      { bg: 'bg-purple-50',  border: 'border-purple-200', text: 'text-purple-700', dot: 'bg-purple-500' },
  deposit_return:   { bg: 'bg-teal-50',    border: 'border-teal-200',  text: 'text-teal-700',   dot: 'bg-teal-500' },
  task:             { bg: 'bg-indigo-50',  border: 'border-indigo-200', text: 'text-indigo-700', dot: 'bg-indigo-500' },
}

const EVENT_GROUPS = {
  orders:      { label: 'Замовлення',     Icon: Package,       types: ['issue_awaiting', 'issue_processing', 'issue_ready', 'return_issued', 'return_processing', 'return_overdue'] },
  maintenance: { label: 'Обслуговування', Icon: Wrench,        types: ['cleaning', 'laundry', 'repair'] },
  issues:      { label: 'Проблеми',       Icon: AlertTriangle, types: ['damage'] },
  finance:     { label: 'Фінанси',        Icon: Wallet,        types: ['payment_due', 'deposit_return'] },
  tasks:       { label: 'Завдання',       Icon: CheckSquare,   types: ['task'] },
}

// ============================================================
// TODAY SUMMARY
// ============================================================
function TodaySummary({ events, todayISO, onNavigate }) {
  const todayEvents = events.filter(e => e.date === todayISO)
  if (todayEvents.length === 0) return null

  const counts = {}
  todayEvents.forEach(e => { const g = e._meta?.group || 'other'; counts[g] = (counts[g] || 0) + 1 })
  const overdueCount = todayEvents.filter(e => e.type === 'return_overdue').length

  return (
    <div className="bg-white rounded-xl border border-corp-border p-4 mb-4" data-testid="today-summary">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-corp-primary animate-pulse" />
          <span className="text-sm font-semibold text-corp-text-dark">Сьогодні</span>
          <span className="text-xs text-corp-text-muted">{fmtDateUA(todayISO)}</span>
        </div>
        <span className="text-xs font-medium text-corp-text-muted bg-corp-bg-light px-2 py-1 rounded-lg">{todayEvents.length} подій</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {Object.entries(EVENT_GROUPS).map(([key, group]) => {
          const cnt = counts[key]
          if (!cnt) return null
          const GIcon = group.Icon
          return (
            <button key={key} onClick={() => onNavigate?.(todayISO)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-corp-bg-light border border-corp-border text-xs font-medium text-corp-text-main hover:bg-white transition-colors">
              <GIcon className="w-3.5 h-3.5" /> {group.label}: <span className="font-bold">{cnt}</span>
            </button>
          )
        })}
        {overdueCount > 0 && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-50 border border-red-200 text-xs font-semibold text-red-700 animate-pulse">
            <AlertTriangle className="w-3.5 h-3.5" /> Прострочено: {overdueCount}
          </div>
        )}
      </div>
    </div>
  )
}

// ============================================================
// EVENT CARD
// ============================================================
function EventCard({ event, compact = false, onClick }) {
  const c = EVENT_COLORS[event.type] || EVENT_COLORS.task
  const meta = event._meta || {}
  const isOverdue = event.type === 'return_overdue'

  if (compact) {
    return (
      <div onClick={() => onClick?.(event)}
        className={cls('px-2 py-1 rounded-lg text-[10px] cursor-pointer truncate border transition-all hover:shadow-sm',
          c.bg, c.border, c.text, isOverdue && 'ring-1 ring-red-400'
        )} data-testid={`cal-event-${event.id}`}>
        <span className="font-medium">{meta.icon} {event.title}</span>
      </div>
    )
  }

  return (
    <div onClick={() => onClick?.(event)}
      className={cls('p-3 rounded-xl border cursor-pointer transition-all hover:shadow-md hover:-translate-y-0.5',
        c.bg, c.border, isOverdue && 'ring-2 ring-red-400 animate-pulse'
      )} data-testid={`cal-event-${event.id}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className={cls('font-semibold text-sm truncate', c.text)}>{meta.icon} {event.title}</div>
          {event.subtitle && <div className="text-xs text-corp-text-muted mt-0.5 truncate">{event.subtitle}</div>}
        </div>
        {event.priority === 1 && <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0" />}
      </div>
      {event.is_range && event.date_end && (
        <div className="mt-1.5 text-[10px] text-corp-text-muted">{event.date} → {event.date_end}</div>
      )}
    </div>
  )
}

// ============================================================
// WEEK VIEW
// ============================================================
function WeekView({ baseDate, events, todayISO, onEventClick, onDayClick }) {
  const days = getWeekDays(baseDate)
  const [y, m] = baseDate.split('-').map(Number)

  return (
    <div className="flex border border-corp-border rounded-xl overflow-hidden bg-white">
      {days.map(day => {
        const dayEvents = events.filter(e => e.date === day)
        const isToday = day === todayISO
        const d = isoToSafe(day)
        const wd = d.toLocaleDateString('uk-UA', { weekday: 'short', timeZone: 'UTC' })
        const isSunday = d.getUTCDay() === 0

        return (
          <div key={day} className={cls('flex-1 min-w-0 border-r border-corp-border last:border-r-0',
            isToday && 'bg-[#f4f8e6]/40', isSunday && !isToday && 'bg-corp-gold/5'
          )}>
            <div onClick={() => onDayClick?.(day)}
              className={cls('p-2 text-center border-b border-corp-border cursor-pointer hover:bg-corp-bg-light transition-colors',
                isToday && 'bg-corp-primary/10'
              )}>
              <div className="text-[10px] text-corp-text-muted uppercase">{wd}</div>
              <div className={cls('text-lg font-bold',
                isToday ? 'text-corp-primary' : 'text-corp-text-dark'
              )}>{d.getUTCDate()}</div>
              {dayEvents.length > 0 && (
                <div className="flex justify-center gap-0.5 mt-1">
                  {dayEvents.slice(0, 5).map((e, i) => (
                    <div key={i} className={cls('w-1.5 h-1.5 rounded-full', EVENT_COLORS[e.type]?.dot || 'bg-corp-text-muted')} />
                  ))}
                  {dayEvents.length > 5 && <span className="text-[8px] text-corp-text-muted ml-0.5">+{dayEvents.length - 5}</span>}
                </div>
              )}
            </div>
            <div className="p-1 space-y-1 max-h-[400px] overflow-y-auto">
              {dayEvents.map(event => (
                <EventCard key={event.id} event={event} onClick={onEventClick} compact />
              ))}
              {dayEvents.length === 0 && (
                <button onClick={() => onDayClick?.(day)}
                  className="w-full py-4 text-corp-text-muted hover:text-corp-primary hover:bg-corp-bg-light rounded-lg transition-colors opacity-0 hover:opacity-100">
                  <Plus className="w-4 h-4 mx-auto" />
                </button>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ============================================================
// MONTH VIEW
// ============================================================
function MonthView({ baseDate, events, todayISO, onEventClick, onDayClick }) {
  const days = getMonthDays(baseDate)
  const [y, m] = baseDate.split('-').map(Number)
  const prefix = `${y}-${String(m).padStart(2, '0')}`
  const weeks = []; for (let i = 0; i < days.length; i += 7) weeks.push(days.slice(i, i + 7))

  return (
    <div className="border border-corp-border rounded-xl overflow-hidden bg-white">
      <div className="grid grid-cols-7 bg-corp-bg-light border-b border-corp-border">
        {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Нд'].map(d => (
          <div key={d} className="p-2 text-center text-xs font-medium text-corp-text-muted">{d}</div>
        ))}
      </div>
      {weeks.map((week, wi) => (
        <div key={wi} className="grid grid-cols-7 border-b border-corp-border last:border-b-0">
          {week.map(day => {
            const de = events.filter(e => e.date === day)
            const isToday = day === todayISO; const isCur = day.startsWith(prefix)
            const hasOverdue = de.some(e => e.type === 'return_overdue')
            return (
              <div key={day} onClick={() => onDayClick?.(day)}
                className={cls('min-h-[90px] p-1.5 border-r border-corp-border last:border-r-0 cursor-pointer hover:bg-corp-bg-light transition-colors',
                  isToday && 'bg-[#f4f8e6]/40', !isCur && 'opacity-40', hasOverdue && 'bg-red-50/50'
                )}>
                <div className={cls('text-sm font-medium mb-1',
                  isToday ? 'text-corp-primary font-bold' : isCur ? 'text-corp-text-dark' : 'text-corp-text-muted'
                )}>{isoToSafe(day).getUTCDate()}</div>
                <div className="space-y-0.5 max-h-[70px] overflow-y-auto">
                  {de.slice(0, 3).map(event => (
                    <div key={event.id} onClick={e => { e.stopPropagation(); onEventClick?.(event) }}
                      className={cls('px-1 py-0.5 rounded text-[9px] truncate cursor-pointer',
                        EVENT_COLORS[event.type]?.bg, EVENT_COLORS[event.type]?.text
                      )}>{event._meta?.icon} {event.title}</div>
                  ))}
                  {de.length > 3 && <div className="text-[9px] text-corp-text-muted text-center">+{de.length - 3}</div>}
                </div>
              </div>
            )
          })}
        </div>
      ))}
    </div>
  )
}

// ============================================================
// DAY VIEW
// ============================================================
function DayView({ date, events, onEventClick, onCreateTask }) {
  const de = events.filter(e => e.date === date)
  const grouped = {}; de.forEach(e => { const g = e._meta?.group || 'other'; (grouped[g] = grouped[g] || []).push(e) })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between bg-white rounded-xl border border-corp-border p-4">
        <div>
          <div className="text-xl font-bold text-corp-text-dark">{fmtDateUA(date)}</div>
          <div className="text-sm text-corp-text-muted">{de.length} подій</div>
        </div>
        <button onClick={() => onCreateTask?.(date)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-corp-primary text-white text-sm font-medium hover:bg-corp-primary-hover transition-colors"
          data-testid="create-task-day">
          <Plus className="w-4 h-4" /> Нова задача
        </button>
      </div>
      {Object.entries(EVENT_GROUPS).map(([gk, group]) => {
        const ge = grouped[gk] || []; if (!ge.length) return null
        const GIcon = group.Icon
        return (
          <div key={gk} className="bg-white rounded-xl border border-corp-border overflow-hidden">
            <div className="px-4 py-2.5 bg-corp-bg-light border-b border-corp-border flex items-center gap-2">
              <GIcon className="w-4 h-4 text-corp-text-main" />
              <span className="font-semibold text-sm text-corp-text-dark">{group.label}</span>
              <span className="text-xs text-corp-text-muted">({ge.length})</span>
            </div>
            <div className="p-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {ge.map(event => <EventCard key={event.id} event={event} onClick={onEventClick} />)}
            </div>
          </div>
        )
      })}
      {de.length === 0 && (
        <div className="text-center py-12 bg-white rounded-xl border border-corp-border">
          <CalendarDays className="w-12 h-12 mx-auto mb-3 text-corp-text-muted opacity-20" />
          <p className="text-sm text-corp-text-muted">Немає подій</p>
          <button onClick={() => onCreateTask?.(date)}
            className="mt-3 text-sm text-corp-primary font-medium hover:underline">+ Створити задачу</button>
        </div>
      )}
    </div>
  )
}

// ============================================================
// EVENT DETAIL MODAL
// ============================================================
function EventDetailModal({ event, onClose }) {
  const nav = useNavigate()
  if (!event) return null
  const c = EVENT_COLORS[event.type] || EVENT_COLORS.task

  const goToOrder = () => { if (event.order_id) { nav(`/order/${event.order_id}/view`); onClose() } }
  const goToOrderChat = () => { nav(`/cabinet?tab=orders&order=${event.order_id}`); onClose() }
  const goToTask = () => { nav(`/cabinet?tab=tasks`); onClose() }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full max-h-[80vh] overflow-y-auto border border-corp-border"
        onClick={e => e.stopPropagation()} data-testid="event-detail-modal">
        <div className={cls('px-5 py-4 border-b border-corp-border', c.bg)}>
          <div className="flex items-center justify-between">
            <div className={cls('text-lg font-bold', c.text)}>{event._meta?.icon} {event._meta?.label}</div>
            <button onClick={onClose} className="p-1 rounded-lg hover:bg-white/50"><X className="w-5 h-5 text-corp-text-muted" /></button>
          </div>
        </div>
        <div className="p-5 space-y-3">
          <div>
            <div className="text-xs text-corp-text-muted">Назва</div>
            <div className="font-semibold text-corp-text-dark">{event.title}</div>
          </div>
          {event.subtitle && <div><div className="text-xs text-corp-text-muted">Деталі</div><div className="text-sm text-corp-text-main">{event.subtitle}</div></div>}
          <div>
            <div className="text-xs text-corp-text-muted">Дата</div>
            <div className="text-sm font-medium text-corp-text-dark">{fmtDateUA(event.date)}</div>
            {event.date_end && <div className="text-xs text-corp-text-muted">→ {fmtDateUA(event.date_end)}</div>}
          </div>
          {event.customer_name && (
            <div>
              <div className="text-xs text-corp-text-muted">Клієнт</div>
              <div className="text-sm font-medium text-corp-text-dark">{event.customer_name}</div>
              {event.customer_phone && (
                <a href={`tel:${event.customer_phone}`} className="flex items-center gap-1 text-sm text-corp-primary hover:underline mt-0.5">
                  <Phone className="w-3.5 h-3.5" /> {event.customer_phone}
                </a>
              )}
            </div>
          )}
          {event.total_price > 0 && (
            <div><div className="text-xs text-corp-text-muted">Сума</div><div className="font-bold text-corp-primary">₴{event.total_price.toLocaleString()}</div></div>
          )}
          {/* Actions */}
          <div className="grid grid-cols-2 gap-2 pt-2">
            {event.order_id && (
              <button onClick={goToOrder} className="px-3 py-2.5 rounded-xl bg-corp-primary text-white text-sm font-medium hover:bg-corp-primary-hover transition-colors">
                Замовлення
              </button>
            )}
            {event.order_id && (
              <button onClick={goToOrderChat} className="px-3 py-2.5 rounded-xl border border-corp-border text-sm font-medium text-corp-text-main hover:bg-corp-bg-light transition-colors">
                Чат замовлення
              </button>
            )}
            {event._meta?.group === 'tasks' && (
              <button onClick={goToTask} className="col-span-2 px-3 py-2.5 rounded-xl bg-indigo-500 text-white text-sm font-medium hover:bg-indigo-600 transition-colors">
                Відкрити в кабінеті
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ============================================================
// CREATE TASK MODAL
// ============================================================
function CreateTaskModal({ date, onClose, onCreated }) {
  const [title, setTitle] = useState('')
  const [desc, setDesc] = useState('')
  const [priority, setPriority] = useState('medium')
  const [saving, setSaving] = useState(false)

  if (!date) return null

  const handleCreate = async () => {
    if (!title.trim()) return
    setSaving(true)
    try {
      const r = await authFetch(`${BACKEND_URL}/api/tasks`, {
        method: 'POST',
        body: JSON.stringify({ title: title.trim(), description: desc.trim(), priority, due_date: date, status: 'todo' })
      })
      if (r.ok) { onCreated?.(); onClose() }
    } catch (e) { console.error('[Calendar] create task error', e) }
    setSaving(false)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full border border-corp-border" onClick={e => e.stopPropagation()} data-testid="create-task-modal">
        <div className="px-5 py-4 border-b border-corp-border flex items-center justify-between">
          <div>
            <div className="text-xs text-corp-text-muted">Нова задача</div>
            <div className="text-lg font-semibold text-corp-text-dark">{fmtDateUA(date)}</div>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-corp-bg-light"><X className="w-5 h-5 text-corp-text-muted" /></button>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <label className="text-sm font-medium text-corp-text-dark">Назва *</label>
            <input value={title} onChange={e => setTitle(e.target.value)} autoFocus placeholder="Наприклад: Перевірити повернення #7044"
              className="mt-1 w-full px-3 py-2.5 rounded-xl border border-corp-border text-sm focus:outline-none focus:border-corp-primary" />
          </div>
          <div>
            <label className="text-sm font-medium text-corp-text-dark">Опис</label>
            <textarea value={desc} onChange={e => setDesc(e.target.value)} rows={2} placeholder="Деталі (опціонально)"
              className="mt-1 w-full px-3 py-2.5 rounded-xl border border-corp-border text-sm focus:outline-none focus:border-corp-primary resize-none" />
          </div>
          <div>
            <label className="text-sm font-medium text-corp-text-dark">Пріоритет</label>
            <div className="flex gap-2 mt-2">
              {[['low', 'Низький'], ['medium', 'Середній'], ['high', 'Високий']].map(([v, l]) => (
                <button key={v} onClick={() => setPriority(v)}
                  className={cls('flex-1 py-2 rounded-xl text-xs font-medium border transition-colors',
                    priority === v ? 'bg-corp-primary text-white border-corp-primary' : 'border-corp-border text-corp-text-main hover:bg-corp-bg-light'
                  )}>{l}</button>
              ))}
            </div>
          </div>
          <button onClick={handleCreate} disabled={!title.trim() || saving}
            className="w-full py-2.5 rounded-xl bg-corp-primary text-white font-medium hover:bg-corp-primary-hover transition-colors disabled:opacity-50"
            data-testid="create-task-submit">
            {saving ? 'Створення...' : 'Створити задачу'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ============================================================
// STATS BAR
// ============================================================
function StatsBar({ events }) {
  const stats = useMemo(() => {
    const r = {}; events.forEach(e => { const t = e.type; r[t] = (r[t] || 0) + 1 }); return r
  }, [events])

  const entries = Object.entries(stats)
  if (!entries.length) return null

  return (
    <div className="flex flex-wrap gap-1.5 mb-4" data-testid="stats-bar">
      {entries.map(([type, count]) => {
        const meta = events.find(e => e.type === type)?._meta || {}
        const c = EVENT_COLORS[type] || {}
        const isOverdue = type === 'return_overdue'
        return (
          <div key={type} className={cls('px-2.5 py-1 rounded-lg text-[11px] flex items-center gap-1 border font-medium',
            c.bg, c.text, c.border, isOverdue && 'animate-pulse ring-1 ring-red-400'
          )}>
            <span>{meta.icon}</span> <span>{meta.label}: {count}</span>
          </div>
        )
      })}
    </div>
  )
}

// ============================================================
// MAIN
// ============================================================
export default function UnifiedCalendar() {
  const nav = useNavigate()
  const [view, setView] = useState('week')
  const [baseDate, setBaseDate] = useState(getKyivTodayISO())
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedEvent, setSelectedEvent] = useState(null)
  const [search, setSearch] = useState('')
  const [activeGroups, setActiveGroups] = useState(new Set(Object.keys(EVENT_GROUPS)))
  const [createTaskDate, setCreateTaskDate] = useState(null)

  const todayISO = useMemo(() => getKyivTodayISO(), [])

  // Mobile: auto day view
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 640px)')
    if (mq.matches) setView('day')
  }, [])

  const dateRange = useMemo(() => {
    if (view === 'day') return { from: baseDate, to: baseDate }
    if (view === 'week') { const d = getWeekDays(baseDate); return { from: d[0], to: d[6] } }
    const [y, m] = baseDate.split('-').map(Number)
    const last = new Date(Date.UTC(y, m, 0)).getUTCDate()
    return { from: addDays(`${y}-${String(m).padStart(2, '0')}-01`, -7), to: addDays(`${y}-${String(m).padStart(2, '0')}-${last}`, 7) }
  }, [view, baseDate])

  const loadEvents = useCallback(async () => {
    setLoading(true)
    try {
      const gp = activeGroups.size > 0 && activeGroups.size < Object.keys(EVENT_GROUPS).length ? `&groups=${[...activeGroups].join(',')}` : ''
      const sp = search ? `&search=${encodeURIComponent(search)}` : ''
      const r = await authFetch(`${BACKEND_URL}/api/calendar/events?date_from=${dateRange.from}&date_to=${dateRange.to}${gp}${sp}`)
      const d = await r.json()
      setEvents(d.events || [])
    } catch (e) { console.error('[Calendar]', e); setEvents([]) }
    setLoading(false)
  }, [dateRange, activeGroups, search])

  useEffect(() => { loadEvents() }, [loadEvents])

  const navDate = (dir) => {
    if (view === 'day') setBaseDate(addDays(baseDate, dir))
    else if (view === 'week') setBaseDate(addDays(baseDate, dir * 7))
    else {
      const [y, m] = baseDate.split('-').map(Number)
      const nm = m + dir; const ny = nm < 1 ? y - 1 : nm > 12 ? y + 1 : y
      setBaseDate(`${ny}-${String(nm < 1 ? 12 : nm > 12 ? 1 : nm).padStart(2, '0')}-01`)
    }
  }

  const toggleGroup = (g) => { const s = new Set(activeGroups); s.has(g) ? s.delete(g) : s.add(g); setActiveGroups(s) }
  const handleDayClick = (d) => { setBaseDate(d); setView('day') }

  return (
    <div className="min-h-screen bg-corp-bg-page" data-testid="unified-calendar">
      <CorporateHeader cabinetName="Календар подій" showBackButton />

      <div className="mx-auto max-w-7xl px-3 sm:px-6 py-4">
        {/* View switcher */}
        <div className="flex items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-1 bg-white rounded-xl p-1 border border-corp-border">
            {[['day', 'День'], ['week', 'Тиждень'], ['month', 'Місяць']].map(([v, l]) => (
              <button key={v} onClick={() => setView(v)}
                className={cls('px-4 py-2 rounded-lg text-sm font-medium transition-all',
                  view === v ? 'bg-corp-primary text-white shadow-sm' : 'text-corp-text-main hover:bg-corp-bg-light'
                )} data-testid={`view-${v}`}>{l}</button>
            ))}
          </div>
        </div>

        {/* Navigation */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-2">
            <button onClick={() => navDate(-1)} className="p-2 rounded-xl bg-white border border-corp-border hover:bg-corp-bg-light transition-colors">
              <ChevronLeft className="w-4 h-4 text-corp-text-main" />
            </button>
            <button onClick={() => setBaseDate(todayISO)}
              className="px-4 py-2 rounded-xl bg-[#f4f8e6] text-corp-primary font-medium text-sm border border-corp-primary/20 hover:bg-corp-primary/10 transition-colors"
              data-testid="go-today">Сьогодні</button>
            <button onClick={() => navDate(1)} className="p-2 rounded-xl bg-white border border-corp-border hover:bg-corp-bg-light transition-colors">
              <ChevronRight className="w-4 h-4 text-corp-text-main" />
            </button>
            <span className="ml-2 text-base font-semibold text-corp-text-dark">
              {view === 'month' ? fmtMonthUA(baseDate) : fmtDateUA(baseDate)}
            </span>
          </div>
          <div className="relative w-full sm:w-auto">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-corp-text-muted" />
            <input type="text" placeholder="Пошук..." value={search} onChange={e => setSearch(e.target.value)}
              className="w-full sm:w-56 pl-9 pr-4 py-2 rounded-xl border border-corp-border text-sm bg-white focus:outline-none focus:border-corp-primary"
              data-testid="cal-search" />
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2 mb-4 p-3 bg-white rounded-xl border border-corp-border">
          <span className="text-xs text-corp-text-muted mr-1">Фільтри:</span>
          {Object.entries(EVENT_GROUPS).map(([key, group]) => {
            const GIcon = group.Icon; const active = activeGroups.has(key)
            return (
              <button key={key} onClick={() => toggleGroup(key)}
                className={cls('flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border',
                  active ? 'bg-corp-primary text-white border-corp-primary' : 'bg-corp-bg-light text-corp-text-main border-corp-border hover:bg-white'
                )} data-testid={`filter-${key}`}>
                <GIcon className="w-3.5 h-3.5" /> {group.label}
              </button>
            )
          })}
        </div>

        {/* Today summary */}
        {view !== 'day' && <TodaySummary events={events} todayISO={todayISO} onNavigate={handleDayClick} />}

        {/* Stats */}
        <StatsBar events={events} />

        {/* Calendar */}
        {loading ? (
          <div className="text-center py-16 text-corp-text-muted animate-pulse">
            <CalendarDays className="w-12 h-12 mx-auto mb-3 opacity-20" />
            <p className="text-sm">Завантаження...</p>
          </div>
        ) : (
          <>
            {view === 'day' && <DayView date={baseDate} events={events} onEventClick={setSelectedEvent} onCreateTask={setCreateTaskDate} />}
            {view === 'week' && <WeekView baseDate={baseDate} events={events} todayISO={todayISO} onEventClick={setSelectedEvent} onDayClick={handleDayClick} />}
            {view === 'month' && <MonthView baseDate={baseDate} events={events} todayISO={todayISO} onEventClick={setSelectedEvent} onDayClick={handleDayClick} />}
          </>
        )}
      </div>

      <EventDetailModal event={selectedEvent} onClose={() => setSelectedEvent(null)} />
      <CreateTaskModal date={createTaskDate} onClose={() => setCreateTaskDate(null)} onCreated={loadEvents} />
    </div>
  )
}
