/* eslint-disable */
/**
 * OrderEstimatePage — Повна сторінка кошторису замовлення
 * Відкривається з картки клієнта. Показує все: товари, фінанси, документи, lifecycle
 */
import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";

const API = process.env.REACT_APP_BACKEND_URL || "";
const cn = (...xs) => xs.filter(Boolean).join(" ");

const authFetch = async (url, opts = {}) => {
  const token = localStorage.getItem("token");
  return fetch(url, {
    ...opts,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...opts.headers },
  });
};

const money = (v) => `${Number(v || 0).toLocaleString("uk-UA")} грн`;
const fmtDate = (d) => d ? new Date(d).toLocaleDateString("uk-UA", { day: "2-digit", month: "2-digit", year: "numeric" }) : "—";
const fmtDateTime = (d) => d ? new Date(d).toLocaleString("uk-UA", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—";

const STATUS_MAP = {
  new: { label: "Новий", color: "bg-blue-100 text-blue-700" },
  confirmed: { label: "Підтверджений", color: "bg-indigo-100 text-indigo-700" },
  processing: { label: "В обробці", color: "bg-yellow-100 text-yellow-800" },
  ready: { label: "Готовий", color: "bg-teal-100 text-teal-700" },
  issued: { label: "Видано", color: "bg-emerald-100 text-emerald-700" },
  returned: { label: "Повернуто", color: "bg-slate-100 text-slate-700" },
  completed: { label: "Завершений", color: "bg-green-100 text-green-700" },
  cancelled: { label: "Скасований", color: "bg-rose-100 text-rose-700" },
};

const LIFECYCLE_LABELS = {
  created: "Створено", confirmed: "Підтверджено", processing: "В обробці",
  ready_for_issue: "Готово до видачі", issued: "Видано клієнту",
  returned: "Повернуто", completed: "Завершено",
};

export default function OrderEstimatePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadOrder();
  }, [id]);

  const loadOrder = async () => {
    setLoading(true);
    try {
      const res = await authFetch(`${API}/api/orders/${id}`);
      if (!res.ok) throw new Error("Ордер не знайдено");
      const data = await res.json();
      setOrder(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center">
      <div className="text-slate-400 text-lg">Завантаження...</div>
    </div>
  );

  if (error || !order) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center">
      <div className="text-center">
        <div className="text-rose-500 text-lg mb-2">{error || "Ордер не знайдено"}</div>
        <button onClick={() => navigate(-1)} className="text-sm text-slate-500 hover:text-slate-700 underline">Назад</button>
      </div>
    </div>
  );

  const status = STATUS_MAP[order.status] || { label: order.status, color: "bg-slate-100 text-slate-700" };
  const totalToPay = order.total_to_pay || ((order.total_after_discount || order.total_rental || 0) + (order.service_fee || 0));
  const paidRent = order.transactions?.filter(t => t.type === "rent_payment" || t.type === "payment").reduce((s, t) => s + t.amount, 0) || 0;
  const debt = Math.max(0, totalToPay - paidRent);
  const itemsCount = order.items?.reduce((s, i) => s + (i.quantity || 1), 0) || 0;

  return (
    <div className="min-h-screen bg-slate-50" data-testid="order-estimate-page">
      {/* Top Bar */}
      <div className="bg-white border-b border-slate-200 sticky top-0 z-30">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate(-1)}
              className="p-2 rounded-lg hover:bg-slate-100 transition text-slate-500"
              data-testid="back-btn"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" /></svg>
            </button>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono font-bold text-lg text-slate-900" data-testid="order-number">{order.order_number}</span>
                <span className={cn("px-2.5 py-0.5 rounded-full text-xs font-medium", status.color)} data-testid="order-status">{status.label}</span>
              </div>
              <div className="text-xs text-slate-500">
                {order.customer_name} · {fmtDate(order.rental_start_date)} — {fmtDate(order.rental_end_date)}
              </div>
            </div>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-slate-900" data-testid="order-total">{money(totalToPay)}</div>
            {debt > 0 ? (
              <div className="text-xs text-rose-600 font-medium">Борг: {money(debt)}</div>
            ) : paidRent > 0 ? (
              <div className="text-xs text-emerald-600 font-medium">Оплачено</div>
            ) : null}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 space-y-6">

        {/* Row: Client + Dates + Financial summary */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Client */}
          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Клієнт</h3>
            <div className="text-base font-semibold text-slate-900">{order.customer_name || "—"}</div>
            {order.client_phone && <div className="text-sm text-slate-600 mt-1">{order.client_phone}</div>}
            {order.client_email && <div className="text-sm text-slate-500">{order.client_email}</div>}
            {order.manager_name && (
              <div className="mt-3 pt-3 border-t border-slate-100 text-xs text-slate-500">
                Менеджер: <span className="text-slate-700 font-medium">{order.manager_name}</span>
              </div>
            )}
          </div>

          {/* Dates */}
          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Дати</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-slate-500">Створено:</span><span className="text-slate-800 font-medium">{fmtDate(order.created_at)}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">Оренда:</span><span className="text-slate-800 font-medium">{fmtDate(order.rental_start_date)} — {fmtDate(order.rental_end_date)}</span></div>
              <div className="flex justify-between"><span className="text-slate-500">Днів:</span><span className="text-slate-800 font-medium">{order.rental_days || 1}</span></div>
              {order.issue_time && <div className="flex justify-between"><span className="text-slate-500">Видача:</span><span className="text-slate-800 font-medium">{order.issue_time}</span></div>}
              {order.return_time && <div className="flex justify-between"><span className="text-slate-500">Повернення:</span><span className="text-slate-800 font-medium">{order.return_time}</span></div>}
            </div>
          </div>

          {/* Financial Summary */}
          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Фінанси</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-slate-500">Товари ({itemsCount} шт):</span><span className="font-semibold">{money(order.total_rental)}</span></div>
              {order.discount_amount > 0 && (
                <div className="flex justify-between"><span className="text-emerald-600">Знижка ({order.discount_percent}%):</span><span className="font-semibold text-emerald-600">-{money(order.discount_amount)}</span></div>
              )}
              {order.service_fee > 0 && (
                <div className="flex justify-between"><span className="text-amber-700">{order.service_fee_name || "Дод. послуга"}:</span><span className="font-semibold text-amber-700">{money(order.service_fee)}</span></div>
              )}
              <div className="flex justify-between pt-2 border-t border-slate-200">
                <span className="font-semibold text-slate-800">До сплати:</span>
                <span className="text-lg font-bold text-slate-900">{money(totalToPay)}</span>
              </div>
              {order.total_deposit > 0 && (
                <div className="flex justify-between"><span className="text-slate-500">Застава:</span><span className="font-semibold">{money(order.total_deposit)}</span></div>
              )}
              {paidRent > 0 && (
                <div className="flex justify-between"><span className="text-emerald-600">Оплачено:</span><span className="font-semibold text-emerald-600">{money(paidRent)}</span></div>
              )}
              {debt > 0 && (
                <div className="flex justify-between"><span className="text-rose-600 font-medium">Борг:</span><span className="font-bold text-rose-600">{money(debt)}</span></div>
              )}
            </div>
          </div>
        </div>

        {/* Items Table */}
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
            <h3 className="font-semibold text-slate-800">Товари ({order.items?.length || 0})</h3>
            <span className="text-sm text-slate-500">{itemsCount} одиниць</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wide">
                  <th className="px-4 py-3 text-left w-12">#</th>
                  <th className="px-4 py-3 text-left">Фото</th>
                  <th className="px-4 py-3 text-left">Назва</th>
                  <th className="px-4 py-3 text-left">Артикул</th>
                  <th className="px-4 py-3 text-center">К-сть</th>
                  <th className="px-4 py-3 text-right">Ціна/день</th>
                  <th className="px-4 py-3 text-right">Сума</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(order.items || []).map((item, i) => (
                  <tr key={i} className="hover:bg-slate-50/50" data-testid={`order-item-${i}`}>
                    <td className="px-4 py-3 text-slate-400">{i + 1}</td>
                    <td className="px-4 py-3">
                      {item.image || item.photo ? (
                        <img src={item.image || item.photo} alt="" className="w-10 h-10 rounded-lg object-cover border border-slate-200" />
                      ) : (
                        <div className="w-10 h-10 rounded-lg bg-slate-100 border border-slate-200" />
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-900">{item.name}</div>
                      <div className="text-xs text-slate-400">{item.category}</div>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-500">{item.sku || item.article}</td>
                    <td className="px-4 py-3 text-center font-medium">{item.quantity || item.qty}</td>
                    <td className="px-4 py-3 text-right text-slate-700">{money(item.price_per_day)}</td>
                    <td className="px-4 py-3 text-right font-semibold text-slate-900">{money(item.total_rental)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="bg-slate-50 font-semibold">
                  <td colSpan={6} className="px-4 py-3 text-right text-slate-700">Разом товари:</td>
                  <td className="px-4 py-3 text-right text-slate-900">{money(order.total_rental)}</td>
                </tr>
                {order.service_fee > 0 && (
                  <tr className="bg-amber-50/50">
                    <td colSpan={6} className="px-4 py-3 text-right text-amber-700">{order.service_fee_name || "Дод. послуга"}:</td>
                    <td className="px-4 py-3 text-right font-semibold text-amber-700">{money(order.service_fee)}</td>
                  </tr>
                )}
                {order.discount_amount > 0 && (
                  <tr className="bg-emerald-50/50">
                    <td colSpan={6} className="px-4 py-3 text-right text-emerald-700">Знижка ({order.discount_percent}%):</td>
                    <td className="px-4 py-3 text-right font-semibold text-emerald-700">-{money(order.discount_amount)}</td>
                  </tr>
                )}
                <tr className="bg-slate-100">
                  <td colSpan={6} className="px-4 py-3 text-right text-lg font-bold text-slate-800">До сплати:</td>
                  <td className="px-4 py-3 text-right text-lg font-bold text-slate-900">{money(totalToPay)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>

        {/* Row: Payments + Documents */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Payments */}
          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h3 className="font-semibold text-slate-800 mb-3">Платежі ({order.transactions?.length || 0})</h3>
            {(order.transactions?.length || 0) === 0 ? (
              <div className="text-sm text-slate-400 text-center py-4">Платежів немає</div>
            ) : (
              <div className="space-y-2">
                {order.transactions.map((t, i) => (
                  <div key={i} className="flex items-center justify-between py-2 px-3 rounded-xl bg-slate-50 text-sm" data-testid={`payment-${i}`}>
                    <div>
                      <div className="font-medium text-slate-800">{t.description || t.type}</div>
                      <div className="text-xs text-slate-400">{fmtDateTime(t.created_at)}</div>
                    </div>
                    <div className={cn("font-semibold", t.amount > 0 ? "text-emerald-700" : "text-rose-600")}>
                      {t.amount > 0 ? "+" : ""}{money(t.amount)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Documents */}
          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h3 className="font-semibold text-slate-800 mb-3">Документи ({order.documents?.length || 0})</h3>
            {(order.documents?.length || 0) === 0 ? (
              <div className="text-sm text-slate-400 text-center py-4">Документів не створено</div>
            ) : (
              <div className="space-y-2">
                {order.documents.map((doc, i) => (
                  <div key={i} className="flex items-center justify-between py-2 px-3 rounded-xl bg-slate-50 text-sm" data-testid={`document-${i}`}>
                    <div>
                      <div className="font-medium text-slate-800">{doc.doc_type_name}</div>
                      <div className="text-xs text-slate-400">
                        {doc.doc_number} · {fmtDate(doc.created_at)}
                        {doc.status === "signed" && <span className="text-emerald-600 ml-1">Підписано</span>}
                      </div>
                    </div>
                    <div className="flex gap-1.5">
                      <a
                        href={`${API}${doc.preview_url}`}
                        target="_blank"
                        rel="noreferrer"
                        className="px-2.5 py-1 rounded-lg text-xs font-medium bg-white border border-slate-200 text-slate-600 hover:bg-slate-100 transition"
                        data-testid={`doc-preview-${i}`}
                      >
                        Перегляд
                      </a>
                      <a
                        href={`${API}${doc.pdf_url}`}
                        target="_blank"
                        rel="noreferrer"
                        className="px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-800 text-white hover:bg-slate-700 transition"
                        data-testid={`doc-pdf-${i}`}
                      >
                        PDF
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Lifecycle */}
        {order.lifecycle?.length > 0 && (
          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h3 className="font-semibold text-slate-800 mb-4">Хронологія</h3>
            <div className="relative pl-6">
              <div className="absolute left-2 top-1 bottom-1 w-0.5 bg-slate-200" />
              {order.lifecycle.map((event, i) => (
                <div key={i} className="relative mb-4 last:mb-0" data-testid={`lifecycle-${i}`}>
                  <div className={cn(
                    "absolute -left-4 top-1.5 w-3 h-3 rounded-full border-2 border-white",
                    i === order.lifecycle.length - 1 ? "bg-emerald-500" : "bg-slate-300"
                  )} />
                  <div className="text-sm font-medium text-slate-800">
                    {LIFECYCLE_LABELS[event.stage] || event.stage}
                  </div>
                  {event.notes && <div className="text-xs text-slate-500">{event.notes}</div>}
                  <div className="text-xs text-slate-400">{fmtDateTime(event.timestamp || event.created_at)}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Internal Notes / Chat */}
        {(order.internal_notes?.length > 0 || order.notes || order.manager_comment) && (
          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h3 className="font-semibold text-slate-800 mb-4">Примітки та чат ({order.internal_notes?.length || 0})</h3>
            
            {/* Manager/order notes */}
            {order.manager_comment && order.manager_comment !== order.notes && (
              <div className="mb-3 p-3 rounded-xl bg-blue-50 border border-blue-200 text-sm">
                <div className="text-xs font-medium text-blue-600 mb-1">Коментар менеджера</div>
                <div className="text-blue-900 whitespace-pre-wrap">{order.manager_comment}</div>
              </div>
            )}
            
            {/* Internal notes chat */}
            {order.internal_notes?.length > 0 && (
              <div className="space-y-2">
                {order.internal_notes.map((note, i) => {
                  const isClient = note.author?.includes("клієнт") || note.author?.includes("Клієнт");
                  const isSystem = note.author === "System";
                  return (
                    <div
                      key={note.id || i}
                      className={cn(
                        "px-4 py-2.5 rounded-xl text-sm",
                        isClient ? "bg-amber-50 border border-amber-200" :
                        isSystem ? "bg-slate-50 border border-slate-200" :
                        "bg-blue-50 border border-blue-200"
                      )}
                      data-testid={`note-${i}`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className={cn(
                          "text-xs font-semibold",
                          isClient ? "text-amber-700" : isSystem ? "text-slate-500" : "text-blue-700"
                        )}>
                          {note.author}
                        </span>
                        <span className="text-xs text-slate-400">{fmtDateTime(note.created_at)}</span>
                      </div>
                      <div className={cn(
                        "whitespace-pre-wrap",
                        isClient ? "text-amber-900" : isSystem ? "text-slate-700" : "text-blue-900"
                      )}>
                        {note.message}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            
            {/* Fallback: order notes if no internal notes */}
            {(!order.internal_notes || order.internal_notes.length === 0) && order.notes && (
              <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-sm">
                <div className="text-amber-900 whitespace-pre-wrap">{order.notes}</div>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
}
