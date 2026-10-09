import React, { useMemo, useState, useEffect } from 'react'

/**************** helpers ****************/
const cls = (...a: (string | false | null | undefined)[]) => a.filter(Boolean).join(' ')
const fmtUA = (n: number) => (Number(n) || 0).toLocaleString('uk-UA', { maximumFractionDigits: 0 })

/**************** types ****************/
type InventoryStatus = 'available' | 'reserved' | 'on_rent' | 'washing' | 'repair' | 'lost'

type HistoryKind =
  | 'created'
  | 'edited'
  | 'moved'
  | 'rent_out'
  | 'returned'
  | 'damage_opened'
  | 'damage_closed'
  | 'cleaned'

interface InventoryItem {
  id: string
  code: string
  status: InventoryStatus
  location: string
  lastOrderId?: string
  lastMovementAt: string
  note?: string
}

interface HistoryEvent {
  id: string
  date: string
  kind: HistoryKind
  actor: string
  orderId?: string
  note: string
}

interface StatusSummary {
  total: number
  available: number
  reserved: number
  on_rent: number
  washing: number
  repair: number
  lost: number
}

interface Product {
  id: string
  product_id: number
  name: string
  mainSku: string
  skuPrefix: string
  category: string
  subcategory?: string
  color?: string
  material?: string
  size?: string
  imageUrl?: string
  defaultLocation: string
  tags: string[]
  description: string
  careNotes: string
  createdAt: string
  updatedAt: string
  statusSummary: StatusSummary
  inventory?: InventoryItem[]
  history?: HistoryEvent[]
  price?: number
  ean?: string
}

/**************** small UI ****************/
function Badge({ tone = 'slate', children }: { tone?: string; children: React.ReactNode }) {
  const tones: Record<string, string> = {
    slate: 'bg-slate-100 text-slate-700 border-slate-200',
    green: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    blue: 'bg-sky-100 text-sky-700 border-sky-200',
    amber: 'bg-amber-100 text-amber-800 border-amber-200',
    violet: 'bg-violet-100 text-violet-700 border-violet-200',
    red: 'bg-rose-100 text-rose-700 border-rose-200',
  }
  return (
    <span
      className={cls(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px]',
        tones[tone] || tones.slate,
      )}
    >
      {children}
    </span>
  )
}

function PillButton({
  children,
  onClick,
  tone = 'slate',
}: {
  children: React.ReactNode
  onClick?: () => void
  tone?: 'slate' | 'green' | 'ghost' | 'red'
}) {
  const tones: Record<string, string> = {
    slate: 'bg-slate-900 text-white hover:bg-slate-800',
    green: 'bg-emerald-600 text-white hover:bg-emerald-700',
    red: 'bg-rose-600 text-white hover:bg-rose-700',
    ghost: 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-50',
  }
  return (
    <button
      type="button"
      onClick={onClick}
      className={cls('rounded-full px-3 py-1 text-[11px] font-medium transition', tones[tone])}
    >
      {children}
    </button>
  )
}

function Card({ title, children, right }: { title: string; children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-corp-text-dark">{title}</h3>
        {right}
      </div>
      {children}
    </div>
  )
}

function StatusPill({ summary }: { summary: StatusSummary }) {
  return (
    <div className="flex flex-wrap gap-1 text-[10px]">
      <Badge tone="slate">Всього: {summary.total}</Badge>
      {summary.available > 0 && <Badge tone="green">В наявності: {summary.available}</Badge>}
      {summary.reserved > 0 && <Badge tone="amber">Резерв: {summary.reserved}</Badge>}
      {summary.on_rent > 0 && <Badge tone="blue">В оренді: {summary.on_rent}</Badge>}
      {summary.washing > 0 && <Badge tone="violet">Мийка: {summary.washing}</Badge>}
      {summary.repair > 0 && <Badge tone="red">Реставрація: {summary.repair}</Badge>}
      {summary.lost > 0 && <Badge tone="red">Втрачено: {summary.lost}</Badge>}
    </div>
  )
}

function TagChip({ label }: { label: string }) {
  return <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-corp-text-main">{label}</span>
}

/**************** left: list & filters ****************/
function CatalogList({
  products,
  selectedId,
  onSelect,
  loading
}: {
  products: Product[]
  selectedId: string | null
  onSelect: (id: string) => void
  loading: boolean
}) {
  const [q, setQ] = useState('')
  const [cat, setCat] = useState('all')

  const filtered = useMemo(() => {
    return products.filter((p) => {
      const text = (p.name + p.mainSku + p.category + (p.subcategory || '') + p.tags.join(' ')).toLowerCase()
      const okQ = !q || text.includes(q.toLowerCase())
      const okCat = cat === 'all' || p.category === cat
      return okQ && okCat
    })
  }, [products, q, cat])

  const categories = Array.from(new Set(products.map((p) => p.category)))

  return (
    <div className="space-y-3">
      <Card
        title="Каталог реквізиту"
        right={<Badge tone="blue">{filtered.length} позицій</Badge>}
      >
        <div className="flex flex-col gap-2 text-[11px] md:flex-row md:items-center">
          <div className="flex-1">
            <input
              className="w-full rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px]"
              placeholder="Пошук по назві, SKU, тегам..."
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-corp-text-muted">Категорія:</span>
            <select
              className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px]"
              value={cat}
              onChange={(e) => setCat(e.target.value)}
            >
              <option value="all">Усі</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
        </div>
      </Card>

      <div className="rounded-2xl border border-slate-200 bg-white">
        <div className="border-b border-slate-100 px-3 py-2 text-[11px] text-corp-text-muted">Список товарів</div>
        {loading ? (
          <div className="py-8 text-center text-sm text-corp-text-muted">Завантаження...</div>
        ) : (
          <div className="max-h-[460px] divide-y divide-slate-100 overflow-auto text-xs">
            {filtered.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => onSelect(p.id)}
                className={cls(
                  'flex w-full items-start justify-between gap-2 px-3 py-2 text-left hover:bg-slate-50',
                  selectedId === p.id && 'bg-slate-900/5',
                )}
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-semibold text-corp-text-dark">{p.name}</span>
                  </div>
                  <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[10px] text-corp-text-muted">
                    <span>{p.category}</span>
                    {p.subcategory && <span>· {p.subcategory}</span>}
                    <span>· SKU: {p.mainSku}</span>
                  </div>
                  <div className="mt-1">
                    <StatusPill summary={p.statusSummary} />
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1 text-[10px] text-corp-text-muted">
                  <span>Стелаж: {p.defaultLocation}</span>
                  <span>Оновлено: {p.updatedAt ? new Date(p.updatedAt).toLocaleDateString('uk-UA') : 'N/A'}</span>
                </div>
              </button>
            ))}
            {filtered.length === 0 && (
              <div className="px-3 py-6 text-center text-[11px] text-corp-text-muted">За фільтрами нічого не знайдено</div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

/**************** right: product details tabs ****************/
function PassportTab({ product, onSave }: { product: Product; onSave: (data: any) => void }) {
  const [edit, setEdit] = useState(false)
  const [form, setForm] = useState({
    name: product.name,
    mainSku: product.mainSku,
    category: product.category,
    subcategory: product.subcategory || '',
    color: product.color || '',
    material: product.material || '',
    size: product.size || '',
    defaultLocation: product.defaultLocation,
    description: product.description,
    careNotes: product.careNotes,
  })

  const save = () => {
    setEdit(false)
    onSave(form)
  }

  return (
    <Card
      title="Паспорт товару"
      right={
        <div className="flex gap-2">
          {!edit && (
            <PillButton tone="ghost" onClick={() => setEdit(true)}>
              Редагувати
            </PillButton>
          )}
          {edit && (
            <PillButton tone="green" onClick={save}>
              Зберегти
            </PillButton>
          )}
        </div>
      }
    >
      <div className="grid gap-4 md:grid-cols-3 text-[11px]">
        <div className="md:col-span-2 space-y-3">
          <div className="grid gap-2 md:grid-cols-2">
            <div>
              <label className="block text-corp-text-muted">Назва</label>
              <input
                disabled={!edit}
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 disabled:bg-slate-50"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-corp-text-muted">Основний SKU</label>
              <input
                disabled={!edit}
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 disabled:bg-slate-50"
                value={form.mainSku}
                onChange={(e) => setForm({ ...form, mainSku: e.target.value })}
              />
            </div>
          </div>
          <div className="grid gap-2 md:grid-cols-3">
            <div>
              <label className="block text-corp-text-muted">Категорія</label>
              <input
                disabled={!edit}
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 disabled:bg-slate-50"
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-corp-text-muted">Підкатегорія</label>
              <input
                disabled={!edit}
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 disabled:bg-slate-50"
                value={form.subcategory}
                onChange={(e) => setForm({ ...form, subcategory: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-corp-text-muted">Колір</label>
              <input
                disabled={!edit}
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 disabled:bg-slate-50"
                value={form.color}
                onChange={(e) => setForm({ ...form, color: e.target.value })}
              />
            </div>
          </div>
          <div className="grid gap-2 md:grid-cols-3">
            <div>
              <label className="block text-corp-text-muted">Матеріал</label>
              <input
                disabled={!edit}
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 disabled:bg-slate-50"
                value={form.material}
                onChange={(e) => setForm({ ...form, material: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-corp-text-muted">Розмір / тип</label>
              <input
                disabled={!edit}
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 disabled:bg-slate-50"
                value={form.size}
                onChange={(e) => setForm({ ...form, size: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-corp-text-muted">Базове місцезнаходження</label>
              <input
                disabled={!edit}
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 disabled:bg-slate-50"
                value={form.defaultLocation}
                onChange={(e) => setForm({ ...form, defaultLocation: e.target.value })}
              />
            </div>
          </div>
          <div>
            <label className="block text-corp-text-muted">Опис</label>
            <textarea
              disabled={!edit}
              rows={3}
              className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 disabled:bg-slate-50"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-corp-text-muted">Нотатки по догляду</label>
            <textarea
              disabled={!edit}
              rows={3}
              className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 disabled:bg-slate-50"
              value={form.careNotes}
              onChange={(e) => setForm({ ...form, careNotes: e.target.value })}
            />
          </div>
        </div>
        <div className="space-y-3">
          <div>
            <div className="mb-1 text-corp-text-muted">Теги</div>
            <div className="flex flex-wrap gap-1">
              {product.tags.map((t) => (
                <TagChip key={t} label={t} />
              ))}
            </div>
          </div>
          <div>
            <div className="mb-1 text-corp-text-muted">Статуси</div>
            <StatusPill summary={product.statusSummary} />
          </div>
          <div className="text-[10px] text-corp-text-muted">
            Створено: {product.createdAt ? new Date(product.createdAt).toLocaleDateString('uk-UA') : 'N/A'}
            <br />
            Оновлено: {product.updatedAt ? new Date(product.updatedAt).toLocaleDateString('uk-UA') : 'N/A'}
          </div>
          <div className="rounded-xl bg-slate-50 p-2 text-[10px] text-corp-text-main">
            <div className="mb-1 font-semibold text-corp-text-dark">Швидкі дії</div>
            <div className="flex flex-wrap gap-2">
              <PillButton
                tone="ghost"
                onClick={() => alert('Мок: створити нову інвентарну одиницю на базі цього товару.')}
              >
                + Додати одиницю на склад
              </PillButton>
              <PillButton
                tone="ghost"
                onClick={() => alert('Мок: відкрити цей товар у кабінеті шкоди з фільтром по всіх кейсах.')}
              >
                Відкрити в кабінеті шкоди
              </PillButton>
            </div>
          </div>
        </div>
      </div>
    </Card>
  )
}

function InventoryTab({ product }: { product: Product }) {
  const inventory = product.inventory || []

  return (
    <Card title="Інвентарні одиниці" right={<Badge tone="blue">{inventory.length} од.</Badge>}>
      {inventory.length === 0 ? (
        <div className="py-8 text-center text-[11px] text-corp-text-muted">
          Інвентарні одиниці не створені. Натисніть "+ Додати одиницю" щоб створити.
        </div>
      ) : (
        <div className="space-y-2 text-[11px]">
          {inventory.map((item) => (
            <div key={item.id} className="rounded-xl border border-slate-100 bg-slate-50 p-3">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="font-semibold text-corp-text-dark">{item.code}</div>
                  <div className="mt-1 text-[10px] text-corp-text-main">
                    📍 {item.location}
                  </div>
                  {item.note && (
                    <div className="mt-1 text-[10px] text-corp-text-muted">{item.note}</div>
                  )}
                </div>
                <div className="flex flex-col items-end gap-1">
                  <Badge tone={item.status === 'available' ? 'green' : 'amber'}>{item.status}</Badge>
                  <span className="text-[10px] text-corp-text-muted">
                    {item.lastMovementAt ? new Date(item.lastMovementAt).toLocaleDateString('uk-UA') : 'N/A'}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

function HistoryTab({ product }: { product: Product }) {
  const history = product.history || []

  const eventLabels: Record<string, string> = {
    created: '📦 Створено',
    edited: '✏️ Редаговано',
    moved: '🚚 Переміщено',
    rent_out: '📤 Видано в оренду',
    returned: '📥 Повернуто',
    damage_opened: '⚠️ Відкрито кейс шкоди',
    damage_closed: '✅ Кейс шкоди закрито',
    cleaned: '🧼 Очищено',
  }

  return (
    <Card title="Історія операцій" right={<Badge tone="blue">{history.length} подій</Badge>}>
      {history.length === 0 ? (
        <div className="py-8 text-center text-[11px] text-corp-text-muted">
          Історія порожня
        </div>
      ) : (
        <div className="space-y-2 text-[11px]">
          {history.map((event) => (
            <div key={event.id} className="rounded-xl border border-slate-100 bg-slate-50 p-3">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="font-semibold text-corp-text-dark">
                    {eventLabels[event.kind] || event.kind}
                  </div>
                  <div className="mt-1 text-[10px] text-corp-text-main">
                    {event.note}
                  </div>
                  <div className="mt-1 text-[10px] text-corp-text-muted">
                    Виконав: {event.actor}
                    {event.orderId && ` · Замовлення: #${event.orderId}`}
                  </div>
                </div>
                <div className="text-[10px] text-corp-text-muted">
                  {new Date(event.date).toLocaleDateString('uk-UA')}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

/**************** main component ****************/
export default function ExtendedCatalog({ onBackToDashboard }: { onBackToDashboard: () => void }) {
  const [products, setProducts] = useState<Product[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  const [activeTab, setActiveTab] = useState<'passport' | 'inventory' | 'history'>('passport')
  const [loading, setLoading] = useState(false)
  const [detailsLoading, setDetailsLoading] = useState(false)

  const API_URL = process.env.REACT_APP_BACKEND_URL

  // Завантажити список продуктів
  const loadProducts = async () => {
    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/api/catalog/extended/search?limit=9999`)
      const data = await response.json()
      
      if (data.items && Array.isArray(data.items)) {
        setProducts(data.items)
        if (data.items.length > 0 && !selectedId) {
          setSelectedId(data.items[0].id)
        }
      } else {
        setProducts([])
      }
    } catch (error) {
      console.error('Помилка завантаження:', error)
      setProducts([])
    } finally {
      setLoading(false)
    }
  }

  // Завантажити деталі продукту
  const loadProductDetails = async (productId: string) => {
    setDetailsLoading(true)
    try {
      const numericId = productId.replace('P-', '')
      const response = await fetch(`${API_URL}/api/catalog/extended/product/${numericId}`)
      const data = await response.json()
      setSelectedProduct(data)
    } catch (error) {
      console.error('Помилка завантаження деталей:', error)
    } finally {
      setDetailsLoading(false)
    }
  }

  // Зберегти зміни
  const handleSave = async (formData: any) => {
    if (!selectedProduct) return
    
    try {
      const numericId = selectedProduct.id.replace('P-', '')
      const response = await fetch(`${API_URL}/api/catalog/extended/product/${numericId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      })
      
      const data = await response.json()
      if (data.success) {
        alert('✅ Зміни збережено!')
        loadProductDetails(selectedProduct.id)
      }
    } catch (error) {
      console.error('Помилка збереження:', error)
      alert('❌ Помилка збереження')
    }
  }

  useEffect(() => {
    loadProducts()
  }, [])

  useEffect(() => {
    if (selectedId) {
      loadProductDetails(selectedId)
    }
  }, [selectedId])

  return (
    <div className="mx-auto max-w-7xl p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-corp-text-dark">Розширений каталог</h1>
          <p className="text-sm text-corp-text-muted">
            Повна інформація про товари: паспорт, інвентарні одиниці, історія руху
          </p>
        </div>
        <button
          onClick={onBackToDashboard}
          className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] text-slate-700 hover:bg-slate-50"
        >
          ← До дашборду
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <CatalogList
          products={products}
          selectedId={selectedId}
          onSelect={setSelectedId}
          loading={loading}
        />

        <div className="space-y-3">
          {/* Tabs */}
          <div className="flex gap-2 text-[11px]">
            <button
              onClick={() => setActiveTab('passport')}
              className={cls(
                'rounded-full px-3 py-1 transition',
                activeTab === 'passport' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              )}
            >
              Паспорт
            </button>
            <button
              onClick={() => setActiveTab('inventory')}
              className={cls(
                'rounded-full px-3 py-1 transition',
                activeTab === 'inventory' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              )}
            >
              Інвентар
            </button>
            <button
              onClick={() => setActiveTab('history')}
              className={cls(
                'rounded-full px-3 py-1 transition',
                activeTab === 'history' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              )}
            >
              Історія
            </button>
          </div>

          {/* Content */}
          {detailsLoading ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-corp-text-muted">
              Завантаження...
            </div>
          ) : selectedProduct ? (
            <>
              {activeTab === 'passport' && <PassportTab product={selectedProduct} onSave={handleSave} />}
              {activeTab === 'inventory' && <InventoryTab product={selectedProduct} />}
              {activeTab === 'history' && <HistoryTab product={selectedProduct} />}
            </>
          ) : (
            <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-corp-text-muted">
              Оберіть товар зі списку
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
