import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
const API_PREFIX = process.env.REACT_APP_API_PREFIX || '/api';

const apiClient = axios.create({
  baseURL: `${BACKEND_URL}${API_PREFIX}`,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 0, // Без обмежень
});

// Interceptor для автоматичного додавання токена авторизації
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ✅ Response Interceptor - редірект на логін при протухлому токені
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const errorDetail = error.response?.data?.detail || '';
      
      // Якщо токен протух або невалідний - редірект на логін
      if (errorDetail.includes('expired') || errorDetail.includes('Invalid token') || errorDetail.includes('Token')) {
        console.warn('🔒 Сесія закінчилась, перенаправлення на логін...');
        
        // Очищаємо localStorage
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        
        // Редірект на логін (якщо ще не там), з урахуванням basename (PUBLIC_URL)
        const base = process.env.PUBLIC_URL || '';
        if (!window.location.pathname.includes('/login')) {
          window.location.href = `${base}/login?session_expired=true`;
        }
      }
    }
    return Promise.reject(error);
  }
);

// Warehouse API
export const warehouseAPI = {
  // Dashboard
  getDashboard: async (date?: string) => {
    const params = date ? { date } : {};
    const response = await apiClient.get('/warehouse/dashboard', { params });
    return response.data;
  },

  // Calendar
  getCalendar: async (fromDate: string, toDate: string, view: 'day' | 'week' = 'day') => {
    const response = await apiClient.get('/warehouse/calendar', {
      params: { from_date: fromDate, to_date: toDate, view }
    });
    return response.data;
  },

  // Zones
  getZones: async () => {
    const response = await apiClient.get('/warehouse/zones');
    return response.data;
  },

  // Move event (drag & drop)
  moveEvent: async (cardId: string, type: 'issue' | 'return', date: string, time: string) => {
    const response = await apiClient.put(`/warehouse/calendar/${cardId}/move`, {
      type,
      date,
      time
    });
    return response.data;
  },
};

// Issue Cards API
export const issueCardsAPI = {
  getAll: async () => {
    const response = await apiClient.get('/issue-cards');
    return response.data;
  },
  
  getById: async (id: string) => {
    const response = await apiClient.get(`/issue-cards/${id}`);
    return response.data;
  },
};

// Return Cards API
export const returnCardsAPI = {
  getAll: async () => {
    const response = await apiClient.get('/return-cards');
    return response.data;
  },
  
  getById: async (id: string) => {
    const response = await apiClient.get(`/return-cards/${id}`);
    return response.data;
  },
};

// Catalog API
export const catalogAPI = {
  getAll: async (search?: string) => {
    const params = search ? { search } : {};
    const response = await apiClient.get('/catalog', { params });
    return response.data;
  },
  
  checkAvailability: async (sku: string, fromDate: string, toDate: string, quantity: number = 1) => {
    const response = await apiClient.get(`/catalog/check-availability/${sku}`, {
      params: { from_date: fromDate, to_date: toDate, quantity }
    });
    return response.data;
  },
};

// Damages API
export const damagesAPI = {
  getAll: async (status?: string) => {
    const params = status ? { status } : {};
    const response = await apiClient.get('/damages', { params });
    return response.data;
  },
  
  getById: async (id: string) => {
    const response = await apiClient.get(`/damages/${id}`);
    return response.data;
  },
};

// Tasks API
export const tasksAPI = {
  getAll: async (params?: { status?: string; my_tasks?: boolean; assigned_to_id?: number }) => {
    const response = await apiClient.get('/tasks', { params });
    return response.data;
  },
  
  // ✅ Отримати список працівників для призначення
  getStaff: async () => {
    const response = await apiClient.get('/tasks/staff');
    return response.data;
  },
  
  // ✅ Статистика по користувачах
  getStatsByUser: async () => {
    const response = await apiClient.get('/tasks/stats/by-user');
    return response.data;
  },
  
  create: async (taskData: any) => {
    const response = await apiClient.post('/tasks', taskData);
    return response.data;
  },
  
  update: async (id: string, taskData: any) => {
    const response = await apiClient.put(`/tasks/${id}`, taskData);
    return response.data;
  },

  delete: async (id: string) => {
    const response = await apiClient.delete(`/tasks/${id}`);
    return response.data;
  },
};

// Packing Cabinet API
export const packingAPI = {
  // Отримати список замовлень в комплектації
  getOrders: async (status?: string, zone?: string, search?: string) => {
    const params = new URLSearchParams();
    if (status && status !== 'all') params.append('status', status);
    if (zone && zone !== 'all') params.append('zone', zone);
    if (search) params.append('search', search);
    
    const response = await apiClient.get(`/warehouse/packing-orders?${params}`);
    return response.data;
  },

  // Отримати деталі замовлення
  getOrderDetails: async (orderId: string) => {
    const response = await apiClient.get(`/warehouse/packing-orders/${orderId}`);
    return response.data;
  },

  // Оновити прогрес комплектації
  updateProgress: async (orderId: string, progressData: { progressPack?: number; notes?: string }) => {
    const response = await apiClient.put(`/warehouse/packing-orders/${orderId}/progress`, progressData);
    return response.data;
  },

  // Позначити як готове до видачі
  markReady: async (orderId: string) => {
    const response = await apiClient.put(`/warehouse/packing-orders/${orderId}/mark-ready`);
    return response.data;
  },

  // Створити чекліст прийому
  createReturnChecklist: async (orderId: string, notes: string) => {
    const response = await apiClient.post(`/warehouse/packing-orders/${orderId}/return-checklist`, { notes });
    return response.data;
  },
};

// Extended Catalog API
export const extendedCatalogAPI = {
  // Пошук товарів
  search: async (params: {
    q?: string;
    color?: string;
    material?: string;
    size?: string;
    category?: string;
    subcategory?: string;
    tags?: string[];
  }) => {
    const response = await apiClient.get('/extended-catalog/search', { params });
    return response.data;
  },

  // Деталі товару
  getDetails: async (productId: number) => {
    const response = await apiClient.get(`/extended-catalog/products/${productId}`);
    return response.data;
  },

  // Історія переміщень
  getHistory: async (productId: number) => {
    const response = await apiClient.get(`/extended-catalog/products/${productId}/history`);
    return response.data;
  },
};

// Audit Cabinet API (Reaudit)
export const auditAPI = {
  // Отримати список товарів для переобліку
  getItems: async (params: {
    q?: string;
    status?: string;
    zone?: string;
    category?: string;
    subcategory?: string;
    sort_by?: string;
  }) => {
    const response = await apiClient.get('/audit/items', { params });
    return response.data;
  },

  // Отримати деталі товару
  getItemDetails: async (itemId: string) => {
    const response = await apiClient.get(`/audit/items/${itemId}`);
    return response.data;
  },

  // Отримати статистику
  getStats: async () => {
    const response = await apiClient.get('/audit/stats');
    return response.data;
  },

  // Отримати історію товару
  getItemHistory: async (itemId: string) => {
    const response = await apiClient.get(`/audit/items/${itemId}/history`);
    return response.data;
  },

  // Отримати категорії
  getCategories: async () => {
    const response = await apiClient.get('/audit/categories');
    return response.data;
  },

  // Підрахувати lifecycle метрики
  calculateLifecycle: async (productId: number) => {
    const response = await apiClient.post(`/audit/calculate-lifecycle/${productId}`);
    return response.data;
  },

  // Оновити кількість
  updateQuantity: async (itemId: string, qty: number, actor?: string) => {
    const response = await apiClient.put(`/audit/items/${itemId}/quantity`, { qty, actor });
    return response.data;
  },

  // Оновити локацію
  updateLocation: async (itemId: string, zone: string, location: string, actor?: string) => {
    const response = await apiClient.put(`/audit/items/${itemId}/location`, { zone, location, actor });
    return response.data;
  },

  // Оновити статус
  updateStatus: async (itemId: string, status: string, actor?: string) => {
    const response = await apiClient.put(`/audit/items/${itemId}/status`, { status, actor });
    return response.data;
  },

  // Оновити нотатки
  updateNotes: async (itemId: string, notes: string) => {
    const response = await apiClient.put(`/audit/items/${itemId}/notes`, { notes });
    return response.data;
  },

  // Масове редагування всіх даних
  editAll: async (itemId: string, data: {
    name?: string;
    qty?: number;
    zone?: string;
    location?: string;
    status?: string;
    notes?: string;
    actor?: string;
  }) => {
    const response = await apiClient.put(`/audit/items/${itemId}/edit-all`, data);
    return response.data;
  },

  // Action buttons
  sendToWash: async (itemId: string, notes?: string, actor?: string) => {
    const response = await apiClient.post(`/audit/items/${itemId}/send-to-wash`, { notes, actor });
    return response.data;
  },

  sendToRestoration: async (itemId: string, notes?: string, actor?: string) => {
    const response = await apiClient.post(`/audit/items/${itemId}/send-to-restoration`, { notes, actor });
    return response.data;
  },

  createDamageCase: async (itemId: string, data: {
    damage_type?: string;
    damage_cost?: number;
    notes?: string;
    actor?: string;
  }) => {
    const response = await apiClient.post(`/audit/items/${itemId}/create-damage-case`, data);
    return response.data;
  },

  // Зафіксувати переоблік
  markAudited: async (itemId: string, data: {
    audited_by?: string;
    audit_status?: string;
    notes?: string;
    next_audit_days?: number;
  }) => {
    const response = await apiClient.put(`/audit/items/${itemId}/audit`, data);
    return response.data;
  },

  // Історія оренд товару
  getRentalHistory: async (itemId: string) => {
    const response = await apiClient.get(`/audit/items/${itemId}/rental-history`);
    return response.data;
  },

  // Додати пошкодження
  addDamage: async (itemId: string, data: {
    damage_type?: string;
    description: string;
    severity: string;
    estimated_cost?: number;
    photo_url?: string;
    create_damage_case?: boolean;
    actor?: string;
  }) => {
    const response = await apiClient.post(`/audit/items/${itemId}/add-damage`, data);
    return response.data;
  },

  // Отримати історію пошкоджень
  getDamages: async (itemId: string) => {
    const response = await apiClient.get(`/audit/items/${itemId}/damages`);
    return response.data;
  },
};

export default apiClient;
