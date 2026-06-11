import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../api/axios';
import { ordersApi } from '../api/orders';
import SignDocumentModal from './SignDocumentModal';

const ORDER_STATUS_LABELS = {
  pending: { text: 'Очікує підтвердження', color: '#b58a00', bg: '#fff7d6' },
  awaiting_customer: { text: 'Чекає на клієнта', color: '#b58a00', bg: '#fff7d6' },
  processing: { text: 'В обробці', color: '#1565c0', bg: '#e3f2fd' },
  ready_for_issue: { text: 'Готове до видачі', color: '#1565c0', bg: '#e3f2fd' },
  issued: { text: 'Видано', color: '#2e7d32', bg: '#e8f5e9' },
  on_rent: { text: 'В оренді', color: '#2e7d32', bg: '#e8f5e9' },
  returned: { text: 'Повернено', color: '#555', bg: '#eee' },
  completed: { text: 'Завершено', color: '#555', bg: '#eee' },
  cancelled: { text: 'Скасовано', color: '#c62828', bg: '#ffebee' },
};

const PAYMENT_LABELS = {
  unpaid: { text: 'Не оплачено', color: '#c62828', bg: '#ffebee' },
  pending: { text: 'Очікує оплати', color: '#b58a00', bg: '#fff7d6' },
  partially_paid: { text: 'Частково сплачено', color: '#1565c0', bg: '#e3f2fd' },
  paid: { text: 'Оплачено', color: '#2e7d32', bg: '#e8f5e9' },
  deposit_paid: { text: 'Завдаток внесено', color: '#2e7d32', bg: '#e8f5e9' },
  refunded: { text: 'Повернуто', color: '#555', bg: '#eee' },
};

const formatDate = (iso) => {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('uk-UA', { day: '2-digit', month: '2-digit', year: 'numeric' });
  } catch { return iso; }
};

const UserProfile = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [boards, setBoards] = useState([]);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('orders'); // 'orders' | 'boards'
  const [docsByOrder, setDocsByOrder] = useState({}); // {orderId: [docs]}
  const [openedOrderId, setOpenedOrderId] = useState(null);
  // Документ що клієнт зараз підписує (модалка)
  const [signingDoc, setSigningDoc] = useState(null); // {orderId, document}
  // Кеш повних деталей замовлення (з items + photos)
  const [orderDetailsCache, setOrderDetailsCache] = useState({}); // {orderId: detail}
  const [expandedItems, setExpandedItems] = useState(null); // orderId: показати items

  useEffect(() => {
    loadData();
  }, []);

  // 🔄 Polling: автооновлення замовлень кожні 30с поки вкладка активна
  useEffect(() => {
    if (activeTab !== 'orders') return;
    const interval = setInterval(() => {
      // Тихе оновлення без спінера
      ordersApi.list()
        .then(data => setOrders(data))
        .catch(() => {});
    }, 30000);
    return () => clearInterval(interval);
  }, [activeTab]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [boardsData, ordersData] = await Promise.all([
        api.get('/event/boards').then(r => r.data).catch(() => []),
        ordersApi.list().catch(() => []),
      ]);
      setBoards(boardsData);
      setOrders(ordersData);
    } catch (error) {
      console.error('Failed to load profile data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteBoard = async (boardId) => {
    if (!window.confirm('Ви впевнені, що хочете видалити цей мудборд?')) {
      return;
    }

    try {
      await api.delete(`/event/boards/${boardId}`);
      setBoards(boards.filter(b => b.id !== boardId));
      alert('✅ Мудборд видалено');
    } catch (error) {
      console.error('Failed to delete board:', error);
      alert('Помилка видалення мудборду');
    }
  };

  const toggleOrderDocs = async (orderId) => {
    if (openedOrderId === orderId) {
      setOpenedOrderId(null);
      return;
    }
    setOpenedOrderId(orderId);
    if (!docsByOrder[orderId]) {
      try {
        const docs = await ordersApi.documents(orderId);
        setDocsByOrder(prev => ({...prev, [orderId]: Array.isArray(docs) ? docs : []}));
      } catch (e) {
        console.error('Failed to load docs:', e);
        setDocsByOrder(prev => ({...prev, [orderId]: []}));
      }
    }
  };

  const toggleOrderItems = async (orderId) => {
    if (expandedItems === orderId) {
      setExpandedItems(null);
      return;
    }
    setExpandedItems(orderId);
    if (!orderDetailsCache[orderId]) {
      try {
        const detail = await ordersApi.get(orderId);
        setOrderDetailsCache(prev => ({...prev, [orderId]: detail}));
      } catch (e) {
        console.error('Failed to load order details:', e);
      }
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return '—';
    return new Date(dateString).toLocaleDateString('uk-UA');
  };

  const getTotalItems = (board) => {
    return board.items?.reduce((sum, item) => sum + item.quantity, 0) || 0;
  };

  return (
    <div className="min-h-screen" style={{background: '#f5f5f5'}}>
      {/* Header */}
      <header className="fd-header sticky top-0 z-10 profile-header" style={{background: '#fff', borderBottom: '1px solid #e3e3e3'}}>
        <div className="profile-header-inner">
          <div className="profile-header-brand">
            <img
              src="/logo.svg"
              alt="FarforDecor Logo"
              style={{height: '40px', width: 'auto'}}
            />
            <h1 className="text-xl font-bold profile-header-title" style={{color: '#333'}}>
              FarforDecorOrenda
            </h1>
            <div className="w-px h-5 profile-header-divider" style={{background: '#e6e6e6'}}></div>
            <span className="text-xs profile-header-label" style={{color: '#999', textTransform: 'uppercase'}}>
              Особистий кабінет
            </span>
          </div>
          <div className="profile-header-actions">
            <button
              onClick={() => navigate('/')}
              className="fd-btn fd-btn-secondary"
            >
              Каталог
            </button>
            <span className="text-sm" style={{color: '#555'}}>
              {user?.firstname} {user?.lastname}
            </span>
            <button
              onClick={logout}
              className="fd-btn fd-btn-secondary"
            >
              Вийти
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto p-8">
        {/* User Info */}
        <div style={{
          background: '#fff',
          borderRadius: '8px',
          padding: '32px',
          marginBottom: '32px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)'
        }}>
          <h2 style={{fontSize: '24px', fontWeight: '600', color: '#333', marginBottom: '16px'}}>
            Вітаємо, {user?.firstname}!
          </h2>
          <div className="profile-stats-grid">
            <div>
              <div style={{fontSize: '12px', color: '#999', textTransform: 'uppercase', marginBottom: '8px'}}>
                Email
              </div>
              <div style={{fontSize: '14px', color: '#333', wordBreak: 'break-word'}}>
                {user?.email}
              </div>
            </div>
            <div>
              <div style={{fontSize: '12px', color: '#999', textTransform: 'uppercase', marginBottom: '8px'}}>
                Телефон
              </div>
              <div style={{fontSize: '14px', color: '#333'}}>
                {user?.telephone || '—'}
              </div>
            </div>
            <div>
              <div style={{fontSize: '12px', color: '#999', textTransform: 'uppercase', marginBottom: '8px'}}>
                Мудбордів
              </div>
              <div style={{fontSize: '24px', fontWeight: '600', color: '#333'}}>
                {boards.length}
              </div>
            </div>
            <div>
              <div style={{fontSize: '12px', color: '#999', textTransform: 'uppercase', marginBottom: '8px'}}>
                Замовлень
              </div>
              <div style={{fontSize: '24px', fontWeight: '600', color: '#333'}}>
                {orders.length}
              </div>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div style={{display: 'flex', gap: '4px', borderBottom: '1px solid #e0e0e0', marginBottom: '24px'}}>
          {[
            {key: 'orders', label: `Мої замовлення (${orders.length})`},
            {key: 'boards', label: `Мої мудборди (${boards.length})`},
          ].map(t => (
            <button
              key={t.key}
              data-testid={`profile-tab-${t.key}`}
              onClick={() => setActiveTab(t.key)}
              style={{
                padding: '12px 24px',
                background: 'transparent',
                border: 'none',
                borderBottom: activeTab === t.key ? '2px solid #0a3d2e' : '2px solid transparent',
                fontWeight: activeTab === t.key ? '600' : '400',
                color: activeTab === t.key ? '#0a3d2e' : '#666',
                cursor: 'pointer',
                fontSize: '14px',
                marginBottom: '-1px',
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Замовлення */}
        {activeTab === 'orders' && (
          <div data-testid="profile-orders-section">
            {loading ? (
              <div className="text-center py-12" style={{color: '#999'}}>Завантаження...</div>
            ) : orders.length === 0 ? (
              <div style={{background: '#fff', borderRadius: '8px', padding: '64px', textAlign: 'center'}}>
                <div style={{fontSize: '48px', marginBottom: '16px'}}>📦</div>
                <div style={{fontSize: '18px', fontWeight: '600', color: '#333', marginBottom: '8px'}}>
                  У вас поки немає замовлень
                </div>
                <div style={{fontSize: '14px', color: '#999', marginBottom: '24px'}}>
                  Створіть мудборд і оформіть перше замовлення
                </div>
                <button onClick={() => navigate('/')} className="fd-btn fd-btn-black">
                  Перейти до каталогу
                </button>
              </div>
            ) : (
              <div style={{display: 'flex', flexDirection: 'column', gap: '16px'}}>
                {orders.map((o) => {
                  const status = ORDER_STATUS_LABELS[o.status] || {text: o.status || '—', color: '#555', bg: '#eee'};
                  const paymentLabel = PAYMENT_LABELS[o.payment_status] || (o.payment_status ? {text: o.payment_status, color: '#555', bg: '#eee'} : null);
                  const isOpen = openedOrderId === o.order_id;
                  const docs = docsByOrder[o.order_id] || [];
                  return (
                    <div
                      key={o.order_id}
                      data-testid={`order-card-${o.order_id}`}
                      style={{
                        background: '#fff',
                        borderRadius: '8px',
                        padding: '20px 24px',
                        boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                        border: '1px solid #ececec',
                      }}
                    >
                      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px', flexWrap: 'wrap'}}>
                        <div style={{flex: 1, minWidth: 0}}>
                          <div style={{display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', flexWrap: 'wrap'}}>
                            <h4 style={{fontSize: '17px', fontWeight: '700', color: '#222', margin: 0}}>
                              {o.order_number || `#${o.order_id}`}
                            </h4>
                            <span style={{
                              padding: '3px 10px',
                              borderRadius: '999px',
                              fontSize: '12px',
                              fontWeight: '600',
                              color: status.color,
                              background: status.bg,
                            }}>
                              {status.text}
                            </span>
                            {paymentLabel && (
                              <span style={{
                                padding: '3px 10px',
                                borderRadius: '999px',
                                fontSize: '12px',
                                fontWeight: '600',
                                color: paymentLabel.color,
                                background: paymentLabel.bg,
                              }}>
                                💳 {paymentLabel.text}
                              </span>
                            )}
                          </div>
                          <div style={{fontSize: '13px', color: '#666', marginBottom: '4px'}}>
                            📅 {formatDate(o.rental_start_date)} → {formatDate(o.rental_end_date)}
                            {o.rental_days ? ` (${o.rental_days} дн)` : ''}
                          </div>
                          {o.event_location && (
                            <div style={{fontSize: '13px', color: '#666'}}>
                              🎉 {o.event_location}
                            </div>
                          )}
                          <div style={{fontSize: '12px', color: '#999', marginTop: '6px'}}>
                            {o.items_count} позицій • створено {formatDate(o.created_at)}
                            {o.updated_at && o.updated_at !== o.created_at && (
                              <> • оновлено {formatDate(o.updated_at)}</>
                            )}
                          </div>

                          {/* 📦 Прогрес комплектації */}
                          {typeof o.packing_progress === 'number' && o.packing_progress > 0 && (
                            <div style={{marginTop: '10px'}} data-testid={`packing-progress-${o.order_id}`}>
                              <div style={{display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#666', marginBottom: '4px'}}>
                                <span>📦 Комплектація</span>
                                <span style={{fontWeight: '600', color: '#0a3d2e'}}>{o.packing_progress}%</span>
                              </div>
                              <div style={{width: '100%', height: '6px', background: '#eef2f0', borderRadius: '999px', overflow: 'hidden'}}>
                                <div style={{
                                  width: `${o.packing_progress}%`,
                                  height: '100%',
                                  background: o.packing_progress >= 100 ? '#16a34a' : '#0a3d2e',
                                  transition: 'width 0.4s ease',
                                }} />
                              </div>
                            </div>
                          )}

                          {/* 💬 Коментар менеджера */}
                          {o.manager_comment && o.manager_comment.trim() && (
                            <div style={{
                              marginTop: '10px',
                              padding: '8px 12px',
                              background: '#fff7d6',
                              borderLeft: '3px solid #b58a00',
                              borderRadius: '4px',
                              fontSize: '12px',
                              color: '#5a4400',
                            }} data-testid={`manager-comment-${o.order_id}`}>
                              <strong>Менеджер:</strong> {o.manager_comment}
                            </div>
                          )}
                        </div>
                        <div style={{textAlign: 'right'}}>
                          <div style={{fontSize: '22px', fontWeight: '700', color: '#0a3d2e'}}>
                            ₴{(o.total_to_pay || o.total_price || 0).toFixed(2)}
                          </div>
                          {/* Деталі суми: знижка / сервісний збір */}
                          {(o.discount_amount > 0 || o.service_fee > 0) && (
                            <div style={{fontSize: '11px', color: '#888', marginTop: '2px'}}>
                              {o.discount_amount > 0 && <>знижка −₴{o.discount_amount.toFixed(2)} </>}
                              {o.service_fee > 0 && <>+сервіс ₴{o.service_fee.toFixed(2)}</>}
                            </div>
                          )}
                          {o.deposit_amount > 0 && (
                            <div style={{fontSize: '12px', color: '#888', marginTop: '4px'}}>
                              Завдаток: ₴{o.deposit_amount.toFixed(2)}
                              {o.paid_deposit > 0 && (
                                <span style={{color: '#2e7d32', fontWeight: '600'}}> (сплачено ₴{o.paid_deposit.toFixed(2)})</span>
                              )}
                            </div>
                          )}
                          {o.paid_rent > 0 && (
                            <div style={{fontSize: '12px', color: '#2e7d32', marginTop: '2px', fontWeight: '600'}} data-testid={`paid-rent-${o.order_id}`}>
                              ✅ Сплачено: ₴{o.paid_rent.toFixed(2)}
                            </div>
                          )}
                          <div style={{display: 'flex', gap: '6px', marginTop: '10px', flexWrap: 'wrap', justifyContent: 'flex-end'}}>
                            <button
                              onClick={() => toggleOrderItems(o.order_id)}
                              data-testid={`order-items-toggle-${o.order_id}`}
                              style={{
                                padding: '6px 12px',
                                background: expandedItems === o.order_id ? '#0a3d2e' : '#f5f5f5',
                                color: expandedItems === o.order_id ? '#fff' : '#0a3d2e',
                                border: '1px solid #0a3d2e',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontSize: '12px',
                                fontWeight: '600',
                              }}
                            >
                              🛍 Склад {expandedItems === o.order_id ? '▲' : '▼'}
                            </button>
                            <button
                              onClick={() => toggleOrderDocs(o.order_id)}
                              data-testid={`order-docs-toggle-${o.order_id}`}
                              style={{
                                padding: '6px 12px',
                                background: isOpen ? '#0a3d2e' : '#f5f5f5',
                                color: isOpen ? '#fff' : '#0a3d2e',
                                border: '1px solid #0a3d2e',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontSize: '12px',
                                fontWeight: '600',
                              }}
                            >
                              📄 Документи {isOpen ? '▲' : '▼'}
                            </button>
                          </div>
                        </div>
                      </div>

                      {/* Розгорнутий склад замовлення з фото, артикулом, цінами */}
                      {expandedItems === o.order_id && (
                        <div
                          data-testid={`order-items-${o.order_id}`}
                          style={{marginTop: '16px', paddingTop: '16px', borderTop: '1px solid #f0f0f0'}}
                        >
                          {!orderDetailsCache[o.order_id] ? (
                            <div style={{fontSize: '13px', color: '#999'}}>Завантаження...</div>
                          ) : (orderDetailsCache[o.order_id].items || []).length === 0 ? (
                            <div style={{fontSize: '13px', color: '#999', fontStyle: 'italic'}}>
                              Позицій ще немає (менеджер опрацьовує)
                            </div>
                          ) : (
                            <>
                              <div style={{fontSize: '13px', fontWeight: '600', color: '#444', marginBottom: '10px'}}>
                                Позиції в замовленні (кількість діб встановлює менеджер):
                              </div>
                              <div style={{display: 'flex', flexDirection: 'column', gap: '10px'}}>
                                {(orderDetailsCache[o.order_id].items || []).map((it, idx) => (
                                  <div key={idx} style={{
                                    display: 'flex', gap: '12px', padding: '10px',
                                    background: '#fafafa', borderRadius: '8px',
                                    border: '1px solid #ececec', alignItems: 'flex-start',
                                  }}>
                                    {/* Фото */}
                                    <div style={{
                                      width: '64px', height: '64px', borderRadius: '6px',
                                      background: '#fff', overflow: 'hidden', flexShrink: 0,
                                      border: '1px solid #eee',
                                    }}>
                                      {it.image_url ? (
                                        <img src={it.image_url} alt={it.product_name}
                                             style={{width: '100%', height: '100%', objectFit: 'cover'}}/>
                                      ) : (
                                        <div style={{width: '100%', height: '100%', background: '#f0f0f0',
                                                     display: 'flex', alignItems: 'center', justifyContent: 'center',
                                                     fontSize: '20px', color: '#bbb'}}>📦</div>
                                      )}
                                    </div>
                                    {/* Інфо */}
                                    <div style={{flex: 1, minWidth: 0}}>
                                      <div style={{fontWeight: '600', color: '#222', fontSize: '14px', lineHeight: 1.3}}>
                                        {it.product_name}
                                      </div>
                                      {it.sku && (
                                        <div style={{fontSize: '11px', color: '#888', marginTop: '2px'}}>
                                          Артикул: <code style={{background: '#eee', padding: '1px 5px', borderRadius: '3px'}}>{it.sku}</code>
                                        </div>
                                      )}
                                      {(it.color || it.material) && (
                                        <div style={{fontSize: '11px', color: '#888', marginTop: '2px'}}>
                                          {it.color && <>🎨 {it.color}</>}{it.color && it.material && ' · '}
                                          {it.material && <>{it.material}</>}
                                        </div>
                                      )}
                                      <div style={{fontSize: '12px', color: '#444', marginTop: '6px', display: 'flex', gap: '14px', flexWrap: 'wrap'}}>
                                        <span><strong>×{it.quantity}</strong> шт</span>
                                        <span style={{color: '#0a3d2e'}}>₴{(it.price_per_day || 0).toFixed(2)}/добу</span>
                                        {it.deposit_per_unit > 0 && (
                                          <span style={{color: '#b58a00'}}>застава: ₴{it.deposit_per_unit.toFixed(2)}/шт</span>
                                        )}
                                      </div>
                                      <div style={{fontSize: '12px', color: '#222', marginTop: '4px', fontWeight: '600'}}>
                                        Разом за позицію: ₴{(it.total_rental || 0).toFixed(2)}
                                        {it.total_deposit > 0 && <span style={{color: '#888', fontWeight: 'normal'}}> + застава ₴{it.total_deposit.toFixed(2)}</span>}
                                      </div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                              <div style={{
                                marginTop: '12px', padding: '10px',
                                background: '#f0f9ff', borderLeft: '3px solid #0ea5e9',
                                borderRadius: '4px', fontSize: '12px', color: '#0c4a6e',
                              }}>
                                💡 <strong>Звертайте увагу:</strong> ціна оренди за добу × кількість діб × кількість одиниць = сума за позицію.
                                Кількість діб оренди визначає менеджер при підтвердженні замовлення (за фактом видачі/повернення).
                              </div>
                            </>
                          )}
                        </div>
                      )}

                      {isOpen && (
                        <div
                          data-testid={`order-docs-${o.order_id}`}
                          style={{
                            marginTop: '16px',
                            paddingTop: '16px',
                            borderTop: '1px solid #f0f0f0',
                          }}
                        >
                          {docs.length === 0 ? (
                            <div style={{fontSize: '13px', color: '#999', fontStyle: 'italic'}}>
                              Документів по цьому замовленню ще немає. Менеджер сформує їх найближчим часом.
                            </div>
                          ) : (
                            <div style={{display: 'flex', flexDirection: 'column', gap: '8px'}}>
                              {docs.map(d => (
                                <div
                                  key={d.id}
                                  style={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                    padding: '10px 14px',
                                    background: d.needs_client_signature ? '#fef3c7' : '#fafafa',
                                    borderRadius: '6px',
                                    border: d.needs_client_signature ? '1px solid #fcd34d' : '1px solid #ececec',
                                    gap: '8px',
                                    flexWrap: 'wrap',
                                  }}
                                >
                                  <div style={{flex: 1, minWidth: '160px'}}>
                                    <div style={{fontWeight: '600', fontSize: '14px', color: '#222'}}>
                                      {d.doc_type_label}
                                      {d.doc_number ? ` №${d.doc_number}` : ''}
                                      {d.needs_client_signature && (
                                        <span style={{marginLeft: '8px', fontSize: '11px', padding: '2px 8px', background: '#dc2626', color: '#fff', borderRadius: '10px', fontWeight: '700'}}>
                                          ПОТРЕБУЄ ВАШОГО ПІДПИСУ
                                        </span>
                                      )}
                                      {d.status === 'signed' && (
                                        <span style={{marginLeft: '8px', fontSize: '11px', padding: '2px 8px', background: '#16a34a', color: '#fff', borderRadius: '10px', fontWeight: '700'}}>
                                          ✓ ПІДПИСАНО
                                        </span>
                                      )}
                                      {d.is_signable && d.tenant_signed && !d.landlord_signed && (
                                        <span style={{marginLeft: '8px', fontSize: '11px', padding: '2px 8px', background: '#f59e0b', color: '#fff', borderRadius: '10px', fontWeight: '700'}}>
                                          ⏳ ОЧІКУЄ МЕНЕДЖЕРА
                                        </span>
                                      )}
                                    </div>
                                    <div style={{fontSize: '11px', color: '#999', marginTop: '2px'}}>
                                      {formatDate(d.created_at)}
                                    </div>
                                  </div>
                                  <div style={{display: 'flex', gap: '6px', flexWrap: 'wrap'}}>
                                    <a
                                      href={d.preview_url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      style={{
                                        padding: '6px 12px',
                                        background: '#fff',
                                        color: '#0a3d2e',
                                        border: '1px solid #0a3d2e',
                                        borderRadius: '4px',
                                        fontSize: '12px',
                                        fontWeight: '600',
                                        textDecoration: 'none',
                                      }}
                                    >
                                      Переглянути
                                    </a>
                                    <a
                                      href={d.pdf_url}
                                      style={{
                                        padding: '6px 12px',
                                        background: '#0a3d2e',
                                        color: '#fff',
                                        border: '1px solid #0a3d2e',
                                        borderRadius: '4px',
                                        fontSize: '12px',
                                        fontWeight: '600',
                                        textDecoration: 'none',
                                      }}
                                    >
                                      PDF
                                    </a>
                                    {d.needs_client_signature && (
                                      <button
                                        onClick={() => setSigningDoc({orderId: o.order_id, document: d})}
                                        data-testid={`sign-doc-btn-${d.id}`}
                                        style={{
                                          padding: '6px 12px',
                                          background: '#dc2626',
                                          color: '#fff',
                                          border: '1px solid #dc2626',
                                          borderRadius: '4px',
                                          fontSize: '12px',
                                          fontWeight: '700',
                                          cursor: 'pointer',
                                        }}
                                      >
                                        ✍️ Підписати
                                      </button>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Мудборди */}
        {activeTab === 'boards' && (
        <div data-testid="profile-boards-section">
          <div className="flex items-center justify-between mb-6">
            <h3 style={{fontSize: '20px', fontWeight: '600', color: '#333'}}>
              Мої мудборди
            </h3>
            <button
              onClick={() => navigate('/')}
              className="fd-btn fd-btn-black"
            >
              + Створити новий
            </button>
          </div>

          {loading ? (
            <div className="text-center py-12" style={{color: '#999'}}>
              Завантаження...
            </div>
          ) : boards.length === 0 ? (
            <div style={{
              background: '#fff',
              borderRadius: '8px',
              padding: '64px',
              textAlign: 'center'
            }}>
              <div style={{fontSize: '48px', marginBottom: '16px'}}>📋</div>
              <div style={{fontSize: '18px', fontWeight: '600', color: '#333', marginBottom: '8px'}}>
                У вас ще немає мудбордів
              </div>
              <div style={{fontSize: '14px', color: '#999', marginBottom: '24px'}}>
                Створіть перший мудборд у каталозі товарів
              </div>
              <button
                onClick={() => navigate('/')}
                className="fd-btn fd-btn-black"
              >
                Перейти до каталогу
              </button>
            </div>
          ) : (
            <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '24px'}}>
              {boards.map((board) => (
                <div
                  key={board.id}
                  style={{
                    background: '#fff',
                    borderRadius: '8px',
                    overflow: 'hidden',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                    transition: 'all 0.2s',
                    cursor: 'pointer',
                    border: '1px solid #e8e8e8'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,0,0,0.12)';
                    e.currentTarget.style.transform = 'translateY(-2px)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.08)';
                    e.currentTarget.style.transform = 'translateY(0)';
                  }}
                >
                  {/* Board Cover */}
                  <div
                    style={{
                      height: '180px',
                      background: board.cover_image
                        ? `url(${board.cover_image}) center/cover`
                        : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#fff',
                      fontSize: '48px'
                    }}
                  >
                    {!board.cover_image && '🎨'}
                  </div>

                  {/* Board Info */}
                  <div style={{padding: '20px'}}>
                    <h4 style={{
                      fontSize: '16px',
                      fontWeight: '600',
                      color: '#333',
                      marginBottom: '12px',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap'
                    }}>
                      {board.board_name}
                    </h4>

                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: '1fr 1fr',
                      gap: '12px',
                      marginBottom: '16px',
                      fontSize: '13px'
                    }}>
                      <div>
                        <div style={{color: '#999', marginBottom: '4px'}}>Товарів</div>
                        <div style={{fontWeight: '600', color: '#333'}}>{getTotalItems(board)}</div>
                      </div>
                      <div>
                        <div style={{color: '#999', marginBottom: '4px'}}>Оновлено</div>
                        <div style={{fontWeight: '600', color: '#333'}}>{formatDate(board.updated_at)}</div>
                      </div>
                    </div>

                    {board.event_date && (
                      <div style={{
                        fontSize: '12px',
                        color: '#666',
                        marginBottom: '16px',
                        padding: '8px 12px',
                        background: '#f9f9f9',
                        borderRadius: '4px'
                      }}>
                        📅 {formatDate(board.event_date)}
                        {board.event_type && ` • ${board.event_type}`}
                      </div>
                    )}

                    {/* Actions */}
                    <div style={{display: 'flex', gap: '8px'}}>
                      <button
                        onClick={() => navigate('/', { state: { boardId: board.id } })}
                        className="fd-btn fd-btn-secondary"
                        style={{flex: 1, fontSize: '12px'}}
                      >
                        Відкрити
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteBoard(board.id);
                        }}
                        className="fd-btn fd-btn-secondary"
                        style={{fontSize: '12px', color: '#dc3545'}}
                      >
                        Видалити
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        )}
      </div>

      {/* Модалка підписання документа */}
      {signingDoc && (
        <SignDocumentModal
          orderId={signingDoc.orderId}
          document={signingDoc.document}
          user={user}
          onClose={() => setSigningDoc(null)}
          onSigned={() => {
            // Перезавантажуємо документи цього замовлення
            setDocsByOrder(prev => {
              const copy = {...prev};
              delete copy[signingDoc.orderId];
              return copy;
            });
            setSigningDoc(null);
            // Перевідкриваємо щоб показати оновлені бейджі
            const oid = signingDoc.orderId;
            setTimeout(() => toggleOrderDocs(oid), 100);
          }}
        />
      )}
    </div>
  );
};

export default UserProfile;
