import React, { useState, useEffect } from 'react'
import CorporateHeader from '../components/CorporateHeader'

/************** helpers **************/
const cls = (...a: (string | false | null | undefined)[]) => a.filter(Boolean).join(' ')

/************** types **************/
type OrderStatus = 'progress' | 'ready'

interface PackingOrder {
  id: string
  order_id: string
  order_number?: string
  client: string
  eventDate: string
  issueTime: string
  returnTime: string
  manager: string
  status: OrderStatus
  itemsCount: number
  skuCount: number
  progressPack: number
  warehouseZone: string
  notes: string
}

/************** small UI **************/
function Badge({ tone = 'slate', children }: { tone?: string; children: React.ReactNode }) {
  const tones: Record<string, string> = {
    slate: 'bg-slate-100 text-slate-700 border-slate-200',
    blue: 'bg-sky-100 text-sky-700 border-sky-200',
    green: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    amber: 'bg-amber-100 text-amber-800 border-amber-200',
    violet: 'bg-violet-100 text-violet-700 border-violet-200',
  }
  return (
    <span
      className={cls(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px]',
        tones[tone] || tones.slate,
      )}
    >
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
  tone?: string
}) {
  const tones: Record<string, string> = {
    slate: 'bg-slate-900 text-white hover:bg-slate-800',
    green: 'bg-emerald-600 text-white hover:bg-emerald-700',
    ghost: 'bg-transparent text-slate-700 hover:bg-slate-100 border border-slate-200',
  }
  return (
    <button
      type="button"
      onClick={onClick}
      className={cls('rounded-full px-3 py-1 text-[11px] font-medium transition', tones[tone] || tones.slate)}
    >
      {children}
    </button>
  )
}

function ProgressBar({ value }: { value: number }) {
  const v = Math.max(0, Math.min(100, value))
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
      <div className="h-full rounded-full bg-sky-500" style={{ width: `${v}%` }} />
    </div>
  )
}

/************** packing list (left column) **************/
function PackingList({ 
  orders, 
  selectedId, 
  onSelect,
  loading 
}: { 
  orders: PackingOrder[]
  selectedId: string | null
  onSelect: (id: string) => void
  loading: boolean
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-corp-text-dark">Ордери в комплектації</h2>
          <p className="text-[11px] text-corp-text-muted">Тільки збір і пакування на видачу · статус progress / ready.</p>
        </div>
        <div className="flex gap-2 text-[11px] text-corp-text-muted">
          <Badge tone="blue">в роботі: {orders.filter((o) => o.status === 'progress').length}</Badge>
          <Badge tone="green">готові: {orders.filter((o) => o.status === 'ready').length}</Badge>
        </div>
      </div>

      {loading ? (
        <div className="py-8 text-center text-sm text-corp-text-muted">Завантаження...</div>
      ) : orders.length === 0 ? (
        <div className="py-8 text-center text-sm text-corp-text-muted">Немає замовлень в комплектації</div>
      ) : (
        <div className="space-y-2 text-xs">
          {orders.map((o) => (
            <button
              key={o.id}
              type="button"
              onClick={() => onSelect(o.id)}
              className={cls(
                'flex w-full items-center justify-between gap-3 rounded-xl border px-3 py-2 text-left transition',
                selectedId === o.id ? 'border-slate-900 bg-slate-900/5' : 'border-slate-200 hover:border-slate-300',
              )}
            >
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-semibold text-corp-text-dark">#{o.order_id}</span>
                  <span className="text-[11px] text-corp-text-muted">{o.client}</span>
                </div>
                <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[10px] text-corp-text-muted">
                  <span>
                    {o.skuCount} SKU · {o.itemsCount} од.
                  </span>
                  <span>Зона: {o.warehouseZone}</span>
                </div>
              </div>
              <div className="flex flex-col items-end gap-1 text-[10px]">
                <span className="text-corp-text-muted">Евент: {o.eventDate}</span>
                <span className="text-corp-text-muted">Видача: {o.issueTime}</span>
                <span>
                  <Badge tone={o.status === 'ready' ? 'green' : 'blue'}>
                    {o.status === 'ready' ? 'Готово до видачі' : 'Комплектація'}
                  </Badge>
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

/************** details panel (right column) **************/
function PackingDetails({ 
  order, 
  loading,
  onMarkReady,
  onOpenIssueCard,
  onOpenReturnCard,
  onCreateChecklist,
  onFlagForDamage
}: { 
  order: PackingOrder | null
  loading: boolean
  onMarkReady: (orderId: string) => void
  onOpenIssueCard: (orderId: string) => void
  onOpenReturnCard: (orderId: string) => void
  onCreateChecklist: (orderId: string) => void
  onFlagForDamage: (orderId: string) => void
}) {
  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-4 text-sm text-corp-text-muted">
        Завантаження...
      </div>
    )
  }

  if (!order) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-4 text-sm text-corp-text-muted">
        Оберіть ордер ліворуч, щоб побачити деталі комплектації.
      </div>
    )
  }

  const isReady = order.status === 'ready'

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      {/* Header */}
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-corp-text-dark">Комплектація #{order.order_number || order.order_id}</h2>
          <p className="text-[11px] text-corp-text-muted">
            {order.client} · {order.itemsCount} од. ({order.skuCount} SKU) · {order.warehouseZone}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1 text-[10px] text-corp-text-muted">
          <span>Евент: {order.eventDate}</span>
          <span>Видача: {order.issueTime}</span>
          <span>Очікуване повернення: {order.returnTime}</span>
          <span>Менеджер: {order.manager}</span>
        </div>
      </div>

      {/* Блок: комплектація на видачу */}
      <div className="mb-4 rounded-xl bg-slate-50 p-3">
        <div className="mb-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-semibold text-corp-text-dark">Комплектація на видачу</span>
            <Badge tone={isReady ? 'green' : 'blue'}>
              {isReady ? 'Готово до видачі' : 'В роботі (progress)'}
            </Badge>
          </div>
          <span className="text-[11px] text-corp-text-muted">Прогрес: {order.progressPack}%</span>
        </div>
        <ProgressBar value={order.progressPack} />
        <div className="mt-2 grid gap-2 text-[11px] text-corp-text-main md:grid-cols-2">
          <ul className="space-y-1">
            <li>• Усі позиції знайдені на складі</li>
            <li>• Підтягнули з мийки/реставрації (якщо щось ще не повернулось)</li>
            <li>• Фірмові чохли / коробки використані де потрібно</li>
          </ul>
          <ul className="space-y-1">
            <li>• Кожен елемент промарковано по ордеру</li>
            <li>• Ордер стоїть у зоні видачі (рампа/видаткова зона)</li>
            <li>• Готово до передачі в картку видачі менеджера</li>
          </ul>
        </div>
        <div className="mt-2 rounded-lg bg-white/70 px-2 py-1 text-[11px] text-corp-text-main">
          <span className="font-semibold">Нотатка:</span> {order.notes}
        </div>
        <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
          {!isReady && (
            <PillButton
              tone="green"
              onClick={() => onMarkReady(order.id)}
            >
              Позначити як готове до видачі
            </PillButton>
          )}
          <PillButton
            onClick={() => onOpenIssueCard(order.id)}
          >
            Відкрити картку видачі
          </PillButton>
        </div>
      </div>

      {/* Блок: підготовка до повернення (логістика, не мийка) */}
      <div className="grid gap-3 md:grid-cols-2 text-[11px]">
        <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="font-semibold text-corp-text-dark">Підготовка до повернення</span>
          </div>
          <div className="space-y-1 text-corp-text-main">
            <div className="flex items-center justify-between">
              <span>Очікувана дата/час:</span>
              <span className="font-medium">{order.returnTime}</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Планова зона прийому:</span>
              <span className="font-medium">Зона B · Приймання повернень</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Обʼєм:</span>
              <span className="font-medium">
                {order.skuCount} SKU / {order.itemsCount} од.
              </span>
            </div>
          </div>
          <div className="mt-2 space-y-1 text-corp-text-main">
            <div className="font-semibold text-corp-text-dark">План дій для складу:</div>
            <ul className="space-y-1">
              <li>• Підготувати місце в зоні повернень</li>
              <li>• При необхідності — виділити додатковий простір біля рампи</li>
              <li>• Зафіксувати, якщо повернення буде кількома авто</li>
            </ul>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <PillButton
              tone="ghost"
              onClick={() => onCreateChecklist(order.id)}
            >
              Створити чекліст прийому
            </PillButton>
            <PillButton
              tone="ghost"
              onClick={() => onOpenReturnCard(order.id)}
            >
              Відкрити картку повернення
            </PillButton>
          </div>
        </div>

        <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="font-semibold text-corp-text-dark">Звʼязок з кабінетом шкоди</span>
          </div>
          <div className="space-y-1 text-corp-text-main">
            <p>
              Після фактичного повернення ордера комірник у картці повернення зможе створити кейс шкоди, якщо декор
              повернувся брудний або пошкоджений.
            </p>
            <p>
              Тут комплектація тільки планує, де це буде складено, і фіксує, що ордер чекаємо назад у конкретну зону.
            </p>
          </div>
          <div className="mt-2 space-y-1 text-corp-text-main">
            <div className="font-semibold text-corp-text-dark">Що побачить склад після повернення:</div>
            <ul className="space-y-1">
              <li>• Статус прийому: ок / є підозра на шкоду</li>
              <li>• Якщо є шкода — лінк на кейс у кабінеті шкоди</li>
              <li>• Інформація, чи дозволено повертати заставу повністю або частково</li>
            </ul>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <PillButton
              tone="ghost"
              onClick={() => onFlagForDamage(order.id)}
            >
              Помітити для перевірки шкоди
            </PillButton>
          </div>
        </div>
      </div>
    </div>
  )
}

/************** main component **************/
export default function PackingCabinet({ 
  onBackToDashboard, 
  onNavigateToTasks,
  initialOrderId
}: { 
  onBackToDashboard: () => void
  onNavigateToTasks?: (orderId: string, orderNumber: string) => void
  initialOrderId?: string
}) {
  const [orders, setOrders] = useState<PackingOrder[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [selectedOrder, setSelectedOrder] = useState<PackingOrder | null>(null)
  const [loading, setLoading] = useState(false)
  const [detailsLoading, setDetailsLoading] = useState(false)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [zoneFilter, setZoneFilter] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState<string>('')

  const API_URL = process.env.REACT_APP_BACKEND_URL

  // Завантажити список замовлень
  const loadOrders = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (statusFilter !== 'all') params.append('status', statusFilter)
      if (zoneFilter !== 'all') params.append('zone', zoneFilter)
      if (searchQuery) params.append('search', searchQuery)

      const response = await fetch(`${API_URL}/api/warehouse/packing-orders?${params}`)
      const data = await response.json()
      
      // Перевірити чи data це масив
      if (Array.isArray(data)) {
        setOrders(data)
        
        // Автоматично вибрати перший
        if (data.length > 0 && !selectedId) {
          setSelectedId(data[0].id)
        }
      } else {
        console.error('API returned non-array:', data)
        setOrders([])
      }
    } catch (error) {
      console.error('Помилка завантаження замовлень:', error)
      setOrders([])
    } finally {
      setLoading(false)
    }
  }

  // Завантажити деталі вибраного замовлення
  const loadOrderDetails = async (orderId: string) => {
    setDetailsLoading(true)
    try {
      const response = await fetch(`${API_URL}/api/warehouse/packing-orders/${orderId}`)
      const data = await response.json()
      setSelectedOrder(data)
    } catch (error) {
      console.error('Помилка завантаження деталей:', error)
    } finally {
      setDetailsLoading(false)
    }
  }

  // Ефекти
  useEffect(() => {
    loadOrders()
  }, [statusFilter, zoneFilter, searchQuery])

  useEffect(() => {
    if (selectedId) {
      loadOrderDetails(selectedId)
    }
  }, [selectedId])

  // Дії
  const handleMarkReady = async (orderId: string) => {
    try {
      const response = await fetch(`${API_URL}/api/warehouse/packing-orders/${orderId}/mark-ready`, {
        method: 'PUT'
      })
      const data = await response.json()
      
      if (data.success) {
        alert('✅ Замовлення позначено як готове до видачі!')
        loadOrders()
        loadOrderDetails(orderId)
      }
    } catch (error) {
      console.error('Помилка:', error)
      alert('❌ Помилка позначення готовності')
    }
  }

  const handleOpenIssueCard = (orderId: string) => {
    alert(`Мок: відкрити повну картку видачі цього ордера у кабінеті менеджера (Issue Card: ${orderId}).`)
  }

  const handleOpenReturnCard = (orderId: string) => {
    alert(`Мок: відкрити картку повернення цього ордера (Return Card) у кабінеті комірника для ${orderId}.`)
  }

  const handleCreateChecklist = async (orderId: string) => {
    try {
      const response = await fetch(`${API_URL}/api/warehouse/packing-orders/${orderId}/return-checklist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes: 'Чекліст створено автоматично' })
      })
      const data = await response.json()
      
      if (data.success) {
        alert('✅ Чекліст прийому створено!')
      }
    } catch (error) {
      console.error('Помилка:', error)
      alert('❌ Помилка створення чекліста')
    }
  }

  const handleFlagForDamage = (orderId: string) => {
    alert(`Мок: позначити, що після повернення треба перевірити цей ордер на можливі пошкодження (${orderId}).`)
  }

  return (
    <div className="min-h-screen bg-corp-bg-main">
      <CorporateHeader cabinetName="Кабінет комплектації" showBackButton={true} onBackClick={onBackToDashboard} />
      
      <div className="mx-auto max-w-7xl p-6">
        <div className="mb-4">
          <p className="text-sm text-corp-text-muted">
            Збір і пакування на видачу + планування повернення. Без мийки/сушки — це окремо в кабінеті шкоди.
          </p>
        </div>

      <div className="mb-4 flex flex-wrap items-center gap-3 text-[11px] text-corp-text-muted">
        <div className="flex items-center gap-2">
          <span>Фільтр по статусу:</span>
          <select 
            className="rounded-full border border-slate-200 bg-white px-3 py-1"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">Всі</option>
            <option value="progress">В роботі (progress)</option>
            <option value="ready">Готово до видачі</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <span>Склад:</span>
          <select 
            className="rounded-full border border-slate-200 bg-white px-3 py-1"
            value={zoneFilter}
            onChange={(e) => setZoneFilter(e.target.value)}
          >
            <option value="all">Усі зони</option>
            <option value="A">Зона A</option>
            <option value="B">Зона B</option>
            <option value="C">Зона C</option>
          </select>
        </div>
        <div className="flex-1" />
        <div className="flex items-center gap-2">
          <input
            className="w-48 rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px]"
            placeholder="Пошук по #, клієнту, менеджеру..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <PackingList 
          orders={orders}
          selectedId={selectedId} 
          onSelect={setSelectedId}
          loading={loading}
        />
        <PackingDetails 
          order={selectedOrder}
          loading={detailsLoading}
          onMarkReady={handleMarkReady}
          onOpenIssueCard={handleOpenIssueCard}
          onOpenReturnCard={handleOpenReturnCard}
          onCreateChecklist={handleCreateChecklist}
          onFlagForDamage={handleFlagForDamage}
        />
      </div>

      <div className="mt-4 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-3 text-[11px] text-corp-text-muted">
        У реальній системі цей кабінет повʼязаний з: календарем реквізитора, карткою видачі (готовність до видачі) та
        кабінетом шкоди (після фактичного повернення і фіксації стану декору).
      </div>
      </div>
    </div>
  )
}
