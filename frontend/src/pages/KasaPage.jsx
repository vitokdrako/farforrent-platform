/* eslint-disable */
import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import CorporateHeader from '../components/CorporateHeader';
import {
  ArrowLeft, Banknote, CreditCard, Wallet, TrendingUp, TrendingDown,
  Search, RefreshCw, Shield, RotateCcw, Plus, X, MessageSquare,
  ChevronDown, Landmark, CalendarCheck, Check
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

const authFetch = (url, opts = {}) => {
  const token = localStorage.getItem('token');
  return fetch(url, { ...opts, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...opts.headers } });
};

const fmtUA = (n) => (Number(n) || 0).toLocaleString('uk-UA', { maximumFractionDigits: 0 });
const money = (v) => `₴${fmtUA(v)}`;
const fmtDate = (d) => d ? new Date(d).toLocaleDateString('uk-UA', { day: '2-digit', month: '2-digit', year: '2-digit' }) : '—';
const fmtTime = (d) => d ? new Date(d).toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' }) : '';

export default function KasaPage({ embedded = false }) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState(searchParams.get('period') || 'month');
  const [searchQuery, setSearchQuery] = useState('');
  const [modal, setModal] = useState(null); // 'income' | 'deposit' | 'expense' | 'collection' | 'closeMonth' | null

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await authFetch(`${BACKEND_URL}/api/finance/kasa?period=${period}`);
      if (res.ok) setData(await res.json());
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchData(); }, [period]);

  const changePeriod = (p) => {
    setPeriod(p);
    setSearchParams({ period: p });
  };

  const periodLabels = { day: 'Сьогодні', week: 'Тиждень', month: 'Місяць', all: 'Весь час' };

  const filterBySearch = (items) => {
    if (!searchQuery) return items;
    const q = searchQuery.toLowerCase();
    return items.filter(i =>
      (i.order_number || '').toLowerCase().includes(q) ||
      (i.customer_name || '').toLowerCase().includes(q) ||
      (i.note || '').toLowerCase().includes(q) ||
      (i.description || '').toLowerCase().includes(q) ||
      (i.category_name || '').toLowerCase().includes(q)
    );
  };

  const income = data?.income || { items: [], cash_total: 0, bank_total: 0, total: 0 };
  const deposits = data?.deposits || { items: [], held_total: 0, available_total: 0 };
  const expenses = data?.expenses || { items: [], refunds: [], cash_total: 0, bank_total: 0, total: 0 };
  const summary = data?.summary || { net_cash: 0, net_bank: 0, net_total: 0 };

  const filteredIncome = filterBySearch(income.items);
  const filteredDeposits = filterBySearch(deposits.items);
  const filteredExpenses = filterBySearch([...expenses.items, ...expenses.refunds.map(r => ({ ...r, category_name: 'Повернення застави', expense_type: 'refund' }))]);

  const onCreated = () => { setModal(null); fetchData(); };

  return (
    <div className={embedded ? "font-montserrat" : "min-h-screen bg-slate-50 font-montserrat"} data-testid="kasa-page">
      {!embedded && <CorporateHeader cabinetName="Каса" />}

      {/* Top Bar */}
      <div className={embedded ? "bg-white border-b border-slate-200 rounded-t-xl" : "sticky top-0 z-20 bg-white border-b border-slate-200 shadow-sm"}>
        <div className="max-w-[1800px] mx-auto px-4 py-3">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              {!embedded && (
                <button onClick={() => navigate('/manager-cabinet')} className="p-2 rounded-lg hover:bg-slate-100 text-slate-500" data-testid="back-btn">
                  <ArrowLeft className="w-5 h-5" />
                </button>
              )}
              <div>
                <h1 className="text-lg font-bold text-slate-800">Каса</h1>
                <p className="text-xs text-slate-500">{periodLabels[period]}</p>
              </div>
            </div>

            <div className="flex bg-slate-100 p-1 rounded-xl" data-testid="period-tabs">
              {Object.entries(periodLabels).map(([key, label]) => (
                <button key={key} onClick={() => changePeriod(key)}
                  className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${period === key ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                  data-testid={`period-${key}`}>{label}</button>
              ))}
            </div>

            <div className="flex items-center gap-3">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input type="text" placeholder="Пошук по ордеру, клієнту..." value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 pr-4 py-2 rounded-lg border border-slate-300 text-sm w-64 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  data-testid="search-input" />
              </div>
              <button onClick={fetchData} disabled={loading} className="p-2 rounded-lg border border-slate-300 hover:bg-slate-50" data-testid="refresh-btn">
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>

          {data && (
            <div className="flex items-center gap-6 mt-3 pt-3 border-t border-slate-100 text-sm" data-testid="summary-bar">
              <SummaryPill icon={TrendingUp} label="Дохід" value={money(income.total)} color="emerald" />
              <SummaryPill icon={Banknote} label="Готівка" value={money(income.cash_total)} color="green" sub />
              <SummaryPill icon={CreditCard} label="Безготівка" value={money(income.bank_total)} color="blue" sub />
              <div className="h-5 w-px bg-slate-200" />
              <SummaryPill icon={Shield} label="Застави" value={money(deposits.held_total)} color="amber" />
              <div className="h-5 w-px bg-slate-200" />
              <SummaryPill icon={TrendingDown} label="Витрати" value={money(expenses.total)} color="rose" />
              <div className="h-5 w-px bg-slate-200" />
              {data?.collection?.total > 0 && (
                <>
                  <SummaryPill icon={Landmark} label="Інкасація" value={money(data.collection.total)} color="violet" />
                  <div className="h-5 w-px bg-slate-200" />
                </>
              )}
              <SummaryPill icon={Wallet} label="Чистий дохід" value={money(summary.net_total)} color={summary.net_total >= 0 ? 'emerald' : 'red'} bold />
              <div className="ml-auto flex items-center gap-2">
                <button
                  onClick={() => setModal('closeMonth')}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold transition-colors shadow-sm"
                  data-testid="close-month-btn"
                >
                  <CalendarCheck className="w-3.5 h-3.5" />
                  Закрити місяць
                </button>
                <button
                  onClick={() => setModal('collection')}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold transition-colors shadow-sm"
                  data-testid="collection-btn"
                >
                  <Landmark className="w-3.5 h-3.5" />
                  Інкасація
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 3-Column Layout */}
      <main className="max-w-[1800px] mx-auto px-4 py-6" data-testid="kasa-columns">
        {loading ? (
          <div className="grid grid-cols-3 gap-6">
            {[1,2,3].map(i => <div key={i} className="bg-white rounded-2xl border border-slate-200 p-6 h-96 animate-pulse" />)}
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <IncomeColumn items={filteredIncome} totals={income} navigate={navigate} onAdd={() => setModal('income')} />
            <DepositsColumn items={filteredDeposits} totals={deposits} navigate={navigate} onAdd={() => setModal('deposit')} />
            <ExpensesColumn items={filteredExpenses} totals={expenses} onAdd={() => setModal('expense')} />
          </div>
        )}
      </main>

      {/* Modals */}
      {modal === 'income' && <AddIncomeModal onClose={() => setModal(null)} onCreated={onCreated} />}
      {modal === 'deposit' && <AddDepositModal onClose={() => setModal(null)} onCreated={onCreated} />}
      {modal === 'expense' && <AddExpenseModal onClose={() => setModal(null)} onCreated={onCreated} />}
      {modal === 'collection' && <CollectionModal onClose={() => setModal(null)} onCreated={onCreated} />}
      {modal === 'closeMonth' && <CloseMonthModal onClose={() => setModal(null)} onCreated={onCreated} />}
    </div>
  );
}

/* ========== Summary Pill ========== */
function SummaryPill({ icon: Icon, label, value, color, sub, bold }) {
  const colorMap = {
    emerald: 'text-emerald-700', green: 'text-green-600', blue: 'text-blue-600',
    amber: 'text-amber-600', rose: 'text-rose-600', red: 'text-red-600',
    violet: 'text-indigo-600',
  };
  return (
    <div className={`flex items-center gap-1.5 ${sub ? 'opacity-75' : ''}`}>
      <Icon className={`w-3.5 h-3.5 ${colorMap[color] || 'text-slate-500'}`} />
      <span className="text-slate-500 text-xs">{label}:</span>
      <span className={`${bold ? 'font-bold text-sm' : 'font-semibold text-xs'} ${colorMap[color] || 'text-slate-700'}`}>{value}</span>
    </div>
  );
}

/* ========== Column Header with + button ========== */
function ColumnHeader({ icon: Icon, title, count, total, totalLabel, color, onAdd, children }) {
  const bg = { emerald: 'bg-emerald-50/50', amber: 'bg-amber-50/50', rose: 'bg-rose-50/50' };
  const border = { emerald: 'border-emerald-100', amber: 'border-amber-100', rose: 'border-rose-100' };
  const iconBg = { emerald: 'bg-emerald-100 text-emerald-700', amber: 'bg-amber-100 text-amber-700', rose: 'bg-rose-100 text-rose-700' };
  const totalColor = { emerald: 'text-emerald-700', amber: 'text-amber-700', rose: 'text-rose-700' };
  const btnColor = { emerald: 'bg-emerald-600 hover:bg-emerald-700', amber: 'bg-amber-600 hover:bg-amber-700', rose: 'bg-rose-600 hover:bg-rose-700' };

  return (
    <div className={`px-5 py-4 border-b ${border[color]} ${bg[color]}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${iconBg[color]}`}>
            <Icon className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-semibold text-slate-800">{title}</h3>
            <p className="text-xs text-slate-500">{count} операцій</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-right">
            <div className={`font-bold text-lg ${totalColor[color]}`}>{totalLabel || money(total)}</div>
          </div>
          <button
            onClick={onAdd}
            className={`w-8 h-8 rounded-lg text-white flex items-center justify-center transition-colors shadow-sm ${btnColor[color]}`}
            data-testid={`add-${color}-btn`}
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>
      </div>
      {children}
    </div>
  );
}

/* ========== Note display ========== */
function NoteDisplay({ note, description }) {
  const text = description || note;
  if (!text) return null;
  return (
    <div className="flex items-start gap-1 mt-1">
      <MessageSquare className="w-3 h-3 text-slate-400 mt-0.5 flex-shrink-0" />
      <span className="text-[11px] text-slate-500 italic leading-tight">{text}</span>
    </div>
  );
}

/* ========== COLUMN 1: INCOME ========== */
function IncomeColumn({ items, totals, navigate, onAdd }) {
  return (
    <section className="rounded-2xl border border-emerald-200 ring-2 ring-emerald-100 bg-white shadow-sm" data-testid="income-column">
      <ColumnHeader icon={TrendingUp} title="Дохід" count={items.length} total={totals.total} color="emerald" onAdd={onAdd}>
        <div className="flex gap-3 text-[11px] text-slate-500 mt-1">
          <span><Banknote className="w-3 h-3 inline mr-0.5" />{money(totals.cash_total)}</span>
          <span><CreditCard className="w-3 h-3 inline mr-0.5" />{money(totals.bank_total)}</span>
        </div>
      </ColumnHeader>
      <div className="p-3 space-y-1.5 max-h-[calc(100vh-340px)] overflow-y-auto">
        {items.length === 0 ? <EmptyState text="Немає оплат за цей період" /> : items.map(item => (
          <div key={item.id}
            className="px-3 py-2.5 rounded-xl border border-slate-100 hover:border-emerald-200 hover:bg-emerald-50/30 transition-all cursor-pointer group"
            onClick={() => item.order_id && navigate(`/order/${item.order_id}/view`)}
            data-testid={`income-item-${item.id}`}>
            <div className="flex items-center gap-3">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${item.method === 'cash' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'}`}>
                {item.method === 'cash' ? <Banknote className="w-4 h-4" /> : <CreditCard className="w-4 h-4" />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-slate-700">{item.order_number || '—'}</span>
                  <TypeBadge type={item.type} label={item.type_label} />
                </div>
                <div className="text-xs text-slate-500 truncate">{item.customer_name || ''}</div>
              </div>
              <div className="text-right flex-shrink-0">
                <div className="font-bold text-emerald-700 text-sm">+{money(item.amount)}</div>
                <div className="text-[10px] text-slate-400">{fmtDate(item.date)} {fmtTime(item.date)}</div>
              </div>
            </div>
            <NoteDisplay note={item.note} description={item.description} />
          </div>
        ))}
      </div>
    </section>
  );
}

/* ========== COLUMN 2: DEPOSITS ========== */
function DepositsColumn({ items, totals, navigate, onAdd }) {
  return (
    <section className="rounded-2xl border border-amber-200 ring-2 ring-amber-100 bg-white shadow-sm" data-testid="deposits-column">
      <ColumnHeader icon={Shield} title="Застави" count={items.length} total={totals.held_total} color="amber" onAdd={onAdd}>
        <div className="flex gap-3 mt-1.5 pt-1.5 border-t border-amber-100 text-[11px]">
          <span className="text-slate-500"><Banknote className="w-3 h-3 inline mr-0.5" />Гот: {money(totals.cash_received || 0)}</span>
          <span className="text-slate-500"><CreditCard className="w-3 h-3 inline mr-0.5" />Безгот: {money(totals.bank_received || 0)}</span>
          <span className="text-rose-500 ml-auto">Утрим: {money(totals.used_total)}</span>
          <span className="text-blue-500">Поверн: {money(totals.refunded_total)}</span>
        </div>
      </ColumnHeader>
      <div className="p-3 space-y-1.5 max-h-[calc(100vh-340px)] overflow-y-auto">
        {items.length === 0 ? <EmptyState text="Немає застав за цей період" /> : items.map(item => {
          const statusCfg = {
            holding: { label: 'Активна', cls: 'bg-amber-100 text-amber-700' },
            partially_used: { label: 'Частк.', cls: 'bg-orange-100 text-orange-700' },
            fully_used: { label: 'Використано', cls: 'bg-rose-100 text-rose-700' },
            refunded: { label: 'Повернуто', cls: 'bg-blue-100 text-blue-700' },
          };
          const st = statusCfg[item.status] || { label: item.status, cls: 'bg-slate-100 text-slate-600' };
          const curr = item.currency === 'USD' ? '$' : item.currency === 'EUR' ? '€' : '₴';
          return (
            <div key={item.id}
              className="px-3 py-2.5 rounded-xl border border-slate-100 hover:border-amber-200 hover:bg-amber-50/30 transition-all cursor-pointer"
              onClick={() => item.order_id && navigate(`/order/${item.order_id}/return-settlement`)}
              data-testid={`deposit-item-${item.id}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-xs font-semibold text-slate-700">{item.order_number || '—'}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${st.cls}`}>{st.label}</span>
                </div>
                <div className="font-bold text-amber-700 text-sm">{curr}{fmtUA(item.actual_amount)}</div>
              </div>
              <div className="flex items-center justify-between mt-1">
                <span className="text-xs text-slate-500 truncate">{item.customer_name}</span>
                <span className="text-[10px] text-slate-400">{fmtDate(item.opened_at)}</span>
              </div>
              {(item.used_amount > 0 || item.refunded_amount > 0) && (
                <div className="flex gap-3 mt-1.5 text-[10px]">
                  {item.used_amount > 0 && <span className="text-rose-600">Утримано: {money(item.used_amount)}</span>}
                  {item.refunded_amount > 0 && <span className="text-blue-600">Повернуто: {money(item.refunded_amount)}</span>}
                  <span className="text-emerald-600 ml-auto">Доступно: {money(item.available)}</span>
                </div>
              )}
              <NoteDisplay note={item.note} />
            </div>
          );
        })}
      </div>
    </section>
  );
}

/* ========== COLUMN 3: EXPENSES ========== */
function ExpensesColumn({ items, totals, onAdd }) {
  return (
    <section className="rounded-2xl border border-rose-200 ring-2 ring-rose-100 bg-white shadow-sm" data-testid="expenses-column">
      <ColumnHeader icon={TrendingDown} title="Витрати" count={items.length} total={totals.total} color="rose" onAdd={onAdd}>
        <div className="flex gap-3 text-[11px] text-slate-500 mt-1">
          <span><Banknote className="w-3 h-3 inline mr-0.5" />{money(totals.cash_total)}</span>
          <span><CreditCard className="w-3 h-3 inline mr-0.5" />{money(totals.bank_total)}</span>
        </div>
      </ColumnHeader>
      <div className="p-3 space-y-1.5 max-h-[calc(100vh-340px)] overflow-y-auto">
        {items.length === 0 ? <EmptyState text="Немає витрат за цей період" /> : items.map((item, idx) => {
          const isRefund = item.expense_type === 'refund';
          const isCollection = item.expense_type === 'collection' || item.category_code === 'COLLECTION';
          return (
            <div key={item.id || idx}
              className="px-3 py-2.5 rounded-xl border border-slate-100 hover:border-rose-200 hover:bg-rose-50/30 transition-all"
              data-testid={`expense-item-${item.id || idx}`}>
              <div className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                  isCollection ? 'bg-indigo-100 text-indigo-700' : isRefund ? 'bg-blue-100 text-blue-700' : item.method === 'cash' ? 'bg-red-100 text-red-700' : 'bg-pink-100 text-pink-700'
                }`}>
                  {isCollection ? <Landmark className="w-4 h-4" /> : isRefund ? <RotateCcw className="w-4 h-4" /> : item.method === 'cash' ? <Banknote className="w-4 h-4" /> : <CreditCard className="w-4 h-4" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-semibold text-slate-700">
                    {isCollection ? 'Інкасація' : isRefund ? 'Повернення застави' : (item.category_name || 'Витрата')}
                  </div>
                  <div className="text-xs text-slate-500 truncate">
                    {isCollection ? (item.method === 'cash' ? 'Готівка' : 'Безготівка') : isRefund ? `${item.order_number} · ${item.customer_name}` : ''}
                  </div>
                </div>
                <div className="text-right flex-shrink-0">
                  <div className={`font-bold text-sm ${isCollection ? 'text-indigo-700' : isRefund ? 'text-blue-700' : 'text-rose-700'}`}>-{money(item.amount)}</div>
                  <div className="text-[10px] text-slate-400">{fmtDate(item.date)}</div>
                </div>
              </div>
              <NoteDisplay note={item.note} />
            </div>
          );
        })}
      </div>
    </section>
  );
}

/* ========== Badges / Empty ========== */
function TypeBadge({ type, label }) {
  const colors = {
    rent: 'bg-emerald-100 text-emerald-700', additional: 'bg-violet-100 text-violet-700',
    damage: 'bg-rose-100 text-rose-700', late: 'bg-red-100 text-red-700',
  };
  return <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${colors[type] || 'bg-slate-100 text-slate-600'}`}>{label}</span>;
}

function EmptyState({ text }) {
  return <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center"><div className="text-slate-400 text-sm">{text}</div></div>;
}


/* ============================================================ */
/*  MODAL: ADD INCOME                                            */
/* ============================================================ */
function AddIncomeModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ payment_type: 'rent', method: 'cash', amount: '', order_id: '', note: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const userEmail = localStorage.getItem('user_email') || '';

  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const submit = async () => {
    if (!form.amount || Number(form.amount) <= 0) return setError('Вкажіть суму');
    setSaving(true); setError('');
    try {
      const body = {
        payment_type: form.payment_type,
        method: form.method,
        amount: Number(form.amount),
        note: form.note || undefined,
        accepted_by_name: userEmail,
      };
      if (form.order_id) body.order_id = Number(form.order_id);
      const res = await authFetch(`${BACKEND_URL}/api/finance/payments`, { method: 'POST', body: JSON.stringify(body) });
      if (res.ok) { onCreated(); } else {
        const d = await res.json().catch(() => ({}));
        setError(d.detail || 'Помилка збереження');
      }
    } catch (e) { setError(e.message); }
    finally { setSaving(false); }
  };

  const typeOpts = [
    { value: 'rent', label: 'Оренда' },
    { value: 'additional', label: 'Донарахування' },
    { value: 'damage', label: 'Шкода' },
    { value: 'late', label: 'Прострочення' },
  ];

  return (
    <ModalWrapper onClose={onClose} title="Внести дохід" color="emerald">
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <FieldSelect label="Тип" value={form.payment_type} onChange={v => set('payment_type', v)} options={typeOpts} testId="income-type" />
          <FieldSelect label="Метод" value={form.method} onChange={v => set('method', v)}
            options={[{ value: 'cash', label: 'Готівка' }, { value: 'bank', label: 'Безготівка' }]} testId="income-method" />
        </div>
        <FieldInput label="Сума (грн)" type="number" value={form.amount} onChange={v => set('amount', v)} testId="income-amount" placeholder="0" />
        <FieldInput label="Номер ордеру (ID)" type="number" value={form.order_id} onChange={v => set('order_id', v)} testId="income-order" placeholder="необов'язково" />
        <FieldTextarea label="Коментар" value={form.note} onChange={v => set('note', v)} testId="income-note" placeholder="Опис оплати..." />
        {error && <div className="text-red-600 text-sm bg-red-50 rounded-lg p-2">{error}</div>}
        <button onClick={submit} disabled={saving}
          className="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-sm transition-colors disabled:opacity-50"
          data-testid="income-submit-btn">
          {saving ? 'Зберігаю...' : 'Внести дохід'}
        </button>
      </div>
    </ModalWrapper>
  );
}


/* ============================================================ */
/*  MODAL: ADD DEPOSIT                                           */
/* ============================================================ */
function AddDepositModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ order_id: '', amount: '', currency: 'UAH', exchange_rate: '', method: 'cash', note: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const userEmail = localStorage.getItem('user_email') || '';

  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const submit = async () => {
    if (!form.order_id) return setError('Вкажіть ID ордеру');
    if (!form.amount || Number(form.amount) <= 0) return setError('Вкажіть суму');
    setSaving(true); setError('');
    try {
      const body = {
        order_id: Number(form.order_id),
        actual_amount: Number(form.amount),
        expected_amount: Number(form.amount),
        currency: form.currency,
        exchange_rate: form.currency !== 'UAH' && form.exchange_rate ? Number(form.exchange_rate) : null,
        method: form.method,
        note: form.note || undefined,
        accepted_by_name: userEmail,
      };
      const res = await authFetch(`${BACKEND_URL}/api/finance/deposits/create`, { method: 'POST', body: JSON.stringify(body) });
      if (res.ok) { onCreated(); } else {
        const d = await res.json().catch(() => ({}));
        setError(d.detail || 'Помилка збереження');
      }
    } catch (e) { setError(e.message); }
    finally { setSaving(false); }
  };

  return (
    <ModalWrapper onClose={onClose} title="Внести заставу" color="amber">
      <div className="space-y-4">
        <FieldInput label="ID ордеру" type="number" value={form.order_id} onChange={v => set('order_id', v)} testId="deposit-order" placeholder="Номер ордеру" />
        <div className="grid grid-cols-2 gap-3">
          <FieldInput label="Сума" type="number" value={form.amount} onChange={v => set('amount', v)} testId="deposit-amount" placeholder="0" />
          <FieldSelect label="Валюта" value={form.currency} onChange={v => set('currency', v)}
            options={[{ value: 'UAH', label: 'UAH' }, { value: 'USD', label: 'USD' }, { value: 'EUR', label: 'EUR' }]} testId="deposit-currency" />
        </div>
        {form.currency !== 'UAH' && (
          <FieldInput label="Курс до UAH" type="number" value={form.exchange_rate} onChange={v => set('exchange_rate', v)} testId="deposit-rate" placeholder="41.5" />
        )}
        <FieldSelect label="Метод" value={form.method} onChange={v => set('method', v)}
          options={[{ value: 'cash', label: 'Готівка' }, { value: 'bank', label: 'Безготівка' }]} testId="deposit-method" />
        <FieldTextarea label="Коментар" value={form.note} onChange={v => set('note', v)} testId="deposit-note" placeholder="Примітка до застави..." />
        {error && <div className="text-red-600 text-sm bg-red-50 rounded-lg p-2">{error}</div>}
        <button onClick={submit} disabled={saving}
          className="w-full py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-semibold text-sm transition-colors disabled:opacity-50"
          data-testid="deposit-submit-btn">
          {saving ? 'Зберігаю...' : 'Внести заставу'}
        </button>
      </div>
    </ModalWrapper>
  );
}


/* ============================================================ */
/*  MODAL: ADD EXPENSE                                           */
/* ============================================================ */
function AddExpenseModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ category_code: 'OTHER', method: 'cash', amount: '', note: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const categoryOpts = [
    { value: 'OTHER', label: 'Інші витрати' },
    { value: 'RENT_EXPENSE', label: 'Витрати на оренду' },
    { value: 'DAMAGE_EXPENSE', label: 'Реставрація' },
    { value: 'SALARY', label: 'Зарплата' },
    { value: 'MARKETING', label: 'Маркетинг' },
    { value: 'OFFICE', label: 'Офісні витрати' },
    { value: 'REPAIR', label: 'Ремонт' },
    { value: 'TRANSPORT', label: 'Транспорт' },
    { value: 'LAUNDRY', label: 'Хімчистка' },
  ];

  const submit = async () => {
    if (!form.amount || Number(form.amount) <= 0) return setError('Вкажіть суму');
    setSaving(true); setError('');
    try {
      const body = {
        expense_type: 'expense',
        category_code: form.category_code,
        method: form.method,
        amount: Number(form.amount),
        note: form.note || undefined,
      };
      const res = await authFetch(`${BACKEND_URL}/api/finance/expenses`, { method: 'POST', body: JSON.stringify(body) });
      if (res.ok) { onCreated(); } else {
        const d = await res.json().catch(() => ({}));
        setError(d.detail || 'Помилка збереження');
      }
    } catch (e) { setError(e.message); }
    finally { setSaving(false); }
  };

  return (
    <ModalWrapper onClose={onClose} title="Записати витрату" color="rose">
      <div className="space-y-4">
        <FieldSelect label="Категорія" value={form.category_code} onChange={v => set('category_code', v)} options={categoryOpts} testId="expense-category" />
        <div className="grid grid-cols-2 gap-3">
          <FieldInput label="Сума (грн)" type="number" value={form.amount} onChange={v => set('amount', v)} testId="expense-amount" placeholder="0" />
          <FieldSelect label="Метод" value={form.method} onChange={v => set('method', v)}
            options={[{ value: 'cash', label: 'Готівка' }, { value: 'bank', label: 'Безготівка' }]} testId="expense-method" />
        </div>
        <FieldTextarea label="Коментар" value={form.note} onChange={v => set('note', v)} testId="expense-note" placeholder="Опис витрати..." />
        {error && <div className="text-red-600 text-sm bg-red-50 rounded-lg p-2">{error}</div>}
        <button onClick={submit} disabled={saving}
          className="w-full py-2.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-semibold text-sm transition-colors disabled:opacity-50"
          data-testid="expense-submit-btn">
          {saving ? 'Зберігаю...' : 'Записати витрату'}
        </button>
      </div>
    </ModalWrapper>
  );
}


/* ============================================================ */
/*  MODAL: COLLECTION (Інкасація)                                */
/* ============================================================ */
function CollectionModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ method: 'cash', amount: '', note: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const userEmail = localStorage.getItem('user_email') || '';

  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const submit = async () => {
    if (!form.amount || Number(form.amount) <= 0) return setError('Вкажіть суму');
    setSaving(true); setError('');
    try {
      const body = {
        amount: Number(form.amount),
        method: form.method,
        note: form.note || undefined,
        collected_by: userEmail,
      };
      const res = await authFetch(`${BACKEND_URL}/api/finance/collection`, { method: 'POST', body: JSON.stringify(body) });
      if (res.ok) { onCreated(); } else {
        const d = await res.json().catch(() => ({}));
        setError(d.detail || 'Помилка збереження');
      }
    } catch (e) { setError(e.message); }
    finally { setSaving(false); }
  };

  return (
    <ModalWrapper onClose={onClose} title="Інкасація" color="indigo">
      <div className="space-y-4">
        <div className="p-3 rounded-xl bg-indigo-50 border border-indigo-100">
          <p className="text-xs text-indigo-700">Вилучення грошей з каси. Оберіть тип (готівка / безготівка) та суму.</p>
        </div>
        <FieldSelect label="Тип" value={form.method} onChange={v => set('method', v)}
          options={[{ value: 'cash', label: 'Готівка' }, { value: 'bank', label: 'Безготівка' }]} testId="collection-method" />
        <FieldInput label="Сума (грн)" type="number" value={form.amount} onChange={v => set('amount', v)} testId="collection-amount" placeholder="0" />
        <FieldTextarea label="Коментар" value={form.note} onChange={v => set('note', v)} testId="collection-note" placeholder="Призначення інкасації..." />
        {error && <div className="text-red-600 text-sm bg-red-50 rounded-lg p-2">{error}</div>}
        <button onClick={submit} disabled={saving}
          className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm transition-colors disabled:opacity-50"
          data-testid="collection-submit-btn">
          {saving ? 'Зберігаю...' : 'Провести інкасацію'}
        </button>
      </div>
    </ModalWrapper>
  );
}


/* ============================================================ */
/*  MODAL: CLOSE MONTH (Закриття місяця)                         */
/* ============================================================ */
function CloseMonthModal({ onClose, onCreated }) {
  const now = new Date();
  const prevMonth = now.getMonth() === 0 ? 12 : now.getMonth();
  const prevYear = now.getMonth() === 0 ? now.getFullYear() - 1 : now.getFullYear();
  
  const [year, setYear] = useState(prevYear);
  const [month, setMonth] = useState(prevMonth);
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  const monthNames = ['Січень','Лютий','Березень','Квітень','Травень','Червень','Липень','Серпень','Вересень','Жовтень','Листопад','Грудень'];

  const submit = async () => {
    setSaving(true); setError('');
    try {
      const user = JSON.parse(localStorage.getItem('user') || '{}');
      const body = {
        year, month, note,
        closed_by: user.firstname ? `${user.firstname} ${user.lastname || ''}`.trim() : (user.email || ''),
        closed_by_id: user.user_id,
      };
      const res = await authFetch(`${BACKEND_URL}/api/finance/close-month`, { method: 'POST', body: JSON.stringify(body) });
      const data = await res.json();
      if (res.ok) {
        setResult(data.report);
      } else {
        setError(data.detail || 'Помилка');
      }
    } catch (e) { setError(e.message); }
    finally { setSaving(false); }
  };

  if (result) {
    const r = result;
    return (
      <ModalWrapper onClose={() => { onCreated(); }} title={`Місяць ${monthNames[month-1]} ${year} закрито`} color="emerald">
        <div className="space-y-3" data-testid="close-month-result">
          <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-center">
            <Check className="w-8 h-8 text-emerald-600 mx-auto mb-1" />
            <p className="text-sm font-semibold text-emerald-700">Звіт збережено</p>
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="bg-slate-50 rounded-lg p-2.5">
              <div className="text-xs text-slate-500">Дохід</div>
              <div className="font-bold text-emerald-700">{money(r.income?.total || 0)}</div>
              <div className="text-[10px] text-slate-400">готівка {money(r.income?.cash || 0)} · банк {money(r.income?.bank || 0)}</div>
            </div>
            <div className="bg-slate-50 rounded-lg p-2.5">
              <div className="text-xs text-slate-500">Витрати + Повернення</div>
              <div className="font-bold text-rose-600">{money((r.expenses?.total || 0) + (r.refunds?.total || 0))}</div>
            </div>
            <div className="bg-slate-50 rounded-lg p-2.5">
              <div className="text-xs text-slate-500">Застави отримано</div>
              <div className="font-bold text-amber-700">{money(r.deposits?.total_held || 0)}</div>
            </div>
            <div className="bg-slate-50 rounded-lg p-2.5">
              <div className="text-xs text-slate-500">Застави повернено</div>
              <div className="font-bold text-amber-600">{money(r.deposits?.total_refunded || 0)}</div>
            </div>
            <div className="col-span-2 bg-slate-800 rounded-lg p-3 text-center">
              <div className="text-xs text-slate-300">Чистий дохід</div>
              <div className="text-lg font-extrabold text-white">{money(r.summary?.net_total || 0)}</div>
            </div>
          </div>
          <p className="text-xs text-slate-500 text-center">Звіт доступний в Адмін-панелі → Звіти</p>
        </div>
      </ModalWrapper>
    );
  }

  return (
    <ModalWrapper onClose={onClose} title="Закриття місяця" color="indigo">
      <div className="space-y-4" data-testid="close-month-form">
        <div className="p-3 rounded-xl bg-amber-50 border border-amber-200">
          <p className="text-xs text-amber-800">
            Система зафіксує всі фінансові операції за обраний місяць і створить підсумковий звіт.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Місяць</label>
            <select value={month} onChange={e => setMonth(Number(e.target.value))}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white"
              data-testid="close-month-month">
              {monthNames.map((m, i) => <option key={i} value={i+1}>{m}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Рік</label>
            <select value={year} onChange={e => setYear(Number(e.target.value))}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white"
              data-testid="close-month-year">
              {[now.getFullYear(), now.getFullYear()-1, now.getFullYear()-2].map(y => 
                <option key={y} value={y}>{y}</option>
              )}
            </select>
          </div>
        </div>
        <FieldTextarea label="Примітка (необов'язково)" value={note} onChange={setNote} testId="close-month-note" placeholder="Коментар до закриття..." />
        {error && <div className="text-red-600 text-sm bg-red-50 rounded-lg p-2">{error}</div>}
        <button onClick={submit} disabled={saving}
          className="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-slate-900 text-white font-semibold text-sm transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          data-testid="close-month-submit-btn">
          <CalendarCheck className="w-4 h-4" />
          {saving ? 'Зберігаю...' : `Закрити ${monthNames[month-1]} ${year}`}
        </button>
      </div>
    </ModalWrapper>
  );
}


/*  SHARED FORM COMPONENTS                                       */
/* ============================================================ */
function ModalWrapper({ onClose, title, color, children }) {
  const titleColor = { emerald: 'text-emerald-700', amber: 'text-amber-700', rose: 'text-rose-700', indigo: 'text-indigo-700' };
  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={onClose} data-testid="modal-overlay">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
          <h2 className={`text-lg font-bold ${titleColor[color]}`}>{title}</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400" data-testid="modal-close-btn">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="px-6 py-5">{children}</div>
      </div>
    </div>
  );
}

function FieldInput({ label, type, value, onChange, testId, placeholder }) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-600 mb-1">{label}</label>
      <input type={type || 'text'} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}
        className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        data-testid={testId} />
    </div>
  );
}

function FieldSelect({ label, value, onChange, options, testId }) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-600 mb-1">{label}</label>
      <select value={value} onChange={e => onChange(e.target.value)}
        className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
        data-testid={testId}>
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

function FieldTextarea({ label, value, onChange, testId, placeholder }) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-600 mb-1">{label}</label>
      <textarea value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} rows={2}
        className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
        data-testid={testId} />
    </div>
  );
}
