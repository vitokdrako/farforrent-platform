/* eslint-disable */
/**
 * DamageHub - Shared helpers and UI components
 */
import React from "react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

// ----------------------------- helpers -----------------------------
export const cls = (...a) => a.filter(Boolean).join(" ");

export const money = (v, currency = "₴") => {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  if (Number.isNaN(n)) return "—";
  return `${currency}${n.toLocaleString("uk-UA")}`;
};

export const fmtDate = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("uk-UA", { day: "2-digit", month: "2-digit", year: "numeric" });
};

export const authFetch = async (url, options = {}) => {
  const token = localStorage.getItem("token");
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  return res;
};

export const getPhotoUrl = (item, backendUrl = BACKEND_URL) => {
  const rawPhoto = item.product_image || item.photo_url;
  if (!rawPhoto) return null;
  return rawPhoto.startsWith('http') ? rawPhoto : `${backendUrl}/${rawPhoto}`;
};

// ----------------------------- constants -----------------------------
export const MODES = {
  ALL: "all",
  WASH: "wash",
  RESTORE: "restore",
  DRYCLEAN: "dryclean",
};

export const modeMeta = {
  [MODES.ALL]: { title: "Головна", hint: "Кейси шкоди по ордерах • статус оплати", color: "bg-slate-900" },
  [MODES.WASH]: { title: "Мийка", hint: "Товари на мийці/чистці", color: "bg-blue-600" },
  [MODES.RESTORE]: { title: "Реставрація", hint: "Товари на ремонті/відновленні", color: "bg-amber-600" },
  [MODES.DRYCLEAN]: { title: "Хімчистка", hint: "Черга та партії відправок", color: "bg-emerald-600" },
};

export const STATUS_FILTERS = {
  all: "Всі",
  pending: "Очікує",
  in_progress: "В роботі",
  completed: "Виконано"
};

// ----------------------------- UI Components -----------------------------
const tonePill = (tone) =>
  cls(
    "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
    tone === "ok" && "bg-emerald-50 text-emerald-800 border-emerald-200",
    tone === "warn" && "bg-amber-50 text-amber-900 border-amber-200",
    tone === "danger" && "bg-rose-50 text-rose-800 border-rose-200",
    tone === "info" && "bg-blue-50 text-blue-800 border-blue-200",
    tone === "neutral" && "bg-corp-bg-page text-corp-text-main border-corp-border"
  );

export const Badge = ({ tone = "neutral", children }) => <span className={tonePill(tone)}>{children}</span>;

export const GhostBtn = ({ onClick, children, disabled, className = "" }) => (
  <button
    onClick={onClick}
    disabled={disabled}
    className={cls(
      "inline-flex items-center justify-center rounded-xl border px-3 py-2 text-sm font-medium transition",
      disabled ? "border-corp-border bg-corp-bg-page text-corp-text-muted cursor-not-allowed" : "border-corp-border bg-white text-corp-text-dark hover:bg-corp-bg-page",
      className
    )}
  >
    {children}
  </button>
);

export const PrimaryBtn = ({ onClick, children, disabled, variant = "primary" }) => {
  const variants = {
    primary: "bg-corp-primary text-white hover:bg-corp-primary-dark",
    dark: "bg-slate-900 text-white hover:bg-slate-800",
    danger: "bg-rose-600 text-white hover:bg-rose-700",
    success: "bg-emerald-600 text-white hover:bg-emerald-700",
    blue: "bg-blue-600 text-white hover:bg-blue-700",
    amber: "bg-amber-600 text-white hover:bg-amber-700",
  };
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cls(
        "inline-flex items-center justify-center rounded-xl px-4 py-2.5 text-sm font-semibold shadow-sm transition",
        disabled ? "bg-corp-border text-corp-text-muted cursor-not-allowed" : variants[variant] || variants.primary
      )}
    >
      {children}
    </button>
  );
};

// Product Photo Component
export const ProductPhoto = ({ item, size = "md", className = "" }) => {
  const photoUrl = getPhotoUrl(item);
  const sizes = {
    sm: "w-10 h-10",
    md: "w-14 h-14",
    lg: "w-20 h-20",
    xl: "w-24 h-24"
  };
  
  if (!photoUrl) {
    return (
      <div className={cls(
        sizes[size] || sizes.md,
        "rounded-lg bg-corp-bg-light border border-corp-border flex items-center justify-center text-corp-text-muted text-xs",
        className
      )}>
        📷
      </div>
    );
  }
  
  return (
    <img 
      src={photoUrl} 
      alt={item.product_name || "Товар"} 
      className={cls(sizes[size] || sizes.md, "rounded-lg object-cover border border-corp-border", className)}
      onError={(e) => { e.target.style.display = 'none'; }}
    />
  );
};
