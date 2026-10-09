/* eslint-disable */
/**
 * ClientChatPage — окрема сторінка чату для клієнта (Event Tool).
 *
 * Маршрут: /chat
 *
 * Ліва панель — усі свої замовлення з лічильником непрочитаних.
 * Права панель — існуючий <OrderChat> з WebSocket (вже працює і
 * використовується inline на сторінках замовлень як модальний чат).
 *
 * Backend (клієнтська частина — НЕ admin):
 *   GET /api/event/orders                              — список власних замовлень
 *   GET /api/event/orders/{id}/chat/messages           — через WebSocket усередині OrderChat
 *   GET /api/event/orders/{id}/chat/unread_count       — для бейджа
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { MessageSquare, ChevronLeft, Search } from 'lucide-react';
import api from '../api/axios';
import { chatAPI } from '../api/chat';
import OrderChat from '../components/OrderChat';

const STATUS_LABELS = {
  pending:            'Очікує',
  awaiting_customer:  'Очікує підтвердження',
  processing:         'Комплектація',
  ready_for_issue:    'Готово до видачі',
  issued:             'Видано',
  on_rent:            'В оренді',
  returned:           'Повернено',
  completed:          'Завершено',
  cancelled:          'Скасовано',
};

function formatDate(d) {
  if (!d) return '';
  try { return new Date(d).toLocaleDateString('uk-UA'); }
  catch { return ''; }
}

const ClientChatPage = () => {
  const navigate = useNavigate();
  const [orders, setOrders] = useState([]);
  const [unread, setUnread] = useState({});
  const [selectedId, setSelectedId] = useState(null);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [mobileView, setMobileView] = useState('list'); // 'list' | 'chat'

  const fetchOrders = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/event/orders');
      const arr = Array.isArray(r.data) ? r.data : r.data?.orders || [];
      setOrders(arr);
      // unread лічильник
      const counts = {};
      await Promise.all(arr.slice(0, 30).map(async (o) => {
        try {
          const u = await chatAPI.unreadCount(o.order_id);
          counts[o.order_id] = u?.unread || u?.count || 0;
        } catch { /* ignore */ }
      }));
      setUnread(counts);
    } catch (e) {
      console.error('[ClientChatPage] orders load:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchOrders(); }, [fetchOrders]);

  // Оновлювати лічильник кожні 30 сек
  useEffect(() => {
    const t = setInterval(fetchOrders, 30000);
    return () => clearInterval(t);
  }, [fetchOrders]);

  // Обираємо замовлення → переходимо у view-режим (mobile)
  useEffect(() => {
    if (selectedId) setMobileView('chat');
  }, [selectedId]);

  const filtered = orders.filter((o) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      String(o.order_number || '').toLowerCase().includes(q) ||
      String(o.event_name || '').toLowerCase().includes(q)
    );
  });

  // Сортування: непрочитані спершу, потім нові
  const sorted = [...filtered].sort((a, b) => {
    const ua = unread[a.order_id] || 0;
    const ub = unread[b.order_id] || 0;
    if (ub !== ua) return ub - ua;
    return new Date(b.created_at || 0) - new Date(a.created_at || 0);
  });

  const totalUnread = Object.values(unread).reduce((s, v) => s + v, 0);
  const selectedOrder = orders.find((o) => String(o.order_id) === String(selectedId));

  return (
    <div style={{
      minHeight: '100vh', background: '#f8f5ef',
      display: 'flex', flexDirection: 'column',
    }} data-testid="client-chat-page">
      {/* Header */}
      <div style={{
        background: '#0a3d2e', color: '#fff', padding: '14px 20px',
        display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <button
          onClick={() => navigate('/profile')}
          data-testid="chat-back-btn"
          style={{
            background: 'transparent', color: '#fff', border: 'none',
            cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 14,
          }}
        >
          <ChevronLeft size={18} /> Профіль
        </button>
        <div style={{ flex: 1, fontSize: 16, fontWeight: 600 }}>
          Чат з менеджером
          {totalUnread > 0 && (
            <span data-testid="client-total-unread" style={{
              marginLeft: 10, padding: '2px 8px', fontSize: 11, fontWeight: 700,
              background: '#ef4444', color: '#fff', borderRadius: 12,
            }}>
              {totalUnread} нових
            </span>
          )}
        </div>
      </div>

      {/* Body */}
      <div style={{
        flex: 1, maxWidth: 1200, width: '100%', margin: '0 auto', padding: 12,
      }}>
        <div style={{
          background: '#fff', borderRadius: 12, border: '1px solid #e7e0d0',
          display: 'flex', overflow: 'hidden',
          height: 'calc(100vh - 110px)', minHeight: 500,
        }} data-testid="client-chat-layout">

          {/* LEFT: order list */}
          <aside
            data-testid="client-chat-orders"
            style={{
              width: window.innerWidth < 768 ? (mobileView === 'chat' ? 0 : '100%') : 340,
              display: window.innerWidth < 768 && mobileView === 'chat' ? 'none' : 'flex',
              flexDirection: 'column', borderRight: '1px solid #e7e0d0',
            }}
          >
            <div style={{ padding: 14, borderBottom: '1px solid #e7e0d0', background: '#fafaf6' }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#0a3d2e', marginBottom: 8 }}>
                Мої замовлення
              </div>
              <div style={{ position: 'relative' }}>
                <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
                <input
                  type="text"
                  placeholder="Пошук номера..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  data-testid="client-chat-search"
                  style={{
                    width: '100%', padding: '8px 12px 8px 32px', fontSize: 12,
                    border: '1px solid #d4cab8', borderRadius: 8, boxSizing: 'border-box',
                  }}
                />
              </div>
            </div>

            <div style={{ flex: 1, overflowY: 'auto' }}>
              {loading && orders.length === 0 ? (
                <div style={{ padding: 24, textAlign: 'center', color: '#94a3b8', fontSize: 12 }}>
                  Завантаження...
                </div>
              ) : sorted.length === 0 ? (
                <div style={{ padding: 24, textAlign: 'center', color: '#94a3b8', fontSize: 12 }}>
                  У вас ще немає замовлень
                </div>
              ) : sorted.map((o) => {
                const isSel = String(o.order_id) === String(selectedId);
                const u = unread[o.order_id] || 0;
                return (
                  <button
                    key={o.order_id}
                    onClick={() => setSelectedId(o.order_id)}
                    data-testid={`client-chat-order-${o.order_id}`}
                    style={{
                      width: '100%', textAlign: 'left', padding: '12px 14px',
                      background: isSel ? '#f0f9ff' : 'transparent',
                      borderLeft: isSel ? '3px solid #0a3d2e' : '3px solid transparent',
                      borderBottom: '1px solid #f0eada',
                      cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 4,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: '#0a3d2e' }}>
                        {o.order_number || `#${o.order_id}`}
                      </span>
                      {u > 0 && (
                        <span
                          data-testid={`client-chat-unread-${o.order_id}`}
                          style={{
                            padding: '2px 6px', fontSize: 10, fontWeight: 700,
                            background: '#ef4444', color: '#fff', borderRadius: 10,
                          }}
                        >
                          {u}
                        </span>
                      )}
                    </div>
                    {o.event_name && (
                      <div style={{ fontSize: 12, color: '#475569' }}>
                        {o.event_name}
                      </div>
                    )}
                    <div style={{ fontSize: 11, color: '#94a3b8', display: 'flex', gap: 8 }}>
                      {o.event_date && <span>Подія: {formatDate(o.event_date)}</span>}
                      {o.status && <span style={{ marginLeft: 'auto' }}>{STATUS_LABELS[o.status] || o.status}</span>}
                    </div>
                  </button>
                );
              })}
            </div>
          </aside>

          {/* RIGHT: chat panel */}
          <main
            data-testid="client-chat-panel"
            style={{
              flex: 1, display: window.innerWidth < 768 && mobileView === 'list' ? 'none' : 'flex',
              flexDirection: 'column', background: '#fff',
            }}
          >
            {!selectedOrder ? (
              <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8' }}>
                <div style={{ textAlign: 'center', maxWidth: 320, padding: 24 }}>
                  <MessageSquare size={40} style={{ opacity: 0.3, marginBottom: 8 }} />
                  <p style={{ fontSize: 13 }}>
                    Оберіть замовлення зліва, щоб переглянути чат з менеджером
                  </p>
                </div>
              </div>
            ) : (
              <>
                {/* Mobile header — Back до списку + номер */}
                <div style={{
                  padding: '10px 14px', borderBottom: '1px solid #e7e0d0',
                  display: 'flex', alignItems: 'center', gap: 10, background: '#fafaf6',
                }}>
                  <button
                    onClick={() => setMobileView('list')}
                    style={{
                      display: window.innerWidth < 768 ? 'flex' : 'none',
                      background: 'transparent', border: 'none', cursor: 'pointer',
                      alignItems: 'center', gap: 2, color: '#0a3d2e',
                    }}
                  >
                    <ChevronLeft size={18} />
                  </button>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: '#0a3d2e' }}>
                      Замовлення {selectedOrder.order_number}
                    </div>
                    {selectedOrder.event_name && (
                      <div style={{ fontSize: 11, color: '#94a3b8' }}>{selectedOrder.event_name}</div>
                    )}
                  </div>
                </div>

                {/* Чат — використовуємо існуючий <OrderChat> з WebSocket */}
                <div style={{ flex: 1, overflow: 'hidden' }}>
                  <OrderChat
                    key={selectedOrder.order_id}  /* force-remount on order switch */
                    orderId={selectedOrder.order_id}
                    orderNumber={selectedOrder.order_number}
                  />
                </div>
              </>
            )}
          </main>
        </div>
      </div>
    </div>
  );
};

export default ClientChatPage;
