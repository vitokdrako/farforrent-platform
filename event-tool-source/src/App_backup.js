import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';
import { AuthProvider, useAuth } from './context/AuthContext';
import { BoardProvider, useBoard } from './context/BoardContext';
import './App.css';
import api from './api/axios';

// Create a client
const queryClient = new QueryClient();

// Auth Components
const LoginPage = () => {
  const { login, register } = useAuth();
  const [isLogin, setIsLogin] = useState(true);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    firstname: '',
    lastname: '',
    telephone: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isLogin) {
        await login(formData.email, formData.password);
        window.location.href = '/';
      } else {
        await register(formData);
        alert('Реєстрація успішна! Тепер увійдіть.');
        setIsLogin(true);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Помилка входу/реєстрації');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-pink-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-md">
        <h1 className="text-3xl font-bold text-center mb-2 text-gray-800">
          🎨 FarforDecor
        </h1>
        <p className="text-center text-gray-600 mb-6">Event Planning Tool</p>

        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setIsLogin(true)}
            className={`flex-1 py-2 rounded-lg font-medium transition-colors ${
              isLogin
                ? 'bg-purple-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            Вхід
          </button>
          <button
            onClick={() => setIsLogin(false)}
            className={`flex-1 py-2 rounded-lg font-medium transition-colors ${
              !isLogin
                ? 'bg-purple-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            Реєстрація
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {!isLogin && (
            <>
              <input
                type="text"
                placeholder="Ім'я"
                value={formData.firstname}
                onChange={(e) =>
                  setFormData({ ...formData, firstname: e.target.value })
                }
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none"
                required={!isLogin}
              />
              <input
                type="text"
                placeholder="Прізвище"
                value={formData.lastname}
                onChange={(e) =>
                  setFormData({ ...formData, lastname: e.target.value })
                }
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none"
                required={!isLogin}
              />
              <input
                type="tel"
                placeholder="Телефон"
                value={formData.telephone}
                onChange={(e) =>
                  setFormData({ ...formData, telephone: e.target.value })
                }
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none"
              />
            </>
          )}

          <input
            type="email"
            placeholder="Email"
            value={formData.email}
            onChange={(e) =>
              setFormData({ ...formData, email: e.target.value })
            }
            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none"
            required
          />
          <input
            type="password"
            placeholder="Пароль"
            value={formData.password}
            onChange={(e) =>
              setFormData({ ...formData, password: e.target.value })
            }
            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none"
            required
            minLength={6}
          />

          {error && (
            <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-purple-600 text-white py-3 rounded-lg font-medium hover:bg-purple-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Завантаження...' : isLogin ? 'Увійти' : 'Зареєструватися'}
          </button>
        </form>
      </div>
    </div>
  );
};

// Main Event Planner Page
const EventPlannerPage = () => {
  const { user, logout } = useAuth();
  const { activeBoard, setActiveBoard, isSidePanelOpen, toggleSidePanel } = useBoard();
  
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [boards, setBoards] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showNewBoardModal, setShowNewBoardModal] = useState(false);

  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    try {
      setLoading(true);
      const [productsData, categoriesData, boardsData] = await Promise.all([
        api.get('/products?limit=50').then(r => r.data),
        api.get('/categories').then(r => r.data),
        api.get('/boards').then(r => r.data),
      ]);
      
      setProducts(productsData);
      setCategories(categoriesData);
      setBoards(boardsData);
      
      if (boardsData.length > 0) {
        setActiveBoard(boardsData[0]);
      }
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateBoard = async (boardData) => {
    try {
      const newBoard = await api.post('/boards', boardData).then(r => r.data);
      setBoards([newBoard, ...boards]);
      setActiveBoard(newBoard);
      setShowNewBoardModal(false);
    } catch (error) {
      console.error('Failed to create board:', error);
      alert('Помилка створення мудборду');
    }
  };

  const handleAddToBoard = async (product) => {
    if (!activeBoard) {
      alert('Спочатку створіть мудборд!');
      return;
    }

    try {
      await api.post(`/boards/${activeBoard.id}/items`, {
        product_id: product.product_id,
        quantity: 1,
      });
      
      // Reload active board
      const updatedBoard = await api.get(`/boards/${activeBoard.id}`).then(r => r.data);
      setActiveBoard(updatedBoard);
      
      // Update boards list
      setBoards(boards.map(b => b.id === updatedBoard.id ? updatedBoard : b));
    } catch (error) {
      console.error('Failed to add item:', error);
      alert('Помилка додавання товару');
    }
  };

  const handleRemoveFromBoard = async (itemId) => {
    if (!activeBoard) return;

    try {
      await api.delete(`/boards/${activeBoard.id}/items/${itemId}`);
      
      // Reload active board
      const updatedBoard = await api.get(`/boards/${activeBoard.id}`).then(r => r.data);
      setActiveBoard(updatedBoard);
      setBoards(boards.map(b => b.id === updatedBoard.id ? updatedBoard : b));
    } catch (error) {
      console.error('Failed to remove item:', error);
    }
  };

  const filteredProducts = products.filter(p => {
    const matchesSearch = !searchTerm || 
      p.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.sku?.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesCategory = !selectedCategory || p.category_id === selectedCategory;
    
    return matchesSearch && matchesCategory;
  });

  const calculateBoardTotal = () => {
    if (!activeBoard || !activeBoard.items) return 0;
    
    return activeBoard.items.reduce((total, item) => {
      const price = item.product?.rental_price || 0;
      const days = activeBoard.rental_days || 1;
      return total + (price * item.quantity * days);
    }, 0);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-2xl text-gray-600">Завантаження...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-bold text-purple-600">🎨 FarforDecor</h1>
            <span className="text-gray-400">|</span>
            <span className="text-gray-600">Event Planning Tool</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-600">
              {user?.firstname} {user?.lastname}
            </span>
            <button
              onClick={logout}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900"
            >
              Вийти
            </button>
          </div>
        </div>
      </header>

      <div className="flex h-[calc(100vh-73px)]">
        {/* Catalog Section */}
        <div className={`flex-1 overflow-auto transition-all duration-300 ${isSidePanelOpen ? 'mr-96' : ''}`}>
          <div className="p-6">
            {/* Search and Filters */}
            <div className="mb-6 space-y-4">
              <input
                type="text"
                placeholder="🔍 Пошук товарів..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none"
              />
              
              <div className="flex gap-2 flex-wrap">
                <button
                  onClick={() => setSelectedCategory(null)}
                  className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                    !selectedCategory
                      ? 'bg-purple-600 text-white'
                      : 'bg-white border border-gray-300 text-gray-700 hover:border-purple-500'
                  }`}
                >
                  Всі категорії
                </button>
                {categories.slice(0, 6).map((cat) => (
                  <button
                    key={cat.category_id}
                    onClick={() => setSelectedCategory(cat.category_id)}
                    className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                      selectedCategory === cat.category_id
                        ? 'bg-purple-600 text-white'
                        : 'bg-white border border-gray-300 text-gray-700 hover:border-purple-500'
                    }`}
                  >
                    {cat.name}
                  </button>
                ))}
              </div>
            </div>

            {/* Products Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
              {filteredProducts.map((product) => (
                <div
                  key={product.product_id}
                  className="bg-white rounded-lg shadow-sm hover:shadow-md transition-shadow overflow-hidden border border-gray-200"
                >
                  <div className="aspect-square bg-gray-100 flex items-center justify-center">
                    {product.image_url ? (
                      <img
                        src={`https://www.farforrent.com.ua/${product.image_url}`}
                        alt={product.name}
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          e.target.style.display = 'none';
                        }}
                      />
                    ) : (
                      <div className="text-6xl">🎨</div>
                    )}
                  </div>
                  <div className="p-4">
                    <h3 className="font-medium text-gray-900 mb-1 line-clamp-2" title={product.name}>
                      {product.name}
                    </h3>
                    <p className="text-sm text-gray-500 mb-2">{product.sku}</p>
                    <div className="flex items-center justify-between">
                      <span className="text-lg font-bold text-purple-600">
                        ₴{product.rental_price}
                      </span>
                      <span className="text-sm text-gray-500">
                        {product.quantity} шт
                      </span>
                    </div>
                    <button
                      onClick={() => handleAddToBoard(product)}
                      className="w-full mt-3 px-4 py-2 bg-purple-600 text-white rounded-lg font-medium hover:bg-purple-700 transition-colors"
                    >
                      + Додати до івенту
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {filteredProducts.length === 0 && (
              <div className="text-center py-12 text-gray-500">
                Товари не знайдено
              </div>
            )}
          </div>
        </div>

        {/* Side Panel - Event Board */}
        {isSidePanelOpen && (
          <div className="w-96 bg-white border-l border-gray-200 flex flex-col fixed right-0 h-[calc(100vh-73px)] shadow-xl">
            {/* Panel Header */}
            <div className="p-4 border-b border-gray-200 flex items-center justify-between bg-purple-50">
              <h2 className="font-bold text-lg text-purple-900">📌 Мій Івент</h2>
              <button
                onClick={toggleSidePanel}
                className="text-gray-500 hover:text-gray-700"
              >
                ← Згорнути
              </button>
            </div>

            {/* Board Selector */}
            <div className="p-4 border-b border-gray-200">
              <select
                value={activeBoard?.id || ''}
                onChange={(e) => {
                  const board = boards.find(b => b.id === e.target.value);
                  setActiveBoard(board);
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg mb-2"
              >
                <option value="">Виберіть мудборд</option>
                {boards.map((board) => (
                  <option key={board.id} value={board.id}>
                    {board.board_name}
                  </option>
                ))}
              </select>
              <button
                onClick={() => setShowNewBoardModal(true)}
                className="w-full px-4 py-2 bg-purple-600 text-white rounded-lg font-medium hover:bg-purple-700"
              >
                + Створити новий івент
              </button>
            </div>

            {/* Board Content */}
            {activeBoard ? (
              <>
                <div className="p-4 border-b border-gray-200 bg-gray-50">
                  <h3 className="font-bold text-gray-900 mb-1">{activeBoard.board_name}</h3>
                  <p className="text-sm text-gray-600">
                    📅 {activeBoard.event_date || 'Дата не вказана'}
                  </p>
                  {activeBoard.rental_days && (
                    <p className="text-sm text-gray-600">
                      🕐 {activeBoard.rental_days} днів оренди
                    </p>
                  )}
                </div>

                {/* Items List */}
                <div className="flex-1 overflow-auto p-4">
                  {activeBoard.items && activeBoard.items.length > 0 ? (
                    <div className="space-y-3">
                      {activeBoard.items.map((item) => (
                        <div
                          key={item.id}
                          className="bg-gray-50 rounded-lg p-3 border border-gray-200"
                        >
                          <div className="flex justify-between items-start mb-2">
                            <h4 className="font-medium text-sm text-gray-900 flex-1 pr-2">
                              {item.product?.name}
                            </h4>
                            <button
                              onClick={() => handleRemoveFromBoard(item.id)}
                              className="text-red-500 hover:text-red-700"
                            >
                              🗑️
                            </button>
                          </div>
                          <div className="flex justify-between items-center text-sm">
                            <span className="text-gray-600">
                              Кількість: {item.quantity} шт
                            </span>
                            <span className="font-bold text-purple-600">
                              ₴{(item.product?.rental_price || 0) * item.quantity}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8 text-gray-500">
                      <p className="text-4xl mb-2">📦</p>
                      <p>Мудборд порожній</p>
                      <p className="text-sm">Додайте товари з каталогу</p>
                    </div>
                  )}
                </div>

                {/* Summary */}
                <div className="p-4 border-t border-gray-200 bg-gray-50">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm text-gray-600">Всього позицій:</span>
                    <span className="font-bold">{activeBoard.items?.length || 0}</span>
                  </div>
                  <div className="flex justify-between items-center mb-4">
                    <span className="font-bold text-gray-900">Загальна вартість:</span>
                    <span className="font-bold text-2xl text-purple-600">
                      ₴{calculateBoardTotal().toFixed(2)}
                    </span>
                  </div>
                  <button className="w-full px-4 py-3 bg-green-600 text-white rounded-lg font-bold hover:bg-green-700 transition-colors">
                    🛒 Оформити замовлення
                  </button>
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-gray-500">
                <div className="text-center">
                  <p className="text-4xl mb-2">🎨</p>
                  <p>Створіть перший мудборд</p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Toggle button when panel is closed */}
        {!isSidePanelOpen && (
          <button
            onClick={toggleSidePanel}
            className="fixed right-0 top-1/2 transform -translate-y-1/2 bg-purple-600 text-white px-2 py-8 rounded-l-lg shadow-lg hover:bg-purple-700 z-20"
          >
            <span className="transform rotate-90 inline-block">📌 Мудборд</span>
          </button>
        )}
      </div>

      {/* New Board Modal */}
      {showNewBoardModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl p-6 w-full max-w-md">
            <h2 className="text-2xl font-bold mb-4">Створити новий івент</h2>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                handleCreateBoard({
                  board_name: formData.get('board_name'),
                  event_date: formData.get('event_date') || undefined,
                  event_type: formData.get('event_type') || undefined,
                  rental_start_date: formData.get('rental_start_date') || undefined,
                  rental_end_date: formData.get('rental_end_date') || undefined,
                  notes: formData.get('notes') || undefined,
                });
              }}
              className="space-y-4"
            >
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Назва івенту *
                </label>
                <input
                  type="text"
                  name="board_name"
                  placeholder="напр. Весілля Марії"
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Дата івенту
                </label>
                <input
                  type="date"
                  name="event_date"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Тип івенту
                </label>
                <select
                  name="event_type"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                >
                  <option value="">Оберіть тип</option>
                  <option value="wedding">Весілля</option>
                  <option value="birthday">День народження</option>
                  <option value="photoshoot">Фотосесія</option>
                  <option value="corporate">Корпоратив</option>
                  <option value="other">Інше</option>
                </select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Початок оренди
                  </label>
                  <input
                    type="date"
                    name="rental_start_date"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Кінець оренди
                  </label>
                  <input
                    type="date"
                    name="rental_end_date"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Нотатки
                </label>
                <textarea
                  name="notes"
                  rows="3"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  placeholder="Додаткова інформація про івент..."
                ></textarea>
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowNewBoardModal(false)}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  Скасувати
                </button>
                <button
                  type="submit"
                  className="flex-1 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
                >
                  Створити
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

// Protected Route
const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-2xl text-gray-600">Завантаження...</div>
      </div>
    );
  }

  return isAuthenticated ? children : <Navigate to="/login" />;
};

// Main App
function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BoardProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <EventPlannerPage />
                  </ProtectedRoute>
                }
              />
            </Routes>
          </BrowserRouter>
        </BoardProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
