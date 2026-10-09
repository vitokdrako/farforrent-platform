/**
 * Finance API Service
 */
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

const mockDashboard = {
  period: 'month',
  metrics: { net_profit: 4700, rent_revenue: 5000, damage_compensation: 500, operating_expenses: 800, cash_balance: 6200 },
  deposits: { held: 2000, used: 500, refunded: 0, available_to_refund: 1500 },
};

const mockAccounts = [
  { id: 1, code: 'CASH', name: 'Каса', kind: 'asset', balance: 1200 },
  { id: 2, code: 'BANK', name: 'Банк', kind: 'asset', balance: 5000 },
  { id: 3, code: 'RENT_REV', name: 'Дохід оренди', kind: 'income', balance: 5000 },
];

function getAuthHeaders() {
  const token = localStorage.getItem('token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
}

async function fetchWithFallback(endpoint, mockData, options) {
  try {
    const response = await fetch(`${BACKEND_URL}${endpoint}`, {
      ...options,
      headers: { 
        'Content-Type': 'application/json', 
        ...getAuthHeaders(),
        ...options?.headers 
      },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    return { data, error: null, isMock: false };
  } catch (err) {
    console.warn(`Finance API fallback for ${endpoint}:`, err);
    return { data: mockData, error: String(err), isMock: true };
  }
}

export const financeApi = {
  getDashboard: async (period = 'month') => fetchWithFallback(`/api/finance/dashboard?period=${period}`, mockDashboard),
  getAccounts: async () => fetchWithFallback('/api/finance/accounts', mockAccounts),
  getCategories: async (type) => {
    const url = type ? `/api/finance/categories?type=${type}` : '/api/finance/categories';
    return fetchWithFallback(url, []);
  },
  getPayments: async (filters = {}) => {
    let url = '/api/finance/payments';
    const params = new URLSearchParams();
    if (filters.order_id) params.append('order_id', String(filters.order_id));
    if (filters.payment_type) params.append('payment_type', filters.payment_type);
    if (params.toString()) url += `?${params}`;
    return fetchWithFallback(url, { payments: [] });
  },
  createPayment: async (data) => fetchWithFallback('/api/finance/payments', null, { method: 'POST', body: JSON.stringify(data) }),
  getExpenses: async (filters = {}) => {
    let url = '/api/finance/expenses';
    const params = new URLSearchParams();
    if (filters.category_code) params.append('category_code', filters.category_code);
    if (params.toString()) url += `?${params}`;
    return fetchWithFallback(url, { expenses: [] });
  },
  createExpense: async (data) => fetchWithFallback('/api/finance/expenses', null, { method: 'POST', body: JSON.stringify(data) }),
  getDeposits: async (status) => {
    const url = status ? `/api/finance/deposits?status=${status}` : '/api/finance/deposits';
    return fetchWithFallback(url, []);
  },
  useDeposit: async (depositId, amount, note, damageCaseId) => {
    const params = new URLSearchParams({ amount: String(amount) });
    if (note) params.append('note', note);
    if (damageCaseId) params.append('damage_case_id', String(damageCaseId));
    return fetchWithFallback(`/api/finance/deposits/${depositId}/use?${params}`, null, { method: 'POST' });
  },
  refundDeposit: async (depositId, amount, method = 'cash', note) => {
    const params = new URLSearchParams({ amount: String(amount), method });
    if (note) params.append('note', note);
    return fetchWithFallback(`/api/finance/deposits/${depositId}/refund?${params}`, null, { method: 'POST' });
  },
  getLedger: async (filters = {}) => {
    let url = '/api/finance/ledger';
    const params = new URLSearchParams();
    if (filters.tx_type) params.append('tx_type', filters.tx_type);
    if (filters.account_code) params.append('account_code', filters.account_code);
    if (params.toString()) url += `?${params}`;
    return fetchWithFallback(url, { transactions: [] });
  },

  // Vendors
  getVendors: async (params = {}) => {
    return fetchWithFallback('/api/finance/vendors', { vendors: [] });
  },
  createVendor: async (data) => {
    return fetchWithFallback('/api/finance/vendors', null, { method: 'POST', body: JSON.stringify(data) });
  },
  updateVendor: async (vendorId, data) => {
    return fetchWithFallback(`/api/finance/vendors/${vendorId}`, null, { method: 'PUT', body: JSON.stringify(data) });
  },

  // Employees
  getEmployees: async (params = {}) => {
    return fetchWithFallback('/api/finance/employees', { employees: [] });
  },
  createEmployee: async (data) => {
    return fetchWithFallback('/api/finance/employees', null, { method: 'POST', body: JSON.stringify(data) });
  },

  // Payroll
  getPayroll: async (params = {}) => {
    return fetchWithFallback('/api/finance/payroll', { payroll: [] });
  },
  createPayroll: async (data) => {
    return fetchWithFallback('/api/finance/payroll', null, { method: 'POST', body: JSON.stringify(data) });
  },
  payPayroll: async (payrollId) => {
    return fetchWithFallback(`/api/finance/payroll/${payrollId}/pay`, null, { method: 'POST', body: JSON.stringify({}) });
  },

  // Deposits with currency
  createDepositWithCurrency: async (data) => {
    return fetchWithFallback('/api/finance/deposits/create', null, { method: 'POST', body: JSON.stringify(data) });
  },
};

export default financeApi;
