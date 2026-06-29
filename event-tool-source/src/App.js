import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';
import { AuthProvider, useAuth } from './context/AuthContext';
import { BoardProvider, useBoard } from './context/BoardContext';
import { FavoritesProvider } from './context/FavoritesContext';
import DateRangePicker from './components/DateRangePicker';
import { calculateRentalDays } from './utils/rentalDays';
import ProductCard from './components/ProductCard';
import ProductDetailsModal from './components/ProductDetailsModal';
import CheckoutModal from './components/CheckoutModal';
import CategoryChips from './components/CategoryChips';
import MobileBottomNav from './components/MobileBottomNav';
import MobileSearchFab from './components/MobileSearchFab';
import BoardItemCard from './components/BoardItemCard';
import MoodboardCanvas from './components/MoodboardCanvas';
import ProductFilters from './components/ProductFilters';
import CreateBoardModal from './components/CreateBoardModal';
import UserProfile from './components/UserProfile';
import RentalRules from './pages/RentalRules';
import FavoritesPage from './pages/FavoritesPage';
import ClientChatPage from './pages/ClientChatPage';
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
  const [allColors, setAllColors] = useState([]);
  const [boards, setBoards] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [selectedSubcategory, setSelectedSubcategory] = useState(null);
  const [selectedColor, setSelectedColor] = useState(null);
  const [minQuantity, setMinQuantity] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [showNewBoardModal, setShowNewBoardModal] = useState(false);
  const [showCanvas, setShowCanvas] = useState(false);
  const [detailsProductId, setDetailsProductId] = useState(null);
  const [showCheckout, setShowCheckout] = useState(false);

  useEffect(() => {
    loadInitialData();
  }, []);

  // Перезавантажуємо товари коли користувач ВРУЧНУ змінив дати оренди (але не при першій ініціалізації)
  const initialDatesRef = React.useRef(null);
  useEffect(() => {
    if (!activeBoard?.rental_start_date || !activeBoard?.rental_end_date) return;
    const key = `${activeBoard.rental_start_date}|${activeBoard.rental_end_date}`;
    // Перший раз — лише запам'ятовуємо (loadInitialData вже завантажив products з цими датами)
    if (initialDatesRef.current === null) {
      initialDatesRef.current = key;
      return;
    }
    if (initialDatesRef.current === key) return;
    initialDatesRef.current = key;
    reloadProductsForDates(activeBoard.rental_start_date, activeBoard.rental_end_date);
  }, [activeBoard?.rental_start_date, activeBoard?.rental_end_date]);

  // Sync body.sidebar-open class for mobile CSS rules (hide chips & FAB while moodboard open)
  useEffect(() => {
    if (isSidePanelOpen) {
      document.body.classList.add('sidebar-open');
    } else {
      document.body.classList.remove('sidebar-open');
    }
    return () => document.body.classList.remove('sidebar-open');
  }, [isSidePanelOpen]);

  // Інфініт-скрол: автозавантажуємо більше товарів коли користувач прокручує до низу
  const loadMoreSentinelRef = React.useRef(null);
  useEffect(() => {
    const node = loadMoreSentinelRef.current;
    if (!node) return;
    const hasFilters = !!(searchTerm || selectedCategory || selectedSubcategory || selectedColor);
    if (hasFilters || !hasMore || loadingMore) return;

    const observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting) {
        loadMoreProducts();
      }
    }, { rootMargin: '300px 0px' });
    observer.observe(node);
    return () => observer.disconnect();
  }, [hasMore, loadingMore, products.length, searchTerm, selectedCategory, selectedSubcategory, selectedColor]);

  const buildProductsUrl = (skip, limit, dateFrom, dateTo) => {
    const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);
    return `/event/products?${params.toString()}`;
  };

  const reloadProductsForDates = async (dateFrom, dateTo) => {
    try {
      setLoading(true);
      const data = await api.get(buildProductsUrl(0, 100, dateFrom, dateTo)).then(r => r.data);
      setProducts(Array.isArray(data) ? data : []);
      setHasMore(Array.isArray(data) && data.length === 100);
    } catch (e) {
      console.error('Failed to reload products for dates:', e);
    } finally {
      setLoading(false);
    }
  };

  const loadInitialData = async () => {
    setLoading(true);
    try {
      // 1) Спочатку — boards/categories/subcategories паралельно (знаємо дати найактивнішого борду)
      const [categoriesData, subcategoriesData, boardsData] = await Promise.all([
        api.get('/event/categories').then(r => r.data),
        api.get('/event/subcategories').then(r => r.data),
        api.get('/event/boards').then(r => r.data),
      ]);

      const categoriesList = Array.isArray(categoriesData)
        ? categoriesData
        : (categoriesData?.categories || []);

      setCategories(categoriesList);
      setAllSubcategories(Array.isArray(subcategoriesData) ? subcategoriesData : []);
      setAllColors(Array.isArray(categoriesData?.colors) ? categoriesData.colors : []);
      setBoards(Array.isArray(boardsData) ? boardsData : []);

      const initialBoard = (Array.isArray(boardsData) && boardsData.length > 0) ? boardsData[0] : null;
      if (initialBoard) {
        setActiveBoard(initialBoard);
      }

      // 2) Products завантажуємо одразу з датами активного борду — щоб НЕ було подвійного fetch
      const productsUrl = buildProductsUrl(
        0,
        100,
        initialBoard?.rental_start_date,
        initialBoard?.rental_end_date
      );
      const productsData = await api.get(productsUrl).then(r => r.data);
      setProducts(Array.isArray(productsData) ? productsData : []);
      setHasMore(Array.isArray(productsData) && productsData.length === 100);
    } catch (error) {
      console.error('Failed to load data:', error);
    }
    setLoading(false);
  };

  const loadMoreProducts = async () => {
    setLoadingMore(true);
    try {
      const currentCount = products.length;
      const moreProducts = await api.get(
        buildProductsUrl(currentCount, 100, activeBoard?.rental_start_date, activeBoard?.rental_end_date)
      ).then(r => r.data);

      if (!Array.isArray(moreProducts) || moreProducts.length === 0) {
        setHasMore(false);
      } else {
        setProducts(prev => [...prev, ...moreProducts]);
      }
    } catch (error) {
      console.error('Failed to load more products:', error);
    }
    setLoadingMore(false);
  };

  const handleCreateBoard = async (boardData) => {
    try {
      const newBoard = await api.post('/event/boards', boardData).then(r => r.data);
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
      const updatedBoard = await api.patch(`/event/boards/${boardId}`, {
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
      const updatedBoard = await api.patch(`/event/boards/${activeBoard.id}`, {
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
      await api.post(`/event/boards/${activeBoard.id}/items`, {
        product_id: product.product_id,
        quantity: 1,
      });
      
      // Reload active board
      const updatedBoard = await api.get(`/event/boards/${activeBoard.id}`).then(r => r.data);
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
      await api.patch(`/event/boards/${activeBoard.id}/items/${itemId}`, updateData);
      
      // Reload active board
      const updatedBoard = await api.get(`/event/boards/${activeBoard.id}`).then(r => r.data);
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
      await api.delete(`/event/boards/${activeBoard.id}/items/${itemId}`);
      
      // Reload active board
      const updatedBoard = await api.get(`/event/boards/${activeBoard.id}`).then(r => r.data);
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

  // Get available subcategories — використовуємо повний список з API
  // (раніше брали з завантажених products, що обмежувало вибір до 100 товарів)
  const availableSubcategories = React.useMemo(() => {
    if (!selectedCategory) return [];

    // Пріоритет — підкатегорії з selectedCategory у дереві категорій
    const cat = (categories || []).find(c => c.name === selectedCategory);
    if (cat && Array.isArray(cat.subcategories) && cat.subcategories.length > 0) {
      return cat.subcategories.map(s => s.name).filter(Boolean).sort((a, b) => a.localeCompare(b, 'uk'));
    }

    // Fallback: з завантажених products
    const subcats = new Set();
    products.forEach(p => {
      if (p.category_name === selectedCategory && p.subcategory_name) {
        subcats.add(p.subcategory_name);
      }
    });
    return Array.from(subcats).sort((a, b) => a.localeCompare(b, 'uk'));
  }, [products, selectedCategory, categories]);

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

  // Серверсайд фільтрація — реагуємо на пошук/категорію/підкатегорію/колір з дебаунсом
  useEffect(() => {
    const handle = setTimeout(() => {
      const params = new URLSearchParams({ skip: '0', limit: '500' });
      if (searchTerm) params.set('search', searchTerm);
      if (selectedCategory) params.set('category_name', selectedCategory);
      if (selectedSubcategory) params.set('subcategory_name', selectedSubcategory);
      if (selectedColor) params.set('color', selectedColor);
      if (activeBoard?.rental_start_date) params.set('date_from', activeBoard.rental_start_date);
      if (activeBoard?.rental_end_date) params.set('date_to', activeBoard.rental_end_date);

      // Якщо немає жодного фільтру — не перевантажуємо, лишаємо завантажені 100
      const hasFilters = searchTerm || selectedCategory || selectedSubcategory || selectedColor;
      if (!hasFilters && !activeBoard?.rental_start_date) return;

      (async () => {
        // НЕ ставимо setLoading(true) — щоб сітка не мерехтіла при кожній буквці
        try {
          const r = await api.get(`/event/products?${params.toString()}`);
          const data = Array.isArray(r.data) ? r.data : [];
          setProducts(data);
          setHasMore(data.length === 500);
        } catch (e) {
          console.error('Filter fetch failed:', e);
        }
      })();
    }, 350); // debounce 350ms

    return () => clearTimeout(handle);
  }, [searchTerm, selectedCategory, selectedSubcategory, selectedColor]);

  const filteredProducts = products.filter(p => {
    // ВАЖЛИВО: при наявності searchTerm — сервер уже виконав розумний пошук (smart_search.py
    // з підтримкою опечаток, розмірних слів та усіх полів). Не фільтруємо повторно на клієнті
    // інакше відсіемо результати які знайшов smart-search але без точного збігу підрядка.
    const matchesCategory = !selectedCategory || p.category_name === selectedCategory;
    const matchesSubcategory = !selectedSubcategory || p.subcategory_name === selectedSubcategory;
    const matchesColor = !selectedColor ||
      (p.color && p.color.split(',').some(c => c.trim() === selectedColor));
    const matchesQuantity = !minQuantity || (Number(p.quantity) || 0) >= minQuantity;

    return matchesCategory && matchesSubcategory && matchesColor && matchesQuantity;
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
          <div
            className="flex items-center gap-4 cursor-pointer"
            onClick={() => navigate('/')}
            role="button"
            data-testid="header-home-link"
          >
            {/* Logo — клік повертає на головну */}
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
            <div className="w-px h-5 hide-on-mobile" style={{background: '#e6e6e6'}}></div>
            <span className="text-xs hide-on-mobile" style={{color: '#999', textTransform: 'uppercase'}}>Event Planning Platform</span>
          </div>
          <div className="flex items-center gap-4 header-actions-desktop">
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
            {/* Категорії + підкатегорії + кольори як chips — тільки на мобільному (через CSS).
                ВАЖЛИВО: рендеримо ПЕРШИМ, щоб на мобільному chips примикали до шапки без gap. */}
            <CategoryChips
              categories={categories}
              subcategories={availableSubcategories}
              colors={allColors}
              selectedCategory={selectedCategory}
              selectedSubcategory={selectedSubcategory}
              selectedColor={selectedColor}
              onSelectCategory={setSelectedCategory}
              onSelectSubcategory={setSelectedSubcategory}
              onSelectColor={setSelectedColor}
              minQuantity={minQuantity}
              onMinQuantityChange={setMinQuantity}
              maxQuantity={Math.max(
                100,
                ...products.map((p) => Number(p.quantity) || 0)
              )}
            />

            {/* Search and Filters — приховано на мобільному */}
            <div className="mb-6 space-y-4 desktop-only-filters">
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
                minQuantity={minQuantity}
                onMinQuantityChange={setMinQuantity}
                maxQuantity={Math.max(
                  100,
                  ...products.map((p) => Number(p.quantity) || 0)
                )}
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
                  onOpenDetails={(id) => setDetailsProductId(id)}
                />
              ))}
            </div>

            {/* Load More — інфініт-скрол sentinel + fallback кнопка */}
            {hasMore && filteredProducts.length > 0 && !searchTerm && !selectedCategory && !selectedSubcategory && !selectedColor && (
              <>
                <div ref={loadMoreSentinelRef} aria-hidden="true" style={{height: '1px'}} />
                <div className="text-center mt-8 mb-4">
                  {loadingMore ? (
                    <div className="inline-flex items-center gap-2" style={{color: '#666', fontSize: '13px'}}>
                      <span className="infinite-spinner" />
                      Завантаження товарів...
                    </div>
                  ) : (
                    <button
                      onClick={loadMoreProducts}
                      className="fd-btn fd-btn-black"
                      style={{minWidth: '200px'}}
                      data-testid="load-more-btn"
                    >
                      Завантажити більше
                    </button>
                  )}
                </div>
              </>
            )}

            {/* Лічильник завантаженого — корисний індикатор пагінації */}
            {filteredProducts.length > 0 && (
              <div className="text-center mt-2 mb-6" style={{fontSize: '11px', color: '#999'}} data-testid="pagination-counter">
                Показано {filteredProducts.length} {hasMore && !(searchTerm || selectedCategory || selectedSubcategory || selectedColor) ? '(прокрутіть, щоб завантажити ще)' : ''}
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
                  
                  {(() => {
                    const calc = calculateRentalDays(activeBoard.rental_start_date, activeBoard.rental_end_date);
                    if (!calc.days) return null;
                    return (
                      <p className="text-center mt-1" style={{fontSize: '11px', color: '#666', lineHeight: 1.3}}>
                        <strong>{calc.days} {calc.days === 1 ? 'доба' : calc.days < 5 ? 'доби' : 'діб'}</strong>
                        {' оренди'}
                        {!calc.isStandard && ' (орієнтовно)'}
                      </p>
                    );
                  })()}
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
                          rentalDays={calculateRentalDays(activeBoard.rental_start_date, activeBoard.rental_end_date).days}
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

                {/* Compact Summary — sticky bottom на мобільному */}
                <div className="sticky-checkout" style={{padding: '14px 18px', borderTop: '1px solid #f0f0f0', background: '#fafafa'}}>
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
                    onClick={() => setShowCheckout(true)}
                    disabled={!activeBoard.items || activeBoard.items.length === 0}
                    style={{padding: '9px 12px', fontSize: '11px'}}
                    data-testid="open-checkout-btn"
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

      {detailsProductId && (
        <ProductDetailsModal
          productId={detailsProductId}
          boardDates={{
            startDate: activeBoard?.rental_start_date,
            endDate: activeBoard?.rental_end_date,
          }}
          onClose={() => setDetailsProductId(null)}
          onAddToBoard={handleAddToBoard}
        />
      )}

      {showCheckout && activeBoard && (
        <CheckoutModal
          board={activeBoard}
          user={user}
          onClose={() => setShowCheckout(false)}
          onSuccess={(orderData) => {
            // Перезавантажуємо мудборди — конвертований буде відфільтровано (status='converted')
            api.get('/event/boards').then(r => {
              const arr = Array.isArray(r.data) ? r.data : [];
              setBoards(arr);
              // Активуємо інший мудборд або скидаємо
              if (arr.length > 0) {
                setActiveBoard(arr[0]);
              } else {
                setActiveBoard(null);
              }
            }).catch(() => {});
            // Закриваємо панель кошику автоматично
            if (isSidePanelOpen) toggleSidePanel();
            // Показуємо успіх
            if (orderData?.order_number) {
              alert(`✅ Замовлення ${orderData.order_number} створено! Перейдіть в "Кабінет" → "Мої замовлення".`);
            }
          }}
        />
      )}

      {/* Нижня навігація — тільки на мобільному (CSS) */}
      <MobileBottomNav
        onOpenCart={() => { if (!isSidePanelOpen) toggleSidePanel(); }}
        cartCount={activeBoard?.items?.length || 0}
      />

      {/* Плаваюча кнопка пошуку (лупа) — тільки на мобільному (CSS) */}
      <MobileSearchFab
        value={searchTerm}
        onChange={setSearchTerm}
        placeholder="Назва, артикул, категорія..."
      />
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

// Невеличкий бейдж версії — щоб одразу видно чи задеплоїлось
const BuildBadge = () => {
  const hash = process.env.REACT_APP_BUILD_HASH || 'dev';
  const time = process.env.REACT_APP_BUILD_TIME || '';
  return (
    <div
      data-testid="build-badge"
      style={{
        position: 'fixed',
        bottom: '4px',
        right: '6px',
        fontSize: '9px',
        color: 'rgba(0,0,0,0.35)',
        background: 'rgba(255,255,255,0.7)',
        padding: '2px 6px',
        borderRadius: '4px',
        fontFamily: 'monospace',
        pointerEvents: 'none',
        zIndex: 9999,
      }}
      title={time}
    >
      v: {hash}
    </div>
  );
};

// Main App
function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <FavoritesProvider>
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
                <Route
                  path="/favorites"
                  element={
                    <ProtectedRoute>
                      <FavoritesPage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/chat"
                  element={
                    <ProtectedRoute>
                      <ClientChatPage />
                    </ProtectedRoute>
                  }
                />
                <Route path="/rules" element={<RentalRules />} />
              </Routes>
              <BuildBadge />
            </BrowserRouter>
          </BoardProvider>
        </FavoritesProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
