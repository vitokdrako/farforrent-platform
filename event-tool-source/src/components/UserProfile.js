import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../api/axios';
import { ordersApi } from '../api/orders';

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
      <header className="fd-header sticky top-0 z-10" style={{background: '#fff', borderBottom: '1px solid #e3e3e3'}}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <img 
              src="/logo.svg" 
              alt="FarforDecor Logo" 
              style={{height: '40px', width: 'auto'}}
            />
            <h1 className="text-xl font-bold" style={{color: '#333'}}>
              FarforDecorOrenda
            </h1>
            <div className="w-px h-5" style={{background: '#e6e6e6'}}></div>
            <span className="text-xs" style={{color: '#999', textTransform: 'uppercase'}}>
              Особистий кабінет
            </span>
          </div>
          <div className="flex items-center gap-4">
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
          <div style={{display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '24px'}}>
            <div>
              <div style={{fontSize: '12px', color: '#999', textTransform: 'uppercase', marginBottom: '8px'}}>
                Email
              </div>
              <div style={{fontSize: '14px', color: '#333'}}>
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
                          <button
                            onClick={() => toggleOrderDocs(o.order_id)}
                            data-testid={`order-docs-toggle-${o.order_id}`}
                            style={{
                              marginTop: '10px',
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
                                    background: '#fafafa',
                                    borderRadius: '6px',
                                    border: '1px solid #ececec',
                                  }}
                                >
                                  <div>
                                    <div style={{fontWeight: '600', fontSize: '14px', color: '#222'}}>
                                      {d.doc_type_label}
                                      {d.doc_number ? ` №${d.doc_number}` : ''}
                                    </div>
                                    <div style={{fontSize: '11px', color: '#999', marginTop: '2px'}}>
                                      {formatDate(d.created_at)}
                                      {d.status === 'signed' && ' • ✅ підписано'}
                                    </div>
                                  </div>
                                  <div style={{display: 'flex', gap: '6px'}}>
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
    </div>
  );
};

export default UserProfile;
