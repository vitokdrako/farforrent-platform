import React, { useState } from 'react';
import { useAvailability } from '../hooks/useAvailability';
import './BoardItemCard.css';

const resolveImageUrl = (url) => {
  if (!url) return null;
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('data:')) return url;
  if (url.startsWith('/')) return url;
  return `/${url}`;
};

const BoardItemCard = ({ item, boardDates, rentalDays, onUpdate, onRemove }) => {
  const [quantity, setQuantity] = useState(item.quantity);
  const [isUpdating, setIsUpdating] = useState(false);

  const { availability, loading } = useAvailability(
    item.product_id,
    quantity,
    boardDates?.startDate,
    boardDates?.endDate
  );

  const handleQuantityChange = async (newQuantity) => {
    if (newQuantity < 1) return;

    if (boardDates?.startDate && boardDates?.endDate) {
      const maxAvail = availability?.available ?? availability?.available_quantity;
      if (maxAvail !== undefined && newQuantity > maxAvail) {
        alert(`Доступно лише ${maxAvail} шт на вибрані дати`);
        return;
      }
    }

    setQuantity(newQuantity);
    setIsUpdating(true);
    try {
      await onUpdate(item.id, { quantity: newQuantity });
    } catch (error) {
      console.error('Failed to update quantity:', error);
      setQuantity(item.quantity);
    } finally {
      setIsUpdating(false);
    }
  };

  const itemTotal = ((item.product?.rental_price || 0) * quantity * (rentalDays || 1));
  const img = resolveImageUrl(item.product?.image_url || item.product?.image);
  const available = availability?.available ?? availability?.available_quantity;
  const maxReached = available !== undefined && quantity >= available;

  return (
    <div className="bi-card" data-testid={`board-item-${item.id}`}>
      {/* Thumbnail */}
      <div className="bi-thumb">
        {img ? (
          <img src={img} alt="" onError={(e) => { e.target.style.display = 'none'; }} />
        ) : (
          <span className="bi-thumb-fallback">🎨</span>
        )}
      </div>

      {/* Основний блок */}
      <div className="bi-body">
        <div className="bi-row1">
          <h4 className="bi-title" title={item.product?.name}>{item.product?.name}</h4>
          <button
            onClick={() => onRemove(item.id)}
            className="bi-remove"
            aria-label="Видалити"
          >✕</button>
        </div>

        <div className="bi-meta">
          <span className="bi-sku">{item.product?.sku}</span>
          {boardDates?.startDate && boardDates?.endDate && (
            <span className={`bi-availability ${available !== undefined && quantity > available ? 'bad' : 'ok'}`}>
              {loading ? '...' : available !== undefined ? `✓ ${available}` : ''}
            </span>
          )}
        </div>

        <div className="bi-row2">
          {/* Лічильник */}
          <div className="bi-qty">
            <button
              onClick={() => handleQuantityChange(quantity - 1)}
              disabled={quantity <= 1 || isUpdating}
              className="bi-qty-btn"
              aria-label="Зменшити"
            >−</button>
            <input
              type="number"
              value={quantity}
              onChange={(e) => {
                const v = parseInt(e.target.value, 10) || 1;
                if (v > 0) handleQuantityChange(v);
              }}
              disabled={isUpdating}
              className="bi-qty-input"
              min="1"
            />
            <button
              onClick={() => handleQuantityChange(quantity + 1)}
              disabled={isUpdating || maxReached}
              className="bi-qty-btn"
              aria-label="Збільшити"
            >+</button>
          </div>

          {/* Підсумок */}
          <div className="bi-price">
            <div className="bi-price-total">₴{itemTotal.toFixed(0)}</div>
            <div className="bi-price-formula">
              ₴{item.product?.rental_price} × {quantity} × {rentalDays || 1}д
            </div>
          </div>
        </div>

        {item.notes && (
          <div className="bi-notes">📝 {item.notes}</div>
        )}
      </div>
    </div>
  );
};

export default BoardItemCard;
