import React, { useState } from 'react';
import { Heart } from 'lucide-react';
import AvailabilityBadge from './AvailabilityBadge';
import { useAvailability } from '../hooks/useAvailability';
import { useFavorites } from '../context/FavoritesContext';
import './ProductCard.css';

const ProductCard = ({ product, onAddToBoard, boardDates, onOpenDetails }) => {
  const [isAdding, setIsAdding] = useState(false);
  const { isFavorite, toggle: toggleFav } = useFavorites();
  const fav = isFavorite(product.product_id);
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
      <div
        className="product-card-image"
        onClick={() => onOpenDetails && onOpenDetails(product.product_id)}
        style={{cursor: onOpenDetails ? 'pointer' : 'default', position: 'relative'}}
        data-testid={`product-card-image-${product.product_id}`}
      >
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); toggleFav(product.product_id); }}
          aria-label={fav ? 'Видалити з обраного' : 'Додати в обране'}
          data-testid={`favorite-btn-${product.product_id}`}
          className={`product-card-fav-btn ${fav ? 'is-fav' : ''}`}
          style={{
            position: 'absolute', top: 8, left: 8, zIndex: 5,
            width: 32, height: 32, borderRadius: '50%',
            border: 'none', background: 'rgba(255,255,255,0.92)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer', boxShadow: '0 1px 3px rgba(0,0,0,0.12)',
            transition: 'transform 0.15s ease',
          }}
          onMouseDown={(e) => { e.currentTarget.style.transform = 'scale(0.85)'; }}
          onMouseUp={(e) => { e.currentTarget.style.transform = 'scale(1)'; }}
        >
          <Heart
            size={17}
            color={fav ? '#e63946' : '#444'}
            fill={fav ? '#e63946' : 'none'}
            strokeWidth={fav ? 0 : 2}
          />
        </button>
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

        <div className="product-card-info">
          <span className="product-card-price">
            ₴{product.rental_price}
            <span className="product-card-price-unit">/день</span>
          </span>
          <span className="product-card-quantity">
            {product.quantity} шт
          </span>
        </div>

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