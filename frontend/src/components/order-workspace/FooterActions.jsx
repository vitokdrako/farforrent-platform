/* eslint-disable */
import React, { useState, useEffect, useRef } from 'react'
import { getStatusConfig } from './statusConfig'
import { MoreHorizontal, X } from 'lucide-react'

/**
 * FooterActions - Фіксований компактний футер з bottom-sheet
 * Mobile: 1 ряд (Save + Primary + More)
 * Desktop: розширена версія
 * 
 * ОПТИМІЗАЦІЯ Phase 2: useRef для scroll listener
 * - lastScrollY тепер в useRef (не викликає ререндер)
 * - scroll listener встановлюється один раз
 */
export default function FooterActions({
  status,
  onPrimaryAction,
  onSecondaryAction,
  onSave,
  primaryLabel,
  primaryDisabled = false,
  primaryDisabledReason,
  saving = false,
  showSave = true,
  additionalActions = [],
  children,
}) {
  const config = getStatusConfig(status)
  const effectivePrimaryLabel = primaryLabel || config.primaryAction
  const [showMore, setShowMore] = useState(false)
  const [hidden, setHidden] = useState(false)
  
  // ОПТИМІЗАЦІЯ Phase 2: useRef замість useState для lastScrollY
  const lastScrollYRef = useRef(0)
  
  // Hide/show footer on scroll (mobile UX) - ОПТИМІЗОВАНО
  useEffect(() => {
    const handleScroll = () => {
      const currentScrollY = window.scrollY
      const lastScrollY = lastScrollYRef.current
      
      // Ховаємо футер при швидкому скролі вниз
      if (currentScrollY > lastScrollY && currentScrollY > 100) {
        setHidden(true)
      } else {
        setHidden(false)
      }
      
      // Оновлюємо ref (не викликає ререндер)
      lastScrollYRef.current = currentScrollY
    }
    
    // Listener встановлюється один раз - без залежності від lastScrollY
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])  // Пустий масив - listener один раз
  
  // Фільтруємо додаткові дії для More меню
  const moreActions = additionalActions.filter(a => !a.alwaysShow)
  const visibleActions = additionalActions.filter(a => a.alwaysShow)
  
  return (
    <>
      {/* Main Footer */}
      <div className={`
        fixed bottom-0 left-0 right-0 bg-white border-t border-slate-200 z-20 
        transition-transform duration-200 safe-area-bottom
        ${hidden ? 'translate-y-full sm:translate-y-0' : 'translate-y-0'}
      `}>
        <div className="mx-auto max-w-7xl px-3 sm:px-6 py-2 sm:py-3">
          <div className="flex items-center justify-between gap-2">
            {/* Desktop: status info */}
            <div className="hidden sm:flex items-center gap-2 text-sm flex-shrink-0">
              {children || (
                <>
                  <span className="text-slate-500">Статус:</span>
                  <span className="font-medium text-slate-800">{config.title}</span>
                </>
              )}
            </div>
            
            {/* Mobile: compact actions row */}
            <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
              {/* Visible additional actions (desktop only) */}
              {visibleActions.map((action, idx) => (
                <button
                  key={idx}
                  onClick={action.onClick}
                  disabled={action.disabled}
                  className={`
                    hidden sm:inline-flex rounded-lg border px-3 py-2 text-sm font-medium transition-colors
                    disabled:opacity-50 disabled:cursor-not-allowed
                    ${action.variant === 'danger'
                      ? 'border-rose-200 text-rose-600 hover:bg-rose-50'
                      : 'border-slate-200 text-slate-700 hover:bg-slate-50'
                    }
                  `}
                >
                  {action.label}
                </button>
              ))}
              
              {/* More button (if has additional actions) */}
              {moreActions.length > 0 && (
                <button
                  onClick={() => setShowMore(true)}
                  className="p-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 active:bg-slate-100"
                >
                  <MoreHorizontal className="w-5 h-5" />
                </button>
              )}
              
              {/* Save button */}
              {showSave && onSave && (
                <button
                  onClick={onSave}
                  disabled={saving}
                  className="rounded-lg border border-slate-200 bg-white px-3 sm:px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 active:bg-slate-100 transition-colors disabled:opacity-50"
                >
                  {saving ? '⏳' : '💾'}
                  <span className="hidden sm:inline ml-1">{saving ? 'Збереження...' : 'Зберегти'}</span>
                </button>
              )}
              
              {/* Primary action - широка кнопка */}
              {effectivePrimaryLabel && onPrimaryAction && (
                <button
                  onClick={onPrimaryAction}
                  disabled={primaryDisabled || saving}
                  title={primaryDisabledReason}
                  className={`
                    flex-1 sm:flex-none rounded-lg px-4 sm:px-5 py-2 sm:py-2.5 text-sm font-medium transition-colors
                    disabled:opacity-50 disabled:cursor-not-allowed
                    ${primaryDisabled 
                      ? 'bg-slate-400 text-white cursor-not-allowed' 
                      : 'bg-slate-900 text-white hover:bg-slate-800 active:bg-slate-700'
                    }
                  `}
                >
                  {effectivePrimaryLabel}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
      
      {/* Bottom Sheet for More actions */}
      {showMore && (
        <div className="fixed inset-0 z-50" onClick={() => setShowMore(false)}>
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/30" />
          
          {/* Sheet */}
          <div 
            className="absolute bottom-0 left-0 right-0 bg-white rounded-t-2xl shadow-xl animate-slide-up safe-area-bottom"
            onClick={e => e.stopPropagation()}
          >
            {/* Handle */}
            <div className="flex justify-center pt-3 pb-2">
              <div className="w-10 h-1 bg-slate-300 rounded-full" />
            </div>
            
            {/* Header */}
            <div className="flex items-center justify-between px-4 pb-3 border-b border-slate-100">
              <span className="font-semibold text-slate-800">Додаткові дії</span>
              <button 
                onClick={() => setShowMore(false)}
                className="p-1 rounded-full hover:bg-slate-100"
              >
                <X className="w-5 h-5 text-slate-500" />
              </button>
            </div>
            
            {/* Actions list */}
            <div className="p-2 max-h-[50vh] overflow-y-auto">
              {moreActions.map((action, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setShowMore(false)
                    action.onClick?.()
                  }}
                  disabled={action.disabled}
                  className={`
                    w-full flex items-center gap-3 px-4 py-3 rounded-xl text-left font-medium transition-colors
                    disabled:opacity-50 disabled:cursor-not-allowed
                    ${action.variant === 'danger'
                      ? 'text-rose-600 hover:bg-rose-50 active:bg-rose-100'
                      : 'text-slate-700 hover:bg-slate-50 active:bg-slate-100'
                    }
                  `}
                >
                  {action.icon && <span className="text-lg">{action.icon}</span>}
                  <span>{action.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
