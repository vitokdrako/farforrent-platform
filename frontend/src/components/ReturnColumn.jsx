/* eslint-disable */
/**
 * ReturnColumn - Колонка "Повернення / Розрахунок" для менеджерської
 * 
 * Використовує ІСНУЮЧІ роути:
 * - GET /api/decor-orders?status=issued,returned,partial_return
 * - GET /api/orders/{order_id} (повні дані з items, return_cards, damages)
 * - GET /api/return-versions/order/{order_id}/versions
 * - GET /api/return-versions/version/{version_id}
 * - GET /api/finance/orders/{order_id}/snapshot
 * - POST /api/finance/payments
 * - POST /api/finance/deposits/{id}/refund
 * - POST /api/finance/deposits/{id}/use
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Clock, Package, CheckCircle, AlertTriangle, ChevronDown, ChevronUp, 
  ArrowLeftRight, DollarSign, Shield, RotateCcw, X, Banknote,
  Layers, Edit3, Eye, ImageOff, Calendar
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

const authFetch = (url, options = {}) => {
  const token = localStorage.getItem('token');
  return fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
};

const fmtUA = (n) => (Number(n) || 0).toLocaleString('uk-UA', { maximumFractionDigits: 0 });
const fmtDate = (d) => d ? new Date(d).toLocaleDateString('uk-UA', { day: '2-digit', month: '2-digit' }) : '—';
const money = (v) => `₴${fmtUA(v)}`;

// ============================================================
// MAIN COLUMN COMPONENT
// ============================================================
export default function ReturnColumn({ onRefreshAll, searchQuery = '' }) {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedOrderId, setExpandedOrderId] = useState(null);

  const fetchReturnOrders = useCallback(async () => {
    try {
      const res = await authFetch(`${BACKEND_URL}/api/decor-orders?status=issued,returned,partial_return&limit=50`);
      if (res.ok) {
        const data = await res.json();
        setOrders(Array.isArray(data) ? data : (data.orders || []));
      }
    } catch (e) {
      console.error('ReturnColumn fetch error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchReturnOrders();
    const interval = setInterval(fetchReturnOrders, 30000);
    return () => clearInterval(interval);
  }, [fetchReturnOrders]);

  const handleRefresh = () => {
    fetchReturnOrders();
    onRefreshAll?.();
  };

  const toggleExpand = (orderId) => {
    setExpandedOrderId(prev => prev === orderId ? null : orderId);
  };

  // Фільтрація за пошуком
  const filteredOrders = searchQuery
    ? orders.filter(o => {
        const q = searchQuery.toLowerCase();
        return (
          (o.order_number || '').toLowerCase().includes(q) ||
          (o.customer_name || '').toLowerCase().includes(q) ||
          (o.client_name || '').toLowerCase().includes(q) ||
          (o.customer_phone || '').includes(q) ||
          (o.client_phone || '').includes(q)
        );
      })
    : orders;

  return (
    <section className="rounded-2xl border p-4 shadow-sm ring-2 bg-white ring-violet-100 border-violet-200">
      <header className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-slate-800" data-testid="return-column-title">&#8617;&#65039; Повернення</h3>
          <p className="text-sm text-slate-500">{filteredOrders.length} замовлень{searchQuery && orders.length !== filteredOrders.length ? ` (з ${orders.length})` : ''}</p>
        </div>
      </header>
      <div className="space-y-3 max-h-[calc(100vh-280px)] overflow-y-auto pr-1">
        {loading ? (
          <div className="space-y-3">
            {[1,2,3].map(i => (
              <div key={i} className="rounded-xl border border-slate-200 p-4 h-32 bg-slate-50 animate-pulse" />
            ))}
          </div>
        ) : filteredOrders.length > 0 ? (
          filteredOrders.map(order => (
            <ReturnOrderCard
              key={order.order_id}
              order={order}
              onOpen={() => toggleExpand(order.order_id)}
            />
          ))
        ) : (
          <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center">
            <div className="text-slate-400 text-sm">{searchQuery ? 'Нічого не знайдено' : 'Немає замовлень на повернення'}</div>
          </div>
        )}
      </div>
    </section>
  );
}

// ============================================================
// RETURN ORDER CARD — compact card only, click opens modal
// ============================================================
function ReturnOrderCard({ order, onOpen }) {
  const navigate = useNavigate();
  const statusConfig = {
    issued: { label: 'Видано', color: 'bg-blue-100 text-blue-700', icon: Package },
    returned: { label: 'Повернуто', color: 'bg-emerald-100 text-emerald-700', icon: CheckCircle },
    partial_return: { label: 'Часткове', color: 'bg-amber-100 text-amber-700', icon: ArrowLeftRight },
  };

  const status = statusConfig[order.status] || { label: order.status, icon: AlertTriangle, color: 'bg-slate-100 text-slate-700' };
  const StatusIcon = status.icon;
  const fmtD = (d) => d ? new Date(d).toLocaleDateString('uk-UA', { day: '2-digit', month: '2-digit' }) : '—';

  return (
    <div 
      className="rounded-xl border border-slate-200 bg-white hover:shadow-md hover:border-violet-300 transition-all cursor-pointer"
      onClick={() => navigate(`/order/${order.order_id}/return-settlement`)}
      data-testid={`return-card-${order.order_id}`}
    >
      <div className="p-4 border-b border-slate-100">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="font-bold text-slate-800">{order.order_number}</span>
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${status.color}`}>
                <StatusIcon className="w-3 h-3" />
                {status.label}
              </span>
            </div>
            <div className="text-sm font-medium text-slate-700 truncate">{order.customer_name}</div>
            <a href={`tel:${order.customer_phone}`} className="text-xs text-blue-600 hover:underline" onClick={(e) => e.stopPropagation()}>
              {order.customer_phone}
            </a>
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); navigate(`/order/${order.order_id}/return-settlement`); }}
            className="p-2 rounded-lg bg-slate-100 text-slate-600 hover:bg-violet-100 hover:text-violet-700 transition-colors"
            title="Розкрити"
          >
            <Eye className="w-4 h-4" />
          </button>
        </div>
      </div>
      <div className="p-4">
        <div className="flex items-center gap-4 text-sm mb-3">
          <div><span className="text-slate-500">Видача:</span> <span className="font-medium">{fmtD(order.rental_start_date)}</span></div>
          <div><span className="text-slate-500">Повернення:</span> <span className="font-medium">{fmtD(order.rental_end_date)}</span></div>
        </div>
        <div className="flex items-center gap-4 text-sm mb-2">
          <div><span className="text-slate-500">Оренда:</span> <span className="font-semibold text-slate-800">{money(order.total_rental)}</span></div>
          <div><span className="text-slate-500">Застава:</span> <span className="font-medium text-slate-700">{money(order.total_deposit || order.deposit_amount)}</span></div>
          {order.discount > 0 && <span className="text-emerald-600 font-medium">-{order.discount}%</span>}
        </div>
        <div className="text-xs text-slate-500 mb-2">
          {order.items?.length || 0} позицій
          {order.manager_name && <span className="ml-2">· Менеджер: <b>{order.manager_name}</b></span>}
        </div>

        {/* Finance status row */}
        {(() => {
          const paidRent = order.paid_rent || 0;
          const totalRent = (order.total_after_discount || order.total_rental || 0) + (order.service_fee || 0);
          const rentDue = Math.max(0, totalRent - paidRent);
          const paidDeposit = order.paid_deposit || 0;
          const totalDeposit = order.total_deposit || order.deposit_amount || 0;
          const allPaid = rentDue <= 0 && paidRent > 0;
          
          return (
            <div className="pt-2 border-t border-slate-100 space-y-1.5">
              {/* Rent progress */}
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-500">Оплата оренди</span>
                <span className={`font-semibold ${allPaid ? 'text-emerald-600' : 'text-amber-600'}`}>
                  {allPaid ? '✓ Оплачено' : `${money(paidRent)} / ${money(totalRent)}`}
                </span>
              </div>
              <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                <div 
                  className={`h-full rounded-full transition-all ${allPaid ? 'bg-emerald-500' : 'bg-amber-500'}`}
                  style={{ width: `${Math.min(100, totalRent > 0 ? (paidRent / totalRent) * 100 : 0)}%` }}
                />
              </div>
              {/* Debt highlight */}
              {rentDue > 0 && (
                <div className="text-xs font-bold text-red-600 bg-red-50 rounded-lg px-2 py-1 text-center">
                  Борг: {money(rentDue)}
                </div>
              )}
              {/* Deposit status */}
              {totalDeposit > 0 && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-500">Застава</span>
                  <span className={`font-semibold ${paidDeposit >= totalDeposit ? 'text-emerald-600' : 'text-amber-600'}`}>
                    {paidDeposit >= totalDeposit ? '✓ Прийнято' : `${money(paidDeposit)} / ${money(totalDeposit)}`}
                  </span>
                </div>
              )}
            </div>
          );
        })()}
      </div>
    </div>
  );
}

