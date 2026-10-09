import React, { useMemo, useState, useEffect } from 'react'
import { getImageUrl } from '../utils/imageHelper'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'https://backrentalhub.farforrent.com.ua'

/*************** helpers ***************/
const cls = (...a: (string | false | null | undefined)[]) => a.filter(Boolean).join(' ')
const fmtUA = (n: number) => (Number(n) || 0).toLocaleString('uk-UA', { maximumFractionDigits: 0 })

/*************** types ***************/
type DamageSeverity = 'low' | 'medium' | 'high' | 'critical'
type DamageStatus = 'draft' | 'awaiting_client' | 'awaiting_payment' | 'in_repair' | 'closed'
type DamageSource = 'return' | 'reaudit' | 'other'

interface DamageLine {
  id: string
  productName: string
  sku: string
  inventoryCode?: string
  category: string
  ruleLabel?: string
  minAmount?: number
  qty: number
  amountPerUnit: number
  total: number
  note?: string
  fromReauditItemId?: string
  image?: string
}

interface DamageCase {
  id: string
  orderId?: string
  source: DamageSource
  fromReauditItemId?: string | null
  createdAt: string
  createdBy: string
  clientName: string
  eventName?: string
  returnDate?: string
  severity: DamageSeverity
  status: DamageStatus
  depositHold: number
  lines: DamageLine[]
  internalNote?: string
}

/*************** small UI ***************/
function Badge({ tone = 'slate', children }: { tone?: string; children: React.ReactNode }) {
  const tones: Record<string, string> = {
    slate: 'corp-badge corp-badge-neutral',
    green: 'corp-badge corp-badge-success',
    blue: 'corp-badge corp-badge-info',
    amber: 'corp-badge corp-badge-warning',
    red: 'corp-badge corp-badge-error',
    violet: 'corp-badge corp-badge-primary',
  }
  return (
    <span className={tones[tone] || tones.slate}>
      {children}
    </span>
  )
}

function PillButton({
  children,
  onClick,
  tone = 'slate',
}: {
  children: React.ReactNode
  onClick?: () => void
  tone?: 'slate' | 'green' | 'ghost' | 'red' | 'amber'
}) {
  const tones: Record<string, string> = {
    slate: 'corp-btn corp-btn-secondary',
    green: 'corp-btn corp-btn-primary',
    red: 'corp-btn corp-btn-secondary text-corp-error hover:bg-corp-error hover:text-white',
    amber: 'corp-btn corp-btn-gold',
    ghost: 'corp-btn corp-btn-outline',
  }
  return (
    <button
      type="button"
      onClick={onClick}
      className={tones[tone]}
    >
      {children}
    </button>
  )
}

function SeverityBadge({ severity }: { severity: DamageSeverity }) {
  if (severity === 'low') return <Badge tone="green">Low</Badge>
  if (severity === 'medium') return <Badge tone="amber">Medium</Badge>
  if (severity === 'high') return <Badge tone="red">High</Badge>
  return <Badge tone="red">Critical</Badge>
}

function StatusBadge({ status }: { status: DamageStatus }) {
  const map: Record<DamageStatus, { label: string; tone: string }> = {
    draft: { label: 'Чернетка', tone: 'slate' },
    awaiting_client: { label: 'Очікуємо підтвердження клієнта', tone: 'amber' },
    awaiting_payment: { label: 'Очікуємо оплату', tone: 'amber' },
    in_repair: { label: 'В реставрації', tone: 'blue' },
    closed: { label: 'Закрито', tone: 'green' },
  }
  const x = map[status] || { label: status || 'Невідомо', tone: 'slate' }
  return <Badge tone={x.tone}>{x.label}</Badge>
}

/*************** main component ***************/
export default function DamageCabinetPro({ 
  onBackToDashboard,
  onNavigateToTasks,
  initialDamageId
}: { 
  onBackToDashboard?: () => void
  onNavigateToTasks?: (damageId: string) => void
  initialDamageId?: string
}) {
  const [cases, setCases] = useState<DamageCase[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedId, setSelectedId] = useState<string | null>(initialDamageId || null)
  const [q, setQ] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | DamageStatus>('all')
  const [severityFilter, setSeverityFilter] = useState<'all' | DamageSeverity>('all')
  const [sourceFilter, setSourceFilter] = useState<'all' | DamageSource>('all')
  const [showTaskModal, setShowTaskModal] = useState(false)
  const [showSendModal, setShowSendModal] = useState(false)

  useEffect(() => {
    loadCases()
  }, [])

  const loadCases = async () => {
    try {
      setLoading(true)
      
      // Завантажити всі пошкодження з product_damage_history
      const response = await fetch(`${BACKEND_URL}/api/product-damage-history/recent?limit=200`)
      const data = await response.json()
      
      console.log('[DamageCabinet] Loaded damage history:', data.length)
      
      // Трансформувати дані з product_damage_history
      const transformedData = data.map((item: any) => ({
        id: String(item.id),
        orderId: item.order_id ? String(item.order_id) : null,
        clientName: item.product_name || 'Без назви',
        eventName: item.order_number 
          ? `Замовлення ${item.order_number}` 
          : (item.note || 'Кейс пошкодження'),
        status: 'closed', // Всі історичні пошкодження вважаються закритими
        severity: item.severity === 'high' ? 'critical' : 
                  item.severity === 'medium' ? 'medium' : 'low',
        source: item.stage === 'return' ? 'return' : 
                item.stage === 'audit' ? 'reaudit' : 'other',
        depositHold: 0,
        lines: [{
          id: String(item.id),
          productName: item.product_name,
          sku: item.sku,
          category: item.category || 'Unknown',
          qty: 1,
          note: item.note || '',
          amountPerUnit: item.fee || 0,
          total: item.fee || 0,
          image: item.product_image || item.photo_url  // Пріоритет: фото товару, потім фото пошкодження
        }],
        createdAt: item.created_at,
        createdBy: item.created_by || 'Unknown',
        returnDate: item.created_at
      }))
      
      setCases(transformedData)
      if (transformedData.length > 0 && !selectedId) {
        setSelectedId(transformedData[0].id)
      }
    } catch (error) {
      console.error('Error loading cases:', error)
      alert('Помилка завантаження кейсів')
    } finally {
      setLoading(false)
    }
  }

  const selected = useMemo(() => {
    if (!cases.length) return null
    if (!selectedId) return cases[0]
    return cases.find((c) => c.id === selectedId) || cases[0]
  }, [cases, selectedId])

  const filtered = useMemo(() => {
    return cases.filter((c) => {
      const linesText = (c.lines || []).map((l) => l.productName + l.sku + l.category + (l.note || '')).join(' ')
      const text = (
        c.id +
        (c.orderId || '') +
        c.clientName +
        (c.eventName || '') +
        linesText
      ).toLowerCase()
      const okQ = !q || text.includes(q.toLowerCase())
      const okStatus = statusFilter === 'all' || c.status === statusFilter
      const okSeverity = severityFilter === 'all' || c.severity === severityFilter
      const okSource = sourceFilter === 'all' || c.source === sourceFilter
      return okQ && okStatus && okSeverity && okSource
    })
  }, [cases, q, statusFilter, severityFilter, sourceFilter])

  const counters = useMemo(() => {
    const open = cases.filter((c) => c.status !== 'closed').length
    const awaitingClient = cases.filter((c) => c.status === 'awaiting_client').length
    const awaitingPayment = cases.filter((c) => c.status === 'awaiting_payment').length
    const inRepair = cases.filter((c) => c.status === 'in_repair').length
    const closed = cases.filter((c) => c.status === 'closed').length
    return { open, awaitingClient, awaitingPayment, inRepair, closed }
  }, [cases])

  const updateCaseStatus = async (id: string, status: DamageStatus) => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/damages/cases/${id}/status`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status })
      })
      if (response.ok) {
        setCases((prev) => prev.map((c) => (c.id === id ? { ...c, status } : c)))
        alert('✅ Статус оновлено')
      }
    } catch (error) {
      alert('Помилка оновлення статусу')
    }
  }

  const editLineAmount = async (caseId: string, lineId: string) => {
    const targetCase = cases.find((c) => c.id === caseId)
    if (!targetCase || !targetCase.lines) return
    const line = targetCase.lines.find((l) => l.id === lineId)
    if (!line) return
    const input = prompt(
      `Нова сума за одиницю (мінімум ${line.minAmount} грн) для «${line.productName}»?`,
      String(line.amountPerUnit),
    )
    if (!input) return
    const value = Number(input)
    if (isNaN(value) || value <= 0) {
      alert('Вкажіть коректну суму.')
      return
    }
    const amountPerUnit = Math.max(line.minAmount || 0, value)
    
    try {
      const response = await fetch(`${BACKEND_URL}/api/damages/cases/${caseId}/lines/${lineId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount_per_unit: amountPerUnit })
      })
      if (response.ok) {
        setCases((prev) =>
          prev.map((c) =>
            c.id === caseId
              ? {
                  ...c,
                  lines: (c.lines || []).map((ln) =>
                    ln.id === lineId
                      ? { ...ln, amountPerUnit, total: Math.round(amountPerUnit * ln.qty) }
                      : ln,
                  ),
                }
              : c,
          ),
        )
        alert('✅ Суму оновлено')
      }
    } catch (error) {
      alert('Помилка оновлення суми')
    }
  }

  const addLine = async (caseId: string) => {
    const productName = prompt('Назва предмета?')
    if (!productName) return
    const sku = prompt('SKU / код (можна пропустити)?') || ''
    const ruleLabel = prompt('Що трапилось? (коротко)') || 'Пошкодження'
    const minStr = prompt('Мінімальна сума згідно прайсу?', '500') || '500'
    const qtyStr = prompt('Кількість одиниць?', '1') || '1'
    const minAmount = Math.max(0, Number(minStr) || 0)
    const qty = Math.max(1, Number(qtyStr) || 1)

    try {
      const response = await fetch(`${BACKEND_URL}/api/damages/cases/${caseId}/lines`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          product_name: productName,
          sku,
          rule_label: ruleLabel,
          min_amount: minAmount,
          qty,
          amount_per_unit: minAmount
        })
      })
      if (response.ok) {
        await loadCases()
        alert('✅ Позицію додано')
      }
    } catch (error) {
      alert('Помилка додавання позиції')
    }
  }

  const openInFinance = (c: DamageCase) => {
    alert(
      `Мок: кейс ${c.id} буде відправлено у фінансовий кабінет (manager frontend) з прив'язкою до замовлення ${
        c.orderId || '—'
      }.`,
    )
  }

  const openInReaudit = (c: DamageCase) => {
    if (!c.fromReauditItemId) {
      alert('Для цього кейсу немає привʼязки до переобліку.')
      return
    }
    alert(`Мок: відкриємо кабінет переобліку з позицією ${c.fromReauditItemId}.`)
  }

  if (loading) {
    return <div className="p-6 text-sm text-corp-text-main">Завантаження...</div>
  }

  if (!selected) {
    return <div className="p-6 text-sm text-corp-text-main">Немає кейсів шкоди.</div>
  }

  const linesTotal = (selected.lines || []).reduce((s, l) => s + l.total, 0)
  const chargeFromDeposit = Math.min(selected.depositHold, linesTotal)
  const extraPayment = Math.max(0, linesTotal - selected.depositHold)

  return (
    <div className="mx-auto max-w-7xl p-6 space-y-5">
      {/* header */}
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          {onBackToDashboard && (
            <button
              onClick={onBackToDashboard}
              className="text-corp-text-main hover:text-corp-text-dark transition"
            >
              ← Назад
            </button>
          )}
          <div>
            <h1 className="text-2xl font-bold text-corp-text-dark">Кабінет шкоди PRO</h1>
            <p className="text-sm text-corp-text-muted">
              Усі кейси пошкоджень: від повернення, переобліку та каталогу. Розрахунок збитків і зв&apos;язок з фінансами.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[11px]">
          <Badge tone="amber">Відкриті кейси: {counters.open}</Badge>
          <Badge tone="amber">Чекаємо клієнта: {counters.awaitingClient}</Badge>
          <Badge tone="amber">Чекаємо оплату: {counters.awaitingPayment}</Badge>
          <Badge tone="blue">В реставрації: {counters.inRepair}</Badge>
          <Badge tone="green">Закрито: {counters.closed}</Badge>
        </div>
      </header>

      {/* filters & list */}
      <div className="grid gap-4 md:grid-cols-[minmax(0,1.25fr),minmax(0,1.75fr)]">
        <div className="space-y-3 text-[11px]">
          <div className="rounded-2xl border border-slate-200 bg-white p-3 space-y-2">
            <div className="flex flex-col gap-2 md:flex-row md:items-end">
              <div className="flex-1">
                <label className="block text-corp-text-muted">Пошук</label>
                <input
                  className="mt-1 w-full rounded-full border border-slate-200 bg-white px-3 py-1.5"
                  placeholder="Клієнт, замовлення, товар, кейс..."
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-corp-text-muted">Статус</label>
                <select
                  className="mt-1 w-40 rounded-full border border-slate-200 bg-white px-2 py-1.5"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value as any)}
                >
                  <option value="all">Усі</option>
                  <option value="draft">Чернетка</option>
                  <option value="awaiting_client">Очікуємо клієнта</option>
                  <option value="awaiting_payment">Очікуємо оплату</option>
                  <option value="in_repair">В реставрації</option>
                  <option value="closed">Закрито</option>
                </select>
              </div>
            </div>
            <div className="flex flex-col gap-2 md:flex-row md:items-end">
              <div>
                <label className="block text-corp-text-muted">Серйозність</label>
                <select
                  className="mt-1 w-40 rounded-full border border-slate-200 bg-white px-2 py-1.5"
                  value={severityFilter}
                  onChange={(e) => setSeverityFilter(e.target.value as any)}
                >
                  <option value="all">Усі</option>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </div>
              <div>
                <label className="block text-corp-text-muted">Джерело</label>
                <select
                  className="mt-1 w-40 rounded-full border border-slate-200 bg-white px-2 py-1.5"
                  value={sourceFilter}
                  onChange={(e) => setSourceFilter(e.target.value as any)}
                >
                  <option value="all">Усі</option>
                  <option value="return">Повернення</option>
                  <option value="reaudit">Переоблік</option>
                  <option value="other">Інше</option>
                </select>
              </div>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-corp-text-muted">
                У вибірці: <span className="font-semibold text-corp-text-dark">{filtered.length}</span> кейсів
              </div>
              <div className="flex gap-2">
                <PillButton tone="ghost" onClick={() => alert('Створення нового кейсу (TODO)')}>
                  + Новий кейс
                </PillButton>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden">
            <div className="border-b border-slate-100 px-3 py-2 text-[11px] text-corp-text-muted">Список кейсів</div>
            <div className="max-h-[360px] divide-y divide-slate-100 overflow-auto text-[11px]">
              {filtered.map((c) => {
                const sum = (c.lines || []).reduce((s, l) => s + l.total, 0)
                const fromDeposit = Math.min(c.depositHold, sum)
                const extra = Math.max(0, sum - c.depositHold)
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => setSelectedId(c.id)}
                    className={cls(
                      'flex w-full items-start justify-between gap-2 px-3 py-2 text-left hover:bg-slate-50',
                      selected?.id === c.id && 'bg-slate-900/5',
                    )}
                  >
                    <div className="flex-1">
                      <div className="flex flex-wrap items-center gap-1">
                        <span className="font-semibold text-corp-text-dark">{c.clientName}</span>
                        {c.orderId && <span className="text-[10px] text-corp-text-muted">· замовлення #{c.orderId}</span>}
                      </div>
                      <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[10px] text-corp-text-muted">
                        <span>{c.eventName || 'Без назви події'}</span>
                        <span>· кейс: {c.id}</span>
                        <span>· створено: {c.createdAt?.slice(0,10)}</span>
                      </div>
                      <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[10px]">
                        <StatusBadge status={c.status} />
                        <SeverityBadge severity={c.severity} />
                        {c.source === 'return' && <Badge tone="blue">з повернення</Badge>}
                        {c.source === 'reaudit' && <Badge tone="violet">з переобліку</Badge>}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1 text-[10px] text-corp-text-main">
                      <span>Збитки: ₴ {fmtUA(sum)}</span>
                      <span>Застава: ₴ {fmtUA(c.depositHold)}</span>
                      {extra > 0 ? (
                        <span className="text-rose-600">Дооплата: ₴ {fmtUA(extra)}</span>
                      ) : (
                        <span className="text-emerald-600">Покриває застава</span>
                      )}
                    </div>
                  </button>
                )
              })}
              {filtered.length === 0 && (
                <div className="px-3 py-6 text-center text-[11px] text-corp-text-muted">Кейсів за цими фільтрами немає</div>
              )}
            </div>
          </div>
        </div>

        {/* right: details */}
        <div className="space-y-3 text-[11px]">
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-semibold text-corp-text-dark">{selected.clientName}</span>
                  {selected.orderId && (
                    <span className="text-[11px] text-corp-text-muted">· замовлення #{selected.orderId}</span>
                  )}
                </div>
                <div className="mt-0.5 text-[11px] text-corp-text-muted">
                  {selected.eventName || 'Без назви події'} · повернення: {selected.returnDate?.slice(0,10) || '—'}
                </div>
                <div className="mt-0.5 text-[11px] text-corp-text-muted">
                  Створено: {selected.createdAt?.slice(0,10)} · {selected.createdBy}
                  {selected.source === 'reaudit' && <span> · створено з переобліку</span>}
                  {selected.fromReauditItemId && <span> · {selected.fromReauditItemId}</span>}
                </div>
              </div>
              <div className="flex flex-col items-end gap-1">
                <StatusBadge status={selected.status} />
                <SeverityBadge severity={selected.severity} />
                <div className="text-[10px] text-corp-text-muted">Кейс: {selected.id}</div>
              </div>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-3">
              <div className="rounded-xl bg-slate-50 p-3">
                <div className="text-corp-text-muted">Загальні збитки</div>
                <div className="mt-1 text-lg font-semibold text-corp-text-dark">₴ {fmtUA(linesTotal)}</div>
              </div>
              <div className="rounded-xl bg-slate-50 p-3">
                <div className="text-corp-text-muted">Застава по замовленню</div>
                <div className="mt-1 text-lg font-semibold text-corp-text-dark">₴ {fmtUA(selected.depositHold)}</div>
              </div>
              <div className="rounded-xl bg-slate-50 p-3">
                <div className="text-corp-text-muted">Розрахунок</div>
                <div className="mt-1 text-sm text-corp-text-dark">Застави списати: ₴ {fmtUA(chargeFromDeposit)}</div>
                <div className="text-sm text-corp-text-dark">
                  До доплати клієнтом: <span className={extraPayment > 0 ? 'text-rose-600' : ''}>₴ {fmtUA(extraPayment)}</span>
                </div>
              </div>
            </div>

            <div className="mt-4">
              {/* lines table */}
              <div className="mb-4">
                <div className="mb-2 flex items-center justify-between">
                  <div className="text-[11px] font-semibold text-corp-text-dark">Пошкоджені позиції ({(selected.lines || []).length})</div>
                  <PillButton tone="ghost" onClick={() => addLine(selected.id)}>
                    + Додати позицію
                  </PillButton>
                </div>
                <div className="max-h-[260px] overflow-auto rounded-xl border border-slate-200">
                  <table className="min-w-full text-[11px]">
                    <thead className="bg-slate-50 text-corp-text-muted">
                      <tr>
                        <th className="px-2 py-1 text-left">Фото</th>
                        <th className="px-2 py-1 text-left">Предмет</th>
                        <th className="px-2 py-1 text-left">Правило / опис</th>
                        <th className="px-2 py-1 text-right">К-сть</th>
                        <th className="px-2 py-1 text-right">Сума/шт</th>
                        <th className="px-2 py-1 text-right">Разом</th>
                        <th className="px-2 py-1 text-right">Дії</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(selected.lines || []).map((l) => (
                        <tr key={l.id} className="border-t border-slate-100 hover:bg-slate-50/60">
                          <td className="px-2 py-1 align-top">
                            {l.image ? (
                              <img 
                                src={getImageUrl(l.image) || ''} 
                                alt={l.productName}
                                className="w-12 h-12 object-cover rounded border border-slate-200"
                                onError={(e) => {
                                  (e.target as HTMLImageElement).src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="48" height="48"%3E%3Crect fill="%23e2e8f0" width="48" height="48"/%3E%3Ctext x="50%25" y="50%25" text-anchor="middle" dy=".3em" fill="%2394a3b8" font-size="10"%3ENo img%3C/text%3E%3C/svg%3E'
                                }}
                              />
                            ) : (
                              <div className="w-12 h-12 bg-slate-100 rounded flex items-center justify-center text-[9px] text-slate-400">
                                No img
                              </div>
                            )}
                          </td>
                          <td className="px-2 py-1 align-top">
                            <div className="font-semibold text-corp-text-dark">{l.productName}</div>
                            <div className="text-[10px] text-corp-text-muted">
                              SKU: {l.sku || '—'} {l.inventoryCode && <>· інв. {l.inventoryCode}</>}
                            </div>
                            <div className="text-[10px] text-corp-text-muted">{l.category}</div>
                          </td>
                          <td className="px-2 py-1 align-top text-corp-text-main">
                            <div>{l.ruleLabel || l.category || '-'}</div>
                            {l.minAmount !== undefined && (
                              <div className="text-[10px] text-slate-400">Мін. згідно прайсу: ₴ {fmtUA(l.minAmount)}</div>
                            )}
                            {l.note && <div className="mt-0.5 text-[10px] text-corp-text-muted">{l.note}</div>}
                            {l.fromReauditItemId && (
                              <div className="mt-0.5 text-[10px] text-violet-700">з переобліку: {l.fromReauditItemId}</div>
                            )}
                          </td>
                          <td className="px-2 py-1 align-top text-right text-corp-text-main">{l.qty}</td>
                          <td className="px-2 py-1 align-top text-right text-corp-text-main">₴ {fmtUA(l.amountPerUnit)}</td>
                          <td className="px-2 py-1 align-top text-right font-semibold text-corp-text-dark">
                            ₴ {fmtUA(l.total)}
                          </td>
                          <td className="px-2 py-1 align-top text-right">
                            <PillButton tone="ghost" onClick={() => editLineAmount(selected.id, l.id)}>
                              Змінити
                            </PillButton>
                          </td>
                        </tr>
                      ))}
                      {(selected.lines || []).length === 0 && (
                        <tr>
                          <td
                            colSpan={6}
                            className="px-3 py-4 text-center text-[11px] text-corp-text-muted"
                          >
                            Поки що немає позицій у цьому кейсі
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* actions */}
              <div className="mb-4">
                <div className="mb-2 text-[11px] font-semibold text-corp-text-dark">Швидкі дії</div>
                <div className="flex flex-wrap gap-2">
                  {selected.status === 'draft' && (
                    <PillButton
                      tone="amber"
                      onClick={() => setShowSendModal(true)}
                    >
                      📧 Відправити клієнту
                    </PillButton>
                  )}
                  {selected.status === 'awaiting_client' && (
                    <PillButton
                      tone="amber"
                      onClick={() => updateCaseStatus(selected.id, 'awaiting_payment')}
                    >
                      ✅ Клієнт погодив
                    </PillButton>
                  )}
                  {selected.status === 'awaiting_payment' && (
                    <PillButton
                      tone="green"
                      onClick={() => updateCaseStatus(selected.id, 'in_repair')}
                    >
                      💸 Оплату отримано
                    </PillButton>
                  )}
                  {selected.status === 'in_repair' && (
                    <PillButton tone="green" onClick={() => updateCaseStatus(selected.id, 'closed')}>
                      ✅ Закрити кейс
                    </PillButton>
                  )}
                  <PillButton tone="green" onClick={() => setShowTaskModal(true)}>
                    📋 Створити завдання
                  </PillButton>
                  {onNavigateToTasks && (
                    <PillButton tone="ghost" onClick={() => onNavigateToTasks(selected.id)}>
                      📋 Перейти до завдань
                    </PillButton>
                  )}
                  <PillButton tone="ghost" onClick={() => openInFinance(selected)}>
                    💰 Відкрити у фінкабінеті
                  </PillButton>
                  <PillButton tone="ghost" onClick={() => openInReaudit(selected)}>
                    📦 Відкрити у переобліку
                  </PillButton>
                  <PillButton tone="red" onClick={async () => {
                    if (!window.confirm(`⚠️ Видалити кейс "${selected.clientName}"?\n\nЦя дія:\n• Розморозить товар (якщо був заморожений)\n• Поверне кількість (якщо була повна втрата)\n• Видалить усі дані кейсу\n\nПродовжити?`)) {
                      return
                    }
                    
                    try {
                      const response = await fetch(`${BACKEND_URL}/api/damage-cases/${selected.id}`, {
                        method: 'DELETE'
                      })
                      const result = await response.json()
                      
                      if (result.success) {
                        alert(`✅ ${result.message}`)
                        // Видалити кейс зі списку
                        setCases(prev => prev.filter(c => c.id !== selected.id))
                        // Вибрати інший кейс або очистити
                        const remaining = cases.filter(c => c.id !== selected.id)
                        if (remaining.length > 0) {
                          setSelectedId(remaining[0].id)
                        } else {
                          setSelectedId('')
                        }
                      } else {
                        alert('❌ Помилка: ' + (result.detail || 'Не вдалося видалити кейс'))
                      }
                    } catch (error) {
                      console.error('Error deleting case:', error)
                      alert('❌ Помилка видалення кейсу')
                    }
                  }}>
                    🗑️ Видалити кейс
                  </PillButton>
                </div>
              </div>

              {/* notes */}
              <div>
                <div className="mb-2 text-[11px] font-semibold text-corp-text-dark">Внутрішня примітка</div>
                <textarea
                  rows={4}
                  defaultValue={selected.internalNote}
                  className="w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-[11px] text-slate-700"
                  placeholder="Що важливо знати..."
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Create Task Modal */}
      {showSendModal && selected && (
        <SendToClientModal
          damageCase={selected}
          onClose={() => setShowSendModal(false)}
          onSuccess={(method) => {
            setShowSendModal(false)
            updateCaseStatus(selected.id, 'awaiting_client')
            alert(`✅ Кейс відправлено клієнту через ${method === 'email' ? 'Email' : 'CallBell'}`)
          }}
        />
      )}

      {showTaskModal && selected && (
        <CreateTaskFromDamageModal
          damageCase={selected}
          onClose={() => setShowTaskModal(false)}
          onSuccess={() => {
            setShowTaskModal(false)
            // Оновити статус на "awaiting_completion" (чекає завершення)
            updateCaseStatus(selected.id, 'in_repair')
            alert('✅ Завдання створено! Кейс чекає завершення.')
          }}
        />
      )}
    </div>
  )
}

/*************** Send To Client Modal ***************/
function SendToClientModal({
  damageCase,
  onClose,
  onSuccess,
}: {
  damageCase: DamageCase
  onClose: () => void
  onSuccess: (method: 'email' | 'callbell') => void
}) {
  const [selectedMethod, setSelectedMethod] = useState<'email' | 'callbell'>('email')

  const handleSend = async () => {
    if (selectedMethod === 'email') {
      // TODO: Інтеграція з Email
      onSuccess('email')
    } else {
      // TODO: Інтеграція з CallBell
      alert('⚠️ Інтеграція з CallBell ще не налаштована')
      onSuccess('callbell')
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-white rounded-2xl w-full max-w-md m-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-semibold text-corp-text-dark mb-4">📧 Відправити клієнту</h3>
        
        <div className="space-y-3 mb-6">
          <div 
            className={cls(
              "p-4 rounded-xl border-2 cursor-pointer transition",
              selectedMethod === 'email' 
                ? "border-blue-500 bg-blue-50" 
                : "border-slate-200 hover:border-slate-300"
            )}
            onClick={() => setSelectedMethod('email')}
          >
            <div className="flex items-center gap-3">
              <div className="text-2xl">📧</div>
              <div>
                <div className="font-semibold text-corp-text-dark">Email (Лист)</div>
                <div className="text-sm text-corp-text-main">Відправити на email клієнта</div>
              </div>
            </div>
          </div>

          <div 
            className={cls(
              "p-4 rounded-xl border-2 cursor-pointer transition",
              selectedMethod === 'callbell' 
                ? "border-green-500 bg-green-50" 
                : "border-slate-200 hover:border-slate-300"
            )}
            onClick={() => setSelectedMethod('callbell')}
          >
            <div className="flex items-center gap-3">
              <div className="text-2xl">💬</div>
              <div>
                <div className="font-semibold text-corp-text-dark">CallBell</div>
                <div className="text-sm text-corp-text-main">Через бот і месенджери</div>
                <div className="text-xs text-amber-600 mt-1">⚠️ Інтеграція в розробці</div>
              </div>
            </div>
          </div>
        </div>

        <div className="flex gap-3">
          <button
            onClick={handleSend}
            className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-xl font-medium hover:bg-blue-700"
          >
            Відправити
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl border border-slate-300 text-slate-700 hover:bg-slate-50"
          >
            Скасувати
          </button>
        </div>
      </div>
    </div>
  )
}

/*************** Create Task Modal ***************/
function CreateTaskFromDamageModal({
  damageCase,
  onClose,
  onSuccess,
}: {
  damageCase: DamageCase
  onClose: () => void
  onSuccess: () => void
}) {
  const [formData, setFormData] = useState({
    title: `Реставрація - ${damageCase.clientName}`,
    description: `Реставрація пошкоджених позицій з кейсу ${damageCase.id}\n\n` +
      `Кількість позицій: ${(damageCase.lines || []).length}\n` +
      `Загальна сума шкоди: ₴${(damageCase.lines || []).reduce((sum, l) => sum + l.total, 0)}`,
    priority: 'high' as 'low' | 'medium' | 'high',
    assigned_to: '',
    due_date: '',
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const response = await fetch(`${BACKEND_URL}/api/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...formData,
          task_type: 'restoration',
          damage_id: damageCase.id,
          status: 'todo',
          due_date: formData.due_date ? new Date(formData.due_date).toISOString() : undefined,
        }),
      })

      if (!response.ok) throw new Error('Failed to create task')
      onSuccess()
    } catch (error) {
      console.error('Error creating task:', error)
      alert('Помилка створення завдання')
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-white rounded-2xl w-full max-w-xl m-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-corp-text-dark">🔧 Створити завдання на реставрацію</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-corp-text-main text-2xl leading-none"
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-slate-700 mb-1">Назва завдання</label>
            <input
              type="text"
              required
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label className="block text-sm text-slate-700 mb-1">Опис</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              rows={5}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-slate-700 mb-1">Пріоритет</label>
              <select
                value={formData.priority}
                onChange={(e) => setFormData({ ...formData, priority: e.target.value as any })}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="low">Низький</option>
                <option value="medium">Середній</option>
                <option value="high">Високий</option>
              </select>
            </div>

            <div>
              <label className="block text-sm text-slate-700 mb-1">Виконавець</label>
              <input
                type="text"
                value={formData.assigned_to}
                onChange={(e) => setFormData({ ...formData, assigned_to: e.target.value })}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                placeholder="Ім'я виконавця"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm text-slate-700 mb-1">Термін виконання</label>
            <input
              type="datetime-local"
              value={formData.due_date}
              onChange={(e) => setFormData({ ...formData, due_date: e.target.value })}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </div>

          <div className="flex gap-3 mt-6">
            <button
              type="submit"
              className="flex-1 bg-emerald-600 text-white rounded-lg py-2 font-medium hover:bg-emerald-700 transition"
            >
              ✅ Створити завдання
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-6 bg-slate-200 text-slate-700 rounded-lg py-2 font-medium hover:bg-slate-300 transition"
            >
              Скасувати
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
