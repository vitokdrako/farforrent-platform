/* eslint-disable */
import React, { useState, useEffect, useRef } from 'react';
import { X, MessageSquare, Send, Search, ChevronRight, ChevronLeft, ArrowLeft } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

// Utility function for authenticated fetch
const authFetch = (url, options = {}) => {
  const token = localStorage.getItem('token');
  return fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
};

// Статуси та їх кольори
const statusConfig = {
  awaiting_customer: { label: 'Очікує', color: 'bg-amber-500' },
  processing: { label: 'Комплектація', color: 'bg-blue-500' },
  ready_for_issue: { label: 'Готово', color: 'bg-emerald-500' },
  issued: { label: 'Видано', color: 'bg-purple-500' },
  on_rent: { label: 'В оренді', color: 'bg-indigo-500' },
  returned: { label: 'Повернено', color: 'bg-slate-500' },
};

export default function OrdersChatModal({ isOpen, onClose }) {
  const [orders, setOrders] = useState([]);
  const [selectedOrderId, setSelectedOrderId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [mobileView, setMobileView] = useState('list'); // 'list' | 'chat'
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  
  const user = JSON.parse(localStorage.getItem('user') || '{}');

  // Завантажити активні замовлення
  useEffect(() => {
    if (isOpen) {
      fetchOrders();
      setMobileView('list');
      setSelectedOrderId(null);
    }
  }, [isOpen]);

  // Завантажити повідомлення при виборі замовлення
  useEffect(() => {
    if (selectedOrderId) {
      fetchMessages(selectedOrderId);
    }
  }, [selectedOrderId]);

  // Прокрутка до останнього повідомлення
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const fetchOrders = async () => {
    setLoading(true);
    try {
      const response = await authFetch(`${BACKEND_URL}/api/decor-orders?status=awaiting_customer,processing,ready_for_issue,issued`);
      if (response.ok) {
        const data = await response.json();
        const ordersList = Array.isArray(data) ? data : (data.orders || []);
        setOrders(ordersList);
      }
    } catch (error) {
      console.error('Error fetching orders:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchMessages = async (orderId) => {
    setLoadingMessages(true);
    try {
      const response = await authFetch(`${BACKEND_URL}/api/orders/${orderId}/internal-notes`);
      if (response.ok) {
        const data = await response.json();
        const notesList = data.notes || data || [];
        setMessages(Array.isArray(notesList) ? notesList : []);
      }
    } catch (error) {
      console.error('Error fetching messages:', error);
      setMessages([]);
    } finally {
      setLoadingMessages(false);
    }
  };

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim() || !selectedOrderId) return;

    try {
      const response = await authFetch(`${BACKEND_URL}/api/orders/${selectedOrderId}/internal-notes`, {
        method: 'POST',
        body: JSON.stringify({
          message: newMessage
        })
      });

      if (response.status === 401) {
        alert('Сесія закінчилась. Будь ласка, перелогіньтесь.');
        localStorage.removeItem('token');
        window.location.href = '/login';
        return;
      }

      if (response.ok) {
        setNewMessage('');
        fetchMessages(selectedOrderId);
      }
    } catch (error) {
      console.error('Error sending message:', error);
    }
  };

  // Вибір замовлення
  const selectOrder = (orderId) => {
    setSelectedOrderId(orderId);
    setMobileView('chat');
  };

  // Повернутися до списку (mobile)
  const backToList = () => {
    setMobileView('list');
  };

  // Фільтрація замовлень
  const filteredOrders = orders.filter(order => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      order.order_number?.toLowerCase().includes(query) ||
      order.customer_name?.toLowerCase().includes(query)
    );
  });

  // Знайти вибране замовлення
  const selectedOrder = orders.find(o => o.order_id === selectedOrderId);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Modal - Full screen on mobile */}
      <div className="absolute inset-2 sm:inset-4 md:inset-auto md:top-1/2 md:left-1/2 md:-translate-x-1/2 md:-translate-y-1/2 md:w-full md:max-w-4xl md:h-[80vh] bg-white rounded-xl sm:rounded-2xl shadow-2xl flex flex-col overflow-hidden">
        
        {/* Header */}
        <div className="flex-shrink-0 h-12 sm:h-14 bg-white border-b border-slate-200 flex items-center justify-between px-3 sm:px-4">
          <div className="flex items-center gap-2">
            {/* Back button on mobile when in chat view */}
            {mobileView === 'chat' && (
              <button
                onClick={backToList}
                className="sm:hidden p-1.5 -ml-1.5 hover:bg-slate-100 rounded-lg"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
            )}
            <MessageSquare className="w-4 h-4 sm:w-5 sm:h-5 text-corp-primary" />
            <h2 className="font-semibold text-slate-800 text-sm sm:text-base">
              {mobileView === 'chat' && selectedOrder ? (
                <span className="sm:hidden">{selectedOrder.order_number}</span>
              ) : null}
              <span className={mobileView === 'chat' ? 'hidden sm:inline' : ''}>Внутрішній чат</span>
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 flex overflow-hidden">
          
          {/* Left Panel - Orders List */}
          <div className={`
            w-full sm:w-72 md:w-80 border-r border-slate-200 flex flex-col bg-slate-50
            ${mobileView === 'chat' ? 'hidden sm:flex' : 'flex'}
          `}>
            {/* Search */}
            <div className="p-2 sm:p-3 border-b border-slate-200">
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Пошук..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-8 pr-3 py-2 rounded-lg border border-slate-300 text-sm focus:ring-2 focus:ring-corp-primary focus:border-transparent"
                />
              </div>
            </div>
            
            {/* Orders List */}
            <div className="flex-1 overflow-y-auto">
              {loading ? (
                <div className="p-4 text-center text-slate-500 text-sm">Завантаження...</div>
              ) : filteredOrders.length === 0 ? (
                <div className="p-4 text-center text-slate-500 text-sm">Немає активних замовлень</div>
              ) : (
                filteredOrders.map(order => {
                  const status = statusConfig[order.status] || { label: order.status, color: 'bg-slate-400' };
                  const isSelected = order.order_id === selectedOrderId;
                  
                  return (
                    <button
                      key={order.order_id}
                      onClick={() => selectOrder(order.order_id)}
                      className={`w-full p-2.5 sm:p-3 text-left border-b border-slate-100 transition-colors flex items-center gap-2 sm:gap-3 ${
                        isSelected ? 'bg-corp-primary/10' : 'hover:bg-white active:bg-slate-100'
                      }`}
                    >
                      {/* Status Dot */}
                      <div className={`w-2.5 h-2.5 sm:w-3 sm:h-3 rounded-full ${status.color} flex-shrink-0`} />
                      
                      {/* Order Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 sm:gap-2">
                          <span className={`font-semibold text-xs sm:text-sm ${isSelected ? 'text-corp-primary' : 'text-slate-800'}`}>
                            {order.order_number}
                          </span>
                          <span className="text-[9px] sm:text-[10px] text-slate-400 bg-slate-100 px-1 sm:px-1.5 py-0.5 rounded">
                            {status.label}
                          </span>
                        </div>
                        <div className="text-[11px] sm:text-xs text-slate-500 truncate">
                          {order.customer_name}
                        </div>
                      </div>
                      
                      {/* Arrow */}
                      <ChevronRight className={`w-4 h-4 flex-shrink-0 ${isSelected ? 'text-corp-primary' : 'text-slate-300'}`} />
                    </button>
                  );
                })
              )}
            </div>
          </div>

          {/* Right Panel - Chat */}
          <div className={`
            flex-1 flex flex-col
            ${mobileView === 'list' ? 'hidden sm:flex' : 'flex'}
          `}>
            {selectedOrderId ? (
              <>
                {/* Chat Header - Desktop only (mobile shows in main header) */}
                {selectedOrder && (
                  <div className="hidden sm:flex p-3 border-b border-slate-200 bg-white items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${statusConfig[selectedOrder.status]?.color || 'bg-slate-400'}`} />
                    <span className="font-semibold text-slate-800 text-sm">{selectedOrder.order_number}</span>
                    <span className="text-slate-400">•</span>
                    <span className="text-sm text-slate-600 truncate">{selectedOrder.customer_name}</span>
                  </div>
                )}

                {/* Messages */}
                <div className="flex-1 overflow-y-auto p-3 sm:p-4 space-y-2 sm:space-y-3 bg-slate-50">
                  {loadingMessages ? (
                    <div className="text-center text-slate-500 py-8 text-sm">Завантаження...</div>
                  ) : messages.length === 0 ? (
                    <div className="text-center text-slate-400 py-8">
                      <MessageSquare className="w-10 h-10 sm:w-12 sm:h-12 mx-auto mb-2 opacity-30" />
                      <p className="text-sm">Немає повідомлень</p>
                      <p className="text-xs mt-1">Напишіть перше повідомлення</p>
                    </div>
                  ) : (
                    messages.map((msg, idx) => {
                      const isSystem = msg.user_name === 'System' || msg.user_name?.includes('Коментар клієнта');
                      const isClientComment = msg.user_name?.includes('Коментар клієнта');
                      
                      return (
                        <div
                          key={msg.id || idx}
                          className={`max-w-[90%] sm:max-w-[85%] ${isSystem ? '' : 'ml-auto'}`}
                        >
                          <div className={`rounded-xl p-2.5 sm:p-3 ${
                            isClientComment 
                              ? 'bg-amber-100 border border-amber-200' 
                              : isSystem 
                                ? 'bg-white border border-slate-200' 
                                : 'bg-corp-primary text-white'
                          }`}>
                            <p className={`text-xs sm:text-sm ${isSystem && !isClientComment ? 'text-slate-700' : ''}`}>
                              {msg.message || msg.note}
                            </p>
                          </div>
                          <div className={`mt-0.5 sm:mt-1 text-[9px] sm:text-[10px] text-slate-400 flex items-center gap-1 ${isSystem ? '' : 'justify-end'}`}>
                            <span>{msg.user_name}</span>
                            <span>•</span>
                            <span>{new Date(msg.created_at).toLocaleString('uk-UA', {
                              day: '2-digit',
                              month: '2-digit',
                              hour: '2-digit',
                              minute: '2-digit'
                            })}</span>
                          </div>
                        </div>
                      );
                    })
                  )}
                  <div ref={messagesEndRef} />
                </div>

                {/* Input */}
                <form onSubmit={sendMessage} className="flex-shrink-0 p-2 sm:p-3 border-t border-slate-200 bg-white safe-area-bottom">
                  <div className="flex gap-2">
                    <input
                      ref={inputRef}
                      type="text"
                      value={newMessage}
                      onChange={(e) => setNewMessage(e.target.value)}
                      placeholder="Повідомлення..."
                      className="flex-1 px-3 sm:px-4 py-2 rounded-xl border border-slate-300 text-sm focus:ring-2 focus:ring-corp-primary focus:border-transparent"
                    />
                    <button
                      type="submit"
                      disabled={!newMessage.trim()}
                      className="px-3 sm:px-4 py-2 bg-corp-primary text-white rounded-xl hover:bg-corp-primary-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed active:scale-95"
                    >
                      <Send className="w-4 h-4" />
                    </button>
                  </div>
                </form>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-slate-400">
                <div className="text-center p-4">
                  <MessageSquare className="w-12 h-12 sm:w-16 sm:h-16 mx-auto mb-3 opacity-30" />
                  <p className="text-sm">Виберіть замовлення</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
