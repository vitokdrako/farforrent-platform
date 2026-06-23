import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Calendar, MapPin, ChevronDown, FileText, ShoppingBag, Check,
  Package, PenLine, Info, CreditCard, Clock
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useFavorites } from '../context/FavoritesContext';
import { favoritesAPI } from '../api/favorites';
import api from '../api/axios';
import { ordersApi } from '../api/orders';
import SignDocumentModal from './SignDocumentModal';
import NotificationToggle from './NotificationToggle';
import OrderChat from './OrderChat';
import AddToBoardModal from './AddToBoardModal';
import ProductCard from './ProductCard';
import { documentApprovalAPI } from '../api/chat';

const ORDER_STATUS_LABELS = {
  pending: { text: 'Очікує підтвердження', color: '#b58a00' },
  awaiting_customer: { text: 'В обробці', color: '#1565c0' },
  preparation: { text: 'На комплектації', color: '#b58a00' },
  processing: { text: 'В обробці', color: '#1565c0' },
  ready_for_issue: { text: 'Готове до видачі', color: '#0a3d2e' },
  issued: { text: 'Видано', color: '#0a3d2e' },
  on_rent: { text: 'В оренді', color: '#0a3d2e' },
  returned: { text: 'Повернено', color: '#555' },
  completed: { text: 'Завершено', color: '#555' },
  cancelled: { text: 'Скасовано', color: '#c62828' },
  cancelled_by_client: { text: 'Скасовано клієнтом', color: '#c62828' },
  cancelled_by_manager: { text: 'Скасовано менеджером', color: '#c62828' },
  signed: { text: 'Підписано', color: '#0a3d2e' },
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
  const { favoriteIds, toggle: toggleFav, refresh: refreshFav } = useFavorites();
  const [boards, setBoards] = useState([]);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('orders'); // 'orders' | 'boards' | 'favorites'
  const [docsByOrder, setDocsByOrder] = useState({}); // {orderId: [docs]}
  const [openedOrderId, setOpenedOrderId] = useState(null);
  // Документ що клієнт зараз підписує (модалка)
  const [signingDoc, setSigningDoc] = useState(null); // {orderId, document}
  // Кеш повних деталей замовлення (з items + photos)
  const [orderDetailsCache, setOrderDetailsCache] = useState({}); // {orderId: detail}
  const [expandedItems, setExpandedItems] = useState(null); // orderId: показати items
  // Кеш timeline
  const [timelineCache, setTimelineCache] = useState({}); // {orderId: [events]}
  // Обране
  const [favProducts, setFavProducts] = useState([]);
  const [favLoading, setFavLoading] = useState(false);
  const [addToBoardProduct, setAddToBoardProduct] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  // Завантажуємо обрані товари коли заходимо на вкладку
  useEffect(() => {
    if (activeTab !== 'favorites') return;
    setFavLoading(true);
    favoritesAPI.listProducts()
      .then((list) => setFavProducts(list))
      .catch(() => setFavProducts([]))
      .finally(() => setFavLoading(false));
  }, [activeTab, favoriteIds.length]);

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

        {/* Notification toggle */}
        <div style={{ marginBottom: '24px' }}>
          <NotificationToggle />
        </div>

        {/* Tabs */}
        <div style={{display: 'flex', gap: '4px', borderBottom: '1px solid #e0e0e0', marginBottom: '24px'}}>
          {[
            {key: 'orders', label: `Мої замовлення (${orders.length})`},
            {key: 'boards', label: `Мої мудборди (${boards.length})`},
            {key: 'favorites', label: `Обране (${favoriteIds.length})`},
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
                  // Єдиний стан розгортання: відкриваємо одночасно склад + документи
                  const expanded = expandedItems === o.order_id;
                  const toggleExpand = async () => {
                    if (expanded) {
                      setExpandedItems(null);
                      setOpenedOrderId(null);
                      return;
                    }
                    setExpandedItems(o.order_id);
                    setOpenedOrderId(o.order_id);
                    // Паралельно завантажуємо items і документи
                    if (!orderDetailsCache[o.order_id]) {
                      try {
                        const detail = await ordersApi.get(o.order_id);
                        setOrderDetailsCache(prev => ({...prev, [o.order_id]: detail}));
                      } catch (e) { /* silent */ }
                    }
                    if (!docsByOrder[o.order_id]) {
                      try {
                        const d = await ordersApi.documents(o.order_id);
                        setDocsByOrder(prev => ({...prev, [o.order_id]: Array.isArray(d) ? d : []}));
                      } catch (e) {
                        setDocsByOrder(prev => ({...prev, [o.order_id]: []}));
                      }
                    }
                    if (!timelineCache[o.order_id]) {
                      try {
                        const tl = await ordersApi.timeline(o.order_id);
                        setTimelineCache(prev => ({...prev, [o.order_id]: Array.isArray(tl) ? tl : []}));
                      } catch (e) {
                        setTimelineCache(prev => ({...prev, [o.order_id]: []}));
                      }
                    }
                  };

                  return (
                    <div
                      key={o.order_id}
                      data-testid={`order-card-${o.order_id}`}
                      style={{
                        background: '#fff',
                        borderRadius: '4px',
                        padding: '18px 20px',
                        border: '1px solid #e5e5e5',
                        transition: 'border-color 0.2s',
                        position: 'relative',
                      }}
                    >
                      {/* Клікабельний заголовок картки */}
                      <div
                        onClick={toggleExpand}
                        data-testid={`order-card-header-${o.order_id}`}
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'flex-start',
                          gap: '16px',
                          cursor: 'pointer',
                          userSelect: 'none',
                        }}
                      >
                        <div style={{flex: 1, minWidth: 0}}>
                          {/* Номер + статуси */}
                          <div style={{display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px', flexWrap: 'wrap'}}>
                            <h4 style={{fontSize: '15px', fontWeight: '600', color: '#1a1a1a', margin: 0, letterSpacing: '0.02em'}}>
                              {o.order_number || `#${o.order_id}`}
                            </h4>
                            <span style={{
                              padding: '2px 10px',
                              border: `1px solid ${status.color}`,
                              borderRadius: '2px',
                              fontSize: '10px',
                              fontWeight: '500',
                              color: status.color,
                              background: 'transparent',
                              textTransform: 'uppercase',
                              letterSpacing: '0.05em',
                            }}>
                              {status.text}
                            </span>
                            {paymentLabel && (
                              <span style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                                padding: '2px 8px',
                                border: '1px solid #e5e5e5',
                                borderRadius: '2px',
                                fontSize: '10px',
                                fontWeight: '500',
                                color: '#666',
                                textTransform: 'uppercase',
                                letterSpacing: '0.05em',
                              }}>
                                <CreditCard size={11} strokeWidth={1.5}/>
                                {paymentLabel.text}
                              </span>
                            )}
                          </div>

                          {/* Дати */}
                          <div style={{display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#666', marginBottom: '4px'}}>
                            <Calendar size={13} strokeWidth={1.5}/>
                            <span>{formatDate(o.rental_start_date)} → {formatDate(o.rental_end_date)}</span>
                            {o.rental_days ? <span style={{color: '#999'}}>· {o.rental_days} дн</span> : null}
                          </div>
                          {o.event_location && (
                            <div style={{display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#666', marginBottom: '4px'}}>
                              <MapPin size={13} strokeWidth={1.5}/>
                              <span>{o.event_location}</span>
                            </div>
                          )}
                          <div style={{display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#999', marginTop: '6px'}}>
                            <ShoppingBag size={11} strokeWidth={1.5}/>
                            <span>{o.items_count} позицій · {formatDate(o.created_at)}</span>
                            {o.updated_at && o.updated_at !== o.created_at && (
                              <span style={{color: '#bbb'}}>· оновлено {formatDate(o.updated_at)}</span>
                            )}
                          </div>

                          {/* Прогрес комплектації */}
                          {typeof o.packing_progress === 'number' && o.packing_progress > 0 && (
                            <div style={{marginTop: '12px'}} data-testid={`packing-progress-${o.order_id}`}>
                              <div style={{display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: '#666', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em'}}>
                                <span>Комплектація</span>
                                <span style={{fontWeight: '600', color: '#0a3d2e'}}>{o.packing_progress}%</span>
                              </div>
                              <div style={{width: '100%', height: '2px', background: '#eee', overflow: 'hidden'}}>
                                <div style={{
                                  width: `${o.packing_progress}%`,
                                  height: '100%',
                                  background: '#0a3d2e',
                                  transition: 'width 0.4s ease',
                                }} />
                              </div>
                            </div>
                          )}

                          {/* Коментар менеджера */}
                          {o.manager_comment && o.manager_comment.trim() && (
                            <div style={{
                              marginTop: '12px',
                              padding: '10px 12px',
                              background: '#fafafa',
                              borderLeft: '2px solid #0a3d2e',
                              fontSize: '12px',
                              color: '#444',
                              lineHeight: 1.5,
                            }} data-testid={`manager-comment-${o.order_id}`}>
                              <div style={{fontSize: '10px', color: '#999', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px'}}>Від менеджера</div>
                              {o.manager_comment}
                            </div>
                          )}
                        </div>

                        {/* Права частина: сума + шеврон */}
                        <div style={{textAlign: 'right', display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px'}}>
                          <div style={{fontSize: '20px', fontWeight: '600', color: '#1a1a1a', letterSpacing: '-0.01em'}}>
                            ₴{(o.total_to_pay || o.total_price || 0).toFixed(2)}
                          </div>
                          {(o.discount_amount > 0 || o.service_fee > 0) && (
                            <div style={{fontSize: '10px', color: '#999'}}>
                              {o.discount_amount > 0 && <>−₴{o.discount_amount.toFixed(2)} </>}
                              {o.service_fee > 0 && <>+сервіс ₴{o.service_fee.toFixed(2)}</>}
                            </div>
                          )}
                          {o.deposit_amount > 0 && (
                            <div style={{fontSize: '11px', color: '#666'}}>
                              Завдаток ₴{o.deposit_amount.toFixed(2)}
                            </div>
                          )}
                          {o.paid_rent > 0 && (
                            <div style={{display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: '#0a3d2e', fontWeight: '600'}} data-testid={`paid-rent-${o.order_id}`}>
                              <Check size={11} strokeWidth={2}/>Сплачено ₴{o.paid_rent.toFixed(2)}
                            </div>
                          )}
                          {/* Шеврон для розгортання */}
                          <ChevronDown
                            size={20}
                            strokeWidth={1.25}
                            style={{
                              color: '#999',
                              transition: 'transform 0.2s ease',
                              transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
                              marginTop: '8px',
                            }}
                            data-testid={`order-expand-chevron-${o.order_id}`}
                          />
                        </div>
                      </div>

                      {/* Розгорнутий блок: ПОЗИЦІЇ + ДОКУМЕНТИ */}
                      {expanded && (
                        <div
                          data-testid={`order-expanded-${o.order_id}`}
                          style={{marginTop: '20px', paddingTop: '20px', borderTop: '1px solid #ececec'}}
                        >
                          {/* Секція ПОЗИЦІЇ */}
                          <div style={{marginBottom: '24px'}}>
                            <div style={{fontSize: '10px', fontWeight: '600', color: '#666', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '12px'}}>
                              Позиції замовлення
                            </div>
                            {!orderDetailsCache[o.order_id] ? (
                              <div style={{fontSize: '12px', color: '#999'}}>Завантаження...</div>
                            ) : (orderDetailsCache[o.order_id].items || []).length === 0 ? (
                              <div style={{fontSize: '12px', color: '#999', fontStyle: 'italic'}}>
                                Позицій ще не оформлено
                              </div>
                            ) : (
                              <>
                                <div style={{display: 'flex', flexDirection: 'column'}}>
                                  {(orderDetailsCache[o.order_id].items || []).map((it, idx) => (
                                    <div key={idx} style={{
                                      display: 'flex',
                                      gap: '12px',
                                      padding: '12px 0',
                                      borderTop: idx === 0 ? '1px solid #ececec' : 'none',
                                      borderBottom: '1px solid #ececec',
                                      alignItems: 'flex-start',
                                    }}>
                                      <div style={{
                                        width: '56px', height: '56px',
                                        background: '#fafafa', overflow: 'hidden', flexShrink: 0,
                                        border: '1px solid #eee',
                                      }}>
                                        {it.image_url ? (
                                          <img
                                            src={
                                              it.image_url.startsWith('http') || it.image_url.startsWith('data:')
                                                ? it.image_url
                                                : `${process.env.REACT_APP_BACKEND_URL || ''}/${it.image_url.replace(/^\/+/, '')}`
                                            }
                                            alt={it.product_name}
                                            onError={(e) => { e.target.style.display = 'none'; }}
                                            style={{width: '100%', height: '100%', objectFit: 'cover'}}
                                          />
                                        ) : (
                                          <div style={{width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ccc'}}>
                                            <Package size={20} strokeWidth={1}/>
                                          </div>
                                        )}
                                      </div>
                                      <div style={{flex: 1, minWidth: 0}}>
                                        <div style={{fontWeight: '500', color: '#1a1a1a', fontSize: '13px', lineHeight: 1.3}}>
                                          {it.product_name}
                                        </div>
                                        <div style={{fontSize: '11px', color: '#999', marginTop: '2px'}}>
                                          {it.sku && <>Арт. <span style={{color: '#666', fontFamily: 'monospace'}}>{it.sku}</span></>}
                                          {(it.color || it.material) && it.sku && <span> · </span>}
                                          {it.color && <>{it.color}</>}
                                          {it.color && it.material && <span> · </span>}
                                          {it.material && <>{it.material}</>}
                                        </div>
                                        <div style={{fontSize: '11px', color: '#666', marginTop: '6px', display: 'flex', gap: '14px', flexWrap: 'wrap'}}>
                                          <span>× <strong style={{color: '#1a1a1a'}}>{it.quantity}</strong> шт</span>
                                          <span>₴{(it.price_per_day || 0).toFixed(2)} / добу</span>
                                          {it.deposit_per_unit > 0 && (
                                            <span style={{color: '#999'}}>застава ₴{it.deposit_per_unit.toFixed(2)} / шт</span>
                                          )}
                                        </div>
                                      </div>
                                      <div style={{textAlign: 'right', flexShrink: 0}}>
                                        <div style={{fontSize: '13px', fontWeight: '600', color: '#1a1a1a'}}>
                                          ₴{(it.total_rental || 0).toFixed(2)}
                                        </div>
                                        {it.total_deposit > 0 && (
                                          <div style={{fontSize: '10px', color: '#999', marginTop: '2px'}}>
                                            +₴{it.total_deposit.toFixed(2)} застава
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  ))}
                                </div>
                                {/* Підсумкова панель — кошториса */}
                                <div style={{
                                  marginTop: '14px', padding: '14px',
                                  background: '#fafafa', border: '1px solid #ececec',
                                }}>
                                  <div style={{display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#666', marginBottom: '4px'}}>
                                    <span>Оренда</span>
                                    <span>₴{((o.total_price || 0)).toFixed(2)}</span>
                                  </div>
                                  {o.discount_amount > 0 && (
                                    <div style={{display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#666', marginBottom: '4px'}}>
                                      <span>Знижка</span>
                                      <span>−₴{o.discount_amount.toFixed(2)}</span>
                                    </div>
                                  )}
                                  {o.service_fee > 0 && (
                                    <div style={{display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#666', marginBottom: '4px'}}>
                                      <span>Сервісний збір</span>
                                      <span>+₴{o.service_fee.toFixed(2)}</span>
                                    </div>
                                  )}
                                  <div style={{display: 'flex', justifyContent: 'space-between', fontSize: '13px', fontWeight: '600', color: '#1a1a1a', marginTop: '8px', paddingTop: '8px', borderTop: '1px solid #ddd'}}>
                                    <span>До сплати</span>
                                    <span>₴{(o.total_to_pay || o.total_price || 0).toFixed(2)}</span>
                                  </div>
                                  {o.deposit_amount > 0 && (
                                    <div style={{display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#999', marginTop: '4px'}}>
                                      <span>Завдаток (повернеться)</span>
                                      <span>₴{o.deposit_amount.toFixed(2)}</span>
                                    </div>
                                  )}
                                </div>
                                <div style={{display: 'flex', alignItems: 'flex-start', gap: '6px', marginTop: '10px', fontSize: '11px', color: '#999', lineHeight: 1.5}}>
                                  <Info size={12} strokeWidth={1.5} style={{flexShrink: 0, marginTop: '1px'}}/>
                                  <span>Кількість діб оренди фіксує менеджер за фактом видачі / повернення.</span>
                                </div>
                              </>
                            )}
                          </div>

                          {/* Секція ДОКУМЕНТИ */}
                          <div style={{marginBottom: '24px'}}>
                            <div style={{fontSize: '10px', fontWeight: '600', color: '#666', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '12px'}}>
                              Документи
                            </div>
                            {docs.length === 0 ? (
                              <div style={{fontSize: '12px', color: '#999', fontStyle: 'italic'}}>
                                Документи ще не сформовано
                              </div>
                            ) : (
                              <div style={{display: 'flex', flexDirection: 'column'}}>
                                {docs.map((d, dIdx) => (
                                  <div
                                    key={d.id}
                                    style={{
                                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                      padding: '12px 0',
                                      borderTop: dIdx === 0 ? '1px solid #ececec' : 'none',
                                      borderBottom: '1px solid #ececec',
                                      gap: '12px', flexWrap: 'wrap',
                                    }}
                                  >
                                    <div style={{flex: 1, minWidth: '150px'}}>
                                      <div style={{display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap'}}>
                                        <FileText size={14} strokeWidth={1.5} style={{color: '#666', flexShrink: 0}}/>
                                        <span style={{fontWeight: '500', fontSize: '13px', color: '#1a1a1a'}}>
                                          {d.doc_type_label}
                                          {d.doc_number ? ` №${d.doc_number}` : ''}
                                        </span>
                                        {d.needs_client_signature && (
                                          <span style={{fontSize: '9px', padding: '2px 6px', border: '1px solid #dc2626', color: '#dc2626', borderRadius: '2px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.05em'}}>
                                            Потребує підпису
                                          </span>
                                        )}
                                        {d.status === 'signed' && (
                                          <span style={{display: 'inline-flex', alignItems: 'center', gap: '3px', fontSize: '9px', padding: '2px 6px', border: '1px solid #0a3d2e', color: '#0a3d2e', borderRadius: '2px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.05em'}}>
                                            <Check size={9} strokeWidth={2.5}/>Підписано
                                          </span>
                                        )}
                                        {d.is_signable && d.tenant_signed && !d.landlord_signed && (
                                          <span style={{display: 'inline-flex', alignItems: 'center', gap: '3px', fontSize: '9px', padding: '2px 6px', border: '1px solid #b58a00', color: '#b58a00', borderRadius: '2px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.05em'}}>
                                            <Clock size={9} strokeWidth={1.5}/>Очікує менеджера
                                          </span>
                                        )}
                                      </div>
                                      <div style={{fontSize: '10px', color: '#999', marginTop: '4px', marginLeft: '20px'}}>
                                        {formatDate(d.created_at)}
                                      </div>
                                    </div>
                                    <div style={{display: 'flex', gap: '6px', flexWrap: 'wrap'}}>
                                      <a
                                        href={d.preview_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        style={{
                                          padding: '5px 10px', background: 'transparent',
                                          color: '#1a1a1a', border: '1px solid #1a1a1a',
                                          borderRadius: '2px', fontSize: '11px', fontWeight: '500',
                                          textDecoration: 'none', textTransform: 'uppercase', letterSpacing: '0.05em',
                                        }}
                                      >
                                        Переглянути
                                      </a>
                                      <a
                                        href={d.pdf_url}
                                        style={{
                                          padding: '5px 10px', background: '#1a1a1a',
                                          color: '#fff', border: '1px solid #1a1a1a',
                                          borderRadius: '2px', fontSize: '11px', fontWeight: '500',
                                          textDecoration: 'none', textTransform: 'uppercase', letterSpacing: '0.05em',
                                        }}
                                      >
                                        PDF
                                      </a>
                                      {d.needs_client_signature && (
                                        <button
                                          onClick={() => setSigningDoc({orderId: o.order_id, document: d})}
                                          data-testid={`sign-doc-btn-${d.id}`}
                                          style={{
                                            display: 'inline-flex', alignItems: 'center', gap: '4px',
                                            padding: '5px 10px', background: '#dc2626', color: '#fff',
                                            border: '1px solid #dc2626', borderRadius: '2px',
                                            fontSize: '11px', fontWeight: '600', cursor: 'pointer',
                                            textTransform: 'uppercase', letterSpacing: '0.05em',
                                          }}
                                        >
                                          <PenLine size={11} strokeWidth={1.5}/>Підписати
                                        </button>
                                      )}
                                      {/* Inline-погодження кошторису */}
                                      {(['estimate', 'invoice_offer', 'quote', 'preliminary_estimate'].includes(d.doc_type)
                                        || (d.category || '') === 'quote')
                                        && d.status !== 'approved' && d.status !== 'signed'
                                        && !d.tenant_signed && (
                                        <button
                                          data-testid={`approve-estimate-btn-${d.id}`}
                                          onClick={async () => {
                                            if (!window.confirm(`Погодити кошторис ${d.doc_number || ''}?`)) return;
                                            try {
                                              await documentApprovalAPI.approve(o.order_id, d.id);
                                              const detail = await ordersApi.get(o.order_id);
                                              setOrderDetailsCache(prev => ({...prev, [o.order_id]: detail}));
                                            } catch (e) {
                                              alert(e?.response?.data?.detail || 'Не вдалося погодити');
                                            }
                                          }}
                                          style={{
                                            display: 'inline-flex', alignItems: 'center', gap: '4px',
                                            padding: '5px 10px', background: '#0a3d2e', color: '#fff',
                                            border: '1px solid #0a3d2e', borderRadius: '2px',
                                            fontSize: '11px', fontWeight: '600', cursor: 'pointer',
                                            textTransform: 'uppercase', letterSpacing: '0.05em',
                                          }}
                                        >
                                          <Check size={11} strokeWidth={2.5}/>Погодити
                                        </button>
                                      )}
                                      {d.status === 'approved' && (
                                        <span style={{
                                          display: 'inline-flex', alignItems: 'center', gap: '3px',
                                          fontSize: '10px', padding: '4px 8px',
                                          background: '#e8f5e9', color: '#0a3d2e',
                                          borderRadius: '2px', fontWeight: '600',
                                          textTransform: 'uppercase', letterSpacing: '0.05em',
                                        }}>
                                          <Check size={10} strokeWidth={2.5}/>Погоджено
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>

                          {/* Секція ЧАТ з менеджером */}
                          <div style={{ marginTop: '24px', marginBottom: '24px' }}>
                            <div style={{
                              fontSize: '10px', fontWeight: '600', color: '#666',
                              textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '12px',
                            }}>
                              Чат з менеджером
                            </div>
                            <OrderChat orderId={o.order_id} orderNumber={o.order_number} />
                          </div>

                          {/* Секція ІСТОРІЯ ЗМІН */}
                          {(timelineCache[o.order_id] || []).length > 0 && (
                            <div>
                              <div style={{fontSize: '10px', fontWeight: '600', color: '#666', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '12px'}}>
                                Історія змін
                              </div>
                              <div style={{display: 'flex', flexDirection: 'column'}}>
                                {timelineCache[o.order_id].map((ev, evIdx) => (
                                  <div key={evIdx} style={{
                                    display: 'flex', gap: '12px', padding: '10px 0',
                                    borderTop: evIdx === 0 ? '1px solid #ececec' : 'none',
                                    borderBottom: '1px solid #ececec',
                                  }}>
                                    {/* Маркер крапки */}
                                    <div style={{flexShrink: 0, marginTop: '6px'}}>
                                      <div style={{
                                        width: '6px', height: '6px',
                                        borderRadius: '50%',
                                        background: '#0a3d2e',
                                      }}/>
                                    </div>
                                    <div style={{flex: 1, minWidth: 0}}>
                                      <div style={{fontSize: '12px', fontWeight: '500', color: '#1a1a1a'}}>
                                        {ev.stage_label}
                                      </div>
                                      {ev.notes && (
                                        <div style={{fontSize: '11px', color: '#666', marginTop: '2px', lineHeight: 1.5}}>
                                          {ev.notes}
                                        </div>
                                      )}
                                      <div style={{fontSize: '10px', color: '#999', marginTop: '4px', textTransform: 'uppercase', letterSpacing: '0.05em'}}>
                                        {ev.actor} · {formatDate(ev.created_at)}
                                      </div>
                                    </div>
                                  </div>
                                ))}
                              </div>
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
                        {formatDate(board.event_date)}
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

        {/* Обране */}
        {activeTab === 'favorites' && (
        <div data-testid="profile-favorites-section">
          <div className="mb-6">
            <h3 style={{fontSize: '20px', fontWeight: '600', color: '#333'}}>
              Обрані товари
            </h3>
          </div>

          {favLoading ? (
            <div className="text-center py-12" style={{color: '#999'}}>Завантаження...</div>
          ) : favProducts.length === 0 ? (
            <div style={{
              background: '#fff', borderRadius: '8px', padding: '64px', textAlign: 'center'
            }}>
              <div style={{fontSize: '48px', marginBottom: '16px'}}>♡</div>
              <p style={{fontSize: '16px', color: '#333', marginBottom: '8px'}}>
                Ще немає обраних товарів
              </p>
              <p style={{fontSize: '14px', color: '#999', marginBottom: '24px'}}>
                Натискайте ♡ на картках каталогу, щоб зберегти товари тут
              </p>
              <button
                onClick={() => navigate('/')}
                className="fd-btn fd-btn-black"
                data-testid="profile-fav-browse-btn"
              >
                Перейти до каталогу
              </button>
            </div>
          ) : (
            <div
              className="product-grid"
              data-testid="profile-favorites-grid"
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
                gap: 16,
              }}
            >
              {favProducts.map((p) => (
                <ProductCard
                  key={p.product_id}
                  product={p}
                  onAddToBoard={() => setAddToBoardProduct(p)}
                  boardDates={{}}
                  onOpenDetails={null}
                />
              ))}
            </div>
          )}
        </div>
        )}
      </div>

      {/* Модалка "Додати в проєкт" */}
      {addToBoardProduct && (
        <AddToBoardModal
          product={addToBoardProduct}
          onClose={() => setAddToBoardProduct(null)}
          onAdded={(board) => {
            // Refresh boards count
            api.get('/event/boards').then((r) => {
              setBoards(Array.isArray(r.data) ? r.data : (r.data?.boards || []));
            }).catch(() => {});
          }}
        />
      )}

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
