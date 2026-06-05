import api from './axios';

export const authAPI = {
  register: async (data) => {
    const response = await api.post('/event/auth/register', data);
    return response.data;
  },

  login: async (email, password) => {
    const response = await api.post('/event/auth/login', { email, password });
    return response.data;
  },

  getMe: async () => {
    const response = await api.get('/event/auth/me');
    return response.data;
  },
};