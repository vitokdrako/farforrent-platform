/* eslint-disable */
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export default function SyncPanel() {
  const [syncInfo, setSyncInfo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [status, setStatus] = useState(null);
  
  useEffect(() => {
    loadSyncInfo();
    loadSyncStatus();
    
    // Auto-refresh every 30 seconds
    const interval = setInterval(() => {
      loadSyncInfo();
      loadSyncStatus();
    }, 30000);
    
    return () => clearInterval(interval);
  }, []);
  
  const loadSyncInfo = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${BACKEND_URL}/api/sync/last-sync`);
      setSyncInfo(response.data);
    } catch (error) {
      console.error('Error loading sync info:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const loadSyncStatus = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/sync/status`);
      setStatus(response.data);
    } catch (error) {
      console.error('Error loading sync status:', error);
    }
  };
  
  const triggerSync = async () => {
    if (!confirm('Запустити синхронізацію з OpenCart? Це може зайняти кілька хвилин.')) {
      return;
    }
    
    try {
      setSyncing(true);
      const response = await axios.post(`${BACKEND_URL}/api/sync/trigger`);
      alert('✅ ' + response.data.message);
      
      // Refresh after 5 seconds
      setTimeout(() => {
        loadSyncInfo();
        loadSyncStatus();
      }, 5000);
      
    } catch (error) {
      alert('❌ Помилка: ' + (error.response?.data?.detail || error.message));
    } finally {
      setSyncing(false);
    }
  };
  
  const formatDate = (dateStr) => {
    if (!dateStr) return 'Ніколи';
    const date = new Date(dateStr);
    return date.toLocaleString('uk-UA');
  };
  
  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">🔄 Синхронізація з OpenCart</h1>
      
      {/* Status Cards */}
      <div className="grid md:grid-cols-3 gap-4 mb-6">
        {/* Products */}
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-500 mb-1">📦 Товари</div>
          {syncInfo ? (
            <>
              <div className="text-2xl font-bold text-blue-600">{syncInfo.products.total_count.toLocaleString()}</div>
              <div className="text-xs text-gray-400 mt-2">
                Остання синхронізація:<br/>
                {formatDate(syncInfo.products.last_sync)}
              </div>
            </>
          ) : (
            <div className="text-gray-400">Завантаження...</div>
          )}
        </div>
        
        {/* Categories */}
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-500 mb-1">📁 Категорії</div>
          {syncInfo ? (
            <>
              <div className="text-2xl font-bold text-green-600">{syncInfo.categories.total_count}</div>
              <div className="text-xs text-gray-400 mt-2">
                Остання синхронізація:<br/>
                {formatDate(syncInfo.categories.last_sync)}
              </div>
            </>
          ) : (
            <div className="text-gray-400">Завантаження...</div>
          )}
        </div>
        
        {/* Orders */}
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-500 mb-1">🛒 Замовлення</div>
          {syncInfo ? (
            <>
              <div className="text-2xl font-bold text-purple-600">{syncInfo.orders.total_count}</div>
              <div className="text-xs text-gray-400 mt-2">
                Остання синхронізація:<br/>
                {formatDate(syncInfo.orders.last_sync)}
              </div>
            </>
          ) : (
            <div className="text-gray-400">Завантаження...</div>
          )}
        </div>
      </div>
      
      {/* Sync Status */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-xl font-bold mb-4">Статус синхронізації</h2>
        
        {status && (
          <>
            <div className="flex items-center gap-2 mb-4">
              <div className={`w-3 h-3 rounded-full ${status.is_running ? 'bg-green-500 animate-pulse' : 'bg-gray-300'}`}></div>
              <span className="font-medium">
                {status.is_running ? '🔄 Синхронізація виконується...' : '✅ Готово до синхронізації'}
              </span>
            </div>
            
            <div className="text-sm text-gray-600 mb-4">
              {status.supervisor_status}
            </div>
            
            {status.last_log_lines && status.last_log_lines.length > 0 && (
              <div className="mt-4">
                <div className="text-sm font-medium mb-2">Останні записи логу:</div>
                <div className="bg-gray-50 rounded p-3 text-xs font-mono max-h-48 overflow-y-auto">
                  {status.last_log_lines.map((line, idx) => (
                    <div key={idx} className="text-gray-700">{line}</div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
      
      {/* Actions */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-bold mb-4">Дії</h2>
        
        <button
          onClick={triggerSync}
          disabled={syncing || (status && status.is_running)}
          className={`px-6 py-3 rounded-lg font-medium ${
            syncing || (status && status.is_running)
              ? 'bg-gray-300 cursor-not-allowed'
              : 'corp-btn corp-btn-primary'
          }`}
        >
          {syncing ? '⏳ Запуск...' : '🔄 Запустити синхронізацію зараз'}
        </button>
        
        <div className="mt-4 text-sm text-gray-600">
          <strong>Примітка:</strong> Автоматична синхронізація виконується кожні 30 хвилин.
          Ви можете запустити синхронізацію вручну, якщо потрібно оновити дані негайно.
        </div>
      </div>
      
      {/* Info */}
      <div className="bg-blue-50 rounded-lg p-4 mt-6">
        <h3 className="font-bold text-blue-900 mb-2">ℹ️ Що синхронізується?</h3>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>✓ Товари з OpenCart (назви, ціни, фото, SKU)</li>
          <li>✓ Категорії товарів</li>
          <li>✓ Кількість товарів на складі</li>
          <li>✓ Нові замовлення від клієнтів</li>
          <li>✓ Атрибути товарів (колір, розмір тощо)</li>
        </ul>
      </div>
    </div>
  );
}
