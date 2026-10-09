const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  // Only proxy API requests to the backend
  app.use(
    '/api',
    createProxyMiddleware({
      target: 'http://localhost:8001',
      changeOrigin: true,
    })
  );
  
  // Proxy uploads (backend serves uploaded files)
  app.use(
    '/uploads',
    createProxyMiddleware({
      target: 'http://localhost:8001',
      changeOrigin: true
    })
  );
  
  // NOTE: Do NOT proxy /static - this is served by webpack dev server
};