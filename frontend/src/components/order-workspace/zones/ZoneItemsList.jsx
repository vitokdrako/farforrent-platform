/* eslint-disable */
import React, { useState, useEffect, useRef, useCallback } from 'react'
import ZoneCard from '../ZoneCard'
import { getImageUrl } from '../../../utils/imageHelper'

// Debounce хук для відкладеного збереження
function useDebounce(callback, delay) {
  const timeoutRef = useRef(null)
  
  const debouncedCallback = useCallback((...args) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }
    timeoutRef.current = setTimeout(() => {
      callback(...args)
    }, delay)
  }, [callback, delay])
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [])
  
  return debouncedCallback
}

/**
 * Zone: Items List - Список позицій
 * Універсальний для всіх статусів
 */
export default function ZoneItemsList({
  items = [],
  rentalDays = 1,
  mode = 'view',  // view | edit | pick | return
  onUpdateQuantity,
  onRemoveItem,
  onTogglePicked,
  onOpenDamage,
  highlightedItems = new Set(), // IDs нових позицій для підсвітки
}) {
  const fmtUA = (n) => (Number(n) || 0).toLocaleString('uk-UA', { maximumFractionDigits: 0 })
  
  const canEdit = mode === 'edit'
  const canPick = mode === 'pick'
  const canReturn = mode === 'return'
  
  // Розрахунок сум
  const totals = items.reduce((acc, item) => {
    const qty = parseInt(item.quantity || item.qty) || 0
    const pricePerDay = parseFloat(item.price_per_day || item.price) || 0
    const deposit = parseFloat(item.deposit || item.damage_cost) || 0
    
    acc.rent += pricePerDay * qty * rentalDays
    acc.deposit += deposit * qty
    acc.items += qty
    return acc
  }, { rent: 0, deposit: 0, items: 0 })
  
  return (
    <ZoneCard
      title={`Позиції замовлення (${items.length})`}
      hint={`Всього ${totals.items} од. • Оренда: ₴${fmtUA(totals.rent)} • Застава: ₴${fmtUA(totals.deposit)}`}
      tone="neutral"
    >
      {items.length === 0 ? (
        <div className="text-center py-6 text-corp-text-muted">
          Немає позицій
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item, idx) => {
            const itemId = item.inventory_id || item.id
            const isHighlighted = highlightedItems instanceof Set 
              ? highlightedItems.has(itemId) 
              : false
            
            return (
              <ItemRow 
                key={item.id || idx}
                item={item}
                rentalDays={rentalDays}
                canEdit={canEdit}
                canPick={canPick}
                canReturn={canReturn}
                onUpdateQuantity={onUpdateQuantity}
                onRemoveItem={onRemoveItem}
                onTogglePicked={onTogglePicked}
                onOpenDamage={onOpenDamage}
                isHighlighted={isHighlighted}
              />
            )
          })}
        </div>
      )}
    </ZoneCard>
  )
}

function ItemRow({ 
  item, 
  rentalDays, 
  canEdit, 
  canPick, 
  canReturn,
  onUpdateQuantity,
  onRemoveItem,
  onTogglePicked,
  onOpenDamage,
  isHighlighted = false,
}) {
  const fmtUA = (n) => (Number(n) || 0).toLocaleString('uk-UA', { maximumFractionDigits: 0 })
  const [showDamagePhoto, setShowDamagePhoto] = useState(null)
  const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''
  
  const getPhotoUrl = (url) => {
    if (!url) return ''
    if (url.startsWith('http')) return url
    return `${BACKEND_URL}${url.startsWith('/') ? '' : '/'}${url}`
  }
  
  const qty = parseInt(item.quantity || item.qty) || 0
  const pricePerDay = parseFloat(item.price_per_day || item.price) || 0
  const deposit = parseFloat(item.deposit || item.damage_cost) || 0
  const sku = item.article || item.sku || item.model || ''
  const name = item.name || item.product_name || ''
  const image = item.image || item.photo || ''
  
  // Локація - тепер тільки zone
  const location = item.location || {}
  const validValue = (v) => v && v !== 'None' && v !== 'null'
  const zoneStr = validValue(location.zone) ? location.zone : (validValue(item.zone) ? item.zone : null)
  
  const totalRent = pricePerDay * qty * rentalDays
  const totalDeposit = deposit * qty
  
  // Для комплектації
  const pickedQty = parseInt(item.picked_qty) || 0
  const isFullyPicked = pickedQty >= qty
  
  // Для повернення
  const returnedQty = parseInt(item.returned_qty) || 0
  const hasFindings = (item.findings || []).length > 0
  
  return (
    <div className={`
      relative rounded-lg border bg-white p-3 flex gap-3 transition-all duration-500
      ${canPick && isFullyPicked ? 'border-corp-primary bg-corp-primary/5' : 'border-corp-border'}
      ${canReturn && hasFindings ? 'border-amber-300 bg-amber-50' : ''}
      ${isHighlighted ? 'ring-2 ring-green-400 border-green-400 bg-green-50 animate-pulse' : ''}
    `}>
      {/* Позначка NEW для нових */}
      {isHighlighted && (
        <div className="absolute -top-2 -right-2 bg-green-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">
          NEW
        </div>
      )}
      
      {/* Зображення */}
      <div className="w-16 h-16 flex-shrink-0 rounded-lg overflow-hidden bg-corp-bg-light">
        {image ? (
          <img 
            src={getImageUrl ? getImageUrl(image) : image} 
            alt={name}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-corp-text-muted text-xs">
            Фото
          </div>
        )}
      </div>
      
      {/* Інфо */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="font-medium text-corp-text-dark text-sm truncate flex items-center gap-1">
              {name}
              {item.has_damage_history && (
                <span className="inline-flex items-center flex-shrink-0 text-amber-500" title={`Є пошкодження (${item.damage_history?.length || 0})`} data-testid={`damage-warning-${item.id || item.inventory_id}`}>
                  <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 6a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 6zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" /></svg>
                </span>
              )}
            </div>
            <div className="text-xs text-corp-text-muted">{sku}</div>
            {/* Локація - тільки zone */}
            {zoneStr && (
              <div className="mt-1 inline-flex items-center gap-2 px-2 py-0.5 rounded bg-corp-bg-light text-xs text-corp-text-main">
                📍 <b>{zoneStr}</b>
              </div>
            )}
            {/* Повна історія пошкоджень з фото */}
            {item.has_damage_history && item.damage_history?.length > 0 && (
              <div className="mt-1.5 rounded-lg bg-amber-50 border border-amber-200 p-2" data-testid={`damage-history-block-${item.id || item.inventory_id}`}>
                <div className="flex items-center gap-1 text-xs font-semibold text-amber-700 mb-1.5">
                  <svg className="w-3.5 h-3.5 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 6a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 6zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" /></svg>
                  Історія пошкоджень ({item.damage_history.length})
                </div>
                <div className="space-y-1.5 max-h-[180px] overflow-y-auto">
                  {item.damage_history.slice(0, 5).map((d, idx) => (
                    <div key={d.id || idx} className="flex items-start gap-2 text-[11px] bg-white rounded-lg p-2 border border-amber-100">
                      {d.photo_url && (
                        <img 
                          src={getPhotoUrl(d.photo_url)} 
                          alt="" 
                          className="w-12 h-12 rounded-lg object-cover flex-shrink-0 cursor-pointer border-2 border-amber-300 hover:border-amber-500 transition-all active:scale-95"
                          onClick={() => setShowDamagePhoto(getPhotoUrl(d.photo_url))}
                        />
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1 flex-wrap">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                            d.severity === 'critical' ? 'bg-red-100 text-red-700' :
                            d.severity === 'high' ? 'bg-orange-100 text-orange-700' :
                            d.severity === 'medium' ? 'bg-amber-100 text-amber-700' : 'bg-green-100 text-green-700'
                          }`}>
                            {d.damage_type || d.type || '—'}
                          </span>
                          <span className="text-amber-500 text-[10px]">{d.stage_label || d.stage || ''}</span>
                        </div>
                        {d.note && <div className="text-slate-600 mt-0.5 truncate">{d.note}</div>}
                        <div className="text-slate-400 text-[10px] mt-0.5 flex items-center gap-2">
                          {d.created_at && <span>{d.created_at}</span>}
                          {d.created_by && <span>{d.created_by}</span>}
                          {d.fee > 0 && <span className="text-amber-600 font-medium">₴{d.fee}</span>}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                {item.damage_history.length > 5 && (
                  <div className="text-center text-[10px] text-amber-600 mt-1 font-medium">
                    + ще {item.damage_history.length - 5} записів
                  </div>
                )}
              </div>
            )}
          </div>
          
          {/* Кількість */}
          {canEdit ? (
            <QuantityInput
              value={qty}
              onChange={(newQty) => onUpdateQuantity?.(item.inventory_id || item.id, newQty)}
            />
          ) : (
            <div className="text-sm font-medium text-corp-text-dark">
              {qty} шт.
            </div>
          )}
        </div>
        
        {/* Ціни */}
        <div className="mt-2 flex items-center gap-3 text-xs">
          <span className="text-corp-text-main">
            ₴{fmtUA(pricePerDay)}/дн. × {rentalDays} = <b className="text-corp-text-dark">₴{fmtUA(totalRent)}</b>
          </span>
          <span className="text-corp-gold">
            Заст: <b>₴{fmtUA(totalDeposit)}</b>
          </span>
        </div>
        
        {/* Комплектація */}
        {canPick && (
          <div className="mt-2 flex items-center gap-2">
            <button
              onClick={() => onTogglePicked?.(item.id)}
              className={`
                px-3 py-1 rounded-lg text-xs font-medium transition-colors
                ${isFullyPicked 
                  ? 'bg-corp-primary text-white' 
                  : 'bg-corp-bg-light text-corp-text-main hover:bg-corp-border'
                }
              `}
            >
              {isFullyPicked ? 'Зібрано' : 'Зібрати'}
            </button>
            <span className="text-xs text-corp-text-muted">
              {pickedQty}/{qty}
            </span>
          </div>
        )}
        
        {/* Повернення */}
        {canReturn && (
          <div className="mt-2 flex items-center gap-2">
            <span className="text-xs text-corp-text-muted">
              Повернуто: {returnedQty}/{qty}
            </span>
            {onOpenDamage && (
              <button
                onClick={() => onOpenDamage?.(item.id)}
                className="px-2 py-1 rounded text-xs bg-amber-100 text-amber-700 hover:bg-amber-200"
              >
                Знахідка
              </button>
            )}
            {hasFindings && (
              <span className="text-xs text-amber-600">
                {item.findings.length} знахідок
              </span>
            )}
          </div>
        )}
      </div>
      
      {/* Видалити */}
      {canEdit && onRemoveItem && (
        <button
          onClick={() => onRemoveItem?.(item.inventory_id || item.id)}
          className="text-rose-500 hover:text-rose-700 text-lg font-bold"
          title="Видалити"
        >
          ×
        </button>
      )}
      
      {/* Модалка повнорозмірного фото пошкодження */}
      {showDamagePhoto && (
        <div 
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/90 p-4"
          onClick={() => setShowDamagePhoto(null)}
          data-testid="damage-photo-fullscreen"
        >
          <div className="relative max-w-full max-h-full">
            <img 
              src={showDamagePhoto} 
              alt="Фото пошкодження"
              className="max-w-full max-h-[85vh] object-contain rounded-lg shadow-2xl"
            />
            <button 
              className="absolute top-3 right-3 w-10 h-10 rounded-full bg-white/20 backdrop-blur text-white flex items-center justify-center hover:bg-white/30 transition-colors"
              onClick={(e) => { e.stopPropagation(); setShowDamagePhoto(null) }}
            >
              <span className="text-xl font-bold">✕</span>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * QuantityInput - Компонент для редагування кількості
 * - Кнопки +/- для швидкого редагування
 * - Можливість ввести число вручну
 * - Debounce 800ms перед збереженням
 */
function QuantityInput({ value, onChange, min = 1, max = 999 }) {
  const [localValue, setLocalValue] = useState(value)
  const [isEditing, setIsEditing] = useState(false)
  const inputRef = useRef(null)
  
  // Синхронізація з зовнішнім значенням
  useEffect(() => {
    if (!isEditing) {
      setLocalValue(value)
    }
  }, [value, isEditing])
  
  // Debounced save - зберігати через 800ms після останньої зміни
  const debouncedSave = useDebounce((newValue) => {
    const numValue = parseInt(newValue) || min
    const clampedValue = Math.min(Math.max(numValue, min), max)
    if (clampedValue !== value) {
      onChange(clampedValue)
    }
  }, 800)
  
  // Обробник зміни input
  const handleInputChange = (e) => {
    const newValue = e.target.value
    // Дозволити тільки цифри
    if (/^\d*$/.test(newValue)) {
      setLocalValue(newValue)
      if (newValue !== '') {
        debouncedSave(newValue)
      }
    }
  }
  
  // Обробник кнопок +/-
  const handleButtonClick = (delta) => {
    const newValue = Math.min(Math.max((parseInt(localValue) || min) + delta, min), max)
    setLocalValue(newValue)
    debouncedSave(newValue)
  }
  
  // При фокусі - виділити весь текст
  const handleFocus = () => {
    setIsEditing(true)
    setTimeout(() => {
      inputRef.current?.select()
    }, 0)
  }
  
  // При втраті фокусу - зберегти одразу
  const handleBlur = () => {
    setIsEditing(false)
    const numValue = parseInt(localValue) || min
    const clampedValue = Math.min(Math.max(numValue, min), max)
    setLocalValue(clampedValue)
    if (clampedValue !== value) {
      onChange(clampedValue)
    }
  }
  
  // Enter - зберегти і зняти фокус
  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      inputRef.current?.blur()
    }
    if (e.key === 'Escape') {
      setLocalValue(value)
      inputRef.current?.blur()
    }
  }
  
  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        onClick={() => handleButtonClick(-1)}
        disabled={parseInt(localValue) <= min}
        className="w-7 h-7 rounded bg-corp-bg-light hover:bg-corp-border text-corp-text-main disabled:opacity-40 disabled:cursor-not-allowed"
      >
        −
      </button>
      <input
        ref={inputRef}
        type="text"
        inputMode="numeric"
        value={localValue}
        onChange={handleInputChange}
        onFocus={handleFocus}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        className="w-12 h-7 text-center font-medium text-corp-text-dark bg-white border border-corp-border rounded focus:outline-none focus:ring-2 focus:ring-corp-primary focus:border-transparent"
      />
      <button
        type="button"
        onClick={() => handleButtonClick(1)}
        disabled={parseInt(localValue) >= max}
        className="w-7 h-7 rounded bg-corp-bg-light hover:bg-corp-border text-corp-text-main disabled:opacity-40 disabled:cursor-not-allowed"
      >
        +
      </button>
    </div>
  )
}

