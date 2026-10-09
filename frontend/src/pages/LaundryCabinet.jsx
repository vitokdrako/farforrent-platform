import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Calendar, Package, TrendingUp, AlertCircle, CheckCircle2, Clock, Trash2, Plus, RefreshCw } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const LaundryCabinet = () => {
  const [batches, setBatches] = useState([]);
  const [statistics, setStatistics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('all');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedBatch, setSelectedBatch] = useState(null);
  const [showReturnModal, setShowReturnModal] = useState(false);

  // Завантажити партії
  const fetchBatches = async () => {
    try {
      const token = localStorage.getItem('token');
      const params = filterStatus !== 'all' ? { status: filterStatus } : {};
      
      const response = await axios.get(`${BACKEND_URL}/api/laundry/batches`, {
        params,
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setBatches(response.data);
    } catch (error) {
      console.error('Помилка завантаження партій:', error);
    }
  };

  // Завантажити статистику
  const fetchStatistics = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${BACKEND_URL}/api/laundry/statistics`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setStatistics(response.data);
    } catch (error) {
      console.error('Помилка завантаження статистики:', error);
    }
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchBatches(), fetchStatistics()]);
      setLoading(false);
    };
    
    loadData();
  }, [filterStatus]);

  // Видалити партію
  const handleDeleteBatch = async (batchId) => {
    if (!window.confirm('Видалити партію? Товари повернуться на склад.')) return;
    
    try {
      const token = localStorage.getItem('token');
      await axios.delete(`${BACKEND_URL}/api/laundry/batches/${batchId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      alert('Партію видалено');
      fetchBatches();
      fetchStatistics();
    } catch (error) {
      alert('Помилка видалення: ' + (error.response?.data?.detail || error.message));
    }
  };

  // Закрити партію
  const handleCompleteBatch = async (batchId) => {
    if (!window.confirm('Закрити партію?')) return;
    
    try {
      const token = localStorage.getItem('token');
      await axios.post(`${BACKEND_URL}/api/laundry/batches/${batchId}/complete`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      alert('Партію закрито');
      fetchBatches();
    } catch (error) {
      alert('Помилка: ' + (error.response?.data?.detail || error.message));
    }
  };

  // Статус badge
  const getStatusBadge = (status) => {
    const statusMap = {
      sent: { label: 'Відправлено', class: 'corp-badge corp-badge-info' },
      partial_return: { label: 'Часткове повернення', class: 'corp-badge corp-badge-warning' },
      returned: { label: 'Повернено', class: 'corp-badge corp-badge-success' },
      completed: { label: 'Закрито', class: 'corp-badge corp-badge-neutral' }
    };
    
    const config = statusMap[status] || statusMap.sent;
    return <span className={config.class}>{config.label}</span>;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-corp-bg-page flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="w-12 h-12 text-corp-primary animate-spin mx-auto mb-4" />
          <p className="text-corp-text-muted font-montserrat">Завантаження...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-corp-bg-page font-montserrat">
      {/* Header */}
      <div className="corp-header sticky top-0 z-30">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-semibold text-corp-text-dark flex items-center gap-2">
              🧺 Управління Хімчисткою
            </h1>
            <p className="text-sm text-corp-text-muted mt-1">Відстеження текстилю у хімчистці</p>
          </div>
          <button 
            onClick={() => setShowCreateModal(true)} 
            className="corp-btn corp-btn-primary"
          >
            <Plus className="w-4 h-4" />
            Нова партія
          </button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6">

        {/* Статистика */}
        {statistics && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div className="corp-stat-card">
              <div className="flex items-center justify-between">
                <div>
                  <p className="corp-stat-label">Всього партій</p>
                  <p className="corp-stat-value">{statistics.total_batches}</p>
                </div>
                <Package className="w-10 h-10 corp-icon-primary" />
              </div>
            </div>
            
            <div className="corp-stat-card">
              <div className="flex items-center justify-between">
                <div>
                  <p className="corp-stat-label">Активні партії</p>
                  <p className="corp-stat-value text-corp-warning">{statistics.active_batches}</p>
                </div>
                <Clock className="w-10 h-10 corp-icon-warning" />
              </div>
            </div>
            
            <div className="corp-stat-card">
              <div className="flex items-center justify-between">
                <div>
                  <p className="corp-stat-label">Відправлено товарів</p>
                  <p className="corp-stat-value text-corp-gold">{statistics.total_items_sent}</p>
                </div>
                <TrendingUp className="w-10 h-10 corp-icon-gold" />
              </div>
            </div>
            
            <div className="corp-stat-card">
              <div className="flex items-center justify-between">
                <div>
                  <p className="corp-stat-label">Вартість</p>
                  <p className="corp-stat-value text-corp-success">{statistics.total_cost.toFixed(2)} ₴</p>
                </div>
                <CheckCircle2 className="w-10 h-10 corp-icon-success" />
              </div>
            </div>
          </div>
        )}

        {/* Фільтри */}
        <div className="corp-card mb-6">
          <div className="flex gap-2 flex-wrap">
            {['all', 'sent', 'partial_return', 'returned', 'completed'].map(status => (
              <button
                key={status}
                className={filterStatus === status ? 'corp-btn corp-btn-primary' : 'corp-btn corp-btn-secondary'}
                onClick={() => setFilterStatus(status)}
              >
                {status === 'all' ? 'Всі' :
                 status === 'sent' ? 'Відправлено' :
                 status === 'partial_return' ? 'Часткове повернення' :
                 status === 'returned' ? 'Повернено' : 'Закрито'}
              </button>
            ))}
          </div>
        </div>

        {/* Список партій */}
        <div className="space-y-4">
          {batches.length === 0 ? (
            <div className="corp-empty">
              <AlertCircle className="corp-empty-icon mx-auto" />
              <h3 className="corp-empty-title">Партій не знайдено</h3>
              <p className="corp-empty-text">Створіть нову партію для відправки текстилю в хімчистку</p>
            </div>
          ) : (
            batches.map(batch => (
              <div key={batch.id} className="corp-card">
                {/* Header партії */}
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="text-lg font-semibold text-corp-text-dark">{batch.batch_number}</h3>
                    <p className="text-sm text-corp-text-muted mt-1">
                      🏢 {batch.laundry_company}
                    </p>
                  </div>
                  <div className="text-right">
                    {getStatusBadge(batch.status)}
                    {batch.cost > 0 && (
                      <p className="text-sm font-medium text-corp-gold mt-2">
                        {batch.cost.toFixed(2)} ₴
                      </p>
                    )}
                  </div>
                </div>
                {/* Інформація про партію */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4 pb-4 border-b border-corp-border-light">
                  <div>
                    <p className="text-xs text-corp-text-muted uppercase tracking-wide mb-1">📅 Відправлено</p>
                    <p className="font-medium text-corp-text-dark">{new Date(batch.sent_date).toLocaleDateString('uk-UA')}</p>
                  </div>
                  <div>
                    <p className="text-xs text-corp-text-muted uppercase tracking-wide mb-1">📆 Очікується</p>
                    <p className="font-medium text-corp-text-dark">{new Date(batch.expected_return_date).toLocaleDateString('uk-UA')}</p>
                  </div>
                  <div>
                    <p className="text-xs text-corp-text-muted uppercase tracking-wide mb-1">📦 Товарів</p>
                    <p className="font-medium text-corp-text-dark mb-2">{batch.returned_items} / {batch.total_items}</p>
                    <div className="corp-progress">
                      <div 
                        className="corp-progress-bar" 
                        style={{ width: `${(batch.returned_items / batch.total_items) * 100}%` }}
                      ></div>
                    </div>
                  </div>
                </div>

                {batch.notes && (
                  <div className="bg-corp-bg-light p-3 rounded-corp-sm mb-4">
                    <p className="text-sm text-corp-text-main">{batch.notes}</p>
                  </div>
                )}

                {/* Товари в партії */}
                {batch.items && batch.items.length > 0 && (
                  <div className="mt-4">
                    <p className="text-xs text-corp-text-muted uppercase tracking-wide mb-2">Товари:</p>
                    <div className="space-y-2">
                      {batch.items.map(item => (
                        <div key={item.id} className="flex justify-between items-center bg-corp-bg-card p-3 rounded-corp-sm border border-corp-border-light">
                          <div className="flex-1">
                            <p className="font-medium text-sm text-corp-text-dark">{item.product_name}</p>
                            <p className="text-xs text-corp-text-muted">{item.sku} • {item.category}</p>
                          </div>
                          <div className="text-right ml-4">
                            <p className="text-sm font-semibold text-corp-text-dark">{item.returned_quantity} / {item.quantity} од.</p>
                            {item.condition_after && (
                              <span className={`inline-flex items-center gap-1 text-xs mt-1 ${
                                item.condition_after === 'clean' ? 'corp-badge corp-badge-success' : 
                                item.condition_after === 'damaged' ? 'corp-badge corp-badge-warning' : 
                                'corp-badge corp-badge-neutral'
                              }`}>
                                {item.condition_after === 'clean' ? '✨ Чисто' : 
                                 item.condition_after === 'damaged' ? '⚠️ Пошкоджено' : item.condition_after}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Дії */}
                <div className="flex gap-2 mt-4 pt-4 border-t border-corp-border-light">
                  <button 
                    className={batch.status === 'completed' ? 'corp-btn corp-btn-secondary opacity-50 cursor-not-allowed' : 'corp-btn corp-btn-outline'}
                    onClick={() => {
                      setSelectedBatch(batch);
                      setShowReturnModal(true);
                    }}
                    disabled={batch.status === 'completed'}
                  >
                    Прийняти повернення
                  </button>
                  
                  {batch.status === 'returned' && (
                    <button 
                      className="corp-btn corp-btn-primary"
                      onClick={() => handleCompleteBatch(batch.id)}
                    >
                      <CheckCircle2 className="w-4 h-4" />
                      Закрити партію
                    </button>
                  )}
                  
                  {batch.status === 'sent' && batch.returned_items === 0 && (
                    <button 
                      className="corp-btn corp-btn-secondary text-corp-error hover:text-white hover:bg-corp-error"
                      onClick={() => handleDeleteBatch(batch.id)}
                    >
                      <Trash2 className="w-4 h-4" />
                      Видалити
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Модалки створення та повернення */}
      {showCreateModal && (
        <CreateBatchModal 
          onClose={() => setShowCreateModal(false)} 
          onSuccess={() => {
            setShowCreateModal(false);
            fetchBatches();
            fetchStatistics();
          }}
        />
      )}

      {showReturnModal && selectedBatch && (
        <ReturnItemsModal 
          batch={selectedBatch}
          onClose={() => {
            setShowReturnModal(false);
            setSelectedBatch(null);
          }} 
          onSuccess={() => {
            setShowReturnModal(false);
            setSelectedBatch(null);
            fetchBatches();
            fetchStatistics();
          }}
        />
      )}
    </div>
  );
};

// ==================== Модалка створення партії ====================

const CreateBatchModal = ({ onClose, onSuccess }) => {
  const [formData, setFormData] = useState({
    laundry_company: '',
    expected_return_date: '',
    cost: '',
    notes: ''
  });
  const [items, setItems] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [loading, setLoading] = useState(false);

  // Пошук товарів-текстилю
  const handleSearch = async (query) => {
    if (query.length < 2) {
      setSearchResults([]);
      return;
    }

    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${BACKEND_URL}/api/products/search`, {
        params: { q: query, category: 'Текстиль' },
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setSearchResults(response.data);
    } catch (error) {
      console.error('Помилка пошуку:', error);
    }
  };

  // Додати товар
  const addItem = (product) => {
    const exists = items.find(i => i.product_id === product.product_id);
    if (exists) {
      alert('Цей товар вже доданий');
      return;
    }

    setItems([...items, {
      product_id: product.product_id,
      product_name: product.name,
      sku: product.sku,
      category: product.category_name || 'Текстиль',
      quantity: 1,
      condition_before: 'dirty'
    }]);
    
    setSearchQuery('');
    setSearchResults([]);
  };

  // Створити партію
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (items.length === 0) {
      alert('Додайте хоча б один товар');
      return;
    }

    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      await axios.post(`${BACKEND_URL}/api/laundry/batches`, {
        ...formData,
        cost: parseFloat(formData.cost) || 0,
        items
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      alert('Партію створено');
      onSuccess();
    } catch (error) {
      alert('Помилка: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="corp-modal-overlay">
      <div className="corp-modal-content max-w-2xl w-full p-6">
        <h2 className="text-2xl font-semibold text-corp-text-dark mb-6">Нова партія в хімчистку</h2>
          
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs text-corp-text-muted uppercase tracking-wide mb-2 block">Компанія хімчистки *</label>
              <input 
                className="corp-input"
                value={formData.laundry_company}
                onChange={(e) => setFormData({...formData, laundry_company: e.target.value})}
                required
                placeholder="Назва компанії"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-corp-text-muted uppercase tracking-wide mb-2 block">Очікувана дата повернення *</label>
                <input 
                  className="corp-input"
                  type="date"
                  value={formData.expected_return_date}
                  onChange={(e) => setFormData({...formData, expected_return_date: e.target.value})}
                  required
                />
              </div>
              
              <div>
                <label className="text-xs text-corp-text-muted uppercase tracking-wide mb-2 block">Вартість послуги</label>
                <input 
                  className="corp-input"
                  type="number"
                  step="0.01"
                  value={formData.cost}
                  onChange={(e) => setFormData({...formData, cost: e.target.value})}
                  placeholder="0.00"
                />
              </div>
            </div>

            <div>
              <label className="text-xs text-corp-text-muted uppercase tracking-wide mb-2 block">Примітки</label>
              <textarea 
                className="corp-input"
                rows="2"
                value={formData.notes}
                onChange={(e) => setFormData({...formData, notes: e.target.value})}
                placeholder="Додаткова інформація"
              />
            </div>

            {/* Пошук товарів */}
            <div>
              <label className="text-xs text-corp-text-muted uppercase tracking-wide mb-2 block">Додати товари *</label>
              <input 
                className="corp-input"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  handleSearch(e.target.value);
                }}
                placeholder="Пошук товарів (текстиль)..."
              />
              
              {searchResults.length > 0 && (
                <div className="border border-corp-border rounded-corp-sm mt-2 max-h-40 overflow-y-auto bg-white">
                  {searchResults.map(product => (
                    <div 
                      key={product.product_id}
                      className="p-3 hover:bg-corp-bg-light cursor-pointer transition-colors border-b border-corp-border-light last:border-b-0"
                      onClick={() => addItem(product)}
                    >
                      <p className="font-medium text-sm text-corp-text-dark">{product.name}</p>
                      <p className="text-xs text-corp-text-muted">{product.sku}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Список доданих товарів */}
            {items.length > 0 && (
              <div className="corp-card-flat">
                <p className="text-xs text-corp-text-muted uppercase tracking-wide mb-3">Додані товари ({items.length}):</p>
                <div className="space-y-2">
                  {items.map((item, idx) => (
                    <div key={idx} className="flex justify-between items-center bg-corp-bg-card p-3 rounded-corp-sm border border-corp-border-light">
                      <div className="flex-1">
                        <p className="font-medium text-sm text-corp-text-dark">{item.product_name}</p>
                        <p className="text-xs text-corp-text-muted">{item.sku}</p>
                      </div>
                      <input 
                        className="corp-input w-20 mr-2"
                        type="number"
                        min="1"
                        value={item.quantity}
                        onChange={(e) => {
                          const newItems = [...items];
                          newItems[idx].quantity = parseInt(e.target.value) || 1;
                          setItems(newItems);
                        }}
                      />
                      <button 
                        type="button"
                        className="corp-btn corp-btn-secondary p-2"
                        onClick={() => setItems(items.filter((_, i) => i !== idx))}
                      >
                        <Trash2 className="w-4 h-4 text-corp-error" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex gap-3 pt-4">
              <button type="submit" disabled={loading} className="corp-btn corp-btn-primary flex-1">
                {loading ? 'Створення...' : 'Створити партію'}
              </button>
              <button type="button" className="corp-btn corp-btn-secondary" onClick={onClose}>
                Скасувати
              </button>
            </div>
          </form>
      </div>
    </div>
  );
};

// ==================== Модалка повернення товарів ====================

const ReturnItemsModal = ({ batch, onClose, onSuccess }) => {
  const [returns, setReturns] = useState({});
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    const returnItems = Object.entries(returns)
      .filter(([_, data]) => data.quantity > 0)
      .map(([item_id, data]) => ({
        item_id,
        returned_quantity: data.quantity,
        condition_after: data.condition,
        notes: data.notes
      }));

    if (returnItems.length === 0) {
      alert('Вкажіть кількість повернених товарів');
      return;
    }

    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      await axios.post(
        `${BACKEND_URL}/api/laundry/batches/${batch.id}/return-items`,
        returnItems,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      alert('Товари прийнято');
      onSuccess();
    } catch (error) {
      alert('Помилка: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="corp-modal-overlay">
      <div className="corp-modal-content max-w-2xl w-full p-6">
        <h2 className="text-2xl font-semibold text-corp-text-dark mb-2">Прийом товарів</h2>
        <p className="text-corp-text-muted mb-6">Партія: <span className="font-medium text-corp-primary">{batch.batch_number}</span></p>
        
        <form onSubmit={handleSubmit} className="space-y-3">
          {batch.items.map(item => {
            const remaining = item.quantity - item.returned_quantity;
            if (remaining <= 0) return null;

            return (
              <div key={item.id} className="corp-card-flat">
                <p className="font-medium text-corp-text-dark">{item.product_name}</p>
                <p className="text-sm text-corp-text-muted mb-3">{item.sku} • Залишок: <span className="font-semibold text-corp-gold">{remaining} од.</span></p>
                
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-corp-text-muted uppercase tracking-wide mb-1 block">Кількість</label>
                    <input 
                      className="corp-input"
                      type="number"
                      min="0"
                      max={remaining}
                      value={returns[item.id]?.quantity || 0}
                      onChange={(e) => setReturns({
                        ...returns,
                        [item.id]: {
                          ...returns[item.id],
                          quantity: parseInt(e.target.value) || 0,
                          condition: returns[item.id]?.condition || 'clean'
                        }
                      })}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-corp-text-muted uppercase tracking-wide mb-1 block">Стан</label>
                    <select 
                      className="corp-select w-full"
                      value={returns[item.id]?.condition || 'clean'}
                      onChange={(e) => setReturns({
                        ...returns,
                        [item.id]: {
                          ...returns[item.id],
                          quantity: returns[item.id]?.quantity || 0,
                          condition: e.target.value
                        }
                      })}
                    >
                      <option value="clean">Чисто</option>
                      <option value="damaged">Пошкоджено</option>
                      <option value="lost">Втрачено</option>
                    </select>
                  </div>
                </div>
              </div>
            );
          })}

          <div className="flex gap-3 pt-4">
            <button type="submit" disabled={loading} className="corp-btn corp-btn-primary flex-1">
              {loading ? 'Обробка...' : 'Прийняти товари'}
            </button>
            <button type="button" className="corp-btn corp-btn-secondary" onClick={onClose}>
              Скасувати
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default LaundryCabinet;
