import React, { useMemo, useState, useEffect } from 'react'

const cls = (...a: (string | false | null | undefined)[]) => a.filter(Boolean).join(' ')
const fmtUA = (n: number) => (Number(n) || 0).toLocaleString('uk-UA', { maximumFractionDigits: 0 })
const todayISO = () => new Date().toISOString().slice(0, 10)

type AuditStatus = 'ok' | 'minor' | 'critical' | 'lost'

interface AuditItem {
  id: string
  product_id: number
  code: string
  name: string
  category: string
  zone: string
  location: string
  qty: number
  status: AuditStatus
  lastAuditDate: string
  lastAuditBy?: string
  nextAuditDate?: string
  daysFromLastAudit: number
  rentalsCount: number
  lastOrderId?: string
  damagesCount: number
  totalProfit: number
  notes?: string
}

function Badge({ tone = 'slate', children }: { tone?: string; children: React.ReactNode }) {
  const tones: Record<string, string> = {
    slate: 'bg-slate-100 text-slate-700 border-slate-200',
    green: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    blue: 'bg-sky-100 text-sky-700 border-sky-200',
    amber: 'bg-amber-100 text-amber-800 border-amber-200',
    red: 'bg-rose-100 text-rose-700 border-rose-200',
  }
  return (
    <span className={cls('inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px]', tones[tone] || tones.slate)}>
      {children}
    </span>
  )
}

function PillButton({ children, onClick, tone = 'slate' }: { children: React.ReactNode; onClick?: () => void; tone?: string }) {
  const tones: Record<string, string> = {
    slate: 'bg-slate-900 text-white hover:bg-slate-800',
    green: 'bg-emerald-600 text-white hover:bg-emerald-700',
    red: 'bg-rose-600 text-white hover:bg-rose-700',
    amber: 'bg-amber-500 text-corp-text-dark hover:bg-amber-600',
    ghost: 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-50',
  }
  return (
    <button type="button" onClick={onClick} className={cls('rounded-full px-3 py-1 text-[11px] font-medium transition', tones[tone])}>
      {children}
    </button>
  )
}

function StatusCell({ status }: { status: AuditStatus }) {
  if (status === 'ok') return <span className="text-emerald-700">✅ задовільний</span>
  if (status === 'minor') return <span className="text-amber-700">⚠️ потребує уваги</span>
  if (status === 'critical') return <span className="text-rose-700">❗ критично</span>
  return <span className="font-semibold text-rose-800">⛔ втрачено</span>
}

function RiskBadge({ item }: { item: AuditItem }) {
  const overdue = item.daysFromLastAudit > 180
  const manyDamages = item.damagesCount >= 3

  if (item.status === 'lost') return <Badge tone="red">Ризик: втрачено</Badge>
  if (item.status === 'critical') return <Badge tone="red">Ризик: критичний стан</Badge>
  if (overdue && manyDamages) return <Badge tone="red">Ризик: перевірити негайно</Badge>
  if (overdue) return <Badge tone="amber">Потрібен переоблік</Badge>
  if (manyDamages) return <Badge tone="amber">Часта шкода</Badge>
  return <Badge tone="green">Ризик низький</Badge>
}

export default function ReauditCabinet({ onBackToDashboard }: { onBackToDashboard: () => void }) {
  const [items, setItems] = useState<AuditItem[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [q, setQ] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | AuditStatus>('all')
  const [stats, setStats] = useState({ total: 0, ok: 0, minor: 0, crit: 0, lost: 0, overdueCnt: 0 })

  const API_URL = process.env.REACT_APP_API_URL

  const loadItems = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (q) params.append('q', q)
      if (statusFilter !== 'all') params.append('status', statusFilter)
      
      const response = await fetch(`${API_URL}/api/audit/items?${params}`)
      const data = await response.json()
      
      if (data.items && Array.isArray(data.items)) {
        setItems(data.items)
        if (data.items.length > 0 && !selectedId) {
          setSelectedId(data.items[0].id)
        }
      }
    } catch (error) {
      console.error('Error:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadStats = async () => {
    try {
      const response = await fetch(`${API_URL}/api/audit/stats`)
      const data = await response.json()
      setStats(data)
    } catch (error) {
      console.error('Error loading stats:', error)
    }
  }

  useEffect(() => {
    loadItems()
    loadStats()
  }, [q, statusFilter])

  const selected = useMemo(() => {
    if (!selectedId) return items[0] || null
    return items.find((i) => i.id === selectedId) || items[0] || null
  }, [items, selectedId])

  const markAudited = async (item: AuditItem) => {
    const days = prompt('Наступний переоблік через (днів)?', '180')
    
    try {
      // Використовуємо НОВИЙ робочий endpoint
      const response = await fetch(`${API_URL}/api/audit/items/${item.id}/mark-as-audited`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          audited_by: 'Реквізитор',
          audit_status: 'ok',
          notes: 'Переоблік проведено',
          next_audit_days: days || '180'
        })
      })
      
      const data = await response.json()
      if (data.success) {
        alert('✅ Переоблік зафіксовано!')
        loadItems()
      }
    } catch (error) {
      console.error('Error:', error)
      alert('❌ Помилка')
    }
  }

  const totalProfit = items.reduce((s, i) => s + i.totalProfit, 0)

  return (
    <div className="mx-auto max-w-7xl p-6 space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-corp-text-dark">Кабінет переобліку PRO</h1>
          <p className="text-sm text-corp-text-muted">Контроль стану декору, циклу використання та ризиків</p>
        </div>
        <button
          onClick={onBackToDashboard}
          className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] text-slate-700 hover:bg-slate-50"
        >
          ← До дашборду
        </button>
      </header>

      {/* KPIs */}
      <div className="grid gap-3 md:grid-cols-5 text-[11px]">
        <div className="rounded-2xl border border-slate-200 bg-white p-3">
          <div className="text-corp-text-muted">Позицій в аудиті</div>
          <div className="mt-1 text-xl font-semibold">{stats.total}</div>
        </div>
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-3">
          <div className="text-emerald-700">Задовільний стан</div>
          <div className="mt-1 text-xl font-semibold">{stats.ok}</div>
        </div>
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3">
          <div className="text-amber-700">Потребують уваги</div>
          <div className="mt-1 text-xl font-semibold">{stats.minor + stats.crit}</div>
        </div>
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-3">
          <div className="text-rose-700">Втрати / критичні</div>
          <div className="mt-1 text-xl font-semibold">{stats.crit + stats.lost}</div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-3">
          <div className="text-corp-text-muted">Сумарний дохід</div>
          <div className="mt-1 text-xl font-semibold">₴ {fmtUA(totalProfit)}</div>
        </div>
      </div>

      {/* Main grid */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Left: List */}
        <div className="space-y-3">
          <div className="rounded-2xl border border-slate-200 bg-white p-3 text-[11px] space-y-2">
            <input
              className="w-full rounded-full border border-slate-200 bg-white px-3 py-1.5"
              placeholder="Пошук..."
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
            <select
              className="w-full rounded-full border border-slate-200 bg-white px-3 py-1.5"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as any)}
            >
              <option value="all">Усі статуси</option>
              <option value="ok">Ок</option>
              <option value="minor">Потребує уваги</option>
              <option value="critical">Критично</option>
              <option value="lost">Втрачено</option>
            </select>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden">
            <div className="border-b border-slate-100 px-3 py-2 text-[11px] text-corp-text-muted">
              Позиції ({items.length})
            </div>
            {loading ? (
              <div className="p-8 text-center text-sm text-corp-text-muted">Завантаження...</div>
            ) : (
              <div className="max-h-[400px] overflow-auto divide-y divide-slate-100 text-[11px]">
                {items.map((it) => (
                  <button
                    key={it.id}
                    onClick={() => setSelectedId(it.id)}
                    className={cls(
                      'flex w-full items-start justify-between gap-2 px-3 py-2 text-left hover:bg-slate-50',
                      selected?.id === it.id && 'bg-slate-900/5'
                    )}
                  >
                    <div className="flex-1">
                      <div className="font-semibold text-corp-text-dark">{it.name}</div>
                      <div className="mt-0.5 text-[10px] text-corp-text-muted">
                        {it.code} · {it.zone} · {it.location}
                      </div>
                      <div className="mt-1 flex gap-2">
                        <StatusCell status={it.status} />
                        <RiskBadge item={it} />
                      </div>
                    </div>
                    <div className="text-[10px] text-corp-text-muted">
                      <div>К-сть: {it.qty}</div>
                      <div>{it.daysFromLastAudit} днів тому</div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: Details */}
        {selected && (
          <div className="rounded-2xl border border-slate-200 bg-white p-4 space-y-3 text-[11px]">
            <div>
              <div className="text-sm font-semibold text-corp-text-dark">{selected.name}</div>
              <div className="text-[10px] text-corp-text-muted">{selected.code} · {selected.zone} · {selected.location}</div>
              <div className="mt-2 flex gap-2">
                <StatusCell status={selected.status} />
                <RiskBadge item={selected} />
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-xl bg-slate-50 p-3">
                <div className="text-corp-text-muted">Кількість</div>
                <div className="mt-1 text-lg font-semibold">{selected.qty}</div>
              </div>
              <div className="rounded-xl bg-slate-50 p-3">
                <div className="text-corp-text-muted">В оренді</div>
                <div className="mt-1 text-lg font-semibold">{selected.rentalsCount} разів</div>
              </div>
              <div className="rounded-xl bg-slate-50 p-3">
                <div className="text-corp-text-muted">Кейси шкоди</div>
                <div className="mt-1 text-lg font-semibold">{selected.damagesCount}</div>
              </div>
            </div>

            <div>
              <div className="mb-1 font-semibold text-corp-text-dark">Чек-лист</div>
              <ul className="space-y-1 text-corp-text-main">
                <li>▢ Перевірити кількість</li>
                <li>▢ Оглянути стан</li>
                <li>▢ Комплектація</li>
                <li>▢ Зафіксувати фото</li>
              </ul>
            </div>

            <div className="flex gap-2">
              <PillButton tone="green" onClick={() => markAudited(selected)}>
                ✅ Зафіксувати переоблік
              </PillButton>
              <PillButton tone="ghost" onClick={() => alert('Мок: відправити на мийку')}>
                🧹 Мийка
              </PillButton>
            </div>

            <div>
              <div className="mb-1 font-semibold">Примітка</div>
              <textarea
                rows={3}
                defaultValue={selected.notes}
                className="w-full rounded-xl border border-slate-200 px-3 py-1.5"
                placeholder="Нотатки..."
              />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
