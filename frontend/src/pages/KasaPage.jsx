/* eslint-disable */
import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import CorporateHeader from '../components/CorporateHeader';
import {
  ArrowLeft, Banknote, CreditCard, Wallet, TrendingUp, TrendingDown,
  Search, RefreshCw, Shield, RotateCcw, Plus, X, MessageSquare,
  ChevronDown, Landmark, CalendarCheck, Check, Users, BarChart3,
  ClipboardCheck, ChevronRight, AlertCircle
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
  const [modal, setModal] = useState(null);
  const [activeView, setActiveView] = useState('kasa'); // kasa | plan | debts | report | summary
  const [mobileSearch, setMobileSearch] = useState(false);

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
  const closedMonths = data?.closed_months || [];
  const carryOver = data?.carry_over_balance || 0;

  // Фактичний баланс каси = перенесений залишок + (відкриті доходи - відкриті витрати)
  const openIncItems = income.items.filter(i => !i._closed);
  const openExpItems = [...expenses.items, ...expenses.refunds].filter(i => !i._closed);
  const openCashIn = openIncItems.filter(i => i.method === 'cash').reduce((s, i) => s + (i.amount || 0), 0);
  const openBankIn = openIncItems.filter(i => i.method !== 'cash').reduce((s, i) => s + (i.amount || 0), 0);
  const openCashOut = openExpItems.filter(i => i.method === 'cash').reduce((s, i) => s + (i.amount || 0), 0);
  const openBankOut = openExpItems.filter(i => i.method !== 'cash').reduce((s, i) => s + (i.amount || 0), 0);
  const actualCash = carryOver + openCashIn - openCashOut;
  const actualBank = openBankIn - openBankOut;

  const filteredIncome = filterBySearch(income.items);
  const filteredDeposits = filterBySearch(deposits.items);
  const filteredExpenses = filterBySearch([...expenses.items, ...expenses.refunds.map(r => ({ ...r, category_name: 'Повернення застави', expense_type: 'refund' }))]);

  const onCreated = () => { setModal(null); fetchData(); };

  return (
    <div className={embedded ? "font-montserrat" : "min-h-screen bg-slate-50 font-montserrat"} data-testid="kasa-page">
      {!embedded && <CorporateHeader cabinetName="Каса" />}

      {/* Top Bar */}
      <div className={embedded ? "bg-white border-b border-slate-200 rounded-t-xl" : "sticky top-0 z-20 bg-white border-b border-slate-200 shadow-sm"}>
        <div className="max-w-[1800px] mx-auto px-3 sm:px-4 py-2 sm:py-3">
          {/* Row 1: Back + Title + Refresh */}
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 sm:gap-3 min-w-0">
              {!embedded && (
                <button onClick={() => navigate('/manager-cabinet')} className="p-1.5 sm:p-2 rounded-lg hover:bg-slate-100 text-slate-500 flex-shrink-0" data-testid="back-btn">
                  <ArrowLeft className="w-4 h-4 sm:w-5 sm:h-5" />
                </button>
              )}
              <div className="min-w-0">
                <h1 className="text-base sm:text-lg font-bold text-slate-800">Каса</h1>
                <p className="text-[11px] sm:text-xs text-slate-500">{periodLabels[period]}</p>
              </div>
            </div>

            {/* Period tabs - hidden on mobile, shown on sm+ */}
            <div className="hidden sm:flex bg-slate-100 p-1 rounded-xl" data-testid="period-tabs">
              {Object.entries(periodLabels).map(([key, label]) => (
                <button key={key} onClick={() => changePeriod(key)}
                  className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${period === key ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                  data-testid={`period-${key}`}>{label}</button>
              ))}
            </div>

            <div className="flex items-center gap-2">
              {/* Search - icon only on mobile */}
              <div className="relative hidden sm:block">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input type="text" placeholder="Пошук по ордеру, клієнту..." value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 pr-4 py-2 rounded-lg border border-slate-300 text-sm w-48 lg:w-64 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  data-testid="search-input" />
              </div>
              <button onClick={() => setMobileSearch(!mobileSearch)} className="p-2 rounded-lg border border-slate-300 hover:bg-slate-50 sm:hidden" data-testid="search-toggle-btn">
                <Search className="w-4 h-4 text-slate-500" />
              </button>
              <button onClick={fetchData} disabled={loading} className="p-2 rounded-lg border border-slate-300 hover:bg-slate-50 flex-shrink-0" data-testid="refresh-btn">
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>

          {/* Mobile search bar */}
          {mobileSearch && (
            <div className="relative mt-2 sm:hidden">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input type="text" placeholder="Пошук..." value={searchQuery} autoFocus
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 pr-4 py-2 rounded-lg border border-slate-300 text-sm w-full focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                data-testid="search-input-mobile" />
            </div>
          )}

          {/* Mobile period tabs */}
          <div className="flex sm:hidden bg-slate-100 p-0.5 rounded-lg mt-2 overflow-x-auto" data-testid="period-tabs-mobile">
            {Object.entries(periodLabels).map(([key, label]) => (
              <button key={key} onClick={() => changePeriod(key)}
                className={`px-3 py-1 rounded-md text-xs font-medium transition-colors whitespace-nowrap flex-1 ${period === key ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500'}`}
                data-testid={`period-m-${key}`}>{label}</button>
            ))}
          </div>

          {data && (
            <div className="flex flex-wrap items-center gap-3 sm:gap-6 mt-2 sm:mt-3 pt-2 sm:pt-3 border-t border-slate-100 text-sm" data-testid="summary-bar">
              <SummaryPill icon={Banknote} label="Готівка" value={money(actualCash)} color="green" bold />
              <SummaryPill icon={CreditCard} label="Безготівка" value={money(actualBank)} color="blue" bold />
              <div className="flex items-center gap-2 ml-auto">
                <button
                  onClick={() => setModal('closeMonth')}
                  className="flex items-center gap-1 sm:gap-1.5 px-2 sm:px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-900 text-white text-[11px] sm:text-xs font-semibold transition-colors shadow-sm"
                  data-testid="close-month-btn"
                >
                  <CalendarCheck className="w-3 h-3 sm:w-3.5 sm:h-3.5" />
                  <span className="hidden sm:inline">Закрити місяць</span>
                </button>
                <button
                  onClick={() => setModal('collection')}
                  className="flex items-center gap-1 sm:gap-1.5 px-2 sm:px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-[11px] sm:text-xs font-semibold transition-colors shadow-sm"
                  data-testid="collection-btn"
                >
                  <Landmark className="w-3 h-3 sm:w-3.5 sm:h-3.5" />
                  Інкасація
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="max-w-[1800px] mx-auto px-3 sm:px-4 pt-3 sm:pt-4">
        <div className="flex items-center gap-0.5 sm:gap-1 bg-white rounded-xl border border-slate-200 p-0.5 sm:p-1 overflow-x-auto no-scrollbar">
          {[
            { key: 'kasa', label: 'Каса', mobileLabel: 'Каса', icon: Wallet },
            { key: 'plan', label: 'План надходжень', mobileLabel: 'План', icon: TrendingUp },
            { key: 'debts', label: 'Борги менеджерів', mobileLabel: 'Борги', icon: Users },
            { key: 'report', label: 'Звіт витрат', mobileLabel: 'Витрати', icon: BarChart3 },
            { key: 'summary', label: 'Зведення каси', mobileLabel: 'Зведення', icon: ClipboardCheck },
          ].map(tab => (
            <button key={tab.key} onClick={() => setActiveView(tab.key)}
              className={`flex items-center gap-1 sm:gap-1.5 px-2 sm:px-3 py-1.5 rounded-lg text-[11px] sm:text-xs font-semibold transition-all whitespace-nowrap flex-shrink-0 ${
                activeView === tab.key ? 'bg-slate-800 text-white shadow-sm' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'
              }`}
              data-testid={`tab-${tab.key}`}>
              <tab.icon className="w-3 h-3 sm:w-3.5 sm:h-3.5 flex-shrink-0" />
              <span className="sm:hidden">{tab.mobileLabel}</span>
              <span className="hidden sm:inline">{tab.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Kasa Main View */}
      {activeView === 'kasa' && (
      <main className="max-w-[1800px] mx-auto px-3 sm:px-4 py-4 sm:py-6" data-testid="kasa-columns">
        {loading ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
            {[1,2,3].map(i => <div key={i} className="bg-white rounded-2xl border border-slate-200 p-6 h-96 animate-pulse" />)}
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
            <IncomeColumn items={filteredIncome} totals={income} navigate={navigate} onAdd={() => setModal('income')} closedMonths={closedMonths} carryOver={data?.carry_over_balance || 0} />
            <DepositsColumn items={filteredDeposits} totals={deposits} navigate={navigate} onAdd={() => setModal('deposit')} onRefresh={fetchData} />
            <ExpensesColumn items={filteredExpenses} totals={expenses} onAdd={() => setModal('expense')} closedMonths={closedMonths} />
          </div>
        )}
      </main>
      )}

      {/* Plan View */}
      {activeView === 'plan' && <ExpectedIncomeView />}

      {/* Manager Debts */}
      {activeView === 'debts' && <ManagerDebtsView />}

      {/* Expense Report */}
      {activeView === 'report' && <ExpenseReportView />}

      {/* Evening Cash Summary */}
      {activeView === 'summary' && <CashSummaryView />}

      {/* Modals */}
      {modal === 'income' && <AddIncomeModal onClose={() => setModal(null)} onCreated={onCreated} />}
      {modal === 'deposit' && <AddDepositModal onClose={() => setModal(null)} onCreated={onCreated} />}
      {modal === 'expense' && <AddExpenseModal onClose={() => setModal(null)} onCreated={onCreated} />}
      {modal === 'collection' && <CollectionModal onClose={() => setModal(null)} onCreated={onCreated} />}
      {modal === 'closeMonth' && <CloseMonthModal onClose={() => setModal(null)} onCreated={onCreated} />}
    </div>
  );
}

/* ========== Expected Income View (План надходжень) ========== */
function ExpectedIncomeView() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());

  const load = () => {
    setLoading(true);
    authFetch(`${BACKEND_URL}/api/finance/expected-income?month=${month}&year=${year}`)
      .then(r => r.json()).then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  };
  useEffect(load, [month, year]);

  const money = (v) => Number(v || 0).toLocaleString('uk-UA', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  const statusBadge = (s) => {
    if (s === 'paid') return <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-700">Оплачено</span>;
    if (s === 'partial') return <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-700">Частково</span>;
    return <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-red-100 text-red-700">Не оплачено</span>;
  };

  const fmtDate = (d) => { if (!d) return '—'; const dt = new Date(d); return `${dt.getDate().toString().padStart(2,'0')}.${(dt.getMonth()+1).toString().padStart(2,'0')}.${dt.getFullYear()}`; };

  const methodBadge = (item) => {
    if (item.paid === 0) return <span className="text-slate-300">—</span>;
    const hasCash = item.paid_cash > 0;
    const hasBank = item.paid_bank > 0;
    if (hasCash && hasBank) {
      return (
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-green-50 text-green-700 border border-green-200 font-medium">Гот {money(item.paid_cash)}</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 font-medium">Безгот {money(item.paid_bank)}</span>
        </div>
      );
    }
    if (hasCash) return <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-green-50 text-green-700 border border-green-200 font-medium">Готівка</span>;
    return <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 font-medium">Безготівка</span>;
  };

  const MONTHS = ['Січень','Лютий','Березень','Квітень','Травень','Червень','Липень','Серпень','Вересень','Жовтень','Листопад','Грудень'];

  return (
    <div className="max-w-[1800px] mx-auto px-4 py-6">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-800">План надходжень</h2>
          <div className="flex items-center gap-2">
            <select value={month} onChange={e => setMonth(+e.target.value)}
              className="text-xs border border-slate-200 rounded-lg px-2 py-1.5" data-testid="plan-month">
              {MONTHS.map((m, i) => <option key={i+1} value={i+1}>{m}</option>)}
            </select>
            <select value={year} onChange={e => setYear(+e.target.value)}
              className="text-xs border border-slate-200 rounded-lg px-2 py-1.5" data-testid="plan-year">
              {[2025, 2026, 2027].map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
        </div>
        {data?.summary && (
          <div className="grid grid-cols-4 gap-4 p-4 bg-slate-50 border-b border-slate-100">
            <div><div className="text-xs text-slate-500">Очікується</div><div className="text-lg font-bold text-slate-800">{money(data.summary.total_expected)} ₴</div></div>
            <div><div className="text-xs text-slate-500">Оплачено</div><div className="text-lg font-bold text-emerald-600">{money(data.summary.total_paid)} ₴</div></div>
            <div><div className="text-xs text-slate-500">Борг</div><div className="text-lg font-bold text-red-600">{money(data.summary.total_debt)} ₴</div></div>
            <div><div className="text-xs text-slate-500">Замовлень</div><div className="text-lg font-bold text-slate-800">{data.summary.orders_count}</div>
              <div className="text-[10px] text-slate-400">{data.summary.paid_count} опл. / {data.summary.partial_count} частк. / {data.summary.unpaid_count} неопл.</div>
            </div>
          </div>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-slate-50 text-slate-500 border-b">
              <tr>
                <th className="text-left px-4 py-2 font-medium">Замовлення</th>
                <th className="text-left px-4 py-2 font-medium">Клієнт</th>
                <th className="text-left px-4 py-2 font-medium">Менеджер</th>
                <th className="text-left px-4 py-2 font-medium">Дата події</th>
                <th className="text-right px-4 py-2 font-medium">Сума</th>
                <th className="text-right px-4 py-2 font-medium">Оплачено</th>
                <th className="text-center px-4 py-2 font-medium">Метод</th>
                <th className="text-center px-4 py-2 font-medium">Дата оплати</th>
                <th className="text-right px-4 py-2 font-medium">Борг</th>
                <th className="text-center px-4 py-2 font-medium">Статус</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {loading ? (
                <tr><td colSpan="10" className="text-center py-8 text-slate-400">Завантаження...</td></tr>
              ) : data?.items?.length === 0 ? (
                <tr><td colSpan="10" className="text-center py-8 text-slate-400">Немає замовлень за цей місяць</td></tr>
              ) : data?.items?.map(item => (
                <tr key={item.order_id} className={`hover:bg-slate-50 ${item.payment_status === 'paid' ? 'opacity-50' : ''}`}>
                  <td className="px-4 py-2.5 font-semibold text-blue-600">{item.order_number}</td>
                  <td className="px-4 py-2.5 text-slate-700">{item.customer_name}</td>
                  <td className="px-4 py-2.5 text-slate-500">{item.manager || '—'}</td>
                  <td className="px-4 py-2.5 text-slate-500">{fmtDate(item.rental_start)}</td>
                  <td className="px-4 py-2.5 text-right font-medium text-slate-700">{money(item.order_total)}</td>
                  <td className="px-4 py-2.5 text-right font-medium text-emerald-600">{money(item.paid)}</td>
                  <td className="px-4 py-2.5 text-center">{methodBadge(item)}</td>
                  <td className="px-4 py-2.5 text-center text-slate-500 text-[11px]">{item.last_paid_at ? fmtDate(item.last_paid_at) : '—'}</td>
                  <td className="px-4 py-2.5 text-right font-bold text-red-600">{item.debt > 0 ? money(item.debt) : '—'}</td>
                  <td className="px-4 py-2.5 text-center">{statusBadge(item.payment_status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

/* ========== Manager Debts View ========== */
function ManagerDebtsView() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState({});
  const [managers, setManagers] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [showAddPanel, setShowAddPanel] = useState(false);

  const loadManagers = () => {
    authFetch(`${BACKEND_URL}/api/finance/event-managers`).then(r => r.json()).then(setManagers).catch(() => {});
  };
  const loadDebts = () => {
    setLoading(true);
    authFetch(`${BACKEND_URL}/api/finance/manager-debts`)
      .then(r => r.json()).then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  };
  const searchClients = (q) => {
    setSearchQuery(q);
    if (q.length < 2) { setSearchResults([]); return; }
    authFetch(`${BACKEND_URL}/api/finance/available-managers?q=${encodeURIComponent(q)}`)
      .then(r => r.json()).then(setSearchResults).catch(() => {});
  };
  useEffect(() => { loadManagers(); loadDebts(); }, []);

  const addManager = async (client) => {
    await authFetch(`${BACKEND_URL}/api/finance/event-managers`, {
      method: 'POST', body: JSON.stringify({ client_user_id: client.client_user_id, name: client.name })
    });
    setSearchQuery(''); setSearchResults([]);
    loadManagers(); loadDebts();
  };
  const removeManager = async (cid) => {
    await authFetch(`${BACKEND_URL}/api/finance/event-managers/${cid}`, { method: 'DELETE' });
    loadManagers(); loadDebts();
  };

  const money = (v) => Number(v || 0).toLocaleString('uk-UA', { minimumFractionDigits: 0 });
  const toggle = (m) => setExpanded(p => ({ ...p, [m]: !p[m] }));

  return (
    <div className="max-w-[1800px] mx-auto px-4 py-6 space-y-4">
      {/* Manager Selection Panel */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-bold text-slate-800">Івент-менеджери</h2>
            <div className="flex items-center gap-1.5 flex-wrap">
              {managers.map(m => (
                <span key={m.client_user_id} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-blue-50 border border-blue-200 text-xs font-medium text-blue-700">
                  {m.name}
                  <button onClick={() => removeManager(m.client_user_id)} className="ml-0.5 text-blue-400 hover:text-red-500" data-testid={`remove-mgr-${m.client_user_id}`}>
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
              {managers.length === 0 && <span className="text-xs text-slate-400">Додайте менеджерів зі списку клієнтів</span>}
            </div>
          </div>
          <button onClick={() => setShowAddPanel(!showAddPanel)}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold"
            data-testid="add-manager-btn">
            <Plus className="w-3.5 h-3.5" />
            Додати
          </button>
        </div>
        {showAddPanel && (
          <div className="p-3 bg-blue-50 border-b border-blue-100 space-y-2">
            <input type="text" value={searchQuery} onChange={e => searchClients(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-blue-200 rounded-lg outline-none focus:ring-2 focus:ring-blue-300"
              placeholder="Пошук клієнта за ім'ям..." data-testid="search-client-input" autoFocus />
            {searchResults.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {searchResults.map(c => (
                  <button key={c.client_user_id} onClick={() => addManager(c)}
                    className="px-3 py-1.5 rounded-lg bg-white border border-blue-200 text-xs font-medium text-slate-700 hover:bg-blue-100 transition-colors"
                    data-testid={`add-client-${c.client_user_id}`}>
                    {c.name} {c.phone && <span className="text-slate-400 ml-1">{c.phone}</span>}
                  </button>
                ))}
              </div>
            )}
            {searchQuery.length >= 2 && searchResults.length === 0 && (
              <div className="text-xs text-slate-400">Нічого не знайдено</div>
            )}
          </div>
        )}
      </div>

      {/* Debts Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-800">Борги по замовленнях</h2>
          {data && <div className="text-sm font-bold text-red-600">Загальний борг: {money(data.total_debt)} ₴</div>}
        </div>
        {loading ? (
          <div className="p-8 text-center text-slate-400 text-sm">Завантаження...</div>
        ) : managers.length === 0 ? (
          <div className="p-8 text-center text-slate-400 text-sm">Додайте івент-менеджерів щоб побачити борги</div>
        ) : data?.managers?.length === 0 ? (
          <div className="p-8 text-center text-emerald-600 text-sm font-semibold">Боргів немає!</div>
        ) : (
          <div className="divide-y divide-slate-100">
            {data?.managers?.map(mgr => (
              <div key={mgr.manager}>
                <button onClick={() => toggle(mgr.manager)}
                  className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 transition-colors"
                  data-testid={`debt-manager-${mgr.manager}`}>
                  <div className="flex items-center gap-3">
                    <Users className="w-4 h-4 text-slate-400" />
                    <span className="text-sm font-semibold text-slate-700">{mgr.manager}</span>
                    <span className="text-xs text-slate-400">{mgr.orders.length} замовл.</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-red-600">{money(mgr.total_debt)} ₴</span>
                    <ChevronRight className={`w-4 h-4 text-slate-400 transition-transform ${expanded[mgr.manager] ? 'rotate-90' : ''}`} />
                  </div>
                </button>
                {expanded[mgr.manager] && (
                  <div className="bg-slate-50 px-4 pb-3">
                    <table className="w-full text-xs">
                      <thead><tr className="text-slate-400">
                        <th className="text-left py-1.5 font-medium">Замовлення</th>
                        <th className="text-left py-1.5 font-medium">Клієнт</th>
                        <th className="text-left py-1.5 font-medium">Дата</th>
                        <th className="text-right py-1.5 font-medium">Сума</th>
                        <th className="text-right py-1.5 font-medium">Оплачено</th>
                        <th className="text-right py-1.5 font-medium">Борг</th>
                      </tr></thead>
                      <tbody className="divide-y divide-slate-100">
                        {mgr.orders.map(o => (
                          <tr key={o.order_id} className="hover:bg-white">
                            <td className="py-1.5 font-semibold text-blue-600">{o.order_number}</td>
                            <td className="py-1.5 text-slate-600">{o.customer_name}</td>
                            <td className="py-1.5 text-slate-500">{o.rental_start ? new Date(o.rental_start).toLocaleDateString('uk-UA') : '—'}</td>
                            <td className="py-1.5 text-right text-slate-600">{money(o.order_total)}</td>
                            <td className="py-1.5 text-right text-emerald-600">{money(o.paid)}</td>
                            <td className="py-1.5 text-right font-bold text-red-600">{money(o.debt)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ========== Expense Report View (Звіт витрат) ========== */
function ExpenseReportView() {
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState('month');
  const [categoryTree, setCategoryTree] = useState([]);
  const [selectedCodes, setSelectedCodes] = useState(new Set());
  const [expandedParents, setExpandedParents] = useState({});
  const [allExpenses, setAllExpenses] = useState([]);
  const [allItems, setAllItems] = useState([]);
  const [expandedGroups, setExpandedGroups] = useState({});

  // Load categories
  useEffect(() => {
    authFetch(`${BACKEND_URL}/api/finance/categories?type=expense`)
      .then(r => r.json())
      .then(d => {
        const tree = (d.tree || []).filter(p => p.code !== 'COLLECTION');
        setCategoryTree(tree);
        const allCodes = new Set();
        tree.forEach(p => { allCodes.add(p.code); (p.children || []).forEach(c => allCodes.add(c.code)); });
        setSelectedCodes(allCodes);
        const exp = {};
        tree.forEach(p => { exp[p.code] = true; });
        setExpandedParents(exp);
      }).catch(() => {});
  }, []);

  // Load expenses
  useEffect(() => {
    setLoading(true);
    authFetch(`${BACKEND_URL}/api/finance/expense-report?period=${period}`)
      .then(r => r.json())
      .then(d => { 
        setAllExpenses(d.by_detail || []); 
        setAllItems(d.items || []);
        // Expand all groups by default
        const eg = {};
        (d.by_detail || []).forEach(det => { eg[det.parent_code || det.code] = true; });
        setExpandedGroups(eg);
        setLoading(false); 
      })
      .catch(() => setLoading(false));
  }, [period]);

  const money = (v) => Number(v || 0).toLocaleString('uk-UA', { minimumFractionDigits: 0 });
  const fmtDate = (d) => { if (!d) return '—'; const dt = new Date(d); return `${dt.getDate().toString().padStart(2,'0')}.${(dt.getMonth()+1).toString().padStart(2,'0')}`; };
  const fmtDateTime = (d) => { if (!d) return '—'; const dt = new Date(d); return `${dt.getDate().toString().padStart(2,'0')}.${(dt.getMonth()+1).toString().padStart(2,'0')} ${dt.getHours().toString().padStart(2,'0')}:${dt.getMinutes().toString().padStart(2,'0')}`; };

  const toggleParent = (code) => {
    setExpandedParents(p => ({ ...p, [code]: !p[code] }));
  };

  const toggleCheck = (code, isParent, children) => {
    setSelectedCodes(prev => {
      const next = new Set(prev);
      if (isParent) {
        const childCodes = (children || []).map(c => c.code);
        const allSelected = [code, ...childCodes].every(c => next.has(c));
        if (allSelected) {
          next.delete(code);
          childCodes.forEach(c => next.delete(c));
        } else {
          next.add(code);
          childCodes.forEach(c => next.add(c));
        }
      } else {
        if (next.has(code)) next.delete(code);
        else next.add(code);
      }
      return next;
    });
  };

  // Filter items by selected codes
  const filteredItems = allItems.filter(e => selectedCodes.has(e.cat_code) || selectedCodes.has(e.parent_code));
  const filteredTotal = filteredItems.reduce((s, e) => s + e.amount, 0);

  // Group filtered items by parent category
  const grouped = {};
  filteredItems.forEach(item => {
    const key = item.parent_code || item.cat_code;
    if (!grouped[key]) grouped[key] = { name: item.parent_name, items: [], total: 0 };
    grouped[key].items.push(item);
    grouped[key].total += item.amount;
  });

  const periods = [
    { value: 'day', label: 'Сьогодні' }, { value: 'week', label: 'Тиждень' },
    { value: 'month', label: 'Місяць' }, { value: 'quarter', label: 'Квартал' },
    { value: 'year', label: 'Рік' }, { value: 'all', label: 'Весь час' },
  ];

  return (
    <div className="max-w-[1800px] mx-auto px-3 sm:px-4 py-4 sm:py-6">
      {/* Period filter */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        {periods.map(p => (
          <button key={p.value} onClick={() => setPeriod(p.value)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              period === p.value ? 'bg-slate-800 text-white' : 'bg-white border border-slate-200 text-slate-500 hover:bg-slate-50'
            }`} data-testid={`report-period-${p.value}`}>{p.label}</button>
        ))}
        <div className="ml-auto text-lg font-bold text-rose-600">{money(filteredTotal)} ₴</div>
      </div>

      <div className="flex flex-col lg:flex-row gap-4">
        {/* Left: Category checkboxes */}
        <div className="w-full lg:w-72 flex-shrink-0 bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-3 border-b border-slate-100">
            <div className="text-xs font-bold text-slate-700">Статті витрат</div>
          </div>
          <div className="max-h-[400px] lg:max-h-[600px] overflow-y-auto">
            {categoryTree.map(parent => {
              const children = parent.children || [];
              const parentChecked = selectedCodes.has(parent.code);
              const allChildrenChecked = children.every(c => selectedCodes.has(c.code));
              const someChildrenChecked = children.some(c => selectedCodes.has(c.code));
              const isExpanded = expandedParents[parent.code];

              return (
                <div key={parent.code} className="border-b border-slate-50">
                  <div className="flex items-center gap-2 px-3 py-2 hover:bg-slate-50">
                    <input type="checkbox" checked={parentChecked && allChildrenChecked}
                      ref={el => { if (el) el.indeterminate = someChildrenChecked && !allChildrenChecked; }}
                      onChange={() => toggleCheck(parent.code, true, children)}
                      className="w-3.5 h-3.5 text-rose-600 rounded border-slate-300 cursor-pointer"
                      data-testid={`check-${parent.code}`} />
                    <button onClick={() => toggleParent(parent.code)}
                      className="flex-1 text-left text-xs font-semibold text-slate-700 flex items-center justify-between">
                      {parent.name}
                      {children.length > 0 && (
                        <ChevronRight className={`w-3 h-3 text-slate-400 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
                      )}
                    </button>
                  </div>
                  {isExpanded && children.map(child => (
                    <label key={child.code}
                      className="flex items-center gap-2 px-3 pl-8 py-1.5 hover:bg-slate-50 cursor-pointer">
                      <input type="checkbox" checked={selectedCodes.has(child.code)}
                        onChange={() => toggleCheck(child.code, false)}
                        className="w-3 h-3 text-rose-600 rounded border-slate-300"
                        data-testid={`check-${child.code}`} />
                      <span className="text-xs text-slate-600">{child.name}</span>
                    </label>
                  ))}
                </div>
              );
            })}
          </div>
        </div>

        {/* Right: Detailed Results */}
        <div className="flex-1 bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-3 sm:p-4 border-b border-slate-100 flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-800">Деталізація витрат</h2>
            <span className="text-xs text-slate-400">{filteredItems.length} записів</span>
          </div>
          {loading ? (
            <div className="p-8 text-center text-slate-400 text-sm">Завантаження...</div>
          ) : Object.keys(grouped).length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-sm">Немає витрат за обраний період</div>
          ) : (
            <div className="divide-y divide-slate-100 max-h-[calc(100vh-300px)] overflow-y-auto">
              {Object.entries(grouped).sort(([,a],[,b]) => b.total - a.total).map(([code, group]) => {
                const isOpen = expandedGroups[code] !== false;
                return (
                  <div key={code}>
                    <button onClick={() => setExpandedGroups(g => ({ ...g, [code]: !isOpen }))}
                      className="w-full px-3 sm:px-4 py-2.5 flex items-center justify-between hover:bg-slate-50 transition-colors"
                      data-testid={`group-${code}`}>
                      <div className="flex items-center gap-2">
                        <ChevronRight className={`w-3.5 h-3.5 text-slate-400 transition-transform ${isOpen ? 'rotate-90' : ''}`} />
                        <span className="text-sm font-semibold text-slate-700">{group.name}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-500">{group.items.length}</span>
                      </div>
                      <span className="text-sm font-bold text-rose-600">{money(group.total)} ₴</span>
                    </button>
                    {isOpen && (
                      <div className="bg-slate-50/50">
                        {/* Table header */}
                        <div className="hidden sm:grid grid-cols-12 gap-2 px-4 py-1.5 text-[10px] uppercase tracking-wider font-semibold text-slate-400 border-b border-slate-100">
                          <div className="col-span-1">Дата</div>
                          <div className="col-span-2">Категорія</div>
                          <div className="col-span-5">Опис</div>
                          <div className="col-span-2">Метод</div>
                          <div className="col-span-2 text-right">Сума</div>
                        </div>
                        {group.items.map(item => (
                          <div key={item.id} className="px-3 sm:px-4 py-2 border-b border-slate-100/50 hover:bg-white/60 transition-colors">
                            {/* Desktop */}
                            <div className="hidden sm:grid grid-cols-12 gap-2 items-center text-xs">
                              <div className="col-span-1 text-slate-500 font-mono">{fmtDate(item.occurred_at)}</div>
                              <div className="col-span-2 text-slate-600">{item.cat_name}</div>
                              <div className="col-span-5 text-slate-700 break-words whitespace-pre-line">{item.note || '—'}</div>
                              <div className="col-span-2">
                                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${item.method === 'cash' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-blue-50 text-blue-700 border border-blue-200'}`}>
                                  {item.method === 'cash' ? 'Готівка' : 'Безготівка'}
                                </span>
                              </div>
                              <div className="col-span-2 text-right font-bold text-rose-600">{money(item.amount)} ₴</div>
                            </div>
                            {/* Mobile */}
                            <div className="sm:hidden">
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <span className="text-[11px] text-slate-400 font-mono">{fmtDateTime(item.occurred_at)}</span>
                                  <span className={`text-[10px] px-1 py-0.5 rounded ${item.method === 'cash' ? 'bg-green-50 text-green-700' : 'bg-blue-50 text-blue-700'}`}>
                                    {item.method === 'cash' ? 'Гот' : 'Безгот'}
                                  </span>
                                </div>
                                <span className="font-bold text-rose-600 text-xs">{money(item.amount)} ₴</span>
                              </div>
                              <div className="text-[11px] text-slate-600 mt-0.5">{item.cat_name}</div>
                              {item.note && <div className="text-[11px] text-slate-500 mt-0.5 whitespace-pre-line">{item.note}</div>}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ========== Cash Summary View (Щовечірнє зведення) ========== */
function CashSummaryView() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [actualCash, setActualCash] = useState('');
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState(null);

  const load = () => {
    setLoading(true);
    authFetch(`${BACKEND_URL}/api/finance/cash-summaries`)
      .then(r => r.json()).then(d => { setHistory(d); setLoading(false); })
      .catch(() => setLoading(false));
  };
  useEffect(load, []);

  const money = (v) => Number(v || 0).toLocaleString('uk-UA', { minimumFractionDigits: 2 });

  const submit = async () => {
    if (!actualCash) return;
    setSaving(true);
    try {
      const res = await authFetch(`${BACKEND_URL}/api/finance/cash-summary`, {
        method: 'POST', body: JSON.stringify({ actual_cash: Number(actualCash), note })
      });
      const d = await res.json();
      if (d.success) { setResult(d); setShowForm(false); setActualCash(''); setNote(''); load(); }
    } catch (e) {}
    finally { setSaving(false); }
  };

  return (
    <div className="max-w-[1800px] mx-auto px-4 py-6">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-800">Щовечірнє зведення каси</h2>
          <button onClick={() => { setShowForm(!showForm); setResult(null); }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-900 text-white text-xs font-semibold"
            data-testid="new-summary-btn">
            <Plus className="w-3.5 h-3.5" />
            Нове зведення
          </button>
        </div>
        {showForm && (
          <div className="p-4 bg-amber-50 border-b border-amber-100 space-y-3">
            <div className="text-xs font-semibold text-amber-800">Введіть фактичну суму готівки в сейфі:</div>
            <div className="flex items-center gap-3">
              <input type="number" value={actualCash} onChange={e => setActualCash(e.target.value)}
                className="w-48 px-3 py-2 text-sm border border-amber-200 rounded-lg focus:ring-2 focus:ring-amber-300 outline-none"
                placeholder="Сума в сейфі" data-testid="actual-cash-input" />
              <input type="text" value={note} onChange={e => setNote(e.target.value)}
                className="flex-1 px-3 py-2 text-sm border border-amber-200 rounded-lg outline-none"
                placeholder="Коментар (опціонально)" data-testid="summary-note-input" />
              <button onClick={submit} disabled={saving || !actualCash}
                className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold disabled:opacity-50"
                data-testid="submit-summary-btn">
                {saving ? '...' : 'Зберегти'}
              </button>
            </div>
          </div>
        )}
        {result && (
          <div className={`p-4 border-b ${result.difference >= 0 ? 'bg-emerald-50 border-emerald-100' : 'bg-red-50 border-red-100'}`}>
            <div className="flex items-center gap-4 text-sm">
              <div><span className="text-slate-500">Система (РХ):</span> <span className="font-bold">{money(result.system_cash)} ₴</span></div>
              <div><span className="text-slate-500">Факт:</span> <span className="font-bold">{money(result.actual_cash)} ₴</span></div>
              <div><span className="text-slate-500">Різниця:</span> <span className={`font-bold ${result.difference >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>{result.difference >= 0 ? '+' : ''}{money(result.difference)} ₴</span></div>
            </div>
          </div>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-slate-50 text-slate-500 border-b">
              <tr>
                <th className="text-left px-4 py-2 font-medium">Дата</th>
                <th className="text-right px-4 py-2 font-medium">Система (РХ)</th>
                <th className="text-right px-4 py-2 font-medium">Факт в сейфі</th>
                <th className="text-right px-4 py-2 font-medium">Різниця</th>
                <th className="text-left px-4 py-2 font-medium">Коментар</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {loading ? (
                <tr><td colSpan="5" className="text-center py-8 text-slate-400">Завантаження...</td></tr>
              ) : history.length === 0 ? (
                <tr><td colSpan="5" className="text-center py-8 text-slate-400">Ще немає зведень</td></tr>
              ) : history.map(s => (
                <tr key={s.id} className="hover:bg-slate-50">
                  <td className="px-4 py-2.5 font-medium text-slate-700">{s.date ? new Date(s.date).toLocaleDateString('uk-UA') : '—'}</td>
                  <td className="px-4 py-2.5 text-right text-slate-600">{money(s.system_cash)}</td>
                  <td className="px-4 py-2.5 text-right font-medium text-slate-800">{money(s.actual_cash)}</td>
                  <td className={`px-4 py-2.5 text-right font-bold ${s.difference >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                    {s.difference >= 0 ? '+' : ''}{money(s.difference)}
                  </td>
                  <td className="px-4 py-2.5 text-slate-500 truncate max-w-xs">{s.note || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
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
    <div className={`px-3 sm:px-5 py-3 sm:py-4 border-b ${border[color]} ${bg[color]}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <div className={`w-7 h-7 sm:w-8 sm:h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${iconBg[color]}`}>
            <Icon className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
          </div>
          <div className="min-w-0">
            <h3 className="font-semibold text-slate-800 text-sm sm:text-base">{title}</h3>
            <p className="text-[11px] sm:text-xs text-slate-500">{count} операцій</p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <div className="text-right">
            <div className={`font-bold text-base sm:text-lg ${totalColor[color]}`}>{totalLabel || money(total)}</div>
          </div>
          <button
            onClick={onAdd}
            className={`w-7 h-7 sm:w-8 sm:h-8 rounded-lg text-white flex items-center justify-center transition-colors shadow-sm ${btnColor[color]}`}
            data-testid={`add-${color}-btn`}
          >
            <Plus className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
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

/* ========== CLOSED MONTH COLLAPSIBLE BAR (with full items list) ========== */
function ClosedMonthBar({ month, type, items = [] }) {
  const [open, setOpen] = useState(false);
  
  const configs = {
    income: { label: 'Дохід', total: month.income_total || 0, color: 'emerald', borderCls: 'border-emerald-200', bgCls: 'bg-emerald-50', textCls: 'text-emerald-800' },
    deposits: { label: 'Застави', total: month.deposits_held || 0, color: 'amber', borderCls: 'border-amber-200', bgCls: 'bg-amber-50', textCls: 'text-amber-800' },
    expenses: { label: 'Витрати', total: month.expenses_total || 0, color: 'rose', borderCls: 'border-rose-200', bgCls: 'bg-rose-50', textCls: 'text-rose-800' },
  };
  const cfg = configs[type] || configs.income;
  
  return (
    <div className={`rounded-xl border ${cfg.borderCls} overflow-hidden`} data-testid={`closed-month-${month.month}-${type}`}>
      <button onClick={() => setOpen(!open)}
        className={`w-full flex items-center justify-between px-3 py-2 ${cfg.bgCls} hover:brightness-95 transition-all`}>
        <div className="flex items-center gap-2">
          <Check className={`w-3.5 h-3.5 ${cfg.textCls}`} />
          <span className={`text-xs font-bold ${cfg.textCls}`}>{month.label}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-xs font-bold ${cfg.textCls}`}>{money(cfg.total)}</span>
          <span className="text-[10px] text-slate-400">{items.length}</span>
          <ChevronDown className={`w-3.5 h-3.5 ${cfg.textCls} transition-transform ${open ? 'rotate-180' : ''}`} />
        </div>
      </button>
      {open && items.length > 0 && (
        <div className={`max-h-[300px] overflow-y-auto divide-y divide-slate-100`}>
          {items.map((item, idx) => (
            <div key={item.id || idx} className="px-3 py-1.5 flex items-center justify-between hover:bg-slate-50 text-xs">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <span className="font-semibold text-slate-700">{item.order_number || item.category_name || '—'}</span>
                  {item.type_label && <span className="text-[10px] text-slate-400">{item.type_label}</span>}
                  {item.status && type === 'deposits' && <span className="text-[10px] px-1 rounded bg-slate-100 text-slate-500">{item.status}</span>}
                </div>
                <div className="text-[11px] text-slate-400 truncate">{item.customer_name || item.note || ''}</div>
              </div>
              <div className="text-right flex-shrink-0 ml-2">
                <div className={`font-bold ${type === 'expenses' ? 'text-rose-600' : type === 'deposits' ? 'text-amber-700' : 'text-emerald-700'}`}>
                  {type === 'expenses' ? '-' : '+'}{money(item.amount || item.actual_amount || 0)}
                </div>
                <div className="text-[10px] text-slate-400">{fmtDate(item.date || item.opened_at)}</div>
              </div>
            </div>
          ))}
        </div>
      )}
      {open && items.length === 0 && (
        <div className="px-3 py-2 text-[11px] text-slate-400 text-center">Немає записів</div>
      )}
    </div>
  );
}

/* ========== COLUMN 1: INCOME ========== */
function IncomeColumn({ items, totals, navigate, onAdd, closedMonths = [], carryOver = 0 }) {
  // Split items: open (current) vs closed (archived)
  const openItems = items.filter(i => !i._closed);
  const closedPeriods = {};
  items.filter(i => i._closed).forEach(i => {
    const p = i._period || 'unknown';
    if (!closedPeriods[p]) closedPeriods[p] = [];
    closedPeriods[p].push(i);
  });
  
  // Totals for open items only
  const openCash = openItems.filter(i => i.method === 'cash').reduce((s, i) => s + (i.amount || 0), 0);
  const openBank = openItems.filter(i => i.method !== 'cash').reduce((s, i) => s + (i.amount || 0), 0);
  const openTotal = openCash + openBank;

  return (
    <section className="rounded-2xl border border-emerald-200 ring-2 ring-emerald-100 bg-white shadow-sm flex flex-col" data-testid="income-column">
      <ColumnHeader icon={TrendingUp} title="Дохід" count={openItems.length} total={openTotal} color="emerald" onAdd={onAdd}>
        <div className="flex gap-3 text-[11px] text-slate-500 mt-1">
          <span><Banknote className="w-3 h-3 inline mr-0.5" />{money(openCash)}</span>
          <span><CreditCard className="w-3 h-3 inline mr-0.5" />{money(openBank)}</span>
        </div>
      </ColumnHeader>
      {carryOver > 0 && (
        <div className="mx-3 mb-1 px-3 py-1.5 rounded-lg bg-blue-50 border border-blue-200 flex items-center justify-between" data-testid="carry-over-balance">
          <span className="text-[11px] text-blue-700 font-medium">Перенесено з мін. місяця</span>
          <span className="text-xs font-bold text-blue-800">{money(carryOver)}</span>
        </div>
      )}
      <div className="p-3 space-y-1.5 max-h-[calc(100vh-380px)] overflow-y-auto flex-1">
        {openItems.length === 0 ? <EmptyState text="Немає нових оплат" /> : openItems.map(item => (
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
      {closedMonths.length > 0 && (
        <div className="p-3 pt-0 space-y-1.5 border-t border-slate-100">
          {closedMonths.map(cm => {
            const key = `${cm.year}-${String(cm.month).padStart(2,'0')}`;
            return <ClosedMonthBar key={key} month={cm} type="income" items={closedPeriods[key] || []} />;
          })}
        </div>
      )}
    </section>
  );
}

/* ========== COLUMN 2: DEPOSITS ========== */
function DepositsColumn({ items, totals, navigate, onAdd, onRefresh }) {
  const activeStatuses = ['holding', 'held', 'partially_used'];
  const activeItems = items.filter(i => activeStatuses.includes(i.status));
  const closedItems = items.filter(i => !activeStatuses.includes(i.status));
  const [refundTarget, setRefundTarget] = useState(null);
  const [refundForm, setRefundForm] = useState({ amount: '', method: 'cash', note: '' });
  const [refundSaving, setRefundSaving] = useState(false);

  const handleRefund = async () => {
    if (!refundTarget || !refundForm.amount) return;
    setRefundSaving(true);
    try {
      const res = await authFetch(
        `${BACKEND_URL}/api/finance/deposits/${refundTarget.id}/refund?amount=${refundForm.amount}&method=${refundForm.method}&note=${encodeURIComponent(refundForm.note || '')}`,
        { method: 'POST' }
      );
      if (res.ok) {
        setRefundTarget(null);
        setRefundForm({ amount: '', method: 'cash', note: '' });
        if (onRefresh) onRefresh();
      }
    } catch (e) { console.error(e); }
    finally { setRefundSaving(false); }
  };

  const statusCfg = {
    holding: { label: 'Активна', cls: 'bg-amber-100 text-amber-700' },
    held: { label: 'Активна', cls: 'bg-amber-100 text-amber-700' },
    partially_used: { label: 'Частк.', cls: 'bg-orange-100 text-orange-700' },
    fully_used: { label: 'Використано', cls: 'bg-rose-100 text-rose-700' },
    refunded: { label: 'Повернуто', cls: 'bg-blue-100 text-blue-700' },
  };

  const renderItem = (item) => {
    const st = statusCfg[item.status] || { label: item.status, cls: 'bg-slate-100 text-slate-600' };
    const curr = item.currency === 'USD' ? '$' : item.currency === 'EUR' ? '€' : '₴';
    const isActive = activeStatuses.includes(item.status);
    const canRefund = isActive && item.available > 0;
    const isCash = (item.method || 'cash') === 'cash';
    return (
      <div key={item.id}
        className="px-3 py-2.5 rounded-xl border border-slate-100 hover:border-amber-200 hover:bg-amber-50/30 transition-all"
        data-testid={`deposit-item-${item.id}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 min-w-0 flex-wrap">
            <span className="text-xs font-semibold text-slate-700 cursor-pointer"
              onClick={() => item.order_id && navigate(`/order/${item.order_id}/return-settlement`)}>
              {item.order_number || (item.client_name ? `Клієнт` : '—')}
            </span>
            <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${st.cls}`}>{st.label}</span>
            <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${isCash ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-blue-50 text-blue-700 border border-blue-200'}`}
              data-testid={`deposit-method-${item.id}`}>
              {isCash ? 'Гот' : 'Безгот'}
            </span>
          </div>
          <div className="font-bold text-amber-700 text-sm flex-shrink-0 ml-2">{curr}{fmtUA(item.actual_amount)}</div>
        </div>
        <div className="flex items-center justify-between mt-1">
          <span className="text-xs text-slate-500 truncate">{item.customer_name || item.client_name || '—'}</span>
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
        {canRefund && (
          <button
            onClick={(e) => { e.stopPropagation(); setRefundTarget(item); setRefundForm({ amount: String(item.available), method: 'cash', note: '' }); }}
            className="mt-2 w-full text-[11px] font-medium py-1.5 rounded-lg border border-blue-200 text-blue-600 hover:bg-blue-50 transition-colors flex items-center justify-center gap-1"
            data-testid={`deposit-refund-btn-${item.id}`}>
            <RotateCcw className="w-3 h-3" /> Повернути заставу
          </button>
        )}
      </div>
    );
  };

  // Cash totals by currency (from active deposits)
  const cashByCurr = { UAH: 0, USD: 0, EUR: 0 };
  const bankTotal = { UAH: 0 };
  activeItems.forEach(i => {
    const c = i.currency || 'UAH';
    const amt = i.actual_amount || 0;
    if ((i.method || 'cash') === 'cash') {
      cashByCurr[c] = (cashByCurr[c] || 0) + amt;
    } else {
      bankTotal.UAH += (i.held_amount || amt);
    }
  });

  return (
    <section className="rounded-2xl border border-amber-200 ring-2 ring-amber-100 bg-white shadow-sm flex flex-col" data-testid="deposits-column">
      <ColumnHeader icon={Shield} title="Застави" count={activeItems.length} total={totals.held_total} color="amber" onAdd={onAdd}>
        <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1.5 pt-1.5 border-t border-amber-100 text-[11px]">
          <span className="text-green-600 font-medium"><Banknote className="w-3 h-3 inline mr-0.5" />Гот:</span>
          {cashByCurr.UAH > 0 && <span className="text-slate-600">₴{fmtUA(cashByCurr.UAH)}</span>}
          {cashByCurr.USD > 0 && <span className="text-slate-600">${fmtUA(cashByCurr.USD)}</span>}
          {cashByCurr.EUR > 0 && <span className="text-slate-600">€{fmtUA(cashByCurr.EUR)}</span>}
          {cashByCurr.UAH === 0 && cashByCurr.USD === 0 && cashByCurr.EUR === 0 && <span className="text-slate-400">₴0</span>}
          <span className="text-blue-600 font-medium"><CreditCard className="w-3 h-3 inline mr-0.5" />Безгот: ₴{fmtUA(bankTotal.UAH)}</span>
          <span className="text-rose-500 ml-auto">Утрим: {money(totals.used_total)}</span>
          <span className="text-blue-500">Поверн: {money(totals.refunded_total)}</span>
        </div>
      </ColumnHeader>
      <div className="p-3 space-y-1.5 max-h-[calc(100vh-380px)] overflow-y-auto flex-1">
        {activeItems.length === 0 && closedItems.length === 0 && <EmptyState text="Немає застав" />}
        {activeItems.map(renderItem)}
        {closedItems.length > 0 && activeItems.length > 0 && (
          <div className="flex items-center gap-2 pt-2 pb-1">
            <div className="flex-1 h-px bg-slate-200" />
            <span className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">Закриті</span>
            <div className="flex-1 h-px bg-slate-200" />
          </div>
        )}
        {closedItems.map(renderItem)}
      </div>

      {/* Refund Modal */}
      {refundTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setRefundTarget(null)}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-5" onClick={e => e.stopPropagation()} data-testid="deposit-refund-modal">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-slate-800">Повернення застави</h3>
              <button onClick={() => setRefundTarget(null)} className="p-1 rounded-lg hover:bg-slate-100"><X className="w-4 h-4" /></button>
            </div>
            <div className="text-sm text-slate-600 mb-3">
              <span className="font-semibold">{refundTarget.order_number || refundTarget.customer_name || refundTarget.client_name || '—'}</span>
              <span className="ml-2 text-slate-400">Доступно: <span className="text-emerald-600 font-bold">{money(refundTarget.available)}</span></span>
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-slate-500 block mb-1">Сума повернення</label>
                <input type="number" value={refundForm.amount} onChange={e => setRefundForm(f => ({ ...f, amount: e.target.value }))}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="0" data-testid="refund-amount-input" />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-500 block mb-1">Метод</label>
                <div className="flex gap-2">
                  {[{ v: 'cash', l: 'Готівка' }, { v: 'bank', l: 'Безготівка' }].map(m => (
                    <button key={m.v} onClick={() => setRefundForm(f => ({ ...f, method: m.v }))}
                      className={`flex-1 py-2 rounded-lg text-xs font-medium border transition-colors ${refundForm.method === m.v ? 'border-blue-400 bg-blue-50 text-blue-700' : 'border-slate-200 text-slate-500 hover:bg-slate-50'}`}
                      data-testid={`refund-method-${m.v}`}>{m.l}</button>
                  ))}
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-slate-500 block mb-1">Коментар</label>
                <input type="text" value={refundForm.note} onChange={e => setRefundForm(f => ({ ...f, note: e.target.value }))}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="Примітка..." data-testid="refund-note-input" />
              </div>
              <button onClick={handleRefund} disabled={refundSaving || !refundForm.amount || Number(refundForm.amount) <= 0}
                className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-xl text-sm font-bold transition-colors"
                data-testid="refund-confirm-btn">
                {refundSaving ? 'Обробка...' : `Повернути ${refundForm.amount ? money(Number(refundForm.amount)) : ''}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

/* ========== COLUMN 3: EXPENSES ========== */
function ExpensesColumn({ items, totals, onAdd, closedMonths = [] }) {
  const openItems = items.filter(i => !i._closed);
  const closedPeriods = {};
  items.filter(i => i._closed).forEach(i => {
    const p = i._period || 'unknown';
    if (!closedPeriods[p]) closedPeriods[p] = [];
    closedPeriods[p].push(i);
  });
  
  const openCash = openItems.filter(i => i.method === 'cash').reduce((s, i) => s + (i.amount || 0), 0);
  const openBank = openItems.filter(i => i.method !== 'cash').reduce((s, i) => s + (i.amount || 0), 0);
  const openTotal = openCash + openBank;

  return (
    <section className="rounded-2xl border border-rose-200 ring-2 ring-rose-100 bg-white shadow-sm flex flex-col" data-testid="expenses-column">
      <ColumnHeader icon={TrendingDown} title="Витрати" count={openItems.length} total={openTotal} color="rose" onAdd={onAdd}>
        <div className="flex gap-3 text-[11px] text-slate-500 mt-1">
          <span><Banknote className="w-3 h-3 inline mr-0.5" />{money(openCash)}</span>
          <span><CreditCard className="w-3 h-3 inline mr-0.5" />{money(openBank)}</span>
        </div>
      </ColumnHeader>
      <div className="p-3 space-y-1.5 max-h-[calc(100vh-380px)] overflow-y-auto flex-1">
        {openItems.length === 0 ? <EmptyState text="Немає нових витрат" /> : openItems.map((item, idx) => {
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
                    {isCollection ? (item.method === 'cash' ? 'Готівка' : 'Безготівка') : isRefund ? `${item.order_number} · ${item.customer_name}` : (item.parent_category || '')}
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
      {closedMonths.length > 0 && (
        <div className="p-3 pt-0 space-y-1.5 border-t border-slate-100">
          {closedMonths.map(cm => {
            const key = `${cm.year}-${String(cm.month).padStart(2,'0')}`;
            return <ClosedMonthBar key={key} month={cm} type="expenses" items={closedPeriods[key] || []} />;
          })}
        </div>
      )}
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
  const [form, setForm] = useState({ order_id: '', client_user_id: '', amount: '', currency: 'UAH', exchange_rate: '', method: 'cash', note: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [bindType, setBindType] = useState('order'); // 'order' | 'client'
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [selectedEntity, setSelectedEntity] = useState(null);
  const userEmail = localStorage.getItem('user_email') || '';

  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const doSearch = async (q) => {
    setSearchQuery(q);
    if (q.length < 2) { setSearchResults([]); return }
    setSearching(true);
    try {
      const endpoint = bindType === 'order' ? 'search/orders' : 'search/clients';
      const res = await authFetch(`${BACKEND_URL}/api/finance/${endpoint}?q=${encodeURIComponent(q)}`);
      setSearchResults(await res.json());
    } catch { setSearchResults([]) }
    setSearching(false);
  };

  const selectEntity = (item) => {
    setSelectedEntity(item);
    setSearchResults([]);
    setSearchQuery('');
    if (bindType === 'order') {
      set('order_id', item.order_id);
      set('client_user_id', '');
      if (item.deposit_amount > 0 && !form.amount) set('amount', String(item.deposit_amount));
    } else {
      set('client_user_id', item.id);
      set('order_id', '');
    }
  };

  const submit = async () => {
    if (!form.order_id && !form.client_user_id) return setError('Оберіть ордер або клієнта');
    if (!form.amount || Number(form.amount) <= 0) return setError('Вкажіть суму');
    setSaving(true); setError('');
    try {
      const body = {
        order_id: form.order_id ? Number(form.order_id) : null,
        client_user_id: form.client_user_id ? Number(form.client_user_id) : null,
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
        {/* Bind type toggle */}
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1.5">Прив'язка</label>
          <div className="flex gap-2">
            <button onClick={() => { setBindType('order'); setSelectedEntity(null); set('order_id',''); set('client_user_id','') }}
              className={`flex-1 py-2 rounded-lg text-xs font-medium border transition-all ${bindType === 'order' ? 'bg-blue-50 border-blue-300 text-blue-700' : 'bg-white border-slate-200 text-slate-500 hover:bg-slate-50'}`}
              data-testid="deposit-bind-order">Ордер</button>
            <button onClick={() => { setBindType('client'); setSelectedEntity(null); set('order_id',''); set('client_user_id','') }}
              className={`flex-1 py-2 rounded-lg text-xs font-medium border transition-all ${bindType === 'client' ? 'bg-violet-50 border-violet-300 text-violet-700' : 'bg-white border-slate-200 text-slate-500 hover:bg-slate-50'}`}
              data-testid="deposit-bind-client">Клієнт</button>
          </div>
        </div>

        {/* Search */}
        <div className="relative">
          <label className="block text-xs font-medium text-slate-600 mb-1.5">
            {bindType === 'order' ? 'Пошук ордеру' : 'Пошук клієнта'}
          </label>
          {selectedEntity ? (
            <div className="flex items-center justify-between px-3 py-2 rounded-lg border border-emerald-300 bg-emerald-50">
              <span className="text-sm font-medium text-emerald-800">
                {bindType === 'order'
                  ? `${selectedEntity.order_number} — ${selectedEntity.customer_name}`
                  : `${selectedEntity.full_name}${selectedEntity.company ? ` (${selectedEntity.company})` : ''}`}
              </span>
              <button onClick={() => { setSelectedEntity(null); set('order_id',''); set('client_user_id','') }}
                className="text-emerald-600 hover:text-emerald-800"><X className="w-4 h-4" /></button>
            </div>
          ) : (
            <>
              <input value={searchQuery} onChange={e => doSearch(e.target.value)}
                placeholder={bindType === 'order' ? 'Номер, клієнт, телефон...' : "Ім'я, телефон, компанія..."}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:ring-2 focus:ring-amber-400"
                data-testid="deposit-search" />
              {searchResults.length > 0 && (
                <div className="absolute z-50 w-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                  {searchResults.map(item => (
                    <button key={bindType === 'order' ? item.order_id : item.id}
                      onClick={() => selectEntity(item)}
                      className="w-full text-left px-3 py-2 text-xs hover:bg-amber-50 border-b border-slate-100 last:border-0">
                      {bindType === 'order' ? (
                        <div>
                          <span className="font-semibold text-blue-700">{item.order_number}</span>
                          <span className="text-slate-600"> — {item.customer_name}</span>
                          <span className="text-slate-400 ml-2">Застава: ₴{(item.deposit_amount||0).toLocaleString('uk-UA')}</span>
                        </div>
                      ) : (
                        <div>
                          <span className="font-semibold text-violet-700">{item.full_name}</span>
                          {item.company && <span className="text-slate-500"> ({item.company})</span>}
                          {item.phone && <span className="text-slate-400 ml-2">{item.phone}</span>}
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              )}
              {searching && <div className="absolute z-50 w-full mt-1 bg-white border rounded-lg p-3 text-xs text-slate-400">Пошук...</div>}
            </>
          )}
        </div>

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
  const [form, setForm] = useState({ category_code: '', method: 'cash', amount: '', note: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [categoryTree, setCategoryTree] = useState([]);
  const [selectedParent, setSelectedParent] = useState(null);

  useEffect(() => {
    authFetch(`${BACKEND_URL}/api/finance/categories?type=expense`)
      .then(r => r.json())
      .then(d => {
        const tree = (d.tree || []).filter(p => p.code !== 'COLLECTION');
        setCategoryTree(tree);
      })
      .catch(() => {});
  }, []);

  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const parentCat = categoryTree.find(c => c.id === selectedParent);
  const subcats = parentCat?.children || [];

  const submit = async () => {
    if (!form.category_code) return setError('Оберіть підкатегорію');
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
        {/* Step 1: Parent category */}
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1.5">Категорія</label>
          <div className="grid grid-cols-2 gap-1.5">
            {categoryTree.map(cat => (
              <button key={cat.id}
                onClick={() => { setSelectedParent(cat.id); set('category_code', ''); }}
                className={`px-3 py-2 rounded-lg text-xs font-medium text-left transition-all border ${
                  selectedParent === cat.id
                    ? 'bg-rose-50 border-rose-300 text-rose-700 ring-1 ring-rose-200'
                    : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
                }`}
                data-testid={`expense-parent-${cat.code}`}>
                {cat.name}
              </button>
            ))}
          </div>
        </div>

        {/* Step 2: Subcategory */}
        {selectedParent && subcats.length > 0 && (
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1.5">Підкатегорія</label>
            <div className="max-h-40 overflow-y-auto border border-slate-200 rounded-lg divide-y divide-slate-100">
              {subcats.map(sub => (
                <button key={sub.id}
                  onClick={() => set('category_code', sub.code)}
                  className={`w-full px-3 py-2 text-xs text-left transition-colors ${
                    form.category_code === sub.code
                      ? 'bg-rose-50 text-rose-700 font-semibold'
                      : 'text-slate-600 hover:bg-slate-50'
                  }`}
                  data-testid={`expense-sub-${sub.code}`}>
                  {sub.name}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* No children — use parent directly */}
        {selectedParent && subcats.length === 0 && (
          <div className="text-xs text-slate-500 bg-slate-50 rounded-lg p-2">
            Підкатегорій немає — буде записано як "{parentCat?.name}"
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <FieldInput label="Сума (грн)" type="number" value={form.amount} onChange={v => set('amount', v)} testId="expense-amount" placeholder="0" />
          <FieldSelect label="Метод" value={form.method} onChange={v => set('method', v)}
            options={[{ value: 'cash', label: 'Готівка' }, { value: 'bank', label: 'Безготівка' }]} testId="expense-method" />
        </div>
        <FieldTextarea label="Коментар" value={form.note} onChange={v => set('note', v)} testId="expense-note" placeholder="Опис витрати..." />
        {error && <div className="text-red-600 text-sm bg-red-50 rounded-lg p-2">{error}</div>}
        <button onClick={submit} disabled={saving || !form.category_code}
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
  const [closingCash, setClosingCash] = useState('');
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  const monthNames = ['Січень','Лютий','Березень','Квітень','Травень','Червень','Липень','Серпень','Вересень','Жовтень','Листопад','Грудень'];

  const submit = async () => {
    if (!closingCash || isNaN(Number(closingCash))) {
      setError('Вкажіть залишок каси');
      return;
    }
    setSaving(true); setError('');
    try {
      const user = JSON.parse(localStorage.getItem('user') || '{}');
      const body = {
        year, month, note,
        closing_cash_balance: Number(closingCash),
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
    const cr = r.cash_register || {};
    return (
      <ModalWrapper onClose={() => { onCreated(); }} title={`${monthNames[month-1]} ${year} — закрито`} color="emerald">
        <div className="space-y-3 max-h-[70vh] overflow-y-auto" data-testid="close-month-result">
          <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-center">
            <Check className="w-8 h-8 text-emerald-600 mx-auto mb-1" />
            <p className="text-sm font-semibold text-emerald-700">Звіт збережено</p>
          </div>

          {/* CASH REGISTER */}
          <div className="p-3 rounded-xl bg-blue-50 border border-blue-200">
            <div className="text-xs font-semibold text-blue-800 mb-2">Каса</div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div><span className="text-slate-500">Початок:</span> <span className="font-bold">{money(cr.opening_balance || 0)}</span></div>
              <div><span className="text-slate-500">Кінець:</span> <span className="font-bold text-blue-700">{money(cr.closing_balance || 0)}</span></div>
            </div>
          </div>

          {/* INCOME */}
          <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-100">
            <div className="text-xs font-semibold text-emerald-800 mb-2">Доходи: {money(r.income?.total || 0)}</div>
            <div className="grid grid-cols-2 gap-1 text-xs text-slate-600">
              <div>Готівка: {money(r.income?.cash || 0)}</div>
              <div>Безготівка: {money(r.income?.bank || 0)}</div>
              {r.income?.by_type?.rent?.total > 0 && <div>Оренда: {money(r.income.by_type.rent.total)} ({r.income.by_type.rent.count})</div>}
              {r.income?.by_type?.damage?.total > 0 && <div>Збитки: {money(r.income.by_type.damage.total)} ({r.income.by_type.damage.count})</div>}
              {r.income?.by_type?.additional?.total > 0 && <div>Інше: {money(r.income.by_type.additional.total)} ({r.income.by_type.additional.count})</div>}
              {r.income?.by_type?.late?.total > 0 && <div>Прострочення: {money(r.income.by_type.late.total)} ({r.income.by_type.late.count})</div>}
            </div>
          </div>

          {/* EXPENSES */}
          <div className="p-3 rounded-xl bg-rose-50 border border-rose-100">
            <div className="text-xs font-semibold text-rose-800 mb-2">Витрати: {money(r.expenses?.total || 0)}</div>
            <div className="grid grid-cols-2 gap-1 text-xs text-slate-600">
              <div>Готівка: {money(r.expenses?.cash || 0)}</div>
              <div>Безготівка: {money(r.expenses?.bank || 0)}</div>
            </div>
            {r.expenses?.by_category && Object.keys(r.expenses.by_category).length > 0 && (
              <div className="mt-2 space-y-0.5">
                {Object.entries(r.expenses.by_category).sort((a,b) => b[1].total - a[1].total).map(([cat, d]) => (
                  <div key={cat} className="flex justify-between text-[11px] text-slate-500">
                    <span>{cat}</span>
                    <span className="font-medium">{money(d.total)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* DEPOSITS */}
          <div className="p-3 rounded-xl bg-amber-50 border border-amber-100">
            <div className="text-xs font-semibold text-amber-800 mb-1">Застави</div>
            <div className="grid grid-cols-2 gap-1 text-xs text-slate-600">
              <div>Прийнято: {money(r.deposits?.total_held || 0)} ({r.deposits?.opened_count || 0})</div>
              <div>Повернено: {money(r.deposits?.total_refunded || 0)} ({r.deposits?.closed_count || 0})</div>
            </div>
          </div>

          {/* REFUNDS */}
          {(r.refunds?.total || 0) > 0 && (
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
              <div className="text-xs font-semibold text-slate-700">Повернення клієнтам: {money(r.refunds?.total || 0)}</div>
            </div>
          )}

          {/* ENCASHMENTS */}
          {(r.encashments?.count || 0) > 0 && (
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
              <div className="text-xs font-semibold text-slate-700">Переміщення: {r.encashments.count} операцій</div>
              <div className="text-xs text-slate-500">В касу: {money(r.encashments?.in || 0)} · З каси: {money(r.encashments?.out || 0)}</div>
            </div>
          )}

          {/* SUMMARY */}
          <div className="bg-slate-800 rounded-xl p-3 text-center">
            <div className="text-xs text-slate-300 mb-1">Чистий дохід за місяць</div>
            <div className="text-lg font-extrabold text-white">{money(r.summary?.net_total || 0)}</div>
            <div className="text-[10px] text-slate-400 mt-1">
              готівка {money(r.summary?.net_cash || 0)} · безготівка {money(r.summary?.net_bank || 0)}
            </div>
          </div>

          <p className="text-xs text-slate-500 text-center">Замовлень за місяць: {r.orders_count || 0}</p>
        </div>
      </ModalWrapper>
    );
  }

  return (
    <ModalWrapper onClose={onClose} title="Закриття місяця" color="indigo">
      <div className="space-y-4" data-testid="close-month-form">
        <div className="p-3 rounded-xl bg-amber-50 border border-amber-200">
          <p className="text-xs text-amber-800">
            Система зафіксує всі фінансові операції за обраний місяць і створить підсумковий звіт. Залишок каси перенесеться на наступний місяць.
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
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">Залишок каси (готівка в касі)</label>
          <input type="number" value={closingCash} onChange={e => setClosingCash(e.target.value)}
            className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm"
            placeholder="Наприклад: 27965"
            data-testid="close-month-cash" />
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
