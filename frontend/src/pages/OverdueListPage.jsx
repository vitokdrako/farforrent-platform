/* eslint-disable */
/**
 * OverdueListPage — лист прострочених повернень ("Борги").
 * 3 секції за ступенем прострочки:
 *   - mild (1-3 дні)
 *   - serious (4-7 днів)
 *   - critical (8+ днів)
 */
import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import CorporateHeader from '../components/CorporateHeader'
import ImageLightbox from '../components/ImageLightbox'
import { useWarehouse } from '../context/WarehouseContext'
import { getImageUrl, FALLBACK_IMAGE, handleImageError } from '../utils/imageHelper'
import { Printer, PackageOpen, AlertTriangle, Phone, RefreshCw, Plus, CheckSquare, X, AlertCircle, Flame } from 'lucide-react'

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

export default function OverdueListPage() {
  const navigate = useNavigate()
  const { active: activeWarehouse, withWh } = useWarehouse()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [taskModal, setTaskModal] = useState(null)
  const [lightbox, setLightbox] = useState(null)
  const [staff, setStaff] = useState([])

  useEffect(() => {
    authFetch(`${BACKEND_URL}/api/tasks/staff`).then(r => r.ok ? r.json() : []).then(setStaff)
  }, [])

  const fetchData = async () => {
    setLoading(true)
    try {
      const res = await authFetch(withWh(`${BACKEND_URL}/api/manager/overdue-list`))
      if (res.ok) setData(await res.json())
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  useEffect(() => {
    if (!activeWarehouse) return
    fetchData()
  }, [activeWarehouse?.id])

  const summary = data?.summary || {}
  const hasAny = (summary.total_count || 0) > 0

  return (
    <div className="min-h-screen bg-corp-bg-page font-montserrat" data-testid="overdue-list-page">
      <CorporateHeader cabinetName="Борги · Прострочені повернення" showBackButton />

      {/* Toolbar */}
      <div className="bg-white border-b border-corp-border sticky top-0 z-20 print:hidden">
        <div className="max-w-7xl mx-auto px-2 sm:px-4 py-2 sm:py-3 flex flex-wrap items-center gap-2 sm:gap-3">
          <div className="flex items-center gap-1.5 sm:gap-3 text-[11px] sm:text-xs flex-wrap">
            <Pill icon={<AlertCircle className="w-3 h-3" />} label="1–3 дні" value={summary.mild_count} color="yellow" />
            <Pill icon={<AlertTriangle className="w-3 h-3" />} label="4–7 днів" value={summary.serious_count} color="orange" />
            <Pill icon={<Flame className="w-3 h-3" />} label="8+ днів" value={summary.critical_count} color="rose" />
            <span className="hidden sm:inline h-5 w-px bg-slate-200" />
            <Pill label="Усього боргів" value={summary.total_count} color="slate" bold />
            <Pill label="Позицій" value={summary.total_items} color="slate" />
            {summary.total_amount > 0 && (
              <Pill label="Сума" value={`${Math.round(summary.total_amount).toLocaleString('uk-UA')} ₴`} color="slate" bold />
            )}
          </div>

          <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
            <button onClick={fetchData} disabled={loading}
              className="p-1.5 sm:p-2 rounded-lg border border-slate-200 hover:bg-slate-50" data-testid="refresh-btn">
              <RefreshCw className={`w-3.5 h-3.5 sm:w-4 sm:h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <button onClick={() => window.print()}
              className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-900 text-white text-[11px] sm:text-xs font-semibold" data-testid="print-btn">
              <Printer className="w-3.5 h-3.5" /> <span className="hidden sm:inline">Друк</span>
            </button>
          </div>
        </div>
      </div>

      <main className="max-w-7xl mx-auto px-2 sm:px-4 py-3 sm:py-5 space-y-4 sm:space-y-6 print:px-0 print:py-2">
        {loading ? (
          <div className="text-center py-20 text-slate-400">Завантаження...</div>
        ) : !hasAny ? (
          <div className="text-center py-20 text-emerald-600">
            <PackageOpen className="w-12 h-12 mx-auto mb-3 opacity-40" />
            <p className="text-sm">Прострочених повернень немає. Все повернуто вчасно 🎉</p>
          </div>
        ) : (
          <>
            {data.critical_overdue.length > 0 && (
              <Section title="🔥 Критична прострочка (8+ днів)" subtitle="Терміново дзвонити клієнту" tone="rose">
                {data.critical_overdue.map(card => (
                  <CardView key={card.id} card={card} onOpenCard={() => navigate(`/order/${card.order_id}/view`)}
                    onCreateTask={setTaskModal} onImageClick={setLightbox} severity="critical" />
                ))}
              </Section>
            )}
            {data.serious_overdue.length > 0 && (
              <Section title="⚠️ Серйозна прострочка (4–7 днів)" subtitle="Нагадати клієнту про повернення" tone="orange">
                {data.serious_overdue.map(card => (
                  <CardView key={card.id} card={card} onOpenCard={() => navigate(`/order/${card.order_id}/view`)}
                    onCreateTask={setTaskModal} onImageClick={setLightbox} severity="serious" />
                ))}
              </Section>
            )}
            {data.mild_overdue.length > 0 && (
              <Section title="📅 Легка прострочка (1–3 дні)" tone="yellow">
                {data.mild_overdue.map(card => (
                  <CardView key={card.id} card={card} onOpenCard={() => navigate(`/order/${card.order_id}/view`)}
                    onCreateTask={setTaskModal} onImageClick={setLightbox} severity="mild" />
                ))}
              </Section>
            )}
          </>
        )}
      </main>

      {taskModal && (
        <TaskCreateModal
          context={taskModal} staff={staff}
          onClose={() => setTaskModal(null)}
          onCreated={() => { setTaskModal(null); fetchData() }}
        />
      )}
      {lightbox && (
        <ImageLightbox src={lightbox.src} alt={lightbox.alt} onClose={() => setLightbox(null)} />
      )}
    </div>
  )
}

function Pill({ icon, label, value, color, bold }) {
  const c = {
    yellow: 'text-yellow-700 bg-yellow-50 border-yellow-200',
    orange: 'text-orange-700 bg-orange-50 border-orange-200',
    rose: 'text-rose-700 bg-rose-50 border-rose-200',
    slate: 'text-slate-700 bg-slate-100 border-slate-200',
  }[color] || 'text-slate-700 bg-slate-100 border-slate-200'
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 sm:px-2.5 py-0.5 sm:py-1 ${c} ${bold ? 'font-bold' : 'font-medium'}`}>
      {icon}
      <span className="opacity-70">{label}:</span>
      <span className="font-bold">{value || 0}</span>
    </span>
  )
}

function Section({ title, subtitle, tone, children }) {
  const tones = {
    yellow: 'border-yellow-200 bg-yellow-50/30',
    orange: 'border-orange-200 bg-orange-50/30',
    rose: 'border-rose-200 bg-rose-50/30',
  }
  return (
    <section className={`rounded-2xl border ${tones[tone] || 'border-slate-200'} p-2.5 sm:p-4 space-y-3 print:border-0 print:bg-transparent print:p-0`}>
      <header>
        <h2 className="text-sm sm:text-base font-bold text-slate-800">{title}</h2>
        {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
      </header>
      <div className="space-y-2 sm:space-y-3">{children}</div>
    </section>
  )
}

function CardView({ card, severity, onOpenCard, onCreateTask, onImageClick }) {
  const severityStyles = {
    critical: 'border-rose-300 bg-rose-50/40',
    serious: 'border-orange-200 bg-orange-50/30',
    mild: 'border-yellow-200 bg-yellow-50/20',
  }
  const dayLabel = card.days_overdue === 1 ? 'день' : card.days_overdue < 5 ? 'дні' : 'днів'

  return (
    <article className={`bg-white rounded-xl border-2 ${severityStyles[severity] || 'border-slate-200'} shadow-sm overflow-hidden print:shadow-none print:border print:rounded-none`}>
      <header className="px-3 py-2.5 sm:px-4 sm:py-3 border-b border-slate-100 flex flex-wrap items-start gap-2 sm:gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={onOpenCard}
              className="font-bold text-slate-800 text-base hover:text-corp-primary hover:underline transition"
              data-testid={`open-order-${card.order_id}`}
            >
              {card.order_number}
            </button>
            <span className="text-slate-400">·</span>
            <span className="text-sm text-slate-700 font-medium">{card.customer_name || '—'}</span>
            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold ${
              severity === 'critical' ? 'bg-rose-600 text-white' :
              severity === 'serious' ? 'bg-orange-500 text-white' :
              'bg-yellow-400 text-yellow-900'
            }`}>
              {card.days_overdue} {dayLabel}
            </span>
          </div>
          {card.customer_phone && (
            <a href={`tel:${card.customer_phone}`} className="inline-flex items-center gap-1 text-xs text-slate-600 hover:text-corp-primary mt-1 font-medium">
              <Phone className="w-3 h-3" />{card.customer_phone}
            </a>
          )}
          <div className="flex items-center gap-2 sm:gap-3 text-[11px] sm:text-xs text-slate-500 mt-1 flex-wrap">
            {card.rental_end_date && (
              <span>Повернення мало бути: <strong className="text-rose-700">{card.rental_end_date}</strong></span>
            )}
            <span><strong className="text-slate-700">{card.items_count}</strong> поз. · <strong className="text-slate-700">{card.items_total_qty}</strong> шт</span>
            {card.total_price > 0 && (
              <span>Сума: <strong className="text-slate-700">{Math.round(card.total_price).toLocaleString('uk-UA')} ₴</strong></span>
            )}
          </div>
        </div>
      </header>

      {card.tasks && card.tasks.length > 0 && (
        <div className="px-3 sm:px-4 py-2 bg-violet-50 border-b border-violet-100 flex flex-wrap items-center gap-1.5 sm:gap-2 text-xs">
          <CheckSquare className="w-3.5 h-3.5 text-violet-600 flex-shrink-0" />
          <span className="font-semibold text-violet-700 uppercase text-[10px]">Завдання:</span>
          {card.tasks.map(t => (
            <span key={t.id} className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 bg-violet-100 text-violet-700">
              {t.title}
              {t.assignee_name && <span className="text-slate-500 whitespace-nowrap">→ {t.assignee_name}</span>}
            </span>
          ))}
        </div>
      )}

      {card.order_notes?.trim() && (
        <div className="px-3 sm:px-4 py-2 bg-amber-50 border-b border-amber-100 text-sm text-amber-900">
          <strong className="text-xs font-semibold uppercase text-amber-700">💬 Коментар:</strong>
          <div className="mt-0.5 whitespace-pre-wrap break-words">{card.order_notes}</div>
        </div>
      )}

      <div className="divide-y divide-slate-100">
        {card.zones.length === 0 ? (
          <div className="px-4 py-3 text-sm text-slate-400 italic">Товари не визначено</div>
        ) : card.zones.map(zone => (
          <div key={zone.zone} className="px-3 py-2.5 sm:px-4 sm:py-3">
            <div className="text-[11px] font-bold uppercase tracking-wide text-slate-500 mb-2">
              Зона: <span className="text-slate-800">{zone.zone}</span>
              <span className="ml-2 text-slate-400 font-normal normal-case">{zone.items.length} поз.</span>
            </div>
            <ul className="space-y-2 sm:space-y-1.5">
              {zone.items.map(it => (
                <ItemRow key={`${it.product_id}-${it.sku}`} it={it} onImageClick={onImageClick}
                  onCreateTask={() => onCreateTask({ order_id: card.order_id, order_number: card.order_number, product_id: it.product_id, product_name: it.name, sku: it.sku })} />
              ))}
            </ul>
          </div>
        ))}
      </div>
    </article>
  )
}

/* Окремий рядок товару зі збільшенням фото */
export function ItemRow({ it, onImageClick, onCreateTask }) {
  const fullImg = getImageUrl(it.image_url, 'full') || getImageUrl(it.image_url, 'thumb') || FALLBACK_IMAGE
  return (
    <li className="flex flex-col gap-1 text-sm group">
      <div className="flex items-center gap-2 sm:gap-3">
        <button
          onClick={(e) => {
            e.stopPropagation()
            if (onImageClick && it.image_url) onImageClick({ src: fullImg, alt: `${it.sku || ''} ${it.name}`.trim() })
          }}
          className="focus:outline-none focus:ring-2 focus:ring-corp-primary rounded flex-shrink-0 print:pointer-events-none"
          title="Клацни для збільшення"
          data-testid={`img-zoom-${it.product_id}`}
          disabled={!it.image_url}
        >
          <img
            src={getImageUrl(it.image_url, 'thumb') || FALLBACK_IMAGE}
            alt={it.name}
            onError={handleImageError}
            className="w-12 h-12 sm:w-10 sm:h-10 object-contain rounded bg-white border border-slate-100 cursor-zoom-in hover:ring-2 hover:ring-corp-primary transition print:w-6 print:h-6 print:cursor-default"
          />
        </button>
        <div className="flex-1 min-w-0 flex flex-col sm:flex-row sm:items-center sm:gap-3">
          {it.sku ? (
            <a href={`/reaudit?sku=${encodeURIComponent(it.sku)}`} target="_blank" rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="text-xs text-corp-primary hover:underline font-mono font-semibold sm:font-normal sm:w-20 flex-shrink-0 print:no-underline print:text-slate-500"
              data-testid={`sku-link-${it.sku}`}>
              {it.sku}
            </a>
          ) : (
            <span className="text-xs text-slate-400 font-mono sm:w-20 flex-shrink-0">—</span>
          )}
          <span className="flex-1 min-w-0 text-sm sm:truncate leading-snug text-slate-800">
            {it.name}
          </span>
        </div>
        {it.has_damage_history && (
          <span title="Має історію шкоди" className="text-amber-500 flex-shrink-0">
            <AlertTriangle className="w-4 h-4" />
          </span>
        )}
        <span className="font-bold text-slate-800 text-sm sm:w-12 text-right flex-shrink-0 whitespace-nowrap">× {it.qty}</span>
        {onCreateTask && (
          <button onClick={(e) => { e.stopPropagation(); onCreateTask() }}
            title="Створити завдання"
            className="sm:opacity-30 sm:group-hover:opacity-100 hover:bg-violet-50 text-violet-600 rounded p-1.5 sm:p-1 transition flex-shrink-0 print:hidden"
            data-testid={`new-task-${it.product_id}`}>
            <Plus className="w-4 h-4 sm:w-3.5 sm:h-3.5" />
          </button>
        )}
      </div>
      {it.components && (
        <div className="ml-7 sm:ml-11 pl-3 border-l-2 border-sky-200 text-xs text-slate-600 italic print:ml-4">
          <span className="not-italic font-semibold text-sky-700">+ комплект:</span> {it.components}
        </div>
      )}
    </li>
  )
}

/* Task Create Modal (той самий, що й у Picking/Returns) */
function TaskCreateModal({ context, staff, onClose, onCreated }) {
  const [title, setTitle] = useState(context.product_name || '')
  const [description, setDescription] = useState('')
  const [taskType, setTaskType] = useState('general')
  const [priority, setPriority] = useState('medium')
  const [assignedToId, setAssignedToId] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async () => {
    if (!title.trim()) { alert('Введіть назву завдання'); return }
    setSaving(true)
    try {
      const res = await authFetch(`${BACKEND_URL}/api/tasks`, {
        method: 'POST',
        body: JSON.stringify({
          title: title.trim(), description: description.trim() || null,
          task_type: taskType, priority,
          assigned_to_id: assignedToId ? Number(assignedToId) : null,
          order_id: context.order_id || null, order_number: context.order_number || null,
          due_date: dueDate || null,
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Помилка' }))
        alert(err.detail || 'Помилка')
        return
      }
      onCreated()
    } catch (e) { alert('Помилка: ' + String(e)) }
    finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3" data-testid="task-create-modal">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-2xl w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col shadow-xl">
        <header className="flex items-center justify-between px-5 py-3 border-b bg-slate-50/50">
          <div>
            <div className="text-xs text-slate-500">Нове завдання</div>
            <h3 className="text-base font-bold">{context.order_number && <>До {context.order_number}</>}</h3>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-slate-100 rounded-lg" data-testid="task-modal-close">
            <X className="w-5 h-5" />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          <input value={title} onChange={e => setTitle(e.target.value)} autoFocus
            className="w-full rounded-lg border px-3 py-2 text-sm" placeholder="Назва завдання *" data-testid="task-title" />
          <textarea value={description} onChange={e => setDescription(e.target.value)} rows={3}
            className="w-full rounded-lg border px-3 py-2 text-sm" placeholder="Опис..." data-testid="task-description" />
          <div className="grid grid-cols-2 gap-3">
            <select value={taskType} onChange={e => setTaskType(e.target.value)} className="rounded-lg border px-3 py-2 text-sm" data-testid="task-type">
              <option value="general">Звичайне</option>
              <option value="call">Дзвінок</option>
              <option value="payment">Оплата</option>
              <option value="return_followup">Нагадати про повернення</option>
            </select>
            <select value={priority} onChange={e => setPriority(e.target.value)} className="rounded-lg border px-3 py-2 text-sm" data-testid="task-priority">
              <option value="low">Низький</option>
              <option value="medium">Середній</option>
              <option value="high">Високий</option>
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <select value={assignedToId} onChange={e => setAssignedToId(e.target.value)} className="rounded-lg border px-3 py-2 text-sm" data-testid="task-assignee">
              <option value="">— Не призначено —</option>
              {staff.map(s => (
                <option key={s.user_id || s.id} value={s.user_id || s.id}>
                  {s.firstname ? `${s.firstname} ${s.lastname || ''}` : s.username || s.name}
                </option>
              ))}
            </select>
            <input type="date" value={dueDate} onChange={e => setDueDate(e.target.value)}
              className="rounded-lg border px-3 py-2 text-sm" data-testid="task-due-date" />
          </div>
        </div>
        <footer className="flex items-center justify-end gap-2 px-5 py-3 border-t bg-slate-50/50">
          <button onClick={onClose} className="px-4 py-2 rounded-lg text-sm text-slate-600 hover:bg-slate-100">Скасувати</button>
          <button onClick={submit} disabled={saving}
            className="px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-700 text-white text-sm font-semibold disabled:opacity-50"
            data-testid="task-submit">
            {saving ? 'Створюю...' : 'Створити'}
          </button>
        </footer>
      </div>
    </div>
  )
}
