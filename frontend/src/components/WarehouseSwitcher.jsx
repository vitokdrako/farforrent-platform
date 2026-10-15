/**
 * WarehouseSwitcher — dropdown у хедері з доступними складами.
 * Показується лише коли у юзера >= 2 складів. Інакше — просто бейдж.
 */
import React, { useState, useRef, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { ChevronDown, Check, Warehouse } from 'lucide-react'
import { useWarehouse } from '../context/WarehouseContext'

const FLAGS = {
  UA: '🇺🇦', PL: '🇵🇱', ES: '🇪🇸', DE: '🇩🇪', FR: '🇫🇷', IT: '🇮🇹',
}

export default function WarehouseSwitcher() {
  const { active, warehouses, switchTo, loading } = useWarehouse()
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    const onClick = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  if (loading || !active) return null

  const handleSelect = (code) => {
    switchTo(code)
    setOpen(false)
    // Якщо на warehouse-scoped URL — переходимо на той же сценарій іншого складу
    const m = location.pathname.match(/^\/admin\/warehouse\/[^/]+\/(.+)$/)
    if (m) {
      navigate(`/admin/warehouse/${code}/${m[1]}`)
    }
  }

  // Якщо склад один — просто бейдж без випадайки
  if (warehouses.length <= 1) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-100 text-slate-700 text-sm" data-testid="warehouse-badge">
        <span className="text-base">{FLAGS[active.country] || '📦'}</span>
        <span className="font-medium">{active.code}</span>
      </div>
    )
  }

  return (
    <div ref={ref} className="relative" data-testid="warehouse-switcher">
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium transition"
        data-testid="warehouse-switcher-btn"
      >
        <span className="text-base">{FLAGS[active.country] || '📦'}</span>
        <span>{active.code}</span>
        <span className="hidden md:inline text-slate-500 text-xs">· {active.city || active.name}</span>
        <ChevronDown className={`w-4 h-4 transition ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-72 bg-white rounded-xl shadow-xl border border-slate-200 overflow-hidden z-50" data-testid="warehouse-switcher-menu">
          <div className="px-3 py-2 text-xs font-bold uppercase text-slate-500 border-b border-slate-100">
            Склади
          </div>
          {warehouses.map(w => (
            <button
              key={w.code}
              onClick={() => handleSelect(w.code)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 hover:bg-slate-50 text-left ${
                w.code === active.code ? 'bg-sky-50' : ''
              }`}
              data-testid={`warehouse-option-${w.code}`}
            >
              <span className="text-xl">{FLAGS[w.country] || '📦'}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-slate-800">{w.code}</span>
                  {w.is_default && (
                    <span className="text-[10px] uppercase font-bold text-sky-600 bg-sky-100 px-1.5 py-0.5 rounded">default</span>
                  )}
                </div>
                <div className="text-xs text-slate-500 truncate">
                  {w.city || w.name} · {w.currency}
                </div>
              </div>
              {w.code === active.code && <Check className="w-4 h-4 text-sky-600 flex-shrink-0" />}
            </button>
          ))}
          <button
            onClick={() => { navigate('/admin/warehouses'); setOpen(false) }}
            className="w-full flex items-center gap-2 px-3 py-2.5 border-t border-slate-100 bg-slate-50 hover:bg-slate-100 text-sm text-slate-600 font-medium"
            data-testid="manage-warehouses-link"
          >
            <Warehouse className="w-4 h-4" />
            Керувати складами
          </button>
        </div>
      )}
    </div>
  )
}
