import { useState, useEffect } from 'react';
import api from '../api/axios';

export const useAvailability = (productId, quantity, startDate, endDate) => {
  const [availability, setAvailability] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!productId || !startDate || !endDate || !quantity) {
      setAvailability(null);
      return;
    }

    const checkAvailability = async () => {
      setLoading(true);
      setError(null);
      
      try {
        const response = await api.post('/event/products/check-availability', {
          product_id: productId,
          quantity: quantity,
          reserved_from: startDate,
          reserved_until: endDate,
        });
        setAvailability(response.data);
      } catch (err) {
        setError(err.response?.data?.detail || 'Помилка перевірки доступності');
        setAvailability(null);
      } finally {
        setLoading(false);
      }
    };

    checkAvailability();
  }, [productId, quantity, startDate, endDate]);

  return { availability, loading, error };
};