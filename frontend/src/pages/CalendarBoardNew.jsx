/* eslint-disable */
import React, { useMemo, useState, useEffect } from 'react'
import axios from 'axios'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL

/************* helpers *************/
const cls = (...a) => a.filter(Boolean).join(' ')

// Часовий пояс Києва
const KYIV_TZ = 'Europe/Kyiv'

// Отримати сьогоднішню дату по Києву як ISO рядок (YYYY-MM-DD)
const getKyivTodayISO = () => {
  const fmt = new Intl.DateTimeFormat('en-CA', {
    timeZone: KYIV_TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
  return fmt.format(new Date()) // "YYYY-MM-DD"
}

// Конвертувати Date в ISO рядок по Києву
const toKyivISO = (d) => {
  const fmt = new Intl.DateTimeFormat('en-CA', {
    timeZone: KYIV_TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
  return fmt.format(d)
}

// Створити "безпечний" Date з ISO рядка (в UTC на полудень)
const isoToSafeDate = (iso) => {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d, 12, 0, 0))
}

// Конвертувати "безпечний" Date назад в ISO рядок
const safeDateToISO = (date) => {
  const y = date.getUTCFullYear()
  const m = String(date.getUTCMonth() + 1).padStart(2, '0')
  const d = String(date.getUTCDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

// Legacy функції для сумісності
const getKyivDate = () => isoToSafeDate(getKyivTodayISO())
const getKyivToday = () => isoToSafeDate(getKyivTodayISO())
const toISO = (d) => toKyivISO(d)

const formatUA = (d) =>
  d.toLocaleDateString('uk-UA', { weekday: 'short', day: '2-digit', month: 'short', timeZone: KYIV_TZ })

const addDays = (d, offset) => {
  // Працюємо через ISO для уникнення timezone проблем
  const iso = safeDateToISO(d)
  const safeDate = isoToSafeDate(iso)
  safeDate.setUTCDate(safeDate.getUTCDate() + offset)
  return safeDate
}

const toISO = (d) => {
  // Використовуємо локальний час замість UTC
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

// toISO для київського часу (alias)
const toKyivISO = toISO

const startOfWeek = (d) => {
  const iso = safeDateToISO(d)
  const safeDate = isoToSafeDate(iso)
  const day = safeDate.getUTCDay()
  const diff = day === 0 ? -6 : 1 - day
  safeDate.setUTCDate(safeDate.getUTCDate() + diff)
  return safeDate
}

const startOfMonth = (d) => {
  const iso = safeDateToISO(d)
  const [y, m] = iso.split('-').map(Number)
  return isoToSafeDate(`${y}-${String(m).padStart(2, '0')}-01`)
}

const endOfMonth = (d) => {
  const iso = safeDateToISO(d)
  const [y, m] = iso.split('-').map(Number)
  const lastDay = new Date(Date.UTC(y, m, 0)).getUTCDate()
  return isoToSafeDate(`${y}-${String(m).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`)
}

/************* UI components *************/
function Badge({ children, tone = 'slate' }) {
  const map = {
    slate: 'corp-badge corp-badge-neutral',
    green: 'corp-badge corp-badge-success',
    blue: 'corp-badge corp-badge-info',
    violet: 'corp-badge corp-badge-primary',
    amber: 'corp-badge corp-badge-warning',
    red: 'corp-badge corp-badge-error',
  }

  return (
    <span className={cls('inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium', map[tone] || map.slate)}>
      {children}
    </span>
  )
}

function Segmented({ value, onChange, options }) {
  return (
    <div className="inline-flex rounded-full border border-slate-200 bg-slate-50 p-0.5 text-[11px]">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          className={cls(
            'rounded-full px-3 py-1 transition',
            value === o.value
              ? 'bg-white text-corp-text-dark shadow-sm'
              : 'text-corp-text-muted hover:text-corp-text-dark',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

/************* Lane metadata *************/
const laneMeta = {
  issue: {
    label: 'Видача',
    color: 'text-[#B08900]',
    bg: 'bg-[#FFF9E7] border-[#F7D75C]',
    desc: 'Нові замовлення та готові до видачі',
  },
  return: {
    label: 'Повернення',
    color: 'text-[#9A5B15]',
    bg: 'bg-[#FFF3E2] border-[#E7B16B]',
    desc: 'Очікувані повернення та перевірка',
  },
  task: {
    label: 'Завдання',
    color: 'text-[#6E349E]',
    bg: 'bg-[#F4E8FF] border-[#B979E6]',
    desc: 'Мийка, реставрація, внутрішні задачі',
  },
  damage: {
    label: 'Шкода',
    color: 'text-[#C43737]',
    bg: 'bg-[#FFE8E8] border-[#E87474]',
    desc: 'Кейси пошкоджень з повернень',
  },
}

const timeSlots = {
  morning: { label: '🌅 Ранок', hours: '06:00-14:00', from: '06:00', to: '14:00' },
  day: { label: '☀️ День', hours: '14:00-18:00', from: '14:00', to: '18:00' },
  evening: { label: '🌆 Вечір', hours: '18:00-22:00', from: '18:00', to: '22:00' },
}

/************* Calendar Card Component *************/
function CalendarCard({ item, onOpen, onDragStart }) {
  const laneInfo = laneMeta[item.lane]
  
  return (
    <div
      draggable
      onDragStart={(e) => onDragStart(e, item)}
      onClick={() => onOpen(item)}
      className={cls(
        'mb-1 cursor-move rounded-lg border px-1.5 py-1 text-left text-[9px] shadow-sm transition hover:-translate-y-0.5 hover:shadow',
        'md:px-2 md:py-1.5 md:text-[10px]',
        laneInfo.bg,
      )}
    >
      <div className="flex items-center justify-between gap-1">
        <span className="font-semibold text-corp-text-dark truncate text-[8px] md:text-[10px]">{item.title}</span>
        <span className="whitespace-nowrap text-[8px] md:text-[9px] text-corp-text-muted">
          {item.timeSlot === 'morning' ? '🌅' : item.timeSlot === 'day' ? '☀️' : '🌆'}
        </span>
      </div>
      <div className="mt-0.5 flex flex-wrap items-center gap-0.5 text-[8px] md:text-[9px] text-corp-text-muted">
        {item.orderCode && <span className="font-mono text-slate-700">{item.orderCode}</span>}
        {item.client && <span className="hidden md:inline">· {item.client}</span>}
      </div>
      {item.badge && (
        <div className="mt-0.5 md:mt-1">
          <Badge tone={
            item.lane === 'issue' ? 'green' :
            item.lane === 'return' ? 'blue' :
            item.lane === 'task' ? 'violet' : 'red'
          }>
            {item.badge}
          </Badge>
        </div>
      )}
    </div>
  )
}

/************* Drop Zone Component *************/
function DropZone({ onDrop, children, isEmpty }) {
  const [isOver, setIsOver] = useState(false)

  const handleDragOver = (e) => {
    e.preventDefault()
    setIsOver(true)
  }

  const handleDragLeave = () => {
    setIsOver(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsOver(false)
    onDrop(e)
  }

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={cls(
        'min-h-[50px] md:min-h-[70px] rounded-lg md:rounded-xl p-1 md:p-1.5 ring-1 transition-colors overflow-y-auto max-h-[120px] md:max-h-[200px]',
        isOver ? 'bg-blue-50 ring-blue-300' : 'bg-slate-50/60 ring-slate-100'
      )}
    >
      {isEmpty && !isOver ? (
        <div className="flex h-full items-center justify-center text-[8px] md:text-[9px] text-slate-300">
          —
        </div>
      ) : children}
    </div>
  )
}

/************* Day View *************/
function DayView({ date, items, onOpen, onUpdateItem }) {
  const dateKey = toISO(date)
  
  const handleDragStart = (e, item) => {
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('application/json', JSON.stringify(item))
  }

  const handleDrop = (e, lane, timeSlot) => {
    const itemData = JSON.parse(e.dataTransfer.getData('application/json'))
    onUpdateItem(itemData, dateKey, lane, timeSlot)
  }

  return (
    <div className="rounded-xl md:rounded-2xl border border-slate-200 bg-white p-2 md:p-3 text-[10px] md:text-[11px] overflow-x-auto">
      {/* Header */}
      <div className="mb-2 grid grid-cols-[70px,1fr] md:grid-cols-[120px,1fr] items-end gap-1 md:gap-2 border-b border-slate-100 pb-2 min-w-[350px]">
        <div className="text-[8px] md:text-[10px] font-semibold uppercase tracking-wide text-corp-text-muted">Потік</div>
        <div className="grid grid-cols-3 gap-0.5 md:gap-1">
          {Object.values(timeSlots).map((slot) => (
            <div key={slot.label} className="text-center text-[8px] md:text-[10px]">
              <div className="font-medium text-corp-text-dark">{slot.label}</div>
              <div className="text-corp-text-muted hidden md:block">{slot.hours}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Lanes */}
      {Object.keys(laneMeta).map((lane) => {
        const laneInfo = laneMeta[lane]
        return (
          <div key={lane} className="grid grid-cols-[70px,1fr] md:grid-cols-[120px,1fr] gap-1 md:gap-2 border-b border-slate-50 py-1.5 md:py-2 last:border-b-0 min-w-[350px]">
            <div className="flex flex-col gap-0.5 md:gap-1">
              <span className={cls('text-[9px] md:text-[11px] font-semibold', laneInfo.color)}>{laneInfo.label}</span>
              <span className="text-[8px] md:text-[10px] text-slate-400 hidden md:block">{laneInfo.desc}</span>
            </div>

            <div className="grid grid-cols-3 gap-1 md:gap-2">
              {Object.keys(timeSlots).map((timeSlot) => {
                const slotItems = items.filter(
                  (i) => i.date === dateKey && i.lane === lane && i.timeSlot === timeSlot
                )
                return (
                  <DropZone
                    key={timeSlot}
                    onDrop={(e) => handleDrop(e, lane, timeSlot)}
                    isEmpty={slotItems.length === 0}
                  >
                    {slotItems.map((item) => (
                      <CalendarCard
                        key={item.id}
                        item={item}
                        onOpen={onOpen}
                        onDragStart={handleDragStart}
                      />
                    ))}
                  </DropZone>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}

/************* Week View *************/
function WeekView({ baseDate, items, onOpen, onUpdateItem }) {
  const scrollRef = React.useRef(null)
  const [touchStart, setTouchStart] = React.useState(0)
  const [touchEnd, setTouchEnd] = React.useState(0)
  const [weeksOffset, setWeeksOffset] = React.useState(0)
  const isLoadingMore = React.useRef(false)

  // Генеруємо багато тижнів (12 місяців = 52 тижні)
  const allWeeks = useMemo(() => {
    const weeks = []
    const weeksToShow = 52 // 1 рік
    const startWeekOffset = weeksOffset - Math.floor(weeksToShow / 2)
    
    for (let i = 0; i < weeksToShow; i++) {
      const weekOffset = startWeekOffset + i
      const weekStart = startOfWeek(addDays(baseDate, weekOffset * 7))
      const weekDates = Array.from({ length: 7 }, (_, dayIdx) => addDays(weekStart, dayIdx))
      
      // Визначаємо чи це поточний тиждень
      const currentWeekStart = startOfWeek(getKyivToday())
      const isCurrentWeek = toISO(weekStart) === toISO(currentWeekStart)
      
      weeks.push({
        id: `week-${weekOffset}`,
        offset: weekOffset,
        dates: weekDates,
        label: isCurrentWeek ? 'Поточний тиждень' : weekDates[0].toLocaleDateString('uk-UA', { month: 'long', year: 'numeric' }),
        isCurrentWeek
      })
    }
    
    return weeks
  }, [baseDate, weeksOffset])

  // Знайти індекс поточного тижня
  const currentWeekIndex = useMemo(() => {
    return allWeeks.findIndex(w => w.isCurrentWeek)
  }, [allWeeks])

  // Scroll до поточного тижня при першому завантаженні
  React.useEffect(() => {
    if (scrollRef.current && currentWeekIndex >= 0) {
      const weekWidth = scrollRef.current.offsetWidth
      scrollRef.current.scrollLeft = currentWeekIndex * weekWidth
    }
  }, [currentWeekIndex])

  // Infinite scroll detector
  const handleScroll = React.useCallback((e) => {
    if (isLoadingMore.current) return
    
    const container = e.target
    const scrollLeft = container.scrollLeft
    const scrollWidth = container.scrollWidth
    const clientWidth = container.clientWidth
    
    // Якщо доскролили майже до кінця - завантажити більше тижнів вперед
    if (scrollLeft + clientWidth > scrollWidth - clientWidth * 2) {
      isLoadingMore.current = true
      setTimeout(() => {
        setWeeksOffset(prev => prev + 10)
        isLoadingMore.current = false
      }, 300)
    }
    
    // Якщо доскролили майже до початку - завантажити більше тижнів назад
    if (scrollLeft < clientWidth * 2) {
      isLoadingMore.current = true
      setTimeout(() => {
        setWeeksOffset(prev => prev - 10)
        // Відкоригувати scroll щоб користувач не помітив стрибка
        if (scrollRef.current) {
          scrollRef.current.scrollLeft = scrollLeft + (clientWidth * 10)
        }
        isLoadingMore.current = false
      }, 300)
    }
  }, [])

  const handleDragStart = (e, item) => {
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('application/json', JSON.stringify(item))
  }

  const handleDrop = (e, date, lane) => {
    const itemData = JSON.parse(e.dataTransfer.getData('application/json'))
    onUpdateItem(itemData, toISO(date), lane, itemData.timeSlot)
  }

  // Touch handlers
  const handleTouchStart = (e) => {
    setTouchStart(e.targetTouches[0].clientX)
  }

  const handleTouchMove = (e) => {
    setTouchEnd(e.targetTouches[0].clientX)
  }

  const handleTouchEnd = () => {
    if (!touchStart || !touchEnd) return
    
    const distance = touchStart - touchEnd
    const isLeftSwipe = distance > 50
    const isRightSwipe = distance < -50

    if (isLeftSwipe && scrollRef.current) {
      scrollRef.current.scrollBy({ left: scrollRef.current.offsetWidth, behavior: 'smooth' })
    }

    if (isRightSwipe && scrollRef.current) {
      scrollRef.current.scrollBy({ left: -scrollRef.current.offsetWidth, behavior: 'smooth' })
    }

    setTouchStart(0)
    setTouchEnd(0)
  }

  return (
    <div className="rounded-xl md:rounded-2xl border border-slate-200 bg-white overflow-hidden">
      {/* Горизонтальний скрол з тижнями */}
      <div 
        ref={scrollRef}
        className="overflow-x-auto overflow-y-visible scroll-smooth hide-scrollbar"
        onScroll={handleScroll}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        style={{ 
          WebkitOverflowScrolling: 'touch'
        }}
      >
        <div className="flex">
          {allWeeks.map((week, weekIndex) => (
            <div 
              key={week.id}
              className="flex-shrink-0 w-full p-2 md:p-3 text-[10px] md:text-[11px]"
            >
              {/* Назва тижня */}
              <div className="text-[10px] md:text-xs font-semibold text-corp-text-main mb-2 md:mb-3 text-center">
                {week.dates[0].toLocaleDateString('uk-UA', { day: '2-digit', month: 'short' })} - {week.dates[6].toLocaleDateString('uk-UA', { day: '2-digit', month: 'short', year: 'numeric' })}
              </div>

              {/* Header */}
              <div className="mb-2 grid grid-cols-[60px,1fr] md:grid-cols-[120px,1fr] items-end gap-1 md:gap-2 border-b border-slate-100 pb-2 overflow-x-auto">
                <div className="text-[8px] md:text-[10px] font-semibold uppercase tracking-wide text-corp-text-muted">Потік</div>
                <div className="grid grid-cols-7 gap-0.5 md:gap-1 min-w-[280px] md:min-w-0">
                  {week.dates.map((d) => {
                    const isToday = toKyivISO(d) === toKyivISO(getKyivToday())
                    return (
                      <div 
                        key={toISO(d)} 
                        className={cls(
                          "text-center text-[8px] md:text-[10px] p-0.5 md:p-1 rounded",
                          isToday && "bg-blue-50 ring-1 ring-blue-200"
                        )}
                      >
                        <div className={cls(
                          "font-medium",
                          isToday ? "text-blue-600" : "text-corp-text-dark"
                        )}>
                          {d.toLocaleDateString('uk-UA', { day: '2-digit' })}
                        </div>
                        <div className={cls(
                          "hidden md:block",
                          isToday ? "text-blue-500" : "text-corp-text-muted"
                        )}>
                          {d.toLocaleDateString('uk-UA', { weekday: 'short' })}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Lanes */}
              <div className="overflow-x-auto">
                {Object.keys(laneMeta).map((lane) => {
                  const laneInfo = laneMeta[lane]
                  return (
                    <div key={lane} className="grid grid-cols-[60px,1fr] md:grid-cols-[120px,1fr] gap-1 md:gap-2 border-b border-slate-50 py-1.5 md:py-2 last:border-b-0">
                      <div className="flex flex-col gap-0.5 md:gap-1">
                        <span className={cls('text-[9px] md:text-[11px] font-semibold', laneInfo.color)}>{laneInfo.label}</span>
                      </div>

                      <div className="grid grid-cols-7 gap-0.5 md:gap-2 min-w-[280px] md:min-w-0">
                        {week.dates.map((d) => {
                          const dateKey = toISO(d)
                          const dayItems = items.filter((i) => i.date === dateKey && i.lane === lane)
                          return (
                            <DropZone
                              key={dateKey}
                              onDrop={(e) => handleDrop(e, d, lane)}
                              isEmpty={dayItems.length === 0}
                            >
                              {dayItems.map((item) => (
                                <CalendarCard
                                  key={item.id}
                                  item={item}
                                  onOpen={onOpen}
                                  onDragStart={handleDragStart}
                                />
                              ))}
                            </DropZone>
                          )
                        })}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Підказка з нескінченним скролом */}
      <div className="px-3 py-2 bg-slate-50 border-t border-slate-200 text-center">
        <div className="text-[10px] text-corp-text-muted">
          ← Нескінченний скрол: протягніть для перегляду інших тижнів →
        </div>
        <div className="text-[9px] text-slate-400 mt-1">
          Показано {allWeeks.length} тижнів • Автоматично завантажується більше при скролі
        </div>
      </div>
    </div>
  )
}

/************* Month View *************/
function MonthView({ baseDate, items, onDateClick }) {
  const scrollRef = React.useRef(null)
  const [touchStart, setTouchStart] = React.useState(0)
  const [touchEnd, setTouchEnd] = React.useState(0)
  const [expandedDates, setExpandedDates] = React.useState(new Set())

  // Генеруємо тижні для горизонтального скролу (попередній, поточний, наступний місяць)
  const allWeeks = useMemo(() => {
    const weeks = []
    
    // Попередній місяць (останній тиждень)
    const prevMonth = new Date(baseDate.getFullYear(), baseDate.getMonth() - 1, 1)
    const prevMonthEnd = endOfMonth(prevMonth)
    const prevWeekStart = startOfWeek(prevMonthEnd)
    const prevWeek = []
    for (let i = 0; i < 7; i++) {
      prevWeek.push(addDays(prevWeekStart, i))
    }
    weeks.push({ id: 'prev', dates: prevWeek, month: prevMonth })
    
    // Поточний місяць (всі тижні)
    const start = startOfMonth(baseDate)
    const end = endOfMonth(baseDate)
    let current = startOfWeek(start)
    
    while (current <= end) {
      const week = []
      for (let i = 0; i < 7; i++) {
        week.push(new Date(current))
        current = addDays(current, 1)
      }
      weeks.push({ id: `current-${weeks.length}`, dates: week, month: baseDate })
    }
    
    // Наступний місяць (перший тиждень)
    const nextMonth = new Date(baseDate.getFullYear(), baseDate.getMonth() + 1, 1)
    const nextWeekStart = startOfWeek(nextMonth)
    const nextWeek = []
    for (let i = 0; i < 7; i++) {
      nextWeek.push(addDays(nextWeekStart, i))
    }
    weeks.push({ id: 'next', dates: nextWeek, month: nextMonth })
    
    return weeks
  }, [baseDate])

  const currentMonth = baseDate.getMonth()

  const getDateItems = (date) => {
    const dateKey = toISO(date)
    const dayItems = items.filter((i) => i.date === dateKey)
    return {
      all: dayItems,
      issue: dayItems.filter((i) => i.lane === 'issue'),
      return: dayItems.filter((i) => i.lane === 'return'),
      task: dayItems.filter((i) => i.lane === 'task'),
      damage: dayItems.filter((i) => i.lane === 'damage'),
      total: dayItems.length,
    }
  }

  const toggleDateExpand = (date) => {
    const dateKey = toISO(date)
    setExpandedDates(prev => {
      const newSet = new Set(prev)
      if (newSet.has(dateKey)) {
        newSet.delete(dateKey)
      } else {
        newSet.add(dateKey)
      }
      return newSet
    })
  }

  // Touch handlers для свайпу
  const handleTouchStart = (e) => {
    setTouchStart(e.targetTouches[0].clientX)
  }

  const handleTouchMove = (e) => {
    setTouchEnd(e.targetTouches[0].clientX)
  }

  const handleTouchEnd = () => {
    if (!touchStart || !touchEnd) return
    
    const distance = touchStart - touchEnd
    const isLeftSwipe = distance > 50
    const isRightSwipe = distance < -50

    if (isLeftSwipe) {
      // Свайп вліво - наступний тиждень/місяць
      if (scrollRef.current) {
        scrollRef.current.scrollBy({ left: 300, behavior: 'smooth' })
      }
    }

    if (isRightSwipe) {
      // Свайп вправо - попередній тиждень/місяць
      if (scrollRef.current) {
        scrollRef.current.scrollBy({ left: -300, behavior: 'smooth' })
      }
    }

    setTouchStart(0)
    setTouchEnd(0)
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden">
      {/* Weekday headers */}
      <div className="grid grid-cols-7 gap-2 px-3 py-2 bg-slate-50 border-b border-slate-200">
        {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Нд'].map((day) => (
          <div key={day} className="text-center text-[10px] font-semibold text-corp-text-muted">{day}</div>
        ))}
      </div>

      {/* Горизонтальний скрол з тижнями */}
      <div 
        ref={scrollRef}
        className="overflow-x-auto overflow-y-hidden scroll-smooth hide-scrollbar"
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        style={{ 
          scrollSnapType: 'x mandatory',
          WebkitOverflowScrolling: 'touch'
        }}
      >
        <div className="flex">
          {allWeeks.map((week, weekIndex) => (
            <div 
              key={week.id}
              className="flex-shrink-0 w-full p-3"
              style={{ scrollSnapAlign: 'start' }}
            >
              {/* Назва місяця тижня */}
              <div className="text-xs font-semibold text-corp-text-main mb-2 text-center">
                {week.dates[3].toLocaleDateString('uk-UA', { month: 'long', year: 'numeric' })}
              </div>
              
              {/* Тиждень */}
              <div className="grid grid-cols-7 gap-2">
                {week.dates.map((date) => {
                  const dateItems = getDateItems(date)
                  const isCurrentMonth = date.getMonth() === currentMonth
                  const isToday = toKyivISO(date) === toKyivISO(getKyivToday())
                  const isExpanded = expandedDates.has(toISO(date))

                  return (
                    <div
                      key={toISO(date)}
                      className={cls(
                        'rounded-xl border transition',
                        isCurrentMonth ? 'bg-white border-slate-200' : 'bg-slate-50 border-slate-100 opacity-60',
                        isToday && 'ring-2 ring-blue-500 shadow-lg',
                        isExpanded ? 'col-span-1 row-span-2' : ''
                      )}
                    >
                      {/* Header дня */}
                      <div className="p-2 border-b border-slate-100">
                        <div className="flex items-center justify-between">
                          <div className={cls(
                            'text-base font-bold',
                            isToday ? 'text-blue-600' : isCurrentMonth ? 'text-corp-text-dark' : 'text-slate-400'
                          )}>
                            {date.getDate()}
                          </div>
                          {dateItems.total > 0 && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                toggleDateExpand(date)
                              }}
                              className="text-xs px-2 py-0.5 rounded bg-slate-100 hover:bg-slate-200 transition"
                            >
                              {isExpanded ? '▲' : `▼ ${dateItems.total}`}
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Компактний вигляд (згорнуто) */}
                      {!isExpanded && dateItems.total > 0 && (
                        <div className="p-2 space-y-1">
                          {dateItems.issue.length > 0 && (
                            <div className="flex items-center gap-1 text-[9px]">
                              <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                              <span className="font-medium">{dateItems.issue.length} видача</span>
                            </div>
                          )}
                          {dateItems.return.length > 0 && (
                            <div className="flex items-center gap-1 text-[9px]">
                              <span className="w-2 h-2 rounded-full bg-sky-500"></span>
                              <span className="font-medium">{dateItems.return.length} повернення</span>
                            </div>
                          )}
                          {dateItems.task.length > 0 && (
                            <div className="flex items-center gap-1 text-[9px]">
                              <span className="w-2 h-2 rounded-full bg-violet-500"></span>
                              <span className="font-medium">{dateItems.task.length} таски</span>
                            </div>
                          )}
                          {dateItems.damage.length > 0 && (
                            <div className="flex items-center gap-1 text-[9px]">
                              <span className="w-2 h-2 rounded-full bg-rose-500"></span>
                              <span className="font-medium">{dateItems.damage.length} шкода</span>
                            </div>
                          )}
                          <button
                            onClick={() => onDateClick(date)}
                            className="w-full mt-1 text-[9px] text-blue-600 hover:underline"
                          >
                            Відкрити день →
                          </button>
                        </div>
                      )}

                      {/* Розгорнутий вигляд (деталі) */}
                      {isExpanded && (
                        <div className="p-2 max-h-[400px] overflow-y-auto space-y-2">
                          {/* Видача */}
                          {dateItems.issue.length > 0 && (
                            <div>
                              <div className="text-[9px] font-semibold text-emerald-700 mb-1 flex items-center gap-1">
                                <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                                Видача ({dateItems.issue.length})
                              </div>
                              {dateItems.issue.map(item => (
                                <div key={item.id} className="text-[8px] bg-emerald-50 rounded p-1 mb-1">
                                  <div className="font-medium truncate">{item.orderCode}</div>
                                  <div className="text-corp-text-main truncate">{item.client}</div>
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Повернення */}
                          {dateItems.return.length > 0 && (
                            <div>
                              <div className="text-[9px] font-semibold text-sky-700 mb-1 flex items-center gap-1">
                                <span className="w-2 h-2 rounded-full bg-sky-500"></span>
                                Повернення ({dateItems.return.length})
                              </div>
                              {dateItems.return.map(item => (
                                <div key={item.id} className="text-[8px] bg-sky-50 rounded p-1 mb-1">
                                  <div className="font-medium truncate">{item.orderCode}</div>
                                  <div className="text-corp-text-main truncate">{item.client}</div>
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Таски */}
                          {dateItems.task.length > 0 && (
                            <div>
                              <div className="text-[9px] font-semibold text-violet-700 mb-1 flex items-center gap-1">
                                <span className="w-2 h-2 rounded-full bg-violet-500"></span>
                                Завдання ({dateItems.task.length})
                              </div>
                              {dateItems.task.map(item => (
                                <div key={item.id} className="text-[8px] bg-violet-50 rounded p-1 mb-1">
                                  <div className="font-medium truncate">{item.title}</div>
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Шкода */}
                          {dateItems.damage.length > 0 && (
                            <div>
                              <div className="text-[9px] font-semibold text-rose-700 mb-1 flex items-center gap-1">
                                <span className="w-2 h-2 rounded-full bg-rose-500"></span>
                                Пошкодження ({dateItems.damage.length})
                              </div>
                              {dateItems.damage.map(item => (
                                <div key={item.id} className="text-[8px] bg-rose-50 rounded p-1 mb-1">
                                  <div className="font-medium truncate">{item.title}</div>
                                </div>
                              ))}
                            </div>
                          )}

                          <button
                            onClick={() => onDateClick(date)}
                            className="w-full text-[9px] text-blue-600 hover:underline border-t border-slate-200 pt-2"
                          >
                            Відкрити повний день →
                          </button>
                        </div>
                      )}

                      {/* Пустий день */}
                      {dateItems.total === 0 && (
                        <button
                          onClick={() => onDateClick(date)}
                          className="w-full p-2 text-[9px] text-slate-400 hover:text-corp-text-main transition"
                        >
                          Немає подій
                        </button>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Індикатор свайпу */}
      <div className="flex justify-center gap-1 py-2 bg-slate-50">
        {allWeeks.map((week, idx) => (
          <div 
            key={week.id} 
            className={cls(
              'w-2 h-2 rounded-full transition-colors',
              idx === 1 ? 'bg-blue-500' : 'bg-slate-300'
            )}
          />
        ))}
      </div>

      {/* Підказка */}
      <div className="px-3 py-2 bg-slate-50 border-t border-slate-200 text-center text-[10px] text-corp-text-muted">
        👆 Протягніть вліво/вправо або прокрутіть для перегляду інших тижнів
      </div>
    </div>
  )
}

/************* Main Component *************/
export default function CalendarBoardNew() {
  const [view, setView] = useState('week')
  const [baseDate, setBaseDate] = useState(getKyivToday())
  const [laneFilter, setLaneFilter] = useState('all')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)

  // Load data from backend
  useEffect(() => {
    loadCalendarData()
  }, [view, baseDate])

  const loadCalendarData = async () => {
    try {
      setLoading(true)
      // Завантажуємо великий діапазон залежно від view
      let start, end
      if (view === 'day') {
        // Для денного вигляду - тільки один день
        start = baseDate
        end = baseDate
      } else {
        // Для тижневого - великий діапазон для нескінченного скролу
        const currentWeekStart = startOfWeek(baseDate)
        start = addDays(currentWeekStart, -180) // 6 місяців назад
        end = addDays(currentWeekStart, 365) // 12 місяців вперед
      }

      const calendarItems = []

      // 1. Load ALL orders (awaiting confirmation)
      try {
        const ordersRes = await axios.get(`${BACKEND_URL}/api/orders`, {
          params: { from_date: toISO(start), to_date: toISO(end) }
        })

        const orders = ordersRes.data.orders || []
        
        orders.forEach((o) => {
          const issueDate = o.issue_date || o.rental_start_date
          const clientName = o.client_name || o.customer_name

          // Issue lane - новi замовлення
          if (issueDate) {
            calendarItems.push({
              id: `order-${o.order_number}-issue`,
              lane: 'issue',
              date: issueDate,
              timeSlot: 'morning',
              orderCode: o.order_number,
              title: `Нове: ${clientName}`,
              client: clientName,
              badge: 'Очікує підтвердження',
              status: o.status,
              orderData: o,
            })
          }
        })
      } catch (err) {
        console.error('Failed to load awaiting orders:', err)
      }

      // 2. Load decor-orders (на комплектації, готові, видані, повернення)
      try {
        const decorRes = await axios.get(`${BACKEND_URL}/api/decor-orders`, {
          params: { 
            status: 'processing,ready_for_issue,issued,on_rent,shipped,delivered,returning',
            from_date: toISO(start), 
            to_date: toISO(end) 
          }
        })

        const decorOrders = decorRes.data.orders || []
        
        decorOrders.forEach((o) => {
          const issueDate = o.issue_date || o.rental_start_date
          const returnDate = o.return_date || o.rental_end_date
          const clientName = o.client_name || o.customer_name

          // Issue lane - комплектація і готові
          if (issueDate && ['processing', 'ready_for_issue', 'ready'].includes(o.status)) {
            calendarItems.push({
              id: `decor-${o.order_number}-issue`,
              lane: 'issue',
              date: issueDate,
              timeSlot: 'day',
              orderCode: o.order_number,
              title: `${o.status === 'ready_for_issue' || o.status === 'ready' ? 'Готово' : 'Комплектація'}: ${clientName}`,
              client: clientName,
              badge: o.status === 'ready_for_issue' || o.status === 'ready' ? 'Готово до видачі' : 'На комплектації',
              status: o.status,
              orderData: o,
            })
          }

          // Return lane - видані і на повернення
          if (returnDate && ['issued', 'on_rent', 'returning'].includes(o.status)) {
            calendarItems.push({
              id: `decor-${o.order_number}-return`,
              lane: 'return',
              date: returnDate,
              timeSlot: 'evening',
              orderCode: o.order_number,
              title: `Повернення: ${clientName}`,
              client: clientName,
              badge: o.status === 'returning' ? 'Повертається' : 'Очікуємо',
              status: o.status,
              orderData: o,
            })
          }
        })
        
        console.log(`[Calendar] Завантажено ${decorOrders.length} замовлень на комплектації/виданих`)
      } catch (err) {
        console.error('Failed to load decor orders:', err)
      }

      // 3. Load issue cards (картки видачі)
      try {
        const issueCardsRes = await axios.get(`${BACKEND_URL}/api/issue-cards`)
        const issueCards = issueCardsRes.data || []
        
        issueCards.forEach((card) => {
          const issueDate = card.issue_date || card.rental_start_date

          // Показуємо картки на підготовці та готові до видачі
          if (issueDate && ['preparation', 'ready', 'ready_for_issue'].includes(card.status)) {
            calendarItems.push({
              id: `issue-card-${card.id}`,
              lane: 'issue',
              date: issueDate,
              timeSlot: 'day',
              orderCode: card.order_number,
              title: `Картка видачі: ${card.customer_name}`,
              client: card.customer_name,
              badge: card.status === 'ready' || card.status === 'ready_for_issue' ? 'Готова' : 'Підготовка',
              status: card.status,
              orderData: card,
            })
          }
          
          // Показуємо ВИДАНІ картки на поверненні (issued)
          if (card.status === 'issued') {
            // Розраховуємо дату повернення: issued_at + rental_days
            let returnDate = card.return_date
            
            if (!returnDate && card.issued_at && card.rental_days) {
              const issuedDate = new Date(card.issued_at)
              issuedDate.setDate(issuedDate.getDate() + card.rental_days)
              returnDate = issuedDate.toISOString().slice(0, 10)
            }
            
            // Fallback на issued_at якщо немає rental_days
            if (!returnDate) {
              returnDate = card.issued_at?.slice(0, 10) || card.created_at?.slice(0, 10)
            }
            
            if (returnDate) {
              calendarItems.push({
                id: `return-card-${card.id}`,
                lane: 'return',
                date: returnDate,
                timeSlot: 'evening',
                orderCode: card.order_number,
                title: `Повернення: ${card.customer_name}`,
                client: card.customer_name,
                badge: 'На поверненні',
                status: 'issued',
                orderData: card,
              })
            }
          }
        })
        
        console.log(`[Calendar] Завантажено ${issueCards.length} карток видачі`)
      } catch (err) {
        console.error('Failed to load issue cards:', err)
      }

      // 4. Load cleaning tasks for Task lane
      try {
        const cleaningRes = await axios.get(`${BACKEND_URL}/api/product-cleaning/all`)
        const cleaningTasks = cleaningRes.data || []
        
        cleaningTasks.forEach((task) => {
          // Показуємо ВСІ завдання, не тільки активні
          const updatedDate = task.updated_at ? task.updated_at.slice(0, 10) : toISO(getKyivToday())
          
          const statusLabels = {
            wash: 'Мийка',
            dry: 'Сушка',
            repair: 'Реставрація',
            clean: 'Чисте',
            damaged: 'Пошкоджено'
          }
          
          calendarItems.push({
            id: `task-${task.sku}-${task.status}-${task.updated_at}`,
            lane: 'task',
            date: updatedDate,
            timeSlot: task.status === 'wash' ? 'morning' : task.status === 'dry' ? 'day' : 'evening',
            orderCode: null,
            title: `${statusLabels[task.status] || task.status}: ${task.sku}`,
            client: `Оновлено: ${new Date(task.updated_at || getKyivDate()).toLocaleDateString('uk-UA')}`,
            badge: task.status === 'repair' ? 'Критично' : task.status === 'clean' ? 'Завершено' : 'В процесі',
            status: task.status,
            orderData: task,
          })
        })
        
        console.log(`[Calendar] Завантажено ${cleaningTasks.length} завдань (включаючи всі статуси)`)
      } catch (err) {
        console.error('Failed to load cleaning tasks:', err)
      }

      // 5. Load damage cases for Damage lane
      try {
        const damageRes = await axios.get(`${BACKEND_URL}/api/product-damage-history/recent?limit=500`)
        const damages = damageRes.data || []
        
        damages.forEach((d) => {
          const damageDate = d.created_at ? d.created_at.slice(0, 10) : toISO(getKyivToday())
          
          calendarItems.push({
            id: `damage-${d.id}`,
            lane: 'damage',
            date: damageDate,
            timeSlot: 'day',
            orderCode: d.order_number,
            title: `Пошкодження: ${d.product_name}`,
            client: d.order_number ? `Замовлення ${d.order_number}` : 'Переоблік',
            badge: d.severity === 'high' ? 'Критично' : d.severity === 'medium' ? 'Середньо' : 'Низько',
            status: d.severity,
            orderData: d,
          })
        })
      } catch (err) {
        console.error('Failed to load damage cases:', err)
      }

      setItems(calendarItems)
    } catch (err) {
      console.error('Failed to load calendar:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleUpdateItem = async (item, newDate, newLane, newTimeSlot) => {
    console.log('Update item:', { item, newDate, newLane, newTimeSlot })
    
    // Update local state immediately for better UX
    setItems((prev) =>
      prev.map((i) =>
        i.id === item.id
          ? { ...i, date: newDate, lane: newLane, timeSlot: newTimeSlot }
          : i
      )
    )

    // Update backend
    try {
      // Only update for orders (issue and return lanes)
      if (item.orderData && (newLane === 'issue' || newLane === 'return')) {
        const orderId = item.orderData.order_id || item.orderData.id
        
        await axios.put(
          `${BACKEND_URL}/api/orders/${orderId}/calendar-update`,
          {
            lane: newLane,
            date: newDate,
            timeSlot: newTimeSlot
          }
        )
        
        console.log('✅ Backend updated successfully')
      }
    } catch (err) {
      console.error('Failed to update backend:', err)
      // Revert local state on error
      setItems((prev) =>
        prev.map((i) =>
          i.id === item.id
            ? { ...i, date: item.date, lane: item.lane, timeSlot: item.timeSlot }
            : i
        )
      )
      alert('Помилка при оновленні. Спробуйте ще раз.')
    }
  }

  const handleOpenDetails = (item) => {
    alert(`Деталі: ${item.title}\nКлієнт: ${item.client}\nСтатус: ${item.badge}`)
  }

  const moveBase = (offset) => {
    setBaseDate((prev) => addDays(prev, offset))
  }

  const filteredItems = useMemo(() => {
    if (laneFilter === 'all') return items
    return items.filter((i) => i.lane === laneFilter)
  }, [items, laneFilter])

  const summary = useMemo(() => {
    return {
      total: filteredItems.length,
      issues: filteredItems.filter((i) => i.lane === 'issue').length,
      returns: filteredItems.filter((i) => i.lane === 'return').length,
      tasks: filteredItems.filter((i) => i.lane === 'task').length,
      damages: filteredItems.filter((i) => i.lane === 'damage').length,
    }
  }, [filteredItems])

  if (loading) {
    return <div className="flex items-center justify-center h-screen">Завантаження...</div>
  }

  return (
    <div className="mx-auto max-w-7xl space-y-4 bg-slate-50 p-4 md:p-6">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-corp-text-dark">Календар процесів</h1>
          <p className="text-xs text-corp-text-muted">
            Всі замовлення, видачі, повернення, завдання та кейси шкоди
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[11px]">
          <Segmented
            value={view}
            onChange={(v) => setView(v)}
            options={[
              { value: 'day', label: 'День' },
              { value: 'week', label: 'Тиждень' },
            ]}
          />
          {view === 'day' && (
            <div className="flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2 py-1">
              <button
                type="button"
                onClick={() => moveBase(-1)}
                className="rounded-full px-2 py-1 text-xs text-corp-text-muted hover:bg-slate-100"
              >
                ‹
              </button>
              <span className="px-2 text-[11px] font-medium text-slate-700">
                {formatUA(baseDate)}
              </span>
              <button
                type="button"
                onClick={() => moveBase(1)}
                className="rounded-full px-2 py-1 text-xs text-corp-text-muted hover:bg-slate-100"
              >
                ›
              </button>
            </div>
          )}
        </div>
      </header>

      {/* Stats */}
      <div className="grid gap-3 text-[11px] md:grid-cols-5">
        <div className="rounded-2xl border border-slate-200 bg-white p-3">
          <div className="text-corp-text-muted">Подій</div>
          <div className="mt-1 text-lg font-semibold text-corp-text-dark">{summary.total}</div>
        </div>
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-3">
          <div className="text-emerald-700">Видачі</div>
          <div className="mt-1 text-lg font-semibold">{summary.issues}</div>
        </div>
        <div className="rounded-2xl border border-sky-200 bg-sky-50 p-3">
          <div className="text-sky-700">Повернення</div>
          <div className="mt-1 text-lg font-semibold">{summary.returns}</div>
        </div>
        <div className="rounded-2xl border border-violet-200 bg-violet-50 p-3">
          <div className="text-violet-700">Завдання</div>
          <div className="mt-1 text-lg font-semibold">{summary.tasks}</div>
        </div>
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-3">
          <div className="text-rose-700">Кейси шкоди</div>
          <div className="mt-1 text-lg font-semibold">{summary.damages}</div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-3 text-[11px]">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-corp-text-muted">Потік</span>
          <Segmented
            value={laneFilter}
            onChange={(v) => setLaneFilter(v)}
            options={[
              { value: 'all', label: 'Усі' },
              { value: 'issue', label: 'Видача' },
              { value: 'return', label: 'Повернення' },
              { value: 'task', label: 'Завдання' },
              { value: 'damage', label: 'Шкода' },
            ]}
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="green">Видача</Badge>
          <Badge tone="blue">Повернення</Badge>
          <Badge tone="violet">Завдання</Badge>
          <Badge tone="red">Шкода</Badge>
        </div>
      </div>

      {/* Main View */}
      {view === 'day' && (
        <DayView
          date={baseDate}
          items={filteredItems}
          onOpen={handleOpenDetails}
          onUpdateItem={handleUpdateItem}
        />
      )}
      {view === 'week' && (
        <WeekView
          baseDate={baseDate}
          items={filteredItems}
          onOpen={handleOpenDetails}
          onUpdateItem={handleUpdateItem}
        />
      )}
    </div>
  )
}

// CSS для приховання scrollbar
const style = document.createElement('style')
style.textContent = `
  .hide-scrollbar::-webkit-scrollbar {
    display: none;
  }
  .hide-scrollbar {
    -ms-overflow-style: none;
    scrollbar-width: none;
  }
`
if (typeof document !== 'undefined') {
  document.head.appendChild(style)
}
