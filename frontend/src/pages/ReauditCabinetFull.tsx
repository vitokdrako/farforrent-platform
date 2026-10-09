/* eslint-disable */
/**
 * ReauditCabinetFull - Кабінет переобліку (паттерн CatalogBoard)
 * Картки товарів → клік → модалка з вкладками (Інфо / Редагування / Шкода / Історія)
 */
import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { getImageUrl, handleImageError, FALLBACK_IMAGE } from '../utils/imageHelper'
import CorporateHeader from '../components/CorporateHeader'
import ProductConditionPanel from '../components/ProductConditionPanel'
import ProductImageGallery from '../components/ProductImageGallery'
import { Filter, X, ChevronDown, Search, Check, AlertTriangle, Clock, Package, Edit3, History, Shield, Upload, Download, Plus, Camera, Trash2, Power, PowerOff, Eye, EyeOff, Image as ImageIcon } from 'lucide-react'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''
const cls = (...a: (string | false | null | undefined)[]) => a.filter(Boolean).join(' ')
const fmtUA = (n: number) => (Number(n) || 0).toLocaleString('uk-UA', { maximumFractionDigits: 0 })

/* ─────────── tiny UI atoms ─────────── */
function Badge({ children, tone = 'slate' }: { children: React.ReactNode; tone?: string }) {
  const t: Record<string, string> = {
    slate: 'bg-slate-100 text-slate-700 border-slate-200',
    green: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
    red: 'bg-rose-50 text-rose-700 border-rose-200',
    blue: 'bg-sky-50 text-sky-700 border-sky-200',
  }
  return <span className={cls('inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium', t[tone] || t.slate)}>{children}</span>
}

function PillButton({ children, onClick, tone = 'slate', disabled = false, className = '', ...rest }: any) {
  const t: Record<string, string> = {
    slate: 'bg-slate-900 text-white hover:bg-slate-800',
    green: 'bg-emerald-600 text-white hover:bg-emerald-700',
    amber: 'bg-amber-500 text-white hover:bg-amber-600',
    red: 'bg-rose-600 text-white hover:bg-rose-700',
    ghost: 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-50',
  }
  return (
    <button type="button" onClick={onClick} disabled={disabled} {...rest}
      className={cls('rounded-full px-3 py-1.5 text-xs font-medium transition disabled:opacity-40', t[tone], className)}>
      {children}
    </button>
  )
}

/* ─────────── KPI strip ─────────── */
function KpiStrip({ stats }: { stats: any }) {
  const items = [
    { label: 'Всього', value: stats.total, color: 'text-slate-800' },
    { label: 'Переоблік.', value: stats.ok, color: 'text-emerald-600' },
    { label: 'Потребують', value: stats.minor, color: 'text-amber-600' },
    { label: 'Критичні', value: stats.crit, color: 'text-rose-600' },
  ]
  return (
    <div className="flex gap-4 overflow-x-auto pb-1 scrollbar-none" data-testid="kpi-strip">
      {items.map(i => (
        <div key={i.label} className="flex-shrink-0 text-center min-w-[60px]">
          <div className={cls('text-lg lg:text-xl font-bold', i.color)}>{fmtUA(i.value)}</div>
          <div className="text-[10px] lg:text-xs text-corp-text-muted">{i.label}</div>
        </div>
      ))}
    </div>
  )
}

/* ─────────── Sidebar filters ─────────── */
function Sidebar({ categories, subcategoriesMap, filters, setFilters, onReset, isMobileOpen, onMobileClose }: any) {
  const [expanded, setExpanded] = useState({ category: true, status: true, search: true })
  const toggle = (k: string) => setExpanded((p: any) => ({ ...p, [k]: !p[k] }))

  return (
    <>
      {isMobileOpen && <div className="lg:hidden fixed inset-0 bg-black/50 z-40" onClick={onMobileClose} />}
      <aside className={cls(
        'flex-shrink-0 space-y-3 transition-all duration-300 z-50',
        'lg:w-64 lg:relative lg:translate-x-0',
        'fixed inset-y-0 left-0 w-[85%] max-w-[300px] bg-slate-50 lg:bg-transparent overflow-y-auto p-4 lg:p-0',
        isMobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
      )}>
        <div className="lg:hidden flex items-center justify-between mb-3 pb-2 border-b border-slate-200">
          <h2 className="font-semibold text-slate-800">Фільтри</h2>
          <button onClick={onMobileClose} className="p-2 hover:bg-slate-200 rounded-lg"><X className="w-5 h-5" /></button>
        </div>
        {/* Search */}
        <div className="bg-white rounded-xl border border-corp-border overflow-hidden">
          <button onClick={() => toggle('search')} className="w-full flex items-center justify-between p-3">
            <div className="flex items-center gap-2"><Search className="w-4 h-4" /><span className="font-semibold text-sm text-corp-text-dark">Пошук</span></div>
            <ChevronDown className={cls('w-4 h-4 text-slate-500 transition-transform lg:hidden', expanded.search && 'rotate-180')} />
          </button>
          <div className={cls('px-3 pb-3', !expanded.search && 'hidden lg:block')}>
            <input type="text" value={filters.q} onChange={e => setFilters({ ...filters, q: e.target.value })}
              placeholder="SKU, назва, категорія..."
              className="w-full rounded-lg border border-corp-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-corp-primary/30"
              data-testid="reaudit-search" />
          </div>
        </div>
        {/* Category */}
        <div className="bg-white rounded-xl border border-corp-border overflow-hidden">
          <button onClick={() => toggle('category')} className="w-full flex items-center justify-between p-3">
            <span className="font-semibold text-sm text-corp-text-dark">Категорія</span>
            <ChevronDown className={cls('w-4 h-4 text-slate-500 transition-transform lg:hidden', expanded.category && 'rotate-180')} />
          </button>
          <div className={cls('px-3 pb-3 space-y-2', !expanded.category && 'hidden lg:block')}>
            <select value={filters.category} onChange={e => setFilters({ ...filters, category: e.target.value, subcategory: '' })}
              className="w-full rounded-lg border border-corp-border px-3 py-2 text-sm" data-testid="reaudit-category-filter">
              <option value="">Всі категорії</option>
              {categories.map((c: string) => <option key={c} value={c}>{c}</option>)}
            </select>
            <select value={filters.subcategory} onChange={e => setFilters({ ...filters, subcategory: e.target.value })}
              disabled={!filters.category} data-testid="reaudit-subcategory-filter"
              className="w-full rounded-lg border border-corp-border px-3 py-2 text-sm disabled:opacity-50">
              <option value="">{filters.category ? 'Всі підкатегорії' : 'Оберіть категорію'}</option>
              {(subcategoriesMap[filters.category] || []).map((s: string) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>
        {/* Status */}
        <div className="bg-white rounded-xl border border-corp-border overflow-hidden">
          <button onClick={() => toggle('status')} className="w-full flex items-center justify-between p-3">
            <span className="font-semibold text-sm text-corp-text-dark">Статус</span>
            <ChevronDown className={cls('w-4 h-4 text-slate-500 transition-transform lg:hidden', expanded.status && 'rotate-180')} />
          </button>
          <div className={cls('px-3 pb-3 space-y-1', !expanded.status && 'hidden lg:block')}>
            {[
              { val: '', label: 'Усі активні', icon: Package },
              { val: 'ok', label: 'Переоблікавані', icon: Check },
              { val: 'needs_recount', label: 'Потребують', icon: Clock },
              { val: 'critical', label: 'Критичні', icon: AlertTriangle },
              { val: 'disabled', label: 'Відключені', icon: EyeOff },
            ].map(s => (
              <button key={s.val} onClick={() => setFilters({ ...filters, statusFilter: s.val })}
                className={cls('w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition',
                  filters.statusFilter === s.val ? 'bg-corp-primary/10 text-corp-primary font-medium' : 'text-corp-text-main hover:bg-slate-50'
                )} data-testid={`reaudit-status-${s.val || 'all'}`}>
                <s.icon className="w-4 h-4" />{s.label}
              </button>
            ))}
          </div>
        </div>
        <button onClick={() => { onReset(); onMobileClose?.() }}
          className="w-full py-2 text-sm text-corp-text-muted hover:text-rose-600 hover:bg-rose-50 rounded-lg border border-corp-border transition"
          data-testid="reaudit-reset-filters">
          Скинути фільтри
        </button>
        <button onClick={onMobileClose}
          className="lg:hidden w-full py-3 bg-corp-primary text-white font-medium rounded-lg hover:bg-corp-primary/90">
          Застосувати
        </button>
      </aside>
    </>
  )
}

/* ─────────── Product card ─────────── */
function AuditCard({ item, onClick }: { item: any; onClick: () => void }) {
  const days = item.daysFromLastAudit
  const isOverdue = days > 180
  const isCritical = item.status === 'critical'
  const isDisabled = item.isDisabled
  const auditLabel = days < 999 ? `${days}д` : 'Ніколи'

  return (
    <div onClick={onClick} data-testid={`audit-card-${item.product_id}`}
      className={cls(
        'bg-white rounded-xl border p-2 lg:p-3 hover:shadow-md transition-all cursor-pointer group relative',
        isDisabled ? 'border-slate-300 opacity-60' :
        isCritical ? 'border-rose-300 bg-rose-50/30' :
        isOverdue ? 'border-amber-300 bg-amber-50/20' : 'border-corp-border'
      )}>
      <div className="relative mb-2">
        <img src={getImageUrl(item.imageUrl, 'thumb') || FALLBACK_IMAGE} alt={item.name} loading="lazy"
          className="w-full h-20 lg:h-24 object-contain rounded-lg bg-white" onError={handleImageError} />
        <div className="absolute top-1.5 right-1.5 flex flex-col gap-1">
          {isDisabled && <Badge tone="slate">Вимкнено</Badge>}
          {isCritical && !isDisabled && <Badge tone="red">Критичний</Badge>}
          {isOverdue && !isCritical && !isDisabled && <Badge tone="amber">{auditLabel}</Badge>}
          {!isOverdue && !isCritical && !isDisabled && <Badge tone="green">{auditLabel}</Badge>}
        </div>
      </div>
      <div className="space-y-0.5">
        <div className="text-[10px] lg:text-xs text-corp-text-muted">{item.code}</div>
        <div className="font-medium text-corp-text-dark text-xs lg:text-sm line-clamp-2 group-hover:text-corp-primary transition-colors min-h-[32px] lg:min-h-[40px]">
          {item.name}
        </div>
        {(item.color || item.material) && (
          <div className="flex flex-wrap gap-1">
            {item.color && <span className="text-[10px] bg-corp-bg-light px-1.5 py-0.5 rounded text-corp-text-muted">{item.color}</span>}
            {item.material && <span className="text-[10px] bg-corp-bg-light px-1.5 py-0.5 rounded text-corp-text-muted">{item.material}</span>}
          </div>
        )}
        <div className="flex items-center justify-between pt-1.5 border-t border-corp-border">
          <span className={cls('text-sm font-semibold', (item.qty || 0) > 0 ? 'text-emerald-600' : 'text-rose-600')}>
            {item.qty || 0} шт
          </span>
          {item.rentalPrice > 0 && <span className="text-xs font-medium text-corp-primary">{fmtUA(item.rentalPrice)} &#8372;</span>}
        </div>
      </div>
    </div>
  )
}

/* ─────────── Photo upload ─────────── */
function PhotoUploader({ item, onUploaded }: { item: any; onUploaded: () => void }) {
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const uploadRes = await fetch(`${BACKEND_URL}/api/products/upload-image`, { method: 'POST', body: formData })
      const uploadData = await uploadRes.json()
      if (!uploadRes.ok || !uploadData.success) { alert('Помилка завантаження: ' + (uploadData.detail || '')); return }

      const token = localStorage.getItem('token')
      const headers: any = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`
      const updateRes = await fetch(`${BACKEND_URL}/api/audit/items/${item.id}/edit-full`, {
        method: 'PUT', headers,
        body: JSON.stringify({ imageUrl: uploadData.path })
      })
      if (updateRes.ok) onUploaded()
      else alert('Фото завантажено, але не збережено в БД')
    } catch (err) { alert('Помилка: ' + String(err)) }
    finally { setUploading(false); if (fileRef.current) fileRef.current.value = '' }
  }

  return (
    <div className="relative">
      <img src={getImageUrl(item.imageUrl) || FALLBACK_IMAGE} alt={item.name}
        className="w-full h-48 md:h-64 object-contain rounded-xl bg-white border border-corp-border" onError={handleImageError} />
      <button onClick={() => fileRef.current?.click()} disabled={uploading}
        className="absolute bottom-2 right-2 flex items-center gap-1.5 rounded-full px-3 py-2 text-xs font-medium bg-white/95 text-slate-700 shadow-md border border-corp-border hover:bg-slate-50 transition active:scale-95"
        data-testid="photo-upload-btn">
        <Camera className="w-4 h-4" />{uploading ? 'Завантаження...' : 'Змінити фото'}
      </button>
      <input ref={fileRef} type="file" accept="image/*" onChange={handleUpload} className="hidden" />
    </div>
  )
}

/* ─────────── Modal: Tab - Info ─────────── */
function TabInfo({ item, onMarkAudited, onToggle, onDelete, onShowCondition, onDuplicate }: any) {
  const [marking, setMarking] = useState(false)

  const handleMark = async () => {
    setMarking(true)
    try { await onMarkAudited(item) } finally { setMarking(false) }
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <PhotoUploader item={item} onUploaded={() => onMarkAudited(item, true)} />
        <div className="space-y-3">
          <div>
            <div className="text-xs text-corp-text-muted">{item.code}</div>
            <h3 className="text-lg font-bold text-corp-text-dark">{item.name}</h3>
            <div className="text-sm text-corp-text-muted">{item.category}</div>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="bg-corp-bg-light rounded-lg p-2"><span className="text-corp-text-muted">Кількість</span><div className="font-bold text-corp-text-dark">{item.qty}</div></div>
            <div className="bg-corp-bg-light rounded-lg p-2"><span className="text-corp-text-muted">Оренди</span><div className="font-bold text-corp-text-dark">{item.rentalsCount}</div></div>
            <div className="bg-corp-bg-light rounded-lg p-2"><span className="text-corp-text-muted">Дохід</span><div className="font-bold text-emerald-600">{fmtUA(item.totalProfit)} &#8372;</div></div>
            <div className="bg-corp-bg-light rounded-lg p-2"><span className="text-corp-text-muted">Шкоди</span><div className="font-bold text-corp-text-dark">{item.damagesCount}</div></div>
          </div>
          <div className="text-xs text-corp-text-muted">
            Останній переоблік: <strong>{item.daysFromLastAudit < 999 ? `${item.daysFromLastAudit} днів тому` : 'Ніколи'}</strong>
          </div>
          {/* Action buttons */}
          <div className="flex flex-wrap gap-2">
            <PillButton tone="green" onClick={handleMark} disabled={marking} data-testid="mark-audited-btn">
              <span className="flex items-center gap-1"><Check className="w-3.5 h-3.5" />{marking ? '...' : 'Переоблік'}</span>
            </PillButton>
            <PillButton tone="ghost" onClick={onShowCondition} data-testid="condition-log-btn">
              <span className="flex items-center gap-1"><History className="w-3.5 h-3.5" />Журнал стану</span>
            </PillButton>
            <PillButton tone="ghost" onClick={() => onDuplicate(item)} data-testid="duplicate-product-btn">
              <span className="flex items-center gap-1"><Plus className="w-3.5 h-3.5" />Дублювати</span>
            </PillButton>
          </div>
          {/* Toggle / Delete */}
          <div className="flex gap-2 pt-2 border-t border-corp-border">
            <button onClick={() => onToggle(item)} data-testid="toggle-product-btn"
              className={cls('flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] font-medium border transition',
                item.isDisabled ? 'border-emerald-200 text-emerald-700 hover:bg-emerald-50' : 'border-amber-200 text-amber-700 hover:bg-amber-50')}>
              {item.isDisabled ? <><Eye className="w-3.5 h-3.5" />Увімкнути</> : <><EyeOff className="w-3.5 h-3.5" />Вимкнути</>}
            </button>
            <button onClick={() => onDelete(item)} data-testid="delete-product-btn"
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] font-medium border border-rose-200 text-rose-600 hover:bg-rose-50 transition">
              <Trash2 className="w-3.5 h-3.5" />Видалити
            </button>
          </div>
        </div>
      </div>
      {item.description && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <div className="text-xs font-semibold text-corp-text-dark mb-1">Опис</div>
          <div className="text-xs text-corp-text-main whitespace-pre-wrap">{item.description}</div>
        </div>
      )}
      {item.careInstructions && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <div className="text-xs font-semibold text-corp-text-dark mb-1">Догляд</div>
          <div className="text-xs text-corp-text-main whitespace-pre-wrap">{item.careInstructions}</div>
        </div>
      )}
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-corp-text-main">
        <div className="font-semibold text-corp-text-dark mb-1">Життєвий цикл</div>
        <p>Предмет був в оренді <strong>{item.rentalsCount}</strong> разів та приніс <strong>{fmtUA(item.totalProfit)} &#8372;</strong> доходу. Кейсів шкоди: <strong>{item.damagesCount}</strong>.</p>
      </div>
    </div>
  )
}

/* ─────────── Multi-select pill selector ─────────── */
function PillMultiSelect({ label, selected, options, onChange, datalistId }: {
  label: string; selected: string[]; options: { name: string; count: number }[];
  onChange: (v: string[]) => void; datalistId: string;
}) {
  const [input, setInput] = useState('')
  const add = (v: string) => { const t = v.trim(); if (t && !selected.includes(t)) onChange([...selected, t]) }
  const remove = (v: string) => onChange(selected.filter(s => s !== v))
  const filtered = options.filter(o => o.name.toLowerCase().includes(input.toLowerCase()) && !selected.includes(o.name)).slice(0, 12)

  return (
    <div>
      <label className="block text-corp-text-muted mb-1 text-xs">{label}</label>
      <div className="flex flex-wrap gap-1 mb-1.5">
        {selected.map(s => (
          <span key={s} className="flex items-center gap-1 bg-corp-primary/10 text-corp-primary rounded-full px-2 py-0.5 text-[10px] font-medium">
            {s}<button type="button" onClick={() => remove(s)} className="hover:text-rose-600 ml-0.5">&times;</button>
          </span>
        ))}
      </div>
      <div className="relative">
        <input value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); add(input); setInput('') } }}
          placeholder={`Додати ${label.toLowerCase()}...`}
          className="w-full rounded-lg border border-corp-border px-3 py-1.5 text-sm" />
        {input.length > 0 && filtered.length > 0 && (
          <div className="absolute z-10 top-full left-0 right-0 mt-1 bg-white rounded-lg border border-corp-border shadow-lg max-h-40 overflow-y-auto">
            {filtered.map(o => (
              <button key={o.name} type="button" onClick={() => { add(o.name); setInput('') }}
                className="w-full text-left px-3 py-1.5 text-sm hover:bg-corp-bg-light flex justify-between items-center">
                <span>{o.name}</span><span className="text-[10px] text-corp-text-muted">{o.count}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

/* ─────────── Modal: Tab - Edit ─────────── */
function TabEdit({ item, categories, subcategoriesMap, hashtags: hashtagDict, shapes: shapeDict, colorDict, materialDict, onSave }: any) {
  const parseList = (v: string) => v ? v.split(',').map((s: string) => s.trim()).filter(Boolean) : []
  const [form, setForm] = useState({
    name: item.name || '', code: item.code || '',
    price: item.price || 0, rentalPrice: item.rentalPrice || 0,
    colors: parseList(item.color || ''), materials: parseList(item.material || ''),
    category: item.categoryName || '', subcategory: item.subcategoryName || '',
    height: item.heightCm || '', width: item.widthCm || '', depth: item.depthCm || '', diameter: item.diameterCm || '',
    shape: item.shape || '', components: item.components || '', hashtags: item.hashtags || [],
    qty: item.qty || 0, zone: item.zone || '',
    description: item.description || '', careInstructions: item.careInstructions || '',
  })
  const [saving, setSaving] = useState(false)
  const [tagInput, setTagInput] = useState('')

  const f = (k: string, v: any) => setForm(p => ({ ...p, [k]: v }))
  const addTag = (t: string) => { if (t && !form.hashtags.includes(t)) f('hashtags', [...form.hashtags, t]) }
  const removeTag = (t: string) => f('hashtags', form.hashtags.filter((h: string) => h !== t))

  const handleSave = async () => {
    setSaving(true)
    try {
      const token = localStorage.getItem('token')
      const headers: any = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`
      const isNew = !item.id
      const payload = {
        ...form,
        color: form.colors.join(', '),
        material: form.materials.join(', '),
      }
      if (isNew) {
        if (!form.name?.trim()) { alert('Введіть назву товару'); return }
        // SKU is optional — backend auto-generates RH-{id} if empty
        const res = await fetch(`${BACKEND_URL}/api/audit/items`, {
          method: 'POST', headers, body: JSON.stringify(payload)
        })
        if (!res.ok) { const r = await res.json(); alert('Помилка: ' + (r.detail || '')); return }
        const created = await res.json()
        onSave(created?.product_id || created?.id || null)
        return
      }
      const editRes = await fetch(`${BACKEND_URL}/api/audit/items/${item.id}/edit-full`, {
        method: 'PUT', headers, body: JSON.stringify(payload)
      })
      if (!editRes.ok) { const r = await editRes.json(); alert('Помилка: ' + (r.detail || '')); return }
      await fetch(`${BACKEND_URL}/api/audit/items/${item.id}/update-info`, {
        method: 'PUT', headers,
        body: JSON.stringify({ description: form.description, care_instructions: form.careInstructions })
      })
      onSave(item.id)
    } catch (e) { alert('Помилка: ' + String(e)) }
    finally { setSaving(false) }
  }

  return (
    <div className="space-y-4 text-xs">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div><label className="block text-corp-text-muted mb-1">Назва</label>
          <input value={form.name} onChange={e => f('name', e.target.value)} className="w-full rounded-lg border border-corp-border px-3 py-2 text-sm" data-testid="edit-name" /></div>
        <div><label className="block text-corp-text-muted mb-1">SKU{!item.id && <span className="text-corp-text-muted/70 ml-1">(авто, якщо порожньо)</span>}</label>
          <input value={form.code} onChange={e => f('code', e.target.value)} className="w-full rounded-lg border border-corp-border px-3 py-2 text-sm" placeholder={!item.id ? `RH-${'{auto}'}` : ''} /></div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div><label className="block text-corp-text-muted mb-1">Ціна купівлі</label>
          <input type="number" value={form.price} onChange={e => f('price', Number(e.target.value))} className="w-full rounded-lg border border-corp-border px-3 py-2 text-sm" /></div>
        <div><label className="block text-corp-text-muted mb-1">Ціна оренди</label>
          <input type="number" value={form.rentalPrice} onChange={e => f('rentalPrice', Number(e.target.value))} className="w-full rounded-lg border border-corp-border px-3 py-2 text-sm" /></div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div><label className="block text-corp-text-muted mb-1">Категорія</label>
          <select value={form.category} onChange={e => { f('category', e.target.value); f('subcategory', '') }}
            className="w-full rounded-lg border border-corp-border px-3 py-2 text-sm" data-testid="edit-category">
            <option value="">—</option>
            {categories.map((c: string) => <option key={c} value={c}>{c}</option>)}
          </select></div>
        <div><label className="block text-corp-text-muted mb-1">Підкатегорія</label>
          <select value={form.subcategory} onChange={e => f('subcategory', e.target.value)} disabled={!form.category}
            className="w-full rounded-lg border border-corp-border px-3 py-2 text-sm disabled:opacity-50">
            <option value="">—</option>
            {(subcategoriesMap[form.category] || []).map((s: string) => <option key={s} value={s}>{s}</option>)}
          </select></div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <PillMultiSelect label="Колір" selected={form.colors} options={colorDict}
          onChange={v => f('colors', v)} datalistId="colors-list" />
        <PillMultiSelect label="Матеріал" selected={form.materials} options={materialDict}
          onChange={v => f('materials', v)} datalistId="materials-list" />
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <div><label className="block text-corp-text-muted mb-1">Форма</label>
          <input value={form.shape} onChange={e => f('shape', e.target.value)} list="shapes-list"
            className="w-full rounded-lg border border-corp-border px-3 py-2 text-sm" />
          <datalist id="shapes-list">{(shapeDict || []).map((s: any) => <option key={s.shape || s} value={s.shape || s} />)}</datalist></div>
        <div><label className="block text-corp-text-muted mb-1">Кількість</label>
          <input type="number" value={form.qty} onChange={e => f('qty', Number(e.target.value))} min={0}
            className="w-full rounded-lg border border-corp-border px-3 py-2 text-sm" data-testid="edit-qty" /></div>
      </div>
      <div>
        <label className="block text-corp-text-muted mb-1">
          Комплектація <span className="text-corp-text-muted/70">(що ще йде з товаром, через кому або з нового рядка)</span>
        </label>
        <textarea
          value={form.components}
          onChange={e => f('components', e.target.value)}
          rows={2}
          placeholder="напр.: підставка, 2 свічки, дзеркальна тарілка"
          className="w-full rounded-lg border border-corp-border px-3 py-2 text-sm"
          data-testid="edit-components"
        />
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div><label className="block text-corp-text-muted mb-1">Висота (см)</label>
          <input type="number" value={form.height} onChange={e => f('height', e.target.value)} className="w-full rounded-lg border border-corp-border px-3 py-2 text-sm" /></div>
        <div><label className="block text-corp-text-muted mb-1">Ширина (см)</label>
          <input type="number" value={form.width} onChange={e => f('width', e.target.value)} className="w-full rounded-lg border border-corp-border px-3 py-2 text-sm" /></div>
        <div><label className="block text-corp-text-muted mb-1">Глибина (см)</label>
          <input type="number" value={form.depth} onChange={e => f('depth', e.target.value)} className="w-full rounded-lg border border-corp-border px-3 py-2 text-sm" /></div>
        <div><label className="block text-corp-text-muted mb-1">Діаметр (см)</label>
          <input type="number" value={form.diameter} onChange={e => f('diameter', e.target.value)} className="w-full rounded-lg border border-corp-border px-3 py-2 text-sm" /></div>
      </div>
      <div><label className="block text-corp-text-muted mb-1">Зона / Стелаж</label>
        <input value={form.zone} onChange={e => f('zone', e.target.value)} className="w-full rounded-lg border border-corp-border px-3 py-2 text-sm" placeholder="A1-10" /></div>
      {/* Hashtags */}
      <div>
        <label className="block text-corp-text-muted mb-1">Хештеги</label>
        <div className="flex flex-wrap gap-1 mb-2">
          {form.hashtags.map((t: string) => (
            <span key={t} className="flex items-center gap-1 bg-corp-primary/10 text-corp-primary rounded-full px-2 py-0.5 text-[10px]">
              #{t}<button type="button" onClick={() => removeTag(t)} className="hover:text-rose-600">&times;</button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <input value={tagInput} onChange={e => setTagInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addTag(tagInput.trim()); setTagInput('') } }}
            list="hashtags-list" placeholder="Додати тег..."
            className="flex-1 rounded-lg border border-corp-border px-3 py-1.5 text-sm" />
          <datalist id="hashtags-list">{(hashtagDict || []).map((h: any) => <option key={h.tag || h} value={h.tag || h} />)}</datalist>
          <PillButton tone="ghost" onClick={() => { addTag(tagInput.trim()); setTagInput('') }}>+</PillButton>
        </div>
      </div>
      <div><label className="block text-corp-text-muted mb-1">Опис</label>
        <textarea rows={3} value={form.description} onChange={e => f('description', e.target.value)} className="w-full rounded-lg border border-corp-border px-3 py-2 text-sm resize-none" /></div>
      <div><label className="block text-corp-text-muted mb-1">Інструкція по догляду</label>
        <textarea rows={2} value={form.careInstructions} onChange={e => f('careInstructions', e.target.value)} className="w-full rounded-lg border border-corp-border px-3 py-2 text-sm resize-none" /></div>
      <div className="flex justify-end">
        <PillButton tone="green" onClick={handleSave} disabled={saving} data-testid="save-edit-btn">
          {saving ? 'Зберігаю...' : (item.id ? 'Зберегти зміни' : 'Створити товар')}
        </PillButton>
      </div>
    </div>
  )
}

/* ─────────── Modal: Tab - Damage ─────────── */
function TabDamage({ item, onDone }: any) {
  const [actionType, setActionType] = useState('')
  const [qty, setQty] = useState(1)
  const [description, setDescription] = useState('')
  const [severity, setSeverity] = useState('minor')
  const [submitting, setSubmitting] = useState(false)
  const [damages, setDamages] = useState<any[]>([])
  const [loadingDmg, setLoadingDmg] = useState(false)

  useEffect(() => { loadDamages() }, [item.id])

  const loadDamages = async () => {
    setLoadingDmg(true)
    try {
      const res = await fetch(`${BACKEND_URL}/api/audit/items/${item.id}/damages`)
      if (res.ok) { const d = await res.json(); setDamages(d.damages || d || []) }
    } catch {} finally { setLoadingDmg(false) }
  }

  const actions = [
    { key: 'washing', label: 'Мийка', tone: 'bg-sky-50 border-sky-200 text-sky-700' },
    { key: 'restoration', label: 'Реставрація', tone: 'bg-amber-50 border-amber-200 text-amber-700' },
    { key: 'laundry', label: 'Пральня', tone: 'bg-violet-50 border-violet-200 text-violet-700' },
    { key: 'total_loss', label: 'Повна втрата', tone: 'bg-rose-50 border-rose-200 text-rose-700' },
  ]

  const handleSubmit = async () => {
    if (!actionType) return alert('Оберіть дію')
    if (!description.trim()) return alert('Введіть причину')
    if (qty <= 0 || qty > (item.qty || 0)) return alert(`Некоректна кількість. Доступно: ${item.qty}`)
    setSubmitting(true)
    try {
      const token = localStorage.getItem('token')
      const headers: any = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`

      if (actionType === 'total_loss') {
        const addRes = await fetch(`${BACKEND_URL}/api/product-damage-history/quick-add-to-queue`, {
          method: 'POST', headers,
          body: JSON.stringify({ product_id: item.product_id, sku: item.code, product_name: item.name, category: item.categoryName || '', queue_type: 'wash', quantity: qty, notes: description })
        })
        const addResult = await addRes.json()
        if (!addResult.success) { alert('Помилка: ' + (addResult.detail || '')); return }
        const woRes = await fetch(`${BACKEND_URL}/api/product-damage-history/${addResult.damage_id}/write-off`, {
          method: 'POST', headers, body: JSON.stringify({ qty, reason: description })
        })
        if (woRes.ok) alert(`Списано ${qty} од.`)
        else { const r = await woRes.json(); alert('Помилка: ' + (r.detail || '')); return }
      } else {
        const queueMap: any = { washing: 'wash', restoration: 'restoration', laundry: 'laundry' }
        const res = await fetch(`${BACKEND_URL}/api/product-damage-history/quick-add-to-queue`, {
          method: 'POST', headers,
          body: JSON.stringify({ product_id: item.product_id, sku: item.code, product_name: item.name, category: item.categoryName || '', queue_type: queueMap[actionType], quantity: qty, notes: `[${severity}] ${description}` })
        })
        const result = await res.json()
        const labels: any = { washing: 'мийку', restoration: 'реставрацію', laundry: 'пральню' }
        if (result.success) alert(`Відправлено на ${labels[actionType]}`)
        else { alert('Помилка: ' + (result.detail || '')); return }
      }
      setActionType(''); setDescription(''); setQty(1)
      loadDamages(); onDone()
    } catch (e) { alert('Помилка: ' + String(e)) }
    finally { setSubmitting(false) }
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {actions.map(a => (
          <button key={a.key} onClick={() => setActionType(a.key)}
            className={cls('rounded-lg border p-2.5 text-xs font-medium transition text-center',
              actionType === a.key ? a.tone + ' ring-2 ring-offset-1' : 'border-corp-border text-corp-text-main hover:bg-slate-50'
            )} data-testid={`damage-action-${a.key}`}>
            {a.label}
          </button>
        ))}
      </div>
      {actionType && (
        <div className="space-y-3 rounded-xl border border-corp-border p-3 bg-corp-bg-light">
          <div className="grid grid-cols-2 gap-3">
            <div><label className="text-[10px] text-corp-text-muted block mb-1">Кількість</label>
              <input type="number" min={1} max={item.qty || 1} value={qty} onChange={e => setQty(Number(e.target.value))}
                className="w-full rounded-lg border border-corp-border px-3 py-2 text-sm" data-testid="damage-qty" /></div>
            {actionType !== 'total_loss' && (
              <div><label className="text-[10px] text-corp-text-muted block mb-1">Серйозність</label>
                <select value={severity} onChange={e => setSeverity(e.target.value)}
                  className="w-full rounded-lg border border-corp-border px-3 py-2 text-sm">
                  <option value="minor">Незначна</option><option value="moderate">Помірна</option><option value="severe">Серйозна</option>
                </select></div>
            )}
          </div>
          <div><label className="text-[10px] text-corp-text-muted block mb-1">Причина / опис</label>
            <textarea rows={2} value={description} onChange={e => setDescription(e.target.value)}
              className="w-full rounded-lg border border-corp-border px-3 py-2 text-sm resize-none" data-testid="damage-description" /></div>
          <div className="flex gap-2">
            <PillButton tone="amber" onClick={handleSubmit} disabled={submitting} data-testid="damage-submit-btn">
              {submitting ? 'Обробка...' : 'Підтвердити'}
            </PillButton>
            <PillButton tone="ghost" onClick={() => setActionType('')}>Скасувати</PillButton>
          </div>
        </div>
      )}
      <div>
        <div className="text-xs font-semibold text-corp-text-dark mb-2">Історія пошкоджень</div>
        {loadingDmg ? <div className="text-xs text-corp-text-muted">Завантаження...</div> :
          damages.length === 0 ? <div className="text-xs text-corp-text-muted">Пошкоджень не зафіксовано</div> : (
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {damages.map((d: any, i: number) => (
                <div key={d.id || i} className="rounded-lg bg-white border border-slate-100 p-2 text-[11px]">
                  <div className="flex justify-between">
                    <span className="font-medium text-corp-text-dark">{d.date ? new Date(d.date).toLocaleDateString('uk-UA') : (d.created_at ? new Date(d.created_at).toLocaleDateString('uk-UA') : '—')}</span>
                    <Badge tone={d.action_type === 'total_loss' ? 'red' : 'amber'}>{d.action_type || d.processing_type || '—'}</Badge>
                  </div>
                  <div className="text-corp-text-main mt-0.5">{d.notes || d.note || d.comment || '—'}</div>
                </div>
              ))}
            </div>
          )}
      </div>
    </div>
  )
}

/* ─────────── Modal: Tab - History ─────────── */
function TabHistory({ item }: any) {
  const [history, setHistory] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    (async () => {
      setLoading(true)
      try {
        const res = await fetch(`${BACKEND_URL}/api/audit/items/${item.id}/rental-history`)
        if (res.ok) { const d = await res.json(); setHistory(d.history || d || []) }
      } catch {} finally { setLoading(false) }
    })()
  }, [item.id])

  return (
    <div>
      <div className="text-xs font-semibold text-corp-text-dark mb-2">Історія оренд</div>
      {loading ? <div className="text-xs text-corp-text-muted py-4 text-center">Завантаження...</div> :
        history.length === 0 ? <div className="text-xs text-corp-text-muted py-4 text-center">Цей товар ще не здавався в оренду</div> : (
          <div className="space-y-2 max-h-[50vh] overflow-y-auto">
            {history.map((r: any, i: number) => (
              <div key={i} className="rounded-lg border border-slate-100 bg-slate-50 p-2 text-[11px]">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-corp-text-dark">{r.order_number}</span>
                  <Badge tone="green">{fmtUA(r.total_rental)} &#8372;</Badge>
                </div>
                <div className="text-corp-text-main">
                  {r.rent_date && <div>{new Date(r.rent_date).toLocaleDateString('uk-UA')}{r.rent_return_date && ` → ${new Date(r.rent_return_date).toLocaleDateString('uk-UA')}`}</div>}
                  <div>{r.client_name || '—'} {r.client_phone && `· ${r.client_phone}`}</div>
                  <div className="mt-0.5 text-[10px] text-corp-text-muted">{r.rental_days} днів · Кіл-сть: {r.quantity}</div>
                </div>
              </div>
            ))}
          </div>
        )}
    </div>
  )
}

/* ─────────── Product detail modal ─────────── */
function ProductModal({ item, onClose, categories, subcategoriesMap, hashtags, shapes, colorDict, materialDict, onItemUpdated, onToggle, onDelete, onDuplicate }: any) {
  const [tab, setTab] = useState<'info' | 'edit' | 'photos' | 'damage' | 'history'>('info')
  const [showConditionPanel, setShowConditionPanel] = useState(false)

  if (!item) return null

  const tabs = [
    { key: 'info', label: 'Інфо', icon: Package },
    { key: 'edit', label: 'Редагування', icon: Edit3 },
    { key: 'photos', label: 'Фото', icon: ImageIcon },
    { key: 'damage', label: 'Шкода', icon: AlertTriangle },
    { key: 'history', label: 'Історія', icon: History },
  ]

  const handleMarkAudited = async (itm: any, skipAlert?: boolean) => {
    const token = localStorage.getItem('token')
    const headers: any = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`
    const res = await fetch(`${BACKEND_URL}/api/audit/items/${itm.id}/mark-as-audited`, {
      method: 'POST', headers,
      body: JSON.stringify({ quantity_actual: itm.qty, audited_by: 'Реквізитор', next_audit_days: 180 })
    })
    if (res.ok) {
      if (!skipAlert) alert('Переоблік зафіксовано!')
      onItemUpdated()
    } else {
      const r = await res.json()
      alert('Помилка: ' + (r.detail || ''))
    }
  }

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4" data-testid="product-modal">
        <div className="absolute inset-0 bg-black/40" onClick={onClose} />
        <div className="relative bg-white rounded-2xl w-full max-w-3xl max-h-[92vh] overflow-hidden flex flex-col shadow-xl">
          <div className="flex items-center justify-between px-4 py-3 border-b border-corp-border bg-corp-bg-light/50">
            <div className="min-w-0">
              <div className="text-xs text-corp-text-muted">{item.code}</div>
              <h2 className="text-base sm:text-lg font-bold text-corp-text-dark truncate">{item.name}</h2>
            </div>
            <button onClick={onClose} className="p-1.5 hover:bg-slate-200 rounded-lg text-corp-text-muted flex-shrink-0">
              <X className="w-5 h-5" />
            </button>
          </div>
          <div className="flex gap-1 px-4 pt-3 pb-2 border-b border-corp-border overflow-x-auto scrollbar-none">
            {tabs.map(t => (
              <button key={t.key} onClick={() => setTab(t.key as any)}
                className={cls('flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition whitespace-nowrap',
                  tab === t.key ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                )} data-testid={`modal-tab-${t.key}`}>
                <t.icon className="w-3.5 h-3.5" />{t.label}
              </button>
            ))}
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            {tab === 'info' && <TabInfo item={item} onMarkAudited={handleMarkAudited} onToggle={onToggle} onDelete={onDelete} onShowCondition={() => setShowConditionPanel(true)} onDuplicate={onDuplicate} />}
            {tab === 'edit' && <TabEdit item={item} categories={categories} subcategoriesMap={subcategoriesMap} hashtags={hashtags} shapes={shapes} colorDict={colorDict} materialDict={materialDict} onSave={() => { onItemUpdated(); setTab('info') }} />}
            {tab === 'photos' && <ProductImageGallery productId={item.id || item.product_id} onChange={() => onItemUpdated && onItemUpdated()} />}
            {tab === 'damage' && <TabDamage item={item} onDone={onItemUpdated} />}
            {tab === 'history' && <TabHistory item={item} />}
          </div>
        </div>
      </div>
      <ProductConditionPanel product={item} isOpen={showConditionPanel}
        onClose={() => setShowConditionPanel(false)} onRecordAdded={() => {}} />
    </>
  )
}

/* ─────────── Create New Product Modal ─────────── */
function CreateProductModal({ onClose, onCreated, categories, subcategoriesMap, hashtags, shapes, colorDict, materialDict, prefillItem }: any) {
  const emptyItem = {
    name: '', code: '', price: 0, rentalPrice: 0,
    color: '', material: '', categoryName: '', subcategoryName: '',
    heightCm: '', widthCm: '', depthCm: '', diameterCm: '',
    shape: '', components: '', hashtags: [], qty: 0, zone: '',
    description: '', careInstructions: '',
  }
  // If duplicating: pre-fill fields, but clear SKU (must be unique) and reset qty to 0
  const initialItem = prefillItem
    ? {
        ...prefillItem,
        name: `${prefillItem.name || ''} (копія)`,
        code: '',
        qty: 0,
      }
    : emptyItem
  const isDup = !!prefillItem
  const [createdId, setCreatedId] = useState<number | null>(null)
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4" data-testid="create-product-modal">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-2xl w-full max-w-3xl max-h-[92vh] overflow-hidden flex flex-col shadow-xl">
        <div className="flex items-center justify-between px-4 py-3 border-b border-corp-border bg-corp-bg-light/50">
          <div className="min-w-0">
            <div className="text-xs text-corp-text-muted">
              {createdId ? 'Крок 2/2: Завантажте фото' : (isDup ? `Дублювання з ${prefillItem.code || ''}` : 'Крок 1/2: Дані товару')}
            </div>
            <h2 className="text-base sm:text-lg font-bold text-corp-text-dark">
              {createdId ? '📸 Додайте фото товара' : (isDup ? 'Створити копію позиції' : 'Додати позицію в каталог')}
            </h2>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-slate-200 rounded-lg text-corp-text-muted flex-shrink-0" data-testid="create-modal-close-btn">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {!createdId ? (
            <TabEdit item={initialItem} categories={categories} subcategoriesMap={subcategoriesMap}
              hashtags={hashtags} shapes={shapes} colorDict={colorDict} materialDict={materialDict}
              onSave={(newId: number) => {
                if (newId) setCreatedId(newId)
                else onCreated()
              }} />
          ) : (
            <div className="space-y-4">
              <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 text-sm text-emerald-800">
                ✅ Товар створено. Тепер додайте фотографії (можна кілька одночасно).
              </div>
              <ProductImageGallery productId={createdId} onChange={undefined} />
              <div className="flex justify-end gap-2 pt-2 border-t border-corp-border">
                <button
                  onClick={onCreated}
                  className="px-4 py-2 rounded-lg bg-corp-primary text-white hover:bg-corp-primary/90 font-medium text-sm"
                  data-testid="finish-create-btn"
                >
                  Готово
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/* ════════════ MAIN COMPONENT ════════════ */
export default function ReauditCabinetFull({ onBackToDashboard, onNavigateToTasks }: { onBackToDashboard?: () => void; onNavigateToTasks?: () => void }) {
  const [items, setItems] = useState<any[]>([])
  const [stats, setStats] = useState({ total: 0, ok: 0, minor: 0, crit: 0 })
  const [categories, setCategories] = useState<string[]>([])
  const [subcategoriesMap, setSubcategoriesMap] = useState<Record<string, string[]>>({})
  const [hashtags, setHashtags] = useState<any[]>([])
  const [shapes, setShapes] = useState<string[]>([])
  const [colorDict, setColorDict] = useState<any[]>([])
  const [materialDict, setMaterialDict] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ q: '', category: '', subcategory: '', statusFilter: '' })
  const resetFilters = () => setFilters({ q: '', category: '', subcategory: '', statusFilter: '' })
  const [selectedItem, setSelectedItem] = useState<any>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [duplicateFrom, setDuplicateFrom] = useState<any>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 60

  const loadItems = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ limit: '9999' })
      if (filters.q) params.set('q', filters.q)
      if (filters.category) params.set('category', filters.category)
      if (filters.subcategory) params.set('subcategory', filters.subcategory)
      if (filters.statusFilter) params.set('status_filter', filters.statusFilter)
      const res = await fetch(`${BACKEND_URL}/api/audit/items?${params}`)
      if (res.ok) setItems(await res.json())
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [filters])

  // Auto-open product modal if URL has ?sku=XXX (from picking-list or other sources)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const skuFromUrl = params.get('sku')
    if (skuFromUrl && items.length > 0 && !selectedItem) {
      const target = items.find((it: any) => it.code === skuFromUrl)
      if (target) {
        setSelectedItem(target)
        // Clean URL so refresh doesn't keep opening it
        const newUrl = window.location.pathname
        window.history.replaceState({}, '', newUrl)
      }
    }
  }, [items])

  const loadStats = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/audit/stats`)
      if (res.ok) setStats(await res.json())
    } catch {}
  }

  const loadCategories = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/audit/categories`)
      if (res.ok) {
        const data = await res.json()
        setCategories(data.categories || [])
        setSubcategoriesMap(data.subcategories || {})
      }
    } catch {}
  }

  const loadDicts = async () => {
    try {
      const [hRes, sRes, cRes, mRes] = await Promise.all([
        fetch(`${BACKEND_URL}/api/audit/hashtags`),
        fetch(`${BACKEND_URL}/api/audit/shapes`),
        fetch(`${BACKEND_URL}/api/audit/colors`),
        fetch(`${BACKEND_URL}/api/audit/materials`),
      ])
      if (hRes.ok) { const d = await hRes.json(); setHashtags(d.hashtags || d || []) }
      if (sRes.ok) { const d = await sRes.json(); setShapes(d.shapes || d || []) }
      if (cRes.ok) { const d = await cRes.json(); setColorDict(d.colors || []) }
      if (mRes.ok) { const d = await mRes.json(); setMaterialDict(d.materials || []) }
    } catch {}
  }

  useEffect(() => { loadStats(); loadCategories(); loadDicts() }, [])
  useEffect(() => { setPage(1); loadItems() }, [loadItems])

  // Sync selectedItem with fresh data after items reload (fixes stale modal after edit)
  useEffect(() => {
    if (!selectedItem) return
    const fresh = items.find((i: any) => i.id === selectedItem.id)
    if (fresh && fresh !== selectedItem) setSelectedItem(fresh)
  }, [items])

  const paginatedItems = useMemo(() => items.slice(0, page * PAGE_SIZE), [items, page])
  const hasMore = page * PAGE_SIZE < items.length

  const handleItemUpdated = () => {
    loadItems(); loadStats()
  }

  const handleToggle = async (itm: any) => {
    const newStatus = itm.isDisabled ? 1 : 0
    const msg = newStatus === 0 ? 'Вимкнути цю позицію?' : 'Увімкнути цю позицію?'
    if (!window.confirm(msg)) return
    try {
      const token = localStorage.getItem('token')
      const headers: any = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`
      const res = await fetch(`${BACKEND_URL}/api/audit/items/${itm.id}/toggle-status`, {
        method: 'POST', headers, body: JSON.stringify({ status: newStatus })
      })
      if (res.ok) {
        setSelectedItem(null)
        handleItemUpdated()
      } else { const r = await res.json(); alert('Помилка: ' + (r.detail || '')) }
    } catch (e) { alert('Помилка: ' + String(e)) }
  }

  const handleDelete = async (itm: any) => {
    if (!window.confirm(`ВИДАЛИТИ "${itm.name}" назавжди? Цю дію не можна скасувати!`)) return
    try {
      const token = localStorage.getItem('token')
      const headers: any = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`
      const res = await fetch(`${BACKEND_URL}/api/audit/items/${itm.id}`, { method: 'DELETE', headers })
      if (res.ok) {
        setSelectedItem(null)
        handleItemUpdated()
      } else { const r = await res.json(); alert('Помилка: ' + (r.detail || '')) }
    } catch (e) { alert('Помилка: ' + String(e)) }
  }

  const handleDuplicate = (itm: any) => {
    setSelectedItem(null)
    setDuplicateFrom(itm)
  }

  // Active filter count for badge
  const activeFilters = [filters.q, filters.category, filters.subcategory, filters.statusFilter].filter(Boolean).length

  return (
    <div className="min-h-screen bg-corp-bg-page" data-testid="reaudit-cabinet">
      <CorporateHeader cabinetName="Кабінет переобліку" showBackButton />
      <div className="max-w-screen-2xl mx-auto px-3 lg:px-6 py-4 space-y-4">
        {/* KPI strip */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white rounded-xl border border-corp-border p-3 lg:p-4">
          <KpiStrip stats={stats} />
        </div>

        {/* Main layout */}
        <div className="flex gap-4">
          <Sidebar categories={categories} subcategoriesMap={subcategoriesMap}
            filters={filters} setFilters={setFilters} onReset={resetFilters}
            isMobileOpen={sidebarOpen} onMobileClose={() => setSidebarOpen(false)} />

          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-3">
              <div className="text-sm text-corp-text-muted">
                {loading ? 'Завантаження...' : `${items.length} товарів`}
              </div>
              <button
                onClick={() => setShowCreateModal(true)}
                className="flex items-center gap-1.5 rounded-full bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-1.5 text-xs font-semibold shadow-sm transition"
                data-testid="add-product-btn"
              >
                <Plus className="w-3.5 h-3.5" />
                Додати товар
              </button>
            </div>
            {loading ? (
              <div className="py-16 text-center text-corp-text-muted">Завантаження...</div>
            ) : items.length === 0 ? (
              <div className="py-16 text-center text-corp-text-muted bg-white rounded-xl border border-corp-border">
                За фільтрами нічого не знайдено
              </div>
            ) : (
              <>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2 lg:gap-3" data-testid="audit-grid">
                  {paginatedItems.map((item: any) => (
                    <AuditCard key={item.id} item={item} onClick={() => setSelectedItem(item)} />
                  ))}
                </div>
                {hasMore && (
                  <div className="mt-4 text-center">
                    <PillButton tone="ghost" onClick={() => setPage(p => p + 1)}>
                      Показати ще ({items.length - page * PAGE_SIZE} залишилось)
                    </PillButton>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* Floating filter FAB — mobile only */}
      <button onClick={() => setSidebarOpen(true)} data-testid="mobile-fab-filter"
        className="lg:hidden fixed bottom-6 right-6 z-30 flex items-center gap-2 bg-[#b5cc18] text-white rounded-full pl-3 pr-4 py-3 shadow-lg hover:shadow-xl transition-all active:scale-95">
        <Filter className="w-5 h-5" />
        <span className="text-sm font-semibold">Фільтри</span>
        {activeFilters > 0 && (
          <span className="absolute -top-1 -right-1 w-5 h-5 bg-rose-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
            {activeFilters}
          </span>
        )}
      </button>

      {/* Product detail modal */}
      {selectedItem && (
        <ProductModal item={selectedItem} onClose={() => setSelectedItem(null)}
          categories={categories} subcategoriesMap={subcategoriesMap}
          hashtags={hashtags} shapes={shapes} colorDict={colorDict} materialDict={materialDict}
          onItemUpdated={handleItemUpdated} onToggle={handleToggle} onDelete={handleDelete}
          onDuplicate={handleDuplicate} />
      )}

      {/* Create new product modal (also used for duplicate) */}
      {(showCreateModal || duplicateFrom) && (
        <CreateProductModal
          onClose={() => { setShowCreateModal(false); setDuplicateFrom(null) }}
          onCreated={() => { setShowCreateModal(false); setDuplicateFrom(null); handleItemUpdated() }}
          categories={categories} subcategoriesMap={subcategoriesMap}
          hashtags={hashtags} shapes={shapes} colorDict={colorDict} materialDict={materialDict}
          prefillItem={duplicateFrom}
        />
      )}
    </div>
  )
}
