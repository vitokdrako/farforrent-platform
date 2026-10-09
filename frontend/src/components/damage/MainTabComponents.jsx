/* eslint-disable */
/**
 * Main Tab Components - Головна tab components
 */
import React, { useState, useEffect } from "react";
import { cls, money, fmtDate, authFetch, getPhotoUrl, Badge, GhostBtn, PrimaryBtn, ProductPhoto } from "./DamageHelpers";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

// ----------------------------- Order Case Row -----------------------------
export function OrderCaseRow({ caseData, active, onClick }) {
  const isPaid = caseData.is_paid;
  const hasPending = (caseData.pending_assignment || 0) > 0;
  
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
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-corp-text-dark">#{caseData.order_number}</span>
            {isPaid ? (
              <Badge tone="ok">✓ Сплачено</Badge>
            ) : (
              <Badge tone="danger">⏳ Очікує оплати</Badge>
            )}
          </div>
          <div className="mt-1 text-sm text-corp-text-main">{caseData.customer_name || "—"}</div>
          <div className="mt-1 text-xs text-corp-text-muted">
            {caseData.items_count} позиц. • {fmtDate(caseData.latest_damage)}
          </div>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <div className="text-lg font-bold text-corp-text-dark">{money(caseData.total_fee)}</div>
          {hasPending && (
            <Badge tone="warn">⚡ {caseData.pending_assignment} не розподілено</Badge>
          )}
        </div>
      </div>
      {!isPaid && caseData.damage_paid > 0 && (
        <div className="mt-3">
          <div className="flex justify-between text-xs text-corp-text-muted mb-1">
            <span>Сплачено: {money(caseData.damage_paid)}</span>
            <span>Залишок: {money(caseData.damage_due)}</span>
          </div>
          <div className="h-1.5 rounded-full bg-corp-border">
            <div 
              className="h-full rounded-full bg-emerald-500 transition-all"
              style={{ width: `${Math.min(100, (caseData.damage_paid / caseData.total_fee) * 100)}%` }}
            />
          </div>
        </div>
      )}
    </button>
  );
}

// ----------------------------- Damage Item Row -----------------------------
export function DamageItemRow({ item, onSendTo }) {
  const getProcessingBadge = () => {
    const type = item.processing_type;
    if (!type || type === 'none') return null;
    const map = {
      wash: { label: "🧼 Мийка", tone: "info" },
      restoration: { label: "🔧 Реставрація", tone: "warn" },
      laundry: { label: "🧺 Хімчистка", tone: "neutral" },
    };
    return map[type] || null;
  };

  const getStatusBadge = () => {
    const status = item.processing_status;
    const map = {
      pending: { label: "Очікує", tone: "warn" },
      in_progress: { label: "В роботі", tone: "info" },
      completed: { label: "✓ Готово", tone: "ok" },
    };
    return map[status] || null;
  };

  const processingBadge = getProcessingBadge();
  const statusBadge = getStatusBadge();
  const isTotalLoss = item.severity === 'total_loss' || item.severity === 'write_off';

  return (
    <div className={cls(
      "rounded-xl border p-3 bg-white",
      isTotalLoss && "border-red-200 bg-red-50"
    )}>
      <div className="flex items-start gap-3">
        <ProductPhoto item={item} size="md" className={isTotalLoss ? "grayscale" : ""} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-corp-text-dark">{item.product_name}</span>
            {processingBadge && <Badge tone={processingBadge.tone}>{processingBadge.label}</Badge>}
            {statusBadge && <Badge tone={statusBadge.tone}>{statusBadge.label}</Badge>}
            {isTotalLoss && <Badge tone="danger">💀 Списано</Badge>}
          </div>
          <div className="mt-1 text-xs text-corp-text-muted">
            SKU: {item.sku} • {item.damage_type || "—"}
          </div>
          {item.notes && (
            <div className="mt-1 text-xs text-corp-text-muted italic">"{item.notes}"</div>
          )}
        </div>
        <div className="text-right flex flex-col gap-1">
          <div className="text-lg font-bold">{money(item.compensation)}</div>
          {!processingBadge && !isTotalLoss && (
            <div className="flex gap-1">
              <button
                onClick={() => onSendTo(item.id, 'wash')}
                className="text-xs px-2 py-1 rounded bg-blue-100 text-blue-800 hover:bg-blue-200"
                title="Відправити на мийку"
              >
                🧼
              </button>
              <button
                onClick={() => onSendTo(item.id, 'restoration')}
                className="text-xs px-2 py-1 rounded bg-amber-100 text-amber-800 hover:bg-amber-200"
                title="Відправити на реставрацію"
              >
                🔧
              </button>
              <button
                onClick={() => onSendTo(item.id, 'laundry')}
                className="text-xs px-2 py-1 rounded bg-emerald-100 text-emerald-800 hover:bg-emerald-200"
                title="Відправити в хімчистку"
              >
                🧺
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ----------------------------- Order Detail Panel -----------------------------
export function OrderDetailPanel({ orderCase, items, loading, onSendTo, onRefresh, onDeductFromDeposit }) {
  if (!orderCase) {
    return (
      <div className="rounded-2xl border border-corp-border bg-white p-10 text-center text-corp-text-muted shadow-sm">
        ← Оберіть замовлення зі списку
      </div>
    );
  }

  const pendingCount = items.filter(i => !i.processing_type || i.processing_type === 'none').length;
  const assignedCount = items.filter(i => i.processing_type && i.processing_type !== 'none').length;

  return (
    <div className="rounded-2xl border border-corp-border bg-white shadow-sm overflow-hidden">
      {/* Header */}
      <div className="p-5 bg-gradient-to-r from-slate-100 to-white border-b border-corp-border">
        <div className="flex items-start justify-between">
          <div>
            <div className="text-xl font-bold text-corp-text-dark">#{orderCase.order_number}</div>
            <div className="mt-1 text-sm text-corp-text-main">{orderCase.customer_name}</div>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-corp-text-dark">{money(orderCase.total_fee)}</div>
            {orderCase.is_paid ? (
              <Badge tone="ok">✓ Оплачено</Badge>
            ) : (
              <Badge tone="danger">Очікує: {money(orderCase.damage_due)}</Badge>
            )}
          </div>
        </div>

        {/* Stats row */}
        <div className="mt-4 flex flex-wrap gap-3">
          <div className="px-3 py-2 rounded-xl bg-white border border-corp-border">
            <div className="text-xs text-corp-text-muted">Всього позицій</div>
            <div className="font-bold">{items.length}</div>
          </div>
          <div className="px-3 py-2 rounded-xl bg-amber-50 border border-amber-200">
            <div className="text-xs text-amber-800">Не розподілено</div>
            <div className="font-bold text-amber-800">{pendingCount}</div>
          </div>
          <div className="px-3 py-2 rounded-xl bg-blue-50 border border-blue-200">
            <div className="text-xs text-blue-800">На обробці</div>
            <div className="font-bold text-blue-800">{assignedCount}</div>
          </div>
        </div>

        {/* Deposit deduct button */}
        {orderCase.deposit_available > 0 && orderCase.damage_due > 0 && (
          <div className="mt-4 p-3 rounded-xl bg-rose-50 border border-rose-200">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-rose-800">Застава клієнта: {money(orderCase.deposit_available)}</div>
                <div className="text-xs text-rose-600">Можна списати на компенсацію шкоди</div>
              </div>
              <PrimaryBtn variant="danger" onClick={() => onDeductFromDeposit(orderCase)}>
                Вирахувати із застави
              </PrimaryBtn>
            </div>
          </div>
        )}
      </div>

      {/* Items list */}
      <div className="p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="font-semibold">Пошкодження</div>
          <GhostBtn onClick={onRefresh}>🔄</GhostBtn>
        </div>

        {loading ? (
          <div className="text-center py-8 text-corp-text-muted">Завантаження...</div>
        ) : items.length === 0 ? (
          <div className="text-center py-8 text-corp-text-muted">Немає записів про пошкодження</div>
        ) : (
          <div className="space-y-2 max-h-[400px] overflow-y-auto">
            {items.map(item => (
              <DamageItemRow key={item.id} item={item} onSendTo={onSendTo} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
