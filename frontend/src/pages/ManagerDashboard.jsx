/* eslint-disable */
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import CorporateHeader from '../components/CorporateHeader';
import { limitedAuthFetch } from '../utils/requestLimiter';  // ✅ Request limiter

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

// Utility function for authenticated fetch - тепер з лімітером
const authFetch = (url, options = {}) => {
  return limitedAuthFetch(url, options);
};

export default function ManagerDashboard() {
  const [orders, setOrders] = useState([]);
  const [decorOrders, setDecorOrders] = useState([]);  // Наші замовлення
  const [issueCards, setIssueCards] = useState([]);  // Картки видачі
  const [partialReturnVersions, setPartialReturnVersions] = useState([]);  // ✅ Версії часткових повернень
  const [loading, setLoading] = useState(true);
  const [financeData, setFinanceData] = useState({ revenue: 0, deposits: 0 });
  const [cleaningStats, setCleaningStats] = useState({ repair: 0 });
  const navigate = useNavigate();
  
  // Стани для розгортання карток
  const [showAllAwaiting, setShowAllAwaiting] = useState(false);
  const [showAllReturns, setShowAllReturns] = useState(true);  // За замовчуванням показуємо всі
  const [showAllPreparation, setShowAllPreparation] = useState(false);  // Комплектація
  const [showAllReady, setShowAllReady] = useState(false);  // Готові до видачі
  const [showAllPartial, setShowAllPartial] = useState(false);  // Часткове повернення
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('Всі');
  const [user, setUser] = useState(null);
  
  // ✅ Режим об'єднання замовлень
  const [mergeMode, setMergeMode] = useState(false);
  const [selectedForMerge, setSelectedForMerge] = useState([]);

  // ✅ Перемикач "Всі / День": null = всі, інакше зсув в днях від сьогодні (0=сьогодні, 1=завтра, ...)
  const [dayOffset, setDayOffset] = useState(null);

  // Завантажити дані користувача
  useEffect(() => {
    const userData = localStorage.getItem('user');
    if (userData) {
      setUser(JSON.parse(userData));
    }
  }, []);

  // Функція для скасування замовлення клієнтом
  const handleCancelByClient = async (orderId, orderNumber) => {
    const reason = prompt(`Скасувати замовлення ${orderNumber}?\n\nПричина відмови клієнта (опціонально):`);
    if (reason === null) return; // User clicked Cancel
    
    if (!confirm(`⚠️ Клієнт відмовився від замовлення ${orderNumber}?\n\nЗамовлення буде скасовано і товари розморожено.`)) {
      return;
    }
    
    try {
      const response = await authFetch(`${BACKEND_URL}/api/decor-orders/${orderId}/cancel-by-client`, {
        method: 'POST',
        body: JSON.stringify({
          reason: reason || 'Клієнт відмовився без пояснень'
        })
      });
      
      if (response.ok) {
        alert('✅ Замовлення скасовано. Товари розморожено.');
        fetchAllData(); // Перезавантажити дані
      } else {
        const error = await response.json();
        alert(`❌ Помилка: ${error.detail || 'Не вдалося скасувати замовлення'}`);
      }
    } catch (error) {
      console.error('Error cancelling order:', error);
      alert(`❌ Помилка: ${error.message}`);
    }
  };
  
  // Функція для архівування замовлення
  const handleArchiveOrder = async (orderId, orderNumber) => {
    if (!confirm(`Архівувати замовлення ${orderNumber}?\n\nВоно буде приховано з основного дашборду.`)) {
      return;
    }
    
    try {
      const response = await authFetch(`${BACKEND_URL}/api/decor-orders/${orderId}/archive`, {
        method: 'POST'
      });
      
      if (response.ok) {
        alert('✅ Замовлення архівовано');
        fetchAllData(); // Перезавантажити дані
      } else {
        const error = await response.json();
        alert(`❌ Помилка: ${error.detail || 'Не вдалося архівувати'}`);
      }
    } catch (error) {
      console.error('Error archiving order:', error);
      alert(`❌ Помилка: ${error.message}`);
    }
  };

  // ✅ Функція для об'єднання замовлень
  const handleMergeOrders = async () => {
    if (selectedForMerge.length < 2) {
      alert('Виберіть мінімум 2 замовлення для об\'єднання');
      return;
    }
    
    // Останнє вибране буде цільовим (його номер залишиться)
    const targetOrderId = selectedForMerge[selectedForMerge.length - 1];
    const sourceOrderIds = selectedForMerge.slice(0, -1);
    
    const targetOrder = awaitingOrders.find(o => (o.order_id || o.id) === targetOrderId);
    const sourceOrders = sourceOrderIds.map(id => awaitingOrders.find(o => (o.order_id || o.id) === id)).filter(Boolean);
    
    const confirmMsg = `Об'єднати ${selectedForMerge.length} замовлень?\n\n` +
      `Товари з:\n${sourceOrders.map(o => `  • ${o.order_number} (${o.customer_name || o.client_name})`).join('\n')}\n\n` +
      `Будуть перенесені в:\n  → ${targetOrder?.order_number} (${targetOrder?.customer_name || targetOrder?.client_name})\n\n` +
      `⚠️ Старі замовлення будуть видалені!`;
    
    if (!confirm(confirmMsg)) {
      return;
    }
    
    try {
      const response = await authFetch(`${BACKEND_URL}/api/orders/merge`, {
        method: 'POST',
        body: JSON.stringify({
          target_order_id: targetOrderId,
          source_order_ids: sourceOrderIds
        })
      });
      
      if (response.ok) {
        const result = await response.json();
        alert(`✅ Замовлення об'єднано!\n\nНовий номер: ${result.order_number}\nТоварів: ${result.items_count}\nСума: ₴${result.total_price}`);
        setMergeMode(false);
        setSelectedForMerge([]);
        fetchAllData(); // Перезавантажити дані
      } else {
        const error = await response.json();
        alert(`❌ Помилка: ${error.detail || 'Не вдалося об\'єднати замовлення'}`);
      }
    } catch (error) {
      console.error('Error merging orders:', error);
      alert(`❌ Помилка: ${error.message}`);
    }
  };

  // Функція для оновлення дат замовлення
  const handleDateUpdate = async (orderId, issueDate, returnDate) => {
    try {
      const response = await authFetch(`${BACKEND_URL}/api/orders/${orderId}`, {
        method: 'PUT',
        body: JSON.stringify({
          issue_date: issueDate,
          return_date: returnDate
        })
      });

      if (response.ok) {
        const updatedOrder = await response.json();
        console.log('[Dashboard] ✅ Order dates updated:', orderId);
        
        // Оновити локальний стан
        setOrders(prevOrders => 
          prevOrders.map(o => o.id === orderId ? updatedOrder : o)
        );
        
        return updatedOrder;
      } else {
        throw new Error('Failed to update dates');
      }
    } catch (error) {
      console.error('[Dashboard] Error updating dates:', error);
      throw error;
    }
  };

  // ============================================================
  // ОПТИМІЗОВАНИЙ ЗАВАНТАЖУВАЧ ДАНИХ - ОДИН ЗАПИТ ЗАМІСТЬ 6-8
  // ============================================================
  
  // AbortController для скасування запитів при unmount
  const abortControllerRef = React.useRef(null);
  
  // Retry fetch з exponential backoff та більшими затримками
  const fetchWithRetry = async (url, options = {}, retries = 3) => {
    const delays = [1000, 3000, 6000]; // Більші затримки для production
    
    for (let i = 0; i <= retries; i++) {
      try {
        // Додаємо випадкову затримку 0-500ms для уникнення "thundering herd"
        if (i > 0) {
          await new Promise(resolve => setTimeout(resolve, Math.random() * 500));
        }
        
        const response = await authFetch(url, options);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
      } catch (error) {
        if (error.name === 'AbortError') throw error; // Не retry при abort
        if (i === retries) throw error;
        console.log(`[Dashboard] Retry ${i + 1}/${retries} after ${delays[i]}ms...`);
        await new Promise(resolve => setTimeout(resolve, delays[i]));
      }
    }
  };

  // Функція для завантаження всіх даних ОДНИМ ЗАПИТОМ
  const fetchAllData = async () => {
    console.log('[Dashboard] 📊 Loading dashboard overview (single request)...');
    
    // Скасовуємо попередній запит якщо є
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();
    
    try {
      const data = await fetchWithRetry(
        `${BACKEND_URL}/api/manager/dashboard/overview`,
        { signal: abortControllerRef.current.signal }
      );
      
      console.log('[Dashboard] ✅ Overview loaded:', {
        awaiting: data.orders_awaiting?.length || 0,
        decor: data.decor_orders?.length || 0,
        cards: data.issue_cards?.length || 0
      });
      
      // Оновлюємо всі стани одночасно
      setOrders(data.orders_awaiting || []);
      setDecorOrders(data.decor_orders || []);
      setIssueCards(data.issue_cards || []);
      setFinanceData({
        revenue: data.finance_summary?.total_revenue || data.finance_summary?.rent_paid || 0,
        deposits: data.finance_summary?.deposits_count || 0
      });
      setCleaningStats({
        repair: data.cleaning_stats?.repair || 0
      });
      
      // ✅ Завантажуємо версії часткових повернень окремо
      try {
        const versionsRes = await authFetch(`${BACKEND_URL}/api/return-versions/active`);
        if (versionsRes.ok) {
          const versionsData = await versionsRes.json();
          setPartialReturnVersions(versionsData.versions || []);
          console.log('[Dashboard] ✅ Partial return versions loaded:', versionsData.count);
        }
      } catch (e) {
        console.log('[Dashboard] Partial return versions not available');
      }
      
      setLoading(false);
      
    } catch (error) {
      if (error.name === 'AbortError') {
        console.log('[Dashboard] Request aborted');
        return;
      }
      console.error('[Dashboard] ❌ Error loading overview:', error);
      setLoading(false);
      
      // Fallback до старих endpoints якщо overview не працює
      console.log('[Dashboard] Falling back to individual requests...');
      fetchAllDataLegacy();
    }
  };
  
  // Legacy fallback (старі окремі запити) - ПОСЛІДОВНО з затримками
  const fetchAllDataLegacy = async () => {
    console.log('[Dashboard] 🔄 Legacy fallback: sequential requests with delays...');
    
    const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));
    
    try {
      // 1. Критичні дані - orders
      const ordersRes = await authFetch(`${BACKEND_URL}/api/orders?status=awaiting_customer`);
      const ordersData = await ordersRes.json();
      setOrders(ordersData.orders || []);
      await delay(300); // Пауза між запитами
      
      // 2. Decor orders
      const decorRes = await authFetch(`${BACKEND_URL}/api/decor-orders?status=processing,ready_for_issue,issued,on_rent,shipped,delivered,returning`);
      const decorData = await decorRes.json();
      setDecorOrders(decorData.orders || []);
      await delay(300);
      
      // 3. Issue cards
      const cardsRes = await authFetch(`${BACKEND_URL}/api/issue-cards`);
      const cardsData = await cardsRes.json();
      setIssueCards(cardsData || []);
      await delay(300);
      
      // 4. Finance (не критичне)
      try {
        const finRes = await authFetch(`${BACKEND_URL}/api/manager/finance/summary`);
        const finData = await finRes.json();
        setFinanceData({
          revenue: finData.total_revenue || finData.rent_paid || 0,
          deposits: finData.deposits_count || 0
        });
      } catch (e) {
        console.log('[Dashboard] Finance fallback skipped');
      }
      
      setLoading(false);
      console.log('[Dashboard] ✅ Legacy fallback completed');
    } catch (err) {
      console.error('[Dashboard] Legacy fallback error:', err);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllData();
    
    // Cleanup - скасовуємо запит при unmount
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);
  
  // Manual reload function - оновити ВСІ дані
  const handleReload = () => {
    setLoading(true);
    console.log('[Dashboard] 🔄 Manual reload triggered');
    fetchAllData();
  };

  // Логіка розподілу замовлень БЕЗ ФІЛЬТРАЦІЇ ПО ДАТІ:
  // Показуємо ВСІ замовлення в певних статусах
  
  // 1. Очікують підтвердження (awaiting_customer)
  const awaitingOrders = orders; // Вже фільтруються по status=awaiting_customer в API
  const newOrders = orders; // Для сумісності з KPI
  
  // 2. В обробці (processing) - на комплектації
  // Фільтрація карток по пошуку
  const filterBySearch = (cards) => {
    let result = cards;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      result = cards.filter(card => {
        const name = (card.customer_name || '').toLowerCase();
        const phone = (card.customer_phone || '').toLowerCase();
        const orderNum = String(card.order_id || card.id || '').toLowerCase();
        const orderNumber = (card.order_number || '').toLowerCase();
        return name.includes(q) || phone.includes(q) || orderNum.includes(q) || orderNumber.includes(q);
      });
    }
    // Сортування від нових до старих
    return [...result].sort((a, b) => {
      const dateA = new Date(a.updated_at || a.created_at || 0);
      const dateB = new Date(b.updated_at || b.created_at || 0);
      return dateB - dateA;
    });
  };

  const processingOrders = decorOrders.filter(o => o.status === 'processing');
  
  // 3. Готові до видачі - ВСІ замовлення що готові до видачі (різні варіанти статусів)
  const readyOrders = decorOrders.filter(o => 
    o.status === 'processing' || 
    o.status === 'ready' || 
    o.status === 'ready_for_issue'
  );
  
  // Issue Cards (картки видачі) по статусам - ВСІ без фільтрації по даті:
  const preparationCardsAll = issueCards.filter(c => c.status === 'preparation');
  const readyCardsAll = issueCards.filter(c => 
    c.status === 'ready' || 
    c.status === 'ready_for_issue'
  );
  const issuedCards = issueCards.filter(c => c.status === 'issued');
  
  // 4. На поверненні - ВСІ issue cards що видані (статус 'issued')
  const returnOrdersAll = issueCards.filter(c => c.status === 'issued');

  // ✅ Дата для фільтру (зсув від сьогодні)
  const filterDate = (() => {
    if (dayOffset === null) return null;
    const d = new Date();
    d.setDate(d.getDate() + dayOffset);
    return d.toISOString().slice(0, 10);  // YYYY-MM-DD
  })();
  const isMatchIssue = (c) => {
    if (!filterDate) return true;
    const d = c.rental_start_date || c.issue_date;
    return d && String(d).slice(0, 10) === filterDate;
  };
  const isMatchReturn = (c) => {
    if (!filterDate) return true;
    const d = c.rental_end_date || c.return_date;
    return d && String(d).slice(0, 10) === filterDate;
  };

  const preparationCards = preparationCardsAll.filter(isMatchIssue);
  const readyCards       = readyCardsAll.filter(isMatchIssue);
  const returnOrders     = returnOrdersAll.filter(isMatchReturn);
  
  // 5. Часткові повернення - ТЕПЕР беремо з окремої таблиці версій
  // Старі картки з partial_return статусом ігноруємо - вони тепер в архіві
  // const partialReturnCards = issueCards.filter(c => c.status === 'partial_return');

  const kpis = {
    today: newOrders.length + preparationCards.length + readyCards.length + returnOrders.length + partialReturnVersions.length,
    revenue: financeData.revenue,
    deposits: financeData.deposits,
    problems: partialReturnVersions.length
  };

  return (
    <div className="min-h-screen bg-corp-bg-page font-montserrat">
      <CorporateHeader cabinetName="Реквізиторська" />
      
      {/* Quick Actions Bar */}
      <div className="bg-white border-b border-corp-border">
        <div className="mx-auto max-w-7xl px-2 sm:px-6 py-2 sm:py-3">
          <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
            
            {/* ✅ Кнопка режиму об'єднання */}
            <button 
              className={`px-2 sm:px-3 py-1.5 sm:py-2 rounded-lg border text-xs sm:text-sm font-medium transition-colors flex items-center gap-1 sm:gap-2 ${
                mergeMode 
                  ? 'border-amber-400 bg-amber-50 text-amber-700 hover:bg-amber-100' 
                  : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
              }`}
              onClick={() => {
                setMergeMode(!mergeMode);
                setSelectedForMerge([]);
              }}
            >
              🔗 <span className="hidden xs:inline">{mergeMode ? 'Скасувати' : 'Об\'єднати'}</span>
            </button>

            {/* ✅ Перемикач "Всі / День" з гортанням по днях */}
            <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-0.5 sm:p-1" data-testid="day-filter">
              <button
                onClick={() => setDayOffset(null)}
                className={`px-2 sm:px-3 py-1 sm:py-1.5 rounded-md text-xs sm:text-sm font-medium transition-colors ${
                  dayOffset === null ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'
                }`}
                data-testid="filter-all-btn"
              >
                Всі
              </button>
              <div className={`flex items-center gap-0.5 rounded-md transition-colors ${
                dayOffset !== null ? 'bg-corp-primary text-white shadow-sm' : ''
              }`}>
                <button
                  onClick={() => setDayOffset(o => (o === null ? 0 : o - 1))}
                  title="Назад на день"
                  className={`px-1.5 sm:px-2 py-1 sm:py-1.5 rounded-l-md text-xs sm:text-sm font-bold transition-colors ${
                    dayOffset !== null ? 'hover:bg-white/15' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-200'
                  }`}
                  data-testid="filter-prev-day"
                >
                  ‹
                </button>
                <button
                  onClick={() => setDayOffset(0)}
                  className={`px-2 sm:px-3 py-1 sm:py-1.5 text-xs sm:text-sm font-medium whitespace-nowrap transition-colors ${
                    dayOffset === null ? 'text-slate-500 hover:text-slate-700 hover:bg-slate-200 rounded-md' : ''
                  }`}
                  data-testid="filter-day-label"
                >
                  {(() => {
                    if (dayOffset === null) return '📅 Сьогодні';
                    if (dayOffset === 0) return 'Сьогодні';
                    if (dayOffset === 1) return 'Завтра';
                    if (dayOffset === -1) return 'Вчора';
                    const d = new Date();
                    d.setDate(d.getDate() + dayOffset);
                    return d.toLocaleDateString('uk-UA', { day: '2-digit', month: 'short', weekday: 'short' });
                  })()}
                </button>
                <button
                  onClick={() => setDayOffset(o => (o === null ? 0 : o + 1))}
                  title="Вперед на день"
                  className={`px-1.5 sm:px-2 py-1 sm:py-1.5 rounded-r-md text-xs sm:text-sm font-bold transition-colors ${
                    dayOffset !== null ? 'hover:bg-white/15' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-200'
                  }`}
                  data-testid="filter-next-day"
                >
                  ›
                </button>
              </div>
            </div>
            
            {/* Панель об'єднання */}
            {mergeMode && selectedForMerge.length > 0 && (
              <div className="flex items-center gap-2 px-2 sm:px-3 py-1 bg-amber-50 border border-amber-200 rounded-lg">
                <span className="text-xs sm:text-sm text-amber-700">
                  Вибрано: <b>{selectedForMerge.length}</b>
                </span>
                <button
                  onClick={handleMergeOrders}
                  disabled={selectedForMerge.length < 2}
                  className="px-2 sm:px-3 py-1 rounded bg-amber-500 text-white text-xs sm:text-sm font-medium hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Об'єднати →
                </button>
              </div>
            )}
            
            <div className="h-6 w-px bg-slate-200 mx-1 hidden md:block" />
            <button 
              className="rounded-lg border border-corp-primary bg-corp-primary/5 px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm font-medium text-corp-primary hover:bg-corp-primary hover:text-white transition-colors"
              onClick={() => navigate('/manager-cabinet')}
            >
              Менеджерська
            </button>
            <button 
              className="rounded-lg border border-corp-gold bg-corp-gold/5 px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm font-medium text-corp-gold hover:bg-corp-gold hover:text-white transition-colors flex items-center gap-1.5"
              onClick={() => navigate('/cabinet')}
              data-testid="nav-cabinet-btn"
            >
              Кабiнет
            </button>
            <button 
              className="rounded-lg border border-slate-200 bg-white px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm font-medium text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition-colors"
              onClick={() => navigate('/calendar')}
            >
              Календар
            </button>
            <button 
              className="rounded-lg border border-sky-300 bg-sky-50 px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm font-medium text-sky-700 hover:bg-sky-100 transition-colors"
              onClick={() => navigate('/manager/picking-list')}
              data-testid="picking-list-nav-btn"
            >
              📋 Збір
            </button>
            <button 
              className="rounded-lg border border-slate-200 bg-white px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm font-medium text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition-colors"
              onClick={() => navigate('/catalog')}
            >
              Каталог
            </button>
            <button 
              className="rounded-lg border border-slate-200 bg-white px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm font-medium text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition-colors"
              onClick={() => navigate('/damages')}
            >
              Шкоди
            </button>
            <button 
              className="rounded-lg border border-slate-200 bg-white px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm font-medium text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition-colors"
              onClick={() => navigate('/reaudit')}
            >
              Переоблік
            </button>
            {user?.role === 'admin' && (
              <button 
                className="rounded-lg border border-slate-200 bg-white px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm font-medium text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition-colors"
                onClick={() => navigate('/admin')}
              >
                Адмін
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Пошук + Лічильник замовлень */}
      <section className="mx-auto max-w-7xl px-2 sm:px-6 py-3 sm:py-4">
        <div className="flex flex-col sm:flex-row sm:items-stretch gap-3 sm:gap-4">
          {/* Пошук */}
          <div className="flex-1">
            <label className="block text-[10px] sm:text-xs font-medium text-slate-500 uppercase tracking-wide mb-1 sm:mb-1.5">Пошук</label>
            <input 
              placeholder="Номер ордеру / Ім'я / Телефон" 
              className="w-full h-10 sm:h-12 px-3 sm:px-4 rounded-xl border border-slate-200 bg-white text-sm focus:ring-2 focus:ring-corp-primary focus:border-transparent"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          
          {/* Лічильник замовлень */}
          <div className="flex-1">
            <label className="block text-[10px] sm:text-xs font-medium text-slate-500 uppercase tracking-wide mb-1 sm:mb-1.5">Замовлення</label>
            <div className="h-10 sm:h-12 px-3 sm:px-4 rounded-xl border border-slate-200 bg-white flex items-center justify-between gap-2">
              <span className="text-xl sm:text-2xl font-bold text-slate-800">{kpis.today}</span>
              <span className="text-[10px] sm:text-xs text-slate-500 text-right">
                {filterBySearch(newOrders).length} нові / {filterBySearch(preparationCards).length} компл. / {filterBySearch(readyCards).length} видач / {filterBySearch(returnOrders).length} поверн.
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Boards - 4 колонки */}
      <main className="mx-auto max-w-7xl px-2 sm:px-6 py-3 sm:py-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-6">
        {/* КОЛОНКА 1: На комплектації / Видача сьогодні */}
        <Column title="📦 На комплектації" subtitle="Збір товарів + видача сьогодні" tone="ok">
          {loading ? (
            <div className="rounded-2xl border border-slate-200 p-4 h-32 bg-slate-50 animate-pulse" />
          ) : filterBySearch(preparationCards).length > 0 ? (
            <>
              {(showAllPreparation ? filterBySearch(preparationCards) : filterBySearch(preparationCards).slice(0, 4)).map(card => (
                <OrderCard 
                  key={card.id}
                  id={card.order_number || card.order_id}
                  order={card}
                  onDateUpdate={null}
                  onCancelByClient={handleCancelByClient}
                  onClick={() => navigate(`/issue/${card.id}`)}
                />
              ))}
              {filterBySearch(preparationCards).length > 4 && !showAllPreparation && (
                <button 
                  onClick={() => setShowAllPreparation(true)}
                  className="text-center py-3 text-sm text-blue-600 hover:text-blue-800 font-medium hover:bg-blue-50 rounded-lg transition-colors cursor-pointer w-full"
                >
                  +{filterBySearch(preparationCards).length - 4} більше карток - Показати всі
                </button>
              )}
              {filterBySearch(preparationCards).length > 4 && showAllPreparation && (
                <button 
                  onClick={() => setShowAllPreparation(false)}
                  className="text-center py-3 text-sm text-corp-text-main hover:text-corp-text-dark font-medium hover:bg-slate-50 rounded-lg transition-colors cursor-pointer w-full"
                >
                  Згорнути ↑
                </button>
              )}
            </>
          ) : (
            <div className="rounded-2xl border border-slate-200 p-8 text-center text-slate-400">
              {searchQuery ? 'Нічого не знайдено' : 'Немає карток на комплектації'}
            </div>
          )}
        </Column>

        {/* КОЛОНКА 2: Готові до видачі */}
        <Column title="✅ Готові до видачі" subtitle="Скомплектовано → готово до передачі клієнту" tone="ok">
          {loading ? (
            <div className="rounded-2xl border border-slate-200 p-4 h-32 bg-slate-50 animate-pulse" />
          ) : filterBySearch(readyCards).length > 0 ? (
            <>
              {(showAllReady ? filterBySearch(readyCards) : filterBySearch(readyCards).slice(0, 4)).map(card => (
                <OrderCard 
                  key={card.id}
                  id={card.order_number || card.order_id}
                  name={card.customer_name || '—'}
                  phone={card.customer_phone || '—'}
                  rent={`₴ ${((card.total_after_discount || card.total_rental || 0) + (card.service_fee || 0)).toFixed(0)}`}
                  deposit={`₴ ${(card.deposit_amount || 0).toFixed(0)}`}
                  badge="ready"
                  order={card}
                  onDateUpdate={null}
                  onCancelByClient={handleCancelByClient}
                  onClick={() => navigate(`/issue/${card.id}`)}
                />
              ))}
              {filterBySearch(readyCards).length > 4 && !showAllReady && (
                <button 
                  onClick={() => setShowAllReady(true)}
                  className="text-center py-3 text-sm text-blue-600 hover:text-blue-800 font-medium hover:bg-blue-50 rounded-lg transition-colors cursor-pointer w-full"
                >
                  +{filterBySearch(readyCards).length - 4} більше карток - Показати всі
                </button>
              )}
              {filterBySearch(readyCards).length > 4 && showAllReady && (
                <button 
                  onClick={() => setShowAllReady(false)}
                  className="text-center py-3 text-sm text-corp-text-main hover:text-corp-text-dark font-medium hover:bg-slate-50 rounded-lg transition-colors cursor-pointer w-full"
                >
                  Згорнути ↑
                </button>
              )}
            </>
          ) : (
            <div className="rounded-2xl border border-slate-200 p-8 text-center text-slate-400">
              {searchQuery ? 'Нічого не знайдено' : 'Немає готових карток'}
            </div>
          )}
        </Column>

        {/* КОЛОНКА 3: Повернення */}
        <Column title="🔙 Повернення" subtitle="Видані замовлення, які очікують повернення" tone="warn">
          {loading ? (
            <div className="rounded-2xl border border-slate-200 p-4 h-32 bg-slate-50 animate-pulse" />
          ) : filterBySearch(returnOrders).length > 0 ? (
            <>
              {(showAllReturns ? filterBySearch(returnOrders) : filterBySearch(returnOrders).slice(0, 4)).map(card => {
                const endDate = card.rental_end_date || card.return_date;
                let overdueDays = 0;
                if (endDate) {
                  const end = new Date(endDate);
                  end.setHours(23, 59, 59);
                  const now = new Date();
                  if (now > end) overdueDays = Math.floor((now - end) / (1000 * 60 * 60 * 24));
                }
                return (
                  <div 
                    key={card.id}
                    className={`relative rounded-2xl border p-3 transition hover:shadow-lg cursor-pointer ${
                      overdueDays > 0 
                        ? 'border-red-300 bg-red-50/50 ring-2 ring-red-100 hover:border-red-400' 
                        : 'border-slate-200 bg-white hover:border-teal-400'
                    }`}
                    onClick={() => navigate(`/return/${card.order_id}`)}
                    data-testid={`return-card-${card.order_id}`}
                  >
                    {overdueDays > 0 && (
                      <div className="absolute -top-2 -right-2 bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full shadow-sm" data-testid={`overdue-badge-${card.order_id}`}>
                        +{overdueDays} дн
                      </div>
                    )}
                    <div className="flex justify-between items-start mb-1">
                      <div>
                        <div className="font-bold text-slate-800 text-sm">{card.order_number}</div>
                        <div className="text-xs text-slate-500">{card.customer_name}</div>
                      </div>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                        overdueDays > 0 ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                      }`}>
                        {overdueDays > 0 ? `Прострочено` : 'Вчасно'}
                      </span>
                    </div>
                    <div className={`text-xs ${overdueDays > 0 ? 'text-red-600 font-medium' : 'text-slate-500'}`}>
                      Повернення: {endDate ? new Date(endDate).toLocaleDateString('uk-UA') : '—'}
                      {overdueDays > 0 && ` (${overdueDays} дн прострочення)`}
                    </div>
                    {card.customer_phone && (
                      <div className="text-xs text-slate-400 mt-0.5">{card.customer_phone}</div>
                    )}
                    {card.has_damage_items && (
                      <div className="mt-1.5 flex items-center gap-1 text-[10px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-2 py-1" data-testid={`return-damage-badge-${card.order_id}`}>
                        <svg className="w-3 h-3 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 6a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 6zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" /></svg>
                        {card.damage_items_count} поз. з пошкодженнями
                      </div>
                    )}
                  </div>
                );
              })}
              {filterBySearch(returnOrders).length > 4 && !showAllReturns && (
                <button 
                  onClick={() => setShowAllReturns(true)}
                  className="text-center py-3 text-sm text-blue-600 hover:text-blue-800 font-medium hover:bg-blue-50 rounded-lg transition-colors cursor-pointer"
                >
                  +{filterBySearch(returnOrders).length - 4} більше замовлень - Показати всі
                </button>
              )}
              {filterBySearch(returnOrders).length > 4 && showAllReturns && (
                <button 
                  onClick={() => setShowAllReturns(false)}
                  className="text-center py-3 text-sm text-corp-text-main hover:text-corp-text-dark font-medium hover:bg-slate-50 rounded-lg transition-colors cursor-pointer"
                >
                  Згорнути ↑
                </button>
              )}
            </>
          ) : (
            <div className="rounded-2xl border border-slate-200 p-8 text-center text-slate-400">
              {searchQuery ? 'Нічого не знайдено' : 'Немає повернень сьогодні'}
            </div>
          )}
        </Column>
        
        {/* КОЛОНКА 4: Часткове повернення - ВЕРСІЇ */}
        <Column title="⚠️ Часткове повернення" subtitle="Товари що залишились у клієнтів" tone="warn">
          {loading ? (
            <div className="rounded-2xl border border-slate-200 p-4 h-32 bg-slate-50 animate-pulse" />
          ) : partialReturnVersions.length > 0 ? (
            <>
              {(showAllPartial ? partialReturnVersions : partialReturnVersions.slice(0, 4)).map(version => (
                <div 
                  key={version.version_id}
                  onClick={() => navigate(`/partial-return/${version.version_id}`)}
                  className="rounded-2xl border border-amber-200 bg-amber-50 p-4 hover:shadow-md hover:border-amber-300 transition-all cursor-pointer"
                >
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <div className="font-bold text-slate-800">{version.display_number}</div>
                      <div className="text-sm text-slate-600">{version.customer_name}</div>
                    </div>
                    <span className="bg-amber-100 text-amber-800 px-2 py-0.5 rounded-full text-xs font-medium">
                      {version.items_count} поз.
                    </span>
                  </div>
                  <div className="flex justify-between text-sm text-slate-500">
                    <span>{version.customer_phone}</span>
                    {version.days_overdue > 0 && (
                      <span className="text-red-600 font-medium">+{version.days_overdue} дн.</span>
                    )}
                  </div>
                </div>
              ))}
              {partialReturnVersions.length > 4 && !showAllPartial && (
                <button 
                  onClick={() => setShowAllPartial(true)}
                  className="text-center py-3 text-sm text-amber-600 hover:text-amber-800 font-medium hover:bg-amber-50 rounded-lg transition-colors cursor-pointer"
                >
                  +{partialReturnVersions.length - 4} більше - Показати всі
                </button>
              )}
              {partialReturnVersions.length > 4 && showAllPartial && (
                <button 
                  onClick={() => setShowAllPartial(false)}
                  className="text-center py-3 text-sm text-corp-text-main hover:text-corp-text-dark font-medium hover:bg-slate-50 rounded-lg transition-colors cursor-pointer"
                >
                  Згорнути ↑
                </button>
              )}
            </>
          ) : (
            <div className="rounded-2xl border border-slate-200 p-8 text-center text-slate-400">
              Всі товари повернено ✓
            </div>
          )}
        </Column>
      </main>
      {/* Footer moved to global LegalFooter in App.tsx */}
      
      {/* Чат замовлень перенесено в Особистий кабінет → вкладка "Замовлення" */}
    </div>
  );
}

function Filter({ label, children }) {
  return (
    <label className="flex flex-col gap-2">
      <span className="text-xs text-corp-text-muted uppercase tracking-wide font-medium">{label}</span>
      {children}
    </label>
  );
}

function Kpi({ title, value, note, tone }) {
  const toneMap = {
    ok: 'text-corp-success',
    warn: 'text-corp-warning',
    info: 'text-corp-primary'
  };
  return (
    <div className="corp-stat-card">
      <div className="corp-stat-label">{title}</div>
      <div className={`corp-stat-value ${tone?toneMap[tone]:''}`}>{value}</div>
      {note && <div className="text-xs text-corp-text-muted mt-2">{note}</div>}
    </div>
  );
}

function Column({ title, subtitle, children, tone }) {
  const ring = { ok: 'ring-emerald-100', warn: 'ring-amber-100', info: 'ring-slate-100' }
  return (
    <section className={`rounded-2xl border border-slate-200 p-4 shadow-sm ring-2 ${tone ? ring[tone] : "ring-transparent"}`}>
      <header className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold leading-none">{title}</h3>
          {subtitle && <p className="mt-1 text-sm text-corp-text-muted">{subtitle}</p>}
        </div>
      </header>
      <div className="grid gap-3">{children}</div>
    </section>
  );
}

function DamagePhotoViewer({ photos, onClose }) {
  const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
  if (!photos || photos.length === 0) return null;
  
  const getPhotoUrl = (url) => {
    if (!url) return '';
    if (url.startsWith('http')) return url;
    return `${BACKEND_URL}${url.startsWith('/') ? '' : '/'}${url}`;
  };
  
  return (
    <div 
      className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4"
      onClick={onClose}
      data-testid="damage-photo-viewer-overlay"
    >
      <div 
        className="bg-white rounded-2xl max-w-lg w-full max-h-[80vh] overflow-y-auto shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        <div className="sticky top-0 bg-white border-b border-slate-200 px-4 py-3 flex items-center justify-between rounded-t-2xl z-10">
          <h3 className="font-semibold text-slate-800 text-sm">Фото пошкоджень ({photos.length})</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-lg font-bold" data-testid="damage-photo-viewer-close">✕</button>
        </div>
        <div className="p-4 grid grid-cols-2 gap-3">
          {photos.map((photo, i) => (
            <div key={i} className="rounded-xl overflow-hidden border border-slate-200">
              <img 
                src={getPhotoUrl(photo.photo_url)} 
                alt={photo.note || 'Пошкодження'}
                className="w-full h-36 object-contain bg-slate-50 cursor-pointer"
                onClick={() => window.open(getPhotoUrl(photo.photo_url), '_blank')}
              />
              {photo.note && (
                <div className="px-2 py-1.5 text-xs text-slate-600 bg-slate-50 border-t border-slate-100 truncate">
                  <span className={`inline-block w-2 h-2 rounded-full mr-1 ${
                    photo.severity === 'critical' ? 'bg-red-500' :
                    photo.severity === 'high' ? 'bg-orange-500' :
                    photo.severity === 'medium' ? 'bg-amber-500' : 'bg-green-500'
                  }`}></span>
                  {photo.note}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function OrderCard({ id, name, phone, rent, deposit, badge, onClick, order, onDateUpdate, onCancelByClient }) {
  // Маячок - перевіряємо чи ордер змінився з останнього перегляду
  const seenKey = `order_seen_${order?.order_id}`;
  const seenAt = localStorage.getItem(seenKey);
  const updatedAt = order?.updated_at;
  const hasChanges = updatedAt && (!seenAt || new Date(updatedAt) > new Date(seenAt));
  
  const handleClick = () => {
    // Зберігаємо час перегляду
    if (order?.order_id) {
      localStorage.setItem(seenKey, new Date().toISOString());
    }
    if (onClick) onClick();
  };
  const map = {
    new: { label: 'Нове', css: 'corp-badge corp-badge-info' },
    awaiting: { label: 'Очікує', css: 'corp-badge corp-badge-warning' },
    processing: { label: 'В роботі', css: 'corp-badge corp-badge-primary' },
    preparation: { label: 'На комплектації', css: 'corp-badge corp-badge-gold' },
    issue: { label: 'Видача', css: 'corp-badge corp-badge-success' },
    return: { label: 'Повернення', css: 'corp-badge corp-badge-warning' },
    ready:{label:'Готово',css:'corp-badge corp-badge-success'},
    issued:{label:'Видано',css:'corp-badge corp-badge-success'},
    partial:{label:'⚠️ Часткове',css:'bg-red-100 text-red-800 px-2 py-0.5 rounded-full text-xs font-medium'}
  }
  
  // Fallback якщо badge невідомий
  const badgeInfo = map[badge] || {label: badge, css: 'corp-badge corp-badge-neutral'}
  
  const [isEditing, setIsEditing] = React.useState(false);
  const [issueDate, setIssueDate] = React.useState(order?.issue_date || '');
  const [returnDate, setReturnDate] = React.useState(order?.return_date || '');
  const [isSaving, setIsSaving] = React.useState(false);
  const [showDamagePhotos, setShowDamagePhotos] = React.useState(false);
  
  const hasDamage = order?.has_damage_items;
  const damagePhotos = order?.damage_photos || [];
  const damageCount = order?.damage_items_count || 0;
  
  const handleSaveDates = async (e) => {
    e.stopPropagation();
    if (!onDateUpdate) return;
    
    setIsSaving(true);
    try {
      await onDateUpdate(id, issueDate, returnDate);
      setIsEditing(false);
    } catch (error) {
      console.error('Error updating dates:', error);
      alert('Помилка оновлення дат');
    } finally {
      setIsSaving(false);
    }
  };
  
  const handleCancel = (e) => {
    e.stopPropagation();
    setIsEditing(false);
    setIssueDate(order?.issue_date || '');
    setReturnDate(order?.return_date || '');
  };

  const handlePhoneClick = (e) => {
    e.stopPropagation();
    window.location.href = `tel:${phone}`;
  };
  
  return (
    <article className="corp-card-flat cursor-pointer hover:shadow-corp transition-shadow active:bg-slate-50" onClick={isEditing ? undefined : onClick}>
      {/* Header row */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={badgeInfo.css}>{badgeInfo.label}</span>
          <span className="text-corp-text-muted text-sm font-medium">#{id}</span>
          {hasDamage && (
            <span 
              className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[10px] font-semibold cursor-pointer hover:bg-amber-200 transition-colors"
              onClick={(e) => { e.stopPropagation(); if (damagePhotos.length > 0) setShowDamagePhotos(true); }}
              title={`${damageCount} позицій з пошкодженнями`}
              data-testid={`damage-badge-${order?.order_id}`}
            >
              <svg className="w-3 h-3" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 6a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 6zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" /></svg>
              {damageCount}
            </span>
          )}
        </div>
        {badge === 'new' && onDateUpdate && !isEditing && (
          <button 
            onClick={(e) => { e.stopPropagation(); setIsEditing(true); }}
            className="text-xs text-corp-primary hover:text-corp-primary-hover font-medium px-2 py-1 rounded-lg bg-blue-50 active:bg-blue-100"
            title="Редагувати дати"
          >
            📅 Дати
          </button>
        )}
      </div>
      
      {/* Damage photo viewer modal */}
      {showDamagePhotos && (
        <DamagePhotoViewer photos={damagePhotos} onClose={() => setShowDamagePhotos(false)} />
      )}
      
      {/* Customer info - mobile optimized */}
      <div className="mb-3">
        <div className="font-semibold text-corp-text-dark text-base">{name}</div>
        <a 
          href={`tel:${phone}`}
          onClick={handlePhoneClick}
          className="text-blue-600 font-medium text-sm flex items-center gap-1 mt-1"
        >
          📞 {phone}
        </a>
      </div>
      
      {/* Dates section */}
      {badge === 'new' && isEditing ? (
        <div className="mb-3 space-y-3 bg-corp-bg-light p-3 rounded-xl" onClick={(e) => e.stopPropagation()}>
          <div>
            <label className="text-xs text-corp-text-muted uppercase tracking-wide block mb-1">Дата видачі</label>
            <input 
              type="date" 
              value={issueDate}
              onChange={(e) => setIssueDate(e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm"
              disabled={isSaving}
            />
          </div>
          <div>
            <label className="text-xs text-corp-text-muted uppercase tracking-wide block mb-1">Дата повернення</label>
            <input 
              type="date" 
              value={returnDate}
              onChange={(e) => setReturnDate(e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm"
              disabled={isSaving}
            />
          </div>
          <div className="flex gap-2">
            <button 
              onClick={handleSaveDates}
              disabled={isSaving}
              className="flex-1 py-2.5 rounded-lg bg-emerald-500 text-white font-medium text-sm disabled:opacity-50 active:bg-emerald-600"
            >
              {isSaving ? '⏳ ...' : '✓ Зберегти'}
            </button>
            <button 
              onClick={handleCancel}
              disabled={isSaving}
              className="px-4 py-2.5 rounded-lg border border-slate-200 bg-white font-medium text-sm disabled:opacity-50 active:bg-slate-50"
            >
              ✕
            </button>
          </div>
        </div>
      ) : (
        // Відображення дат оренди - перевіряємо різні поля
        (order?.rental_start_date || order?.rental_end_date || order?.issue_date || order?.return_date) ? (
          <div className="mb-3 text-sm text-corp-text-main bg-slate-50 p-2.5 rounded-lg space-y-1">
            {(order.rental_start_date || order.issue_date) && (
              <div>📅 Видача: <span className="font-medium">{order.rental_start_date || order.issue_date}</span></div>
            )}
            {(order.rental_end_date || order.return_date) && (
              <div>📆 Поверн.: <span className="font-medium">{order.rental_end_date || order.return_date}</span></div>
            )}
          </div>
        ) : null
      )}
      
      {/* Packing progress bar for preparation cards */}
      {badge === 'preparation' && (() => {
        const items = order?.items || [];
        const totalQty = items.reduce((s, it) => s + (it.qty || it.quantity || 1), 0);
        const pickedQty = items.reduce((s, it) => s + (it.picked_qty || 0), 0);
        const progress = totalQty > 0 ? Math.round((pickedQty / totalQty) * 100) : 0;
        return (
          <div className="mt-3 pt-3 border-t border-slate-100" data-testid={`packing-progress-${id}`}>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-slate-500">Прогрес комплектації</span>
              <span className={`font-medium ${progress === 100 ? 'text-emerald-600' : 'text-slate-700'}`}>{progress}%</span>
            </div>
            <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
              <div 
                className={`h-full rounded-full transition-all duration-300 ${progress === 100 ? 'bg-emerald-500' : 'bg-blue-500'}`}
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        );
      })()}

      {/* Cancel button - bigger for mobile */}
      {onCancelByClient && ['awaiting', 'processing', 'preparation', 'ready'].includes(badge) && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onCancelByClient(order?.order_id, id);
          }}
          className="mt-3 w-full text-sm text-rose-600 border-2 border-rose-200 rounded-xl px-3 py-2.5 font-medium hover:bg-rose-50 active:bg-rose-100 transition-colors"
        >
          🚫 Клієнт відмовився
        </button>
      )}
      
      {/* Damage photos quick access button */}
      {hasDamage && damagePhotos.length > 0 && (
        <button
          onClick={(e) => { e.stopPropagation(); setShowDamagePhotos(true); }}
          className="mt-2 w-full text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2 font-medium hover:bg-amber-100 active:bg-amber-200 transition-colors flex items-center justify-center gap-1.5"
          data-testid={`damage-photos-btn-${order?.order_id}`}
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M1 8a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 018.07 3h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0016.07 6H17a2 2 0 012 2v7a2 2 0 01-2 2H3a2 2 0 01-2-2V8zm13.5 3a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0zM10 14a3 3 0 100-6 3 3 0 000 6z" clipRule="evenodd" /></svg>
          Фото пошкоджень ({damagePhotos.length})
        </button>
      )}
    </article>
  );
}

function OrderCardWithArchive({ id, name, phone, rent, deposit, badge, onClick, order, onArchive }) {
  return (
    <article onClick={handleClick} className={`relative cursor-pointer rounded-xl border ${hasChanges ? 'border-blue-400 ring-2 ring-blue-100' : 'border-slate-200'} bg-white p-3 transition hover:border-teal-400 hover:shadow-lg`}>
      {/* Маячок змін */}
      {hasChanges && (
        <div className="absolute -top-1.5 -right-1.5 w-4 h-4 bg-blue-500 rounded-full border-2 border-white animate-pulse" data-testid={`change-beacon-${order?.order_id}`} title="Менеджер вніс зміни" />
      )}
      <div className="mb-2 flex items-center justify-between">
        <div className="text-sm font-semibold text-corp-text-dark">{id}</div>
      </div>
      
      <div className="mb-2 text-xs text-corp-text-muted">{name}</div>
      <div className="mb-3 text-xs text-corp-text-muted">{phone}</div>
      
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div className="rounded-xl bg-slate-50 px-3 py-2">
          <div className="text-corp-text-muted">Сума</div>
          <div className="font-semibold tabular-nums">{rent}</div>
        </div>
        <div className="rounded-xl bg-slate-50 px-3 py-2">
          <div className="text-corp-text-muted">Застава</div>
          <div className="font-semibold tabular-nums">{deposit}</div>
        </div>
      </div>
      
      {onArchive && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onArchive(order?.order_id, id);
          }}
          className="mt-2 w-full text-xs text-corp-text-main border border-slate-300 rounded-lg px-2 py-1.5 hover:bg-slate-50 transition-colors"
        >
          📂 В архів
        </button>
      )}
    </article>
  );
}

function NavCard({ title, description, onClick }) {
  return (
    <article 
      className="corp-card cursor-pointer hover:border-corp-primary group"
      onClick={onClick}
    >
      <h3 className="text-lg font-semibold text-corp-text-dark mb-2 group-hover:text-corp-primary transition-colors">{title}</h3>
      <p className="text-sm text-corp-text-muted group-hover:text-corp-text-main transition-colors">{description}</p>
    </article>
  );
}
