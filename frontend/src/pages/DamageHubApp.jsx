/* eslint-disable */
/**
 * DamageHubApp - Кабінет шкоди
 * 
 * Три колонки: Мийка | Реставрація | Пральня (черга + партії)
 * Декор летить одразу з повернення у відповідну чергу
 */
import React, { useState, useEffect, useCallback, useRef } from "react";
import CorporateHeader from "../components/CorporateHeader";
import { getImageUrl, handleImageError, FALLBACK_IMAGE } from "../utils/imageHelper";
import { Search, Droplets, Wrench, Shirt, Package, RefreshCw, Check, X, ChevronDown, ChevronRight, Plus, Clock, ArrowRight, Printer, Camera, Trash2 } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";
const fmtTime = (d) => d ? new Date(d).toLocaleString("uk-UA", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—";
const fmtDate = (d) => d ? new Date(d).toLocaleDateString("uk-UA") : "—";

const authFetch = async (url, options = {}) => {
  const token = localStorage.getItem("token");
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return fetch(url, { ...options, headers: { ...headers, ...options.headers } });
};

const getPhotoUrl = (item) => {
  return getImageUrl(item?.product_image || item?.photo_url || item?.image_url || item?.image);
};

// ============= QUICK ADD POPOVER =============
const QuickAddPopover = ({ queueType, onAdd, onClose }) => {
  const [query, setQuery] = useState('');
  const [qty, setQty] = useState(1);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(null);
  const inputRef = useRef(null);
  const timerRef = useRef(null);

  useEffect(() => { inputRef.current?.focus(); }, []);
  useEffect(() => () => clearTimeout(timerRef.current), []);

  const doSearch = (q) => {
    clearTimeout(timerRef.current);
    if (!q || q.length < 2) { setResults([]); setLoading(false); return; }
    setLoading(true);
    timerRef.current = setTimeout(async () => {
      try {
        const res = await authFetch(`${BACKEND_URL}/api/catalog?search=${encodeURIComponent(q)}&limit=20`);
        const data = await res.json();
        const items = Array.isArray(data) ? data : (data.products || data.items || []);
        setResults(items);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);
  };

  const handleAdd = async (product) => {
    const pid = product.product_id || product.id;
    setAdding(pid);
    try {
      await onAdd({
        product_id: pid,
        sku: product.sku || '',
        product_name: product.name || product.product_name || '',
        category: product.category || product.category_name || '',
        queue_type: queueType,
        quantity: qty,
        notes: `Додано вручну (${qty} шт)`
      });
      setQuery('');
      setResults([]);
      setQty(1);
    } catch {
      // handled upstream
    } finally {
      setAdding(null);
    }
  };

  const queueLabel = { wash: 'Мийку', restoration: 'Реставрацію', laundry: 'Пральню' }[queueType] || queueType;
  const queueColor = { wash: 'blue', restoration: 'orange', laundry: 'purple' }[queueType] || 'slate';

  return (
    <div className="absolute top-full left-0 right-0 mt-1 z-40 rounded-xl border border-slate-200 bg-white shadow-xl overflow-hidden" data-testid="quick-add-popover">
      <div className={`px-3 py-2 border-b bg-${queueColor}-50 flex items-center justify-between`}>
        <span className={`text-xs font-semibold text-${queueColor}-700`}>Додати в {queueLabel}</span>
        <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-600 rounded-md hover:bg-white/60">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
      <div className="flex items-center gap-2 p-2.5 border-b border-slate-100">
        <Search className="w-4 h-4 text-slate-400 flex-shrink-0" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={e => { setQuery(e.target.value); doSearch(e.target.value); }}
          onKeyDown={e => e.key === 'Escape' && onClose()}
          placeholder="Артикул (SKU) або назва..."
          className="flex-1 text-sm bg-transparent outline-none placeholder:text-slate-400"
          data-testid="quick-add-search-input"
        />
        <div className="flex items-center gap-0.5 flex-shrink-0 border border-slate-200 rounded-lg">
          <button onClick={() => setQty(Math.max(1, qty - 1))} className="px-1.5 py-0.5 text-slate-500 hover:text-slate-800 text-sm font-bold">-</button>
          <input
            type="number"
            min={1}
            value={qty}
            onChange={e => setQty(Math.max(1, parseInt(e.target.value) || 1))}
            className="w-8 text-center text-sm font-medium bg-transparent outline-none [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
            data-testid="quick-add-qty-input"
          />
          <button onClick={() => setQty(qty + 1)} className="px-1.5 py-0.5 text-slate-500 hover:text-slate-800 text-sm font-bold">+</button>
        </div>
        {loading && <RefreshCw className="w-3.5 h-3.5 text-slate-400 animate-spin flex-shrink-0" />}
      </div>

      <div className="max-h-[320px] overflow-y-auto">
        {loading && results.length === 0 ? (
          <div className="text-center py-6 text-slate-400 text-xs"><RefreshCw className="w-4 h-4 animate-spin mx-auto mb-1" />Пошук...</div>
        ) : results.length === 0 ? (
          <div className="text-center py-5 text-xs text-slate-400">
            {query.length < 2 ? "Введіть мінімум 2 символи" : "Товари не знайдено"}
          </div>
        ) : (
          <div className="divide-y divide-slate-50">
            {results.map(p => {
              const pid = p.product_id || p.id;
              const imgSrc = getImageUrl(p.image || p.image_url || p.cover || p.photo);
              return (
                <button
                  key={pid}
                  onClick={() => handleAdd(p)}
                  disabled={adding === pid}
                  className="w-full flex items-center gap-2.5 px-3 py-2 text-left hover:bg-emerald-50 transition-colors disabled:opacity-50"
                  data-testid={`quick-add-item-${pid}`}
                >
                  {imgSrc ? (
                    <img src={imgSrc} className="w-10 h-10 rounded-md object-cover border border-slate-200 flex-shrink-0" alt="" onError={handleImageError} />
                  ) : (
                    <div className="w-10 h-10 rounded-md bg-slate-100 border border-slate-200 flex items-center justify-center flex-shrink-0"><Package className="w-4 h-4 text-slate-400" /></div>
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-slate-800 truncate">{p.name || p.product_name}</div>
                    <div className="text-xs text-slate-500 truncate">{p.sku} {p.category_name ? `\u00B7 ${p.category_name}` : ''}</div>
                  </div>
                  <div className="text-right flex-shrink-0 mr-1">
                    <div className="text-xs font-semibold text-slate-700">{p.available ?? p.quantity ?? '—'}</div>
                    <div className="text-[10px] text-slate-400">доступно</div>
                  </div>
                  {adding === pid ? (
                    <RefreshCw className="w-4 h-4 text-emerald-500 animate-spin flex-shrink-0" />
                  ) : (
                    <Plus className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

// ============= ITEM CARD =============
const QueueItemCard = ({ item, onComplete, onDelete, onPhotoClick, completing }) => {
  const [acceptQty, setAcceptQty] = useState(null); // null = не показувати, число = кількість
  const photoUrl = getPhotoUrl(item);
  const isInProgress = item.processing_status === 'in_progress';
  
  const totalQty = item.qty || 1;
  const processedQty = item.processed_qty || 0;
  const remaining = totalQty - processedQty;

  const handleAccept = () => {
    const qty = acceptQty ?? remaining;
    onComplete(item.id, qty);
    setAcceptQty(null);
  };

  return (
    <div className={`p-2.5 sm:p-3 rounded-xl border bg-white transition-all hover:shadow-sm ${isInProgress ? 'border-blue-200 bg-blue-50/30' : 'border-slate-200'}`}>
      <div className="flex gap-2 sm:gap-3">
        {/* Photo */}
        {photoUrl ? (
          <img
            src={photoUrl}
            alt={item.product_name}
            className="w-10 h-10 sm:w-14 sm:h-14 rounded-lg object-cover border border-slate-200 cursor-pointer hover:opacity-80 flex-shrink-0"
            onClick={() => onPhotoClick?.(photoUrl, item.product_name)}
            onError={handleImageError}
          />
        ) : (
          <div className="w-10 h-10 sm:w-14 sm:h-14 rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center flex-shrink-0">
            <Package className="w-4 h-4 sm:w-5 sm:h-5 text-slate-400" />
          </div>
        )}
        
        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="font-semibold text-slate-800 text-sm truncate">{item.product_name}</div>
              <div className="text-xs text-slate-500 font-mono">{item.sku}</div>
            </div>
            <span className="flex-shrink-0 px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 text-xs font-bold">
              {processedQty > 0 ? `${processedQty}/${totalQty}` : totalQty} шт
            </span>
          </div>
          
          {/* Damage type */}
          <div className="mt-1.5 px-2 py-1 rounded-lg bg-amber-50 border border-amber-100 text-xs text-amber-800 truncate" title={item.damage_type}>
            {item.damage_type || "Не вказано"}
          </div>
          
          {/* Meta row */}
          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-slate-500">
            <span title="Замовлення">
              <span className="font-medium text-slate-700">#{item.order_number}</span>
            </span>
            <span title="Відправлено">
              {fmtTime(item.sent_to_processing_at || item.created_at)}
            </span>
            {item.created_by && (
              <span className="truncate max-w-[120px]" title={`Розподілив: ${item.created_by}`}>
                {item.created_by.split('@')[0]}
              </span>
            )}
          </div>
          
          {/* Note */}
          {item.note && (
            <div className="mt-1.5 text-xs text-slate-600 italic truncate" title={item.note}>
              {item.note}
            </div>
          )}
        </div>
      </div>
      
      {/* Action */}
      <div className="mt-2 flex items-center justify-end gap-1.5 flex-wrap">
        <button
          onClick={() => onDelete(item.id)}
          className="px-3 py-1.5 rounded-lg text-xs font-medium bg-red-50 text-red-600 border border-red-200 hover:bg-red-100 transition-colors flex items-center gap-1"
        >
          <X className="w-3.5 h-3.5" />
          Видалити
        </button>
        
        {remaining > 1 ? (
          <div className="flex items-center gap-1">
            <div className="flex items-center border border-emerald-200 rounded-lg overflow-hidden bg-emerald-50/50">
              <button
                onClick={() => setAcceptQty(Math.max(1, (acceptQty ?? remaining) - 1))}
                className="px-1.5 py-1 text-emerald-600 hover:bg-emerald-100 text-xs font-bold"
              >-</button>
              <input
                type="number"
                min={1}
                max={remaining}
                value={acceptQty ?? remaining}
                onChange={e => setAcceptQty(Math.max(1, Math.min(remaining, parseInt(e.target.value) || 1)))}
                className="w-9 text-center text-xs font-semibold bg-transparent outline-none text-emerald-800 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                data-testid={`accept-qty-${item.id}`}
              />
              <button
                onClick={() => setAcceptQty(Math.min(remaining, (acceptQty ?? remaining) + 1))}
                className="px-1.5 py-1 text-emerald-600 hover:bg-emerald-100 text-xs font-bold"
              >+</button>
            </div>
            <button
              onClick={handleAccept}
              disabled={completing === item.id}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 disabled:opacity-50 transition-colors flex items-center gap-1"
              data-testid={`accept-btn-${item.id}`}
            >
              <Check className="w-3.5 h-3.5" />
              {completing === item.id ? '...' : 'Прийняти'}
            </button>
          </div>
        ) : (
          <button
            onClick={() => onComplete(item.id, remaining)}
            disabled={completing === item.id}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 disabled:opacity-50 transition-colors flex items-center gap-1"
          >
            <Check className="w-3.5 h-3.5" />
            {completing === item.id ? 'Обробка...' : 'Готово'}
          </button>
        )}
      </div>
    </div>
  );
};

// ============= COLUMN =============
const QueueColumn = ({ title, icon: Icon, iconColor, queueType, items, loading, onComplete, onDelete, onPhotoClick, completing, searchQuery, onQuickAdd }) => {
  const [showAdd, setShowAdd] = useState(false);
  
  const filtered = searchQuery 
    ? items.filter(i => 
        (i.product_name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (i.sku || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (i.order_number || '').toLowerCase().includes(searchQuery.toLowerCase())
      )
    : items;
  
  const pendingCount = items.filter(i => i.processing_status === 'pending').length;
  const inProgressCount = items.filter(i => i.processing_status === 'in_progress').length;

  const openPrintList = () => {
    window.open(`${BACKEND_URL}/api/documents/processing-list/${queueType}/preview`, '_blank');
  };

  return (
    <div className="flex flex-col h-full min-w-0">
      {/* Header */}
      <div className="relative px-4 py-3 border-b border-slate-200 bg-white rounded-t-xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${iconColor}`}>
              <Icon className="w-4 h-4" />
            </div>
            <div>
              <div className="font-bold text-slate-800 text-sm">{title}</div>
              <div className="text-[11px] text-slate-500">
                {pendingCount > 0 && <span className="text-amber-600 font-medium">{pendingCount} очікує</span>}
                {pendingCount > 0 && inProgressCount > 0 && ' · '}
                {inProgressCount > 0 && <span className="text-blue-600 font-medium">{inProgressCount} в роботі</span>}
                {pendingCount === 0 && inProgressCount === 0 && <span>Порожньо</span>}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              onClick={openPrintList}
              disabled={items.length === 0}
              className="w-7 h-7 rounded-lg flex items-center justify-center bg-slate-100 hover:bg-slate-200 text-slate-600 transition disabled:opacity-30"
              title="Друк списку"
            >
              <Printer className="w-4 h-4" />
            </button>
            <button
              onClick={() => setShowAdd(!showAdd)}
              className="w-7 h-7 rounded-lg flex items-center justify-center bg-slate-100 hover:bg-slate-200 text-slate-600 transition"
              title="Додати по артикулу"
            >
              <Plus className="w-4 h-4" />
            </button>
            <span className="px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 text-xs font-bold">
              {filtered.length}
            </span>
          </div>
        </div>
        {showAdd && (
          <QuickAddPopover
            queueType={queueType}
            onAdd={async (data) => { await onQuickAdd(data); setShowAdd(false); }}
            onClose={() => setShowAdd(false)}
          />
        )}
      </div>
      
      {/* Items */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2 bg-slate-50/50">
        {loading ? (
          <div className="text-center py-12 text-slate-400 text-sm">Завантаження...</div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-12">
            <Icon className={`w-8 h-8 mx-auto mb-2 text-slate-300`} />
            <div className="text-slate-400 text-sm">
              {searchQuery ? 'Нічого не знайдено' : 'Черга порожня'}
            </div>
          </div>
        ) : (
          filtered.map(item => (
            <QueueItemCard
              key={item.id}
              item={item}
              onComplete={onComplete}
              onDelete={onDelete}
              onPhotoClick={onPhotoClick}
              completing={completing}
            />
          ))
        )}
      </div>
    </div>
  );
};

// ============= BATCH CARD =============
const BatchCard = ({ batch, onToggle, isOpen, onReturnItem }) => {
  const [returnQty, setReturnQty] = useState({});

  const statusColors = {
    sent: 'bg-blue-50 text-blue-700 border-blue-200',
    partial_return: 'bg-amber-50 text-amber-700 border-amber-200',
    returned: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    completed: 'bg-slate-50 text-slate-600 border-slate-200',
  };
  const statusLabels = {
    sent: 'Відправлено',
    partial_return: 'Часткове повернення',
    returned: 'Повернено',
    completed: 'Завершено',
  };

  const openBatchPrint = (e) => {
    e.stopPropagation();
    window.open(`${BACKEND_URL}/api/documents/laundry-batch/${batch.id}/preview`, '_blank');
  };

  const getRemaining = (item) => (item.quantity || 1) - (item.returned_quantity || 0);

  const handleAccept = (e, item) => {
    e.stopPropagation();
    const remaining = getRemaining(item);
    const qty = returnQty[item.id] ?? remaining;
    if (qty < 1 || qty > remaining) return;
    onReturnItem?.(batch.id, item, qty);
    setReturnQty(prev => { const n = { ...prev }; delete n[item.id]; return n; });
  };
  
  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
      <button onClick={onToggle} className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-slate-50 transition text-left">
        {isOpen ? <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" /> : <ChevronRight className="w-4 h-4 text-slate-400 flex-shrink-0" />}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm text-slate-800 truncate">{batch.batch_number}</span>
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${statusColors[batch.status] || statusColors.sent}`}>
              {statusLabels[batch.status] || batch.status}
            </span>
          </div>
          <div className="text-[11px] text-slate-500 flex gap-2">
            <span>{batch.laundry_company}</span>
            <span>·</span>
            <span>{fmtDate(batch.sent_date)}</span>
            <span>·</span>
            <span>{batch.returned_items || 0}/{batch.total_items} шт</span>
          </div>
        </div>
        <button
          onClick={openBatchPrint}
          className="w-7 h-7 rounded-lg flex items-center justify-center bg-slate-100 hover:bg-slate-200 text-slate-600 transition flex-shrink-0"
          title="Друк списку партії"
        >
          <Printer className="w-3.5 h-3.5" />
        </button>
      </button>
      {isOpen && batch.items?.length > 0 && (
        <div className="px-3 pb-3 space-y-1.5 border-t border-slate-100 pt-2">
          {batch.items.map(item => {
            const remaining = getRemaining(item);
            const isReturned = remaining <= 0;
            const currentQty = returnQty[item.id] ?? remaining;
            return (
              <div key={item.id} className={`flex items-center gap-2 py-1.5 px-2 rounded-lg text-xs ${isReturned ? 'bg-emerald-50/50' : 'hover:bg-slate-50'}`}>
                {item.product_image ? (
                  <img src={getPhotoUrl(item)} className="w-8 h-8 rounded-md object-cover border" alt="" onError={handleImageError} />
                ) : (
                  <div className="w-8 h-8 rounded-md bg-slate-100 flex items-center justify-center"><Package className="w-3 h-3 text-slate-400"/></div>
                )}
                <div className="flex-1 min-w-0">
                  <div className="truncate font-medium text-slate-700">{item.product_name}</div>
                  <div className="text-slate-500 font-mono">{item.sku} · {item.returned_quantity || 0}/{item.quantity} шт</div>
                </div>
                {!isReturned && (
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <div className="flex items-center border border-slate-200 rounded-lg overflow-hidden">
                      <button
                        onClick={(e) => { e.stopPropagation(); setReturnQty(prev => ({ ...prev, [item.id]: Math.max(1, (prev[item.id] ?? remaining) - 1) })); }}
                        className="px-1.5 py-0.5 text-slate-500 hover:bg-slate-100 text-xs font-bold"
                      >-</button>
                      <input
                        type="number"
                        min={1}
                        max={remaining}
                        value={currentQty}
                        onClick={e => e.stopPropagation()}
                        onChange={e => { const v = Math.max(1, Math.min(remaining, parseInt(e.target.value) || 1)); setReturnQty(prev => ({ ...prev, [item.id]: v })); }}
                        className="w-8 text-center text-xs font-medium bg-transparent outline-none [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                        data-testid={`batch-return-qty-${item.id}`}
                      />
                      <button
                        onClick={(e) => { e.stopPropagation(); setReturnQty(prev => ({ ...prev, [item.id]: Math.min(remaining, (prev[item.id] ?? remaining) + 1) })); }}
                        className="px-1.5 py-0.5 text-slate-500 hover:bg-slate-100 text-xs font-bold"
                      >+</button>
                    </div>
                    <button
                      onClick={(e) => handleAccept(e, item)}
                      className="px-2 py-1 rounded-lg text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 transition-colors"
                      title={`Прийняти ${currentQty} з ${remaining}`}
                      data-testid={`batch-accept-${item.id}`}
                    >
                      <Check className="w-3 h-3 inline mr-0.5" />
                      Прийняти
                    </button>
                  </div>
                )}
                {isReturned && (
                  <span className="px-2 py-1 text-[10px] font-semibold text-emerald-600 bg-emerald-100 rounded-full flex-shrink-0">Повернуто</span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

// ============= LAUNDRY COLUMN (з партіями) =============
const LaundryColumn = ({ items, loading, onComplete, onDelete, onPhotoClick, completing, searchQuery, batches, batchesLoading, onCreateBatch, onRefreshBatches, onQuickAdd, onReturnBatchItem }) => {
  const [tab, setTab] = useState('queue'); // queue | batches
  const [openBatch, setOpenBatch] = useState(null);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [showBatchForm, setShowBatchForm] = useState(false);
  const [batchCompany, setBatchCompany] = useState('');
  const [batchType, setBatchType] = useState('laundry');
  const [showAdd, setShowAdd] = useState(false);

  const filtered = searchQuery
    ? items.filter(i =>
        (i.product_name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (i.sku || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (i.order_number || '').toLowerCase().includes(searchQuery.toLowerCase())
      )
    : items;

  // Items not yet in a batch
  const queueItems = filtered.filter(i => !i.laundry_batch_id);
  const pendingCount = queueItems.length;
  const activeBatches = (batches || []).filter(b => b.status !== 'completed');

  const toggleSelect = (id) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const handleCreateBatch = async () => {
    if (selectedIds.size === 0 || !batchCompany.trim()) return;
    await onCreateBatch(Array.from(selectedIds), batchCompany, batchType);
    setSelectedIds(new Set());
    setShowBatchForm(false);
    setBatchCompany('');
  };

  return (
    <div className="flex flex-col h-full min-w-0">
      {/* Header */}
      <div className="relative px-4 py-3 border-b border-slate-200 bg-white rounded-t-xl">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-purple-100 text-purple-600">
              <Shirt className="w-4 h-4" />
            </div>
            <div>
              <div className="font-bold text-slate-800 text-sm">Пральня</div>
              <div className="text-[11px] text-slate-500">
                {pendingCount > 0 && <span className="text-amber-600 font-medium">{pendingCount} в черзі</span>}
                {activeBatches.length > 0 && pendingCount > 0 && ' · '}
                {activeBatches.length > 0 && <span className="text-purple-600 font-medium">{activeBatches.length} партій</span>}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => window.open(`${BACKEND_URL}/api/documents/processing-list/laundry/preview`, '_blank')}
              disabled={items.length === 0}
              className="w-7 h-7 rounded-lg flex items-center justify-center bg-slate-100 hover:bg-slate-200 text-slate-600 transition disabled:opacity-30"
              title="Друк списку пральні"
            >
              <Printer className="w-4 h-4" />
            </button>
            <button
              onClick={() => setShowAdd(!showAdd)}
              className="w-7 h-7 rounded-lg flex items-center justify-center bg-slate-100 hover:bg-slate-200 text-slate-600 transition"
              title="Додати по артикулу"
            >
              <Plus className="w-4 h-4" />
            </button>
            <span className="px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 text-xs font-bold">
              {items.length}
            </span>
          </div>
        </div>
        {showAdd && (
          <QuickAddPopover
            queueType="laundry"
            onAdd={async (data) => { await onQuickAdd(data); setShowAdd(false); }}
            onClose={() => setShowAdd(false)}
          />
        )}
        {/* Tabs */}
        <div className="flex gap-1 bg-slate-100 rounded-lg p-0.5">
          <button onClick={() => setTab('queue')} className={`flex-1 px-3 py-1.5 rounded-md text-xs font-medium transition ${tab === 'queue' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}>
            Черга ({queueItems.length})
          </button>
          <button onClick={() => setTab('batches')} className={`flex-1 px-3 py-1.5 rounded-md text-xs font-medium transition ${tab === 'batches' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}>
            Партії ({activeBatches.length})
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2 bg-slate-50/50">
        {loading || batchesLoading ? (
          <div className="text-center py-12 text-slate-400 text-sm">Завантаження...</div>
        ) : tab === 'queue' ? (
          <>
            {/* Batch creation toolbar */}
            {queueItems.length > 0 && (
              <div className="mb-2">
                {selectedIds.size > 0 && !showBatchForm && (
                  <button onClick={() => setShowBatchForm(true)} className="w-full px-3 py-2 rounded-lg text-xs font-medium bg-purple-50 text-purple-700 border border-purple-200 hover:bg-purple-100 flex items-center justify-center gap-1.5">
                    <Plus className="w-3.5 h-3.5" /> Сформувати партію ({selectedIds.size})
                  </button>
                )}
                {showBatchForm && (
                  <div className="p-3 rounded-xl border border-purple-200 bg-purple-50 space-y-2">
                    <input
                      type="text"
                      value={batchCompany}
                      onChange={e => setBatchCompany(e.target.value)}
                      placeholder="Назва пральні / хімчистки..."
                      className="w-full px-3 py-2 text-sm border rounded-lg"
                    />
                    <div className="flex gap-2">
                      <select value={batchType} onChange={e => setBatchType(e.target.value)} className="flex-1 px-2 py-1.5 text-xs border rounded-lg">
                        <option value="laundry">Хімчистка</option>
                        <option value="wash">Прання</option>
                      </select>
                      <button onClick={handleCreateBatch} disabled={!batchCompany.trim()} className="px-4 py-1.5 rounded-lg text-xs font-medium bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50">
                        Створити
                      </button>
                      <button onClick={() => setShowBatchForm(false)} className="px-3 py-1.5 rounded-lg text-xs border hover:bg-white">
                        Ні
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
            {queueItems.length === 0 ? (
              <div className="text-center py-12">
                <Shirt className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                <div className="text-slate-400 text-sm">{searchQuery ? 'Нічого не знайдено' : 'Черга порожня'}</div>
              </div>
            ) : (
              queueItems.map(item => (
                <div key={item.id} className="flex gap-2 items-start">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(item.id)}
                    onChange={() => toggleSelect(item.id)}
                    className="mt-4 w-4 h-4 rounded flex-shrink-0"
                  />
                  <div className="flex-1">
                    <QueueItemCard item={item} onComplete={onComplete} onDelete={onDelete} onPhotoClick={onPhotoClick} completing={completing} />
                  </div>
                </div>
              ))
            )}
          </>
        ) : (
          /* Batches tab */
          activeBatches.length === 0 ? (
            <div className="text-center py-12">
              <Package className="w-8 h-8 mx-auto mb-2 text-slate-300" />
              <div className="text-slate-400 text-sm">Немає активних партій</div>
            </div>
          ) : (
            activeBatches.map(batch => (
              <BatchCard key={batch.id} batch={batch} isOpen={openBatch === batch.id} onToggle={() => setOpenBatch(openBatch === batch.id ? null : batch.id)} onReturnItem={onReturnBatchItem} />
            ))
          )
        )}
      </div>
    </div>
  );
};

// ============= PHOTO MODAL =============
const PhotoModal = ({ isOpen, photoUrl, productName, onClose }) => {
  if (!isOpen || !photoUrl) return null;
  const fullUrl = getImageUrl(photoUrl);
  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4" onClick={onClose}>
      <button onClick={onClose} className="absolute top-4 right-4 p-2 bg-white/10 hover:bg-white/20 rounded-full text-white z-10">
        <X className="w-6 h-6" />
      </button>
      <img src={fullUrl} alt={productName || ''} className="max-w-full max-h-[90vh] object-contain rounded-lg shadow-2xl" onClick={e => e.stopPropagation()} />
    </div>
  );
};

// ============= MAIN =============
export default function DamageHubApp() {
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [completing, setCompleting] = useState(null);
  
  const [washItems, setWashItems] = useState([]);
  const [restoreItems, setRestoreItems] = useState([]);
  const [laundryItems, setLaundryItems] = useState([]);
  const [writtenOffItems, setWrittenOffItems] = useState([]);
  const [writtenOffStats, setWrittenOffStats] = useState({ total_items: 0, total_loss_amount: 0 });
  const [showWrittenOff, setShowWrittenOff] = useState(false);
  const [photoRecords, setPhotoRecords] = useState([]);
  const [showPhotoRecords, setShowPhotoRecords] = useState(false);
  const [batches, setBatches] = useState([]);
  const [batchesLoading, setBatchesLoading] = useState(false);
  
  const [photoModal, setPhotoModal] = useState({ isOpen: false, url: null, name: null });

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const results = await Promise.allSettled([
        authFetch(`${BACKEND_URL}/api/product-damage-history/processing/wash`).then(r => r.ok ? r.json() : { items: [] }),
        authFetch(`${BACKEND_URL}/api/product-damage-history/processing/restoration`).then(r => r.ok ? r.json() : { items: [] }),
        authFetch(`${BACKEND_URL}/api/product-damage-history/processing/laundry`).then(r => r.ok ? r.json() : { items: [] }),
        authFetch(`${BACKEND_URL}/api/product-damage-history/written-off`).then(r => r.ok ? r.json() : { items: [], total_items: 0, total_loss_amount: 0 }),
        authFetch(`${BACKEND_URL}/api/product-damage-history/photo-records`).then(r => r.ok ? r.json() : { items: [] }),
      ]);
      
      setWashItems(results[0].status === 'fulfilled' ? (results[0].value.items || []) : []);
      setRestoreItems(results[1].status === 'fulfilled' ? (results[1].value.items || []) : []);
      setLaundryItems(results[2].status === 'fulfilled' ? (results[2].value.items || []) : []);
      if (results[3].status === 'fulfilled') {
        setWrittenOffItems(results[3].value.items || []);
        setWrittenOffStats({ total_items: results[3].value.total_items || 0, total_loss_amount: results[3].value.total_loss_amount || 0 });
      }
      if (results[4].status === 'fulfilled') {
        setPhotoRecords(results[4].value.items || []);
      }
    } catch (e) {
      console.error("Load error:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadBatches = useCallback(async () => {
    setBatchesLoading(true);
    try {
      const res = await authFetch(`${BACKEND_URL}/api/laundry/batches`);
      if (res.ok) {
        const data = await res.json();
        setBatches(data || []);
      }
    } catch (e) {
      console.error("Batches load error:", e);
    } finally {
      setBatchesLoading(false);
    }
  }, []);

  useEffect(() => { loadAll(); loadBatches(); }, [loadAll, loadBatches]);

  const handleComplete = async (itemId, qty) => {
    setCompleting(itemId);
    try {
      const res = await authFetch(`${BACKEND_URL}/api/product-damage-history/${itemId}/return-to-stock`, {
        method: "POST",
        body: JSON.stringify({ notes: "Обробку завершено", return_qty: qty || null })
      });
      if (res.ok) {
        await loadAll();
      } else {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || 'Помилка завершення');
      }
    } catch (e) {
      console.error("Complete error:", e);
      alert('Помилка з\'єднання');
    } finally {
      setCompleting(null);
    }
  };

  const handleReturnBatchItem = async (batchId, item, qty) => {
    try {
      const res = await authFetch(`${BACKEND_URL}/api/laundry/batches/${batchId}/return-items`, {
        method: "POST",
        body: JSON.stringify([
          { item_id: String(item.id), returned_quantity: qty, condition_after: "clean" }
        ])
      });
      if (res.ok) {
        await Promise.all([loadAll(), loadBatches()]);
      } else {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || 'Помилка повернення');
      }
    } catch (e) {
      console.error("Batch return error:", e);
    }
  };


  const handleCreateBatch = async (itemIds, company, batchType) => {
    try {
      const user = JSON.parse(localStorage.getItem('user') || '{}');
      const res = await authFetch(`${BACKEND_URL}/api/laundry/queue/add-to-batch`, {
        method: "POST",
        body: JSON.stringify({
          item_ids: itemIds,
          laundry_company: company,
          batch_type: batchType,
          created_by: user.name || user.firstname || 'system'
        })
      });
      if (res.ok) {
        await Promise.all([loadAll(), loadBatches()]);
      }
    } catch (e) {
      console.error("Create batch error:", e);
    }
  };

  const openPhoto = (url, name) => setPhotoModal({ isOpen: true, url, name });

  const handleDelete = async (itemId) => {
    if (!confirm('Видалити цю позицію з черги?')) return;
    try {
      const user = JSON.parse(localStorage.getItem('user') || '{}');
      const res = await authFetch(`${BACKEND_URL}/api/product-damage-history/${itemId}`, {
        method: "DELETE",
        body: JSON.stringify({ deleted_by: user.name || 'system', reason: 'Видалено з кабінету шкоди' })
      });
      if (res.ok) await loadAll();
    } catch (e) { console.error("Delete error:", e); }
  };

  const handleQuickAdd = async (data) => {
    try {
      const res = await authFetch(`${BACKEND_URL}/api/product-damage-history/quick-add-to-queue`, {
        method: "POST",
        body: JSON.stringify(data)
      });
      if (res.ok) await loadAll();
    } catch (e) { console.error("Quick add error:", e); }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <CorporateHeader />
      
      {/* Toolbar */}
      <div className="sticky top-0 z-30 bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-[1600px] mx-auto px-3 sm:px-4 py-2.5 sm:py-3 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
          <div className="flex items-center justify-between">
            <h1 className="text-base sm:text-lg font-bold text-slate-800">Кабінет шкоди</h1>
            <button
              onClick={loadAll}
              disabled={loading}
              className="sm:hidden p-2 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-600 disabled:opacity-50 transition"
              title="Оновити"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
          
          <div className="flex items-center gap-2 sm:gap-3 flex-1 sm:max-w-md">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                placeholder="Пошук..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-4 py-2 text-sm border border-slate-200 rounded-xl bg-slate-50 focus:bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-300 transition"
                data-testid="damage-hub-search"
              />
            </div>
          </div>
          
          <button
            onClick={loadAll}
            disabled={loading}
            className="hidden sm:block p-2 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-600 disabled:opacity-50 transition"
            title="Оновити"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Three columns */}
      <div className="max-w-[1600px] mx-auto px-3 sm:px-4 py-3 sm:py-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4 lg:h-[calc(100vh-140px)]" data-testid="damage-hub-columns">
          {/* Мийка */}
          <div className="border border-slate-200 rounded-xl overflow-hidden bg-white flex flex-col h-[60vh] md:h-[70vh] lg:h-full" data-testid="wash-column">
            <QueueColumn
              title="Мийка"
              icon={Droplets}
              iconColor="bg-blue-100 text-blue-600"
              queueType="wash"
              items={washItems}
              loading={loading}
              onComplete={handleComplete}
              onDelete={handleDelete}
              onPhotoClick={openPhoto}
              completing={completing}
              searchQuery={searchQuery}
              onQuickAdd={handleQuickAdd}
            />
          </div>
          
          {/* Реставрація */}
          <div className="border border-slate-200 rounded-xl overflow-hidden bg-white flex flex-col h-[60vh] md:h-[70vh] lg:h-full" data-testid="restore-column">
            <QueueColumn
              title="Реставрація"
              icon={Wrench}
              iconColor="bg-orange-100 text-orange-600"
              queueType="restoration"
              items={restoreItems}
              loading={loading}
              onComplete={handleComplete}
              onDelete={handleDelete}
              onPhotoClick={openPhoto}
              completing={completing}
              searchQuery={searchQuery}
              onQuickAdd={handleQuickAdd}
            />
          </div>
          
          {/* Пральня */}
          <div className="border border-slate-200 rounded-xl overflow-hidden bg-white flex flex-col h-[60vh] md:h-[70vh] lg:h-full" data-testid="laundry-column">
            <LaundryColumn
              items={laundryItems}
              loading={loading}
              onComplete={handleComplete}
              onDelete={handleDelete}
              onPhotoClick={openPhoto}
              completing={completing}
              searchQuery={searchQuery}
              batches={batches}
              batchesLoading={batchesLoading}
              onCreateBatch={handleCreateBatch}
              onRefreshBatches={loadBatches}
              onQuickAdd={handleQuickAdd}
              onReturnBatchItem={handleReturnBatchItem}
            />
          </div>
        </div>
      </div>

      {/* Photo Records Section (Фіксації) */}
      <div className="max-w-[1600px] mx-auto px-3 sm:px-4 pb-3">
        <button 
          onClick={() => setShowPhotoRecords(!showPhotoRecords)}
          className="w-full flex items-center justify-between p-3 bg-blue-50 border border-blue-200 rounded-xl hover:bg-blue-100 transition"
          data-testid="photo-records-toggle"
        >
          <div className="flex items-center gap-3">
            <div className="p-1.5 bg-blue-100 rounded-lg"><Camera className="w-4 h-4 text-blue-600" /></div>
            <span className="font-bold text-sm text-blue-800">Фіксації (фото до видачі / при поверненні)</span>
            <span className="px-2 py-0.5 bg-blue-200 text-blue-800 rounded-full text-xs font-bold">{photoRecords.length}</span>
          </div>
          <ChevronDown className={`w-4 h-4 text-blue-400 transition-transform ${showPhotoRecords ? 'rotate-180' : ''}`} />
        </button>
        
        {showPhotoRecords && (
          <div className="mt-2 border border-blue-200 rounded-xl overflow-hidden bg-white">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-blue-50 border-b border-blue-200">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-blue-700">Фото</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-blue-700">Артикул</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-blue-700">Назва</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-blue-700">Замовлення</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-blue-700">Етап</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-blue-700">Фото фіксації</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-blue-700">Коментар</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-blue-700">Хто / Коли</th>
                    <th className="px-3 py-2 text-center text-xs font-semibold text-blue-700"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {photoRecords.filter(item => {
                    if (!searchQuery) return true;
                    const q = searchQuery.toLowerCase();
                    return (item.sku || '').toLowerCase().includes(q) || (item.product_name || '').toLowerCase().includes(q) || (item.order_number || '').toLowerCase().includes(q);
                  }).map(item => (
                    <tr key={item.id} className="hover:bg-blue-50/50">
                      <td className="px-3 py-2">
                        <div className="w-10 h-10 rounded-lg overflow-hidden bg-slate-100">
                          {item.product_image ? <img src={getImageUrl(item.product_image)} alt="" className="w-full h-full object-cover" onError={handleImageError} /> : <span className="flex items-center justify-center w-full h-full text-slate-400 text-xs">—</span>}
                        </div>
                      </td>
                      <td className="px-3 py-2 font-mono text-xs font-bold text-slate-700">{item.sku}</td>
                      <td className="px-3 py-2 text-slate-800 text-xs max-w-[160px] truncate">{item.product_name}</td>
                      <td className="px-3 py-2 text-xs text-slate-600">{item.order_number || '—'}</td>
                      <td className="px-3 py-2">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          item.stage === 'pre_issue' ? 'bg-amber-100 text-amber-800' : 
                          item.stage === 'return' ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'
                        }`}>
                          {item.stage === 'pre_issue' ? 'До видачі' : item.stage === 'return' ? 'Повернення' : item.stage || '—'}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        {item.photo_url ? (
                          <div className="w-10 h-10 rounded-lg overflow-hidden bg-slate-100 cursor-pointer border-2 border-blue-200 hover:border-blue-400 transition"
                            onClick={() => openPhoto(item.photo_url, item.product_name)}>
                            <img src={getImageUrl(item.photo_url)} alt="" className="w-full h-full object-cover" onError={handleImageError} />
                          </div>
                        ) : <span className="text-slate-400 text-xs">—</span>}
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-600 max-w-[180px] truncate">{item.note || '—'}</td>
                      <td className="px-3 py-2 text-xs text-slate-500">
                        <div>{item.created_by || '—'}</div>
                        <div>{fmtTime(item.created_at)}</div>
                      </td>
                      <td className="px-3 py-2 text-center">
                        <button
                          onClick={async () => {
                            if (!window.confirm(`Видалити фіксацію ${item.sku}?`)) return;
                            try {
                              await authFetch(`${BACKEND_URL}/api/product-damage-history/photo-records/${item.id}`, { method: 'DELETE' });
                              setPhotoRecords(prev => prev.filter(r => r.id !== item.id));
                            } catch {}
                          }}
                          className="p-1.5 rounded-lg hover:bg-red-100 text-slate-400 hover:text-red-600 transition"
                          title="Видалити"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                  {photoRecords.length === 0 && (
                    <tr><td colSpan={9} className="px-3 py-8 text-center text-slate-400 text-sm">Немає фіксацій</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Written Off Section */}
      <div className="max-w-[1600px] mx-auto px-3 sm:px-4 pb-6">
        <button 
          onClick={() => setShowWrittenOff(!showWrittenOff)}
          className="w-full flex items-center justify-between p-3 bg-red-50 border border-red-200 rounded-xl hover:bg-red-100 transition"
          data-testid="written-off-toggle"
        >
          <div className="flex items-center gap-3">
            <div className="p-1.5 bg-red-100 rounded-lg"><X className="w-4 h-4 text-red-600" /></div>
            <span className="font-bold text-sm text-red-800">Списані</span>
            <span className="px-2 py-0.5 bg-red-200 text-red-800 rounded-full text-xs font-bold">{writtenOffItems.length}</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-red-600">{writtenOffStats.total_items} шт / ₴{writtenOffStats.total_loss_amount.toLocaleString('uk-UA')}</span>
            <ChevronDown className={`w-4 h-4 text-red-400 transition-transform ${showWrittenOff ? 'rotate-180' : ''}`} />
          </div>
        </button>
        
        {showWrittenOff && (
          <div className="mt-2 border border-red-200 rounded-xl overflow-hidden bg-white">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-red-50 border-b border-red-200">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-red-700">Фото</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-red-700">Артикул</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-red-700">Назва</th>
                    <th className="px-3 py-2 text-center text-xs font-semibold text-red-700">К-сть</th>
                    <th className="px-3 py-2 text-right text-xs font-semibold text-red-700">Сума</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-red-700">Фото шкоди</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-red-700">Коментар</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-red-700">Хто / Коли / Звідки</th>
                    <th className="px-3 py-2 text-center text-xs font-semibold text-red-700 w-10"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {writtenOffItems.filter(item => {
                    if (!searchQuery) return true;
                    const q = searchQuery.toLowerCase();
                    return (item.sku || '').toLowerCase().includes(q) || (item.product_name || '').toLowerCase().includes(q);
                  }).map(item => (
                    <tr key={item.id} className="hover:bg-red-50/50">
                      <td className="px-3 py-2">
                        <div className="w-10 h-10 rounded-lg overflow-hidden bg-slate-100 flex-shrink-0">
                          <img src={getImageUrl(item.product_image)} alt="" className="w-full h-full object-cover" onError={handleImageError} />
                        </div>
                      </td>
                      <td className="px-3 py-2 font-mono text-xs font-bold text-slate-700">{item.sku}</td>
                      <td className="px-3 py-2 text-slate-800 text-xs max-w-[200px] truncate">{item.product_name}</td>
                      <td className="px-3 py-2 text-center font-bold text-red-700">{item.qty}</td>
                      <td className="px-3 py-2 text-right font-bold text-red-700">₴{(item.fee || 0).toLocaleString('uk-UA')}</td>
                      <td className="px-3 py-2">
                        {item.photo_url ? (
                          <div className="w-10 h-10 rounded-lg overflow-hidden bg-slate-100 cursor-pointer border-2 border-red-200 hover:border-red-400 transition"
                            onClick={() => openPhoto(item.photo_url, item.product_name)}>
                            <img src={getImageUrl(item.photo_url)} alt="damage" className="w-full h-full object-cover" onError={handleImageError} />
                          </div>
                        ) : <span className="text-slate-400 text-xs">—</span>}
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-600 max-w-[200px] truncate">{item.note || '—'}</td>
                      <td className="px-3 py-2 text-xs text-slate-500">
                        <div>{item.created_by || '—'}</div>
                        <div>{fmtTime(item.created_at)}</div>
                        <div className="text-[10px]">
                          {item.source === 'return' || item.stage === 'return' ? (
                            <span className="text-emerald-600 font-medium">Повернення {item.order_number ? `• ${item.order_number}` : ''}</span>
                          ) : item.source === 'reaudit' || item.stage === 'reaudit' ? (
                            <span className="text-blue-500">Переоблік</span>
                          ) : item.order_number ? (
                            <span className="text-slate-400">{item.order_number}</span>
                          ) : (
                            <span className="text-slate-400">—</span>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-2 text-center">
                        <button
                          data-testid={`delete-written-off-${item.id}`}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                          title="Видалити запис"
                          onClick={async () => {
                            if (!window.confirm(`Видалити запис списання "${item.product_name}"?`)) return;
                            try {
                              const res = await authFetch(`${BACKEND_URL}/api/product-damage-history/${item.id}`, { method: 'DELETE' });
                              if (res.ok) {
                                setWrittenOffItems(prev => prev.filter(i => i.id !== item.id));
                                setWrittenOffStats(prev => ({
                                  total_items: prev.total_items - (item.qty || 1),
                                  total_loss_amount: prev.total_loss_amount - (item.fee || 0)
                                }));
                              }
                            } catch (e) { console.error('Delete error:', e); }
                          }}
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                  {writtenOffItems.length === 0 && (
                    <tr><td colSpan={8} className="px-3 py-8 text-center text-slate-400 text-sm">Немає списаних позицій</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Photo Modal */}
      <PhotoModal
        isOpen={photoModal.isOpen}
        photoUrl={photoModal.url}
        productName={photoModal.name}
        onClose={() => setPhotoModal({ isOpen: false, url: null, name: null })}
      />
    </div>
  );
}
