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
import SignMasterAgreementModal from './SignMasterAgreementModal';
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

// Helpers для форми Профілю
const inputStyle = {
  width: '100%',
  padding: '10px 12px',
  border: '1px solid #d4cab8',
  borderRadius: 8,
  fontSize: 14,
  background: '#fffdf7',
  color: '#0a3d2e',
  outline: 'none',
  boxSizing: 'border-box',
};
const inputStyleLocked = {
  ...inputStyle,
  background: '#f1f5f9',
  color: '#64748b',
  cursor: 'not-allowed',
};
const Field = ({ label, children }) => (
  <div>
    <label style={{
      display: 'block', fontSize: 11, color: '#94a3b8',
      textTransform: 'uppercase', letterSpacing: '0.6px',
      marginBottom: 4, fontWeight: 600,
    }}>{label}</label>
    {children}
  </div>
);

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
  // Документи (Cabinet 2.0)
  const [docsList, setDocsList] = useState([]);
  const [docsLoading, setDocsLoading] = useState(false);
  // Профіль (Cabinet 2.0)
  const [profileData, setProfileData] = useState(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMsg, setProfileMsg] = useState('');
  // Платники (Cabinet 2.0)
  const [payersList, setPayersList] = useState([]);
  const [payersLoading, setPayersLoading] = useState(false);
  const [payersMsg, setPayersMsg] = useState('');
  const [payerEdit, setPayerEdit] = useState(null); // {id?, payer_type, company_name, ...} — null=closed, {}=new
  const [payerSaving, setPayerSaving] = useState(false);
  // Master Agreement (Cabinet 2.0)
  const [agreement, setAgreement] = useState(null);
  const [agreementLoading, setAgreementLoading] = useState(false);
  const [agreementMsg, setAgreementMsg] = useState('');
  const [signingAgreement, setSigningAgreement] = useState(false);

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

  // Завантажуємо документи коли заходимо на вкладку
  useEffect(() => {
    if (activeTab !== 'documents') return;
    setDocsLoading(true);
    api.get('/event/cabinet/documents')
      .then((r) => setDocsList(r.data?.documents || []))
      .catch(() => setDocsList([]))
      .finally(() => setDocsLoading(false));
  }, [activeTab]);

  // Завантажуємо профіль
  useEffect(() => {
    if (activeTab !== 'profile') return;
    setProfileLoading(true);
    api.get('/event/cabinet/profile')
      .then((r) => setProfileData(r.data))
      .catch((e) => setProfileMsg(`Помилка: ${e?.response?.data?.detail || e.message}`))
      .finally(() => setProfileLoading(false));
  }, [activeTab]);

  const saveProfile = async () => {
    if (!profileData) return;
    setProfileSaving(true);
    setProfileMsg('');
    try {
      const payload = {
        full_name: profileData.full_name,
        phone: profileData.phone,
        payer_type: profileData.payer_type,
        tax_id: profileData.tax_id,
        bank_details: profileData.bank_details,
        company: profileData.company,
        instagram: profileData.instagram,
        preferred_contact: profileData.preferred_contact,
      };
      await api.put('/event/cabinet/profile', payload);
      setProfileMsg('Профіль збережено');
      setTimeout(() => setProfileMsg(''), 3000);
    } catch (e) {
      setProfileMsg(`Помилка: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setProfileSaving(false);
    }
  };

  // ===== Платники (Cabinet 2.0) =====
  const loadPayers = async () => {
    setPayersLoading(true);
    try {
      const r = await api.get('/event/cabinet/payers');
      setPayersList(r.data?.payers || []);
    } catch (e) {
      setPayersMsg(`Помилка: ${e?.response?.data?.detail || e.message}`);
      setPayersList([]);
    } finally {
      setPayersLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab !== 'payers') return;
    loadPayers();
  }, [activeTab]);

  const startNewPayer = () => {
    setPayerEdit({
      payer_type: 'fop',
      company_name: '',
      edrpou: '',
      iban: '',
      bank_name: '',
      director_name: '',
      address: '',
      phone: '',
      email: '',
    });
    setPayersMsg('');
  };

  const savePayer = async () => {
    if (!payerEdit) return;
    if (!payerEdit.company_name || !payerEdit.company_name.trim()) {
      setPayersMsg('Помилка: вкажіть назву платника');
      return;
    }
    setPayerSaving(true);
    setPayersMsg('');
    try {
      const payload = {
        payer_type: payerEdit.payer_type || 'fop',
        company_name: payerEdit.company_name,
        edrpou: payerEdit.edrpou || null,
        iban: payerEdit.iban || null,
        bank_name: payerEdit.bank_name || null,
        director_name: payerEdit.director_name || null,
        address: payerEdit.address || null,
        phone: payerEdit.phone || null,
        email: payerEdit.email || null,
      };
      if (payerEdit.id) {
        await api.put(`/event/cabinet/payers/${payerEdit.id}`, payload);
        setPayersMsg('Платника оновлено');
      } else {
        await api.post('/event/cabinet/payers', payload);
        setPayersMsg('Платника додано');
      }
      setPayerEdit(null);
      await loadPayers();
      setTimeout(() => setPayersMsg(''), 3000);
    } catch (e) {
      setPayersMsg(`Помилка: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setPayerSaving(false);
    }
  };

  const setDefaultPayer = async (id) => {
    try {
      await api.put(`/event/cabinet/payers/${id}/default`);
      await loadPayers();
      setPayersMsg('Призначено основним');
      setTimeout(() => setPayersMsg(''), 2500);
    } catch (e) {
      setPayersMsg(`Помилка: ${e?.response?.data?.detail || e.message}`);
    }
  };

  const deletePayer = async (id) => {
    if (!window.confirm('Відв\'язати цього платника від профілю?')) return;
    try {
      await api.delete(`/event/cabinet/payers/${id}`);
      await loadPayers();
      setPayersMsg('Платника відв\'язано');
      setTimeout(() => setPayersMsg(''), 2500);
    } catch (e) {
      setPayersMsg(`Помилка: ${e?.response?.data?.detail || e.message}`);
    }
  };

  // ===== Master Agreement (Cabinet 2.0) =====
  const loadAgreement = async () => {
    setAgreementLoading(true);
    setAgreementMsg('');
    try {
      const r = await api.get('/event/cabinet/master-agreement');
      setAgreement(r.data);
    } catch (e) {
      setAgreementMsg(`Помилка: ${e?.response?.data?.detail || e.message}`);
      setAgreement(null);
    } finally {
      setAgreementLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab !== 'agreement') return;
    loadAgreement();
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
        <div
          style={{
            display: 'flex', gap: '4px', borderBottom: '1px solid #e0e0e0',
            marginBottom: '24px', overflowX: 'auto', whiteSpace: 'nowrap',
            WebkitOverflowScrolling: 'touch',
          }}
        >
          {[
            {key: 'orders', label: `Мої замовлення (${orders.length})`},
            {key: 'boards', label: `Мої мудборди (${boards.length})`},
            {key: 'favorites', label: `Обране (${favoriteIds.length})`},
            {key: 'documents', label: 'Документи'},
            {key: 'agreement', label: 'Договір'},
            {key: 'payers', label: 'Платники'},
            {key: 'profile', label: 'Профіль'},
          ].map(t => (
            <button
              key={t.key}
              data-testid={`profile-tab-${t.key}`}
              onClick={() => setActiveTab(t.key)}
              style={{
                padding: '12px 18px',
                background: 'transparent',
                border: 'none',
                borderBottom: activeTab === t.key ? '2px solid #0a3d2e' : '2px solid transparent',
                fontWeight: activeTab === t.key ? '600' : '400',
                color: activeTab === t.key ? '#0a3d2e' : '#666',
                cursor: 'pointer',
                fontSize: '14px',
                marginBottom: '-1px',
                flexShrink: 0,
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

        {/* Документи */}
        {activeTab === 'documents' && (
          <div data-testid="profile-documents-section">
            <div className="mb-6">
              <h3 style={{fontSize: '20px', fontWeight: '600', color: '#333'}}>
                Документи
              </h3>
              <p style={{fontSize: '13px', color: '#666', marginTop: 4}}>
                Усі документи з ваших замовлень: кошториси, рахунки, акти, договори.
              </p>
            </div>

            {docsLoading ? (
              <div className="text-center py-12" style={{color: '#999'}}>Завантаження...</div>
            ) : docsList.length === 0 ? (
              <div style={{background: '#fff', borderRadius: '8px', padding: '48px', textAlign: 'center', border: '1px solid #f0f0f0'}}>
                <p style={{fontSize: '15px', color: '#333', marginBottom: 4}}>Поки що немає документів</p>
                <p style={{fontSize: '13px', color: '#999'}}>Документи з'являться тут після оформлення замовлення</p>
              </div>
            ) : (
              <div data-testid="profile-documents-list" style={{display: 'grid', gridTemplateColumns: '1fr', gap: 10}}>
                {(() => {
                  // Групуємо за замовленням
                  const byOrder = {};
                  docsList.forEach(d => {
                    const k = d.order_id;
                    if (!byOrder[k]) byOrder[k] = { order_number: d.order_number, event_date: d.event_date, docs: [] };
                    byOrder[k].docs.push(d);
                  });
                  return Object.entries(byOrder).map(([oid, grp]) => (
                    <div key={oid} style={{
                      background: '#fff', border: '1px solid #e5e7eb', borderRadius: 10, padding: 14,
                    }}>
                      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10, flexWrap: 'wrap', gap: 8}}>
                        <div style={{fontWeight: 600, color: '#0a3d2e', fontSize: 14}}>
                          Замовлення № {grp.order_number}
                        </div>
                        {grp.event_date && (
                          <div style={{color: '#94a3b8', fontSize: 12}}>
                            Подія: {new Date(grp.event_date).toLocaleDateString('uk-UA')}
                          </div>
                        )}
                      </div>
                      <div style={{display: 'flex', flexDirection: 'column', gap: 6}}>
                        {grp.docs.map(d => {
                          const url = `${process.env.REACT_APP_BACKEND_URL || ''}/api/event/cabinet/documents/${d.id}/view?token=${encodeURIComponent(localStorage.getItem('access_token') || '')}`;
                          return (
                            <a
                              key={d.id}
                              href={url}
                              target="_blank"
                              rel="noopener noreferrer"
                              data-testid={`doc-link-${d.id}`}
                              style={{
                                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                padding: '10px 12px', background: '#f8fafc', borderRadius: 8,
                                textDecoration: 'none', color: '#0f172a', border: '1px solid #f0f0f0',
                                gap: 12, flexWrap: 'wrap',
                              }}
                            >
                              <span style={{fontWeight: 500, fontSize: 14, flex: '1 1 60%', minWidth: 200}}>
                                {d.doc_type_label}
                                {d.doc_number ? <span style={{color: '#94a3b8', fontWeight: 400, marginLeft: 6}}>№ {d.doc_number}</span> : null}
                                {d.version > 1 ? <span style={{color: '#b08d2e', fontSize: 11, marginLeft: 6}}>v{d.version}</span> : null}
                              </span>
                              <span style={{fontSize: 12, color: '#64748b'}}>
                                {d.created_at ? new Date(d.created_at).toLocaleDateString('uk-UA') : ''}
                              </span>
                              <span style={{
                                fontSize: 12, padding: '4px 10px',
                                background: d.status === 'signed' ? '#dcfce7' : '#fef3c7',
                                color: d.status === 'signed' ? '#166534' : '#92400e',
                                borderRadius: 12, fontWeight: 600,
                              }}>
                                {d.status === 'signed' ? 'Підписано' : d.status === 'draft' ? 'Чернетка' : d.status}
                              </span>
                            </a>
                          );
                        })}
                      </div>
                    </div>
                  ));
                })()}
              </div>
            )}
          </div>
        )}

        {/* Договір (Master Agreement) */}
        {activeTab === 'agreement' && (
          <div data-testid="profile-agreement-section">
            <div className="mb-6">
              <h3 style={{fontSize: '20px', fontWeight: '600', color: '#333'}}>Річний договір</h3>
              <p style={{fontSize: '13px', color: '#666', marginTop: 4}}>
                Рамковий договір оренди підписується один раз на рік. Усі окремі замовлення оформлюються як додатки до цього договору.
              </p>
            </div>

            {agreementMsg && (
              <div data-testid="agreement-msg" style={{
                padding: '10px 14px', marginBottom: 14, borderRadius: 8,
                background: agreementMsg.startsWith('Помилка') ? '#fee2e2' : '#dcfce7',
                color: agreementMsg.startsWith('Помилка') ? '#991b1b' : '#166534',
                fontSize: 13,
              }}>{agreementMsg}</div>
            )}

            {agreementLoading || !agreement ? (
              <div className="text-center py-12" style={{color: '#999'}}>Завантаження...</div>
            ) : (() => {
              const isSigned = agreement.status === 'signed' && !agreement.needs_signature;
              const validUntil = agreement.valid_until ? new Date(agreement.valid_until) : null;
              const validUntilStr = validUntil ? validUntil.toLocaleDateString('uk-UA') : '—';
              const signedAtStr = agreement.signed_at ? new Date(agreement.signed_at).toLocaleDateString('uk-UA') : null;
              const previewUrl = `${process.env.REACT_APP_BACKEND_URL || ''}/api/event/cabinet/master-agreement/view?token=${encodeURIComponent(localStorage.getItem('access_token') || '')}`;
              return (
                <div data-testid="agreement-card" style={{
                  background: '#fff', border: isSigned ? '2px solid #0a3d2e' : '1px solid #fbbf24',
                  borderRadius: 10, padding: 20, maxWidth: 720,
                }}>
                  <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap', marginBottom: 14}}>
                    <div>
                      <div style={{fontSize: 11, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 4}}>
                        Договір №
                      </div>
                      <div style={{fontSize: 18, fontWeight: 600, color: '#0a3d2e'}} data-testid="agreement-number">
                        {agreement.contract_number || '—'}
                      </div>
                    </div>
                    <div data-testid="agreement-status-badge" style={{
                      padding: '6px 14px', borderRadius: 14, fontSize: 12, fontWeight: 600,
                      background: isSigned ? '#dcfce7' : '#fef3c7',
                      color: isSigned ? '#166534' : '#92400e',
                    }}>
                      {isSigned ? '✓ Підписано' : 'Очікує підпису'}
                    </div>
                  </div>

                  <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 14, marginBottom: 18}}>
                    <div>
                      <div style={{fontSize: 11, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 4}}>
                        Дійсний до
                      </div>
                      <div style={{fontSize: 14, color: '#0f172a', fontWeight: 500}} data-testid="agreement-valid-until">
                        {validUntilStr}
                      </div>
                    </div>
                    {signedAtStr && (
                      <div>
                        <div style={{fontSize: 11, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 4}}>
                          Підписано
                        </div>
                        <div style={{fontSize: 14, color: '#0f172a', fontWeight: 500}} data-testid="agreement-signed-at">
                          {signedAtStr}
                        </div>
                      </div>
                    )}
                  </div>

                  {!isSigned && (
                    <div style={{
                      padding: 12, background: '#fef3c7', border: '1px solid #fbbf24',
                      borderRadius: 8, fontSize: 13, color: '#92400e', marginBottom: 14, lineHeight: 1.5,
                    }}>
                      <strong>Увага:</strong> без підписаного річного договору ви не зможете оформити замовлення. Будь ласка, перегляньте умови та підпишіть.
                    </div>
                  )}

                  <div style={{display: 'flex', gap: 10, flexWrap: 'wrap'}}>
                    <a
                      href={previewUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      data-testid="agreement-preview-btn"
                      style={{
                        padding: '10px 20px', background: 'transparent',
                        border: '1px solid #d4cab8', borderRadius: 8, color: '#0a3d2e',
                        cursor: 'pointer', fontSize: 13, textDecoration: 'none',
                        display: 'inline-flex', alignItems: 'center',
                      }}
                    >
                      Переглянути договір
                    </a>
                    {!isSigned && (
                      <button
                        onClick={() => setSigningAgreement(true)}
                        data-testid="agreement-sign-btn"
                        className="fd-btn fd-btn-black"
                        style={{padding: '10px 24px', fontSize: 13}}
                      >
                        Підписати договір
                      </button>
                    )}
                  </div>
                </div>
              );
            })()}
          </div>
        )}

        {/* Платники */}
        {activeTab === 'payers' && (
          <div data-testid="profile-payers-section">
            <div className="mb-6" style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', flexWrap: 'wrap', gap: 12}}>
              <div>
                <h3 style={{fontSize: '20px', fontWeight: '600', color: '#333'}}>Мої платники</h3>
                <p style={{fontSize: '13px', color: '#666', marginTop: 4}}>
                  Юридичні особи, ФОП або фізособи, від імені яких ви оформлюєте оренду. Один платник може бути основним — він буде підставлятися автоматично під час оформлення.
                </p>
              </div>
              {!payerEdit && (
                <button
                  onClick={startNewPayer}
                  data-testid="payer-new-btn"
                  className="fd-btn fd-btn-black"
                  style={{padding: '10px 18px', fontSize: 13}}
                >
                  + Додати платника
                </button>
              )}
            </div>

            {payersMsg && (
              <div data-testid="payers-msg" style={{
                padding: '10px 14px', marginBottom: 14, borderRadius: 8,
                background: payersMsg.startsWith('Помилка') ? '#fee2e2' : '#dcfce7',
                color: payersMsg.startsWith('Помилка') ? '#991b1b' : '#166534',
                fontSize: 13,
              }}>{payersMsg}</div>
            )}

            {/* Форма редагування / додавання */}
            {payerEdit && (
              <div data-testid="payer-edit-form" style={{
                background: '#fff', border: '1px solid #e5e7eb', borderRadius: 10,
                padding: 20, marginBottom: 18,
              }}>
                <div style={{fontWeight: 600, color: '#0a3d2e', marginBottom: 14, fontSize: 15}}>
                  {payerEdit.id ? 'Редагування платника' : 'Новий платник'}
                </div>
                <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12}}>
                  <Field label="Тип платника">
                    <select
                      value={payerEdit.payer_type || 'fop'}
                      onChange={(e) => setPayerEdit({...payerEdit, payer_type: e.target.value})}
                      data-testid="payer-type-input"
                      style={inputStyle}
                    >
                      <option value="individual">Фізична особа</option>
                      <option value="fop">ФОП</option>
                      <option value="fop_simple">ФОП спрощена</option>
                      <option value="tov">ТОВ</option>
                    </select>
                  </Field>
                  <Field label="Назва / ПІБ">
                    <input
                      type="text"
                      value={payerEdit.company_name || ''}
                      onChange={(e) => setPayerEdit({...payerEdit, company_name: e.target.value})}
                      data-testid="payer-name-input"
                      placeholder='Напр. "ФОП Іванов І.І."'
                      style={inputStyle}
                    />
                  </Field>
                  <Field label="ЄДРПОУ / ІПН">
                    <input
                      type="text"
                      value={payerEdit.edrpou || ''}
                      onChange={(e) => setPayerEdit({...payerEdit, edrpou: e.target.value})}
                      data-testid="payer-edrpou-input"
                      style={inputStyle}
                    />
                  </Field>
                  <Field label="Директор / підписант">
                    <input
                      type="text"
                      value={payerEdit.director_name || ''}
                      onChange={(e) => setPayerEdit({...payerEdit, director_name: e.target.value})}
                      data-testid="payer-director-input"
                      style={inputStyle}
                    />
                  </Field>
                  <Field label="Юридична адреса">
                    <input
                      type="text"
                      value={payerEdit.address || ''}
                      onChange={(e) => setPayerEdit({...payerEdit, address: e.target.value})}
                      data-testid="payer-address-input"
                      style={inputStyle}
                    />
                  </Field>
                  <Field label="Телефон">
                    <input
                      type="tel"
                      value={payerEdit.phone || ''}
                      onChange={(e) => setPayerEdit({...payerEdit, phone: e.target.value})}
                      data-testid="payer-phone-input"
                      style={inputStyle}
                    />
                  </Field>
                  <Field label="Email">
                    <input
                      type="email"
                      value={payerEdit.email || ''}
                      onChange={(e) => setPayerEdit({...payerEdit, email: e.target.value})}
                      data-testid="payer-email-input"
                      style={inputStyle}
                    />
                  </Field>
                  <Field label="IBAN">
                    <input
                      type="text"
                      value={payerEdit.iban || ''}
                      onChange={(e) => setPayerEdit({...payerEdit, iban: e.target.value})}
                      data-testid="payer-iban-input"
                      placeholder="UA12 ..."
                      style={inputStyle}
                    />
                  </Field>
                  <Field label="Назва банку">
                    <input
                      type="text"
                      value={payerEdit.bank_name || ''}
                      onChange={(e) => setPayerEdit({...payerEdit, bank_name: e.target.value})}
                      data-testid="payer-bank-input"
                      style={inputStyle}
                    />
                  </Field>
                </div>

                <div style={{marginTop: 18, display: 'flex', gap: 10, justifyContent: 'flex-end'}}>
                  <button
                    onClick={() => { setPayerEdit(null); setPayersMsg(''); }}
                    data-testid="payer-cancel-btn"
                    style={{
                      padding: '10px 22px', background: 'transparent',
                      border: '1px solid #d4cab8', borderRadius: 8, color: '#0a3d2e',
                      cursor: 'pointer', fontSize: 13,
                    }}
                  >
                    Скасувати
                  </button>
                  <button
                    onClick={savePayer}
                    disabled={payerSaving}
                    data-testid="payer-save-btn"
                    className="fd-btn fd-btn-black"
                    style={{padding: '10px 28px', opacity: payerSaving ? 0.6 : 1, fontSize: 13}}
                  >
                    {payerSaving ? 'Збереження...' : 'Зберегти'}
                  </button>
                </div>
              </div>
            )}

            {/* Список платників */}
            {payersLoading ? (
              <div className="text-center py-12" style={{color: '#999'}}>Завантаження...</div>
            ) : payersList.length === 0 && !payerEdit ? (
              <div style={{background: '#fff', borderRadius: 8, padding: 48, textAlign: 'center', border: '1px solid #f0f0f0'}}>
                <p style={{fontSize: '15px', color: '#333', marginBottom: 4}}>У вас ще немає платників</p>
                <p style={{fontSize: '13px', color: '#999'}}>Додайте ФОП або юр. особу, щоб менеджер міг готувати документи на правильні реквізити.</p>
              </div>
            ) : (
              <div data-testid="payers-list" style={{display: 'grid', gridTemplateColumns: '1fr', gap: 10}}>
                {payersList.map((p) => {
                  const typeLabel = {
                    individual: 'Фізична особа',
                    fop: 'ФОП',
                    fop_simple: 'ФОП спрощена',
                    tov: 'ТОВ',
                  }[p.payer_type] || p.payer_type;
                  return (
                    <div
                      key={p.id}
                      data-testid={`payer-card-${p.id}`}
                      style={{
                        background: '#fff', border: p.is_default ? '2px solid #0a3d2e' : '1px solid #e5e7eb',
                        borderRadius: 10, padding: 16,
                      }}
                    >
                      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap'}}>
                        <div style={{flex: '1 1 280px', minWidth: 0}}>
                          <div style={{display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap'}}>
                            <span style={{fontWeight: 600, color: '#0a3d2e', fontSize: 15}}>{p.company_name}</span>
                            <span style={{
                              fontSize: 11, padding: '3px 8px', background: '#f1f5f9',
                              color: '#475569', borderRadius: 12, fontWeight: 500,
                            }}>{typeLabel}</span>
                            {p.is_default ? (
                              <span data-testid={`payer-default-badge-${p.id}`} style={{
                                fontSize: 11, padding: '3px 8px', background: '#dcfce7',
                                color: '#166534', borderRadius: 12, fontWeight: 600,
                              }}>★ Основний</span>
                            ) : null}
                          </div>
                          <div style={{fontSize: 13, color: '#64748b', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '4px 16px'}}>
                            {p.edrpou && <div>ЄДРПОУ: <span style={{color: '#0f172a'}}>{p.edrpou}</span></div>}
                            {p.director_name && <div>Підписант: <span style={{color: '#0f172a'}}>{p.director_name}</span></div>}
                            {p.iban && <div>IBAN: <span style={{color: '#0f172a'}}>{p.iban}</span></div>}
                            {p.bank_name && <div>Банк: <span style={{color: '#0f172a'}}>{p.bank_name}</span></div>}
                            {p.phone && <div>Тел.: <span style={{color: '#0f172a'}}>{p.phone}</span></div>}
                            {p.email && <div>Email: <span style={{color: '#0f172a'}}>{p.email}</span></div>}
                          </div>
                        </div>
                        <div style={{display: 'flex', flexDirection: 'column', gap: 6, flex: '0 0 auto'}}>
                          {!p.is_default && (
                            <button
                              onClick={() => setDefaultPayer(p.id)}
                              data-testid={`payer-make-default-${p.id}`}
                              style={{
                                padding: '6px 12px', background: '#0a3d2e', color: '#fff',
                                border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 12,
                              }}
                            >
                              Зробити основним
                            </button>
                          )}
                          <button
                            onClick={() => { setPayerEdit({...p}); setPayersMsg(''); }}
                            data-testid={`payer-edit-${p.id}`}
                            style={{
                              padding: '6px 12px', background: 'transparent',
                              border: '1px solid #d4cab8', color: '#0a3d2e',
                              borderRadius: 6, cursor: 'pointer', fontSize: 12,
                            }}
                          >
                            Редагувати
                          </button>
                          <button
                            onClick={() => deletePayer(p.id)}
                            data-testid={`payer-delete-${p.id}`}
                            style={{
                              padding: '6px 12px', background: 'transparent',
                              border: '1px solid #fecaca', color: '#b91c1c',
                              borderRadius: 6, cursor: 'pointer', fontSize: 12,
                            }}
                          >
                            Відв'язати
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Профіль */}
        {activeTab === 'profile' && (
          <div data-testid="profile-edit-section">
            <div className="mb-6">
              <h3 style={{fontSize: '20px', fontWeight: '600', color: '#333'}}>Профіль</h3>
              <p style={{fontSize: '13px', color: '#666', marginTop: 4}}>
                Особисті дані та реквізити. Email змінити не можна (звертайтесь до менеджера).
              </p>
            </div>

            {profileLoading || !profileData ? (
              <div className="text-center py-12" style={{color: '#999'}}>Завантаження...</div>
            ) : (
              <div style={{
                background: '#fff', border: '1px solid #e5e7eb', borderRadius: 10,
                padding: 20, maxWidth: 720,
              }}>
                {profileMsg && (
                  <div data-testid="profile-msg" style={{
                    padding: '10px 14px', marginBottom: 14, borderRadius: 8,
                    background: profileMsg.startsWith('Помилка') ? '#fee2e2' : '#dcfce7',
                    color: profileMsg.startsWith('Помилка') ? '#991b1b' : '#166534',
                    fontSize: 13,
                  }}>{profileMsg}</div>
                )}

                <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 14}}>
                  {/* Email — read-only */}
                  <Field label="Email">
                    <input
                      type="email" value={profileData.email || ''} disabled
                      data-testid="profile-email-input"
                      style={inputStyleLocked}
                    />
                  </Field>
                  <Field label="ПІБ">
                    <input
                      type="text"
                      value={profileData.full_name || ''}
                      onChange={(e) => setProfileData({...profileData, full_name: e.target.value})}
                      data-testid="profile-fullname-input"
                      style={inputStyle}
                    />
                  </Field>
                  <Field label="Телефон">
                    <input
                      type="tel"
                      value={profileData.phone || ''}
                      onChange={(e) => setProfileData({...profileData, phone: e.target.value})}
                      data-testid="profile-phone-input"
                      style={inputStyle}
                    />
                  </Field>
                  <Field label="Тип платника">
                    <select
                      value={profileData.payer_type || 'individual'}
                      onChange={(e) => setProfileData({...profileData, payer_type: e.target.value})}
                      data-testid="profile-payer-type"
                      style={inputStyle}
                    >
                      <option value="individual">Фізична особа</option>
                      <option value="fop">ФОП</option>
                      <option value="fop_simple">ФОП спрощена</option>
                      <option value="tov">ТОВ</option>
                    </select>
                  </Field>
                  {profileData.payer_type !== 'individual' && (
                    <>
                      <Field label="ЕДРПОУ / ІПН">
                        <input
                          type="text"
                          value={profileData.tax_id || ''}
                          onChange={(e) => setProfileData({...profileData, tax_id: e.target.value})}
                          data-testid="profile-taxid-input"
                          style={inputStyle}
                        />
                      </Field>
                      <Field label="Компанія">
                        <input
                          type="text"
                          value={profileData.company || ''}
                          onChange={(e) => setProfileData({...profileData, company: e.target.value})}
                          data-testid="profile-company-input"
                          style={inputStyle}
                        />
                      </Field>
                    </>
                  )}
                  <Field label="Instagram">
                    <input
                      type="text" placeholder="@username"
                      value={profileData.instagram || ''}
                      onChange={(e) => setProfileData({...profileData, instagram: e.target.value})}
                      data-testid="profile-instagram-input"
                      style={inputStyle}
                    />
                  </Field>
                  <Field label="Бажаний контакт">
                    <select
                      value={profileData.preferred_contact || ''}
                      onChange={(e) => setProfileData({...profileData, preferred_contact: e.target.value})}
                      data-testid="profile-preferred-contact"
                      style={inputStyle}
                    >
                      <option value="">Не вказано</option>
                      <option value="phone">Телефон</option>
                      <option value="viber">Viber</option>
                      <option value="telegram">Telegram</option>
                      <option value="instagram">Instagram</option>
                      <option value="email">Email</option>
                    </select>
                  </Field>
                </div>

                {profileData.payer_type !== 'individual' && (
                  <div style={{marginTop: 16, padding: 14, background: '#f8fafc', borderRadius: 8}}>
                    <div style={{fontSize: 13, fontWeight: 600, color: '#0a3d2e', marginBottom: 10}}>Банківські реквізити</div>
                    <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10}}>
                      <Field label="IBAN">
                        <input type="text" placeholder="UA12 ..."
                          value={(profileData.bank_details && profileData.bank_details.iban) || ''}
                          onChange={(e) => setProfileData({...profileData, bank_details: {...(profileData.bank_details || {}), iban: e.target.value}})}
                          data-testid="profile-bank-iban"
                          style={inputStyle}
                        />
                      </Field>
                      <Field label="Банк">
                        <input type="text"
                          value={(profileData.bank_details && profileData.bank_details.bank) || ''}
                          onChange={(e) => setProfileData({...profileData, bank_details: {...(profileData.bank_details || {}), bank: e.target.value}})}
                          data-testid="profile-bank-name"
                          style={inputStyle}
                        />
                      </Field>
                      <Field label="МФО">
                        <input type="text"
                          value={(profileData.bank_details && profileData.bank_details.mfo) || ''}
                          onChange={(e) => setProfileData({...profileData, bank_details: {...(profileData.bank_details || {}), mfo: e.target.value}})}
                          data-testid="profile-bank-mfo"
                          style={inputStyle}
                        />
                      </Field>
                    </div>
                  </div>
                )}

                <div style={{marginTop: 20, display: 'flex', gap: 10, justifyContent: 'flex-end'}}>
                  <button
                    onClick={saveProfile}
                    disabled={profileSaving}
                    data-testid="profile-save-btn"
                    className="fd-btn fd-btn-black"
                    style={{padding: '12px 28px', opacity: profileSaving ? 0.6 : 1}}
                  >
                    {profileSaving ? 'Збереження...' : 'Зберегти'}
                  </button>
                </div>
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

      {/* Модалка підписання річного договору */}
      {signingAgreement && agreement && (
        <SignMasterAgreementModal
          agreement={agreement}
          user={user}
          onClose={() => setSigningAgreement(false)}
          onSigned={() => {
            setSigningAgreement(false);
            setAgreementMsg('Договір успішно підписано');
            setTimeout(() => setAgreementMsg(''), 3000);
            loadAgreement();
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
