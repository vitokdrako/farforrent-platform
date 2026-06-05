import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';
import { AuthProvider, useAuth } from './context/AuthContext';
import { BoardProvider, useBoard } from './context/BoardContext';
import DateRangePicker from './components/DateRangePicker';
import ProductCard from './components/ProductCard';
import BoardItemCard from './components/BoardItemCard';
import MoodboardCanvas from './components/MoodboardCanvas';
import ProductFilters from './components/ProductFilters';
import CreateBoardModal from './components/CreateBoardModal';
import UserProfile from './components/UserProfile';
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
    <div className="min-h-screen flex items-center justify-center p-4" style={{background: '#f3f3f3'}}>
      <div className="bg-white shadow-sm p-10 w-full max-w-md" style={{borderRadius: '4px', boxShadow: '0 2px 6px rgba(0,0,0,0.03)'}}>
        <div className="text-center mb-8">
          {/* Logo */}
          <div className="flex justify-center mb-4">
            <img 
              src="/logo.svg" 
              alt="FarforDecor Logo" 
              style={{
                height: '60px',
                width: 'auto'
              }}
            />
          </div>
          {/* Company Name */}
          <h1 className="text-2xl font-bold mb-1" style={{color: '#333', letterSpacing: '0.05em'}}>
            FarforDecorOrenda
          </h1>
          <p className="text-xs" style={{color: '#999', marginTop: '8px', textTransform: 'uppercase'}}>Event Planning Platform</p>
        </div>

        <div className="flex gap-2 mb-8">
          <button
            onClick={() => setIsLogin(true)}
            className={`flex-1 fd-btn transition-all ${
              isLogin
                ? 'fd-btn-black'
                : 'fd-btn-secondary'
            }`}
            style={{padding: '9px 12px'}}
          >
            Вхід
          </button>
          <button
            onClick={() => setIsLogin(false)}
            className={`flex-1 fd-btn transition-all ${
              !isLogin
                ? 'fd-btn-black'
                : 'fd-btn-secondary'
            }`}
            style={{padding: '9px 12px'}}
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
                className="w-full fd-input"
                required={!isLogin}
              />
              <input
                type="text"
                placeholder="Прізвище"
                value={formData.lastname}
                onChange={(e) =>
                  setFormData({ ...formData, lastname: e.target.value })
                }
                className="w-full fd-input"
                required={!isLogin}
              />
              <input
                type="tel"
                placeholder="Телефон"
                value={formData.telephone}
                onChange={(e) =>
                  setFormData({ ...formData, telephone: e.target.value })
                }
                className="w-full fd-input"
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
            className="w-full fd-btn fd-btn-black disabled:opacity-50 disabled:cursor-not-allowed"
            style={{padding: '12px'}}
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
  const navigate = useNavigate();
  
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [allSubcategories, setAllSubcategories] = useState([]);
  const [boards, setBoards] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [selectedSubcategory, setSelectedSubcategory] = useState(null);
  const [selectedColor, setSelectedColor] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [showNewBoardModal, setShowNewBoardModal] = useState(false);
  const [showCanvas, setShowCanvas] = useState(false);

  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    try {
      setLoading(true);
      // Завантажити перші 100 товарів для швидкого старту
      const [productsData, categoriesData, subcategoriesData, boardsData] = await Promise.all([
        api.get('/products?limit=100').then(r => r.data),
        api.get('/categories').then(r => r.data),
        api.get('/subcategories').then(r => r.data),
        api.get('/boards').then(r => r.data),
      ]);
      
      setProducts(productsData);
      setCategories(categoriesData);
      setAllSubcategories(subcategoriesData);
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

  const loadMoreProducts = async () => {
    try {
      setLoadingMore(true);
      const currentCount = products.length;
      const moreProducts = await api.get(`/products?skip=${currentCount}&limit=100`).then(r => r.data);
      
      if (moreProducts.length === 0) {
        setHasMore(false);
      } else {
        setProducts([...products, ...moreProducts]);
      }
    } catch (error) {
      console.error('Failed to load more products:', error);
    } finally {
      setLoadingMore(false);
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

  const handleUpdateBoardDates = async (boardId, startDate, endDate) => {
    if (!startDate || !endDate) return;

    try {
      const updatedBoard = await api.patch(`/boards/${boardId}`, {
        rental_start_date: startDate,
        rental_end_date: endDate,
      }).then(r => r.data);
      
      setActiveBoard(updatedBoard);
      setBoards(boards.map(b => b.id === boardId ? updatedBoard : b));
    } catch (error) {
      console.error('Failed to update dates:', error);
      alert('Помилка оновлення дат');
    }
  };

  const handleSaveCanvas = async (canvasLayout) => {
    if (!activeBoard) return;

    try {
      const updatedBoard = await api.patch(`/boards/${activeBoard.id}`, {
        canvas_layout: canvasLayout,
      }).then(r => r.data);
      
      setActiveBoard(updatedBoard);
      setBoards(boards.map(b => b.id === updatedBoard.id ? updatedBoard : b));
      setShowCanvas(false);
      alert('✅ Візуальний мудборд збережено!');
    } catch (error) {
      console.error('Failed to save canvas:', error);
      alert('Помилка збереження мудборду');
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

  const handleUpdateItem = async (itemId, updateData) => {
    if (!activeBoard) return;

    try {
      await api.patch(`/boards/${activeBoard.id}/items/${itemId}`, updateData);
      
      // Reload active board
      const updatedBoard = await api.get(`/boards/${activeBoard.id}`).then(r => r.data);
      setActiveBoard(updatedBoard);
      setBoards(boards.map(b => b.id === updatedBoard.id ? updatedBoard : b));
    } catch (error) {
      console.error('Failed to update item:', error);
      throw error;
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

  // Get all categories from API and products
  const allCategories = React.useMemo(() => {
    // Combine categories from API and products
    const categoriesMap = new Map();
    
    // Add categories from API
    categories.forEach(cat => {
      categoriesMap.set(cat.name, {
        name: cat.name,
        id: cat.category_id,
        sort_order: cat.sort_order
      });
    });
    
    // Add categories from products that might not be in API
    products.forEach(p => {
      if (p.category_name && !categoriesMap.has(p.category_name)) {
        categoriesMap.set(p.category_name, {
          name: p.category_name,
          sort_order: 999
        });
      }
    });
    
    return Array.from(categoriesMap.values()).sort((a, b) => {
      // Sort by sort_order first, then by name
      if (a.sort_order !== b.sort_order) {
        return a.sort_order - b.sort_order;
      }
      return a.name.localeCompare(b.name);
    });
  }, [categories, products]);

  // Get available subcategories based on selected category
  // IMPORTANT: Use only subcategories from currently loaded products
  const availableSubcategories = React.useMemo(() => {
    if (!selectedCategory) return [];
    
    // Get subcategories from loaded products only (not from API)
    // This ensures we only show subcategories that have products in current view
    const subcats = new Set();
    products.forEach(p => {
      if (p.category_name === selectedCategory && p.subcategory_name) {
        subcats.add(p.subcategory_name);
      }
    });
    
    return Array.from(subcats).sort((a, b) => a.localeCompare(b, 'uk'));
  }, [products, selectedCategory]);

  // Get all available colors
  const availableColors = React.useMemo(() => {
    const colors = new Set();
    products.forEach(p => {
      if (p.color) {
        p.color.split(',').forEach(c => {
          const trimmed = c.trim();
          if (trimmed) colors.add(trimmed);
        });
      }
    });
    return Array.from(colors).sort((a, b) => a.localeCompare(b, 'uk'));
  }, [products]);

  // Reset subcategory when category changes
  useEffect(() => {
    setSelectedSubcategory(null);
  }, [selectedCategory]);

  const filteredProducts = products.filter(p => {
    // Smart search - checks name, SKU, category, subcategory, color, material
    const matchesSearch = !searchTerm || 
      p.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.sku?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.category_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.subcategory_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.color?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.material?.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesCategory = !selectedCategory || p.category_name === selectedCategory;
    
    const matchesSubcategory = !selectedSubcategory || p.subcategory_name === selectedSubcategory;
    
    const matchesColor = !selectedColor || 
      (p.color && p.color.split(',').some(c => c.trim() === selectedColor));
    
    return matchesSearch && matchesCategory && matchesSubcategory && matchesColor;
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
      <header className="fd-header sticky top-0 z-10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            {/* Logo */}
            <img 
              src="/logo.svg" 
              alt="FarforDecor Logo" 
              style={{
                height: '40px',
                width: 'auto'
              }}
            />
            {/* Company Name */}
            <h1 className="text-xl font-bold" style={{color: '#333', letterSpacing: '0.03em'}}>
              FarforDecorOrenda
            </h1>
            <div className="w-px h-5" style={{background: '#e6e6e6'}}></div>
            <span className="text-xs" style={{color: '#999', textTransform: 'uppercase'}}>Event Planning Platform</span>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/profile')}
              className="fd-btn fd-btn-secondary"
            >
              Мої мудборди
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

      <div className="flex h-[calc(100vh-73px)]" style={{background: '#f3f3f3'}}>
        {/* Catalog Section */}
        <div className={`flex-1 overflow-auto transition-all duration-300 ${isSidePanelOpen ? 'mr-96' : ''}`}>
          <div className="p-8">
            {/* Search and Filters */}
            <div className="mb-6 space-y-4">
              <div style={{maxWidth: '600px'}}>
                <input
                  type="text"
                  placeholder="Розумний пошук: назва, артикул, категорія, колір, матеріал..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '12px 15px',
                    border: '1px solid #e5ecf3',
                    borderRadius: '4px',
                    fontSize: '14px',
                    fontFamily: 'Montserrat, Arial, sans-serif',
                    color: '#838182',
                    transition: 'all 0.3s ease'
                  }}
                />
              </div>
              
              <ProductFilters
                categories={allCategories}
                subcategories={availableSubcategories}
                colors={availableColors}
                selectedCategory={selectedCategory}
                selectedSubcategory={selectedSubcategory}
                selectedColor={selectedColor}
                onCategoryChange={setSelectedCategory}
                onSubcategoryChange={setSelectedSubcategory}
                onColorChange={setSelectedColor}
              />
            </div>

            {/* Products Count */}
            <div className="mb-4 flex items-center justify-between">
              <div className="text-sm" style={{color: '#666'}}>
                Знайдено товарів: <span style={{fontWeight: 'bold', color: '#333'}}>{filteredProducts.length}</span>
                {(selectedCategory || selectedSubcategory || selectedColor || searchTerm) && (
                  <span style={{color: '#999'}}> (з {products.length} всього)</span>
                )}
              </div>
            </div>

            {/* Products Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
              {filteredProducts.map((product) => (
                <ProductCard
                  key={product.product_id}
                  product={product}
                  onAddToBoard={handleAddToBoard}
                  boardDates={{
                    startDate: activeBoard?.rental_start_date,
                    endDate: activeBoard?.rental_end_date,
                  }}
                />
              ))}
            </div>

            {/* Load More Button */}
            {hasMore && filteredProducts.length > 0 && !searchTerm && !selectedCategory && !selectedSubcategory && !selectedColor && (
              <div className="text-center mt-8">
                <button
                  onClick={loadMoreProducts}
                  disabled={loadingMore}
                  className="fd-btn fd-btn-black disabled:opacity-50"
                  style={{minWidth: '200px'}}
                >
                  {loadingMore ? 'Завантаження...' : 'Завантажити більше'}
                </button>
              </div>
            )}

            {filteredProducts.length === 0 && (
              <div className="text-center py-12 text-gray-500">
                Товари не знайдено
              </div>
            )}
          </div>
        </div>

        {/* Side Panel - Event Board */}
        {isSidePanelOpen && (
          <div className="w-96 fd-side-panel flex flex-col fixed right-0 h-[calc(100vh-73px)]">
            {/* Compact Panel Header - Оптимізовано */}
            <div className="fd-side-header flex items-center justify-between" style={{padding: '14px 18px 10px', marginBottom: '0', borderBottom: '1px solid #f0f0f0'}}>
              <h2 className="fd-side-title" style={{fontSize: '13px'}}>МІЙ ІВЕНТ</h2>
              <button
                onClick={toggleSidePanel}
                className="fd-btn"
                style={{fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#999', background: 'none', border: 'none', padding: 0}}
              >
                згорнути
              </button>
            </div>

            {/* Compact Board Selector - Оптимізовано */}
            <div style={{padding: '12px 18px 12px', background: '#fafafa'}}>
              <select
                value={activeBoard?.id || ''}
                onChange={(e) => {
                  const board = boards.find(b => b.id === e.target.value);
                  setActiveBoard(board);
                }}
                className="w-full fd-select mb-2"
                style={{fontSize: '12px', padding: '8px 12px'}}
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
                className="w-full fd-btn fd-btn-primary"
                style={{padding: '8px 12px', fontSize: '11px'}}
              >
                + створити івент
              </button>
            </div>

            {/* Board Content */}
            {activeBoard ? (
              <>
                {/* Compact Board Info - Оптимізовано */}
                <div style={{padding: '12px 18px', borderBottom: '1px solid #f0f0f0'}}>
                  {/* Cover Image - Менше */}
                  {activeBoard.cover_image && (
                    <div style={{
                      width: '100%',
                      height: '80px',
                      borderRadius: '4px',
                      overflow: 'hidden',
                      marginBottom: '10px',
                      background: '#f5f5f5'
                    }}>
                      <img 
                        src={activeBoard.cover_image} 
                        alt={activeBoard.board_name}
                        style={{
                          width: '100%',
                          height: '100%',
                          objectFit: 'cover'
                        }}
                        onError={(e) => {
                          e.target.style.display = 'none';
                        }}
                      />
                    </div>
                  )}
                  
                  <h3 className="font-bold mb-1" style={{fontSize: '13px', color: '#333', lineHeight: '1.3'}}>{activeBoard.board_name}</h3>
                  <p className="fd-label mb-2" style={{fontSize: '10px'}}>
                    {activeBoard.event_date || 'Дата не вказана'}
                  </p>
                  
                  {/* Компактний DateRangePicker */}
                  <DateRangePicker
                    startDate={activeBoard.rental_start_date}
                    endDate={activeBoard.rental_end_date}
                    onStartDateChange={(date) => handleUpdateBoardDates(activeBoard.id, date, activeBoard.rental_end_date)}
                    onEndDateChange={(date) => handleUpdateBoardDates(activeBoard.id, activeBoard.rental_start_date, date)}
                  />
                  
                  {activeBoard.rental_days && (
                    <p className="text-center mt-1" style={{fontSize: '10px', color: '#999'}}>
                      {activeBoard.rental_days} днів оренди
                    </p>
                  )}
                </div>

                {/* Items List - Більше місця для товарів */}
                <div className="flex-1 overflow-auto" style={{padding: '12px 12px'}}>
                  {activeBoard.items && activeBoard.items.length > 0 ? (
                    <div className="space-y-2">
                      {activeBoard.items.map((item) => (
                        <BoardItemCard
                          key={item.id}
                          item={item}
                          boardDates={{
                            startDate: activeBoard.rental_start_date,
                            endDate: activeBoard.rental_end_date,
                          }}
                          rentalDays={activeBoard.rental_days}
                          onUpdate={handleUpdateItem}
                          onRemove={handleRemoveFromBoard}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8 text-gray-500">
                      <p style={{fontSize: '14px', fontWeight: '600', marginBottom: '6px'}}>Мудборд порожній</p>
                      <p style={{fontSize: '12px'}}>Додайте товари з каталогу</p>
                    </div>
                  )}
                </div>

                {/* Compact Summary - Оптимізовано */}
                <div style={{padding: '14px 18px', borderTop: '1px solid #f0f0f0', background: '#fafafa'}}>
                  {/* Інфо в один рядок */}
                  <div className="flex justify-between items-center mb-3" style={{fontSize: '11px'}}>
                    <span style={{color: '#666'}}>
                      Позицій: <strong style={{color: '#333'}}>{activeBoard.items?.length || 0}</strong>
                    </span>
                    <span style={{color: '#666'}}>
                      Разом: <strong style={{color: '#333', fontSize: '13px'}}>₴{calculateBoardTotal().toFixed(2)}</strong>
                    </span>
                  </div>
                  
                  {/* Кнопки */}
                  <button 
                    onClick={() => setShowCanvas(true)}
                    className="w-full fd-btn fd-btn-primary mb-2"
                    disabled={!activeBoard.items || activeBoard.items.length === 0}
                    style={{padding: '9px 12px', fontSize: '11px'}}
                  >
                    Візуальний мудборд
                  </button>
                  <button 
                    className="w-full fd-btn fd-btn-black" 
                    style={{padding: '9px 12px', fontSize: '11px'}}
                  >
                    Оформити замовлення
                  </button>
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center">
                <div className="fd-empty" style={{textAlign: 'center'}}>
                  <div style={{fontSize: '16px', fontWeight: '600', color: '#999', marginBottom: '12px'}}>
                    Створіть перший мудборд
                  </div>
                  <div className="fd-empty-text" style={{fontSize: '13px', color: '#999', lineHeight: '1.6'}}>
                    Додавайте позиції з каталогу ліворуч,<br/>щоб зібрати підбірку для клієнта
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Toggle button when panel is closed */}
        {!isSidePanelOpen && (
          <button
            onClick={toggleSidePanel}
            className="fixed right-0 top-1/2 transform -translate-y-1/2 fd-btn-black px-3 py-10 z-20"
            style={{boxShadow: '0 2px 8px rgba(0,0,0,0.1)', borderRadius: '4px 0 0 4px'}}
          >
            <span className="transform rotate-90 inline-block fd-uppercase">Мудборд</span>
          </button>
        )}
      </div>

      {/* New Board Modal */}
      {showNewBoardModal && (
        <CreateBoardModal
          onClose={() => setShowNewBoardModal(false)}
          onCreateBoard={handleCreateBoard}
        />
      )}

      {/* Moodboard Canvas */}
      {showCanvas && activeBoard && (
        <MoodboardCanvas
          board={activeBoard}
          onClose={() => setShowCanvas(false)}
          onSave={handleSaveCanvas}
        />
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
              <Route
                path="/profile"
                element={
                  <ProtectedRoute>
                    <UserProfile />
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
