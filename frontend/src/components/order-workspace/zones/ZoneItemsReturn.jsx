/* eslint-disable */
import React, { useState } from 'react'
import ZoneCard from '../ZoneCard'
import { getImageUrl } from '../../../utils/imageHelper'
import { AlertTriangle, Check, ChevronDown, X, MoreVertical, Package } from 'lucide-react'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''

/**
 * Zone: Items Return - Приймання товарів при поверненні
 * Компактний мобільний дизайн (як ZoneItemsPickup)
 */
export default function ZoneItemsReturn({
  items = [],
  onSetReturnedQty,     // (itemId, qty) => void
  onToggleSerial,       // (itemId, serial) => void
  onOpenDamage,         // (itemId) => void
  onMarkAsLost,         // (itemId) => void
  readOnly = false,
  isCompleted = false,  // Чи завершено приймання
}) {
  const totalRented = items.reduce((s, it) => s + (it.rented_qty || 0), 0)
  const totalReturned = items.reduce((s, it) => s + (it.returned_qty || 0), 0)
  const totalFindings = items.reduce((s, it) => s + (it.findings?.length || 0), 0)
  const totalDamageHistory = items.reduce((s, it) => s + (it.damage_history?.length || 0), 0)
  
  const allReturned = items.every(it => it.returned_qty >= it.rented_qty)
  const tone = allReturned && totalFindings === 0 ? 'ok' : totalFindings > 0 ? 'warn' : 'info'

  return (
    <ZoneCard
      title={`Приймання (${totalReturned}/${totalRented})`}
      hint={totalDamageHistory > 0 ? `${totalDamageHistory} записів історії` : totalFindings > 0 ? `${totalFindings} зауважень` : 'Перевірте стан товарів'}
      tone={tone}
    >
      {items.length === 0 ? (
        <div className="text-center py-6 text-slate-400">Немає позицій</div>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <CompactReturnCard
              key={item.id}
              item={item}
              onSetReturnedQty={onSetReturnedQty}
              onToggleSerial={onToggleSerial}
              onOpenDamage={onOpenDamage}
              onMarkAsLost={onMarkAsLost}
              readOnly={readOnly}
              isCompleted={isCompleted}
            />
          ))}
        </div>
      )}
    </ZoneCard>
  )
}

function CompactReturnCard({ item, onSetReturnedQty, onToggleSerial, onOpenDamage, onMarkAsLost, readOnly, isCompleted }) {
  const [expanded, setExpanded] = useState(false)
  const [showPhoto, setShowPhoto] = useState(false)
  const [showDamagePhoto, setShowDamagePhoto] = useState(null)
  
  const photoUrl = getImageUrl(item.image || item.image_url)
  const rentedQty = item.rented_qty || 0
  const returnedQty = item.returned_qty || 0
  const findings = item.findings || []
  const serials = item.serials || []
  const okSerials = item.ok_serials || []
  
  // Історія пошкоджень
  const damageHistory = item.damage_history || []
  const hasDamageHistory = item.has_damage_history || damageHistory.length > 0
  
  const isFullyReturned = returnedQty >= rentedQty
  const hasDamage = findings.length > 0
  const isPartialReturn = returnedQty > 0 && returnedQty < rentedQty
  
  // Сірий тільки якщо завершено І повернуто І немає пошкоджень
  const isDisabled = isCompleted && isFullyReturned && !hasDamage
  
  const getBorderClass = () => {
    if (isDisabled) return 'border-slate-200 opacity-50'
    if (hasDamage) return 'border-amber-400'
    if (isFullyReturned) return 'border-emerald-300'
    if (isPartialReturn) return 'border-amber-300'
    return 'border-slate-200'
  }
  
  // Клік на фото
  const handlePhotoClick = (e) => {
    e.stopPropagation()
    if (expanded && photoUrl) {
      setShowPhoto(true)
    } else {
      setExpanded(true)
    }
  }
  
  return (
    <div className={`
      rounded-lg border bg-white overflow-hidden transition-all
      ${getBorderClass()}
      ${isDisabled ? 'pointer-events-none' : ''}
    `}>
      {/* Top row: Name + SKU + badges */}
      <div className="px-2 pt-2 pb-1">
        <div className="flex items-center gap-1 flex-wrap text-[11px]">
          <span className="font-medium text-slate-800 truncate max-w-[180px]">{item.name}</span>
          <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 font-mono">{item.sku || '—'}</span>
          
          {/* Статус бейджі */}
          {isCompleted && isFullyReturned && !hasDamage && (
            <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 font-medium">OK</span>
          )}
          {isPartialReturn && (
            <span className="px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 font-medium">Часткове</span>
          )}
          {hasDamage && (
            <span className="px-1.5 py-0.5 rounded bg-amber-500 text-white font-bold">{findings.length} пошк.</span>
          )}
          
          {/* Індикатор історії пошкоджень */}
          {hasDamageHistory && (
            <span className="px-1.5 py-0.5 rounded bg-red-500 text-white font-bold flex items-center gap-0.5">
              <AlertTriangle className="w-3 h-3" />
              Є історія ({damageHistory.length})
            </span>
          )}
          
          {/* Локація */}
          {item.location?.zone && item.location.zone !== 'None' && (
            <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700">{item.location.zone}</span>
          )}
        </div>
      </div>
      
      {/* Main row: Photo + Stepper + Actions */}
      <div className="flex items-center gap-2 px-2 pb-2">
        {/* Photo */}
        <div 
          className={`
            w-10 h-10 flex-shrink-0 rounded-lg overflow-hidden bg-slate-100 cursor-pointer
            transition-all active:scale-95
            ${expanded && photoUrl ? 'ring-2 ring-blue-300' : ''}
          `}
          onClick={handlePhotoClick}
        >
          {photoUrl ? (
            <img src={photoUrl} alt="" className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-slate-300 text-xs">—</div>
          )}
        </div>
        
        {/* Stepper */}
        <div className="flex items-center gap-1 flex-1" onClick={e => e.stopPropagation()}>
          <button 
            onClick={() => !readOnly && onSetReturnedQty?.(item.id, Math.max(0, returnedQty - 1))} 
            disabled={readOnly || returnedQty === 0}
            className="w-8 h-8 rounded-lg border border-slate-300 bg-white text-base font-bold disabled:opacity-30 active:bg-slate-100"
          >
            −
          </button>
          <input
            type="number"
            value={returnedQty}
            onChange={(e) => {
              if (readOnly) return;
              const v = Math.max(0, Math.min(rentedQty, parseInt(e.target.value) || 0));
              onSetReturnedQty?.(item.id, v);
            }}
            disabled={readOnly}
            className={`
              w-10 h-8 text-center text-sm font-bold border border-slate-200 rounded-lg
              [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none
              ${isFullyReturned ? 'text-emerald-600' : 'text-slate-800'}
              disabled:opacity-50
            `}
            min="0"
            max={rentedQty}
            data-testid={`return-qty-input-${item.id}`}
          />
          <button 
            onClick={() => !readOnly && onSetReturnedQty?.(item.id, Math.min(rentedQty, returnedQty + 1))} 
            disabled={readOnly || returnedQty >= rentedQty}
            className="w-8 h-8 rounded-lg border border-slate-300 bg-white text-base font-bold disabled:opacity-30 active:bg-slate-100"
          >
            +
          </button>
          <span className="text-xs text-slate-400">/{rentedQty}</span>
        </div>
        
        {/* Quick complete / Status */}
        <div className="flex-shrink-0" onClick={e => e.stopPropagation()}>
          {isFullyReturned ? (
            <div className="w-8 h-8 rounded-lg bg-emerald-100 flex items-center justify-center">
              <Check className="w-5 h-5 text-emerald-600" />
            </div>
          ) : !readOnly ? (
            <button 
              onClick={() => onSetReturnedQty?.(item.id, rentedQty)}
              className="w-8 h-8 rounded-lg bg-emerald-500 text-white flex items-center justify-center active:bg-emerald-600"
            >
              <Check className="w-5 h-5" />
            </button>
          ) : null}
        </div>
        
        {/* Expand toggle */}
        <button 
          onClick={() => setExpanded(!expanded)}
          className="w-8 h-8 rounded-lg border border-slate-200 flex items-center justify-center active:bg-slate-100"
        >
          <ChevronDown className={`w-4 h-4 text-slate-500 transition-transform ${expanded ? 'rotate-180' : ''}`} />
        </button>
      </div>
      
      {/* Expanded content */}
      {expanded && (
        <div className="px-2 pb-2 space-y-2 border-t border-slate-100 pt-2">
          {/* Damage History Alert */}
          {hasDamageHistory && (
            <div className="rounded-lg bg-red-50 border border-red-200 p-2">
              <div className="flex items-center gap-1 text-xs font-semibold text-red-700 mb-1">
                <AlertTriangle className="w-3.5 h-3.5" />
                Історія пошкоджень ({damageHistory.length})
              </div>
              <div className="text-[10px] text-red-600 mb-1.5">
                Перевірте ці дефекти перед прийманням
              </div>
              <div className="space-y-1.5 max-h-[150px] overflow-y-auto">
                {damageHistory.slice(0, 5).map((d, idx) => {
                  const getFullPhotoUrl = (url) => {
                    if (!url) return null;
                    if (url.startsWith('http')) return url;
                    const base = BACKEND_URL.endsWith('/') ? BACKEND_URL.slice(0, -1) : BACKEND_URL;
                    const cleanPath = url.startsWith('/') ? url : `/${url}`;
                    return `${base}${cleanPath}`;
                  };
                  const photoUrl = getFullPhotoUrl(d.photo_url);
                  
                  return (
                  <div key={d.id || idx} className="flex items-start gap-2 text-[10px] bg-white rounded p-1.5 border border-red-100">
                    {photoUrl && (
                      <img 
                        src={photoUrl} 
                        alt="" 
                        className="w-10 h-10 rounded object-cover flex-shrink-0 cursor-pointer border-2 border-red-200 hover:border-red-400"
                        onClick={(e) => { 
                          e.stopPropagation()
                          setShowDamagePhoto(photoUrl)
                        }}
                      />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1 flex-wrap">
                        <span className={`px-1 py-0.5 rounded text-[9px] font-medium ${
                          d.stage === 'pre_issue' ? 'bg-blue-100 text-blue-700' : 
                          d.stage === 'return' ? 'bg-orange-100 text-orange-700' : 'bg-slate-100 text-slate-600'
                        }`}>
                          {d.stage_label || (d.stage === 'pre_issue' ? 'До видачі' : d.stage === 'return' ? 'Повернення' : 'Аудит')}
                        </span>
                        {d.order_number && <span className="text-slate-400">#{d.order_number}</span>}
                        {(d.qty || 1) > 1 && <span className="font-bold text-slate-700">{d.qty} шт</span>}
                        {d.fee > 0 && <span className="text-red-600 font-medium">₴{d.fee}</span>}
                      </div>
                      <div className="font-medium text-slate-700">
                        {d.damage_type || d.type}
                        {(d.qty || 1) > 1 && d.fee > 0 && (
                          <span className="text-slate-400 font-normal ml-1">
                            ({d.qty} шт × ₴{Math.round(d.fee / d.qty)}/шт)
                          </span>
                        )}
                      </div>
                      {d.note && <div className="text-slate-500 truncate">{d.note}</div>}
                      <div className="text-slate-400">{d.created_at}</div>
                    </div>
                  </div>
                )})}
              </div>
              {damageHistory.length > 5 && (
                <div className="text-center text-[10px] text-red-600 mt-1">
                  + ще {damageHistory.length - 5} записів
                </div>
              )}
            </div>
          )}
          
          {/* Current findings */}
          {findings.length > 0 && (
            <div className="rounded-lg bg-amber-50 border border-amber-200 p-2">
              <div className="text-xs text-amber-700 font-medium mb-1">Зафіксовані пошкодження:</div>
              {findings.map((f, idx) => (
                <div key={idx} className="text-[11px] text-amber-800">
                  • {f.category || f.type} - {f.kind || f.description}
                  {(f.qty || 1) > 1 && <span className="font-bold ml-1">{f.qty} шт</span>}
                  {f.fee > 0 && (
                    <span className="ml-1">
                      (₴{f.fee}
                      {(f.qty || 1) > 1 && ` = ${f.qty} шт × ₴${Math.round(f.fee / f.qty)}/шт`}
                      )
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
          
          {/* Issued Packaging per item */}
          {item.issued_packaging && Object.keys(item.issued_packaging).filter(k => k !== 'other_text').some(k => (parseInt(item.issued_packaging[k]) || 0) > 0) && (
            <div className="rounded-lg bg-blue-50 border border-blue-200 p-2">
              <div className="text-[10px] text-blue-600 font-semibold mb-1 flex items-center gap-1">
                <Package className="w-3 h-3" /> Видано пакування:
              </div>
              <div className="flex flex-wrap gap-1.5">
                {[
                  { key: 'native_cover', label: 'Чохол' },
                  { key: 'native_box', label: 'Коробка' },
                  { key: 'felt', label: 'Войлок' },
                  { key: 'special', label: 'Спец.' },
                  { key: 'other', label: item.issued_packaging?.other_text || 'Інше' },
                ].filter(o => (parseInt(item.issued_packaging?.[o.key]) || 0) > 0).map(o => (
                  <span key={o.key} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-100 text-blue-800 text-[10px] font-medium">
                    {o.label}: {item.issued_packaging[o.key]}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Serials */}
          {serials.length > 0 && (
            <div>
              <div className="text-[10px] text-slate-500 mb-1">Серійні номери:</div>
              <div className="flex flex-wrap gap-1">
                {serials.map(serial => {
                  const isOk = okSerials.includes(serial)
                  return (
                    <button
                      key={serial}
                      onClick={() => !readOnly && onToggleSerial?.(item.id, serial)}
                      disabled={readOnly}
                      className={`
                        rounded px-2 py-1 text-[10px] font-medium border transition-all
                        ${isOk 
                          ? 'border-emerald-400 bg-emerald-100 text-emerald-700' 
                          : 'border-slate-200 bg-white hover:bg-slate-50'
                        }
                        disabled:opacity-50
                      `}
                    >
                      {serial} {isOk && '✓'}
                    </button>
                  )
                })}
              </div>
            </div>
          )}
          
          {/* Damage button */}
          {onOpenDamage && !readOnly && (
            <button 
              onClick={() => onOpenDamage(item.id)} 
              className="w-full py-2 rounded-lg bg-amber-500 text-white text-xs font-medium active:bg-amber-600"
            >
              Зафіксувати пошкодження
            </button>
          )}
          {/* Mark as Lost button — повна втрата, списується з quantity */}
          {onMarkAsLost && !readOnly && item.status !== 'lost' && (
            <button
              onClick={() => onMarkAsLost(item.id)}
              data-testid={`btn-mark-lost-${item.id}`}
              className="w-full py-2 mt-1 rounded-lg border border-red-600 text-red-600 text-xs font-medium active:bg-red-50"
            >
              ❌ Повна втрата (списати)
            </button>
          )}
          {item.status === 'lost' && (
            <div className="w-full py-2 mt-1 rounded-lg bg-red-50 text-red-700 text-xs font-medium text-center">
              ✓ Списано як втрату
            </div>
          )}
        </div>
      )}
      
      {/* Photo Modal */}
      {showPhoto && photoUrl && (
        <div 
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/90 p-4"
          onClick={() => setShowPhoto(false)}
        >
          <div className="relative max-w-full max-h-full">
            <img 
              src={photoUrl} 
              alt={item.name}
              className="max-w-full max-h-[85vh] object-contain rounded-lg shadow-2xl"
            />
            <button 
              className="absolute top-3 right-3 w-10 h-10 rounded-full bg-white/20 backdrop-blur text-white flex items-center justify-center"
              onClick={(e) => { e.stopPropagation(); setShowPhoto(false) }}
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>
      )}
      
      {/* Damage Photo Modal */}
      {showDamagePhoto && (
        <div 
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/90 p-4"
          onClick={() => setShowDamagePhoto(null)}
        >
          <div className="relative max-w-full max-h-full">
            <img 
              src={showDamagePhoto} 
              alt="Фото пошкодження"
              className="max-w-full max-h-[85vh] object-contain rounded-lg shadow-2xl"
            />
            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-4 rounded-b-lg">
              <div className="text-white font-medium text-center">📷 Фото пошкодження</div>
              <div className="text-white/70 text-sm text-center">{item.name}</div>
            </div>
            <button 
              className="absolute top-3 right-3 w-10 h-10 rounded-full bg-white/20 backdrop-blur text-white flex items-center justify-center"
              onClick={(e) => { e.stopPropagation(); setShowDamagePhoto(null) }}
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
