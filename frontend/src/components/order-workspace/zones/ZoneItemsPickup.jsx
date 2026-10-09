/* eslint-disable */
import React, { useState } from 'react'
import ZoneCard from '../ZoneCard'
import { getImageUrl } from '../../../utils/imageHelper'
import { MoreVertical, X, Trash2, AlertTriangle, Package, Check, ChevronUp, ChevronDown } from 'lucide-react'

/**
 * Zone: Items Pickup - Компактна мобільна версія комплектування
 */
export default function ZoneItemsPickup({
  items = [],
  onPick,
  onScan,
  onOpenDamage,
  onPackagingChange,
  onRemoveItem,
  readOnly = false,
}) {
  const totalItems = items.length
  const pickedItems = items.filter(it => it.picked_qty >= it.qty).length
  const totalQty = items.reduce((s, it) => s + (it.qty || 0), 0)
  const pickedQty = items.reduce((s, it) => s + (it.picked_qty || 0), 0)
  
  const tone = pickedItems === totalItems ? 'ok' : pickedItems > 0 ? 'info' : 'neutral'
  
  return (
    <ZoneCard
      title={`Комплектування`}
      hint={`${pickedItems}/${totalItems} позицій • ${pickedQty}/${totalQty} од.`}
      tone={tone}
      compact
    >
      {items.length === 0 ? (
        <div className="text-center py-4 text-slate-400 text-sm">
          Немає позицій
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <CompactItemCard
              key={item.id}
              item={item}
              onPick={onPick}
              onScan={onScan}
              onOpenDamage={onOpenDamage}
              onPackagingChange={onPackagingChange}
              onRemoveItem={onRemoveItem}
              readOnly={readOnly}
            />
          ))}
        </div>
      )}
    </ZoneCard>
  )
}

function CompactItemCard({ 
  item, 
  onPick, 
  onScan, 
  onOpenDamage, 
  onPackagingChange,
  onRemoveItem,
  readOnly 
}) {
  const [expanded, setExpanded] = useState(false)
  const [showMenu, setShowMenu] = useState(false)
  const [showPackaging, setShowPackaging] = useState(false)
  const [showPhoto, setShowPhoto] = useState(false)
  const [showDamagePhoto, setShowDamagePhoto] = useState(null) // URL для модалки фото пошкодження
  
  const photoUrl = getImageUrl(item.image || item.image_url)
  const qty = item.qty || 0
  const pickedQty = item.picked_qty || 0
  const isComplete = pickedQty >= qty
  const isNew = item.is_new === true
  const qtyChanged = item.qty_changed === true
  
  // Packaging options
  const packagingOptions = [
    { key: 'native_cover', label: 'Рідний чохол' },
    { key: 'native_box', label: 'Рідна коробка' },
    { key: 'felt', label: 'Войлок' },
    { key: 'special', label: 'Спец. пакування' },
    { key: 'other', label: 'Інше' },
  ]
  
  const selectedPackaging = packagingOptions.filter(p => item.packaging?.[p.key]).map(p => p.label)

  const packagingSummary = packagingOptions
    .filter(p => (parseInt(item.packaging?.[p.key]) || 0) > 0)
    .map(p => `${p.label}: ${item.packaging[p.key]}`)
  
  // Обробка кліку на фото
  const handlePhotoClick = (e) => {
    e.stopPropagation()
    if (expanded && photoUrl) {
      // Картка вже розгорнута - показуємо збільшене фото
      setShowPhoto(true)
    } else {
      // Картка згорнута - розгортаємо її
      setExpanded(true)
    }
  }
  
  return (
    <div className={`
      rounded-lg border bg-white overflow-hidden transition-all
      ${isNew ? 'border-blue-400 ring-1 ring-blue-200' : 
        qtyChanged ? 'border-amber-400' :
        isComplete ? 'border-emerald-300' : 'border-slate-200'}
    `}>
      {/* Top row: Name + SKU as badges */}
      <div className="px-2 pt-2 pb-1">
        <div className="flex items-center gap-1 flex-wrap text-[11px]">
          <span className="font-medium text-slate-800 truncate max-w-[200px]">{item.name}</span>
          <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 font-mono">{item.sku || '—'}</span>
          {isNew && <span className="px-1.5 py-0.5 rounded bg-blue-500 text-white font-bold">NEW</span>}
          {qtyChanged && !isNew && <span className="px-1.5 py-0.5 rounded bg-amber-500 text-white font-bold">ЗМ.</span>}
          {/* Індикатор історії пошкоджень */}
          {item.has_damage_history && item.total_damages > 0 && (
            <span className="px-1.5 py-0.5 rounded bg-red-500 text-white font-bold flex items-center gap-0.5">
              <AlertTriangle className="w-3 h-3" />
              {item.total_damages}
            </span>
          )}
          {item.location?.zone && item.location.zone !== 'None' && (
            <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700">{item.location.zone}</span>
          )}
        </div>
      </div>
      
      {/* Main row: Photo + Stepper + Actions */}
      <div className="flex items-center gap-2 px-2 pb-2">
        {/* Photo - clickable */}
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
            onClick={() => !readOnly && onPick?.(item.id, Math.max(0, pickedQty - 1))} 
            disabled={readOnly || pickedQty === 0}
            className="w-8 h-8 rounded-lg border border-slate-300 bg-white text-base font-bold disabled:opacity-30 active:bg-slate-100"
          >
            −
          </button>
          <input
            type="number"
            value={pickedQty}
            onChange={(e) => {
              if (readOnly) return;
              const v = Math.max(0, parseInt(e.target.value) || 0);
              onPick?.(item.id, v);
            }}
            disabled={readOnly}
            className={`
              w-10 h-8 text-center text-sm font-bold border border-slate-200 rounded-lg
              [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none
              ${isComplete ? 'text-emerald-600' : 'text-slate-800'}
              disabled:opacity-50
            `}
            min="0"
            data-testid={`pick-qty-input-${item.id}`}
          />
          <button 
            onClick={() => !readOnly && onPick?.(item.id, pickedQty + 1)} 
            disabled={readOnly}
            className="w-8 h-8 rounded-lg border border-slate-300 bg-white text-base font-bold disabled:opacity-30 active:bg-slate-100"
          >
            +
          </button>
          <span className="text-xs text-slate-400">/{qty}</span>
        </div>
        
        {/* Quick complete */}
        <div className="flex-shrink-0" onClick={e => e.stopPropagation()}>
          {isComplete ? (
            <div className="w-8 h-8 rounded-lg bg-emerald-100 flex items-center justify-center">
              <Check className="w-5 h-5 text-emerald-600" />
            </div>
          ) : !readOnly ? (
            <button 
              onClick={() => onPick?.(item.id, qty)}
              className="w-8 h-8 rounded-lg bg-emerald-500 text-white flex items-center justify-center active:bg-emerald-600"
            >
              <Check className="w-5 h-5" />
            </button>
          ) : null}
        </div>
        
        {/* Expand/Collapse toggle */}
        <button 
          onClick={() => setExpanded(!expanded)}
          className="p-1 rounded text-slate-400 hover:bg-slate-100"
        >
          {expanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
        </button>
        
        {/* More menu */}
        <button 
          onClick={(e) => { e.stopPropagation(); setShowMenu(true) }}
          className="p-1 rounded text-slate-400 hover:bg-slate-100"
        >
          <MoreVertical className="w-5 h-5" />
        </button>
      </div>
      
      {/* Expanded content */}
      {expanded && (
        <div className="px-2 pb-2 space-y-2 border-t border-slate-100 pt-2">
          {/* Damage History Alert */}
          {item.has_damage_history && item.damage_history?.length > 0 && (
            <div className="rounded-lg bg-red-50 border border-red-200 p-2">
              <div className="flex items-center gap-1 text-xs font-semibold text-red-700 mb-1.5">
                <AlertTriangle className="w-3.5 h-3.5" />
                Історія пошкоджень ({item.damage_history.length})
              </div>
              <div className="space-y-1.5 max-h-[120px] overflow-y-auto">
                {item.damage_history.slice(0, 5).map((d, idx) => (
                  <div key={d.id || idx} className="flex items-start gap-2 text-[10px] bg-white rounded p-1.5 border border-red-100">
                    {d.photo_url && (
                      <img 
                        src={d.photo_url.startsWith('http') ? d.photo_url : `${process.env.REACT_APP_BACKEND_URL || ''}${d.photo_url}`} 
                        alt="" 
                        className="w-10 h-10 rounded object-cover flex-shrink-0 cursor-pointer border-2 border-red-300 hover:border-red-500 transition-all active:scale-95"
                        onClick={(e) => { 
                          e.stopPropagation()
                          const fullUrl = d.photo_url.startsWith('http') ? d.photo_url : `${process.env.REACT_APP_BACKEND_URL || ''}${d.photo_url}`
                          setShowDamagePhoto(fullUrl)
                        }}
                      />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1 flex-wrap">
                        <span className={`px-1 py-0.5 rounded text-[9px] ${
                          d.stage === 'pre_issue' ? 'bg-blue-100 text-blue-700' : 
                          d.stage === 'return' ? 'bg-orange-100 text-orange-700' : 'bg-slate-100 text-slate-600'
                        }`}>
                          {d.stage_label || d.stage}
                        </span>
                        {d.order_number && <span className="text-slate-400">#{d.order_number}</span>}
                        {(d.qty || 1) > 1 && <span className="font-bold text-slate-700">{d.qty} шт</span>}
                        {d.fee > 0 && <span className="text-red-600 font-medium">₴{d.fee}</span>}
                      </div>
                      <div className="text-slate-700 truncate">
                        {d.damage_type || d.type}
                        {(d.qty || 1) > 1 && d.fee > 0 && (
                          <span className="text-slate-400 font-normal ml-1">
                            ({d.qty} × ₴{Math.round(d.fee / d.qty)})
                          </span>
                        )}
                      </div>
                      {d.note && <div className="text-slate-500 truncate">{d.note}</div>}
                      <div className="text-slate-400">{d.created_at}</div>
                    </div>
                  </div>
                ))}
              </div>
              {item.damage_history.length > 5 && (
                <div className="text-center text-[10px] text-red-600 mt-1">
                  + ще {item.damage_history.length - 5} записів
                </div>
              )}
            </div>
          )}
          
          {/* Availability row */}
          <div className="flex items-center gap-1 text-[10px] flex-wrap">
            <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
              Наявн: <b>{item.available || 0}</b>
            </span>
            <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
              Рез: <b>{item.reserved || 0}</b>
            </span>
            <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
              Оренда: <b>{item.in_rent || 0}</b>
            </span>
            <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
              Рест: <b>{item.in_restore || 0}</b>
            </span>
          </div>
          
          {/* Packaging button */}
          <button
            onClick={() => setShowPackaging(true)}
            className="w-full flex items-center justify-between px-2 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-xs"
          >
            <span className="text-slate-600">
              <Package className="w-3.5 h-3.5 inline mr-1" />
              Пакування
            </span>
            <span className="text-slate-800 font-medium">
              {packagingSummary.length > 0 ? packagingSummary.join(', ') : 'Не обрано'}
            </span>
          </button>
          
          {/* Damage button */}
          {onOpenDamage && !readOnly && (
            <button 
              onClick={() => onOpenDamage(item.id)} 
              className="w-full py-1.5 rounded-lg bg-amber-100 text-amber-700 text-xs font-medium flex items-center justify-center gap-1"
            >
              <AlertTriangle className="w-3.5 h-3.5" />
              Зафіксувати пошкодження
            </button>
          )}
        </div>
      )}
      
      {/* Photo Modal */}
      {showPhoto && photoUrl && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
          onClick={() => setShowPhoto(false)}
        >
          <div className="relative max-w-full max-h-full animate-scale-in">
            <img 
              src={photoUrl} 
              alt={item.name}
              className="max-w-full max-h-[80vh] object-contain rounded-lg shadow-2xl"
            />
            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-4 rounded-b-lg">
              <div className="text-white font-medium">{item.name}</div>
              <div className="text-white/70 text-sm">{item.sku}</div>
            </div>
            <button 
              className="absolute top-2 right-2 w-8 h-8 rounded-full bg-black/50 text-white flex items-center justify-center"
              onClick={() => setShowPhoto(false)}
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}
      
      {/* Item Menu Bottom Sheet */}
      {showMenu && (
        <div className="fixed inset-0 z-50" onClick={() => setShowMenu(false)}>
          <div className="absolute inset-0 bg-black/30" />
          <div 
            className="absolute bottom-0 left-0 right-0 bg-white rounded-t-2xl shadow-xl animate-slide-up safe-area-bottom"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex justify-center pt-3 pb-2">
              <div className="w-10 h-1 bg-slate-300 rounded-full" />
            </div>
            <div className="px-4 pb-2 border-b border-slate-100">
              <div className="font-semibold text-slate-800 truncate">{item.name}</div>
              <div className="text-xs text-slate-500">{item.sku}</div>
            </div>
            <div className="p-2">
              {onOpenDamage && !readOnly && (
                <button
                  onClick={() => { setShowMenu(false); onOpenDamage(item.id) }}
                  className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-amber-600 hover:bg-amber-50"
                >
                  <AlertTriangle className="w-5 h-5" />
                  Зафіксувати пошкодження
                </button>
              )}
              {onRemoveItem && !readOnly && (
                <button
                  onClick={() => {
                    setShowMenu(false)
                    if (window.confirm(`Видалити "${item.name}"?`)) {
                      onRemoveItem(item.id, item.name)
                    }
                  }}
                  className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-rose-600 hover:bg-rose-50"
                >
                  <Trash2 className="w-5 h-5" />
                  Видалити з замовлення
                </button>
              )}
            </div>
          </div>
        </div>
      )}
      
      {/* Packaging Bottom Sheet */}
      {showPackaging && (
        <div className="fixed inset-0 z-50" onClick={() => setShowPackaging(false)}>
          <div className="absolute inset-0 bg-black/30" />
          <div 
            className="absolute bottom-0 left-0 right-0 bg-white rounded-t-2xl shadow-xl animate-slide-up safe-area-bottom"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex justify-center pt-3 pb-2">
              <div className="w-10 h-1 bg-slate-300 rounded-full" />
            </div>
            <div className="flex items-center justify-between px-4 pb-3 border-b border-slate-100">
              <span className="font-semibold text-slate-800">Пакування</span>
              <button onClick={() => setShowPackaging(false)} className="p-1 rounded-full hover:bg-slate-100">
                <X className="w-5 h-5 text-slate-500" />
              </button>
            </div>
            <div className="p-3 space-y-2">
              {packagingOptions.map(opt => {
                const qty = parseInt(item.packaging?.[opt.key]) || 0
                return (
                  <div 
                    key={opt.key}
                    className={`
                      flex items-center gap-3 p-3 rounded-xl border transition-colors
                      ${qty > 0 ? 'bg-emerald-50 border-emerald-300' : 'bg-white border-slate-200'}
                    `}
                  >
                    <span className="flex-1 text-sm font-medium text-slate-800">{opt.label}</span>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => !readOnly && onPackagingChange?.(item.id, opt.key, Math.max(0, qty - 1))}
                        disabled={readOnly || qty <= 0}
                        className="w-8 h-8 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 font-bold text-sm flex items-center justify-center disabled:opacity-30"
                      >-</button>
                      <input
                        type="number"
                        value={qty}
                        onChange={(e) => !readOnly && onPackagingChange?.(item.id, opt.key, Math.max(0, parseInt(e.target.value) || 0))}
                        disabled={readOnly}
                        className="w-12 h-8 text-center text-sm font-bold border border-slate-200 rounded-lg"
                        min="0"
                      />
                      <button
                        onClick={() => !readOnly && onPackagingChange?.(item.id, opt.key, qty + 1)}
                        disabled={readOnly}
                        className="w-8 h-8 rounded-lg bg-emerald-100 hover:bg-emerald-200 text-emerald-700 font-bold text-sm flex items-center justify-center disabled:opacity-30"
                      >+</button>
                    </div>
                  </div>
                )
              })}
              {item.packaging?.other > 0 && (
                <input
                  type="text"
                  value={item.packaging?.other_text || ''}
                  onChange={(e) => !readOnly && onPackagingChange?.(item.id, 'other_text', e.target.value)}
                  placeholder="Опишіть пакування..."
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl focus:ring-1 focus:ring-emerald-400"
                />
              )}
            </div>
          </div>
        </div>
      )}
      
      {/* Damage Photo Modal */}
      {showDamagePhoto && (
        <div 
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/90 p-4"
          onClick={() => setShowDamagePhoto(null)}
        >
          <div className="relative max-w-full max-h-full animate-scale-in">
            <img 
              src={showDamagePhoto} 
              alt="Фото пошкодження"
              className="max-w-full max-h-[85vh] object-contain rounded-lg shadow-2xl"
              onError={(e) => { e.target.style.display = 'none' }}
            />
            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-4 rounded-b-lg">
              <div className="text-white font-medium text-center">📷 Фото пошкодження</div>
              <div className="text-white/70 text-sm text-center">{item.name} ({item.sku})</div>
            </div>
            <button 
              className="absolute top-3 right-3 w-10 h-10 rounded-full bg-white/20 backdrop-blur text-white flex items-center justify-center hover:bg-white/30 transition-colors"
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
