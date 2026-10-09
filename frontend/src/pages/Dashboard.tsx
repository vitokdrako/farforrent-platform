import React, { useState, useEffect } from 'react'
import { warehouseAPI } from '../api/client'

// Small helpers
const cls = (...a: (string | false | null | undefined)[]) => a.filter(Boolean).join(' ')
const hours = Array.from({ length: 12 }, (_, i) => 8 + i) // 08–19

interface OrderCard {
  id: string
  order_id?: string
  type: 'issue' | 'return'
  time: string
  date?: string
  client: string
  label: string
  color: string
  status: string
  itemsSummary: string
  itemsCount: number
  warehouseZone: string
}

function TopTiles({ active, onTileClick }: { active: string; onTileClick: (key: string) => void }) {
  // Get user role from localStorage
  const user = JSON.parse(localStorage.getItem('user') || '{}')
  const isManager = user.role === 'manager' || user.role === 'admin'
  const isRequisitioner = user.role === 'requisitioner' || user.role === 'admin'
  
  const tiles = [
    // Manager only tiles
    ...(isManager ? [
      {
        key: 'orders',
        title: '📦 Замовлення',
        desc: 'Створення та управління замовленнями',
        icon: '📦',
      },
      {
        key: 'catalog',
        title: '📚 Каталог',
        desc: 'Товари, категорії, ціни',
        icon: '📚',
      },
    ] : []),
    // Requisitioner only tiles
    ...(isRequisitioner ? [
      {
        key: 'audit',
        title: '🔍 Переоблік',
        desc: 'Каталог реквізиту, стан декору, історія оренд',
        icon: '🔍',
      },
    ] : []),
    // Common tiles
    {
      key: 'damage',
      title: '⚠️ Шкоди PRO',
      desc: 'Кейси після повернення, реставрація, списання',
      icon: '⚠️',
    },
    {
      key: 'tasks',
      title: '🧾 Завдання PRO',
      desc: 'Kanban дошка, мийка, збір, пакування',
      icon: '🧾',
    },
  ]

  return (
    <div className="mb-4 grid gap-4 md:grid-cols-4">
      {tiles.map((t) => (
        <div
          key={t.key}
          onClick={() => onTileClick(t.key)}
          className={cls(
            'cursor-pointer rounded-2xl border bg-white p-4 shadow-sm transition',
            active === t.key
              ? 'border-slate-900 shadow-md'
              : 'border-slate-200 hover:border-slate-300',
          )}
        >
          <div className="mb-2 flex items-center justify-between">
            <div className="text-2xl">{t.icon}</div>
            {active === t.key && (
              <span className="rounded-full bg-slate-900 px-2 py-0.5 text-xs text-white">активно</span>
            )}
          </div>
          <div className="text-sm font-semibold text-corp-text-dark">{t.title}</div>
          <div className="mt-1 text-xs text-corp-text-muted">{t.desc}</div>
        </div>
      ))}
    </div>
  )
}

function CalendarToolbar({ view, setView, date, setDate }: any) {
  const formatDate = (d: Date) =>
    d.toLocaleDateString('uk-UA', { weekday: 'short', day: '2-digit', month: 'short' })

  const shift = (delta: number) => {
    const d = new Date(date)
    d.setDate(d.getDate() + (view === 'day' ? delta : delta * 7))
    setDate(d)
  }

  return (
    <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-2 text-sm">
        <button
          onClick={() => shift(-1)}
          className="rounded-full border border-slate-200 px-2 py-1 text-xs text-corp-text-main hover:bg-slate-50"
        >
          ◀
        </button>
        <button
          onClick={() => setDate(new Date())}
          className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-700 hover:bg-slate-50"
        >
          Сьогодні
        </button>
        <button
          onClick={() => shift(1)}
          className="rounded-full border border-slate-200 px-2 py-1 text-xs text-corp-text-main hover:bg-slate-50"
        >
          ▶
        </button>
        <div className="ml-2 text-sm font-medium text-corp-text-dark">{formatDate(date)}</div>
      </div>

      <div className="flex items-center gap-2 text-xs">
        <span className="text-corp-text-muted">Вигляд:</span>
        <button
          onClick={() => setView('day')}
          className={cls(
            'rounded-full px-3 py-1',
            view === 'day' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700',
          )}
        >
          День
        </button>
        <button
          onClick={() => setView('week')}
          className={cls(
            'rounded-full px-3 py-1',
            view === 'week' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700',
          )}
        >
          Тиждень
        </button>
      </div>
    </div>
  )
}

function OrderCardComponent({ card, onOpenFull }: { card: OrderCard; onOpenFull?: (card: OrderCard) => void }) {
  const palette: Record<string, string> = {
    emerald: 'bg-emerald-100 text-emerald-800 border-emerald-200',
    amber: 'bg-amber-100 text-amber-800 border-amber-200',
    sky: 'bg-sky-100 text-sky-800 border-sky-200',
  }
  const statusLabel: Record<string, string> = {
    scheduled: 'Заплановано',
    progress: 'Комплектація',
    done: 'Завершено',
    issued: 'Видано',
    pending: 'Очікує',
  }

  const statusTone =
    card.status === 'progress'
      ? 'bg-sky-800/80 text-white'
      : card.status === 'done' || card.status === 'issued'
      ? 'bg-emerald-800/80 text-white'
      : 'bg-slate-900/80 text-white'

  return (
    <div
      className={cls(
        'mb-1 flex cursor-pointer flex-col gap-1 rounded-xl border px-2 py-1 text-[11px] shadow-sm hover:shadow-md transition',
        palette[card.color] || 'bg-slate-100 text-corp-text-dark border-slate-200',
      )}
      onClick={(e) => {
        // Open full card on click
        if (onOpenFull && !e.defaultPrevented) {
          onOpenFull(card);
        }
      }}
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData('text/plain', JSON.stringify({ id: card.id, type: card.type }))
      }}
    >
      <div className="flex items-start gap-2">
        <div className="flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="font-semibold text-xs">{card.label}</span>
            <span className="text-[10px] opacity-80">{card.time}</span>
          </div>
          <div className="truncate text-[10px] mt-0.5">{card.client}</div>
          <div className="flex items-center gap-2 text-[9px] opacity-80 mt-1">
            <span>#{card.order_id || card.id}</span>
            <span className={cls('rounded-full px-1.5 py-0.5 text-[8px]', statusTone)}>
              {statusLabel[card.status] ?? 'Статус'}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

function DayGrid({ view, cards, onDrop, onOpenCard }: { view: 'day' | 'week', cards: OrderCard[], onDrop: (data: any, slot: any) => void, onOpenCard?: (card: OrderCard) => void }) {
  const onDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
  }

  if (view === 'week') {
    const days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Нд']
    return (
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <div className="grid grid-cols-7 border-b border-slate-100 bg-slate-50 text-xs font-medium text-corp-text-main">
          {days.map((d) => (
            <div key={d} className="px-2 py-2 text-center">
              {d}
            </div>
          ))}
        </div>
        <div className="grid h-[420px] grid-cols-7 text-xs">
          {days.map((d, idx) => (
            <div
              key={d}
              className="border-l border-slate-100 first:border-l-0"
              onDragOver={onDragOver}
              onDrop={(e) => {
                const data = JSON.parse(e.dataTransfer.getData('text/plain'))
                onDrop(data, { day: d, dayIndex: idx })
              }}
            >
              <div className="h-full p-1">
                {idx === 0 && (
                  <div className="space-y-1">
                    {cards.map((c) => (
                      <OrderCardComponent key={c.id} card={c} onOpenFull={onOpenCard} />
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  // Денний вигляд
  const issueCards = cards.filter((c) => c.type === 'issue')
  const returnCards = cards.filter((c) => c.type === 'return')

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <div className="grid grid-cols-[60px,1fr,1fr] border-b border-slate-100 bg-slate-50 text-xs font-medium text-corp-text-main">
        <div className="px-2 py-2" />
        <div className="px-2 py-2">Видача</div>
        <div className="px-2 py-2 border-l border-slate-100">Повернення</div>
      </div>
      <div className="h-[480px] overflow-y-auto text-xs">
        {hours.map((h) => (
          <div key={h} className="grid grid-cols-[60px,1fr,1fr] border-t border-slate-100 last:border-b">
            <div className="px-2 py-3 text-[11px] text-slate-400">{h.toString().padStart(2, '0')}:00</div>
            <div
              className="border-l border-slate-100 px-2 py-2"
              onDragOver={onDragOver}
              onDrop={(e) => {
                const data = JSON.parse(e.dataTransfer.getData('text/plain'))
                onDrop(data, { hour: h, type: 'issue' })
              }}
            >
              {issueCards
                .filter(c => parseInt(c.time.split(':')[0]) === h)
                .map(c => <OrderCardComponent key={c.id} card={c} onOpenFull={onOpenCard} />)
              }
            </div>
            <div
              className="border-l border-slate-100 px-2 py-2"
              onDragOver={onDragOver}
              onDrop={(e) => {
                const data = JSON.parse(e.dataTransfer.getData('text/plain'))
                onDrop(data, { hour: h, type: 'return' })
              }}
            >
              {returnCards
                .filter(c => parseInt(c.time.split(':')[0]) === h)
                .map(c => <OrderCardComponent key={c.id} card={c} onOpenFull={onOpenCard} />)
              }
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function RentalHubRekvisitorDashboard({ 
  onNavigateToCatalog,
  onNavigateToAudit,
  onNavigateToDamage,
  onNavigateToTasks,
  onNavigateToOrders,
  onNavigateToFinance,
  onNavigateToCatalogBoard
}: { 
  onNavigateToCatalog?: () => void
  onNavigateToAudit?: () => void
  onNavigateToDamage?: () => void
  onNavigateToTasks?: () => void
  onNavigateToOrders?: () => void
  onNavigateToFinance?: () => void
  onNavigateToCatalogBoard?: () => void
}) {
  const [view, setView] = useState<'day' | 'week'>('day')
  const [date, setDate] = useState<Date>(new Date())
  const [cards, setCards] = useState<OrderCard[]>([])
  const [dashboardStats, setDashboardStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [selectedCard, setSelectedCard] = useState<OrderCard | null>(null)

  useEffect(() => {
    loadDashboard()
    loadCalendar()
  }, [date])

  const loadDashboard = async () => {
    try {
      const data = await warehouseAPI.getDashboard(date.toISOString().split('T')[0])
      setDashboardStats(data)
    } catch (error) {
      console.error('Error loading dashboard:', error)
    }
  }

  const loadCalendar = async () => {
    try {
      setLoading(true)
      const fromDate = new Date(date)
      const toDate = new Date(date)
      
      if (view === 'week') {
        toDate.setDate(toDate.getDate() + 7)
      }

      const data = await warehouseAPI.getCalendar(
        fromDate.toISOString().split('T')[0],
        toDate.toISOString().split('T')[0],
        view
      )
      
      setCards(data.events || [])
    } catch (error) {
      console.error('Error loading calendar:', error)
      // Fallback to empty if error
      setCards([])
    } finally {
      setLoading(false)
    }
  }

  const handleDrop = async (dragData: any, slot: any) => {
    try {
      const newTime = slot.hour ? `${slot.hour.toString().padStart(2, '0')}:00` : '10:00'
      const newDate = date.toISOString().split('T')[0]
      
      await warehouseAPI.moveEvent(dragData.id, dragData.type, newDate, newTime)
      loadCalendar() // Reload
    } catch (error) {
      console.error('Error moving event:', error)
      alert('Помилка переміщення події')
    }
  }

  return (
    <div className="mx-auto max-w-7xl p-6">
      {/* Header */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-corp-text-dark">RentalHub Warehouse</h1>
          <p className="text-sm text-corp-text-muted">
            Дашборд реквізитора: календар видачі та повернення, швидкий доступ до каталогу, шкод і завдань.
          </p>
        </div>
        {dashboardStats && (
          <div className="flex gap-2 text-xs text-corp-text-muted">
            <div className="rounded-full bg-emerald-50 px-3 py-1 text-emerald-700">
              {dashboardStats.quick_summary || 'Завантаження...'}
            </div>
          </div>
        )}
      </div>

      {/* Top navigation tiles */}
      <TopTiles 
        active="" 
        onTileClick={(key) => {
          if (key === 'catalog' && onNavigateToCatalog) {
            onNavigateToCatalog()
          } else if (key === 'audit' && onNavigateToAudit) {
            onNavigateToAudit()
          } else if (key === 'damage' && onNavigateToDamage) {
            onNavigateToDamage()
          } else if (key === 'tasks' && onNavigateToTasks) {
            onNavigateToTasks()
          } else if (key === 'orders' && onNavigateToOrders) {
            onNavigateToOrders()
          } else if (key === 'finance' && onNavigateToFinance) {
            onNavigateToFinance()
          } else if (key === 'catalog' && onNavigateToCatalogBoard) {
            onNavigateToCatalogBoard()
          } else {
            alert(`Перехід до розділу: ${key}`)
          }
        }}
      />

      {/* Filters row */}
      <div className="mb-4 flex flex-wrap items-center gap-3 text-xs">
        <div className="flex items-center gap-2">
          <span className="text-corp-text-muted">Склад:</span>
          <select className="rounded-full border border-slate-200 bg-white px-3 py-1">
            <option>Основний склад</option>
            <option>Склад текстилю</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-corp-text-muted">Комірник:</span>
          <select className="rounded-full border border-slate-200 bg-white px-3 py-1">
            <option>Всі</option>
            <option>Олег</option>
            <option>Оксана</option>
          </select>
        </div>
        <div className="flex-1" />
        <div className="flex items-center gap-2">
          <input
            className="w-40 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs"
            placeholder="Пошук по #, клієнту..."
          />
        </div>
      </div>

      {/* Main calendar card */}
      <div className="rounded-2xl bg-slate-50 p-4">
        <CalendarToolbar view={view} setView={setView} date={date} setDate={setDate} />
        {loading ? (
          <div className="flex h-[480px] items-center justify-center text-corp-text-muted">
            Завантаження...
          </div>
        ) : (
          <DayGrid view={view} cards={cards} onDrop={handleDrop} onOpenCard={setSelectedCard} />
        )}
      </div>

      {/* Full Card Modal */}
      {selectedCard && (
        <FullCardModal card={selectedCard} onClose={() => setSelectedCard(null)} />
      )}
    </div>
  )
}

/*************** Full Card Modal ***************/
function FullCardModal({ card, onClose }: { card: OrderCard; onClose: () => void }) {
  const cardTypeLabel = card.type === 'issue' ? '📦 Картка видачі' : '↩️ Картка повернення'
  const cardTypeColor = card.type === 'issue' ? 'from-blue-600 to-indigo-600' : 'from-emerald-600 to-green-600'

  return (
    <div 
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div 
        className="bg-white rounded-3xl w-full max-w-3xl max-h-[90vh] overflow-y-auto shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className={`bg-gradient-to-r ${cardTypeColor} text-white p-6 rounded-t-3xl`}>
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="text-sm opacity-90 mb-1">{cardTypeLabel}</div>
              <h2 className="text-2xl font-bold mb-2">{card.label}</h2>
              <div className="flex items-center gap-3 text-sm">
                <span>🕐 {card.time}</span>
                <span>📅 {card.date}</span>
                <span className="bg-white/20 px-3 py-1 rounded-full">#{card.order_id || card.id}</span>
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-white/80 hover:text-white text-3xl leading-none p-2"
            >
              ×
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Client Info */}
          <div className="bg-slate-50 rounded-2xl p-5">
            <div className="text-xs text-corp-text-main mb-2 uppercase tracking-wide">Клієнт</div>
            <div className="text-xl font-semibold text-corp-text-dark">{card.client}</div>
          </div>

          {/* Order Details */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-slate-50 rounded-2xl p-5">
              <div className="text-xs text-corp-text-main mb-2 uppercase tracking-wide">Склад / Зона</div>
              <div className="text-lg font-semibold text-corp-text-dark">{card.warehouseZone}</div>
            </div>
            <div className="bg-slate-50 rounded-2xl p-5">
              <div className="text-xs text-corp-text-main mb-2 uppercase tracking-wide">Статус</div>
              <div className="text-lg font-semibold text-corp-text-dark">
                {card.status === 'progress' && '🔄 В роботі'}
                {card.status === 'done' && '✅ Завершено'}
                {card.status === 'issued' && '📤 Видано'}
                {card.status === 'pending' && '⏳ Очікує'}
              </div>
            </div>
          </div>

          {/* Items Summary */}
          <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-2xl p-5 border border-blue-100">
            <div className="text-xs text-blue-700 mb-2 uppercase tracking-wide font-medium">Товари</div>
            <div className="text-2xl font-bold text-blue-900 mb-1">{card.itemsCount} найменувань</div>
            <div className="text-sm text-blue-800">{card.itemsSummary}</div>
          </div>

          {/* Progress Bar (if in progress) */}
          {card.status === 'progress' && (
            <div className="bg-slate-50 rounded-2xl p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="text-sm font-medium text-corp-text-dark">Прогрес комплектації</div>
                <div className="text-sm text-corp-text-main">В процесі</div>
              </div>
              <div className="h-3 w-full overflow-hidden rounded-full bg-slate-200">
                <div className="h-full w-2/3 rounded-full bg-gradient-to-r from-blue-500 to-indigo-500" />
              </div>
              <div className="mt-2 text-xs text-corp-text-main">Приблизно 67% завершено</div>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-4 border-t border-slate-200">
            <button 
              onClick={() => alert('Відкрити повну картку замовлення (функція в розробці)')}
              className={`flex-1 bg-gradient-to-r ${cardTypeColor} text-white py-3 rounded-xl font-semibold hover:shadow-lg transition`}
            >
              Відкрити повну картку
            </button>
            <button 
              onClick={onClose}
              className="px-6 bg-slate-200 text-slate-700 py-3 rounded-xl font-semibold hover:bg-slate-300 transition"
            >
              Закрити
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
