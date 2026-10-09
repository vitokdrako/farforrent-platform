/* eslint-disable */
/**
 * Processing Components - Мийка/Реставрація tab components
 */
import React, { useState, useEffect } from "react";
import { cls, money, fmtDate, authFetch, getPhotoUrl, Badge, GhostBtn, PrimaryBtn, ProductPhoto, STATUS_FILTERS } from "./DamageHelpers";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

// ----------------------------- Status Chips -----------------------------
export function StatusChips({ value, onChange, counts = {}, labels = {} }) {
  // Порядок: Потребують уваги -> В обробці -> Закриті -> Всі
  const statuses = ["pending", "in_progress", "completed", "all"];
  const icons = { all: "📋", pending: "⏳", in_progress: "🔄", completed: "✅" };
  const tones = { all: "neutral", pending: "warn", in_progress: "info", completed: "ok" };
  
  return (
    <div className="flex flex-wrap gap-2">
      {statuses.map(s => (
        <button
          key={s}
          onClick={() => onChange(s)}
          className={cls(
            "flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-sm font-medium border transition",
            value === s 
              ? "bg-corp-primary/10 text-corp-primary border-corp-primary/30" 
              : "bg-white text-corp-text-muted border-corp-border hover:border-corp-primary/30"
          )}
        >
          <span>{icons[s]}</span>
          <span>{labels[s] || STATUS_FILTERS[s]}</span>
          {counts[s] > 0 && (
            <span className={cls(
              "ml-1 text-xs px-1.5 py-0.5 rounded-full",
              value === s ? "bg-corp-primary text-white" : "bg-corp-bg-light"
            )}>
              {counts[s]}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

// ----------------------------- Processing Item Row -----------------------------
export function ProcessingItemRow({ item, active, onClick }) {
  const totalQty = item.qty || 1;
  const processedQty = item.processed_qty || 0;
  const remainingQty = Math.max(0, totalQty - processedQty);
  const progress = totalQty > 0 ? (processedQty / totalQty) * 100 : 0;
  const isCompleted = progress >= 100;

  const statusMap = {
    pending: { label: "Очікує", tone: "warn" },
    in_progress: { label: "В роботі", tone: "info" },
    completed: { label: "✓ Готово", tone: "ok" },
  };
  const st = statusMap[item.processing_status] || { label: item.processing_status, tone: "neutral" };

  return (
    <button
      onClick={onClick}
      className={cls(
        "w-full rounded-2xl border bg-white p-4 text-left shadow-sm hover:shadow transition",
        active && "ring-2 ring-corp-primary/30 border-corp-primary/30"
      )}
    >
      <div className="flex items-start gap-3">
        <ProductPhoto item={item} size="md" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-corp-text-dark truncate">{item.product_name}</span>
            <Badge tone={st.tone}>{st.label}</Badge>
          </div>
          <div className="mt-1 text-xs text-corp-text-muted">
            SKU: {item.sku} • #{item.order_number || "—"}
          </div>
          <div className="mt-1 text-sm">
            <span className="text-corp-text-muted">Пошкодження:</span>{" "}
            <span className="font-medium">{item.damage_type || "—"}</span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-lg font-bold">{remainingQty}/{totalQty}</div>
          <div className="text-xs text-corp-text-muted">залишилось</div>
        </div>
      </div>
      
      {/* Progress bar */}
      {totalQty > 1 && (
        <div className="mt-3">
          <div className="h-2 rounded-full bg-corp-border">
            <div 
              className={cls("h-full rounded-full transition-all", isCompleted ? "bg-emerald-500" : "bg-blue-500")}
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}
    </button>
  );
}

// ----------------------------- Processing Detail Panel -----------------------------
export function ProcessingDetailPanel({ mode, item, onComplete, onMarkFailed, onRefresh }) {
  const [notes, setNotes] = useState("");
  const [completedQty, setCompletedQty] = useState(1);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (item) {
      const remaining = (item.qty || 1) - (item.processed_qty || 0);
      setCompletedQty(Math.min(remaining, 1));
      setNotes("");
    }
  }, [item?.id]);

  if (!item) {
    return (
      <div className="rounded-2xl border border-corp-border bg-white p-10 text-center text-corp-text-muted shadow-sm">
        ← Оберіть товар зі списку
      </div>
    );
  }

  const totalQty = item.qty || 1;
  const processedQty = item.processed_qty || 0;
  const remainingQty = Math.max(0, totalQty - processedQty);
  const progress = totalQty > 0 ? (processedQty / totalQty) * 100 : 0;
  const isFullyCompleted = progress >= 100;

  const handleComplete = async () => {
    if (completedQty < 1 || completedQty > remainingQty) return;
    setSaving(true);
    try {
      await onComplete(item.id, completedQty, notes);
    } finally {
      setSaving(false);
    }
  };

  const modeLabels = {
    wash: { title: "Мийка", action: "Помито", icon: "🧼" },
    restore: { title: "Реставрація", action: "Відреставровано", icon: "🔧" },
  };
  const ml = modeLabels[mode] || { title: "Обробка", action: "Оброблено", icon: "📦" };

  return (
    <div className="rounded-2xl border border-corp-border bg-white shadow-sm overflow-hidden">
      {/* Header with photo */}
      <div className="p-5 bg-gradient-to-r from-corp-bg-light to-white border-b border-corp-border">
        <div className="flex items-start gap-4">
          <ProductPhoto item={item} size="lg" />
          <div className="flex-1 min-w-0">
            <div className="text-xl font-bold text-corp-text-dark">{item.product_name}</div>
            <div className="mt-1 text-sm text-corp-text-muted">SKU: {item.sku}</div>
            <div className="mt-2 flex flex-wrap gap-2">
              <Badge tone="neutral">#{item.order_number || "—"}</Badge>
              <Badge tone={item.damage_type ? "warn" : "neutral"}>
                {item.damage_type || "Без типу"}
              </Badge>
            </div>
          </div>
        </div>
      </div>

      {/* Progress section */}
      <div className="p-5 border-b border-corp-border">
        <div className="flex justify-between items-center mb-2">
          <span className="text-sm font-medium">Прогрес обробки</span>
          <span className="text-sm font-bold">{processedQty} / {totalQty} шт</span>
        </div>
        <div className="h-3 rounded-full bg-corp-border">
          <div 
            className={cls(
              "h-full rounded-full transition-all duration-500",
              isFullyCompleted ? "bg-emerald-500" : "bg-blue-500"
            )}
            style={{ width: `${progress}%` }}
          />
        </div>
        {isFullyCompleted ? (
          <div className="mt-2 text-emerald-600 text-sm font-medium">✓ Повністю оброблено</div>
        ) : (
          <div className="mt-2 text-corp-text-muted text-sm">Залишилось: {remainingQty} шт</div>
        )}
      </div>

      {/* Action section */}
      {!isFullyCompleted && (
        <div className="p-5">
          <div className="space-y-4">
            {/* Quantity selector */}
            {remainingQty > 1 && (
              <div>
                <label className="text-sm font-medium block mb-2">Кількість {ml.action.toLowerCase()}</label>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setCompletedQty(Math.max(1, completedQty - 1))}
                    className="w-10 h-10 rounded-xl border border-corp-border bg-white hover:bg-corp-bg-light text-lg"
                  >
                    −
                  </button>
                  <input
                    type="number"
                    value={completedQty}
                    onChange={(e) => setCompletedQty(Math.max(1, Math.min(remainingQty, parseInt(e.target.value) || 1)))}
                    className="w-20 h-10 rounded-xl border border-corp-border text-center text-lg font-bold"
                    min={1}
                    max={remainingQty}
                  />
                  <button
                    onClick={() => setCompletedQty(Math.min(remainingQty, completedQty + 1))}
                    className="w-10 h-10 rounded-xl border border-corp-border bg-white hover:bg-corp-bg-light text-lg"
                  >
                    +
                  </button>
                  <button
                    onClick={() => setCompletedQty(remainingQty)}
                    className="px-3 py-2 text-sm text-corp-primary hover:underline"
                  >
                    Все ({remainingQty})
                  </button>
                </div>
              </div>
            )}

            {/* Notes */}
            <div>
              <label className="text-sm font-medium block mb-2">Примітка (опційно)</label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Додаткова інформація про обробку..."
                className="w-full h-20 rounded-xl border border-corp-border px-3 py-2 text-sm resize-none"
              />
            </div>

            {/* Action buttons */}
            <div className="flex flex-wrap gap-2">
              <PrimaryBtn variant="success" onClick={handleComplete} disabled={saving}>
                {saving ? "Збереження..." : `${ml.icon} ${ml.action} (${completedQty} шт)`}
              </PrimaryBtn>
              <PrimaryBtn variant="danger" onClick={() => onMarkFailed(item.id)} disabled={saving}>
                ❌ Списати
              </PrimaryBtn>
              <GhostBtn onClick={onRefresh}>🔄</GhostBtn>
            </div>
          </div>
        </div>
      )}

      {/* Completed state */}
      {isFullyCompleted && (
        <div className="p-5 bg-emerald-50">
          <div className="flex items-center gap-3">
            <span className="text-3xl">✓</span>
            <div>
              <div className="font-semibold text-emerald-800">Обробку завершено</div>
              <div className="text-sm text-emerald-600">Товар повернуто на склад</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
