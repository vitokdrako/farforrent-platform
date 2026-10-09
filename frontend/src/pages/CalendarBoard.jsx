/* eslint-disable */
// Manager Calendar — day/week/month views with issue/return/new counts and quick drill‑down
// Tailwind only, no external imports. Default export = CalendarBoard

import React, { useMemo, useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

/******************** utils ********************/
const cls = (...a)=> a.filter(Boolean).join(' ')
const pad = (n)=> (n<10? '0'+n : ''+n)
const todayISO = ()=> new Date().toISOString().slice(0,10)
const addDays = (iso, d)=> { const x=new Date(iso); x.setDate(x.getDate()+d); return x.toISOString().slice(0,10) }
const sameDay = (a,b)=> a===b
const dow = (iso)=> { const x=new Date(iso); let w=x.getDay(); return w===0?7:w } // 1..7 (Mon..Sun)
const startOfWeek = (iso)=> { const k=dow(iso)-1; return addDays(iso, -k) }
const endOfWeek = (iso)=> addDays(startOfWeek(iso), 6)
const startOfMonth = (iso)=> { const d=new Date(iso); d.setDate(1); return d.toISOString().slice(0,10) }
const endOfMonth = (iso)=> { const d=new Date(iso); d.setMonth(d.getMonth()+1); d.setDate(0); return d.toISOString().slice(0,10) }
const monthGrid = (iso)=>{ // Monday‑first 6x7 grid of iso dates
  const start = startOfMonth(iso)
  const first = startOfWeek(start)
  return Array.from({length:42}, (_,i)=> addDays(first, i))
}
const fmtTime = (t)=> t||'—'

const KIND_META = {
  new:    { label:'Нове',      tone:'bg-violet-100 text-violet-700 border-violet-200', dot:'bg-violet-500' },
  issue:  { label:'Видача',    tone:'bg-emerald-100 text-emerald-700 border-emerald-200', dot:'bg-emerald-500' },
  return: { label:'Повернення',tone:'bg-amber-100 text-amber-800 border-amber-200', dot:'bg-amber-500' },
}

/******************** small UI ********************/
function Badge({kind, children}){
  const meta=KIND_META[kind]||{tone:'bg-slate-100 text-slate-700 border-slate-200'}
  return <span className={cls('inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs', meta.tone)}>{children}</span>
}

function Toolbar({view,setView, date,setDate, onToday}){
  const label = new Date(date).toLocaleDateString('uk-UA', { month:'long', year:'numeric'})
  return (
    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div className="flex items-center gap-2">
        <button onClick={()=>setDate(addDays(date, view==='day'? -1 : view==='week'? -7 : -30))} className="rounded-xl border px-3 py-2">‹</button>
        <button onClick={onToday} className="rounded-xl border px-3 py-2">Сьогодні</button>
        <button onClick={()=>setDate(addDays(date, view==='day'? 1 : view==='week'? 7 : 30))} className="rounded-xl border px-3 py-2">›</button>
        <div className="ml-3 text-lg font-semibold capitalize">{label}</div>
      </div>
      <div className="flex gap-2">
        {['day','week','month'].map(v=> (
          <button key={v} onClick={()=>setView(v)} className={cls('rounded-full px-3 py-1 text-sm', view===v? 'bg-slate-900 text-white':'bg-slate-200 text-corp-text-dark')}>{v}</button>
        ))}
      </div>
    </div>
  )
}

function Legend(){
  return (
    <div className="flex flex-wrap items-center gap-3 text-sm">
      <span className="inline-flex items-center gap-2"><i className="h-2 w-2 rounded-full bg-emerald-500"/> Готово до видачі</span>
      <span className="inline-flex items-center gap-2"><i className="h-2 w-2 rounded-full bg-amber-500"/> Повернення</span>
    </div>
  )
}

/******************** views ********************/
function DayView({date, orders, onOpen}){
  const list = useMemo(()=> (orders || []).filter(o=> o.date===date).sort((a,b)=> a.time.localeCompare(b.time)), [orders,date])
  const buckets = {
    issue: list.filter(o=>o.kind==='issue'),
    return: list.filter(o=>o.kind==='return')
  }
  const Block = ({title, kind, arr})=> (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center gap-2"><Badge kind={kind}>{title}</Badge><span className="text-xs text-corp-text-muted">{(arr || []).length}</span></div>
      <div className="space-y-2">
        {(arr || []).map(o=> (
          <div key={o.id} className="flex items-center justify-between rounded-xl border border-slate-200 px-3 py-2 hover:bg-slate-50">
            <div>
              <div className="font-medium text-corp-text-dark">#{o.order_id} · {o.customer}</div>
              <div className="text-xs text-corp-text-muted">{fmtTime(o.time)} · {o.items} позицій · {o.status}</div>
            </div>
            <div className="flex items-center gap-2">
              <span className={cls('h-2 w-2 rounded-full', KIND_META[o.kind].dot)} />
              <button onClick={()=>onOpen(o)} className="rounded-full bg-slate-900 px-3 py-1 text-sm text-white">
                {o.kind === 'issue' ? 'Видати' : 'Повернення'}
              </button>
            </div>
          </div>
        ))}
        {(arr || []).length===0 && <div className="text-sm text-corp-text-muted">Немає записів</div>}
      </div>
    </div>
  )
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Block title="Готово до видачі" kind="issue" arr={buckets.issue || []} />
      <Block title="Повернення" kind="return" arr={buckets.return || []} />
      <Block title="Нове" kind="new" arr={buckets.new} />
    </div>
  )
}

function WeekView({date, orders, onOpen, onPickDay}){
  const start = startOfWeek(date)
  const days = Array.from({length:7}, (_,i)=> addDays(start, i))
  const byDay = (d)=> (orders || []).filter(o=> o.date===d)
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50">
          <tr>
            {days.map(d=> (
              <th key={d} className="px-3 py-2 text-left">
                <div className="flex items-center justify-between">
                  <div className="font-medium">{new Date(d).toLocaleDateString('uk-UA', {weekday:'short', day:'2-digit', month:'2-digit'})}</div>
                  {(byDay(d) || []).length > 0 && (
                    <button onClick={()=>onPickDay(d)} className="rounded-md border px-2 py-0.5 text-xs hover:bg-slate-100">День</button>
                  )}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            {days.map(d=> {
              const arr = byDay(d) || []
              const count = {
                issue: arr.filter(x=>x.kind==='issue').length,
                return: arr.filter(x=>x.kind==='return').length,
                new: arr.filter(x=>x.kind==='new').length,
              }
              return (
                <td key={d} className="min-h-40 align-top border-t p-2">
                  <div className="flex flex-col gap-1">
                    {['issue','return','new'].map(k => count[k]>0 && (
                      <div key={k} className="flex items-center justify-between rounded-lg border px-2 py-1 text-xs">
                        <span className="flex items-center gap-2"><i className={cls('h-2 w-2 rounded-full', KIND_META[k].dot)} /> {KIND_META[k].label}</span>
                        <span className="text-xs font-semibold">{count[k]}</span>
                      </div>
                    ))}
                    <div className="mt-1 space-y-1">
                      {arr.map(o=> (
                        <button key={o.id} onClick={()=>onOpen(o)} className="block w-full truncate rounded-md bg-slate-100 px-2 py-1 text-left hover:bg-slate-200 text-xs">#{o.order_id} · {o.customer}</button>
                      ))}
                      {arr.length===0 && <div className="text-xs text-slate-400">—</div>}
                    </div>
                  </div>
                </td>
              )
            })}
          </tr>
        </tbody>
      </table>
    </div>
  )
}

function MonthView({date, orders, onOpen, onPickDay}){
  const days = monthGrid(date)
  const curMonth = new Date(date).getMonth()
  const byDay = (d)=> (orders || []).filter(o=> o.date===d)
  return (
    <div className="grid grid-cols-7 gap-1">
      {['Пн','Вт','Ср','Чт','Пт','Сб','Нд'].map(h=> (
        <div key={h} className="px-2 py-1 text-center text-xs text-corp-text-muted">{h}</div>
      ))}
      {days.map(d=> {
        const arr = byDay(d) || []
        const dayNum = new Date(d).getDate()
        const faded = new Date(d).getMonth()!==curMonth
        return (
          <div key={d} className={cls('min-h-24 rounded-xl border p-2', faded? 'border-slate-100 text-slate-400':'border-slate-200')}> 
            <div className="mb-1 flex items-center justify-between">
              <div className="text-xs font-semibold">{pad(dayNum)}</div>
              {arr.length > 0 && (
                <button onClick={()=>onPickDay(d)} className="rounded-md border px-2 py-0.5 text-xs hover:bg-slate-100">День</button>
              )}
            </div>
            <div className="space-y-1">
              {arr.map(o=> (
                <button key={o.id} onClick={()=>onOpen(o)} className="flex w-full items-center gap-1 truncate rounded-md px-2 py-1 text-left hover:bg-slate-100 border text-xs">
                  <i className={cls('h-2 w-2 rounded-full flex-shrink-0', KIND_META[o.kind].dot)} />
                  <span className="truncate text-xs">#{o.order_id} · {o.customer}</span>
                </button>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

/******************** side panel ********************/
function SidePanel({open, onClose, date, orders, onOpen}){
  if(!open) return null
  const list = (orders || []).filter(o=>o.date===date)
  return (
    <div className="fixed inset-0 z-30 flex">
      <div className="h-full w-full bg-black/20" onClick={onClose} />
      <div className="absolute right-0 top-0 h-full w-full max-w-md overflow-y-auto rounded-l-2xl bg-white p-4 shadow-xl">
        <div className="mb-3 flex items-center justify-between">
          <div className="text-lg font-semibold">{new Date(date).toLocaleDateString('uk-UA')}</div>
          <button onClick={onClose} className="rounded-full bg-slate-900 px-3 py-1 text-sm text-white">Закрити</button>
        </div>
        <Legend />
        <div className="mt-3 space-y-2">
          {list.map(o=> (
            <div key={o.id} className="flex items-center justify-between rounded-xl border p-3">
              <div>
                <div className="font-medium text-corp-text-dark">#{o.order_id} · {o.customer}</div>
                <div className="text-xs text-corp-text-muted">{KIND_META[o.kind].label} · {fmtTime(o.time)} · {o.items} позицій</div>
              </div>
              <button onClick={()=>onOpen(o)} className="rounded-full bg-slate-900 px-3 py-1 text-sm text-white">Відкрити</button>
            </div>
          ))}
          {list.length===0 && <div className="text-sm text-corp-text-muted">Записів немає</div>}
        </div>
      </div>
    </div>
  )
}

/******************** main ********************/
export default function CalendarBoard(){
  const [view, setView] = useState('week')
  const [date, setDate] = useState(todayISO())
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [panel, setPanel] = useState({open:false, date: todayISO()})
  const navigate = useNavigate()

  // Load orders from backend
  useEffect(() => {
    const loadOrders = async () => {
      try {
        // Load orders for current month
        const start = startOfMonth(date)
        const end = endOfMonth(date)
        
        const response = await fetch(`${BACKEND_URL}/api/orders?from_date=${start}&to_date=${end}`, {
          method: 'GET',
          mode: 'cors',
          headers: { 'Content-Type': 'application/json' },
        })
        
        if (response.ok) {
          const result = await response.json()
          const data = result.orders || []
          
          // Transform orders from RentalHub DB to calendar format
          const calendarOrders = data.flatMap(o => {
            const results = []
            
            // Використовуємо issue_date та return_date як основні дати
            const issueDate = o.issue_date || o.rental_start_date
            const returnDate = o.return_date || o.rental_end_date
            
            // Видача - для всіх замовлень крім archived
            // Показуємо ready_for_issue та awaiting_customer як готові до видачі
            if (issueDate && ['ready_for_issue', 'awaiting_customer', 'processing', 'pending'].includes(o.status)) {
              results.push({
                id: `${o.order_id}-issue`,
                order_id: o.order_number,
                date: issueDate,
                time: '10:00',
                kind: 'issue',
                customer: o.client_name || o.customer_name,
                items: o.items?.length || 0,
                status: o.status,
                order: o
              })
            }
            
            // Повернення - для замовлень що issued або on_rent
            if (returnDate && (o.status === 'issued' || o.status === 'on_rent')) {
              results.push({
                id: `${o.order_id}-return`,
                order_id: o.order_number,
                date: returnDate,
                time: '16:00',
                kind: 'return',
                customer: o.client_name || o.customer_name,
                items: o.items?.length || 0,
                status: o.status,
                order: o
              })
            }
            
            return results
          })
          
          setOrders(calendarOrders)
        }
        setLoading(false)
      } catch (error) {
        console.error('Error loading calendar:', error)
        setLoading(false)
      }
    }
    
    loadOrders()
  }, [date])

  const counters = useMemo(()=>{
    const list = (orders || []).filter(o=> sameDay(o.date, date))
    return {
      issue: list.filter(o=>o.kind==='issue').length,
      return: list.filter(o=>o.kind==='return').length,
      total:  list.length
    }
  },[orders,date])

  const openOrder = (o)=> {
    if (o.order) {
      // Navigate to appropriate view
      if (o.kind === 'new') {
        navigate(`/order/${o.order.order_number}/view`)
      } else if (o.kind === 'issue') {
        // Navigate to issue card for ready_for_issue orders
        // Issue card has endpoints to mark as issued
        navigate(`/issue/${o.order.order_id}`)
      } else if (o.kind === 'return') {
        navigate(`/return/${o.order.order_number}`)
      }
    }
  }

  const onPickDay = (d)=> { setDate(d); setView('day') }

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-12 bg-slate-200 rounded"></div>
          <div className="h-96 bg-slate-200 rounded"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-7xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Календар ордерів</h1>
        <div className="flex gap-2">
          <button onClick={() => (window.history.length > 1 ? navigate(-1) : navigate('/'))} className="rounded-full bg-slate-200 px-3 py-1 text-sm">← Назад</button>
          <button onClick={()=>setPanel({open:true, date})} className="rounded-full bg-slate-900 px-3 py-1 text-sm text-white">Список на день</button>
        </div>
      </div>

      <Toolbar view={view} setView={setView} date={date} setDate={setDate} onToday={()=>setDate(todayISO())} />

      {/* KPI Bar - Horizontal */}
      <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="text-sm text-corp-text-main">
            На <span className="font-semibold">{new Date(date).toLocaleDateString('uk-UA')}</span>
          </div>
          <div className="flex flex-wrap gap-3">
            <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2">
              <i className="h-2 w-2 rounded-full bg-emerald-500" />
              <span className="text-xs text-emerald-700">Видача:</span>
              <span className="text-lg font-semibold text-emerald-900">{counters.issue}</span>
            </div>
            <div className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2">
              <i className="h-2 w-2 rounded-full bg-amber-500" />
              <span className="text-xs text-amber-700">Повернення:</span>
              <span className="text-lg font-semibold text-amber-900">{counters.return}</span>
            </div>
            <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-4 py-2">
              <i className="h-2 w-2 rounded-full bg-slate-500" />
              <span className="text-xs text-slate-700">Разом:</span>
              <span className="text-lg font-semibold text-corp-text-dark">{counters.total}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Calendar Views */}
      <div className="mt-4">
        {view==='day'   && <DayView   date={date} orders={orders} onOpen={openOrder} />}
        {view==='week'  && <WeekView  date={date} orders={orders} onOpen={openOrder} onPickDay={onPickDay} />}
        {view==='month' && <MonthView date={date} orders={orders} onOpen={openOrder} onPickDay={onPickDay} />}
      </div>

      <SidePanel open={panel.open} onClose={()=>setPanel({open:false, date})} date={panel.date} orders={orders} onOpen={openOrder} />
    </div>
  )
}
