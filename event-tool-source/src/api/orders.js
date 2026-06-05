import api from './axios';

export const ordersApi = {
  // Список моїх замовлень
  list: async () => {
    const res = await api.get('/event/orders');
    return res.data;
  },
  // Деталі замовлення
  get: async (orderId) => {
    const res = await api.get(`/event/orders/${orderId}`);
    return res.data;
  },
  // Документи замовлення
  documents: async (orderId) => {
    const res = await api.get(`/event/orders/${orderId}/documents`);
    return res.data;
  },
};
