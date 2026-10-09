import api from './axios';

export const productsAPI = {
  getProducts: async (params = {}) => {
    const response = await api.get('/event/products', { params });
    return response.data;
  },

  getProduct: async (id) => {
    const response = await api.get(`/event/products/${id}`);
    return response.data;
  },

  checkAvailability: async (data) => {
    const response = await api.post('/event/products/check-availability', data);
    return response.data;
  },
};
