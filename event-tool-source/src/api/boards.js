import api from './axios';

export const boardsAPI = {
  getBoards: async (status) => {
    const params = status ? { status } : {};
    const response = await api.get('/event/boards', { params });
    return response.data;
  },

  getBoard: async (id) => {
    const response = await api.get(`/event/boards/${id}`);
    return response.data;
  },

  createBoard: async (data) => {
    const response = await api.post('/event/boards', data);
    return response.data;
  },

  updateBoard: async (id, data) => {
    const response = await api.patch(`/event/boards/${id}`, data);
    return response.data;
  },

  deleteBoard: async (id) => {
    await api.delete(`/event/boards/${id}`);
  },

  addItem: async (boardId, data) => {
    const response = await api.post(`/event/boards/${boardId}/items`, data);
    return response.data;
  },

  updateItem: async (boardId, itemId, data) => {
    const response = await api.patch(`/event/boards/${boardId}/items/${itemId}`, data);
    return response.data;
  },

  deleteItem: async (boardId, itemId) => {
    await api.delete(`/event/boards/${boardId}/items/${itemId}`);
  },
};
