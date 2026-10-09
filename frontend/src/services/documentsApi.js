/**
 * Documents API Service
 */
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

export const documentsApi = {
  getTypes: async (entityType) => {
    try {
      const url = entityType ? `${BACKEND_URL}/api/documents/types/${entityType}` : `${BACKEND_URL}/api/documents/types`;
      const response = await fetch(url);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (err) {
      console.error('Documents API error:', err);
      return [];
    }
  },

  getEntityDocuments: async (entityType, entityId) => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/documents/entity/${entityType}/${entityId}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (err) {
      console.error('Documents API error:', err);
      return { documents: [], available_types: [] };
    }
  },

  generate: async (docType, entityId, options = {}) => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${BACKEND_URL}/api/documents/generate`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          doc_type: docType,
          entity_id: String(entityId),
          format: 'html',
          options: options,
        }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (err) {
      console.error('Documents API error:', err);
      return { success: false, error: String(err) };
    }
  },

  getPreviewUrl: (documentId) => `${BACKEND_URL}/api/documents/${documentId}/preview`,
  getPdfUrl: (documentId) => `${BACKEND_URL}/api/documents/${documentId}/pdf`,
  downloadPdf: (documentId) => window.open(`${BACKEND_URL}/api/documents/${documentId}/pdf`, '_blank'),
  openPreview: (documentId) => window.open(`${BACKEND_URL}/api/documents/${documentId}/preview`, '_blank'),
};

export default documentsApi;
