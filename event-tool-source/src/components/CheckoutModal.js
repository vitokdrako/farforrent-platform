/**
 * CheckoutModal — оформлення замовлення з мудборду.
 * POST /event/boards/{board_id}/convert-to-order
 */
import React, { useState, useEffect } from 'react';
import api from '../api/axios';
import { calculateRentalDays, PICKUP_TIME_SLOTS, RETURN_TIME } from '../utils/rentalDays';

const CheckoutModal = ({ board, user, onClose, onSuccess }) => {
  const [form, setForm] = useState({
    customer_name: user ? `${user.firstname || ''} ${user.lastname || ''}`.trim() : '',
    customer_phone: user?.telephone || '',
    customer_email: user?.email || '',
    notes: '',
    payment_method: 'cash',
    pickup_time_slot: '11:00-12:00',
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(null);

  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768;

  const update = (k) => (e) => setForm(prev => ({...prev, [k]: e.target.value}));

  const totalItems = board?.items?.reduce((s, i) => s + (i.quantity || 0), 0) || 0;

  // Розрахунок діб за правилами Farfor Decor (повернення до 17:00)
  const { days: rentalDays, isStandard, hint: daysHint } = calculateRentalDays(
    board?.rental_start_date,
    board?.rental_end_date
  );

  const totalPrice = board?.items?.reduce((s, i) => {
    const price = i.product?.rental_price || 0;
    return s + price * (i.quantity || 0) * rentalDays;
  }, 0) || 0;

  // Застава = сума (price / 2 * quantity) — половина вартості товару
  const totalDeposit = board?.items?.reduce((s, i) => {
    const fullPrice = Number(i.product?.price) || 0;
    return s + (fullPrice / 2) * (i.quantity || 0);
  }, 0) || 0;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.customer_name || !form.customer_phone) {
      setError('Вкажіть ім\'я та телефон');
      return;
    }
    setError('');
    setSubmitting(true);
    try {
      // Збираємо коментар + спосіб оплати в одне поле (бекенд приймає customer_comment)
      const paymentLabels = {cash: 'Готівка', card: 'Картка', bank_transfer: 'Безготівка'};
      const fullComment = [
        `Оплата: ${paymentLabels[form.payment_method] || form.payment_method}`,
        form.notes && form.notes.trim() ? `Коментар: ${form.notes.trim()}` : null,
      ].filter(Boolean).join(' | ');

      const res = await api.post(`/event/boards/${board.id}/convert-to-order`, {
        customer_name: form.customer_name,
        phone: form.customer_phone,
        customer_comment: fullComment,
        payer_type: 'individual',
        pickup_time_slot: form.pickup_time_slot,
        return_time: RETURN_TIME,
      });
      setSuccess(res.data);
      if (onSuccess) onSuccess(res.data);
    } catch (err) {
      const d = err?.response?.data?.detail;
      let msg = 'Помилка оформлення';
      if (typeof d === 'string') msg = d;
      else if (Array.isArray(d)) msg = d.map(x => x.msg || JSON.stringify(x)).join('; ');
      else if (d?.message) msg = d.message + (d.details ? ` (${d.details})` : '');
      else if (d?.msg) msg = d.msg;
      else if (d?.details) msg = d.details;
      else if (err?.message) msg = err.message;
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  if (success) {
    return (
      <Overlay onClose={onClose}>
        <div style={{padding: isMobile ? '24px' : '40px', maxWidth: '480px', textAlign: 'center'}}>
          <div style={{fontSize: '56px', marginBottom: '12px'}}>✅</div>
          <h2 style={{fontSize: '22px', fontWeight: '700', color: '#0a3d2e', marginBottom: '8px'}}>
            Замовлення створено
          </h2>
          <div style={{fontSize: '14px', color: '#475569', marginBottom: '4px'}}>
            Номер: <strong>{success.order_number || `#${success.order_id}`}</strong>
          </div>
          <div style={{fontSize: '13px', color: '#94a3b8', marginBottom: '24px'}}>
            Менеджер зв'яжеться з вами найближчим часом для підтвердження.
          </div>
          <div style={{display: 'flex', gap: '10px', justifyContent: 'center', flexWrap: 'wrap'}}>
            <a
              href={`${process.env.REACT_APP_BACKEND_URL || ''}/api/event/orders/${success.order_id}/estimate.html?token=${encodeURIComponent(localStorage.getItem('access_token') || '')}`}
              target="_blank"
              rel="noopener noreferrer"
              data-testid="checkout-view-estimate"
              className="fd-btn"
              style={{padding: '12px 22px', background: '#fff', border: '1px solid #0a3d2e', color: '#0a3d2e', textDecoration: 'none', borderRadius: '8px', fontWeight: 600}}
            >
              📄 Переглянути кошторис
            </a>
            <button onClick={onClose} className="fd-btn fd-btn-black" style={{padding: '12px 22px'}}>
              Закрити
            </button>
          </div>
        </div>
      </Overlay>
    );
  }

  return (
    <Overlay onClose={onClose}>
      <form
        onSubmit={handleSubmit}
        data-testid="checkout-modal"
        style={{
          padding: isMobile ? '20px' : '32px',
          maxWidth: isMobile ? '100%' : '880px',
          width: '100%',
          maxHeight: isMobile ? '100vh' : '92vh',
          overflowY: 'auto',
        }}
      >
        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px'}}>
          <h2 style={{fontSize: '22px', fontWeight: '700', color: '#0f172a', margin: 0}}>
            Оформити замовлення
          </h2>
          <button
            type="button"
            onClick={onClose}
            style={{background: 'transparent', border: 'none', fontSize: '24px', cursor: 'pointer', color: '#64748b'}}
            aria-label="Закрити"
          >×</button>
        </div>

        {/* Підсумок з заставою та поясненням діб */}
        <div style={{
          padding: '16px', background: '#f8fafc', borderRadius: '8px', marginBottom: '20px',
          display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'repeat(3, 1fr)', gap: '12px 20px', fontSize: '13px',
        }}>
          <div>
            <div style={{color: '#94a3b8', textTransform: 'uppercase', fontSize: '10px', letterSpacing: '0.8px'}}>Позицій</div>
            <div style={{fontWeight: '600', color: '#0f172a'}}>{board?.items?.length || 0} ({totalItems} шт)</div>
          </div>
          <div>
            <div style={{color: '#94a3b8', textTransform: 'uppercase', fontSize: '10px', letterSpacing: '0.8px'}}>
              Діб {isStandard ? '✓' : '~'}
            </div>
            <div style={{fontWeight: '600', color: '#0f172a'}}>
              {rentalDays || '—'}
            </div>
            {daysHint && (
              <div style={{fontSize: '11px', color: '#64748b', marginTop: '2px', lineHeight: 1.3}}>
                {daysHint}
              </div>
            )}
          </div>
          <div>
            <div style={{color: '#94a3b8', textTransform: 'uppercase', fontSize: '10px', letterSpacing: '0.8px'}}>Застава</div>
            <div style={{fontWeight: '700', color: '#b08d2e', fontSize: '16px'}}>
              ₴{totalDeposit.toLocaleString('uk-UA', {minimumFractionDigits: 0, maximumFractionDigits: 0})}
            </div>
            <div style={{fontSize: '11px', color: '#64748b', marginTop: '2px'}}>
              повертається після здачі
            </div>
          </div>
          <div style={{gridColumn: '1 / -1', borderTop: '1px solid #e2e8f0', paddingTop: '12px', marginTop: '4px'}}>
            <div style={{color: '#94a3b8', textTransform: 'uppercase', fontSize: '10px', letterSpacing: '0.8px'}}>До сплати при отриманні</div>
            <div style={{fontSize: '26px', fontWeight: '800', color: '#0a3d2e'}}>
              ₴{(totalPrice + totalDeposit).toLocaleString('uk-UA', {minimumFractionDigits: 2, maximumFractionDigits: 2})}
            </div>
            <div style={{fontSize: '12px', color: '#64748b', marginTop: '2px'}}>
              Оренда ₴{totalPrice.toLocaleString('uk-UA', {minimumFractionDigits: 0})} + застава ₴{totalDeposit.toLocaleString('uk-UA', {minimumFractionDigits: 0})}
            </div>
          </div>
        </div>

        {/* Двоколонкова сітка на десктопі: ліворуч контакти, праворуч деталі */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr',
          gap: isMobile ? 0 : '24px',
        }}>
          <div>
            <Section title="Ваші дані">
              <Input label="ПІБ *" value={form.customer_name} onChange={update('customer_name')} data-testid="checkout-name" />
              <Input label="Телефон *" type="tel" value={form.customer_phone} onChange={update('customer_phone')} placeholder="+380..." data-testid="checkout-phone" />
              <Input label="Email" type="email" value={form.customer_email} onChange={update('customer_email')} data-testid="checkout-email" />
            </Section>
          </div>

          <div>
            <Section title="Час видачі">
              <select
                value={form.pickup_time_slot}
                onChange={update('pickup_time_slot')}
                data-testid="checkout-pickup-slot"
                style={inputStyle}
              >
                {PICKUP_TIME_SLOTS.map(s => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
              <div style={{fontSize: '12px', color: '#64748b', marginTop: '6px'}}>
                Повернення завжди до <strong>{RETURN_TIME}</strong> у вказаний день.
              </div>
            </Section>

            <Section title="Деталі івенту">
              <label style={labelStyle}>Коментар менеджеру</label>
              <textarea
                value={form.notes}
                onChange={update('notes')}
                rows={3}
                placeholder="Особливі побажання..."
                data-testid="checkout-notes"
                style={{...inputStyle, resize: 'vertical', minHeight: '70px'}}
              />
            </Section>
          </div>
        </div>

        {/* Оплата */}
        <Section title="Спосіб оплати">
          <div style={{display: 'flex', gap: '8px', flexWrap: 'wrap'}}>
            {[
              {key: 'cash', label: '💵 Готівка'},
              {key: 'bank_transfer', label: '🏦 Безготівка'},
            ].map(m => (
              <button
                key={m.key}
                type="button"
                onClick={() => setForm(prev => ({...prev, payment_method: m.key}))}
                data-testid={`checkout-pay-${m.key}`}
                style={{
                  flex: '1 1 100px',
                  padding: '10px',
                  border: `1px solid ${form.payment_method === m.key ? '#0a3d2e' : '#cbd5e1'}`,
                  background: form.payment_method === m.key ? '#0a3d2e' : '#fff',
                  color: form.payment_method === m.key ? '#fff' : '#0f172a',
                  borderRadius: '6px',
                  fontSize: '13px',
                  fontWeight: '500',
                  cursor: 'pointer',
                }}
              >
                {m.label}
              </button>
            ))}
          </div>
        </Section>

        {error && (
          <div style={{padding: '12px', background: '#fee2e2', color: '#991b1b', borderRadius: '6px', fontSize: '13px', marginBottom: '16px'}}>
            ⚠️ {error}
          </div>
        )}

        <button
          type="submit"
          disabled={submitting}
          data-testid="checkout-submit"
          className="fd-btn fd-btn-black"
          style={{
            width: '100%',
            padding: '14px',
            fontSize: '13px',
            opacity: submitting ? 0.6 : 1,
          }}
        >
          {submitting ? 'Створюємо...' : 'Підтвердити замовлення'}
        </button>

        <div style={{marginTop: '12px', fontSize: '11px', color: '#94a3b8', textAlign: 'center'}}>
          Натискаючи кнопку, ви погоджуєтесь з умовами оренди.
        </div>
      </form>
    </Overlay>
  );
};

const Overlay = ({children, onClose}) => (
  <div
    onClick={onClose}
    data-testid="checkout-overlay"
    style={{
      position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.55)',
      zIndex: 1100, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px',
    }}
  >
    <div
      onClick={(e) => e.stopPropagation()}
      style={{background: '#fff', borderRadius: '12px', boxShadow: '0 20px 60px rgba(0,0,0,0.3)'}}
    >
      {children}
    </div>
  </div>
);

const Section = ({title, children}) => (
  <div style={{marginBottom: '20px'}}>
    <div style={{fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '10px', letterSpacing: '0.8px', fontWeight: '600'}}>
      {title}
    </div>
    {children}
  </div>
);

const labelStyle = {
  display: 'block',
  fontSize: '12px',
  color: '#475569',
  marginBottom: '6px',
  fontWeight: '500',
};

const inputStyle = {
  width: '100%',
  padding: '10px 12px',
  border: '1px solid #cbd5e1',
  borderRadius: '6px',
  fontSize: '14px',
  fontFamily: 'inherit',
  outline: 'none',
  boxSizing: 'border-box',
};

const Input = ({label, ...props}) => (
  <div style={{marginBottom: '14px'}}>
    <label style={labelStyle}>{label}</label>
    <input style={inputStyle} {...props} />
  </div>
);

export default CheckoutModal;
