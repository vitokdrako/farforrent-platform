/* eslint-disable */
/**
 * ReturnSettlementPage — Сторінка розрахунку повернення ордера
 * 
 * Ордер бьється на частини повернення із підсумками та прострочкою.
 * Використовує ІСНУЮЧІ роути.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  ArrowLeft, Package, AlertTriangle, CheckCircle, Clock, Layers,
  DollarSign, Shield, RotateCcw, Banknote, X, ImageOff, 
  ArrowLeftRight, CalendarDays, Timer, FileText, Lock,
  Calculator, Printer, Eye, ScrollText
} from 'lucide-react';
import { getImageUrl, handleImageError } from '../utils/imageHelper';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

const authFetch = (url, opts = {}) => {
  const token = localStorage.getItem('token');
  return fetch(url, { ...opts, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...opts.headers } });
};

const fmtUA = (n) => (Number(n) || 0).toLocaleString('uk-UA', { maximumFractionDigits: 0 });
const money = (v) => `₴${fmtUA(v)}`;
const fmtDate = (d) => d ? new Date(d).toLocaleDateString('uk-UA', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '—';
const fmtDateTime = (d) => d ? new Date(d).toLocaleString('uk-UA', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—';

function daysDiff(dateA, dateB) {
  if (!dateA || !dateB) return 0;
  const a = new Date(dateA); a.setHours(0,0,0,0);
  const b = new Date(dateB); b.setHours(0,0,0,0);
  return Math.floor((a - b) / 86400000);
}

export default function ReturnSettlementPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const orderId = parseInt(id);

  const [loading, setLoading] = useState(true);
  const [orderDetail, setOrderDetail] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [versions, setVersions] = useState([]);
  const [versionItems, setVersionItems] = useState({});
  const [saving, setSaving] = useState(false);
  const [charges, setCharges] = useState(null);

  // Payment form
  const [showPayForm, setShowPayForm] = useState(false);
  const [payType, setPayType] = useState('rent');
  const [payMethod, setPayMethod] = useState('cash');
  const [payAmount, setPayAmount] = useState('');

  // Settlement Act modal
  const [showSettlement, setShowSettlement] = useState(false);
  const [settlementAmount, setSettlementAmount] = useState('');
  const [settlementNote, setSettlementNote] = useState('');

  // Editable charge forms
  const [showLateFeeForm, setShowLateFeeForm] = useState(false);
  const [lateFeeAmount, setLateFeeAmount] = useState('');
  const [lateFeeNote, setLateFeeNote] = useState('');
  const [showDamageChargeForm, setShowDamageChargeForm] = useState(false);
  const [damageChargeAmount, setDamageChargeAmount] = useState('');
  const [damageChargeNote, setDamageChargeNote] = useState('');

  // Load all data
  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true);
      try {
        const [orderRes, snapshotRes, versionsRes, chargesRes] = await Promise.allSettled([
          authFetch(`${BACKEND_URL}/api/orders/${orderId}`),
          authFetch(`${BACKEND_URL}/api/finance/orders/${orderId}/snapshot`),
          authFetch(`${BACKEND_URL}/api/return-versions/order/${orderId}/versions`),
          authFetch(`${BACKEND_URL}/api/finance/order/${orderId}/charges`),
        ]);
        if (mounted) {
          if (orderRes.status === 'fulfilled' && orderRes.value.ok) setOrderDetail(await orderRes.value.json());
          if (snapshotRes.status === 'fulfilled' && snapshotRes.value.ok) setSnapshot(await snapshotRes.value.json());
          if (chargesRes.status === 'fulfilled' && chargesRes.value.ok) setCharges(await chargesRes.value.json());
          if (versionsRes.status === 'fulfilled' && versionsRes.value.ok) {
            const v = await versionsRes.value.json();
            const vers = v.versions || [];
            setVersions(vers);
            // Load items for each version in parallel
            const itemsMap = {};
            const itemPromises = vers.map(async (ver) => {
              try {
                const res = await authFetch(`${BACKEND_URL}/api/return-versions/version/${ver.version_id}`);
                if (res.ok) {
                  const data = await res.json();
                  itemsMap[ver.version_id] = data.items || [];
                }
              } catch (e) { console.error(e); }
            });
            await Promise.all(itemPromises);
            if (mounted) setVersionItems(itemsMap);
          }
        }
      } catch (e) { console.error(e); }
      finally { if (mounted) setLoading(false); }
    };
    load();
    return () => { mounted = false; };
  }, [orderId]);

  const reloadSnapshot = async () => {
    const res = await authFetch(`${BACKEND_URL}/api/finance/orders/${orderId}/snapshot`);
    if (res.ok) setSnapshot(await res.json());
  };

  const reloadCharges = async () => {
    const res = await authFetch(`${BACKEND_URL}/api/finance/order/${orderId}/charges`);
    if (res.ok) setCharges(await res.json());
  };

  const handleAddLateFee = async (amount, note) => {
    if (!amount || amount <= 0) return;
    setSaving(true);
    try {
      const res = await authFetch(`${BACKEND_URL}/api/finance/order/${orderId}/charges/add`, {
        method: 'POST',
        body: JSON.stringify({ type: 'late', amount, note }),
      });
      if (res.ok) {
        setShowLateFeeForm(false);
        setLateFeeAmount('');
        setLateFeeNote('');
        await Promise.all([reloadSnapshot(), reloadCharges()]);
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`Помилка: ${err.detail || 'Не вдалося нарахувати'}`);
      }
    } catch (e) { alert(`Помилка: ${e.message}`); }
    finally { setSaving(false); }
  };

  const handleAddDamageCharge = async (amount, note) => {
    if (!amount || amount <= 0) return;
    setSaving(true);
    try {
      const res = await authFetch(`${BACKEND_URL}/api/finance/order/${orderId}/charges/add`, {
        method: 'POST',
        body: JSON.stringify({ type: 'damage', amount, note }),
      });
      if (res.ok) {
        setShowDamageChargeForm(false);
        setDamageChargeAmount('');
        setDamageChargeNote('');
        await Promise.all([reloadSnapshot(), reloadCharges()]);
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`Помилка: ${err.detail || 'Не вдалося нарахувати'}`);
      }
    } catch (e) { alert(`Помилка: ${e.message}`); }
    finally { setSaving(false); }
  };

  const getUser = () => JSON.parse(localStorage.getItem("user") || "{}");

  const handlePayment = async () => {
    if (!payAmount || Number(payAmount) <= 0) return;
    setSaving(true);
    const user = getUser();
    try {
      const res = await authFetch(`${BACKEND_URL}/api/finance/payments`, {
        method: 'POST',
        body: JSON.stringify({ payment_type: payType, method: payMethod, amount: Number(payAmount), order_id: orderId, accepted_by_id: user.id, accepted_by_name: user.email, note: `Оплата (${payType})` }),
      });
      if (res.ok) { setPayAmount(''); setShowPayForm(false); await reloadSnapshot(); }
      else { const err = await res.json(); alert(`Помилка: ${err.detail || 'Невідома помилка'}`); }
    } catch (e) { alert(`Помилка: ${e.message}`); }
    finally { setSaving(false); }
  };

  // Deposit partial refund
  const [showDepositRefund, setShowDepositRefund] = useState(false);
  const [refundAmount, setRefundAmount] = useState('');
  const [refundNote, setRefundNote] = useState('');
  const [refundMethod, setRefundMethod] = useState('cash');

  const handleDepositRefund = async () => {
    const deposit = snapshot?.deposit;
    if (!deposit) return;
    const amt = parseFloat(refundAmount);
    if (!amt || amt <= 0) { alert('Вкажіть суму'); return; }
    const available = deposit.available ?? (deposit.held_amount - (deposit.used_amount || 0) - (deposit.refunded_amount || 0));
    if (amt > available) { alert(`Максимум для повернення: ${money(available)}`); return; }
    setSaving(true);
    try {
      const noteText = refundNote.trim() || 'Повернення застави';
      await authFetch(`${BACKEND_URL}/api/finance/deposits/${deposit.id}/refund?amount=${amt}&method=${refundMethod}&note=${encodeURIComponent(noteText)}`, { method: 'POST' });
      setShowDepositRefund(false);
      setRefundAmount('');
      setRefundNote('');
      await reloadSnapshot();
    } catch (e) { alert(`Помилка: ${e.message}`); }
    finally { setSaving(false); }
  };

  const handleDepositUse = async () => {
    const deposit = snapshot?.deposit;
    const damageDue = snapshot?.damage?.due || 0;
    if (!deposit || damageDue <= 0) return;
    const available = deposit.available ?? (deposit.held_amount - (deposit.used_amount || 0) - (deposit.refunded_amount || 0));
    const useAmount = Math.min(available, damageDue);
    if (useAmount <= 0) return;
    if (!window.confirm(`Утримати ${money(useAmount)} із застави за шкоду?`)) return;
    setSaving(true);
    try {
      await authFetch(`${BACKEND_URL}/api/finance/deposits/${deposit.id}/use?amount=${useAmount}`, { method: 'POST', body: JSON.stringify({ note: 'Утримання за шкоду' }) });
      await reloadSnapshot();
    } catch (e) { alert(`Помилка: ${e.message}`); }
    finally { setSaving(false); }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-slate-400 animate-pulse text-lg">Завантаження ордера...</div>
      </div>
    );
  }

  if (!orderDetail) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <div className="text-slate-500 text-lg mb-4">Ордер не знайдено</div>
          <button onClick={() => navigate('/manager-cabinet')} className="text-blue-600 hover:underline">← Назад</button>
        </div>
      </div>
    );
  }

  const items = orderDetail.items || [];
  const returnCards = orderDetail.return_cards || [];
  const damageItems = snapshot?.damage?.items || [];
  const damage = snapshot?.damage;
  const totals = snapshot?.totals;
  const deposit = snapshot?.deposit;
  const payments = snapshot?.payments || [];
  const depositAvailable = deposit ? (deposit.available ?? (deposit.held_amount - (deposit.used_amount || 0) - (deposit.refunded_amount || 0))) : 0;

  // Build damage map
  const damageMap = {};
  damageItems.forEach(d => {
    const key = d.sku || d.product_id;
    if (!damageMap[key]) damageMap[key] = [];
    damageMap[key].push(d);
  });

  // Build product image map from order items
  const productImageMap = {};
  items.forEach(item => {
    const key = item.sku || item.article;
    productImageMap[key] = item.image || item.photo;
  });

  // Determine parts: if we have versions, use them. Otherwise, show full order as one part.
  const hasVersions = versions.length > 0;
  
  // For non-partial-return orders, build one "part" from all items
  const orderEndDate = orderDetail.rental_end_date || orderDetail.return_date;

  // Calculate which items were returned in each version transition
  // v1: items with status=returned are the ones returned in part 1
  // v2: items from v1 that were pending are carried over, v2's returned items = part 2
  // etc.
  const parts = [];
  
  if (hasVersions) {
    for (let i = 0; i < versions.length; i++) {
      const v = versions[i];
      const vitems = versionItems[v.version_id] || [];
      
      // Items returned in this version = items with status "returned"
      const returnedInThisPart = vitems.filter(it => it.status === 'returned');
      const pendingInThisPart = vitems.filter(it => it.status === 'pending' || it.status === 'active');
      const lostInThisPart = vitems.filter(it => it.status === 'lost');
      
      // Calculate late days: version created_at vs rental_end_date
      const lateDays = daysDiff(v.created_at, v.rental_end_date || orderEndDate);
      const isLate = lateDays > 0;
      
      // Late fee for this part = returned items * daily_rate * late_days
      const lateFee = isLate ? returnedInThisPart.reduce((sum, it) => sum + (it.daily_rate || 0) * (it.qty || 1) * lateDays, 0) : 0;
      
      // Damage for items in this part
      const partDamage = [];
      returnedInThisPart.forEach(it => {
        if (damageMap[it.sku]) partDamage.push(...damageMap[it.sku]);
      });
      
      parts.push({
        versionNumber: v.version_number,
        displayNumber: v.display_number,
        status: v.status,
        createdAt: v.created_at,
        endDate: v.rental_end_date || orderEndDate,
        totalPrice: v.total_price,
        returnedItems: returnedInThisPart,
        pendingItems: pendingInThisPart,
        lostItems: lostInThisPart,
        lateDays: isLate ? lateDays : 0,
        lateFee,
        damage: partDamage,
        damageTotal: partDamage.reduce((s, d) => s + (d.fee || 0), 0),
      });
    }
  } else {
    // Single return - one part with all items
    const lateDays = daysDiff(new Date(), orderEndDate);
    const isLate = lateDays > 0 && orderDetail.status === 'issued';
    
    parts.push({
      versionNumber: 1,
      displayNumber: orderDetail.order_number,
      status: orderDetail.status === 'returned' ? 'returned' : 'active',
      createdAt: returnCards[0]?.returned_at || null,
      endDate: orderEndDate,
      totalPrice: orderDetail.total_rental,
      returnedItems: items,
      pendingItems: [],
      lostItems: [],
      lateDays: isLate ? lateDays : 0,
      lateFee: isLate ? items.reduce((s, it) => s + (it.price_per_day || 0) * (it.qty || it.quantity || 1) * lateDays, 0) : 0,
      damage: damageItems,
      damageTotal: damage?.total || 0,
    });
  }

  const statusConfig = {
    issued: { label: 'Видано', color: 'bg-blue-100 text-blue-700' },
    returned: { label: 'Повернуто', color: 'bg-emerald-100 text-emerald-700' },
    partial_return: { label: 'Часткове повернення', color: 'bg-amber-100 text-amber-700' },
  };
  const orderStatus = statusConfig[orderDetail.status] || { label: orderDetail.status, color: 'bg-slate-100 text-slate-700' };

  return (
    <div className="min-h-screen bg-slate-50" data-testid="return-settlement-page">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 sticky top-0 z-30">
        <div className="max-w-6xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button onClick={() => navigate('/manager-cabinet')} className="p-2 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-700 transition-colors" data-testid="back-to-cabinet">
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div>
                <div className="flex items-center gap-3">
                  <h1 className="text-xl font-bold text-slate-800">{orderDetail.order_number}</h1>
                  <span className={`px-3 py-1 rounded-full text-xs font-semibold ${orderStatus.color}`}>{orderStatus.label}</span>
                </div>
                <div className="text-sm text-slate-500 mt-0.5">
                  {orderDetail.customer_name} · <a href={`tel:${orderDetail.client_phone}`} className="text-blue-600 hover:underline">{orderDetail.client_phone}</a>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-6 text-sm">
              <div><span className="text-slate-500">Видача:</span> <span className="font-semibold">{fmtDate(orderDetail.rental_start_date)}</span></div>
              <div><span className="text-slate-500">Повернення:</span> <span className="font-semibold">{fmtDate(orderDetail.rental_end_date)}</span></div>
              <div><span className="text-slate-500">Днів:</span> <span className="font-semibold">{orderDetail.rental_days}</span></div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* LEFT: Parts / Versions (2/3) */}
          <div className="lg:col-span-2 space-y-6">
            
            {/* Return Card Summary from requisitors */}
            {returnCards.length > 0 && returnCards[0] && (
              <div className="bg-white rounded-2xl border border-slate-200 p-5">
                <div className="text-xs font-bold text-slate-600 mb-3 uppercase tracking-wide">Результат перевірки реквізиторами</div>
                <div className="grid grid-cols-4 gap-4 text-center">
                  {[
                    { label: 'OK', value: returnCards[0].items_ok, color: 'text-emerald-600' },
                    { label: 'Брудні', value: returnCards[0].items_dirty, color: 'text-amber-600' },
                    { label: 'Пошкоджені', value: returnCards[0].items_damaged, color: 'text-rose-600' },
                    { label: 'Відсутні', value: returnCards[0].items_missing, color: 'text-red-700' },
                  ].map(({ label, value, color }) => (
                    <div key={label}>
                      <div className={`font-bold text-3xl ${color}`}>{value || 0}</div>
                      <div className="text-xs text-slate-500 mt-1">{label}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* PARTS */}
            {parts.map((part, pi) => (
              <div key={pi} className="bg-white rounded-2xl border border-slate-200 overflow-hidden" data-testid={`return-part-${pi}`}>
                {/* Part Header */}
                <div className={`px-5 py-4 flex items-center justify-between ${
                  part.status === 'returned' || part.status === 'archived' 
                    ? 'bg-emerald-50 border-b border-emerald-200' 
                    : part.lateDays > 0 
                      ? 'bg-red-50 border-b border-red-200'
                      : 'bg-slate-50 border-b border-slate-200'
                }`}>
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-violet-100 text-violet-700 text-lg font-bold flex items-center justify-center flex-shrink-0">
                      {part.versionNumber}
                    </div>
                    <div>
                      <div className="font-bold text-slate-800">{part.displayNumber}</div>
                      <div className="text-xs text-slate-500 flex items-center gap-2 mt-0.5">
                        <span>До: {fmtDate(part.endDate)}</span>
                        {part.createdAt && <span>· Повернуто: {fmtDateTime(part.createdAt)}</span>}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold text-slate-800 text-lg">{money(part.totalPrice)}</div>
                    {part.lateDays > 0 && (
                      <div className="flex items-center gap-1 text-red-600 text-xs font-semibold mt-0.5">
                        <Timer className="w-3.5 h-3.5" />
                        Прострочка: {part.lateDays} дн.
                      </div>
                    )}
                    {part.status === 'returned' || part.status === 'archived' ? (
                      <span className="text-xs text-emerald-600 font-medium">Завершено</span>
                    ) : (
                      <span className="text-xs text-blue-600 font-medium">Активна</span>
                    )}
                  </div>
                </div>

                {/* Part Items */}
                <div className="p-5 space-y-3">
                  {/* Returned Items */}
                  {part.returnedItems.length > 0 && (
                    <div>
                      {hasVersions && <div className="text-xs font-semibold text-emerald-600 mb-2">Повернуто ({part.returnedItems.length})</div>}
                      <div className="space-y-2">
                        {part.returnedItems.map((item, i) => {
                          const sku = item.sku || item.article;
                          const hasDmg = damageMap[sku];
                          const img = getImageUrl(productImageMap[sku] || item.image || item.photo);
                          return (
                            <div key={i} className={`flex gap-3 p-3 rounded-xl border ${hasDmg ? 'border-rose-200 bg-rose-50/50' : 'border-slate-100 bg-slate-50/40'}`}>
                              <div className="w-16 h-16 rounded-lg overflow-hidden bg-slate-200 flex-shrink-0 border border-slate-200">
                                {img ? (
                                  <img src={img} alt={item.name} className="w-full h-full object-cover" onError={handleImageError} />
                                ) : null}
                                <div className={`w-full h-full items-center justify-center text-slate-400 ${img ? 'hidden' : 'flex'}`}><ImageOff className="w-5 h-5" /></div>
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="text-xs font-mono text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">{sku}</span>
                                  {hasDmg && <span className="text-[10px] px-2 py-0.5 rounded-full bg-rose-100 text-rose-700 font-semibold">шкода</span>}
                                </div>
                                <div className="text-sm font-medium text-slate-800 mt-0.5">{item.name}</div>
                                <div className="flex items-center gap-3 text-xs text-slate-500 mt-1">
                                  <span>×{item.qty || item.quantity}</span>
                                  <span>{money(item.daily_rate || item.price_per_day)}/день</span>
                                  <span className="font-semibold text-slate-700">{money((item.daily_rate || item.price_per_day || 0) * (item.qty || item.quantity || 1))}</span>
                                </div>
                                {hasDmg && damageMap[sku].map((d, di) => (
                                  <div key={di} className="mt-2 text-xs text-rose-700 bg-rose-100/70 rounded-lg px-3 py-1.5">
                                    <div className="flex justify-between"><span className="font-semibold">{d.damage_type}</span><span className="font-bold">{money(d.fee)}</span></div>
                                    {d.note && <div className="text-rose-500 mt-0.5">{d.note}</div>}
                                  </div>
                                ))}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Pending items (still with client) */}
                  {part.pendingItems.length > 0 && (
                    <div>
                      <div className="text-xs font-semibold text-amber-600 mb-2">Ще у клієнта ({part.pendingItems.length})</div>
                      <div className="space-y-1.5">
                        {part.pendingItems.map((item, i) => (
                          <div key={i} className="flex items-center justify-between text-sm bg-amber-50/60 border border-amber-100 rounded-lg px-3 py-2">
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="w-2 h-2 rounded-full bg-amber-400 flex-shrink-0" />
                              <span className="text-xs font-mono text-slate-500">{item.sku}</span>
                              <span className="text-slate-700 truncate">{item.name}</span>
                            </div>
                            <span className="text-slate-500 text-xs flex-shrink-0 ml-2">×{item.qty}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Lost items */}
                  {part.lostItems.length > 0 && (
                    <div>
                      <div className="text-xs font-semibold text-red-600 mb-2">Втрачено ({part.lostItems.length})</div>
                      <div className="space-y-1.5">
                        {part.lostItems.map((item, i) => (
                          <div key={i} className="flex items-center justify-between text-sm bg-red-50/60 border border-red-100 rounded-lg px-3 py-2">
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="w-2 h-2 rounded-full bg-red-500 flex-shrink-0" />
                              <span className="text-xs font-mono text-slate-500">{item.sku}</span>
                              <span className="text-slate-700 truncate">{item.name}</span>
                            </div>
                            <span className="text-slate-500 text-xs flex-shrink-0 ml-2">×{item.qty}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Part Footer Summary */}
                <div className="px-5 py-3 bg-slate-50 border-t border-slate-200">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-600">Підсумок частини:</span>
                    <span className="font-bold text-slate-800">{money(part.totalPrice)}</span>
                  </div>
                  {part.lateDays > 0 && (
                    <div className="flex items-center justify-between text-sm mt-1">
                      <span className="text-red-600 flex items-center gap-1"><Timer className="w-3.5 h-3.5" /> Прострочка ({part.lateDays} дн.)</span>
                      <span className="font-bold text-red-600">{money(part.lateFee)}</span>
                    </div>
                  )}
                  {part.damageTotal > 0 && (
                    <div className="flex items-center justify-between text-sm mt-1">
                      <span className="text-rose-600 flex items-center gap-1"><AlertTriangle className="w-3.5 h-3.5" /> Шкода</span>
                      <span className="font-bold text-rose-600">{money(part.damageTotal)}</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* RIGHT: Finance sidebar (1/3) */}
          <div className="space-y-5">
            {/* Overall Summary */}
            <div className="bg-white rounded-2xl border border-slate-200 p-5">
              <div className="text-xs font-bold text-slate-600 mb-3 flex items-center gap-1.5 uppercase tracking-wide">
                <DollarSign className="w-3.5 h-3.5" />
                Загальний розрахунок
              </div>

              {totals && (
                <div className="space-y-3 text-sm">
                  {/* Вартість ордеру (до знижки) */}
                  <div className="flex justify-between">
                    <span className="text-slate-600">Вартість ордеру</span>
                    <span className="font-semibold">{money(totals.rental_total)}</span>
                  </div>
                  {/* Знижка */}
                  {totals.discount > 0 && (
                    <div className="flex justify-between">
                      <span className="text-emerald-600">Знижка {totals.discount_percent > 0 ? `(${totals.discount_percent}%)` : ''}</span>
                      <span className="font-semibold text-emerald-600">-{money(totals.discount)}</span>
                    </div>
                  )}
                  {/* Сума зі знижкою */}
                  {totals.discount > 0 && (
                    <div className="flex justify-between pt-1 border-t border-slate-100">
                      <span className="text-slate-700 font-medium">Оренда (зі знижкою)</span>
                      <span className="font-bold text-slate-800">{money(totals.rental_after_discount)}</span>
                    </div>
                  )}
                  {/* Оплачено */}
                  <div className="flex justify-between">
                    <span className="text-slate-600">Оплачено</span>
                    <span className="font-semibold text-emerald-600">{money(totals.rent_paid + totals.advance_paid)}</span>
                  </div>
                  {totals.rent_due > 0 && (
                    <div className="flex justify-between font-medium">
                      <span className="text-amber-600">Борг (оренда)</span>
                      <span className="text-amber-600">{money(totals.rent_due)}</span>
                    </div>
                  )}

                  {/* Late fees — from charges API + calculated */}
                  {(() => {
                    const calcLate = parts.reduce((s, p) => s + p.lateFee, 0);
                    const chargesLate = charges?.late;
                    const lateTotal = chargesLate?.total || 0;
                    const latePaid = chargesLate?.paid || 0;
                    const lateDue = chargesLate?.due || 0;
                    const hasLate = calcLate > 0 || lateTotal > 0;
                    
                    if (!hasLate) return null;
                    return (
                      <div className="pt-2 border-t border-slate-100 space-y-1">
                        <div className="flex justify-between font-medium">
                          <span className="text-red-600 flex items-center gap-1"><Timer className="w-3.5 h-3.5" /> Прострочка</span>
                          <span className="text-red-600">{money(lateTotal || calcLate)}</span>
                        </div>
                        {latePaid > 0 && (
                          <div className="flex justify-between text-xs">
                            <span className="text-emerald-500">Оплачено</span>
                            <span className="text-emerald-600">{money(latePaid)}</span>
                          </div>
                        )}
                        {lateDue > 0 && (
                          <div className="flex justify-between text-xs font-medium">
                            <span className="text-red-500">До сплати</span>
                            <span className="text-red-600">{money(lateDue)}</span>
                          </div>
                        )}
                        {/* Button to add calculated late fee if not yet charged */}
                        {calcLate > 0 && lateTotal === 0 && !showLateFeeForm && (
                          <button
                            onClick={() => {
                              setLateFeeAmount(String(calcLate));
                              const note = parts.filter(p => p.lateDays > 0).map(p => `${p.displayNumber}: ${p.lateDays} дн.`).join(', ');
                              setLateFeeNote(`Прострочка: ${note}`);
                              setShowLateFeeForm(true);
                            }}
                            disabled={saving}
                            className="w-full mt-1 py-2 text-xs font-semibold text-red-700 bg-red-50 hover:bg-red-100 border border-red-200 rounded-lg transition-colors disabled:opacity-50 flex items-center justify-center gap-1"
                            data-testid="add-late-fee-btn"
                          >
                            <Timer className="w-3 h-3" />
                            Нарахувати прострочку ({money(calcLate)})
                          </button>
                        )}
                        {showLateFeeForm && (
                          <div className="mt-2 p-3 bg-red-50/80 border border-red-200 rounded-xl space-y-2" data-testid="late-fee-form">
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-bold text-red-700">Нарахувати прострочку</span>
                              <button onClick={() => setShowLateFeeForm(false)} className="text-red-400 hover:text-red-600"><X className="w-3.5 h-3.5" /></button>
                            </div>
                            <div className="relative">
                              <input
                                type="number"
                                value={lateFeeAmount}
                                onChange={(e) => setLateFeeAmount(e.target.value)}
                                className="w-full px-3 py-2 text-sm border border-red-300 rounded-lg focus:ring-2 focus:ring-red-300 bg-white"
                                placeholder="Сума"
                                data-testid="late-fee-amount"
                              />
                              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-red-400">грн</span>
                            </div>
                            <input
                              type="text"
                              value={lateFeeNote}
                              onChange={(e) => setLateFeeNote(e.target.value)}
                              className="w-full px-3 py-1.5 text-xs border border-red-200 rounded-lg bg-white"
                              placeholder="Примітка"
                              data-testid="late-fee-note"
                            />
                            <button
                              onClick={() => handleAddLateFee(Number(lateFeeAmount), lateFeeNote)}
                              disabled={saving || !lateFeeAmount || Number(lateFeeAmount) <= 0}
                              className="w-full py-2 text-xs font-semibold text-white bg-red-600 hover:bg-red-700 rounded-lg disabled:opacity-50 flex items-center justify-center gap-1"
                              data-testid="late-fee-submit"
                            >
                              <Timer className="w-3 h-3" />
                              Нарахувати {lateFeeAmount ? money(Number(lateFeeAmount)) : ''}
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })()}

                  {/* Damage */}
                  {damage && damage.total > 0 && (
                    <div className="pt-2 border-t border-slate-100 space-y-1">
                      <div className="flex justify-between font-medium">
                        <span className="text-rose-600">Шкода</span>
                        <span className="font-semibold text-rose-600">{money(damage.total)}</span>
                      </div>
                      {damage.paid > 0 && (
                        <div className="flex justify-between text-xs">
                          <span className="text-emerald-500">Оплачено (шкода)</span>
                          <span className="text-emerald-600">{money(damage.paid)}</span>
                        </div>
                      )}
                      {damage.due > 0 && (
                        <div className="flex justify-between text-xs font-medium">
                          <span className="text-rose-500">До сплати</span>
                          <span className="text-rose-600">{money(damage.due)}</span>
                        </div>
                      )}
                      {/* Editable damage charge button - only when system detected damage but no charge made */}
                      {damage.total > 0 && !charges?.damage?.total && !showDamageChargeForm && (
                        <button
                          onClick={() => {
                            setDamageChargeAmount(String(damage.total));
                            setDamageChargeNote('Нарахування за пошкодження');
                            setShowDamageChargeForm(true);
                          }}
                          disabled={saving}
                          className="w-full mt-1 py-2 text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 rounded-lg transition-colors disabled:opacity-50 flex items-center justify-center gap-1"
                          data-testid="add-damage-charge-btn"
                        >
                          <AlertTriangle className="w-3 h-3" />
                          Нарахувати шкоду ({money(damage.total)})
                        </button>
                      )}
                      {showDamageChargeForm && (
                        <div className="mt-2 p-3 bg-rose-50/80 border border-rose-200 rounded-xl space-y-2" data-testid="damage-charge-form">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold text-rose-700">Нарахувати шкоду</span>
                            <button onClick={() => setShowDamageChargeForm(false)} className="text-rose-400 hover:text-rose-600"><X className="w-3.5 h-3.5" /></button>
                          </div>
                          <div className="relative">
                            <input
                              type="number"
                              value={damageChargeAmount}
                              onChange={(e) => setDamageChargeAmount(e.target.value)}
                              className="w-full px-3 py-2 text-sm border border-rose-300 rounded-lg focus:ring-2 focus:ring-rose-300 bg-white"
                              placeholder="Сума"
                              data-testid="damage-charge-amount"
                            />
                            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-rose-400">грн</span>
                          </div>
                          <input
                            type="text"
                            value={damageChargeNote}
                            onChange={(e) => setDamageChargeNote(e.target.value)}
                            className="w-full px-3 py-1.5 text-xs border border-rose-200 rounded-lg bg-white"
                            placeholder="Примітка"
                            data-testid="damage-charge-note"
                          />
                          <button
                            onClick={() => handleAddDamageCharge(Number(damageChargeAmount), damageChargeNote)}
                            disabled={saving || !damageChargeAmount || Number(damageChargeAmount) <= 0}
                            className="w-full py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-700 rounded-lg disabled:opacity-50 flex items-center justify-center gap-1"
                            data-testid="damage-charge-submit"
                          >
                            <AlertTriangle className="w-3 h-3" />
                            Нарахувати {damageChargeAmount ? money(Number(damageChargeAmount)) : ''}
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Deposit */}
                  <div className="pt-3 border-t border-slate-200 space-y-1">
                    <div className="flex justify-between">
                      <span className="text-slate-600">Застава (очік.)</span>
                      <span className="font-semibold">{money(totals.deposit_expected)}</span>
                    </div>
                    {deposit && (
                      <>
                        <div className="flex justify-between">
                          <span className="text-slate-600">Прийнято</span>
                          <span className="font-semibold">
                            {deposit.currency !== 'UAH' ? `${deposit.currency === 'USD' ? '$' : '€'}${fmtUA(deposit.actual_amount)}` : money(deposit.held_amount)}
                          </span>
                        </div>
                        {deposit.used_amount > 0 && (
                          <div className="flex justify-between text-xs"><span className="text-rose-500">Утримано</span><span className="text-rose-600">-{money(deposit.used_amount)}</span></div>
                        )}
                        {deposit.refunded_amount > 0 && (
                          <div className="flex justify-between text-xs"><span className="text-blue-500">Повернуто</span><span className="text-blue-600">{money(deposit.refunded_amount)}</span></div>
                        )}
                        <div className="flex justify-between font-medium">
                          <span className="text-slate-700">Доступно</span>
                          <span className="text-emerald-600">{money(depositAvailable)}</span>
                        </div>
                        {/* Історія повернень застави */}
                        {deposit.events && deposit.events.filter(e => e.event_type === 'refunded').length > 0 && (
                          <div className="mt-1 pt-1 border-t border-slate-100">
                            <div className="text-[10px] font-semibold text-slate-400 mb-1">Повернення:</div>
                            {deposit.events.filter(e => e.event_type === 'refunded').map((e, i) => (
                              <div key={i} className="flex items-center justify-between text-[10px] text-blue-600 bg-blue-50/50 rounded px-1.5 py-0.5 mb-0.5">
                                <span className="truncate max-w-[60%]">{e.note || 'Повернення застави'}</span>
                                <span className="font-medium">{money(e.amount)}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </>
                    )}
                  </div>

                  {/* Grand Total */}
                  {totals.grand_total_due > 0 ? (
                    <div className="pt-3 border-t-2 border-slate-300 flex justify-between">
                      <span className="font-bold text-slate-800 text-base">Загальний борг</span>
                      <span className="font-bold text-red-600 text-xl">{money(totals.grand_total_due)}</span>
                    </div>
                  ) : (
                    <div className="pt-3 border-t-2 border-slate-300 flex justify-between">
                      <span className="font-bold text-slate-800">Статус</span>
                      <span className="font-bold text-emerald-600 text-lg">Все оплачено</span>
                    </div>
                  )}
                </div>
              )}

              {/* Payment History */}
              {payments.length > 0 && (
                <div className="mt-5 pt-4 border-t border-slate-200">
                  <div className="text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">Історія оплат</div>
                  <div className="space-y-1 max-h-40 overflow-y-auto">
                    {payments.map((p) => {
                      const typeLabels = { rent: 'Оренда', additional: 'Донарах.', damage: 'Шкода', deposit: 'Застава', late: 'Прострочка', advance: 'Передпл.', discount: 'Знижка', loss: 'Втрата' };
                      const isCharge = p.status === 'pending';
                      const isSystem = ['discount', 'loss'].includes(p.payment_type);
                      const methodText = isCharge ? 'нараховано' : isSystem ? '' : (p.method === 'cash' ? 'гот.' : p.method === 'card' ? 'безгот.' : (p.method || ''));
                      const amountColor = isCharge ? 'text-amber-600' : isSystem ? 'text-slate-500' : 'text-emerald-700';
                      const prefix = isCharge ? '' : '+';
                      return (
                        <div key={p.id} className="flex items-center justify-between text-xs bg-slate-50 rounded-lg px-2.5 py-1.5">
                          <div>
                            <span className="text-slate-700 font-medium">{typeLabels[p.payment_type] || p.payment_type}</span>
                            {methodText && <span className={`ml-1 ${isCharge ? 'text-amber-500' : 'text-slate-400'}`}>{methodText}</span>}
                          </div>
                          <span className={`font-bold ${amountColor}`}>{prefix}{money(p.amount)}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="mt-5 pt-4 border-t border-slate-200 space-y-2">
                {!showPayForm ? (
                  <>
                    <button
                      onClick={() => setShowPayForm(true)}
                      className="w-full py-3 text-sm font-semibold text-white bg-slate-800 hover:bg-slate-700 rounded-xl transition-colors flex items-center justify-center gap-2"
                      data-testid="pay-btn"
                    >
                      <Banknote className="w-4 h-4" /> Прийняти оплату
                    </button>
                    <div className="flex gap-2">
                      {deposit && depositAvailable > 0 && !showDepositRefund && (
                        <button onClick={() => { setRefundAmount(depositAvailable.toString()); setShowDepositRefund(true); }} disabled={saving}
                          className="flex-1 py-2.5 text-xs font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded-xl transition-colors disabled:opacity-50 flex items-center justify-center gap-1"
                          data-testid="refund-btn"
                        >
                          <RotateCcw className="w-3.5 h-3.5" /> Повернути заставу
                        </button>
                      )}
                      {showDepositRefund && (
                        <div className="flex-1 bg-blue-50 border border-blue-200 rounded-xl p-3 space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold text-blue-800">Повернення застави</span>
                            <button onClick={() => setShowDepositRefund(false)} className="text-blue-400 hover:text-blue-600"><X className="w-3.5 h-3.5" /></button>
                          </div>
                          <div className="text-[10px] text-blue-600">Доступно: {money(depositAvailable)}</div>
                          <input
                            type="number" value={refundAmount} onChange={(e) => setRefundAmount(e.target.value)}
                            placeholder="Сума повернення" max={depositAvailable} min={0} step="0.01"
                            className="w-full text-xs border border-blue-300 rounded-lg px-2.5 py-1.5 bg-white focus:ring-2 focus:ring-blue-400 focus:border-blue-400"
                            data-testid="refund-amount"
                          />
                          <input
                            type="text" value={refundNote} onChange={(e) => setRefundNote(e.target.value)}
                            placeholder="Причина (необов'язково)"
                            className="w-full text-xs border border-blue-300 rounded-lg px-2.5 py-1.5 bg-white focus:ring-2 focus:ring-blue-400 focus:border-blue-400"
                            data-testid="refund-note"
                          />
                          <div className="flex gap-2">
                            <select value={refundMethod} onChange={(e) => setRefundMethod(e.target.value)}
                              className="text-xs border border-blue-300 rounded-lg px-2 py-1.5 bg-white" data-testid="refund-method">
                              <option value="cash">Готівка</option>
                              <option value="bank">Безготівка</option>
                            </select>
                            <button onClick={handleDepositRefund} disabled={saving || !refundAmount}
                              className="flex-1 py-1.5 text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition disabled:opacity-50"
                              data-testid="refund-confirm-btn"
                            >
                              {saving ? '...' : 'Повернути'}
                            </button>
                          </div>
                        </div>
                      )}
                      {deposit && depositAvailable > 0 && damage?.due > 0 && (
                        <button onClick={handleDepositUse} disabled={saving}
                          className="flex-1 py-2.5 text-xs font-medium text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 rounded-xl transition-colors disabled:opacity-50 flex items-center justify-center gap-1"
                          data-testid="use-deposit-btn"
                        >
                          <Shield className="w-3.5 h-3.5" /> Утримати
                        </button>
                      )}
                    </div>
                  </>
                ) : (
                  <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-bold text-slate-700">Оплата</span>
                      <button onClick={() => setShowPayForm(false)} className="text-slate-400 hover:text-slate-600"><X className="w-4 h-4" /></button>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <select value={payType} onChange={(e) => setPayType(e.target.value)} className="text-xs border border-slate-300 rounded-lg px-2 py-1.5 bg-white" data-testid="pay-type">
                        <option value="rent">Оренда</option><option value="damage">Шкода</option><option value="late">Прострочення</option><option value="additional">Донарахування</option>
                      </select>
                      <select value={payMethod} onChange={(e) => setPayMethod(e.target.value)} className="text-xs border border-slate-300 rounded-lg px-2 py-1.5 bg-white" data-testid="pay-method">
                        <option value="cash">Готівка</option><option value="bank">Безготівка</option>
                      </select>
                    </div>
                    <div className="flex gap-2">
                      <input type="number" value={payAmount} onChange={(e) => setPayAmount(e.target.value)} placeholder="Сума ₴" className="flex-1 text-sm border border-slate-300 rounded-lg px-3 py-1.5" data-testid="pay-amount" />
                      <button onClick={handlePayment} disabled={saving || !payAmount || Number(payAmount) <= 0}
                        className="px-4 py-1.5 text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg disabled:opacity-50" data-testid="pay-submit"
                      >{saving ? '...' : 'OK'}</button>
                    </div>
                    {(totals?.rent_due > 0 || damage?.due > 0) && (
                      <div className="flex gap-1.5 flex-wrap">
                        {totals?.rent_due > 0 && <button onClick={() => { setPayType('rent'); setPayAmount(String(totals.rent_due)); }} className="text-[10px] px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full hover:bg-amber-200 font-medium">Борг: {money(totals.rent_due)}</button>}
                        {damage?.due > 0 && <button onClick={() => { setPayType('damage'); setPayAmount(String(damage.due)); }} className="text-[10px] px-2 py-0.5 bg-rose-100 text-rose-700 rounded-full hover:bg-rose-200 font-medium">Шкода: {money(damage.due)}</button>}
                        {charges?.late?.due > 0 && <button onClick={() => { setPayType('late'); setPayAmount(String(charges.late.due)); }} className="text-[10px] px-2 py-0.5 bg-red-100 text-red-700 rounded-full hover:bg-red-200 font-medium">Простр: {money(charges.late.due)}</button>}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Defect Act & Close Order — INSIDE same sticky card */}
            <div className="bg-white rounded-2xl border border-slate-200 p-5 space-y-3">
              <div className="text-xs font-bold text-slate-600 uppercase tracking-wide flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5" />
                Документи та дії
              </div>

              {/* Settlement Act - opens directly, no modal */}
              <button
                onClick={() => {
                  window.open(`${BACKEND_URL}/api/documents/settlement-act/${orderId}/preview`, '_blank');
                }}
                className="w-full py-3 text-sm font-semibold text-white bg-slate-800 hover:bg-slate-900 rounded-xl transition-colors flex items-center justify-center gap-2"
                data-testid="generate-settlement-act"
              >
                <Calculator className="w-4 h-4" />
                Акт взаєморозрахунків
              </button>

              {/* Return Act */}
              <button
                onClick={async () => {
                  setSaving(true);
                  try {
                    const res = await authFetch(`${BACKEND_URL}/api/documents/generate`, {
                      method: 'POST',
                      body: JSON.stringify({ doc_type: 'return_act', entity_type: 'order', entity_id: String(orderId) }),
                    });
                    if (res.ok) {
                      const data = await res.json();
                      if (data.preview_url) {
                        window.open(`${BACKEND_URL}${data.preview_url}`, '_blank');
                      } else if (data.document_id) {
                        window.open(`${BACKEND_URL}/api/documents/${data.document_id}/preview`, '_blank');
                      }
                    } else {
                      const err = await res.json().catch(() => ({}));
                      alert(`Помилка: ${err.detail || 'Не вдалося згенерувати'}`);
                    }
                  } catch (e) { alert(`Помилка: ${e.message}`); }
                  finally { setSaving(false); }
                }}
                disabled={saving}
                className="w-full py-3 text-sm font-semibold text-slate-700 bg-slate-50 hover:bg-slate-100 border border-slate-300 rounded-xl transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                data-testid="generate-return-act"
              >
                <ScrollText className="w-4 h-4" />
                Акт повернення
              </button>

              {/* Generate Defect Act - show when there are ANY damage records (including photo_only with fee=0) */}
              {damage && damage.items && damage.items.length > 0 && (
                <button
                  onClick={async () => {
                    setSaving(true);
                    try {
                      const res = await authFetch(`${BACKEND_URL}/api/documents/generate`, {
                        method: 'POST',
                        body: JSON.stringify({ doc_type: 'defect_act', entity_type: 'order', entity_id: String(orderId) }),
                      });
                      if (res.ok) {
                        const data = await res.json();
                        if (data.preview_url) {
                          window.open(`${BACKEND_URL}${data.preview_url}`, '_blank');
                        } else if (data.document_id) {
                          window.open(`${BACKEND_URL}/api/documents/${data.document_id}/preview`, '_blank');
                        }
                      } else {
                        const err = await res.json().catch(() => ({}));
                        alert(`Помилка: ${err.detail || 'Не вдалося згенерувати'}`);
                      }
                    } catch (e) { alert(`Помилка: ${e.message}`); }
                    finally { setSaving(false); }
                  }}
                  disabled={saving}
                  className="w-full py-3 text-sm font-semibold text-slate-700 bg-slate-50 hover:bg-slate-100 border border-slate-300 rounded-xl transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                  data-testid="generate-defect-act"
                >
                  <FileText className="w-4 h-4" />
                  Дефектний акт
                </button>
              )}

              {/* Close Order - only when everything is paid */}
              {totals && totals.grand_total_due <= 0 && orderDetail.status !== 'completed' && (
                <button
                  onClick={async () => {
                    if (!window.confirm('Закрити замовлення? Після цього зміни неможливі.')) return;
                    setSaving(true);
                    try {
                      const res = await authFetch(`${BACKEND_URL}/api/orders/${orderId}/status`, {
                        method: 'PUT',
                        body: JSON.stringify({ status: 'completed' }),
                      });
                      if (res.ok) {
                        setOrderDetail(prev => ({ ...prev, status: 'completed' }));
                      } else {
                        const err = await res.json().catch(() => ({}));
                        alert(`Помилка: ${err.detail || 'Не вдалося закрити'}`);
                      }
                    } catch (e) { alert(`Помилка: ${e.message}`); }
                    finally { setSaving(false); }
                  }}
                  disabled={saving}
                  className="w-full py-3 text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                  data-testid="close-order-btn"
                >
                  <Lock className="w-4 h-4" />
                  Закрити замовлення
                </button>
              )}

              {orderDetail.status === 'completed' && (
                <div className="text-center py-3 text-sm font-semibold text-emerald-600 bg-emerald-50 rounded-xl border border-emerald-200">
                  <CheckCircle className="w-4 h-4 inline mr-1.5" />
                  Замовлення закрито
                </div>
              )}

              {totals && totals.grand_total_due > 0 && orderDetail.status !== 'completed' && (
                <div className="text-center py-2 text-xs text-slate-500">
                  Для закриття потрібно погасити борг
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}
