import api from './axios';

export const favoritesAPI = {
  async list() {
    const { data } = await api.get('/event/favorites');
    return data.product_ids || [];
  },
  async listProducts() {
    const { data } = await api.get('/event/favorites/products');
    return data.products || [];
  },
  async add(productId) {
    const { data } = await api.post(`/event/favorites/${productId}`);
    return data;
  },
  async remove(productId) {
    const { data } = await api.delete(`/event/favorites/${productId}`);
    return data;
  },
};

export default favoritesAPI;
