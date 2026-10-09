/* eslint-disable */
import React, { useState, useEffect, useCallback } from 'react';
import { financeApi } from '../../services/financeApi.js';
import DocumentsPanel from './DocumentsPanel';
import eventBus, { EVENTS } from '../../utils/eventBus';

const cls = (...a) => a.filter(Boolean).join(' ');
const money = (v, cur = '₴') => `${cur} ${(v || 0).toLocaleString('uk-UA', { maximumFractionDigits: 2 })}`;

const Pill = ({ t = 'neutral', children }) => {
  const tones = { ok: 'bg-emerald-50 text-emerald-800 border-emerald-200', warn: 'bg-amber-50 text-amber-800 border-amber-200', info: 'bg-sky-50 text-sky-800 border-sky-200', neutral: 'bg-slate-50 text-slate-800 border-slate-200', danger: 'bg-rose-50 text-rose-800 border-rose-200' };
  return <span className={cls('inline-flex items-center rounded-full border px-2 py-0.5 text-xs', tones[t] || tones.neutral)}>{children}</span>;
};

const Btn = ({ variant = 'outline', className = '', children, ...props }) => {
  const base = 'inline-flex items-center justify-center rounded-xl px-3 py-2 text-sm transition disabled:opacity-50';
  const v = variant === 'primary' ? 'bg-lime-600 text-white hover:bg-lime-700' 
    : variant === 'danger' ? 'bg-rose-600 text-white hover:bg-rose-700'
    : 'border bg-white hover:bg-slate-50';
  return <button className={cls(base, v, className)} {...props}>{children}</button>;
};

const Card = ({ className, children }) => <div className={cls('rounded-2xl border bg-white shadow-sm', className)}>{children}</div>;
const CardHd = ({ title, subtitle, right }) => (
  <div className="flex items-start justify-between gap-3 border-b p-4">
    <div><div className="text-sm font-semibold">{title}</div>{subtitle && <div className="mt-0.5 text-xs text-slate-500">{subtitle}</div>}</div>
    {right && <div className="shrink-0">{right}</div>}
  </div>
);
const CardBd = ({ className, children }) => <div className={cls('p-4', className)}>{children}</div>;

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

// Компонент для редагування рядка донарахування
const ChargeRow = ({ item, type, onUpdate, onDelete, onPay }) => {
  const [editing, setEditing] = useState(false);
  const [amount, setAmount] = useState(item.amount || item.fee || 0);
  const [saving, setSaving] = useState(false);
  
  const handleSave = async () => {
    setSaving(true);
    await onUpdate(item.id, type, amount);
    setEditing(false);
    setSaving(false);
  };
  
  const isPending = item.status === 'pending';
  const isPaid = item.status === 'confirmed' || item.status === 'completed';
  
  return (
    <div className={cls(
      "flex items-center justify-between gap-2 p-2 rounded-lg text-sm",
      isPaid ? "bg-emerald-50" : "bg-slate-50"
    )}>
      <div className="flex-1 min-w-0">
        <div className="text-xs text-slate-500 truncate">{item.note || (type === 'damage' ? item.damage_type : 'Прострочення')}</div>
        {item.sku && <span className="text-xs text-slate-400">{item.sku}</span>}
      </div>
      
      {editing ? (
        <div className="flex items-center gap-1">
          <input
            type="number"
            value={amount}
            onChange={(e) => setAmount(Number(e.target.value))}
            className="w-24 rounded border px-2 py-1 text-sm"
          />
          <button onClick={handleSave} disabled={saving} className="text-emerald-600 hover:text-emerald-800 px-1">✓</button>
          <button onClick={() => setEditing(false)} className="text-slate-400 hover:text-slate-600 px-1">✕</button>
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <span className={cls("font-medium", isPaid ? "text-emerald-600" : "text-rose-600")}>
            {money(item.amount || item.fee)}
          </span>
          {isPaid && <Pill t="ok">Оплачено</Pill>}
          {isPending && (
            <>
              <button onClick={() => setEditing(true)} className="text-slate-400 hover:text-slate-600 text-xs">✏️</button>
              <button onClick={() => onPay(item.id)} className="text-emerald-600 hover:text-emerald-800 text-xs">💵</button>
              <button onClick={() => onDelete(item.id, type)} className="text-rose-400 hover:text-rose-600 text-xs">🗑️</button>
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default function OrderFinancePanel({ order, onUpdate }) {
  const [rentAmount, setRentAmount] = useState(order.rent.due);
  const [rentMethod, setRentMethod] = useState('cash');
  const [depositAmount, setDepositAmount] = useState(Math.max(0, order.deposit.expected - order.deposit.held));
  const [depositMethod, setDepositMethod] = useState('cash');
  const [depositCurrency, setDepositCurrency] = useState('UAH');
  const [exchangeRate, setExchangeRate] = useState(1);
  const [loading, setLoading] = useState(null);
  
  // Charges data (damage + late)
  const [chargesData, setChargesData] = useState({ damage: { items: [], due: 0 }, late: { items: [], due: 0 } });
  const [newDamageAmount, setNewDamageAmount] = useState(0);
  const [newDamageNote, setNewDamageNote] = useState('');
  const [newLateAmount, setNewLateAmount] = useState(0);
  const [newLateNote, setNewLateNote] = useState('');
  
  // Load charges data
  const loadCharges = useCallback(async () => {
    if (!order.id) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/finance/order/${order.id}/charges`);
      if (res.ok) {
        const data = await res.json();
        setChargesData(data);
      }
    } catch (e) {
      console.error('Error loading charges:', e);
    }
  }, [order.id]);
  
  useEffect(() => {
    loadCharges();
  }, [loadCharges]);
  
  // Legacy damage data support
  const [damageData, setDamageData] = useState(null);
  const [damageAmount, setDamageAmount] = useState(0);
  
  useEffect(() => {
    const loadDamageData = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/api/analytics/order-damage-fee/${order.id}`);
        if (res.ok) {
          const data = await res.json();
          setDamageData(data);
          setDamageAmount(data.due_amount || 0);
        }
      } catch (e) {
        console.error('Error loading damage data:', e);
      }
    };
    if (order.id) loadDamageData();
  }, [order.id]);
  
  // Add new charge
  const handleAddCharge = async (type) => {
    const amount = type === 'damage' ? newDamageAmount : newLateAmount;
    const note = type === 'damage' ? newDamageNote : newLateNote;
    if (amount <= 0) return alert('Сума має бути більше 0');
    
    setLoading(`add_${type}`);
    try {
      const res = await fetch(`${BACKEND_URL}/api/finance/order/${order.id}/charges/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type, amount, note })
      });
      if (res.ok) {
        if (type === 'damage') { setNewDamageAmount(0); setNewDamageNote(''); }
        else { setNewLateAmount(0); setNewLateNote(''); }
        loadCharges();
        onUpdate?.();
      }
    } finally {
      setLoading(null);
    }
  };
  
  // Update charge
  const handleUpdateCharge = async (id, type, amount) => {
    try {
      await fetch(`${BACKEND_URL}/api/finance/order/${order.id}/charges/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type, amount })
      });
      loadCharges();
      onUpdate?.();
    } catch (e) {
      console.error('Error updating charge:', e);
    }
  };
  
  // Delete charge
  const handleDeleteCharge = async (id, type) => {
    if (!confirm('Видалити донарахування?')) return;
    try {
      await fetch(`${BACKEND_URL}/api/finance/order/${order.id}/charges/${id}?charge_type=${type}`, {
        method: 'DELETE'
      });
      loadCharges();
      onUpdate?.();
    } catch (e) {
      console.error('Error deleting charge:', e);
    }
  };
  
  // Pay late fee
  const handlePayLateFee = async (id) => {
    const method = prompt('Метод оплати: cash, card, bank', 'cash');
    if (!method) return;
    try {
      await fetch(`${BACKEND_URL}/api/finance/order/${order.id}/charges/${id}/pay`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ method })
      });
      loadCharges();
      onUpdate?.();
      eventBus.emit(EVENTS.FINANCE_UPDATED, { orderId: order.id });
    } catch (e) {
      console.error('Error paying charge:', e);
    }
  };

  // Exchange rates (can be fetched from API)
  const RATES = { UAH: 1, USD: 41.5, EUR: 45.2 };
  const currencySymbols = { UAH: '₴', USD: '$', EUR: '€' };

  const holdAvailable = Math.max(0, order.deposit.held - order.deposit.used_for_damage - order.deposit.refunded);
  const uahEquivalent = depositCurrency === 'UAH' ? depositAmount : depositAmount * exchangeRate;

  const handlePayment = async (type) => {
    let amount = type === 'rent' ? rentAmount : type === 'deposit' ? depositAmount : damageAmount;
    let method = type === 'rent' ? rentMethod : depositMethod;
    if (amount <= 0) {
      alert('Сума має бути більше 0');
      return;
    }
    setLoading(type);
    
    // Отримуємо інформацію про поточного користувача
    const userStr = localStorage.getItem('user');
    const user = userStr ? JSON.parse(userStr) : null;
    const acceptedById = user?.user_id || null;
    // Формуємо ім'я: firstname + lastname або username
    const acceptedByName = user ? 
      (user.firstname && user.lastname ? `${user.firstname} ${user.lastname}` : 
       user.firstname || user.username || 'Невідомий') 
      : null;
    
    try {
      if (type === 'deposit') {
        // Use currency-aware deposit creation
        const result = await financeApi.createDepositWithCurrency({
          order_id: order.id,
          expected_amount: order.deposit.expected,
          actual_amount: depositAmount,
          currency: depositCurrency,
          exchange_rate: depositCurrency === 'UAH' ? null : exchangeRate,
          method: depositMethod,
          note: depositCurrency !== 'UAH' ? `${depositAmount} ${depositCurrency} @ ${exchangeRate}` : null,
          accepted_by_id: acceptedById,
          accepted_by_name: acceptedByName
        });
        if (result.data && result.data.success) {
          // Emit event for real-time updates
          eventBus.emit(EVENTS.DEPOSIT_CREATED, { orderId: order.id });
          eventBus.emit(EVENTS.FINANCE_UPDATED, { orderId: order.id });
          onUpdate?.();
        }
      } else {
        const result = await financeApi.createPayment({ 
          payment_type: type, 
          method, 
          amount, 
          order_id: order.id,
          accepted_by_id: acceptedById,
          accepted_by_name: acceptedByName
        });
        if (result.data && result.data.success) {
          // Emit event for real-time updates
          eventBus.emit(EVENTS.PAYMENT_CREATED, { orderId: order.id, paymentType: type });
          eventBus.emit(EVENTS.FINANCE_UPDATED, { orderId: order.id });
          onUpdate?.();
        }
      }
    } finally {
      setLoading(null);
    }
  };

  const handleCurrencyChange = (cur) => {
    setDepositCurrency(cur);
    setExchangeRate(RATES[cur] || 1);
  };

  return (
    <div className="mt-3 grid grid-cols-12 gap-3">
      {/* Quick stats */}
      <div className="col-span-12">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <Card><CardBd><div className="text-xs text-slate-500">Нараховано</div><div className="mt-1 text-xl font-semibold">{money(order.rent.accrued)}</div></CardBd></Card>
          <Card><CardBd><div className="text-xs text-slate-500">Оплачено</div><div className="mt-1 text-xl font-semibold text-emerald-600">{money(order.rent.paid)}</div></CardBd></Card>
          <Card><CardBd><div className="text-xs text-slate-500">Очікувана застава</div><div className="mt-1 text-xl font-semibold">{money(order.deposit.expected)}</div><div className="mt-1 text-xs text-slate-500">(не дохід)</div></CardBd></Card>
          <Card><CardBd>
            <div className="text-xs text-slate-500">Фактична застава</div>
            <div className="mt-1 text-xl font-semibold">
              {order.deposit.held > 0 ? (order.deposit.display || money(order.deposit.held)) : '—'}
            </div>
            {order.deposit.held > 0 && order.deposit.currency !== 'UAH' && (
              <div className="text-xs text-slate-400">≈ {money(order.deposit.held)}</div>
            )}
            {order.deposit.held === 0 && <div className="text-xs text-amber-600">Не прийнято</div>}
          </CardBd></Card>
          <Card><CardBd><div className="text-xs text-slate-500">До сплати</div><div className="mt-1 text-xl font-semibold text-rose-700">{money(order.rent.due + order.damage.due)}</div></CardBd></Card>
        </div>
      </div>

      {/* Left: Rent + Charges */}
      <div className="col-span-12 md:col-span-7 space-y-3">
        <Card>
          <CardHd title="Прийом оплати (оренда)" subtitle="CASH/BANK → RENT_REV" right={<Pill t="info">rent</Pill>} />
          <CardBd>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <label className="text-sm"><div className="text-xs text-slate-500 mb-1">Метод</div>
                <select className="w-full rounded-xl border px-3 py-2 text-sm" value={rentMethod} onChange={(e) => setRentMethod(e.target.value)}>
                  <option value="cash">Готівка</option><option value="card">Карта</option><option value="iban">IBAN</option>
                </select>
              </label>
              <label className="text-sm"><div className="text-xs text-slate-500 mb-1">Сума</div>
                <input type="number" className="w-full rounded-xl border px-3 py-2 text-sm" value={rentAmount} onChange={(e) => setRentAmount(Number(e.target.value))} />
              </label>
              <label className="text-sm"><div className="text-xs text-slate-500 mb-1">Примітка</div>
                <input className="w-full rounded-xl border px-3 py-2 text-sm" placeholder="Напр., WayForPay" />
              </label>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Btn variant="primary" onClick={() => handlePayment('rent')} disabled={loading === 'rent' || rentAmount <= 0}>{loading === 'rent' ? '...' : 'Зарахувати'}</Btn>
            </div>
          </CardBd>
        </Card>

        {/* === ШКОДА (Damage) === */}
        <Card>
          <CardHd 
            title="💔 Шкода / Пошкодження" 
            subtitle={`${chargesData.damage?.items?.length || 0} позицій`}
            right={
              chargesData.damage?.due > 0 ? (
                <Pill t="danger">До сплати: {money(chargesData.damage.due)}</Pill>
              ) : (
                <Pill t="ok">Оплачено</Pill>
              )
            } 
          />
          <CardBd>
            {/* Існуючі записи шкоди */}
            {chargesData.damage?.items?.length > 0 && (
              <div className="mb-3 space-y-1 max-h-32 overflow-y-auto">
                {chargesData.damage.items.map((item, i) => (
                  <ChargeRow 
                    key={item.id || i} 
                    item={{...item, amount: item.fee, status: 'pending'}} 
                    type="damage"
                    onUpdate={handleUpdateCharge}
                    onDelete={handleDeleteCharge}
                    onPay={() => {}}
                  />
                ))}
              </div>
            )}
            
            {/* Статистика */}
            <div className="grid grid-cols-3 gap-2 mb-3">
              <div className="rounded-xl border bg-slate-50 p-2 text-center">
                <div className="text-xs text-slate-500">Всього</div>
                <div className="font-semibold">{money(chargesData.damage?.total || 0)}</div>
              </div>
              <div className="rounded-xl border bg-emerald-50 p-2 text-center">
                <div className="text-xs text-slate-500">Оплачено</div>
                <div className="font-semibold text-emerald-600">{money(chargesData.damage?.paid || 0)}</div>
              </div>
              <div className="rounded-xl border bg-rose-50 p-2 text-center">
                <div className="text-xs text-slate-500">До сплати</div>
                <div className="font-semibold text-rose-600">{money(chargesData.damage?.due || 0)}</div>
              </div>
            </div>
            
            {/* Додати нову шкоду */}
            <details className="border rounded-xl">
              <summary className="px-3 py-2 text-sm font-medium cursor-pointer hover:bg-slate-50">➕ Додати шкоду вручну</summary>
              <div className="p-3 border-t space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <input 
                    type="number" 
                    placeholder="Сума ₴" 
                    className="rounded-lg border px-3 py-2 text-sm"
                    value={newDamageAmount || ''}
                    onChange={(e) => setNewDamageAmount(Number(e.target.value))}
                  />
                  <input 
                    placeholder="Опис" 
                    className="rounded-lg border px-3 py-2 text-sm"
                    value={newDamageNote}
                    onChange={(e) => setNewDamageNote(e.target.value)}
                  />
                </div>
                <Btn 
                  variant="primary" 
                  className="w-full"
                  onClick={() => handleAddCharge('damage')}
                  disabled={loading === 'add_damage' || newDamageAmount <= 0}
                >
                  {loading === 'add_damage' ? '...' : 'Додати'}
                </Btn>
              </div>
            </details>
            
            {/* Прийняти оплату за шкоду */}
            {chargesData.damage?.due > 0 && (
              <div className="mt-3">
                <Btn variant="primary" onClick={() => handlePayment('damage')} disabled={loading === 'damage'}>
                  {loading === 'damage' ? '...' : `Прийняти оплату ${money(chargesData.damage.due)}`}
                </Btn>
              </div>
            )}
          </CardBd>
        </Card>

        {/* === ПРОСТРОЧЕННЯ (Late fees) === */}
        <Card>
          <CardHd 
            title="⏰ Прострочення / Часткове повернення" 
            subtitle={`${chargesData.late?.items?.length || 0} записів`}
            right={
              chargesData.late?.due > 0 ? (
                <Pill t="warn">До сплати: {money(chargesData.late.due)}</Pill>
              ) : chargesData.late?.total > 0 ? (
                <Pill t="ok">Оплачено</Pill>
              ) : (
                <Pill t="neutral">Немає</Pill>
              )
            } 
          />
          <CardBd>
            {/* Існуючі записи прострочення */}
            {chargesData.late?.items?.length > 0 && (
              <div className="mb-3 space-y-1 max-h-40 overflow-y-auto">
                {chargesData.late.items.map((item, i) => (
                  <ChargeRow 
                    key={item.id || i} 
                    item={item} 
                    type="late"
                    onUpdate={handleUpdateCharge}
                    onDelete={handleDeleteCharge}
                    onPay={handlePayLateFee}
                  />
                ))}
              </div>
            )}
            
            {/* Статистика */}
            <div className="grid grid-cols-3 gap-2 mb-3">
              <div className="rounded-xl border bg-slate-50 p-2 text-center">
                <div className="text-xs text-slate-500">Всього</div>
                <div className="font-semibold">{money(chargesData.late?.total || 0)}</div>
              </div>
              <div className="rounded-xl border bg-emerald-50 p-2 text-center">
                <div className="text-xs text-slate-500">Оплачено</div>
                <div className="font-semibold text-emerald-600">{money(chargesData.late?.paid || 0)}</div>
              </div>
              <div className="rounded-xl border bg-amber-50 p-2 text-center">
                <div className="text-xs text-slate-500">До сплати</div>
                <div className="font-semibold text-amber-600">{money(chargesData.late?.due || 0)}</div>
              </div>
            </div>
            
            {/* Додати нове прострочення */}
            <details className="border rounded-xl">
              <summary className="px-3 py-2 text-sm font-medium cursor-pointer hover:bg-slate-50">➕ Додати прострочення вручну</summary>
              <div className="p-3 border-t space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <input 
                    type="number" 
                    placeholder="Сума ₴" 
                    className="rounded-lg border px-3 py-2 text-sm"
                    value={newLateAmount || ''}
                    onChange={(e) => setNewLateAmount(Number(e.target.value))}
                  />
                  <input 
                    placeholder="Опис (напр., 3 дні × ₴100)" 
                    className="rounded-lg border px-3 py-2 text-sm"
                    value={newLateNote}
                    onChange={(e) => setNewLateNote(e.target.value)}
                  />
                </div>
                <Btn 
                  variant="primary" 
                  className="w-full"
                  onClick={() => handleAddCharge('late')}
                  disabled={loading === 'add_late' || newLateAmount <= 0}
                >
                  {loading === 'add_late' ? '...' : 'Додати'}
                </Btn>
              </div>
            </details>
          </CardBd>
        </Card>
      </div>

      {/* Right: Deposit */}
      <div className="col-span-12 md:col-span-5 space-y-3">
        <Card>
          <CardHd title="Прийом застави" subtitle="CASH/BANK → DEP_HOLD" right={<Pill t="info">hold</Pill>} />
          <CardBd>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <label className="text-sm"><div className="text-xs text-slate-500 mb-1">Метод</div>
                <select className="w-full rounded-xl border px-3 py-2 text-sm" value={depositMethod} onChange={(e) => setDepositMethod(e.target.value)}>
                  <option value="cash">Готівка</option><option value="card">Карта</option><option value="bank">Банк</option>
                </select>
              </label>
              <label className="text-sm"><div className="text-xs text-slate-500 mb-1">Валюта</div>
                <select className="w-full rounded-xl border px-3 py-2 text-sm" value={depositCurrency} onChange={(e) => handleCurrencyChange(e.target.value)}>
                  <option value="UAH">🇺🇦 UAH (₴)</option>
                  <option value="USD">🇺🇸 USD ($)</option>
                  <option value="EUR">🇪🇺 EUR (€)</option>
                </select>
              </label>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-sm"><div className="text-xs text-slate-500 mb-1">Сума ({currencySymbols[depositCurrency]})</div>
                <input type="number" className="w-full rounded-xl border px-3 py-2 text-sm" value={depositAmount} onChange={(e) => setDepositAmount(Number(e.target.value))} />
              </label>
              {depositCurrency !== 'UAH' && (
                <label className="text-sm"><div className="text-xs text-slate-500 mb-1">Курс</div>
                  <input type="number" step="0.01" className="w-full rounded-xl border px-3 py-2 text-sm" value={exchangeRate} onChange={(e) => setExchangeRate(Number(e.target.value))} />
                </label>
              )}
            </div>
            {depositCurrency !== 'UAH' && (
              <div className="mt-2 rounded-lg bg-sky-50 border border-sky-200 p-2 text-sm text-sky-800">
                💱 Еквівалент: <b>{money(uahEquivalent)}</b> ({depositAmount} {depositCurrency} × {exchangeRate})
              </div>
            )}
            <div className="mt-3"><Btn variant="primary" onClick={() => handlePayment('deposit')} disabled={loading === 'deposit' || depositAmount <= 0}>{loading === 'deposit' ? '...' : 'Прийняти'}</Btn></div>
          </CardBd>
        </Card>

        <Card>
          <CardHd title="Операції із заставою" />
          <CardBd>
            <div className="rounded-2xl border bg-slate-50 p-3 mb-3">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium">Баланс холду</div>
                <div className="text-sm font-semibold">
                  {order.deposit.held > 0 ? (
                    order.deposit.currency !== 'UAH' 
                      ? `${order.deposit.actual_amount} ${order.deposit.currency}` 
                      : money(holdAvailable)
                  ) : '₴0'}
                </div>
              </div>
              {order.deposit.held > 0 ? (
                <div className="mt-1 text-xs text-slate-500">
                  Використано: {money(order.deposit.used_for_damage)} • Повернуто: {money(order.deposit.refunded)}
                </div>
              ) : (
                <div className="mt-1 text-xs text-amber-600">Застава ще не прийнята</div>
              )}
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Btn disabled={holdAvailable <= 0 || order.damage.due <= 0}>На шкоду</Btn>
              <Btn disabled={holdAvailable <= 0}>Повернути</Btn>
            </div>
          </CardBd>
        </Card>

      </div>

      {/* Документи - один великий блок */}
      <div className="col-span-12"><DocumentsPanel orderId={order.id} /></div>

      {/* Journal */}
      <div className="col-span-12">
        <Card>
          <CardHd title="Журнал по замовленню" />
          <CardBd className="p-0">
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-xs text-slate-500">
                  <tr>
                    <th className="px-4 py-3 text-left">Дата</th>
                    <th className="px-4 py-3 text-left">Тип</th>
                    <th className="px-4 py-3 text-left">Назва</th>
                    <th className="px-4 py-3 text-right">Сума</th>
                    <th className="px-4 py-3 text-left">Прийняв</th>
                  </tr>
                </thead>
                <tbody>
                  {order.timeline.map((r, idx) => (
                    <tr key={idx} className="border-t">
                      <td className="px-4 py-3">{r.at}</td>
                      <td className="px-4 py-3"><Pill t="neutral">{r.type}</Pill></td>
                      <td className="px-4 py-3">{r.label}</td>
                      <td className="px-4 py-3 text-right">{money(r.debit || r.credit)}</td>
                      <td className="px-4 py-3 text-slate-600">{r.accepted_by || '—'}</td>
                    </tr>
                  ))}
                  {!order.timeline.length && <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-500">Немає записів</td></tr>}
                </tbody>
              </table>
            </div>
          </CardBd>
        </Card>
      </div>
    </div>
  );
}
