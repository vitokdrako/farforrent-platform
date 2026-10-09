import api from './axios';

export const chatAPI = {
  async list(orderId) {
    const { data } = await api.get(`/event/orders/${orderId}/chat/messages`);
    return data.messages || [];
  },
  async send(orderId, message, attachmentUrl = null) {
    const { data } = await api.post(`/event/orders/${orderId}/chat/messages`, {
      message,
      attachment_url: attachmentUrl,
    });
    return data.messages || [];
  },
  async unreadCount(orderId) {
    const { data } = await api.get(`/event/orders/${orderId}/chat/unread_count`);
    return data.unread || 0;
  },
};

export const documentApprovalAPI = {
  async approve(orderId, documentId, signerName = null) {
    const { data } = await api.post(
      `/event/orders/${orderId}/documents/${documentId}/approve`,
      signerName ? { signer_name: signerName } : {}
    );
    return data;
  },
};

export default chatAPI;
