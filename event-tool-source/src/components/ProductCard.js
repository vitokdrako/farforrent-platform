import React, { useState } from 'react';
import AvailabilityBadge from './AvailabilityBadge';
import { useAvailability } from '../hooks/useAvailability';
import './ProductCard.css';

const ProductCard = ({ product, onAddToBoard, boardDates }) => {
  const [isAdding, setIsAdding] = useState(false);
  const { availability, loading } = useAvailability(
    product.product_id,
    1,
    boardDates?.startDate,
    boardDates?.endDate
  );

  const handleAdd = async () => {
    if (!boardDates?.startDate || !boardDates?.endDate) {
      alert('Спочатку оберіть дати оренди в мудборді!');
      return;
    }

    if (availability && !availability.is_available) {
      alert(availability.message || 'Товар недоступний на вибрані дати');
      return;
    }

    setIsAdding(true);
    try {
      await onAddToBoard(product);
    } catch (error) {
      console.error('Failed to add:', error);
    } finally {
      setIsAdding(false);
    }
  };

  const getImageUrl = () => {
    if (!product.image_url) return null;
    const url = product.image_url;
    // Повний URL — повертаємо як є
    if (url.startsWith('http://') || url.startsWith('https://')) return url;
    // Абсолютний шлях same-origin
    if (url.startsWith('/')) return url;
    // Відносний шлях з нашого бекенду (static/images/... або uploads/...)
    return `/${url}`;
  };

  return (
    <div className="product-card">
      <div className="product-card-image">
        {getImageUrl() ? (
          <img
            src={getImageUrl()}
            alt={product.name}
            onError={(e) => {
              e.target.style.display = 'none';
              const placeholder = document.createElement('div');
              placeholder.className = 'product-card-image-placeholder';
              placeholder.textContent = '🎨';
              e.target.parentElement.appendChild(placeholder);
            }}
          />
        ) : (
          <div className="product-card-image-placeholder">🎨</div>
        )}
        
        {/* Availability badge overlay */}
        {boardDates?.startDate && boardDates?.endDate && (
          <div className="product-availability-badge">
            {loading ? (
              <span>⏳ Перевірка...</span>
            ) : availability ? (
              <AvailabilityBadge
                available={availability.available ?? availability.available_quantity ?? 0}
                total={product.quantity}
                requested={1}
                compact={true}
              />
            ) : null}
          </div>
        )}
      </div>
      
      <div className="product-card-body">
        <h3 className="product-card-title" title={product.name}>
          {product.name}
        </h3>
        <p className="product-card-sku">{product.sku}</p>
        
        {/* Availability info */}
        {product.available !== undefined && (
          <div style={{
            display: 'flex',
            gap: '8px',
            alignItems: 'center',
            marginTop: '6px',
            fontSize: '11px',
            color: '#666'
          }}>
            <span style={{
              padding: '2px 8px',
              borderRadius: '12px',
              background: product.available > 0 ? '#e8f5e9' : '#ffebee',
              color: product.available > 0 ? '#2e7d32' : '#c62828',
              fontWeight: '500'
            }}>
              {product.available > 0 ? `✓ Доступно: ${product.available}` : '✗ Недоступно'}
            </span>
            {product.reserved > 0 && (
              <span style={{color: '#999', fontSize: '10px'}}>
                ({product.reserved} в резерві)
              </span>
            )}
          </div>
        )}
        
        <div className="product-card-info">
          <span className="product-card-price">
            ₴{product.rental_price}
            <span className="product-card-price-unit">/день</span>
          </span>
          <span className="product-card-quantity">
            {product.quantity} шт
          </span>
        </div>

        {/* Full availability info */}
        {boardDates?.startDate && boardDates?.endDate && availability && (
          <div className="product-card-availability">
            <AvailabilityBadge
              available={availability.available ?? availability.available_quantity ?? 0}
              total={product.quantity}
              requested={1}
            />
          </div>
        )}
        
        <button
          onClick={handleAdd}
          disabled={isAdding || (availability && !availability.is_available)}
          className={`product-card-button ${isAdding ? 'adding' : ''}`}
        >
          {isAdding ? 'Додавання...' : 'Додати в підбірку'}
        </button>
      </div>
    </div>
  );
};

export default ProductCard;