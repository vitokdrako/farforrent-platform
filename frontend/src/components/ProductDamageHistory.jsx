import React, { useState, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

export function ProductDamageHistory({ productId, sku }) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    if (showHistory && (productId || sku)) {
      loadHistory();
    }
  }, [showHistory, productId, sku]);

  const loadHistory = async () => {
    try {
      setLoading(true);
      const endpoint = productId 
        ? `${BACKEND_URL}/api/product-damage-history/product/${productId}`
        : `${BACKEND_URL}/api/product-damage-history/by-sku?sku=${encodeURIComponent(sku)}`;
      
      const { data } = await axios.get(endpoint);
      setHistory(data.history || []);
    } catch (err) {
      console.error('Error loading damage history:', err);
    } finally {
      setLoading(false);
    }
  };

  if (!showHistory) {
    return (
      <button
        onClick={() => setShowHistory(true)}
        className="text-sm text-blue-600 hover:text-blue-800 underline"
      >
        📋 Історія пошкоджень
      </button>
    );
  }

  return (
    <div className="border rounded-lg p-4 mt-2 bg-slate-50">
      <div className="flex justify-between items-center mb-3">
        <h3 className="font-semibold text-lg">📋 Історія пошкоджень</h3>
        <button
          onClick={() => setShowHistory(false)}
          className="text-slate-500 hover:text-slate-700"
        >
          ✕
        </button>
      </div>

      {loading ? (
        <div className="text-center py-4 text-slate-500">Завантаження...</div>
      ) : history.length === 0 ? (
        <div className="text-center py-4 text-slate-500">Немає записів про пошкодження</div>
      ) : (
        <div className="space-y-3">
          {history.map((record) => (
            <div key={record.id} className="border border-slate-200 rounded-lg p-3 bg-white">
              <div className="flex justify-between items-start mb-2">
                <div>
                  <div className="font-medium text-slate-800">{record.damage_type}</div>
                  <div className="text-xs text-slate-500">
                    {record.category} • {record.stage_label}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-semibold text-amber-600">
                    ₴ {record.fee.toLocaleString('uk-UA', { maximumFractionDigits: 2 })}
                  </div>
                  <div className={`text-xs px-2 py-0.5 rounded inline-block ${
                    record.severity === 'critical' ? 'bg-red-100 text-red-700' :
                    record.severity === 'high' ? 'bg-orange-100 text-orange-700' :
                    record.severity === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                    'bg-slate-100 text-slate-700'
                  }`}>
                    {record.severity}
                  </div>
                </div>
              </div>
              
              {record.note && (
                <div className="text-sm text-slate-600 mb-2 italic">"{record.note}"</div>
              )}
              
              {record.order_number && (
                <div className="text-xs text-slate-500">
                  Замовлення: {record.order_number}
                </div>
              )}
              
              <div className="text-xs text-slate-400 mt-2">
                {new Date(record.created_at).toLocaleString('uk-UA')} • {record.created_by}
              </div>
            </div>
          ))}
          
          <div className="pt-2 border-t border-slate-200">
            <div className="font-semibold text-slate-700">
              Всього пошкоджень: {history.length}
            </div>
            <div className="font-semibold text-amber-600">
              Загальна сума: ₴ {history.reduce((sum, r) => sum + r.fee, 0).toLocaleString('uk-UA', { maximumFractionDigits: 2 })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
