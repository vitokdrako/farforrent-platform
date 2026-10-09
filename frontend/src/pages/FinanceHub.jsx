/* eslint-disable */
/**
 * Finance Hub 2.0 - Уніфікований фінансовий центр з вкладками
 * 
 * Вкладки:
 * 1. Операції - головна (OrderList + OrderFinancePanel)
 * 2. Документи - центр документів
 * 3. Каси - баланси + зведення
 * 4. План надходжень - прогноз
 * 5. Витрати - категорії витрат
 * 6. Депозити - глобальний список
 * 7. Аналітика - звіти
 */
import React, { useEffect, useMemo, useState, useCallback } from "react";
import CorporateHeader from "../components/CorporateHeader";
import { DocumentPreviewModal } from "../components/DocumentPreviewModal";
import { SignatureModal } from "../components/SignatureCanvas";
import ClientsTab from "../components/ClientsTab";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

// ===== HELPERS =====
const cn = (...xs) => xs.filter(Boolean).join(" ");

const money = (v, currency = "₴") => {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  if (Number.isNaN(n)) return "—";
  return `${currency}${n.toLocaleString("uk-UA")}`;
};

const fmtDate = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("uk-UA", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
};

const fmtDateShort = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("uk-UA", { day: "2-digit", month: "2-digit" });
};

const authFetch = async (url, options = {}) => {
  const token = localStorage.getItem("token");
  return fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
};

// ===== UI COMPONENTS =====
const Badge = ({ kind, children }) => (
  <span className={cn(
    "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
    kind === "ok" && "bg-emerald-50 text-emerald-700 border border-emerald-100",
    kind === "pending" && "bg-amber-50 text-amber-700 border border-amber-100",
    kind === "warn" && "bg-rose-50 text-rose-700 border border-rose-100",
    kind === "info" && "bg-blue-50 text-blue-700 border border-blue-100"
  )}>
    {children}
  </span>
);

const Card = ({ title, right, children, className, noPadding }) => (
  <div className={cn("rounded-2xl border border-slate-200 bg-white shadow-sm", className)}>
    {(title || right) && (
      <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-slate-100">
        <div className="text-sm font-semibold text-slate-800">{title}</div>
        <div>{right}</div>
      </div>
    )}
    <div className={noPadding ? "" : "p-4"}>{children}</div>
  </div>
);

const Timeline = ({ items }) => (
  <div className="space-y-3">
    {items.map((it) => (
      <div key={it.id} className="flex gap-3">
        <div className="pt-1">
          <div className={cn(
            "h-2.5 w-2.5 rounded-full",
            it.status === "done" && "bg-emerald-500",
            it.status === "pending" && "bg-amber-500",
            it.status === "warn" && "bg-rose-500"
          )} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="text-xs text-slate-500">{it.at}</span>
            <span className="text-sm font-medium text-slate-900">{it.label}</span>
            {it.amount && <span className="text-sm font-semibold text-slate-900">{it.amount}</span>}
          </div>
          {it.meta && <div className="text-xs text-slate-600 mt-0.5">{it.meta}</div>}
        </div>
      </div>
    ))}
  </div>
);

const Select = ({ value, onChange, options }) => (
  <select
    className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:ring-2 focus:ring-slate-200"
    value={value}
    onChange={(e) => onChange(e.target.value)}
  >
    {options.map((o) => (
      <option key={o.value} value={o.value}>{o.label}</option>
    ))}
  </select>
);

const Input = (props) => (
  <input
    {...props}
    className={cn(
      "h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:ring-2 focus:ring-slate-200",
      props.className
    )}
  />
);

const Button = ({ children, variant = "primary", size = "md", ...props }) => (
  <button
    {...props}
    className={cn(
      "rounded-xl font-semibold transition active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed",
      size === "sm" && "h-8 px-3 text-xs",
      size === "md" && "h-10 px-4 text-sm",
      size === "lg" && "h-12 px-6 text-base",
      variant === "primary" && "bg-slate-900 text-white hover:bg-slate-800",
      variant === "ghost" && "bg-white text-slate-700 border border-slate-200 hover:bg-slate-50",
      variant === "warn" && "bg-amber-500 text-white hover:bg-amber-600",
      variant === "danger" && "bg-rose-500 text-white hover:bg-rose-600",
      variant === "success" && "bg-emerald-500 text-white hover:bg-emerald-600",
      variant === "deposit" && "bg-blue-500 text-white hover:bg-blue-600",
      variant === "advance" && "bg-violet-500 text-white hover:bg-violet-600",
      props.className
    )}
  >
    {children}
  </button>
);

// Tab Button Component
const TabButton = ({ active, onClick, children, icon }) => (
  <button
    onClick={onClick}
    className={cn(
      "flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-xl transition whitespace-nowrap",
      active 
        ? "bg-slate-900 text-white" 
        : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200"
    )}
  >
    {icon && <span className="text-base">{icon}</span>}
    {children}
  </button>
);

// ===== MAIN COMPONENT =====
export default function FinanceHub() {
  console.log("[FinanceHub] Component rendering...");
  
  // === GLOBAL STATE ===
  const [activeTab, setActiveTab] = useState("operations");
  const [month, setMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  });
  
  // Data states
  const [orders, setOrders] = useState([]);
  const [selectedOrderId, setSelectedOrderId] = useState(null);
  const [orderSnapshot, setOrderSnapshot] = useState(null);
  const [deposits, setDeposits] = useState([]);
  const [payoutsStats, setPayoutsStats] = useState(null);
  const [payments, setPayments] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [damageFees, setDamageFees] = useState({ total_fee: 0, paid_amount: 0, due_amount: 0, items: [] });
  const [lateFeeData, setLateFeeData] = useState({ total: 0, paid: 0, due: 0, items: [] });
  const [allExpenses, setAllExpenses] = useState([]);
  const [payerProfiles, setPayerProfiles] = useState([]);
  const [selectedPayerProfile, setSelectedPayerProfile] = useState(null);
  const [orderPayerOptions, setOrderPayerOptions] = useState(null); // Payer options for selected order
  const [matchedClient, setMatchedClient] = useState(null); // Auto-matched client for order
  const [clientPayers, setClientPayers] = useState([]); // Payers linked to matched client
  const [selectedClientPayer, setSelectedClientPayer] = useState(null); // Selected payer for documents
  const [clientSearching, setClientSearching] = useState(false);
  
  // Loading/UI states
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  
  // Get current user
  const getUser = () => JSON.parse(localStorage.getItem("user") || "{}");
  
  // ===== DATA LOADING =====
  const loadOrders = useCallback(async () => {
    console.log("[FinanceHub] loadOrders called");
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000);
      
      const res = await authFetch(`${BACKEND_URL}/api/manager/finance/orders-with-finance?limit=100`, { signal: controller.signal });
      clearTimeout(timeoutId);
      
      console.log("[FinanceHub] loadOrders response status:", res.status);
      const data = await res.json();
      console.log("[FinanceHub] loadOrders response:", data.orders?.length);
      setOrders(data.orders || []);
      if (data.orders?.length > 0) {
        setSelectedOrderId(prev => prev || data.orders[0].order_id);
      }
    } catch (e) {
      console.error("Load orders error:", e.name, e.message);
    }
  }, []);
  
  const loadDeposits = useCallback(async () => {
    console.log("[FinanceHub] loadDeposits called");
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000);
      
      const res = await authFetch(`${BACKEND_URL}/api/finance/deposits`, { signal: controller.signal });
      clearTimeout(timeoutId);
      
      console.log("[FinanceHub] loadDeposits response status:", res.status);
      const data = await res.json();
      console.log("[FinanceHub] loadDeposits response:", Array.isArray(data) ? data.length : 0);
      setDeposits(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error("Load deposits error:", e.name, e.message);
    }
  }, []);
  
  const loadPayoutsStats = useCallback(async () => {
    console.log("[FinanceHub] loadPayoutsStats called");
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000);
      
      const res = await authFetch(`${BACKEND_URL}/api/finance/payouts-stats-v2`, { signal: controller.signal });
      clearTimeout(timeoutId);
      
      console.log("[FinanceHub] loadPayoutsStats response status:", res.status);
      const data = await res.json();
      console.log("[FinanceHub] loadPayoutsStats response:", data?.total_cash_balance);
      setPayoutsStats(data);
    } catch (e) {
      console.error("Load stats error:", e.name, e.message);
    }
  }, []);
  
  const loadOrderSnapshot = useCallback(async (orderId) => {
    if (!orderId) return;
    try {
      const res = await authFetch(`${BACKEND_URL}/api/finance/orders/${orderId}/snapshot`);
      const data = await res.json();
      if (data.order_id) {
        setOrderSnapshot(data);
        setPayments(data.payments || []);
        setDocuments(data.documents || []);
        setDamageFees({
          total_fee: data.damage?.total || 0,
          paid_amount: data.damage?.paid || 0,
          due_amount: data.damage?.due || 0,
          items: data.damage?.items || []
        });
        setLateFeeData({
          total: data.late?.total || 0,
          paid: data.late?.paid || 0,
          due: data.late?.due || 0,
          items: data.late?.items || []
        });
        setSelectedPayerProfile(data.payer_profile || null);
      }
    } catch (e) {
      console.error("Load snapshot error:", e);
    }
  }, []);
  
  const loadAllExpenses = useCallback(async () => {
    try {
      const res = await authFetch(`${BACKEND_URL}/api/finance/expenses/all?limit=200`);
      const data = await res.json();
      setAllExpenses(data.expenses || []);
    } catch (e) {
      console.error("Load expenses error:", e);
    }
  }, []);
  
  const loadPayerProfiles = useCallback(async () => {
    console.log("[FinanceHub] loadPayerProfiles called");
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000);
      
      const res = await authFetch(`${BACKEND_URL}/api/payer-profiles`, { signal: controller.signal });
      clearTimeout(timeoutId);
      
      console.log("[FinanceHub] loadPayerProfiles response status:", res.status);
      const data = await res.json();
      console.log("[FinanceHub] loadPayerProfiles response:", data.profiles?.length);
      setPayerProfiles(data.profiles || []);
    } catch (e) {
      console.error("Load payer profiles error:", e.name, e.message);
    }
  }, []);
  
  // Load payer options for selected order
  const loadOrderPayerOptions = useCallback(async (orderId) => {
    if (!orderId) {
      setOrderPayerOptions(null);
      return;
    }
    try {
      const res = await authFetch(`${BACKEND_URL}/api/orders/${orderId}/payer-options`);
      if (res.ok) {
        const data = await res.json();
        setOrderPayerOptions(data);
      }
    } catch (e) {
      console.error("Load order payer options error:", e);
    }
  }, []);
  
  // Set payer for order
  const setOrderPayer = useCallback(async (orderId, payerId) => {
    try {
      setSaving(true);
      const res = await authFetch(`${BACKEND_URL}/api/orders/${orderId}/set-payer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ payer_profile_id: payerId })
      });
      if (res.ok) {
        await loadOrderPayerOptions(orderId);
        await loadOrders();
      } else {
        const err = await res.json();
        alert(`❌ Помилка: ${err.detail || 'Невідома помилка'}`);
      }
    } catch (e) {
      console.error("Set order payer error:", e);
      alert("❌ Помилка встановлення платника");
    } finally {
      setSaving(false);
    }
  }, [loadOrderPayerOptions, loadOrders]);
  
  // Auto-search for client by order's customer name/phone
  const searchClientForOrder = useCallback(async (order) => {
    if (!order) {
      setMatchedClient(null);
      setClientPayers([]);
      setSelectedClientPayer(null);
      return;
    }
    
    // If order already has client_user_id, load that client
    if (order.client_user_id) {
      try {
        const res = await authFetch(`${BACKEND_URL}/api/clients/${order.client_user_id}`);
        if (res.ok) {
          const client = await res.json();
          // Also get MA status
          const maRes = await authFetch(`${BACKEND_URL}/api/agreements/client/${order.client_user_id}`);
          const maData = await maRes.json();
          
          // Load client payers
          const payersRes = await authFetch(`${BACKEND_URL}/api/clients/${order.client_user_id}/payers`);
          const payersData = payersRes.ok ? await payersRes.json() : [];
          setClientPayers(payersData);
          
          // Auto-select default payer or first payer
          const defaultPayer = payersData.find(p => p.is_default) || payersData[0];
          setSelectedClientPayer(defaultPayer || null);
          
          setMatchedClient({
            ...client,
            has_agreement: maData.exists,
            agreement_status: maData.status,
            agreement_number: maData.contract_number,
            agreement_id: maData.id
          });
        }
      } catch (e) {
        console.error("Load client error:", e);
      }
      return;
    }
    
    // Search by name/phone
    const name = order.client_name || order.customer_name;
    const phone = order.client_phone || order.customer_phone;
    
    if (!name && !phone) {
      setMatchedClient(null);
      setClientPayers([]);
      setSelectedClientPayer(null);
      return;
    }
    
    setClientSearching(true);
    try {
      const params = new URLSearchParams();
      if (name) params.append("name", name);
      if (phone) params.append("phone", phone);
      
      const res = await authFetch(`${BACKEND_URL}/api/clients/find-match?${params}`);
      if (res.ok) {
        const data = await res.json();
        if (data.found && data.best_match) {
          setMatchedClient(data.best_match);
          
          // Load payers for matched client
          if (data.best_match.id) {
            const payersRes = await authFetch(`${BACKEND_URL}/api/clients/${data.best_match.id}/payers`);
            const payersData = payersRes.ok ? await payersRes.json() : [];
            setClientPayers(payersData);
            const defaultPayer = payersData.find(p => p.is_default) || payersData[0];
            setSelectedClientPayer(defaultPayer || null);
          }
        } else {
          // No match - show "new client" option
          setMatchedClient({
            is_new: true,
            suggested_name: name,
            suggested_phone: phone
          });
          setClientPayers([]);
          setSelectedClientPayer(null);
        }
      }
    } catch (e) {
      console.error("Search client error:", e);
    } finally {
      setClientSearching(false);
    }
  }, []);
  
  // Link order to client
  const linkOrderToClient = useCallback(async (orderId, clientId) => {
    try {
      setSaving(true);
      const res = await authFetch(`${BACKEND_URL}/api/orders/${orderId}/link-client`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_user_id: clientId })
      });
      if (res.ok) {
        await loadOrders();
        // Re-search to update matched client
        const order = orders.find(o => o.order_id === orderId);
        if (order) {
          searchClientForOrder({ ...order, client_user_id: clientId });
        }
      } else {
        const err = await res.json();
        alert(`❌ Помилка: ${err.detail || 'Невідома помилка'}`);
      }
    } catch (e) {
      console.error("Link client error:", e);
    } finally {
      setSaving(false);
    }
  }, [loadOrders, orders, searchClientForOrder]);
  
  // Initial load
  useEffect(() => {
    console.log("[FinanceHub] Initial load starting...");
    let isMounted = true;
    
    const loadAll = async () => {
      if (!isMounted) return;
      setLoading(true);
      try {
        console.log("[FinanceHub] Loading data...");
        
        // Load all in parallel for speed
        const results = await Promise.allSettled([
          loadOrders(),
          loadDeposits(),
          loadPayoutsStats(),
          loadPayerProfiles()
        ]);
        
        // Log any failures
        results.forEach((result, idx) => {
          if (result.status === 'rejected') {
            console.error(`[FinanceHub] Load ${idx} failed:`, result.reason);
          }
        });
        
        console.log("[FinanceHub] Data loaded successfully");
      } catch (e) {
        console.error("[FinanceHub] Load error:", e);
      } finally {
        // Always set loading to false when done
        if (isMounted) {
          setLoading(false);
        }
      }
    };
    
    loadAll();
    
    return () => { isMounted = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  
  // Load order snapshot when selection changes
  useEffect(() => {
    if (selectedOrderId) {
      loadOrderSnapshot(selectedOrderId);
      loadOrderPayerOptions(selectedOrderId);
      // Auto-search client for the selected order
      const order = orders.find(o => o.order_id === selectedOrderId);
      if (order) {
        searchClientForOrder(order);
      }
    } else {
      setMatchedClient(null);
    }
  }, [selectedOrderId, loadOrderSnapshot, loadOrderPayerOptions, orders, searchClientForOrder]);
  
  // Load expenses when tab changes to expenses
  useEffect(() => {
    if (activeTab === "expenses") {
      loadAllExpenses();
    }
  }, [activeTab, loadAllExpenses]);
  
  // Refresh all
  const refreshAll = useCallback(async () => {
    await Promise.all([
      loadOrders(),
      loadDeposits(),
      loadPayoutsStats(),
      selectedOrderId && loadOrderSnapshot(selectedOrderId)
    ]);
  }, [selectedOrderId, loadOrderSnapshot]);
  
  // ===== COMPUTED VALUES =====
  const selectedOrder = useMemo(() => {
    return orders.find(o => o.order_id === selectedOrderId) || null;
  }, [orders, selectedOrderId]);
  
  const orderDeposit = useMemo(() => {
    if (!selectedOrderId) return null;
    if (orderSnapshot?.deposit) return orderSnapshot.deposit;
    return deposits.find(d => d.order_id === selectedOrderId) || null;
  }, [deposits, selectedOrderId, orderSnapshot]);
  
  const filteredOrders = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    if (!q) return orders;
    return orders.filter(o =>
      (o.order_number || "").toLowerCase().includes(q) ||
      (o.customer_name || o.client_name || "").toLowerCase().includes(q) ||
      (o.customer_phone || "").toLowerCase().includes(q)
    );
  }, [orders, searchQuery]);
  
  const depositsByCurrency = useMemo(() => {
    const result = { UAH: 0, USD: 0, EUR: 0 };
    deposits.forEach(d => {
      const available = (d.held_amount || 0) - (d.used_amount || 0) - (d.refunded_amount || 0);
      if (available > 0) {
        const currency = d.currency || "UAH";
        if (currency === "UAH") result.UAH += available;
        else if (currency === "USD") result.USD += d.actual_amount - (d.used_amount || 0) - (d.refunded_amount || 0);
        else if (currency === "EUR") result.EUR += d.actual_amount - (d.used_amount || 0) - (d.refunded_amount || 0);
      }
    });
    return result;
  }, [deposits]);
  
  const orderStats = useMemo(() => {
    const total = orders.length;
    const paid = orders.filter(o => {
      const rentDue = Math.max(0, (o.total_rental || 0) - (o.rent_paid || 0));
      return rentDue <= 0 && (o.damage_due || 0) <= 0;
    }).length;
    return { total, paid, withDebt: total - paid };
  }, [orders]);
  
  // ===== TIMELINE =====
  const timeline = useMemo(() => {
    const items = [];
    payments.forEach(p => {
      const typeLabels = {
        rent: "Оренда", additional: "Донарахування", damage: "Шкода",
        deposit: "Застава", late: "Прострочення", advance: "Передплата"
      };
      items.push({
        id: `p_${p.id}`, at: fmtDate(p.occurred_at), status: "done",
        label: p.note || typeLabels[p.payment_type] || p.payment_type,
        amount: money(p.amount),
        meta: `${p.method === "cash" ? "готівка" : "безготівка"}${p.accepted_by_name ? ` · ${p.accepted_by_name}` : ""}`
      });
    });
    if (orderDeposit) {
      if (orderDeposit.used_amount > 0) {
        items.push({
          id: "dep_used", at: fmtDate(orderDeposit.closed_at), status: "warn",
          label: "Утримано із застави", amount: money(-orderDeposit.used_amount), meta: "компенсація"
        });
      }
      if (orderDeposit.refunded_amount > 0) {
        items.push({
          id: "dep_ref", at: fmtDate(orderDeposit.closed_at), status: "done",
          label: "Застава повернута", amount: money(orderDeposit.refunded_amount), meta: ""
        });
      }
    }
    if (damageFees.due_amount > 0) {
      items.push({
        id: "dmg_due", at: "Очікує", status: "warn",
        label: "Шкода (не сплачено)", amount: money(damageFees.due_amount),
        meta: damageFees.items.map(d => d.name).slice(0, 3).join(", ")
      });
    }
    return items.sort((a, b) => (a.at === "Очікує" ? -1 : b.at === "Очікує" ? 1 : 0));
  }, [payments, orderDeposit, damageFees]);
  
  // ===== PAYMENT HANDLERS =====
  const handlePayment = async (paymentType, paymentAmount, paymentMethod, extraData = {}) => {
    if (!selectedOrderId || !paymentAmount || Number(paymentAmount) <= 0) return false;
    setSaving(true);
    const user = getUser();
    
    try {
      if (paymentType === "deposit_in") {
        // Accept deposit (застава)
        const currency = extraData.currency || "UAH";
        const rate = currency === "USD" ? 41.5 : currency === "EUR" ? 45.2 : 1;
        await authFetch(`${BACKEND_URL}/api/finance/deposits/create`, {
          method: "POST",
          body: JSON.stringify({
            order_id: selectedOrderId,
            expected_amount: selectedOrder?.total_deposit || 0,
            actual_amount: Number(paymentAmount),
            currency: currency,
            exchange_rate: rate,
            method: paymentMethod,
            accepted_by_id: user.id,
            accepted_by_name: user.email,
          }),
        });
      } else if (paymentType === "advance") {
        // Advance payment (передплата) - йде в дохід
        await authFetch(`${BACKEND_URL}/api/finance/payments`, {
          method: "POST",
          body: JSON.stringify({
            payment_type: "advance",
            method: paymentMethod,
            amount: Number(paymentAmount),
            order_id: selectedOrderId,
            accepted_by_id: user.id,
            accepted_by_name: user.email,
            note: extraData.note || "Передплата",
          }),
        });
      } else if (paymentType === "deposit_out" && orderDeposit) {
        // Refund deposit
        const available = orderDeposit.available || (orderDeposit.held_amount - orderDeposit.used_amount - orderDeposit.refunded_amount);
        const refundAmount = Math.min(Number(paymentAmount), available);
        await authFetch(`${BACKEND_URL}/api/finance/deposits/${orderDeposit.id}/refund?amount=${refundAmount}&method=${paymentMethod}`, {
          method: "POST",
        });
      } else if (paymentType === "deposit_use" && orderDeposit) {
        // Use deposit for damage
        await authFetch(`${BACKEND_URL}/api/finance/deposits/${orderDeposit.id}/use?amount=${Number(paymentAmount)}`, {
          method: "POST",
          body: JSON.stringify({ note: "Утримання за шкоду" }),
        });
      } else {
        // Regular payment (rent, additional, damage, late)
        await authFetch(`${BACKEND_URL}/api/finance/payments`, {
          method: "POST",
          body: JSON.stringify({
            payment_type: paymentType,
            method: paymentMethod,
            amount: Number(paymentAmount),
            order_id: selectedOrderId,
            accepted_by_id: user.id,
            accepted_by_name: user.email,
            note: extraData.note,
            description: extraData.description,
          }),
        });
      }
      
      await refreshAll();
      setSaving(false);
      return true;
    } catch (e) {
      console.error("Payment error:", e);
      alert("Помилка: " + e.message);
      setSaving(false);
      return false;
    }
  };
  
  // Add expense
  const handleAddExpense = async (category, amount, description, opType = "expense") => {
    if (!amount || Number(amount) <= 0 || !description.trim()) return false;
    setSaving(true);
    const user = getUser();
    
    try {
      await authFetch(`${BACKEND_URL}/api/finance/expenses/simple`, {
        method: "POST",
        body: JSON.stringify({
          amount: Number(amount),
          description,
          category,
          operation_type: opType,
          created_by_id: user.id,
          created_by_name: user.email,
        }),
      });
      await loadPayoutsStats();
      await loadAllExpenses();
      setSaving(false);
      return true;
    } catch (e) {
      console.error("Add expense error:", e);
      setSaving(false);
      return false;
    }
  };
  
  // Generate document
  const generateDocument = async (docType) => {
    if (!selectedOrderId) return;
    try {
      const options = selectedPayerProfile ? { payer_profile_id: selectedPayerProfile.id } : {};
      const res = await authFetch(`${BACKEND_URL}/api/documents/generate`, {
        method: "POST",
        body: JSON.stringify({
          doc_type: docType,
          entity_id: String(selectedOrderId),
          format: "html",
          options
        })
      });
      const data = await res.json();
      if (data.success && data.html_content) {
        const win = window.open("", "_blank");
        win.document.write(data.html_content);
        win.document.close();
        await loadOrderSnapshot(selectedOrderId);
      }
    } catch (e) {
      console.error("Generate doc error:", e);
    }
  };
  
  // ===== TABS CONFIG =====
  // Нова структура: MA в Клієнтах, документи в Операціях, Документи → Реєстр
  const TABS = [
    { id: "operations", label: "Операції", icon: "💰" },      // Головна: ордери + всі документи
    { id: "clients", label: "Клієнти", icon: "👥" },          // Клієнти + Платники + MA
    { id: "registry", label: "Реєстр", icon: "📄" },          // Архів документів (read-only)
    { id: "cash", label: "Каси", icon: "💵" },
    { id: "deposits", label: "Депозити", icon: "🔒" },
    { id: "expenses", label: "Витрати", icon: "📉" },
    { id: "analytics", label: "Аналітика", icon: "📈" },
    { id: "forecast", label: "План", icon: "📊" },
  ];
  
  // ===== RENDER =====
  // Show loading for max 5 seconds, then render anyway
  const [loadingTimeout, setLoadingTimeout] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setLoadingTimeout(true), 5000);
    return () => clearTimeout(timer);
  }, []);
  
  if (loading && !loadingTimeout) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-slate-500">Завантаження...</div>
      </div>
    );
  }
  
  return (
    <div className="min-h-screen bg-slate-50">
      <CorporateHeader />
      
      {/* Header with KPI */}
      <div className="sticky top-[60px] z-20 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto max-w-7xl px-4 py-3">
          {/* Top row: Title + KPI + Controls */}
          <div className="flex items-center justify-between gap-4 mb-3">
            <div className="flex items-center gap-3">
              <span className="text-xl font-extrabold">💰 Фінанси</span>
              <div className="hidden sm:flex items-center gap-4 ml-4 text-sm">
                <div className="flex items-center gap-1.5">
                  <span className="text-slate-500">Готівка:</span>
                  <span className="font-bold text-emerald-600">{money(payoutsStats?.total_cash_balance || 0)}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-slate-500">Банк:</span>
                  <span className="font-bold text-blue-600">{money(payoutsStats?.bank_balance || 0)}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-slate-500">Застави:</span>
                  <span className="font-bold text-amber-600">{money(depositsByCurrency.UAH)}</span>
                  {depositsByCurrency.USD > 0 && <span className="font-bold text-amber-600">+ ${depositsByCurrency.USD.toFixed(0)}</span>}
                </div>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              <Input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="w-[140px]" />
              <Button variant="ghost" onClick={refreshAll} className="!px-3">🔄</Button>
            </div>
          </div>
          
          {/* Tabs */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1 -mb-1">
            {TABS.map(tab => (
              <TabButton
                key={tab.id}
                active={activeTab === tab.id}
                onClick={() => setActiveTab(tab.id)}
                icon={tab.icon}
              >
                {tab.label}
              </TabButton>
            ))}
          </div>
        </div>
      </div>
      
      {/* Tab Content */}
      <div className="mx-auto max-w-7xl px-4 py-4">
        {/* TAB: Operations */}
        {activeTab === "operations" && (
          <OperationsTab
            orders={filteredOrders}
            selectedOrderId={selectedOrderId}
            setSelectedOrderId={setSelectedOrderId}
            selectedOrder={selectedOrder}
            orderSnapshot={orderSnapshot}
            orderDeposit={orderDeposit}
            payments={payments}
            damageFees={damageFees}
            lateFeeData={lateFeeData}
            timeline={timeline}
            searchQuery={searchQuery}
            setSearchQuery={setSearchQuery}
            saving={saving}
            handlePayment={handlePayment}
            refreshAll={refreshAll}
            payoutsStats={payoutsStats}
            depositsByCurrency={depositsByCurrency}
            orderStats={orderStats}
            generateDocument={generateDocument}
            selectedPayerProfile={selectedPayerProfile}
            payerProfiles={payerProfiles}
            orderPayerOptions={orderPayerOptions}
            setOrderPayer={setOrderPayer}
            matchedClient={matchedClient}
            clientPayers={clientPayers}
            selectedClientPayer={selectedClientPayer}
            setSelectedClientPayer={setSelectedClientPayer}
            clientSearching={clientSearching}
            linkOrderToClient={linkOrderToClient}
          />
        )}
        
        {/* TAB: Registry (read-only документи) */}
        {activeTab === "registry" && (
          <RegistryTab
            orders={orders}
            documents={documents}
            payerProfiles={payerProfiles}
          />
        )}
        
        {/* TAB: Cash */}
        {activeTab === "cash" && (
          <CashTab
            payoutsStats={payoutsStats}
            depositsByCurrency={depositsByCurrency}
            handleAddExpense={handleAddExpense}
            saving={saving}
            refreshAll={refreshAll}
          />
        )}
        
        {/* TAB: Forecast */}
        {activeTab === "forecast" && (
          <ForecastTab orders={orders} />
        )}
        
        {/* TAB: Expenses */}
        {activeTab === "expenses" && (
          <ExpensesTab
            allExpenses={allExpenses}
            handleAddExpense={handleAddExpense}
            saving={saving}
            refreshAll={refreshAll}
          />
        )}
        
        {/* TAB: Deposits */}
        {activeTab === "deposits" && (
          <DepositsTab
            deposits={deposits}
            depositsByCurrency={depositsByCurrency}
          />
        )}
        
        {/* TAB: Analytics */}
        {activeTab === "analytics" && (
          <AnalyticsTab
            orders={orders}
            payoutsStats={payoutsStats}
            deposits={deposits}
            orderStats={orderStats}
          />
        )}
        
        {/* TAB: Clients */}
        {activeTab === "clients" && (
          <ClientsTab />
        )}
      </div>
    </div>
  );
}


// ============================================================
// TAB: OPERATIONS (Main tab)
// ============================================================
function OperationsTab({
  orders, selectedOrderId, setSelectedOrderId, selectedOrder, orderSnapshot,
  orderDeposit, payments, damageFees, lateFeeData, timeline,
  searchQuery, setSearchQuery, saving, handlePayment, refreshAll,
  payoutsStats, depositsByCurrency, orderStats, generateDocument,
  selectedPayerProfile, payerProfiles, orderPayerOptions, setOrderPayer,
  matchedClient, clientPayers, selectedClientPayer, setSelectedClientPayer,
  clientSearching, linkOrderToClient
}) {
  // Payment form state
  const [payType, setPayType] = useState("rent");
  const [method, setMethod] = useState("cash");
  const [amount, setAmount] = useState("");
  const [additionalName, setAdditionalName] = useState("");
  const [depositCurrency, setDepositCurrency] = useState("UAH");
  
  // Damage/Late forms
  const [newDamageAmount, setNewDamageAmount] = useState("");
  const [newDamageNote, setNewDamageNote] = useState("");
  const [newLateAmount, setNewLateAmount] = useState("");
  const [newLateNote, setNewLateNote] = useState("");
  
  const getOrderBadge = (order) => {
    const rentDue = Math.max(0, (order.total_rental || 0) - (order.rent_paid || 0));
    const hasDamage = (order.damage_due || 0) > 0;
    if (hasDamage) return { kind: "warn", text: `⚠️ ${money(order.damage_due)}` };
    if (rentDue > 0) return { kind: "pending", text: `⏳ ${money(rentDue)}` };
    return { kind: "ok", text: "✓ OK" };
  };
  
  const needsName = payType === "additional";
  const needsCurrency = payType === "deposit_in";
  const canSubmit = amount.trim().length > 0 && Number(amount) > 0 && (!needsName || additionalName.trim().length > 2);
  
  const onSubmitPayment = async () => {
    const extraData = {};
    if (payType === "additional") extraData.description = additionalName;
    if (payType === "deposit_in") extraData.currency = depositCurrency;
    
    const success = await handlePayment(payType, amount, method, extraData);
    if (success) {
      setAmount("");
      setAdditionalName("");
    }
  };
  
  // Calculate totals with discount
  const totals = useMemo(() => {
    if (!selectedOrder) return null;
    const discount = selectedOrder.discount_amount || 0;
    const serviceFee = selectedOrder.service_fee || 0;
    const totalWithServiceFee = selectedOrder.total_rental + serviceFee;
    const totalAfterDiscount = totalWithServiceFee - discount;
    const toPay = Math.max(0, totalAfterDiscount - (selectedOrder.rent_paid || 0));
    return { discount, serviceFee, totalWithServiceFee, totalAfterDiscount, toPay };
  }, [selectedOrder]);
  
  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
      {/* LEFT: Cash summary + Orders list */}
      <div className="lg:col-span-3 space-y-4">
        {/* Mini Cash Summary */}
        <Card title="📊 Каси">
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-600">💵 Готівка</span>
              <span className="font-bold text-emerald-600">{money(payoutsStats?.total_cash_balance || 0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-600">🏦 Безготівка</span>
              <span className="font-bold text-blue-600">{money(payoutsStats?.bank_balance || 0)}</span>
            </div>
            <div className="flex justify-between pt-2 border-t border-slate-100">
              <span className="text-slate-600">🔒 Застави</span>
              <span className="font-bold text-amber-600">
                ₴{depositsByCurrency.UAH.toLocaleString()}
                {depositsByCurrency.USD > 0 && ` + $${depositsByCurrency.USD.toFixed(0)}`}
              </span>
            </div>
          </div>
        </Card>
        
        {/* Orders List */}
        <Card title="📋 Ордери" right={<span className="text-xs text-slate-500">{orders.length}</span>}>
          <div className="mb-3">
            <Input 
              placeholder="код / клієнт / телефон" 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <div className="space-y-2 max-h-[450px] overflow-y-auto">
            {orders.length === 0 ? (
              <div className="text-center text-slate-500 py-4">Немає ордерів</div>
            ) : (
              orders.map((o) => {
                const badge = getOrderBadge(o);
                const isSelected = o.order_id === selectedOrderId;
                return (
                  <button
                    key={o.order_id}
                    onClick={() => setSelectedOrderId(o.order_id)}
                    className={cn(
                      "w-full rounded-xl border px-3 py-2 text-left transition",
                      isSelected 
                        ? "border-slate-900 bg-slate-50 ring-1 ring-slate-900" 
                        : "border-slate-200 bg-white hover:bg-slate-50"
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-sm font-semibold text-slate-900">#{o.order_number}</div>
                      <Badge kind={badge.kind}>{badge.text}</Badge>
                    </div>
                    <div className="text-xs text-slate-500">{o.customer_name || o.client_name}</div>
                  </button>
                );
              })
            )}
          </div>
        </Card>
      </div>
      
      {/* CENTER: Selected Order */}
      <div className="lg:col-span-6 space-y-4">
        {selectedOrder ? (
          <>
            {/* Order Header */}
            <Card
              title={
                <div className="flex items-center gap-2">
                  <span>🔍 Ордер</span>
                  <span className="text-slate-500 font-medium">
                    #{selectedOrder.order_number} · {selectedOrder.customer_name || selectedOrder.client_name}
                  </span>
                </div>
              }
              right={<Badge kind={getOrderBadge(selectedOrder).kind}>{selectedOrder.status}</Badge>}
            >
              {/* KPI Row */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                <div className="rounded-xl bg-slate-50 border border-slate-200 p-3">
                  <div className="text-xs text-slate-500">Нараховано</div>
                  <div className="text-lg font-bold">{money(totals?.totalWithServiceFee || selectedOrder.total_rental)}</div>
                  {totals?.serviceFee > 0 && (
                    <div className="text-xs text-amber-600">+ {selectedOrder.service_fee_name || "Дод. послуга"} {money(totals.serviceFee)}</div>
                  )}
                  {totals?.discount > 0 && (
                    <div className="text-xs text-emerald-600">− знижка {money(totals.discount)}</div>
                  )}
                </div>
                <div className="rounded-xl bg-slate-50 border border-slate-200 p-3">
                  <div className="text-xs text-slate-500">Оплачено</div>
                  <div className="text-lg font-bold text-emerald-600">{money(selectedOrder.rent_paid)}</div>
                </div>
                <div className="rounded-xl bg-slate-50 border border-slate-200 p-3">
                  <div className="text-xs text-slate-500">Застава</div>
                  <div className="text-lg font-bold">{money(selectedOrder.deposit_held)}</div>
                </div>
                <div className="rounded-xl bg-slate-50 border border-slate-200 p-3">
                  <div className="text-xs text-slate-500">До сплати</div>
                  <div className={cn("text-lg font-bold", totals?.toPay > 0 ? "text-amber-600" : "text-emerald-600")}>
                    {money(totals?.toPay || 0)}
                  </div>
                </div>
              </div>
              
              {/* Timeline */}
              {timeline.length > 0 && (
                <div className="rounded-2xl bg-slate-50 border border-slate-200 p-4 mb-4">
                  <div className="text-xs font-semibold text-slate-600 mb-3">ТАЙМЛАЙН ОПЕРАЦІЙ</div>
                  <Timeline items={timeline} />
                </div>
              )}
            </Card>
            
            {/* Payment Form - with SEPARATE buttons for Deposit and Advance */}
            <Card title="💳 Прийняти оплату">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <div className="text-xs text-slate-500 mb-1">Тип</div>
                  <Select
                    value={payType}
                    onChange={setPayType}
                    options={[
                      { value: "rent", label: "💵 Оренда" },
                      { value: "additional", label: "➕ Донарахування" },
                      { value: "damage", label: "💔 Шкода" },
                      { value: "late", label: "⏰ Прострочення" },
                    ]}
                  />
                </div>
                
                <div>
                  <div className="text-xs text-slate-500 mb-1">Метод</div>
                  <Select
                    value={method}
                    onChange={setMethod}
                    options={[
                      { value: "cash", label: "Готівка" },
                      { value: "bank", label: "Безготівка" },
                    ]}
                  />
                </div>
                
                {needsName && (
                  <div className="sm:col-span-2">
                    <div className="text-xs text-slate-500 mb-1">Назва *</div>
                    <Input
                      value={additionalName}
                      onChange={(e) => setAdditionalName(e.target.value)}
                      placeholder="Доставка, упаковка..."
                    />
                  </div>
                )}
                
                <div>
                  <div className="text-xs text-slate-500 mb-1">Сума (₴)</div>
                  <Input value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="0" inputMode="decimal" />
                </div>
                
                <div className="flex items-end">
                  <Button className="w-full" disabled={!canSubmit || saving} onClick={onSubmitPayment}>
                    {saving ? "..." : "Зарахувати"}
                  </Button>
                </div>
              </div>
              
              {/* SEPARATE BUTTONS: Deposit vs Advance */}
              <div className="mt-4 pt-4 border-t border-slate-200">
                <div className="text-xs font-semibold text-slate-600 mb-3">ЗАСТАВА / ПЕРЕДПЛАТА</div>
                <div className="grid grid-cols-2 gap-3">
                  {/* Deposit Button */}
                  <DepositAdvanceButton
                    type="deposit"
                    orderDeposit={orderDeposit}
                    expectedAmount={selectedOrder.total_deposit}
                    handlePayment={handlePayment}
                    saving={saving}
                    method={method}
                  />
                  
                  {/* Advance Button */}
                  <DepositAdvanceButton
                    type="advance"
                    handlePayment={handlePayment}
                    saving={saving}
                    method={method}
                  />
                </div>
              </div>
            </Card>
            
            {/* Deposit Details */}
            {orderDeposit && (
              <Card title="🔒 Застава">
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-600">Прийнято</span>
                    <span className="font-semibold">
                      {orderDeposit.currency === "USD" ? "$" : orderDeposit.currency === "EUR" ? "€" : "₴"}
                      {(orderDeposit.actual_amount || orderDeposit.held_amount).toLocaleString()}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-600">Використано</span>
                    <span className="font-semibold text-rose-600">
                      -{orderDeposit.currency === "USD" ? "$" : orderDeposit.currency === "EUR" ? "€" : "₴"}
                      {(orderDeposit.used_amount || 0).toLocaleString()}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-600">Повернуто</span>
                    <span className="font-semibold text-blue-600">
                      {orderDeposit.currency === "USD" ? "$" : orderDeposit.currency === "EUR" ? "€" : "₴"}
                      {(orderDeposit.refunded_amount || 0).toLocaleString()}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm pt-2 border-t border-slate-200">
                    <span className="text-slate-700 font-medium">Доступно</span>
                    <span className="font-bold text-emerald-600">
                      {orderDeposit.currency === "USD" ? "$" : orderDeposit.currency === "EUR" ? "€" : "₴"}
                      {(orderDeposit.available || (orderDeposit.held_amount - (orderDeposit.used_amount || 0) - (orderDeposit.refunded_amount || 0))).toLocaleString()}
                    </span>
                  </div>
                  
                  {/* Refund button */}
                  {(orderDeposit.available || (orderDeposit.held_amount - (orderDeposit.used_amount || 0) - (orderDeposit.refunded_amount || 0))) > 0 && (
                    <Button
                      variant="success"
                      className="w-full mt-3"
                      disabled={saving}
                      onClick={async () => {
                        const avail = orderDeposit.available || (orderDeposit.held_amount - (orderDeposit.used_amount || 0) - (orderDeposit.refunded_amount || 0));
                        if (!window.confirm(`Повернути заставу: ${orderDeposit.currency === "USD" ? "$" : orderDeposit.currency === "EUR" ? "€" : "₴"}${avail}?`)) return;
                        await handlePayment("deposit_out", avail, "cash");
                      }}
                    >
                      💸 Повернути заставу
                    </Button>
                  )}
                </div>
              </Card>
            )}
            
            {/* Damage Section */}
            <Card title="💔 Шкода" className="border-rose-200 bg-rose-50/50">
              {damageFees.items?.length > 0 && (
                <div className="mb-3">
                  <div className="text-xs text-rose-700 mb-2 font-medium">Зафіксовано:</div>
                  <div className="space-y-1 max-h-32 overflow-y-auto">
                    {damageFees.items.map((d, i) => {
                      const qty = d.qty || 1
                      const feePerItem = d.fee_per_item || (qty > 0 ? d.fee / qty : d.fee)
                      return (
                        <div key={i} className="flex items-center justify-between text-sm bg-white rounded-lg p-2">
                          <div className="flex-1 min-w-0">
                            <span className="text-rose-800 font-medium">{d.name}</span>
                            {qty > 1 && <span className="text-rose-600 font-bold ml-1">×{qty} шт</span>}
                            <div className="text-xs text-rose-600/80 truncate">{d.damage_type}</div>
                          </div>
                          <div className="text-right flex-shrink-0 ml-2">
                            <div className="font-semibold text-rose-600">{money(d.fee)}</div>
                            {qty > 1 && (
                              <div className="text-[10px] text-rose-500">{qty} × {money(feePerItem)}</div>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                  <div className="mt-2 text-right text-sm">
                    <span className="text-rose-700">Всього: </span>
                    <span className="font-bold text-rose-800">{money(damageFees.total_fee)}</span>
                    {damageFees.paid_amount > 0 && (
                      <span className="text-emerald-600 ml-2">(оплачено {money(damageFees.paid_amount)})</span>
                    )}
                  </div>
                </div>
              )}
              
              {damageFees.due_amount > 0 && (
                <div className="p-3 bg-rose-100 rounded-xl mb-3">
                  <div className="text-rose-800 font-semibold">До сплати: {money(damageFees.due_amount)}</div>
                </div>
              )}
              
              {/* Add damage */}
              <div className="flex gap-2">
                <Input 
                  type="number"
                  placeholder="Сума ₴"
                  value={newDamageAmount}
                  onChange={(e) => setNewDamageAmount(e.target.value)}
                  className="flex-1"
                />
                <Input 
                  placeholder="Опис"
                  value={newDamageNote}
                  onChange={(e) => setNewDamageNote(e.target.value)}
                  className="flex-1"
                />
                <Button
                  variant="danger"
                  size="sm"
                  disabled={!newDamageAmount || saving}
                  onClick={async () => {
                    const success = await handlePayment("damage", newDamageAmount, "cash", { note: newDamageNote });
                    if (success) {
                      setNewDamageAmount("");
                      setNewDamageNote("");
                    }
                  }}
                >
                  Оплатити
                </Button>
              </div>
            </Card>
            
            {/* Late fees */}
            <Card title="⏰ Прострочення" className="border-amber-200 bg-amber-50/50">
              {lateFeeData.due > 0 && (
                <div className="p-3 bg-amber-100 rounded-xl mb-3">
                  <div className="text-amber-800 font-semibold">До сплати: {money(lateFeeData.due)}</div>
                </div>
              )}
              
              {lateFeeData.items?.length > 0 && (
                <div className="mb-3 space-y-1">
                  {lateFeeData.items.map((l, i) => (
                    <div key={i} className="flex justify-between text-sm">
                      <span className="text-amber-700">{l.note || "Прострочення"}</span>
                      <span className={cn("font-semibold", l.status === "pending" ? "text-amber-600" : "text-emerald-600")}>
                        {money(l.amount)} {l.status !== "pending" && "✓"}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              
              <div className="flex gap-2">
                <Input 
                  type="number"
                  placeholder="Сума ₴"
                  value={newLateAmount}
                  onChange={(e) => setNewLateAmount(e.target.value)}
                  className="flex-1"
                />
                <Input 
                  placeholder="Опис"
                  value={newLateNote}
                  onChange={(e) => setNewLateNote(e.target.value)}
                  className="flex-1"
                />
                <Button
                  variant="warn"
                  size="sm"
                  disabled={!newLateAmount || saving}
                  onClick={async () => {
                    const success = await handlePayment("late", newLateAmount, "cash", { note: newLateNote });
                    if (success) {
                      setNewLateAmount("");
                      setNewLateNote("");
                    }
                  }}
                >
                  Оплатити
                </Button>
              </div>
            </Card>
          </>
        ) : (
          <Card>
            <div className="text-center text-slate-500 py-8">Виберіть ордер зі списку</div>
          </Card>
        )}
      </div>
      
      {/* RIGHT: Statistics & Documents */}
      <div className="lg:col-span-3 space-y-4">
        {/* Stats */}
        <Card title="📊 Статистика">
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-600">Ордерів</span>
              <span className="font-semibold">{orderStats.total}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-600">Оплачено</span>
              <span className="font-semibold text-emerald-600">{orderStats.paid}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-600">З боргом</span>
              <span className="font-semibold text-amber-600">{orderStats.withDebt}</span>
            </div>
          </div>
        </Card>
        
        {/* Quick Documents */}
        {selectedOrder && (
          <Card title="📄 Документи">
            <div className="space-y-3">
              {/* === CLIENT STATUS === */}
              <div className="pb-3 border-b border-slate-100">
                <div className="text-xs font-medium text-slate-600 mb-2">👤 Клієнт:</div>
                
                {clientSearching ? (
                  <div className="text-xs text-slate-500 animate-pulse">Пошук клієнта...</div>
                ) : matchedClient?.is_new ? (
                  // New client - not found in system
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-2">
                    <div className="text-xs text-amber-700 font-medium">⚠️ Новий клієнт</div>
                    <div className="text-xs text-amber-600 mt-1">
                      {matchedClient.suggested_name || selectedOrder.client_name || selectedOrder.customer_name}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="mt-2 w-full text-xs h-7"
                      onClick={() => {
                        // Open create client modal or navigate to clients tab
                        window.dispatchEvent(new CustomEvent('create-client-for-order', { 
                          detail: { 
                            name: matchedClient.suggested_name || selectedOrder.customer_name,
                            phone: matchedClient.suggested_phone || selectedOrder.customer_phone,
                            orderId: selectedOrder.order_id
                          }
                        }));
                      }}
                    >
                      ➕ Створити клієнта
                    </Button>
                  </div>
                ) : matchedClient ? (
                  // Found client
                  <div className="bg-slate-50 rounded-lg p-2">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-sm font-medium text-slate-800">{matchedClient.full_name}</div>
                        <div className="text-xs text-slate-500">{matchedClient.email}</div>
                        <div className="text-xs text-slate-500">
                          {matchedClient.payer_type === 'individual' && '👤 Фіз. особа'}
                          {matchedClient.payer_type === 'fop' && '🏪 ФОП'}
                          {matchedClient.payer_type === 'fop_simple' && '🏪 ФОП (спрощена)'}
                          {matchedClient.payer_type === 'tov' && '🏢 ТОВ'}
                        </div>
                      </div>
                      {!selectedOrder.client_user_id && (
                        <Button
                          variant="primary"
                          size="sm"
                          className="text-xs h-7"
                          onClick={() => linkOrderToClient(selectedOrder.order_id, matchedClient.id)}
                          disabled={saving}
                        >
                          Прив'язати
                        </Button>
                      )}
                    </div>
                    
                    {/* MA Status */}
                    <div className="mt-2 pt-2 border-t border-slate-200">
                      {matchedClient.has_agreement ? (
                        <div className="flex items-center justify-between">
                          <div>
                            <span className={cn(
                              "text-xs px-2 py-0.5 rounded-full",
                              matchedClient.agreement_status === 'signed' ? "bg-emerald-100 text-emerald-700" :
                              matchedClient.agreement_status === 'draft' ? "bg-amber-100 text-amber-700" :
                              "bg-slate-100 text-slate-600"
                            )}>
                              {matchedClient.agreement_status === 'signed' ? '✅ MA підписано' :
                               matchedClient.agreement_status === 'draft' ? '⏳ MA чернетка' :
                               matchedClient.agreement_status}
                            </span>
                            <span className="text-xs text-slate-500 ml-2">{matchedClient.agreement_number}</span>
                          </div>
                        </div>
                      ) : (
                        <div className="text-xs text-amber-600">
                          ⚠️ Рамковий договір не створено
                          <Button
                            variant="ghost"
                            size="sm"
                            className="ml-2 text-xs h-6 text-amber-700"
                            onClick={() => {
                              // Navigate to clients tab to create MA
                              window.dispatchEvent(new CustomEvent('navigate-to-client', { 
                                detail: { clientId: matchedClient.id }
                              }));
                            }}
                          >
                            Створити →
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="text-xs text-slate-500 italic">
                    Оберіть ордер для пошуку клієнта
                  </div>
                )}
              </div>
              
              {/* === DOCUMENT GENERATION === */}
              <div className="text-xs font-medium text-slate-600 mb-2 mt-2">📄 Документи ордера:</div>
              
              {(() => {
                const hasSignedMA = matchedClient?.agreement_status === 'signed';
                const clientPayerType = matchedClient?.payer_type || 'individual';
                
                // Determine effective payer type (from selected payer or client default)
                const effectivePayerType = selectedClientPayer?.type || selectedClientPayer?.payer_type || clientPayerType;
                const isLegalEntity = ['fop', 'fop_simple', 'tov'].includes(effectivePayerType);
                
                const PAYER_TYPE_LABELS = {
                  'individual': '👤 Фіз. особа',
                  'fop': '🏪 ФОП',
                  'fop_simple': '🏪 ФОП (спрощена)',
                  'tov': '🏢 ТОВ'
                };
                
                return (
                  <div className="space-y-2">
                    {/* Payer selector if client has multiple payers */}
                    {clientPayers && clientPayers.length > 0 && (
                      <div className="p-2 bg-slate-50 rounded-lg border border-slate-200 mb-2">
                        <div className="text-[10px] text-slate-500 mb-1">Платник для документів:</div>
                        <select
                          value={selectedClientPayer?.id || ''}
                          onChange={(e) => {
                            const payer = clientPayers.find(p => p.id === parseInt(e.target.value));
                            setSelectedClientPayer(payer || null);
                          }}
                          className="w-full text-xs border border-slate-300 rounded px-2 py-1.5 bg-white"
                        >
                          <option value="">— {PAYER_TYPE_LABELS[clientPayerType]} (клієнт) —</option>
                          {clientPayers.map(p => (
                            <option key={p.id} value={p.id}>
                              {p.display_name || p.company_name} ({PAYER_TYPE_LABELS[p.type || p.payer_type]})
                              {p.is_default && ' ⭐'}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                    
                    {/* Base documents - always available */}
                    <div className="space-y-1">
                      <Button
                        variant="outline"
                        size="sm"
                        className="w-full justify-start text-xs h-8"
                        onClick={() => {
                          if (selectedOrder) {
                            window.open(`${BACKEND_URL}/api/documents/estimate/${selectedOrder.order_id}/preview`, '_blank');
                          }
                        }}
                        disabled={!selectedOrder}
                      >
                        📄 Кошторис
                      </Button>
                      
                      <Button
                        variant="outline"
                        size="sm"
                        className="w-full justify-start text-xs h-8"
                        onClick={() => {
                          if (selectedOrder) {
                            const execType = effectivePayerType === 'fop' || effectivePayerType === 'fop_simple' ? 'fop' : 'tov';
                            window.open(`${BACKEND_URL}/api/documents/invoice-offer/${selectedOrder.order_id}/preview?executor_type=${execType}`, '_blank');
                          }
                        }}
                        disabled={!selectedOrder}
                      >
                        💵 Рахунок-оферта
                      </Button>
                    </div>
                    
                    {/* Legal entity / FOP specific documents */}
                    {isLegalEntity && hasSignedMA && (
                      <div className="border-t border-slate-200 pt-2 mt-2 space-y-1">
                        <div className="text-[10px] text-slate-500 mb-1">
                          Юридичні документи ({PAYER_TYPE_LABELS[effectivePayerType]}):
                        </div>
                        
                        <Button
                          variant="outline"
                          size="sm"
                          className="w-full justify-start text-xs h-8 border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                          onClick={() => {
                            if (selectedOrder && matchedClient?.agreement_id) {
                              window.open(`${BACKEND_URL}/api/documents/annex/${selectedOrder.order_id}/preview?agreement_id=${matchedClient.agreement_id}`, '_blank');
                            }
                          }}
                          disabled={!selectedOrder || !hasSignedMA}
                        >
                          📎 Додаток до договору
                        </Button>
                        
                        <Button
                          variant="outline"
                          size="sm"
                          className="w-full justify-start text-xs h-8"
                          onClick={() => generateDocument('invoice_legal')}
                          disabled={!selectedOrder}
                        >
                          📄 Рахунок (юр. особа)
                        </Button>
                        
                        <Button
                          variant="outline"
                          size="sm"
                          className="w-full justify-start text-xs h-8"
                          onClick={() => generateDocument('service_act')}
                          disabled={!selectedOrder || !hasSignedMA}
                        >
                          📋 Акт виконаних робіт
                        </Button>
                      </div>
                    )}
                    
                    {/* Acts - always available */}
                    <div className="border-t border-slate-200 pt-2 mt-2 space-y-1">
                      <div className="text-[10px] text-slate-500 mb-1">Акти:</div>
                      
                      <Button
                        variant="ghost"
                        size="sm"
                        className="w-full justify-start text-xs h-8"
                        onClick={() => {
                          if (selectedOrder) {
                            const execType = effectivePayerType === 'fop' || effectivePayerType === 'fop_simple' ? 'fop' : 'tov';
                            window.open(`${BACKEND_URL}/api/documents/issue-act/${selectedOrder.order_id}/preview?executor_type=${execType}`, '_blank');
                          }
                        }}
                        disabled={!selectedOrder}
                      >
                        📦 Акт видачі
                      </Button>
                      
                      <Button
                        variant="ghost"
                        size="sm"
                        className="w-full justify-start text-xs h-8"
                        onClick={() => generateDocument('return_act')}
                        disabled={!selectedOrder}
                      >
                        📦 Акт повернення
                      </Button>
                      
                      <Button
                        variant="ghost"
                        size="sm"
                        className="w-full justify-start text-xs h-8"
                        onClick={() => generateDocument('defect_act')}
                        disabled={!selectedOrder}
                      >
                        ⚠️ Дефектний акт
                      </Button>
                      
                      <Button
                        variant="ghost"
                        size="sm"
                        className="w-full justify-start text-xs h-8"
                        onClick={() => generateDocument('deposit_settlement_act')}
                        disabled={!selectedOrder}
                      >
                        💰 Акт взаєморозрахунків
                      </Button>
                    </div>
                    
                    {/* Warning if FOP/TOV but no MA */}
                    {isLegalEntity && !hasSignedMA && (
                      <div className="mt-2 p-2 bg-amber-50 rounded-lg text-xs text-amber-700">
                        ⚠️ Для Додатку та Акту виконаних робіт потрібен підписаний договір.
                        <Button
                          variant="ghost"
                          size="sm"
                          className="mt-1 text-xs h-6 text-amber-700"
                          onClick={() => {
                            window.dispatchEvent(new CustomEvent('navigate-to-client', { 
                              detail: { clientId: matchedClient.id }
                            }));
                          }}
                        >
                          Перейти до клієнта →
                        </Button>
                      </div>
                    )}
                  </div>
                );
              })()}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}


// ============================================================
// COMPONENT: Deposit/Advance Button (separated)
// ============================================================
function DepositAdvanceButton({ type, orderDeposit, expectedAmount, handlePayment, saving, method }) {
  const [showForm, setShowForm] = useState(false);
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("UAH");
  const [note, setNote] = useState("");
  
  const isDeposit = type === "deposit";
  const hasDeposit = isDeposit && orderDeposit;
  
  const onSubmit = async () => {
    if (!amount || Number(amount) <= 0) return;
    
    const extraData = isDeposit ? { currency } : { note: note || "Передплата" };
    const success = await handlePayment(
      isDeposit ? "deposit_in" : "advance",
      amount,
      method,
      extraData
    );
    
    if (success) {
      setAmount("");
      setNote("");
      setShowForm(false);
    }
  };
  
  if (!showForm) {
    return (
      <div className="space-y-2">
        <Button
          variant={isDeposit ? "deposit" : "advance"}
          className="w-full"
          onClick={() => setShowForm(true)}
          disabled={saving}
        >
          {isDeposit ? "🔒 Прийняти заставу" : "💜 Прийняти передплату"}
        </Button>
        {hasDeposit && (
          <div className="text-xs text-center text-blue-600">
            Вже прийнято: {orderDeposit.display_amount || money(orderDeposit.held_amount)}
          </div>
        )}
        {isDeposit && expectedAmount > 0 && !hasDeposit && (
          <div className="text-xs text-center text-slate-500">
            Очікується: {money(expectedAmount)}
          </div>
        )}
      </div>
    );
  }
  
  return (
    <div className="p-3 rounded-xl border-2 border-dashed" style={{ borderColor: isDeposit ? "#3b82f6" : "#8b5cf6" }}>
      <div className="text-xs font-semibold mb-2" style={{ color: isDeposit ? "#3b82f6" : "#8b5cf6" }}>
        {isDeposit ? "🔒 ЗАСТАВА" : "💜 ПЕРЕДПЛАТА"}
      </div>
      
      <div className="space-y-2">
        <Input
          type="number"
          placeholder="Сума"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
        
        {isDeposit && (
          <Select
            value={currency}
            onChange={setCurrency}
            options={[
              { value: "UAH", label: "₴ UAH" },
              { value: "USD", label: "$ USD" },
              { value: "EUR", label: "€ EUR" },
            ]}
          />
        )}
        
        {!isDeposit && (
          <Input
            placeholder="Примітка (опціонально)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        )}
        
        <div className="flex gap-2">
          <Button
            variant="ghost"
            size="sm"
            className="flex-1"
            onClick={() => setShowForm(false)}
          >
            Скасувати
          </Button>
          <Button
            variant={isDeposit ? "deposit" : "advance"}
            size="sm"
            className="flex-1"
            disabled={!amount || saving}
            onClick={onSubmit}
          >
            {saving ? "..." : "Прийняти"}
          </Button>
        </div>
      </div>
    </div>
  );
}


// ============================================================
// TAB: DOCUMENTS
// ============================================================
function DocumentsTab({ orders, selectedOrderId, setSelectedOrderId, selectedOrder, documents, generateDocument, selectedPayerProfile, setSelectedPayerProfile, payerProfiles }) {
  // === State for Phase 3 Documents Engine ===
  const [activeSubTab, setActiveSubTab] = useState("documents"); // documents | agreements | annexes
  const [masterAgreements, setMasterAgreements] = useState([]);
  const [orderAnnexes, setOrderAnnexes] = useState([]);
  const [availableDocs, setAvailableDocs] = useState([]);
  const [loadingPolicy, setLoadingPolicy] = useState(false);
  const [creatingAgreement, setCreatingAgreement] = useState(false);
  const [generatingAnnex, setGeneratingAnnex] = useState(false);
  
  // === State for Document Preview Modal ===
  const [previewModal, setPreviewModal] = useState({
    isOpen: false,
    docType: null,
    orderId: null,
    payerProfileId: null,
    agreementId: null,
    annexId: null
  });
  
  const PAYER_TYPE_LABELS = {
    individual: "Фізична особа",
    fop_simple: "ФОП (спрощена)",
    fop_general: "ФОП (загальна)",
    llc_simple: "ТОВ (спрощена)",
    llc_general: "ТОВ (загальна)"
  };
  
  const STATUS_LABELS = {
    draft: { label: "Чернетка", color: "bg-slate-100 text-slate-600" },
    sent: { label: "Відправлено", color: "bg-blue-100 text-blue-700" },
    signed: { label: "Підписано", color: "bg-emerald-100 text-emerald-700" },
    expired: { label: "Закінчився", color: "bg-rose-100 text-rose-700" },
    generated: { label: "Згенеровано", color: "bg-blue-100 text-blue-700" },
  };
  
  const CATEGORY_LABELS = {
    quote: "Кошториси",
    contract: "Договори",
    annex: "Додатки",
    act: "Акти",
    finance: "Фінансові",
    operations: "Операційні"
  };
  
  // === Open Document Preview ===
  const openDocumentPreview = (docType) => {
    setPreviewModal({
      isOpen: true,
      docType,
      orderId: selectedOrderId,
      payerProfileId: selectedPayerProfile?.id,
      agreementId: masterAgreements.find(a => a.payer_profile_id === selectedPayerProfile?.id && a.status === "signed")?.id,
      annexId: orderAnnexes[0]?.id
    });
  };
  
  const closePreviewModal = () => {
    setPreviewModal(prev => ({ ...prev, isOpen: false }));
  };
  
  // === Load master agreements ===
  useEffect(() => {
    const loadAgreements = async () => {
      try {
        const res = await authFetch(`${BACKEND_URL}/api/agreements`);
        const data = await res.json();
        setMasterAgreements(data.agreements || []);
      } catch (e) {
        console.error("Failed to load agreements:", e);
      }
    };
    loadAgreements();
  }, []);
  
  // === Load annexes for selected order ===
  useEffect(() => {
    if (!selectedOrderId) {
      setOrderAnnexes([]);
      return;
    }
    const loadAnnexes = async () => {
      console.log(`[DocumentsTab] Loading annexes for order ${selectedOrderId}...`);
      try {
        const res = await authFetch(`${BACKEND_URL}/api/annexes?order_id=${selectedOrderId}`);
        const data = await res.json();
        console.log(`[DocumentsTab] Loaded ${data.annexes?.length || 0} annexes`);
        setOrderAnnexes(data.annexes || []);
      } catch (e) {
        console.error("Failed to load annexes:", e);
      }
    };
    loadAnnexes();
  }, [selectedOrderId]);
  
  // === Load available documents based on policy ===
  useEffect(() => {
    if (!selectedOrderId) {
      setAvailableDocs([]);
      return;
    }
    const loadPolicy = async () => {
      setLoadingPolicy(true);
      try {
        const res = await authFetch(`${BACKEND_URL}/api/documents/policy/available?order_id=${selectedOrderId}`);
        const data = await res.json();
        setAvailableDocs(data.documents || []);
      } catch (e) {
        console.error("Failed to load policy:", e);
      } finally {
        setLoadingPolicy(false);
      }
    };
    loadPolicy();
  }, [selectedOrderId, selectedPayerProfile]);
  
  // === Create Master Agreement ===
  const createMasterAgreement = async () => {
    if (!selectedPayerProfile) {
      alert("Виберіть профіль платника");
      return;
    }
    setCreatingAgreement(true);
    try {
      const res = await authFetch(`${BACKEND_URL}/api/agreements/create`, {
        method: "POST",
        body: JSON.stringify({
          payer_profile_id: selectedPayerProfile.id,
          template_version: "v1",
          valid_months: 12
        })
      });
      const data = await res.json();
      if (data.success) {
        alert(`Договір створено: ${data.contract_number}`);
        // Reload agreements
        const res2 = await authFetch(`${BACKEND_URL}/api/agreements`);
        const data2 = await res2.json();
        setMasterAgreements(data2.agreements || []);
      } else {
        alert(data.detail || "Помилка створення договору");
      }
    } catch (e) {
      alert("Помилка: " + e.message);
    } finally {
      setCreatingAgreement(false);
    }
  };
  
  // === Generate Annex for Order ===
  const generateAnnex = async () => {
    if (!selectedOrderId) return;
    setGeneratingAnnex(true);
    try {
      const res = await authFetch(`${BACKEND_URL}/api/annexes/generate-for-order/${selectedOrderId}`, {
        method: "POST"
      });
      const data = await res.json();
      if (data.success) {
        alert(`Додаток створено: ${data.annex_number}`);
        // Reload annexes
        const res2 = await authFetch(`${BACKEND_URL}/api/annexes?order_id=${selectedOrderId}`);
        const data2 = await res2.json();
        setOrderAnnexes(data2.annexes || []);
      } else {
        alert(data.detail || "Помилка створення додатку");
      }
    } catch (e) {
      alert("Помилка: " + e.message);
    } finally {
      setGeneratingAnnex(false);
    }
  };
  
  // === Sign Agreement ===
  const signAgreement = async (agreementId) => {
    try {
      const res = await authFetch(`${BACKEND_URL}/api/agreements/${agreementId}`, {
        method: "PUT",
        body: JSON.stringify({ status: "signed" })
      });
      const data = await res.json();
      if (data.success) {
        // Reload
        const res2 = await authFetch(`${BACKEND_URL}/api/agreements`);
        const data2 = await res2.json();
        setMasterAgreements(data2.agreements || []);
      }
    } catch (e) {
      alert("Помилка: " + e.message);
    }
  };
  
  // === Group available docs by category ===
  const docsByCategory = useMemo(() => {
    const grouped = {};
    availableDocs.forEach(doc => {
      if (!grouped[doc.category]) grouped[doc.category] = [];
      grouped[doc.category].push(doc);
    });
    return grouped;
  }, [availableDocs]);
  
  // === Render sub-tabs ===
  const subTabs = [
    { id: "documents", label: "📄 Документи" },
    { id: "agreements", label: "📋 Договори" },
    { id: "annexes", label: "📎 Додатки" }
  ];
  
  return (
    <div className="space-y-4">
      {/* Sub-tabs */}
      <div className="flex gap-2 border-b border-slate-200 pb-2">
        {subTabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveSubTab(tab.id)}
            className={cn(
              "px-4 py-2 rounded-lg text-sm font-medium transition",
              activeSubTab === tab.id 
                ? "bg-slate-900 text-white" 
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>
      
      {/* === DOCUMENTS SUB-TAB === */}
      {activeSubTab === "documents" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* Left: Order selection */}
          <div className="lg:col-span-3">
            <Card title="📋 Виберіть ордер">
              <div className="space-y-2 max-h-[500px] overflow-y-auto">
                {orders.slice(0, 50).map(o => (
                  <button
                    key={o.order_id}
                    onClick={() => setSelectedOrderId(o.order_id)}
                    className={cn(
                      "w-full rounded-lg border px-3 py-2 text-left transition text-sm",
                      o.order_id === selectedOrderId 
                        ? "border-slate-900 bg-slate-50" 
                        : "border-slate-200 hover:bg-slate-50"
                    )}
                  >
                    <div className="font-medium">#{o.order_number}</div>
                    <div className="text-xs text-slate-500">{o.customer_name}</div>
                    <div className="text-xs text-slate-400">{o.status}</div>
                  </button>
                ))}
              </div>
            </Card>
          </div>
          
          {/* Center: Policy-based document generation */}
          <div className="lg:col-span-6 space-y-4">
            {selectedOrder ? (
              <>
                {/* Order Info */}
                <Card title={`Ордер #${selectedOrder.order_number}`}>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-slate-500">Клієнт:</span> {selectedOrder.customer_name}
                    </div>
                    <div>
                      <span className="text-slate-500">Статус:</span> <Badge kind="info">{selectedOrder.status}</Badge>
                    </div>
                    <div>
                      <span className="text-slate-500">Платник:</span>{" "}
                      {selectedPayerProfile ? (
                        <span className="font-medium">{selectedPayerProfile.company_name || "Фіз. особа"}</span>
                      ) : (
                        <span className="text-slate-400">Не вибрано</span>
                      )}
                    </div>
                    {/* Contract Status Badge */}
                    <div>
                      <span className="text-slate-500">Договір:</span>{" "}
                      {(() => {
                        const agreement = masterAgreements.find(a => 
                          a.payer_profile_id === selectedPayerProfile?.id && a.status === "signed"
                        );
                        if (!agreement) {
                          return <span className="text-slate-400">—</span>;
                        }
                        const today = new Date();
                        const validUntil = agreement.valid_until ? new Date(agreement.valid_until) : null;
                        const daysUntilExpiry = validUntil ? Math.ceil((validUntil - today) / (1000 * 60 * 60 * 24)) : null;
                        
                        if (daysUntilExpiry !== null && daysUntilExpiry < 0) {
                          return <span className="px-2 py-0.5 bg-rose-100 text-rose-700 text-xs rounded-full">🔴 закінч.</span>;
                        } else if (daysUntilExpiry !== null && daysUntilExpiry <= 30) {
                          return <span className="px-2 py-0.5 bg-amber-100 text-amber-700 text-xs rounded-full">⚠️ {daysUntilExpiry}дн.</span>;
                        } else {
                          return <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs rounded-full">✅ активн.</span>;
                        }
                      })()}
                    </div>
                  </div>
                  
                  {/* Payer Profile Selection */}
                  {!selectedPayerProfile && payerProfiles.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-slate-100">
                      <div className="text-xs font-semibold text-slate-500 mb-2">Виберіть платника:</div>
                      <div className="flex flex-wrap gap-2">
                        {payerProfiles.slice(0, 4).map(p => (
                          <button
                            key={p.id}
                            onClick={() => setSelectedPayerProfile(p)}
                            className="px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-xs"
                          >
                            {p.company_name} ({PAYER_TYPE_LABELS[p.payer_type]})
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  {selectedPayerProfile && (
                    <div className="mt-4 pt-4 border-t border-slate-100 flex items-center justify-between">
                      <div className="text-sm">
                        <span className="font-medium">{selectedPayerProfile.company_name}</span>
                        <span className="text-slate-500 ml-2">{PAYER_TYPE_LABELS[selectedPayerProfile.payer_type]}</span>
                      </div>
                      <Button variant="ghost" size="sm" onClick={() => setSelectedPayerProfile(null)}>
                        Змінити
                      </Button>
                    </div>
                  )}
                </Card>
                
                {/* Available Documents by Category */}
                {loadingPolicy ? (
                  <Card><div className="text-center py-4 text-slate-500">Завантаження...</div></Card>
                ) : (
                  Object.entries(docsByCategory).map(([category, docs]) => (
                    <Card key={category} title={CATEGORY_LABELS[category] || category}>
                      <div className="grid grid-cols-2 gap-2">
                        {docs.map(doc => (
                          <button
                            key={doc.doc_type}
                            onClick={() => doc.available && openDocumentPreview(doc.doc_type)}
                            disabled={!doc.available}
                            data-testid={`doc-btn-${doc.doc_type}`}
                            className={cn(
                              "p-3 rounded-lg border text-left text-sm transition",
                              doc.available 
                                ? "border-slate-200 hover:bg-slate-50 hover:border-slate-300" 
                                : "border-slate-100 bg-slate-50 opacity-50 cursor-not-allowed"
                            )}
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <span>{doc.is_legal ? "⚖️" : "📄"}</span>
                                <span className="font-medium">{doc.name}</span>
                              </div>
                              {doc.available && (
                                <span className="text-xs text-blue-600">👁️ Перегляд</span>
                              )}
                            </div>
                            {!doc.available && doc.reason && (
                              <div className="text-xs text-rose-500 mt-1">{doc.reason}</div>
                            )}
                            {doc.warnings && doc.warnings.length > 0 && (
                              <div className="text-xs text-amber-600 mt-1">{doc.warnings[0]}</div>
                            )}
                          </button>
                        ))}
                      </div>
                    </Card>
                  ))
                )}
              </>
            ) : (
              <Card>
                <div className="text-center text-slate-500 py-8">Виберіть ордер для генерації документів</div>
              </Card>
            )}
          </div>
          
          {/* Right: Recent documents */}
          <div className="lg:col-span-3">
            <Card title="📜 Останні документи">
              {documents.length > 0 ? (
                <div className="space-y-2">
                  {documents.map(doc => (
                    <div key={doc.id} className="p-2 bg-slate-50 rounded-lg text-sm">
                      <div className="font-medium">{doc.doc_type}</div>
                      <div className="text-xs text-slate-500">v{doc.version} · {fmtDateShort(doc.created_at)}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-slate-500">Документів поки немає</div>
              )}
            </Card>
          </div>
        </div>
      )}
      
      {/* Document Preview Modal */}
      <DocumentPreviewModal
        isOpen={previewModal.isOpen}
        onClose={closePreviewModal}
        docType={previewModal.docType}
        orderId={previewModal.orderId}
        payerProfileId={previewModal.payerProfileId}
        agreementId={previewModal.agreementId}
        annexId={previewModal.annexId}
        onDocumentGenerated={(data) => console.log("Document generated:", data)}
        onDocumentSigned={(data) => console.log("Document signed:", data)}
      />
      
      {/* === AGREEMENTS SUB-TAB === */}
      {activeSubTab === "agreements" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* Left: Create new agreement */}
          <div className="lg:col-span-4">
            <Card title="➕ Новий рамковий договір">
              <div className="space-y-4">
                <div className="text-sm text-slate-600">
                  Рамковий договір діє 12 місяців. Всі додатки (Annexes) посилаються на нього.
                </div>
                
                {selectedPayerProfile ? (
                  <div className="p-3 bg-slate-50 rounded-xl">
                    <div className="text-sm font-semibold">{selectedPayerProfile.company_name || "Фіз. особа"}</div>
                    <div className="text-xs text-slate-500">{PAYER_TYPE_LABELS[selectedPayerProfile.payer_type]}</div>
                    {selectedPayerProfile.edrpou && <div className="text-xs text-slate-500">ЄДРПОУ: {selectedPayerProfile.edrpou}</div>}
                    <Button variant="ghost" size="sm" className="mt-2" onClick={() => setSelectedPayerProfile(null)}>
                      Змінити платника
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <div className="text-xs text-slate-500">Виберіть платника:</div>
                    <div className="grid grid-cols-1 gap-2 max-h-[300px] overflow-y-auto">
                      {payerProfiles.map(p => (
                        <button
                          key={p.id}
                          onClick={() => setSelectedPayerProfile(p)}
                          className="text-left p-2 rounded-lg border border-slate-200 hover:bg-slate-50 text-sm"
                        >
                          <div className="font-medium truncate">{p.company_name}</div>
                          <div className="text-xs text-slate-500">{PAYER_TYPE_LABELS[p.payer_type]}</div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                
                <Button 
                  onClick={createMasterAgreement} 
                  disabled={!selectedPayerProfile || creatingAgreement}
                  className="w-full"
                >
                  {creatingAgreement ? "Створення..." : "📋 Створити договір"}
                </Button>
              </div>
            </Card>
          </div>
          
          {/* Right: Agreements list */}
          <div className="lg:col-span-8">
            <Card title="📋 Рамкові договори">
              {masterAgreements.length > 0 ? (
                <div className="space-y-3">
                  {masterAgreements.map(a => {
                    // Calculate expiration status
                    const today = new Date();
                    const validUntil = a.valid_until ? new Date(a.valid_until) : null;
                    let expirationStatus = null;
                    let daysUntilExpiry = null;
                    
                    if (validUntil && a.status === "signed") {
                      daysUntilExpiry = Math.ceil((validUntil - today) / (1000 * 60 * 60 * 24));
                      if (daysUntilExpiry < 0) {
                        expirationStatus = "expired";
                      } else if (daysUntilExpiry <= 30) {
                        expirationStatus = "warning";
                      } else {
                        expirationStatus = "active";
                      }
                    }
                    
                    return (
                    <div key={a.id} className="p-4 bg-slate-50 rounded-xl">
                      {/* Expiration Banner */}
                      {expirationStatus === "expired" && (
                        <div className="mb-3 p-3 bg-rose-100 border border-rose-200 rounded-lg">
                          <div className="flex items-center gap-2 text-rose-700">
                            <span className="text-lg">🔴</span>
                            <div>
                              <div className="font-semibold">Договір закінчився</div>
                              <div className="text-sm">Створення додатків заблоковано. Оновіть або створіть новий договір.</div>
                            </div>
                          </div>
                          <button 
                            onClick={() => {/* TODO: Open create agreement modal */}}
                            className="mt-2 px-4 py-1.5 bg-rose-600 text-white text-sm rounded-lg hover:bg-rose-700"
                          >
                            ➕ Створити новий договір
                          </button>
                        </div>
                      )}
                      
                      {expirationStatus === "warning" && (
                        <div className="mb-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                          <div className="flex items-center gap-2 text-amber-700">
                            <span className="text-lg">⚠️</span>
                            <div>
                              <div className="font-semibold">Договір закінчується через {daysUntilExpiry} {daysUntilExpiry === 1 ? 'день' : daysUntilExpiry < 5 ? 'дні' : 'днів'}</div>
                              <div className="text-sm">Рекомендуємо завчасно продовжити договір.</div>
                            </div>
                          </div>
                        </div>
                      )}
                      
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-lg">{a.contract_number}</span>
                            {/* Expiration Badge */}
                            {expirationStatus === "active" && (
                              <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs rounded-full">✅ активний</span>
                            )}
                            {expirationStatus === "warning" && (
                              <span className="px-2 py-0.5 bg-amber-100 text-amber-700 text-xs rounded-full">⚠️ {daysUntilExpiry} дн.</span>
                            )}
                            {expirationStatus === "expired" && (
                              <span className="px-2 py-0.5 bg-rose-100 text-rose-700 text-xs rounded-full">🔴 закінчився</span>
                            )}
                          </div>
                          <div className="text-sm text-slate-600">{a.payer?.company_name || "—"}</div>
                          <div className="text-xs text-slate-500">
                            {PAYER_TYPE_LABELS[a.payer?.payer_type] || "—"}
                          </div>
                        </div>
                        <span className={cn(
                          "px-2 py-1 rounded-full text-xs font-medium",
                          STATUS_LABELS[a.status]?.color || "bg-slate-100"
                        )}>
                          {STATUS_LABELS[a.status]?.label || a.status}
                        </span>
                      </div>
                      
                      <div className="mt-3 grid grid-cols-3 gap-4 text-sm">
                        <div>
                          <span className="text-slate-500">Дійсний з:</span>{" "}
                          {a.valid_from ? fmtDateShort(a.valid_from) : "—"}
                        </div>
                        <div>
                          <span className="text-slate-500">До:</span>{" "}
                          {a.valid_until ? fmtDateShort(a.valid_until) : "—"}
                        </div>
                        <div>
                          <span className="text-slate-500">Підписано:</span>{" "}
                          {a.signed_at ? fmtDateShort(a.signed_at) : "—"}
                        </div>
                      </div>
                      
                      {a.status === "draft" && (
                        <div className="mt-3 flex gap-2">
                          <Button size="sm" variant="ghost" onClick={() => signAgreement(a.id)}>
                            ✅ Позначити підписаним
                          </Button>
                        </div>
                      )}
                    </div>
                  )})}
                </div>
              ) : (
                <div className="text-center text-slate-500 py-8">
                  Договорів поки немає. Створіть перший рамковий договір.
                </div>
              )}
            </Card>
          </div>
        </div>
      )}
      
      {/* === ANNEXES SUB-TAB === */}
      {activeSubTab === "annexes" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          {/* Left: Order selection */}
          <div className="lg:col-span-3">
            <Card title="📋 Виберіть ордер">
              <div className="space-y-2 max-h-[500px] overflow-y-auto">
                {orders.slice(0, 50).map(o => (
                  <button
                    key={o.order_id}
                    onClick={() => setSelectedOrderId(o.order_id)}
                    className={cn(
                      "w-full rounded-lg border px-3 py-2 text-left transition text-sm",
                      o.order_id === selectedOrderId 
                        ? "border-slate-900 bg-slate-50" 
                        : "border-slate-200 hover:bg-slate-50"
                    )}
                  >
                    <div className="font-medium">#{o.order_number}</div>
                    <div className="text-xs text-slate-500">{o.customer_name}</div>
                    <div className="text-xs text-slate-400">{o.status}</div>
                  </button>
                ))}
              </div>
            </Card>
          </div>
          
          {/* Center: Generate annex */}
          <div className="lg:col-span-5">
            <Card title="📎 Додатки до договору">
              {selectedOrder ? (
                <div className="space-y-4">
                  <div className="text-sm">
                    Ордер: <span className="font-semibold">#{selectedOrder.order_number}</span> · {selectedOrder.customer_name}
                  </div>
                  
                  <div className="p-4 bg-blue-50 rounded-xl text-sm text-blue-800">
                    <strong>Додаток (Annex)</strong> — юридичний документ, що описує конкретну оренду. 
                    Після генерації стає immutable (snapshot даних).
                  </div>
                  
                  <Button 
                    onClick={generateAnnex} 
                    disabled={generatingAnnex}
                    className="w-full"
                  >
                    {generatingAnnex ? "Генерація..." : "📎 Згенерувати Додаток"}
                  </Button>
                </div>
              ) : (
                <div className="text-center text-slate-500 py-8">
                  Виберіть ордер для створення додатку
                </div>
              )}
            </Card>
          </div>
          
          {/* Right: Annexes list */}
          <div className="lg:col-span-4">
            <Card title="📜 Історія додатків">
              {orderAnnexes.length > 0 ? (
                <div className="space-y-2">
                  {orderAnnexes.map(annex => (
                    <div key={annex.id} className="p-3 bg-slate-50 rounded-lg">
                      <div className="flex items-center justify-between">
                        <div className="font-medium">{annex.annex_number}</div>
                        <span className={cn(
                          "px-2 py-0.5 rounded-full text-xs",
                          STATUS_LABELS[annex.status]?.color || "bg-slate-100"
                        )}>
                          {STATUS_LABELS[annex.status]?.label || annex.status}
                        </span>
                      </div>
                      <div className="text-xs text-slate-500 mt-1">
                        v{annex.version} · {fmtDateShort(annex.created_at)}
                      </div>
                      <div className="text-xs text-slate-400">
                        Договір: {annex.contract_number || "—"}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-slate-500">
                  {selectedOrderId ? "Додатків для цього ордера немає" : "Виберіть ордер"}
                </div>
              )}
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}


// ============================================================
// TAB: CASH
// ============================================================
function CashTab({ payoutsStats, depositsByCurrency, handleAddExpense, saving, refreshAll }) {
  const [showExpenseForm, setShowExpenseForm] = useState(false);
  const [expenseCategory, setExpenseCategory] = useState("rent_cash");
  const [expenseAmount, setExpenseAmount] = useState("");
  const [expenseDesc, setExpenseDesc] = useState("");
  const [operationType, setOperationType] = useState("expense");
  
  const onAddExpense = async () => {
    const success = await handleAddExpense(expenseCategory, expenseAmount, expenseDesc, operationType);
    if (success) {
      setExpenseAmount("");
      setExpenseDesc("");
      setShowExpenseForm(false);
    }
  };
  
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {/* Cash Balance */}
      <Card title="💵 Готівка">
        <div className="space-y-4">
          <div>
            <div className="text-xs text-slate-500 mb-1">Оренда</div>
            <div className="text-2xl font-bold text-emerald-600">{money(payoutsStats?.rent_cash_balance || 0)}</div>
            {payoutsStats?.rent_cash_expenses > 0 && (
              <div className="text-xs text-rose-600">Витрачено: -{money(payoutsStats.rent_cash_expenses)}</div>
            )}
          </div>
          
          <div>
            <div className="text-xs text-slate-500 mb-1">Шкода</div>
            <div className="text-2xl font-bold text-amber-600">{money(payoutsStats?.damage_cash_balance || 0)}</div>
            {payoutsStats?.damage_cash_expenses > 0 && (
              <div className="text-xs text-rose-600">Витрачено: -{money(payoutsStats.damage_cash_expenses)}</div>
            )}
          </div>
          
          <div className="pt-3 border-t border-slate-200">
            <div className="text-xs text-slate-500 mb-1">Всього готівки</div>
            <div className="text-3xl font-bold">{money(payoutsStats?.total_cash_balance || 0)}</div>
          </div>
        </div>
      </Card>
      
      {/* Bank Balance */}
      <Card title="🏦 Безготівка">
        <div className="space-y-4">
          <div>
            <div className="text-xs text-slate-500 mb-1">Оренда</div>
            <div className="text-2xl font-bold text-blue-600">{money(payoutsStats?.rent_bank_balance || 0)}</div>
          </div>
          
          <div>
            <div className="text-xs text-slate-500 mb-1">Шкода</div>
            <div className="text-2xl font-bold text-blue-500">{money(payoutsStats?.damage_bank_balance || 0)}</div>
          </div>
          
          <div className="pt-3 border-t border-slate-200">
            <div className="text-xs text-slate-500 mb-1">Всього безготівки</div>
            <div className="text-3xl font-bold text-blue-600">{money(payoutsStats?.bank_balance || 0)}</div>
          </div>
        </div>
      </Card>
      
      {/* Deposits */}
      <Card title="🔒 Застави (холд)">
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-slate-600">₴ UAH</span>
            <span className="text-xl font-bold">{depositsByCurrency.UAH.toLocaleString()}</span>
          </div>
          {depositsByCurrency.USD > 0 && (
            <div className="flex justify-between items-center">
              <span className="text-slate-600">$ USD</span>
              <span className="text-xl font-bold">{depositsByCurrency.USD.toFixed(0)}</span>
            </div>
          )}
          {depositsByCurrency.EUR > 0 && (
            <div className="flex justify-between items-center">
              <span className="text-slate-600">€ EUR</span>
              <span className="text-xl font-bold">{depositsByCurrency.EUR.toFixed(0)}</span>
            </div>
          )}
        </div>
      </Card>
      
      {/* Add expense/deposit */}
      <Card title="➕ Додати операцію" className="lg:col-span-3">
        {!showExpenseForm ? (
          <div className="flex gap-3">
            <Button onClick={() => { setOperationType("expense"); setShowExpenseForm(true); }}>
              📉 Витрата
            </Button>
            <Button variant="success" onClick={() => { setOperationType("deposit"); setShowExpenseForm(true); }}>
              📥 Внесення
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
            <div>
              <div className="text-xs text-slate-500 mb-1">Категорія</div>
              <Select
                value={expenseCategory}
                onChange={setExpenseCategory}
                options={[
                  { value: "rent_cash", label: "Оренда (готівка)" },
                  { value: "damage_cash", label: "Шкода (готівка)" },
                  { value: "rent_bank", label: "Оренда (банк)" },
                  { value: "damage_bank", label: "Шкода (банк)" },
                ]}
              />
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-1">Сума</div>
              <Input
                type="number"
                placeholder="0"
                value={expenseAmount}
                onChange={(e) => setExpenseAmount(e.target.value)}
              />
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-1">Опис</div>
              <Input
                placeholder="Опис операції"
                value={expenseDesc}
                onChange={(e) => setExpenseDesc(e.target.value)}
              />
            </div>
            <div className="flex items-end gap-2">
              <Button
                variant={operationType === "expense" ? "danger" : "success"}
                disabled={!expenseAmount || !expenseDesc || saving}
                onClick={onAddExpense}
              >
                {saving ? "..." : operationType === "expense" ? "Витрата" : "Внесення"}
              </Button>
              <Button variant="ghost" onClick={() => setShowExpenseForm(false)}>✕</Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}


// ============================================================
// TAB: FORECAST
// ============================================================
function ForecastTab({ orders }) {
  const forecast = useMemo(() => {
    const upcoming = orders
      .filter(o => o.status !== "completed" && o.status !== "cancelled")
      .map(o => ({
        ...o,
        rentDue: Math.max(0, (o.total_rental || 0) - (o.rent_paid || 0)),
        depositExpected: Math.max(0, (o.total_deposit || 0) - (o.deposit_held || 0))
      }))
      .filter(o => o.rentDue > 0 || o.depositExpected > 0)
      .sort((a, b) => new Date(a.rental_start_date) - new Date(b.rental_start_date));
    
    const totalRentExpected = upcoming.reduce((s, o) => s + o.rentDue, 0);
    const totalDepositExpected = upcoming.reduce((s, o) => s + o.depositExpected, 0);
    
    return { upcoming, totalRentExpected, totalDepositExpected };
  }, [orders]);
  
  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <div className="text-center">
            <div className="text-xs text-slate-500">Очікується оренди</div>
            <div className="text-2xl font-bold text-emerald-600">{money(forecast.totalRentExpected)}</div>
          </div>
        </Card>
        <Card>
          <div className="text-center">
            <div className="text-xs text-slate-500">Очікується застав</div>
            <div className="text-2xl font-bold text-blue-600">{money(forecast.totalDepositExpected)}</div>
          </div>
        </Card>
        <Card>
          <div className="text-center">
            <div className="text-xs text-slate-500">Всього очікується</div>
            <div className="text-2xl font-bold">{money(forecast.totalRentExpected + forecast.totalDepositExpected)}</div>
          </div>
        </Card>
      </div>
      
      {/* Upcoming orders */}
      <Card title="📅 Очікувані надходження">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="text-left py-2 px-2">Ордер</th>
                <th className="text-left py-2 px-2">Клієнт</th>
                <th className="text-left py-2 px-2">Дата</th>
                <th className="text-right py-2 px-2">Оренда</th>
                <th className="text-right py-2 px-2">Застава</th>
                <th className="text-right py-2 px-2">Всього</th>
              </tr>
            </thead>
            <tbody>
              {forecast.upcoming.map(o => (
                <tr key={o.order_id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="py-2 px-2 font-medium">#{o.order_number}</td>
                  <td className="py-2 px-2">{o.customer_name}</td>
                  <td className="py-2 px-2">{fmtDateShort(o.rental_start_date)}</td>
                  <td className="py-2 px-2 text-right text-emerald-600 font-medium">{o.rentDue > 0 ? money(o.rentDue) : "—"}</td>
                  <td className="py-2 px-2 text-right text-blue-600 font-medium">{o.depositExpected > 0 ? money(o.depositExpected) : "—"}</td>
                  <td className="py-2 px-2 text-right font-bold">{money(o.rentDue + o.depositExpected)}</td>
                </tr>
              ))}
              {forecast.upcoming.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-500">Немає очікуваних надходжень</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}


// ============================================================
// TAB: EXPENSES
// ============================================================
function ExpensesTab({ allExpenses, handleAddExpense, saving, refreshAll }) {
  const [showForm, setShowForm] = useState(false);
  const [category, setCategory] = useState("rent_cash");
  const [amount, setAmount] = useState("");
  const [desc, setDesc] = useState("");
  
  const expensesByCategory = useMemo(() => {
    const groups = {};
    allExpenses.forEach(e => {
      const cat = e.category || "OTHER";
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(e);
    });
    return groups;
  }, [allExpenses]);
  
  const categoryLabels = {
    RENT_CASH_EXPENSE: "Витрати готівка (оренда)",
    DAMAGE_EXPENSE: "Витрати готівка (шкода)",
    RENT_BANK_EXPENSE: "Витрати банк (оренда)",
    DAMAGE_BANK_EXPENSE: "Витрати банк (шкода)",
    RENT_CASH_DEPOSIT: "Внесення готівка (оренда)",
    DAMAGE_CASH_DEPOSIT: "Внесення готівка (шкода)",
    OTHER: "Інше"
  };
  
  return (
    <div className="space-y-4">
      {/* Add expense button */}
      <div className="flex justify-end">
        <Button onClick={() => setShowForm(true)}>➕ Додати витрату</Button>
      </div>
      
      {/* Add form */}
      {showForm && (
        <Card title="Нова витрата">
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
            <Select
              value={category}
              onChange={setCategory}
              options={[
                { value: "rent_cash", label: "Оренда (готівка)" },
                { value: "damage_cash", label: "Шкода (готівка)" },
                { value: "rent_bank", label: "Оренда (банк)" },
                { value: "damage_bank", label: "Шкода (банк)" },
              ]}
            />
            <Input type="number" placeholder="Сума" value={amount} onChange={(e) => setAmount(e.target.value)} />
            <Input placeholder="Опис" value={desc} onChange={(e) => setDesc(e.target.value)} />
            <div className="flex gap-2">
              <Button
                disabled={!amount || !desc || saving}
                onClick={async () => {
                  const success = await handleAddExpense(category, amount, desc, "expense");
                  if (success) {
                    setAmount("");
                    setDesc("");
                    setShowForm(false);
                  }
                }}
              >
                {saving ? "..." : "Додати"}
              </Button>
              <Button variant="ghost" onClick={() => setShowForm(false)}>✕</Button>
            </div>
          </div>
        </Card>
      )}
      
      {/* Expenses list */}
      <Card title="📉 Історія витрат">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="text-left py-2 px-2">Дата</th>
                <th className="text-left py-2 px-2">Категорія</th>
                <th className="text-left py-2 px-2">Опис</th>
                <th className="text-right py-2 px-2">Сума</th>
              </tr>
            </thead>
            <tbody>
              {allExpenses.slice(0, 50).map(e => (
                <tr key={e.id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="py-2 px-2">{fmtDateShort(e.created_at)}</td>
                  <td className="py-2 px-2">
                    <Badge kind={e.expense_type === "income" ? "ok" : "warn"}>
                      {categoryLabels[e.category] || e.category}
                    </Badge>
                  </td>
                  <td className="py-2 px-2">{e.description}</td>
                  <td className={cn("py-2 px-2 text-right font-medium", e.expense_type === "income" ? "text-emerald-600" : "text-rose-600")}>
                    {e.expense_type === "income" ? "+" : "-"}{money(e.amount)}
                  </td>
                </tr>
              ))}
              {allExpenses.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-8 text-center text-slate-500">Немає витрат</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}


// ============================================================
// TAB: DEPOSITS
// ============================================================
function DepositsTab({ deposits, depositsByCurrency }) {
  const activeDeposits = useMemo(() => {
    return deposits
      .filter(d => d.status === "holding" || d.status === "partially_used")
      .sort((a, b) => new Date(b.opened_at) - new Date(a.opened_at));
  }, [deposits]);
  
  const closedDeposits = useMemo(() => {
    return deposits
      .filter(d => d.status === "refunded" || d.status === "fully_used")
      .sort((a, b) => new Date(b.closed_at) - new Date(a.closed_at));
  }, [deposits]);
  
  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <div className="text-center">
            <div className="text-xs text-slate-500">₴ UAH</div>
            <div className="text-2xl font-bold">{depositsByCurrency.UAH.toLocaleString()}</div>
          </div>
        </Card>
        <Card>
          <div className="text-center">
            <div className="text-xs text-slate-500">$ USD</div>
            <div className="text-2xl font-bold">{depositsByCurrency.USD.toFixed(0)}</div>
          </div>
        </Card>
        <Card>
          <div className="text-center">
            <div className="text-xs text-slate-500">€ EUR</div>
            <div className="text-2xl font-bold">{depositsByCurrency.EUR.toFixed(0)}</div>
          </div>
        </Card>
      </div>
      
      {/* Active deposits */}
      <Card title="🔒 Активні застави" right={<Badge kind="pending">{activeDeposits.length}</Badge>}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="text-left py-2 px-2">Ордер</th>
                <th className="text-left py-2 px-2">Клієнт</th>
                <th className="text-right py-2 px-2">Прийнято</th>
                <th className="text-right py-2 px-2">Використано</th>
                <th className="text-right py-2 px-2">Доступно</th>
                <th className="text-left py-2 px-2">Статус</th>
              </tr>
            </thead>
            <tbody>
              {activeDeposits.map(d => (
                <tr key={d.id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="py-2 px-2 font-medium">#{d.order_number}</td>
                  <td className="py-2 px-2">{d.customer_name}</td>
                  <td className="py-2 px-2 text-right">{d.display_amount}</td>
                  <td className="py-2 px-2 text-right text-rose-600">{d.used_amount > 0 ? money(d.used_amount) : "—"}</td>
                  <td className="py-2 px-2 text-right font-bold text-emerald-600">{money(d.available)}</td>
                  <td className="py-2 px-2"><Badge kind="pending">{d.status}</Badge></td>
                </tr>
              ))}
              {activeDeposits.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-500">Немає активних застав</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
      
      {/* Closed deposits */}
      <Card title="📜 Закриті застави" right={<Badge kind="ok">{closedDeposits.length}</Badge>}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="text-left py-2 px-2">Ордер</th>
                <th className="text-left py-2 px-2">Клієнт</th>
                <th className="text-right py-2 px-2">Було</th>
                <th className="text-right py-2 px-2">Використано</th>
                <th className="text-right py-2 px-2">Повернуто</th>
                <th className="text-left py-2 px-2">Статус</th>
              </tr>
            </thead>
            <tbody>
              {closedDeposits.slice(0, 20).map(d => (
                <tr key={d.id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="py-2 px-2 font-medium">#{d.order_number}</td>
                  <td className="py-2 px-2">{d.customer_name}</td>
                  <td className="py-2 px-2 text-right">{d.display_amount}</td>
                  <td className="py-2 px-2 text-right text-rose-600">{d.used_amount > 0 ? money(d.used_amount) : "—"}</td>
                  <td className="py-2 px-2 text-right text-blue-600">{d.refunded_amount > 0 ? money(d.refunded_amount) : "—"}</td>
                  <td className="py-2 px-2"><Badge kind="ok">{d.status}</Badge></td>
                </tr>
              ))}
              {closedDeposits.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-500">Немає закритих застав</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}


// ============================================================
// TAB: ANALYTICS
// ============================================================
function AnalyticsTab({ orders, payoutsStats, deposits, orderStats }) {
  const analytics = useMemo(() => {
    const totalRevenue = (payoutsStats?.total_cash_balance || 0) + (payoutsStats?.bank_balance || 0);
    const totalDeposits = deposits.reduce((s, d) => s + (d.held_amount || 0), 0);
    const avgOrderValue = orders.length > 0 ? orders.reduce((s, o) => s + (o.total_rental || 0), 0) / orders.length : 0;
    const paidRate = orderStats.total > 0 ? (orderStats.paid / orderStats.total * 100).toFixed(1) : 0;
    
    return { totalRevenue, totalDeposits, avgOrderValue, paidRate };
  }, [orders, payoutsStats, deposits, orderStats]);
  
  return (
    <div className="space-y-4">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <div className="text-center">
            <div className="text-xs text-slate-500">Загальний дохід</div>
            <div className="text-2xl font-bold text-emerald-600">{money(analytics.totalRevenue)}</div>
          </div>
        </Card>
        <Card>
          <div className="text-center">
            <div className="text-xs text-slate-500">Застави в холді</div>
            <div className="text-2xl font-bold text-blue-600">{money(analytics.totalDeposits)}</div>
          </div>
        </Card>
        <Card>
          <div className="text-center">
            <div className="text-xs text-slate-500">Середній чек</div>
            <div className="text-2xl font-bold">{money(analytics.avgOrderValue)}</div>
          </div>
        </Card>
        <Card>
          <div className="text-center">
            <div className="text-xs text-slate-500">% оплачених</div>
            <div className="text-2xl font-bold text-violet-600">{analytics.paidRate}%</div>
          </div>
        </Card>
      </div>
      
      {/* Revenue breakdown */}
      <Card title="💰 Розбивка доходу">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-sm font-medium text-slate-600 mb-3">Готівка</div>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Оренда</span>
                <span className="font-semibold text-emerald-600">{money(payoutsStats?.rent_cash_balance || 0)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span>Шкода</span>
                <span className="font-semibold text-amber-600">{money(payoutsStats?.damage_cash_balance || 0)}</span>
              </div>
              <div className="flex justify-between text-sm pt-2 border-t border-slate-200">
                <span className="font-medium">Всього</span>
                <span className="font-bold">{money(payoutsStats?.total_cash_balance || 0)}</span>
              </div>
            </div>
          </div>
          
          <div>
            <div className="text-sm font-medium text-slate-600 mb-3">Безготівка</div>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Оренда</span>
                <span className="font-semibold text-blue-600">{money(payoutsStats?.rent_bank_balance || 0)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span>Шкода</span>
                <span className="font-semibold text-blue-500">{money(payoutsStats?.damage_bank_balance || 0)}</span>
              </div>
              <div className="flex justify-between text-sm pt-2 border-t border-slate-200">
                <span className="font-medium">Всього</span>
                <span className="font-bold">{money(payoutsStats?.bank_balance || 0)}</span>
              </div>
            </div>
          </div>
        </div>
      </Card>
      
      {/* Order stats */}
      <Card title="📊 Статистика ордерів">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-3xl font-bold">{orderStats.total}</div>
            <div className="text-sm text-slate-500">Всього ордерів</div>
          </div>
          <div>
            <div className="text-3xl font-bold text-emerald-600">{orderStats.paid}</div>
            <div className="text-sm text-slate-500">Оплачено</div>
          </div>
          <div>
            <div className="text-3xl font-bold text-amber-600">{orderStats.withDebt}</div>
            <div className="text-sm text-slate-500">З боргом</div>
          </div>
        </div>
      </Card>
    </div>
  );
}


// ============================================================
// TAB: REGISTRY (read-only архів документів)
// ============================================================
function RegistryTab({ orders, documents, payerProfiles }) {
  const [search, setSearch] = useState("");
  const [filterType, setFilterType] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");
  const [masterAgreements, setMasterAgreements] = useState([]);
  const [annexes, setAnnexes] = useState([]);
  
  // Load all agreements and annexes on mount
  useEffect(() => {
    const loadData = async () => {
      try {
        const [agRes, anRes] = await Promise.all([
          authFetch(`${BACKEND_URL}/api/agreements`),
          authFetch(`${BACKEND_URL}/api/annexes`)
        ]);
        const agData = await agRes.json();
        const anData = await anRes.json();
        setMasterAgreements(agData.agreements || []);
        setAnnexes(anData.annexes || []);
      } catch (e) {
        console.error("Registry load error:", e);
      }
    };
    loadData();
  }, []);
  
  const DOC_TYPES = [
    { value: "all", label: "Всі типи" },
    { value: "master_agreement", label: "Рамкові договори" },
    { value: "annex", label: "Додатки" },
    { value: "invoice", label: "Рахунки" },
    { value: "act", label: "Акти" }
  ];
  
  const STATUSES = [
    { value: "all", label: "Всі статуси" },
    { value: "draft", label: "Чернетка" },
    { value: "signed", label: "Підписано" },
    { value: "expired", label: "Закінчився" }
  ];
  
  // Combine all documents
  const allDocuments = useMemo(() => {
    const docs = [];
    
    // Master agreements
    masterAgreements.forEach(ma => {
      docs.push({
        id: `ma-${ma.id}`,
        type: "master_agreement",
        number: ma.contract_number,
        date: ma.created_at,
        status: ma.status,
        payer: ma.payer?.company_name || "—",
        payerId: ma.payer_profile_id,
        orderId: null,
        validUntil: ma.valid_until
      });
    });
    
    // Annexes
    annexes.forEach(an => {
      docs.push({
        id: `an-${an.id}`,
        type: "annex",
        number: an.annex_number,
        date: an.created_at,
        status: an.status,
        payer: "—",
        payerId: an.payer_profile_id,
        orderId: an.order_id,
        validUntil: null
      });
    });
    
    return docs.sort((a, b) => new Date(b.date) - new Date(a.date));
  }, [masterAgreements, annexes]);
  
  // Filtered documents
  const filtered = useMemo(() => {
    return allDocuments.filter(doc => {
      // Type filter
      if (filterType !== "all" && doc.type !== filterType) return false;
      // Status filter
      if (filterStatus !== "all" && doc.status !== filterStatus) return false;
      // Search
      if (search) {
        const s = search.toLowerCase();
        if (!doc.number?.toLowerCase().includes(s) && 
            !doc.payer?.toLowerCase().includes(s)) return false;
      }
      return true;
    });
  }, [allDocuments, filterType, filterStatus, search]);
  
  const getStatusBadge = (status) => {
    const styles = {
      draft: "bg-slate-100 text-slate-600",
      signed: "bg-emerald-100 text-emerald-700",
      expired: "bg-rose-100 text-rose-600",
      sent: "bg-blue-100 text-blue-700"
    };
    const labels = {
      draft: "Чернетка",
      signed: "Підписано",
      expired: "Закінчився",
      sent: "Відправлено"
    };
    return (
      <span className={cn("text-xs px-2 py-0.5 rounded-full", styles[status] || "bg-slate-100")}>
        {labels[status] || status}
      </span>
    );
  };
  
  const getTypeBadge = (type) => {
    const styles = {
      master_agreement: "bg-purple-100 text-purple-700",
      annex: "bg-blue-100 text-blue-700",
      invoice: "bg-amber-100 text-amber-700",
      act: "bg-slate-100 text-slate-600"
    };
    const labels = {
      master_agreement: "📋 Рамковий",
      annex: "📎 Додаток",
      invoice: "📄 Рахунок",
      act: "📝 Акт"
    };
    return (
      <span className={cn("text-xs px-2 py-0.5 rounded-full", styles[type] || "bg-slate-100")}>
        {labels[type] || type}
      </span>
    );
  };
  
  return (
    <div className="space-y-4">
      {/* Header */}
      <Card>
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1">
            <Input
              type="search"
              placeholder="🔍 Пошук: номер, платник..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <select
            className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-sm"
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
          >
            {DOC_TYPES.map(t => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <select
            className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-sm"
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
          >
            {STATUSES.map(s => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>
      </Card>
      
      {/* Stats */}
      <div className="grid grid-cols-4 gap-3">
        <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
          <div className="text-2xl font-bold text-slate-900">{allDocuments.length}</div>
          <div className="text-xs text-slate-500">Всього</div>
        </div>
        <div className="bg-purple-50 rounded-xl border border-purple-200 p-4 text-center">
          <div className="text-2xl font-bold text-purple-700">
            {masterAgreements.length}
          </div>
          <div className="text-xs text-purple-600">Рамкових</div>
        </div>
        <div className="bg-blue-50 rounded-xl border border-blue-200 p-4 text-center">
          <div className="text-2xl font-bold text-blue-700">
            {annexes.length}
          </div>
          <div className="text-xs text-blue-600">Додатків</div>
        </div>
        <div className="bg-emerald-50 rounded-xl border border-emerald-200 p-4 text-center">
          <div className="text-2xl font-bold text-emerald-700">
            {allDocuments.filter(d => d.status === "signed").length}
          </div>
          <div className="text-xs text-emerald-600">Підписано</div>
        </div>
      </div>
      
      {/* Documents List */}
      <Card title={`📄 Документи (${filtered.length})`}>
        {filtered.length === 0 ? (
          <div className="text-center py-8 text-slate-400">
            <div className="text-4xl mb-2">📄</div>
            <p>Документів не знайдено</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100 -mx-4">
            {filtered.slice(0, 100).map(doc => (
              <div
                key={doc.id}
                className="px-4 py-3 hover:bg-slate-50 flex items-center gap-3"
              >
                {/* Type */}
                <div className="flex-shrink-0">
                  {getTypeBadge(doc.type)}
                </div>
                
                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-slate-900">{doc.number}</div>
                  <div className="text-xs text-slate-500">
                    {doc.payer}
                    {doc.orderId && <> · Ордер #{doc.orderId}</>}
                  </div>
                </div>
                
                {/* Date */}
                <div className="text-xs text-slate-500 text-right flex-shrink-0">
                  {new Date(doc.date).toLocaleDateString('uk-UA')}
                  {doc.validUntil && (
                    <div className="text-[10px]">до {new Date(doc.validUntil).toLocaleDateString('uk-UA')}</div>
                  )}
                </div>
                
                {/* Status */}
                <div className="flex-shrink-0">
                  {getStatusBadge(doc.status)}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
      
      {/* Info banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-800">
        <strong>ℹ️ Це архів документів.</strong> Для генерації нових документів використовуйте вкладку "Операції" (для документів замовлення) або "Клієнти" (для рамкових договорів).
      </div>
    </div>
  );
}

