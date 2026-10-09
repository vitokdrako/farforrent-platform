/* eslint-disable */
/**
 * BulkProductEditor — Масове редагування продуктів
 * Drag & drop колонок, інлайн-редагування, фільтри, пагінація
 */
import React, { useState, useEffect, useCallback, useRef } from 'react'
import { Search, ChevronLeft, ChevronRight, X, Filter, ZoomIn, GripVertical, RotateCcw } from 'lucide-react'
import { getImageUrl, handleImageError } from '../../utils/imageHelper'

const API = process.env.REACT_APP_BACKEND_URL || ''
const cls = (...a) => a.filter(Boolean).join(' ')
const LS_KEY = 'bulk_editor_col_order'

const authFetch = async (url, opts = {}) => {
  const token = localStorage.getItem('token')
  return fetch(url, { ...opts, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...opts.headers } })
}

const toast = {
  success: (msg) => { const el = document.createElement('div'); el.className = 'fixed top-4 right-4 z-[999] px-4 py-3 rounded-xl bg-emerald-600 text-white text-sm font-medium shadow-lg'; el.textContent = msg; document.body.appendChild(el); setTimeout(() => el.remove(), 2500) },
  error: (msg) => { const el = document.createElement('div'); el.className = 'fixed top-4 right-4 z-[999] px-4 py-3 rounded-xl bg-red-600 text-white text-sm font-medium shadow-lg'; el.textContent = msg; document.body.appendChild(el); setTimeout(() => el.remove(), 3000) },
}

const STATE_LABELS = { available: 'Доступний', damaged: 'Пошкоджений', good: 'Добрий', ok: 'OK', shelf: 'На полиці', '': '—' }
const SHAPE_OPTIONS = ['', 'круглий', 'квадратний', 'прямокутний', 'овальний']
const STATE_OPTIONS = ['', 'available', 'good', 'ok', 'shelf', 'damaged']

// ===== COLUMN DEFINITIONS =====
// id must match the product field name (except special ones like 'photo')
const ALL_COLUMNS = [
  { id: 'photo', label: 'Фото', w: 'w-14' },
  { id: 'sku', label: 'SKU', w: 'w-16' },
  { id: 'name', label: 'Назва', w: 'min-w-[180px]' },
  { id: 'category_name', label: 'Категорія', w: 'w-28' },
  { id: 'color', label: 'Колір', w: 'w-24' },
  { id: 'material', label: 'Матеріал', w: 'w-20' },
  { id: 'shape', label: 'Форма', w: 'w-16' },
  { id: 'rental_price', label: 'Оренда', w: 'w-16', type: 'number', align: 'text-right' },
  { id: 'price', label: 'Втрата', w: 'w-16', type: 'number', align: 'text-right' },
  { id: 'quantity', label: 'Кіл', w: 'w-10', type: 'number', align: 'text-center' },
  { id: 'zone', label: 'Зона', w: 'w-12' },
  { id: 'aisle', label: 'Ряд', w: 'w-12' },
  { id: 'shelf', label: 'Пол.', w: 'w-12' },
  { id: 'height_cm', label: 'В', w: 'w-12', type: 'number', align: 'text-right' },
  { id: 'width_cm', label: 'Ш', w: 'w-12', type: 'number', align: 'text-right' },
  { id: 'depth_cm', label: 'Г', w: 'w-12', type: 'number', align: 'text-right' },
  { id: 'diameter_cm', label: 'D', w: 'w-12', type: 'number', align: 'text-right' },
  { id: 'product_state', label: 'Стан', w: 'w-16' },
  { id: 'hashtags', label: 'Хештеги', w: 'min-w-[120px]' },
  { id: 'description', label: 'Опис', w: 'min-w-[140px]' },
  { id: 'care_instructions', label: 'Догляд', w: 'min-w-[140px]' },
]

const DEFAULT_ORDER = ALL_COLUMNS.map(c => c.id)

function getStoredOrder() {
  try {
    const saved = localStorage.getItem(LS_KEY)
    if (!saved) return DEFAULT_ORDER
    const parsed = JSON.parse(saved)
    // Merge: keep saved order but add any new columns not yet saved
    const known = new Set(parsed)
    const merged = [...parsed.filter(id => ALL_COLUMNS.some(c => c.id === id))]
    for (const c of ALL_COLUMNS) {
      if (!known.has(c.id)) merged.push(c.id)
    }
    return merged
  } catch { return DEFAULT_ORDER }
}

// ===== INLINE CELL =====
const InlineCell = ({ value, field, productId, onSave, type = 'text', options, className = '' }) => {
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState(value ?? '')
  const inputRef = useRef(null)

  useEffect(() => { setVal(value ?? '') }, [value])
  useEffect(() => { if (editing && inputRef.current) inputRef.current.focus() }, [editing])

  const save = () => {
    setEditing(false)
    const newVal = type === 'number' ? (val === '' ? null : parseFloat(val)) : val
    if (newVal !== value) onSave(productId, field, newVal)
  }

  const handleKey = (e) => {
    if (e.key === 'Enter') save()
    if (e.key === 'Escape') { setVal(value ?? ''); setEditing(false) }
  }

  if (editing) {
    if (options) {
      return (
        <select ref={inputRef} value={val} onChange={e => setVal(e.target.value)}
          onBlur={save} onKeyDown={handleKey}
          className="w-full px-1.5 py-1 text-xs border border-blue-400 rounded bg-blue-50 outline-none"
          data-testid={`edit-${field}-${productId}`}>
          {options.map(o => <option key={o} value={o}>{o || '—'}</option>)}
        </select>
      )
    }
    return (
      <input ref={inputRef} type={type} value={val}
        onChange={e => setVal(e.target.value)} onBlur={save} onKeyDown={handleKey}
        className={cls("w-full px-1.5 py-1 text-xs border border-blue-400 rounded bg-blue-50 outline-none", className)}
        step={type === 'number' ? 'any' : undefined}
        data-testid={`edit-${field}-${productId}`}
      />
    )
  }

  const isEmpty = value === null || value === undefined || value === '' || value === 0
  return (
    <div onClick={() => setEditing(true)}
      className={cls(
        "cursor-pointer px-1.5 py-1 text-xs rounded min-h-[24px] hover:bg-blue-50 transition-colors truncate",
        isEmpty && "text-slate-300 italic",
        className
      )}
      title={String(value ?? '')}
      data-testid={`cell-${field}-${productId}`}>
      {isEmpty ? '—' : (options ? (STATE_LABELS[value] || value) : String(value))}
    </div>
  )
}

// ===== PHOTO MODAL =====
const PhotoModal = ({ src, onClose }) => {
  if (!src) return null
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 p-4" onClick={onClose} data-testid="photo-modal">
      <div className="relative max-w-3xl max-h-[90vh]" onClick={e => e.stopPropagation()}>
        <button onClick={onClose} className="absolute -top-3 -right-3 w-8 h-8 rounded-full bg-white shadow-lg flex items-center justify-center text-slate-500 hover:text-slate-800 z-10">
          <X className="w-4 h-4" />
        </button>
        <img src={src} alt="" className="max-w-full max-h-[85vh] rounded-xl shadow-2xl object-contain" onError={handleImageError} />
      </div>
    </div>
  )
}

// ===== MAIN COMPONENT =====
export default function BulkProductEditor() {
  const [products, setProducts] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [loading, setLoading] = useState(true)

  // Filters
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [filterCategory, setFilterCategory] = useState('')
  const [filterColor, setFilterColor] = useState('')
  const [filterShape, setFilterShape] = useState('')
  const [filterState, setFilterState] = useState('')
  const [filterMissing, setFilterMissing] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const [filterOptions, setFilterOptions] = useState(null)

  // Photo modal
  const [photoModalSrc, setPhotoModalSrc] = useState(null)

  // Column ordering (drag & drop)
  const [colOrder, setColOrder] = useState(getStoredOrder)
  const dragCol = useRef(null)
  const dragOverCol = useRef(null)

  const orderedCols = colOrder.map(id => ALL_COLUMNS.find(c => c.id === id)).filter(Boolean)

  const handleDragStart = (idx) => { dragCol.current = idx }
  const handleDragEnter = (idx) => { dragOverCol.current = idx }
  const handleDragEnd = () => {
    if (dragCol.current === null || dragOverCol.current === null) return
    const from = dragCol.current
    const to = dragOverCol.current
    if (from === to) { dragCol.current = null; dragOverCol.current = null; return }
    const newOrder = [...colOrder]
    const [moved] = newOrder.splice(from, 1)
    newOrder.splice(to, 0, moved)
    setColOrder(newOrder)
    localStorage.setItem(LS_KEY, JSON.stringify(newOrder))
    dragCol.current = null
    dragOverCol.current = null
  }

  const resetColOrder = () => {
    setColOrder(DEFAULT_ORDER)
    localStorage.removeItem(LS_KEY)
  }

  // Load filter options
  useEffect(() => {
    const t = setTimeout(() => {
      authFetch(`${API}/api/admin/bulk-products/filters`).then(r => r.json()).then(setFilterOptions).catch(console.error)
    }, 2000)
    return () => clearTimeout(t)
  }, [])

  // Load products
  const loadProducts = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ page: String(page), per_page: '50' })
      if (search) params.append('search', search)
      if (filterCategory) params.append('category', filterCategory)
      if (filterColor) params.append('color', filterColor)
      if (filterShape) params.append('shape', filterShape)
      if (filterState) params.append('product_state', filterState)
      if (filterMissing) params.append('missing', filterMissing)
      const res = await authFetch(`${API}/api/admin/bulk-products?${params.toString()}`)
      if (res.ok) {
        const data = await res.json()
        setProducts(data.products || [])
        setTotal(data.total || 0)
        setTotalPages(data.total_pages || 1)
      }
    } catch (err) {
      console.error('[BulkEditor] Fetch error:', err)
    } finally {
      setLoading(false)
    }
  }, [page, search, filterCategory, filterColor, filterShape, filterState, filterMissing])

  useEffect(() => { loadProducts() }, [loadProducts])

  // Debounced search
  useEffect(() => {
    const t = setTimeout(() => { setSearch(searchInput); setPage(1) }, 400)
    return () => clearTimeout(t)
  }, [searchInput])

  // Save single field
  const handleSave = async (productId, field, value) => {
    try {
      const body = { [field]: value }
      const res = await authFetch(`${API}/api/admin/bulk-products/${productId}`, {
        method: 'PATCH', body: JSON.stringify(body)
      })
      if (res.ok) {
        setProducts(prev => prev.map(p =>
          p.product_id === productId ? { ...p, [field]: value } : p
        ))
        toast.success(`ID ${productId}: оновлено`)
      } else {
        const err = await res.json()
        toast.error(err.detail || 'Помилка')
      }
    } catch { toast.error('Помилка мережі') }
  }

  // Special save for hashtags (comma string -> array)
  const handleHashtagsSave = (productId, _field, commaStr) => {
    const arr = commaStr ? commaStr.split(',').map(s => s.trim()).filter(Boolean) : []
    handleSave(productId, 'hashtags', arr)
  }

  const clearFilters = () => {
    setFilterCategory(''); setFilterColor(''); setFilterShape('')
    setFilterState(''); setFilterMissing(''); setSearchInput(''); setSearch('')
    setPage(1)
  }

  const hasActiveFilters = filterCategory || filterColor || filterShape || filterState || filterMissing

  // ===== CELL RENDERER per column =====
  const renderCell = (col, p) => {
    if (col.id === 'photo') {
      const imgSrc = getImageUrl(p.image_url)
      return (
        <div className="relative w-10 h-10 rounded border border-slate-200 overflow-hidden bg-slate-50 cursor-pointer group/photo"
          onClick={() => imgSrc && setPhotoModalSrc(imgSrc)}
          data-testid={`bulk-photo-${p.product_id}`}>
          {imgSrc ? (
            <>
              <img src={imgSrc} alt="" className="w-full h-full object-cover" onError={handleImageError} />
              <div className="absolute inset-0 bg-black/0 group-hover/photo:bg-black/30 transition flex items-center justify-center opacity-0 group-hover/photo:opacity-100">
                <ZoomIn className="w-4 h-4 text-white" />
              </div>
            </>
          ) : (
            <div className="w-full h-full flex items-center justify-center text-slate-300 text-[9px]">—</div>
          )}
        </div>
      )
    }

    if (col.id === 'category_name' && filterOptions) {
      return <InlineCell value={p.category_name} field="category_name" productId={p.product_id} onSave={handleSave}
        options={['', ...filterOptions.categories]} />
    }

    if (col.id === 'shape') {
      return <InlineCell value={p.shape} field="shape" productId={p.product_id} onSave={handleSave} options={SHAPE_OPTIONS} />
    }

    if (col.id === 'product_state') {
      return <InlineCell value={p.product_state} field="product_state" productId={p.product_id} onSave={handleSave} options={STATE_OPTIONS} />
    }

    if (col.id === 'hashtags') {
      const displayVal = Array.isArray(p.hashtags) && p.hashtags.length > 0 ? p.hashtags.join(', ') : ''
      return <InlineCell value={displayVal} field="hashtags" productId={p.product_id} onSave={handleHashtagsSave} />
    }

    // Generic field
    const fieldName = col.id
    return <InlineCell
      value={p[fieldName]}
      field={fieldName}
      productId={p.product_id}
      onSave={handleSave}
      type={col.type || 'text'}
      className={cls(col.align, col.id === 'sku' && 'font-mono', col.id === 'name' && 'font-medium')}
    />
  }

  const colCount = orderedCols.length + 1 // +1 for ID column (pinned)

  return (
    <div className="space-y-4" data-testid="bulk-product-editor">
      {/* Search & Filter Bar */}
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input type="text" value={searchInput} onChange={e => setSearchInput(e.target.value)}
              placeholder="Пошук за назвою, SKU, ID..."
              className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-200"
              data-testid="bulk-search-input" />
          </div>

          <button onClick={() => setShowFilters(!showFilters)}
            className={cls("flex items-center gap-1.5 px-3 py-2 text-sm rounded-lg border transition",
              hasActiveFilters ? "bg-blue-50 border-blue-300 text-blue-700" : "border-slate-200 text-slate-600 hover:bg-slate-50"
            )} data-testid="bulk-filter-toggle">
            <Filter className="w-4 h-4" /> Фільтри
            {hasActiveFilters && <span className="w-2 h-2 rounded-full bg-blue-500" />}
          </button>

          <div className="text-sm text-slate-500">{total.toLocaleString('uk-UA')} товарів</div>

          {hasActiveFilters && (
            <button onClick={clearFilters} className="text-xs text-red-500 hover:text-red-700" data-testid="bulk-clear-filters">
              Скинути фільтри
            </button>
          )}

          {/* Reset columns button */}
          <button onClick={resetColOrder} title="Скинути порядок колонок"
            className="flex items-center gap-1 px-2 py-1.5 text-xs text-slate-500 hover:text-slate-700 border border-slate-200 rounded-lg hover:bg-slate-50 transition"
            data-testid="bulk-reset-columns">
            <RotateCcw className="w-3 h-3" /> Колонки
          </button>
        </div>

        {showFilters && filterOptions && (
          <div className="flex flex-wrap gap-3 mt-4 pt-4 border-t border-slate-100">
            <select value={filterCategory} onChange={e => { setFilterCategory(e.target.value); setPage(1) }}
              className="px-2 py-1.5 text-xs border border-slate-200 rounded-lg bg-white" data-testid="bulk-filter-category">
              <option value="">Всі категорії</option>
              {filterOptions.categories.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            <select value={filterColor} onChange={e => { setFilterColor(e.target.value); setPage(1) }}
              className="px-2 py-1.5 text-xs border border-slate-200 rounded-lg bg-white" data-testid="bulk-filter-color">
              <option value="">Всі кольори</option>
              {filterOptions.colors.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            <select value={filterShape} onChange={e => { setFilterShape(e.target.value); setPage(1) }}
              className="px-2 py-1.5 text-xs border border-slate-200 rounded-lg bg-white" data-testid="bulk-filter-shape">
              <option value="">Всі форми</option>
              {filterOptions.shapes.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <select value={filterState} onChange={e => { setFilterState(e.target.value); setPage(1) }}
              className="px-2 py-1.5 text-xs border border-slate-200 rounded-lg bg-white" data-testid="bulk-filter-state">
              <option value="">Всі стани</option>
              {filterOptions.states.map(s => <option key={s} value={s}>{STATE_LABELS[s] || s}</option>)}
            </select>
            <select value={filterMissing} onChange={e => { setFilterMissing(e.target.value); setPage(1) }}
              className={cls("px-2 py-1.5 text-xs border rounded-lg",
                filterMissing ? "border-amber-400 bg-amber-50 text-amber-800" : "border-slate-200 bg-white"
              )} data-testid="bulk-filter-missing">
              <option value="">Відсутні атрибути</option>
              {Object.entries(filterOptions.missing_counts).map(([key, count]) => {
                const labels = { color: 'Колір', photo: 'Фото', price: 'Ціна оренди', loss_price: 'Ціна втрати',
                  dimensions: 'Розміри', shape: 'Форма', material: 'Матеріал', sku: 'Артикул' }
                return <option key={key} value={key}>Без {labels[key] || key} ({count})</option>
              })}
            </select>
          </div>
        )}
      </div>

      {/* Draggable hint */}
      <p className="text-[11px] text-slate-400 px-1">Перетягуй заголовки колонок для зміни порядку</p>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left" data-testid="bulk-products-table">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                {/* ID column - always first, not draggable */}
                <th className="px-2 py-2.5 text-[10px] font-semibold text-slate-500 uppercase w-12 sticky left-0 bg-slate-50 z-10">ID</th>

                {orderedCols.map((col, idx) => (
                  <th key={col.id}
                    draggable
                    onDragStart={() => handleDragStart(idx)}
                    onDragEnter={() => handleDragEnter(idx)}
                    onDragEnd={handleDragEnd}
                    onDragOver={e => e.preventDefault()}
                    className={cls(
                      "px-2 py-2.5 text-[10px] font-semibold text-slate-500 uppercase cursor-grab active:cursor-grabbing select-none",
                      col.w, col.align,
                      "hover:bg-slate-100 transition-colors"
                    )}
                    data-testid={`col-header-${col.id}`}
                  >
                    <span className="flex items-center gap-0.5">
                      <GripVertical className="w-3 h-3 text-slate-300 flex-shrink-0" />
                      {col.label}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr><td colSpan={colCount} className="px-4 py-12 text-center text-slate-400">Завантаження...</td></tr>
              ) : products.length === 0 ? (
                <tr><td colSpan={colCount} className="px-4 py-12 text-center text-slate-400">Товарів не знайдено</td></tr>
              ) : products.map(p => (
                <tr key={p.product_id} className="hover:bg-slate-50/50 group" data-testid={`bulk-row-${p.product_id}`}>
                  <td className="px-2 py-1.5 text-[11px] font-mono text-slate-400 sticky left-0 bg-white group-hover:bg-slate-50/50 z-10">{p.product_id}</td>
                  {orderedCols.map(col => (
                    <td key={col.id} className="px-1 py-1">{renderCell(col, p)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-200 bg-slate-50">
            <div className="text-xs text-slate-500">
              Сторінка {page} з {totalPages} ({total.toLocaleString('uk-UA')} товарів)
            </div>
            <div className="flex items-center gap-1">
              <button onClick={() => setPage(1)} disabled={page <= 1}
                className="px-2 py-1 text-xs rounded border border-slate-200 hover:bg-white disabled:opacity-30">1</button>
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}
                className="px-2 py-1 text-xs rounded border border-slate-200 hover:bg-white disabled:opacity-30"
                data-testid="bulk-page-prev">
                <ChevronLeft className="w-3 h-3" />
              </button>
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                let num
                if (totalPages <= 5) num = i + 1
                else if (page <= 3) num = i + 1
                else if (page >= totalPages - 2) num = totalPages - 4 + i
                else num = page - 2 + i
                return (
                  <button key={num} onClick={() => setPage(num)}
                    className={cls("px-2.5 py-1 text-xs rounded border transition",
                      num === page ? "bg-slate-800 text-white border-slate-800" : "border-slate-200 hover:bg-white"
                    )}>{num}</button>
                )
              })}
              <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages}
                className="px-2 py-1 text-xs rounded border border-slate-200 hover:bg-white disabled:opacity-30"
                data-testid="bulk-page-next">
                <ChevronRight className="w-3 h-3" />
              </button>
              <button onClick={() => setPage(totalPages)} disabled={page >= totalPages}
                className="px-2 py-1 text-xs rounded border border-slate-200 hover:bg-white disabled:opacity-30">
                {totalPages}</button>
            </div>
          </div>
        )}
      </div>

      {photoModalSrc && <PhotoModal src={photoModalSrc} onClose={() => setPhotoModalSrc(null)} />}
    </div>
  )
}
