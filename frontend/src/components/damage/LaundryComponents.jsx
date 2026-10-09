/* eslint-disable */
/**
 * Laundry Components - Хімчистка tab components
 */
import React, { useState } from "react";
import { cls, money, fmtDate, Badge, GhostBtn, PrimaryBtn, ProductPhoto } from "./DamageHelpers";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

// ----------------------------- Laundry Queue Item -----------------------------
export function LaundryQueueItem({ item, selected, onSelect, onAddToBatch }) {
  return (
    <div className={cls(
      "rounded-xl border bg-white p-3 transition",
      selected && "ring-2 ring-corp-primary border-corp-primary"
    )}>
      <div className="flex items-start gap-3">
        <input
          type="checkbox"
          checked={selected}
          onChange={onSelect}
          className="mt-1 h-4 w-4 rounded border-gray-300"
        />
        <ProductPhoto item={item} size="sm" />
        <div className="min-w-0 flex-1">
          <div className="font-semibold text-corp-text-dark truncate">{item.product_name}</div>
          <div className="mt-0.5 text-xs text-corp-text-muted">
            SKU: {item.sku} • {item.order_number || "—"}
          </div>
          <div className="mt-0.5 text-xs text-corp-text-muted">
            {item.condition_before || "dirty"}
          </div>
        </div>
        <Badge tone="warn">Черга</Badge>
      </div>
      <div className="mt-2 flex gap-2">
        <button
          onClick={() => onAddToBatch(item)}
          className="text-xs px-2 py-1 rounded-lg bg-blue-100 text-blue-800 hover:bg-blue-200"
        >
          + В партію
        </button>
      </div>
    </div>
  );
}

// ----------------------------- Laundry Batch Card -----------------------------
export function LaundryBatchCard({ batch, active, onClick }) {
  const statusMap = {
    sent: { label: "Відправлено", tone: "info" },
    partial_return: { label: "Часткове", tone: "warn" },
    returned: { label: "Повернуто", tone: "ok" },
    completed: { label: "✓ Закрито", tone: "ok" },
  };
  const s = statusMap[batch.status] || { label: batch.status, tone: "neutral" };
  const progress = batch.total_items > 0 ? (batch.returned_items / batch.total_items) * 100 : 0;

  return (
    <button
      onClick={onClick}
      className={cls(
        "w-full rounded-2xl border bg-white p-4 text-left shadow-sm hover:shadow transition",
        active && "ring-2 ring-corp-primary/30 border-corp-primary/30"
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="font-bold text-corp-text-dark">{batch.batch_number || batch.id}</div>
          <div className="mt-1 text-sm text-corp-text-muted">{batch.laundry_company}</div>
        </div>
        <Badge tone={s.tone}>{s.label}</Badge>
      </div>
      
      <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
        <div>
          <span className="text-corp-text-muted">Відправлено:</span>{" "}
          <span className="font-medium">{fmtDate(batch.sent_date)}</span>
        </div>
        <div>
          <span className="text-corp-text-muted">Очікується:</span>{" "}
          <span className="font-medium">{fmtDate(batch.expected_return_date)}</span>
        </div>
      </div>
      
      {/* Progress */}
      <div className="mt-3">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-corp-text-muted">Прийнято</span>
          <span className="font-medium">{batch.returned_items} / {batch.total_items}</span>
        </div>
        <div className="h-2 rounded-full bg-corp-border">
          <div 
            className={cls("h-full rounded-full transition-all", progress >= 100 ? "bg-emerald-500" : "bg-blue-500")}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
      
      {batch.cost > 0 && (
        <div className="mt-2 text-sm">
          <span className="text-corp-text-muted">Вартість:</span>{" "}
          <span className="font-bold">{money(batch.cost)}</span>
        </div>
      )}
    </button>
  );
}

// ----------------------------- Laundry Batch Detail Panel -----------------------------
export function LaundryBatchDetailPanel({ batch, items, onReceiveItems, onCloseBatch, onRefresh }) {
  const [selectedItems, setSelectedItems] = useState([]);
  
  if (!batch) {
    return (
      <div className="rounded-2xl border border-corp-border bg-white p-10 text-center text-corp-text-muted shadow-sm">
        ← Оберіть партію зі списку
      </div>
    );
  }

  const hasItems = items && items.length > 0;
  const allReturned = hasItems && items.every(i => (i.returned_quantity || 0) >= i.quantity);
  const isCompleted = batch.status === 'completed';
  const progress = batch.total_items > 0 ? (batch.returned_items / batch.total_items) * 100 : 0;

  const toggleItem = (itemId) => {
    setSelectedItems(prev => 
      prev.includes(itemId) ? prev.filter(id => id !== itemId) : [...prev, itemId]
    );
  };

  const selectAllUnreturned = () => {
    const unreturned = items.filter(i => (i.returned_quantity || 0) < i.quantity).map(i => i.id);
    setSelectedItems(unreturned);
  };

  const handleReceive = () => {
    if (selectedItems.length === 0) return;
    onReceiveItems(batch.batch_number || batch.id, selectedItems);
    setSelectedItems([]);
  };

  return (
    <div className="rounded-2xl border border-corp-border bg-white shadow-sm overflow-hidden">
      {/* Header */}
      <div className="p-5 bg-gradient-to-r from-emerald-50 to-white border-b border-corp-border">
        <div className="flex items-start justify-between">
          <div>
            <div className="text-xl font-bold text-corp-text-dark">{batch.batch_number || batch.id}</div>
            <div className="mt-1 text-sm text-corp-text-muted">{batch.laundry_company}</div>
          </div>
          <Badge tone={isCompleted ? "ok" : progress >= 100 ? "ok" : "info"}>
            {isCompleted ? "✓ Закрито" : progress >= 100 ? "Повернуто" : `${Math.round(progress)}%`}
          </Badge>
        </div>
        
        {/* Progress bar */}
        <div className="mt-4">
          <div className="flex justify-between text-sm mb-1">
            <span className="text-corp-text-muted">Прийнято товарів</span>
            <span className="font-bold">{batch.returned_items} / {batch.total_items}</span>
          </div>
          <div className="h-3 rounded-full bg-corp-border">
            <div 
              className={cls("h-full rounded-full transition-all", progress >= 100 ? "bg-emerald-500" : "bg-blue-500")}
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>

      {/* Batch info */}
      <div className="p-5 border-b border-corp-border grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
        <div>
          <div className="text-corp-text-muted">Відправлено</div>
          <div className="font-medium">{fmtDate(batch.sent_date)}</div>
        </div>
        <div>
          <div className="text-corp-text-muted">Очікується</div>
          <div className="font-medium">{fmtDate(batch.expected_return_date)}</div>
        </div>
        <div>
          <div className="text-corp-text-muted">Вартість</div>
          <div className="font-bold">{money(batch.cost)}</div>
        </div>
        <div>
          <div className="text-corp-text-muted">Статус</div>
          <div className="font-medium">{batch.status}</div>
        </div>
      </div>

      {/* Items list */}
      <div className="p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="font-semibold">Товари партії</div>
          {!isCompleted && !allReturned && (
            <button
              onClick={selectAllUnreturned}
              className="text-xs px-2 py-1 rounded-lg bg-slate-100 hover:bg-slate-200"
            >
              ✓ Вибрати всі неприйняті
            </button>
          )}
        </div>
        
        <div className="space-y-2 max-h-[300px] overflow-y-auto">
          {items.map(item => {
            const isFullyReturned = (item.returned_quantity || 0) >= item.quantity;
            const isSelected = selectedItems.includes(item.id);
            
            return (
              <div 
                key={item.id}
                className={cls(
                  "rounded-xl border p-3 transition",
                  isFullyReturned ? "bg-emerald-50 border-emerald-200" : 
                  isSelected ? "bg-blue-50 border-blue-300 ring-2 ring-blue-200" : "bg-white"
                )}
              >
                <div className="flex items-center gap-3">
                  {!isCompleted && !isFullyReturned && (
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleItem(item.id)}
                      className="h-4 w-4 rounded border-gray-300"
                    />
                  )}
                  {isFullyReturned && (
                    <span className="text-emerald-500 text-lg">✓</span>
                  )}
                  <ProductPhoto item={item} size="sm" />
                  <div className="min-w-0 flex-1">
                    <div className="font-medium truncate">{item.product_name}</div>
                    <div className="text-xs text-corp-text-muted">
                      SKU: {item.sku} • {item.condition_before || "—"} → {item.condition_after || "—"}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-medium">
                      {item.returned_quantity || 0} / {item.quantity}
                    </div>
                    <div className="text-xs text-corp-text-muted">прийнято</div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Actions */}
      {!isCompleted && (
        <div className="p-5 bg-corp-bg-page">
          <div className="flex flex-wrap gap-2">
            {!allReturned && items.length > 0 && (
              <PrimaryBtn variant="blue" onClick={handleReceive} disabled={selectedItems.length === 0}>
                📥 Прийняти вибрані ({selectedItems.length})
              </PrimaryBtn>
            )}
            {allReturned && hasItems && (
              <PrimaryBtn variant="success" onClick={() => onCloseBatch(batch)}>
                ✓ Закрити партію
              </PrimaryBtn>
            )}
            {!hasItems && (
              <div className="text-sm text-amber-600">
                ⚠️ Партія не має товарів
              </div>
            )}
            <GhostBtn onClick={onRefresh}>🔄 Оновити</GhostBtn>
          </div>
          
          {!allReturned && items.length > 0 && (
            <div className="mt-3 text-sm text-corp-text-muted">
              💡 Виберіть товари які повернулись з хімчистки та натисніть "Прийняти"
            </div>
          )}
        </div>
      )}

      {/* Completed state */}
      {isCompleted && (
        <div className="p-5 bg-emerald-50">
          <div className="flex items-center gap-2 text-emerald-700">
            <span className="text-2xl">✓</span>
            <div>
              <div className="font-semibold">Партію закрито</div>
              <div className="text-sm">Всі товари прийняті та доступні для оренди</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
