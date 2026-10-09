import React, { useState, useEffect } from 'react';
import { Clock, User, Package, FileText, DollarSign, AlertCircle, CheckCircle } from 'lucide-react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL;

const OrderHistoryTimeline = ({ orderId }) => {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (orderId) {
      fetchHistory();
    }
  }, [orderId]);

  const fetchHistory = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_URL}/api/user-tracking/orders/${orderId}/history`);
      setHistory(response.data.history || []);
    } catch (err) {
      console.error('Error fetching order history:', err);
      setError('Не вдалося завантажити історію');
    } finally {
      setLoading(false);
    }
  };

  const getActionIcon = (action) => {
    switch (action) {
      case 'created':
        return <FileText className="w-4 h-4" />;
      case 'confirmed':
        return <CheckCircle className="w-4 h-4" />;
      case 'packed':
        return <Package className="w-4 h-4" />;
      case 'prepared':
      case 'issued':
      case 'returned':
        return <Package className="w-4 h-4" />;
      case 'damage_recorded':
        return <AlertCircle className="w-4 h-4" />;
      case 'finance_transaction':
        return <DollarSign className="w-4 h-4" />;
      default:
        return <Clock className="w-4 h-4" />;
    }
  };

  const getActionColor = (action) => {
    switch (action) {
      case 'created':
        return 'text-blue-600';
      case 'confirmed':
        return 'text-green-600';
      case 'packed':
      case 'prepared':
        return 'text-purple-600';
      case 'issued':
        return 'text-indigo-600';
      case 'returned':
        return 'text-orange-600';
      case 'damage_recorded':
        return 'text-red-600';
      case 'finance_transaction':
        return 'text-emerald-600';
      default:
        return 'text-gray-600';
    }
  };

  const formatDate = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleString('uk-UA', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-4">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
        <p className="text-red-600">{error}</p>
      </div>
    );
  }

  if (history.length === 0) {
    return (
      <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg">
        <p className="text-gray-600">Історія дій відсутня</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h3 className="text-lg font-semibold flex items-center gap-2">
        <Clock className="w-5 h-5" />
        Історія дій
      </h3>
      
      <div className="relative">
        {/* Timeline line */}
        <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-200"></div>
        
        {/* Timeline items */}
        <div className="space-y-4">
          {history.map((item, index) => (
            <div key={index} className="relative flex gap-4 items-start">
              {/* Icon */}
              <div className={`relative z-10 flex items-center justify-center w-8 h-8 rounded-full bg-white border-2 ${getActionColor(item.action)}`}>
                {getActionIcon(item.action)}
              </div>
              
              {/* Content */}
              <div className="flex-1 bg-white rounded-lg border border-gray-200 p-3 shadow-sm">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1">
                    <p className="font-medium text-gray-900">{item.action_label}</p>
                    
                    {/* User info */}
                    <div className="flex items-center gap-2 mt-1 text-sm text-gray-600">
                      <User className="w-3 h-3" />
                      <span>{item.user_name || 'System'}</span>
                    </div>
                    
                    {/* Details */}
                    {item.details && (
                      <div className="mt-2 p-2 bg-gray-50 rounded text-sm">
                        {item.details.sku && (
                          <p><span className="font-medium">SKU:</span> {item.details.sku}</p>
                        )}
                        {item.details.product_name && (
                          <p><span className="font-medium">Товар:</span> {item.details.product_name}</p>
                        )}
                        {item.details.quantity && (
                          <p><span className="font-medium">Кількість:</span> {item.details.quantity}</p>
                        )}
                        {item.details.location && (
                          <p><span className="font-medium">Локація:</span> {item.details.location}</p>
                        )}
                        {item.details.type && (
                          <p><span className="font-medium">Тип:</span> {item.details.type}</p>
                        )}
                        {item.details.amount !== undefined && (
                          <p><span className="font-medium">Сума:</span> {item.details.amount} {item.details.currency || 'UAH'}</p>
                        )}
                        {item.details.damage_type && (
                          <p><span className="font-medium">Пошкодження:</span> {item.details.damage_type}</p>
                        )}
                        {item.details.fee && (
                          <p><span className="font-medium">Штраф:</span> ₴{item.details.fee}</p>
                        )}
                      </div>
                    )}
                  </div>
                  
                  {/* Timestamp */}
                  <div className="text-xs text-gray-500 whitespace-nowrap">
                    {formatDate(item.timestamp)}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default OrderHistoryTimeline;