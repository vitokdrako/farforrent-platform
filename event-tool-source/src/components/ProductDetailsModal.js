/**
 * ProductDetailsModal — розгорнута картка товару при кліку на фото.
 * - Карусель з кількома фото (swipe / стрілки / точки)
 * - Розміри з графічними символами (↕ ↔ ⤢ ⌀)
 * - Комплектація
 * - Лічильник кількості в одну лінію
 */
import React, { useEffect, useRef, useState } from 'react';
import api from '../api/axios';

const resolveImageUrl = (url) => {
  if (!url) return null;
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('data:')) return url;
  if (url.startsWith('/')) return url;
  return `/${url}`;
};

// Символи для розмірів — нагадують стрілки і ⌀
const DIM_ICONS = {
  height:   { sym: '↕',   label: 'Висота' },
  width:    { sym: '↔',   label: 'Ширина' },
  length:   { sym: '⤢',   label: 'Довжина' },
  depth:    { sym: '⤢',   label: 'Глибина' },
  diameter: { sym: '⌀',   label: 'Діаметр' },
  weight:   { sym: '⚖',   label: 'Вага' },
};

const ProductDetailsModal = ({ productId, boardDates, onClose, onAddToBoard }) => {
  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [qty, setQty] = useState(1);
  const [adding, setAdding] = useState(false);
  const [activeImage, setActiveImage] = useState(0);

  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768;
  const touchStartX = useRef(null);

  useEffect(() => {
    if (!productId) return;
    let cancelled = false;

    const params = new URLSearchParams();
    if (boardDates?.startDate) params.set('date_from', boardDates.startDate);
    if (boardDates?.endDate) params.set('date_to', boardDates.endDate);
    const query = params.toString() ? `?${params.toString()}` : '';

    (async () => {
      if (cancelled) return;
      setLoading(true);
      setError('');
      try {
        const r = await api.get(`/event/products/${productId}${query}`);
        if (cancelled) return;
        setProduct(r.data);
        setActiveImage(0);
      } catch (e) {
        if (!cancelled) setError(e?.response?.data?.detail || 'Не вдалося завантажити товар');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [productId, boardDates?.startDate, boardDates?.endDate]);

  const handleAdd = async () => {
    if (!boardDates?.startDate || !boardDates?.endDate) {
      alert('Спочатку оберіть дати оренди в мудборді!');
      return;
    }
    if (!product) return;
    setAdding(true);
    try {
      await onAddToBoard({ ...product, _quantity: qty });
      onClose();
    } catch (e) {
      console.error(e);
    } finally {
      setAdding(false);
    }
  };

  if (!productId) return null;

  const images = (product?.images?.length ? product.images : [product?.image_url]).filter(Boolean).map(resolveImageUrl);
  const hasMultiple = images.length > 1;
  const currentImg = images[activeImage] || null;
  const available = product?.available ?? product?.quantity ?? 0;
  const maxAdd = Math.max(1, available || 1);

  // Зібрати непорожні розміри для виведення з іконами
  const sizeChips = [];
  if (product?.height)   sizeChips.push({ ...DIM_ICONS.height,   val: `${product.height} см`  });
  if (product?.width)    sizeChips.push({ ...DIM_ICONS.width,    val: `${product.width} см`   });
  if (product?.length)   sizeChips.push({ ...DIM_ICONS.length,   val: `${product.length} см`  });
  if (product?.depth)    sizeChips.push({ ...DIM_ICONS.depth,    val: `${product.depth} см`   });
  if (product?.diameter) sizeChips.push({ ...DIM_ICONS.diameter, val: `${product.diameter} см`});
  if (product?.weight)   sizeChips.push({ ...DIM_ICONS.weight,   val: `${product.weight} кг`  });

  // Карусель — touch обробники
  const onTouchStart = (e) => { touchStartX.current = e.touches[0].clientX; };
  const onTouchEnd = (e) => {
    if (touchStartX.current === null) return;
    const dx = e.changedTouches[0].clientX - touchStartX.current;
    if (Math.abs(dx) > 50 && hasMultiple) {
      if (dx < 0) setActiveImage((i) => (i + 1) % images.length);
      else setActiveImage((i) => (i - 1 + images.length) % images.length);
    }
    touchStartX.current = null;
  };

  return (
    <div
      data-testid="product-details-overlay"
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.55)',
        zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: isMobile ? '0' : '24px',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#fff',
          borderRadius: isMobile ? '0' : '12px',
          maxWidth: '960px', width: '100%',
          maxHeight: isMobile ? '100vh' : '90vh',
          height: isMobile ? '100vh' : 'auto',
          overflow: 'hidden', display: 'grid',
          gridTemplateColumns: isMobile ? '1fr' : 'minmax(0, 1fr) minmax(0, 1fr)',
          gridTemplateRows: isMobile ? 'minmax(280px, 45vh) 1fr' : 'auto',
          boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
        }}
        data-testid="product-details-modal"
      >
        {/* Карусель зображень */}
        <div
          style={{background: '#fafafa', position: 'relative', overflow: 'hidden'}}
          onTouchStart={onTouchStart}
          onTouchEnd={onTouchEnd}
        >
          <button
            data-testid="product-details-close"
            onClick={onClose}
            style={{
              position: 'absolute', top: '12px', right: '12px', zIndex: 5,
              background: 'rgba(255,255,255,0.92)', border: 'none', borderRadius: '50%',
              width: '36px', height: '36px', cursor: 'pointer', fontSize: '18px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.15)', backdropFilter: 'blur(6px)',
            }}
            aria-label="Закрити"
          >×</button>

          {currentImg ? (
            <img src={currentImg} alt={product?.name || ''}
              style={{width: '100%', height: '100%', objectFit: 'contain', padding: '16px', display: 'block'}}
              onError={(e) => { e.target.style.display = 'none'; }}
            />
          ) : (
            <div style={{display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', fontSize: '64px'}}>🎨</div>
          )}

          {/* Стрілки навігації */}
          {hasMultiple && (
            <>
              <button
                onClick={() => setActiveImage((i) => (i - 1 + images.length) % images.length)}
                aria-label="Попереднє фото"
                style={arrowStyle('left')}
              >‹</button>
              <button
                onClick={() => setActiveImage((i) => (i + 1) % images.length)}
                aria-label="Наступне фото"
                style={arrowStyle('right')}
              >›</button>

              {/* Точки індикатора */}
              <div style={{
                position: 'absolute', bottom: '12px', left: '50%', transform: 'translateX(-50%)',
                display: 'flex', gap: '6px', zIndex: 3,
              }}>
                {images.map((_, i) => (
                  <button
                    key={i}
                    onClick={() => setActiveImage(i)}
                    aria-label={`Фото ${i + 1}`}
                    style={{
                      width: '8px', height: '8px', padding: 0,
                      borderRadius: '50%', border: 'none',
                      background: i === activeImage ? '#0a3d2e' : 'rgba(15,23,42,0.3)',
                      cursor: 'pointer', transition: 'all 0.2s',
                    }}
                  />
                ))}
              </div>
            </>
          )}
        </div>

        {/* Інфо панель */}
        <div style={{padding: isMobile ? '20px' : '32px', overflowY: 'auto'}}>
          {loading && <div style={{color: '#999'}}>Завантаження...</div>}
          {error && <div style={{color: '#c62828'}}>⚠️ {error}</div>}
          {product && (
            <>
              <div style={{fontSize: '11px', color: '#999', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '6px'}}>
                {product.sku}
              </div>
              <h2 style={{fontSize: '24px', fontWeight: '700', color: '#0f172a', marginBottom: '12px', lineHeight: '1.3'}}>
                {product.name}
              </h2>

              {/* Бейдж доступності */}
              <div style={{marginBottom: '16px'}}>
                <span style={{
                  padding: '4px 12px', borderRadius: '999px', fontSize: '12px', fontWeight: '600',
                  background: available > 0 ? '#dcfce7' : '#fee2e2',
                  color: available > 0 ? '#166534' : '#991b1b',
                }}>
                  {available > 0 ? `✓ Доступно: ${available} шт` : '✗ Недоступно'}
                </span>
              </div>

              {/* Категорії / Колір / Матеріал */}
              <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px 24px', marginBottom: '16px'}}>
                {product.category_name && <Field label="Категорія" value={product.category_name} />}
                {product.subcategory_name && <Field label="Підкатегорія" value={product.subcategory_name} />}
                {product.color && <Field label="Колір" value={product.color} />}
                {product.material && <Field label="Матеріал" value={product.material} />}
              </div>

              {/* Розміри з графічними символами */}
              {sizeChips.length > 0 && (
                <div style={{marginBottom: '18px'}}>
                  <div style={{fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '8px', letterSpacing: '0.8px', fontWeight: '600'}}>
                    Розміри
                  </div>
                  <div style={{display: 'flex', flexWrap: 'wrap', gap: '8px'}}>
                    {sizeChips.map((c, i) => (
                      <div
                        key={i}
                        title={c.label}
                        style={{
                          display: 'inline-flex', alignItems: 'center', gap: '6px',
                          padding: '6px 12px', background: '#f1f5f9', borderRadius: '999px',
                          fontSize: '13px', color: '#0f172a', fontWeight: '500',
                        }}
                      >
                        <span style={{fontSize: '17px', lineHeight: 1, fontWeight: '700', color: '#0a3d2e'}}>{c.sym}</span>
                        <span>{c.val}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* size як текст (старі дані) */}
              {product.size && sizeChips.length === 0 && (
                <div style={{marginBottom: '18px'}}>
                  <Field label="Розмір" value={product.size} />
                </div>
              )}

              {/* Комплектація */}
              {(product.set_contents || product.complectation) && (
                <div style={{marginBottom: '20px'}}>
                  <div style={{fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '6px', letterSpacing: '0.8px', fontWeight: '600'}}>
                    Комплектація
                  </div>
                  <div style={{fontSize: '14px', color: '#0f172a', lineHeight: '1.55', whiteSpace: 'pre-wrap', padding: '12px', background: '#f8fafc', borderRadius: '6px', border: '1px solid #e2e8f0'}}>
                    {product.set_contents || product.complectation}
                  </div>
                </div>
              )}

              {/* Опис */}
              {product.description && (
                <div style={{marginBottom: '20px'}}>
                  <div style={{fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '6px', letterSpacing: '0.8px', fontWeight: '600'}}>
                    Опис
                  </div>
                  <div style={{fontSize: '14px', color: '#475569', lineHeight: '1.55', whiteSpace: 'pre-wrap'}}>
                    {product.description}
                  </div>
                </div>
              )}

              {/* Ціна + застава */}
              <div style={{
                background: '#f8fafc', borderRadius: '8px', padding: '16px',
                marginBottom: '16px',
              }}>
                <div style={{display: 'flex', alignItems: 'baseline', gap: '8px', marginBottom: '8px'}}>
                  <span style={{fontSize: '32px', fontWeight: '800', color: '#0a3d2e'}}>
                    ₴{(product.rental_price || 0).toLocaleString('uk-UA')}
                  </span>
                  <span style={{fontSize: '14px', color: '#64748b'}}>/день</span>
                </div>
                {/* Застава (повертається) */}
                {(() => {
                  const dep = Number(product.deposit) > 0
                    ? Number(product.deposit)
                    : (Number(product.price) || 0) / 2;
                  if (!dep) return null;
                  return (
                    <div
                      data-testid="product-deposit"
                      style={{
                        display: 'flex',
                        alignItems: 'baseline',
                        gap: '6px',
                        borderTop: '1px dashed #cbd5e1',
                        paddingTop: '8px',
                        marginTop: '6px',
                      }}
                    >
                      <span style={{fontSize: '12px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.6px'}}>Застава:</span>
                      <span style={{fontSize: '18px', fontWeight: '700', color: '#b08d2e'}}>
                        ₴{dep.toLocaleString('uk-UA', {minimumFractionDigits: 0, maximumFractionDigits: 0})}
                      </span>
                      <span style={{fontSize: '11px', color: '#64748b', marginLeft: 'auto'}}>повертається після здачі</span>
                    </div>
                  );
                })()}
              </div>

              {/* Лічильник + кнопка */}
              {boardDates?.startDate && boardDates?.endDate ? (
                <div>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',          /* центруємо все по вертикалі — ОДНА ЛІНІЯ */
                    justifyContent: 'space-between',
                    gap: '8px',
                    marginBottom: '12px',
                  }}>
                    <span style={{fontSize: '13px', color: '#64748b', flexShrink: 0}}>Кількість:</span>

                    <div style={{display: 'flex', alignItems: 'center', gap: '8px', flex: 1, justifyContent: 'center'}}>
                      <button
                        type="button"
                        onClick={() => setQty(q => Math.max(1, q - 1))}
                        aria-label="Зменшити"
                        style={qtyBtnStyle(false)}
                      >−</button>
                      <input
                        type="number" min="1" max={maxAdd} value={qty}
                        onChange={(e) => {
                          const v = parseInt(e.target.value, 10) || 1;
                          setQty(Math.min(maxAdd, Math.max(1, v)));
                        }}
                        data-testid="product-details-qty"
                        style={{
                          width: '64px', height: '40px',
                          textAlign: 'center',
                          padding: '0',
                          borderRadius: '8px',
                          border: '1px solid #cbd5e1',
                          fontSize: '16px', fontWeight: '600',
                          background: '#fff',
                          boxSizing: 'border-box',
                        }}
                      />
                      <button
                        type="button"
                        onClick={() => setQty(q => Math.min(maxAdd, q + 1))}
                        disabled={qty >= maxAdd}
                        aria-label="Збільшити"
                        style={qtyBtnStyle(qty >= maxAdd)}
                      >+</button>
                    </div>

                    <span style={{fontSize: '12px', color: '#94a3b8', flexShrink: 0}}>макс. {maxAdd}</span>
                  </div>
                  <button
                    onClick={handleAdd}
                    disabled={adding || available <= 0}
                    data-testid="product-details-add"
                    style={{
                      width: '100%', padding: '14px', background: '#0a3d2e', color: '#fff',
                      border: 'none', borderRadius: '8px', fontSize: '14px', fontWeight: '700',
                      cursor: (adding || available <= 0) ? 'not-allowed' : 'pointer',
                      opacity: (adding || available <= 0) ? 0.6 : 1,
                      textTransform: 'uppercase', letterSpacing: '0.5px',
                    }}
                  >
                    {adding ? 'Додається...' : `Додати в підбірку (${qty} шт)`}
                  </button>
                </div>
              ) : (
                <div style={{padding: '12px', background: '#fef3c7', borderRadius: '8px', fontSize: '13px', color: '#92400e'}}>
                  ⚠️ Оберіть дати оренди у боксі «Мій івент» щоб додати в підбірку
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

const Field = ({label, value}) => (
  <div>
    <div style={{fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '3px'}}>{label}</div>
    <div style={{fontSize: '14px', color: '#0f172a', fontWeight: '500'}}>{value}</div>
  </div>
);

const arrowStyle = (side) => ({
  position: 'absolute',
  top: '50%',
  [side]: '8px',
  transform: 'translateY(-50%)',
  width: '40px', height: '40px',
  borderRadius: '50%',
  background: 'rgba(255,255,255,0.95)',
  border: 'none',
  fontSize: '24px',
  color: '#0f172a',
  cursor: 'pointer',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
  zIndex: 3,
  fontWeight: '300',
  lineHeight: 1,
  padding: 0,
});

const qtyBtnStyle = (disabled) => ({
  width: '40px',
  height: '40px',
  borderRadius: '8px',
  border: '1px solid #cbd5e1',
  background: '#fff',
  cursor: disabled ? 'not-allowed' : 'pointer',
  opacity: disabled ? 0.5 : 1,
  fontSize: '20px',
  fontWeight: '600',
  color: '#0f172a',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  padding: 0,
  lineHeight: 1,
  boxSizing: 'border-box',
});

export default ProductDetailsModal;
