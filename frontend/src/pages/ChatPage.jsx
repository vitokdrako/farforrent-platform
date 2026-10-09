/* eslint-disable */
/**
 * ChatPage — окрема сторінка спілкування з клієнтами для менеджерів.
 *
 * Маршрут: /manager/chat
 *
 * Layout (desktop):
 *   ┌──────────────────────────────────────────────────────────────┐
 *   │ CorporateHeader (Назад + Чат)                                 │
 *   ├──────────────┬───────────────────────────────────────────────┤
 *   │ Список       │ Заголовок (замовлення, клієнт)                │
 *   │ активних     │                                                │
 *   │ замовлень    │ Стрічка повідомлень                            │
 *   │ + пошук      │                                                │
 *   │              │ Поле введення + кнопка "Надіслати"             │
 *   └──────────────┴───────────────────────────────────────────────┘
 *
 * Backend:
 *   GET  /api/decor-orders?status=...           — список активних замовлень
 *   GET  /api/admin/orders/{id}/chat/messages   — повідомлення обраного
 *   POST /api/admin/orders/{id}/chat/messages   — відправити (як менеджер)
 *   GET  /api/admin/orders/{id}/chat/unread_count — лічильник нерпрочитаних
 *
 * Polling: кожні 10 сек оновлюємо вибрану розмову (без WebSocket поки що).
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Send, Search, MessageSquare, ChevronLeft, User } from 'lucide-react';
import CorporateHeader from '../components/CorporateHeader';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

const authFetch = (url, options = {}) => {
  const token = localStorage.getItem('token');
  return fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
};

const statusLabels = {
  awaiting_customer: { label: 'Очікує', color: 'bg-amber-500' },
  processing:        { label: 'Комплектація', color: 'bg-blue-500' },
  ready_for_issue:   { label: 'Готово', color: 'bg-emerald-500' },
  issued:            { label: 'Видано', color: 'bg-purple-500' },
  on_rent:           { label: 'В оренді', color: 'bg-indigo-500' },
  returned:          { label: 'Повернено', color: 'bg-slate-500' },
};

function formatTime(dt) {
  if (!dt) return '';
  try {
    const d = new Date(dt);
    return d.toLocaleString('uk-UA', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  } catch { return ''; }
}

export default function ChatPage() {
  const navigate = useNavigate();
  const [orders, setOrders] = useState([]);
  const [unreadByOrder, setUnreadByOrder] = useState({});
  const [selectedId, setSelectedId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [loadingOrders, setLoadingOrders] = useState(false);
  const [loadingMsgs, setLoadingMsgs] = useState(false);
  const [sending, setSending] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [mobileView, setMobileView] = useState('list'); // 'list' | 'chat'
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const selectedOrder = orders.find((o) => String(o.order_id) === String(selectedId));

  // === Завантажити активні замовлення + лічильники нерпрочитаних
  const fetchOrders = useCallback(async () => {
    setLoadingOrders(true);
    try {
      const r = await authFetch(
        `${BACKEND_URL}/api/decor-orders?status=awaiting_customer,processing,ready_for_issue,issued,on_rent&limit=200`
      );
      if (!r.ok) throw new Error('orders ' + r.status);
      const data = await r.json();
      const list = Array.isArray(data) ? data : data.orders || [];
      setOrders(list);

      // Lazy лічильники нерпрочитаних для активних
      const counts = {};
      await Promise.all(
        list.slice(0, 60).map(async (o) => {
          try {
            const ur = await authFetch(
              `${BACKEND_URL}/api/admin/orders/${o.order_id}/chat/unread_count`
            );
            if (ur.ok) {
              const ud = await ur.json();
              counts[o.order_id] = ud?.unread || 0;
            }
          } catch { /* ignore */ }
        })
      );
      setUnreadByOrder(counts);
    } catch (e) {
      console.error('[ChatPage] orders load:', e);
    } finally {
      setLoadingOrders(false);
    }
  }, []);

  // === Завантажити повідомлення обраного замовлення
  const fetchMessages = useCallback(async (orderId, opts = {}) => {
    if (!orderId) return;
    if (!opts.silent) setLoadingMsgs(true);
    try {
      const r = await authFetch(
        `${BACKEND_URL}/api/admin/orders/${orderId}/chat/messages?limit=200`
      );
      if (!r.ok) throw new Error('messages ' + r.status);
      const data = await r.json();
      const arr = Array.isArray(data) ? data : data.messages || [];
      setMessages(arr);
      // Прочитали — обнуляємо лічильник
      setUnreadByOrder((prev) => ({ ...prev, [orderId]: 0 }));
    } catch (e) {
      console.error('[ChatPage] messages load:', e);
    } finally {
      if (!opts.silent) setLoadingMsgs(false);
    }
  }, []);

  // === Відправка повідомлення
  const sendMessage = async () => {
    const text = newMessage.trim();
    if (!text || !selectedId || sending) return;
    setSending(true);
    try {
      const r = await authFetch(
        `${BACKEND_URL}/api/admin/orders/${selectedId}/chat/messages`,
        { method: 'POST', body: JSON.stringify({ message: text }) }
      );
      if (!r.ok) {
        const errText = await r.text();
        throw new Error(`send ${r.status}: ${errText}`);
      }
      setNewMessage('');
      await fetchMessages(selectedId, { silent: true });
      inputRef.current?.focus();
    } catch (e) {
      console.error('[ChatPage] send:', e);
      alert('Не вдалось надіслати повідомлення: ' + e.message);
    } finally {
      setSending(false);
    }
  };

  // Initial load
  useEffect(() => { fetchOrders(); }, [fetchOrders]);

  // Load messages on order select
  useEffect(() => {
    if (selectedId) {
      fetchMessages(selectedId);
      setMobileView('chat');
    }
  }, [selectedId, fetchMessages]);

  // Polling кожні 10 сек для активної розмови
  useEffect(() => {
    if (!selectedId) return;
    const t = setInterval(() => fetchMessages(selectedId, { silent: true }), 10000);
    return () => clearInterval(t);
  }, [selectedId, fetchMessages]);

  // Refresh orders/unread кожні 30 сек
  useEffect(() => {
    const t = setInterval(fetchOrders, 30000);
    return () => clearInterval(t);
  }, [fetchOrders]);

  // Скрол до низу при нових повідомленнях
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length]);

  // Фільтрація списку
  const filteredOrders = orders.filter((o) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      String(o.order_number || '').toLowerCase().includes(q) ||
      String(o.customer_name || '').toLowerCase().includes(q) ||
      String(o.customer_phone || '').toLowerCase().includes(q) ||
      String(o.customer_email || '').toLowerCase().includes(q)
    );
  });

  // Sort: непрочитані спочатку, потім за оновленням
  const sortedOrders = [...filteredOrders].sort((a, b) => {
    const ua = unreadByOrder[a.order_id] || 0;
    const ub = unreadByOrder[b.order_id] || 0;
    if (ub !== ua) return ub - ua;
    return new Date(b.updated_at || b.created_at || 0) - new Date(a.updated_at || a.created_at || 0);
  });

  const totalUnread = Object.values(unreadByOrder).reduce((a, b) => a + b, 0);

  return (
    <div className="min-h-screen bg-corp-bg-light flex flex-col" data-testid="chat-page">
      <CorporateHeader cabinetName="Чат з клієнтами" showBackButton />

      <div className="flex-1 max-w-7xl mx-auto w-full p-3 sm:p-4">
        <div
          className="bg-white rounded-corp shadow-sm border border-corp-border overflow-hidden flex"
          style={{ height: 'calc(100vh - 120px)', minHeight: 500 }}
          data-testid="chat-layout"
        >
          {/* ─── LEFT: Список замовлень ─────────────────────────────────────── */}
          <aside
            className={`${mobileView === 'chat' ? 'hidden md:flex' : 'flex'} flex-col w-full md:w-[340px] lg:w-[380px] border-r border-corp-border`}
            data-testid="chat-orders-list"
          >
            <div className="px-4 py-3 border-b border-corp-border bg-corp-bg-light">
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-sm font-semibold text-corp-text-dark">
                  Активні замовлення
                </h2>
                {totalUnread > 0 && (
                  <span
                    className="text-[10px] font-bold bg-rose-500 text-white px-2 py-0.5 rounded-full"
                    data-testid="chat-total-unread"
                  >
                    {totalUnread} нових
                  </span>
                )}
              </div>
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-corp-text-muted absolute left-2.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Пошук за номером, ПІБ, тел..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  data-testid="chat-search-input"
                  className="w-full pl-8 pr-3 py-1.5 text-xs border border-corp-border rounded-corp focus:outline-none focus:border-corp-primary"
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto">
              {loadingOrders && orders.length === 0 ? (
                <div className="p-6 text-center text-xs text-corp-text-muted">Завантаження...</div>
              ) : sortedOrders.length === 0 ? (
                <div className="p-6 text-center text-xs text-corp-text-muted">
                  Немає активних замовлень
                </div>
              ) : (
                sortedOrders.map((o) => {
                  const isSel = String(o.order_id) === String(selectedId);
                  const unread = unreadByOrder[o.order_id] || 0;
                  const st = statusLabels[o.status] || { label: o.status, color: 'bg-slate-400' };
                  return (
                    <button
                      key={o.order_id}
                      onClick={() => setSelectedId(o.order_id)}
                      data-testid={`chat-order-${o.order_id}`}
                      className={`w-full text-left px-4 py-3 border-b border-corp-border/50 hover:bg-corp-bg-light transition-colors ${isSel ? 'bg-corp-primary/5 border-l-2 border-l-corp-primary' : ''}`}
                    >
                      <div className="flex items-start justify-between gap-2 mb-1">
                        <span className="text-xs font-semibold text-corp-text-dark truncate">
                          {o.order_number}
                        </span>
                        <span className={`text-[9px] uppercase tracking-wide px-1.5 py-0.5 rounded text-white ${st.color}`}>
                          {st.label}
                        </span>
                      </div>
                      <div className="text-xs text-corp-text-dark truncate">
                        {o.customer_name || '—'}
                      </div>
                      {o.event_date && (
                        <div className="text-[10px] text-corp-text-muted mt-0.5">
                          Подія: {new Date(o.event_date).toLocaleDateString('uk-UA')}
                        </div>
                      )}
                      {unread > 0 && (
                        <div className="mt-1.5 inline-flex items-center gap-1">
                          <span
                            data-testid={`chat-order-unread-${o.order_id}`}
                            className="text-[10px] font-bold bg-rose-500 text-white px-1.5 py-0.5 rounded-full"
                          >
                            {unread} нових
                          </span>
                        </div>
                      )}
                    </button>
                  );
                })
              )}
            </div>
          </aside>

          {/* ─── RIGHT: Розмова ─────────────────────────────────────────────── */}
          <main
            className={`${mobileView === 'list' ? 'hidden md:flex' : 'flex'} flex-1 flex-col bg-corp-bg-light/30`}
            data-testid="chat-conversation"
          >
            {!selectedOrder ? (
              <div className="flex-1 flex items-center justify-center text-corp-text-muted">
                <div className="text-center max-w-sm px-6">
                  <MessageSquare className="w-12 h-12 mx-auto mb-3 opacity-30" />
                  <p className="text-sm">Оберіть замовлення зі списку зліва, щоб переглянути чат із клієнтом</p>
                </div>
              </div>
            ) : (
              <>
                {/* Header */}
                <div className="px-4 py-3 border-b border-corp-border bg-white flex items-center gap-3" data-testid="chat-header">
                  <button
                    onClick={() => setMobileView('list')}
                    className="md:hidden p-1 hover:bg-corp-bg-light rounded transition"
                    aria-label="Назад"
                  >
                    <ChevronLeft className="w-5 h-5" />
                  </button>
                  <div className="h-9 w-9 rounded-full bg-corp-primary/10 grid place-content-center">
                    <User className="w-4 h-4 text-corp-primary" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold text-corp-text-dark truncate">
                      {selectedOrder.customer_name || '—'}
                    </div>
                    <div className="text-xs text-corp-text-muted truncate">
                      {selectedOrder.order_number}
                      {selectedOrder.customer_phone ? ` · ${selectedOrder.customer_phone}` : ''}
                    </div>
                  </div>
                  <button
                    onClick={() => navigate(`/order/${selectedOrder.order_id}/estimate`)}
                    className="text-xs px-3 py-1.5 border border-corp-border rounded-corp hover:bg-corp-bg-light"
                    data-testid="chat-open-order-btn"
                  >
                    Відкрити замовлення
                  </button>
                </div>

                {/* Messages */}
                <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2" data-testid="chat-messages">
                  {loadingMsgs && messages.length === 0 ? (
                    <div className="text-center text-xs text-corp-text-muted py-8">Завантаження...</div>
                  ) : messages.length === 0 ? (
                    <div className="text-center text-xs text-corp-text-muted py-8">
                      Ще немає повідомлень. Напишіть першим — клієнт побачить його у своєму кабінеті.
                    </div>
                  ) : (
                    messages.map((m) => {
                      const isManager = m.sender_type === 'manager' || m.sender_type === 'admin';
                      const isSystem  = m.sender_type === 'system';
                      if (isSystem) {
                        return (
                          <div key={m.id} className="flex justify-center" data-testid={`chat-message-${m.id}`}>
                            <div className="text-[11px] text-corp-text-muted bg-corp-bg-light px-3 py-1 rounded-full">
                              {m.message}
                              <span className="ml-2 opacity-60">{formatTime(m.created_at)}</span>
                            </div>
                          </div>
                        );
                      }
                      return (
                        <div
                          key={m.id}
                          className={`flex ${isManager ? 'justify-end' : 'justify-start'}`}
                          data-testid={`chat-message-${m.id}`}
                        >
                          <div
                            className={`max-w-[78%] rounded-2xl px-3 py-2 text-sm ${
                              isManager
                                ? 'bg-corp-primary text-white rounded-br-sm'
                                : 'bg-white border border-corp-border text-corp-text-dark rounded-bl-sm'
                            }`}
                          >
                            <div className="whitespace-pre-wrap break-words">{m.message}</div>
                            <div className={`text-[10px] mt-1 ${isManager ? 'text-white/70' : 'text-corp-text-muted'}`}>
                              {m.sender_name || (isManager ? 'Менеджер' : 'Клієнт')} · {formatTime(m.created_at)}
                            </div>
                          </div>
                        </div>
                      );
                    })
                  )}
                  <div ref={messagesEndRef} />
                </div>

                {/* Input */}
                <div className="px-3 py-3 border-t border-corp-border bg-white flex items-end gap-2" data-testid="chat-input-row">
                  <textarea
                    ref={inputRef}
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        sendMessage();
                      }
                    }}
                    placeholder="Напишіть клієнту..."
                    rows={1}
                    data-testid="chat-input"
                    className="flex-1 resize-none px-3 py-2 text-sm border border-corp-border rounded-corp focus:outline-none focus:border-corp-primary"
                    style={{ maxHeight: 120 }}
                  />
                  <button
                    onClick={sendMessage}
                    disabled={sending || !newMessage.trim()}
                    data-testid="chat-send-btn"
                    className="flex items-center gap-1.5 px-4 py-2 bg-corp-primary text-white rounded-corp text-sm font-medium hover:bg-corp-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition"
                  >
                    <Send className="w-4 h-4" />
                    <span className="hidden sm:inline">Надіслати</span>
                  </button>
                </div>
              </>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
