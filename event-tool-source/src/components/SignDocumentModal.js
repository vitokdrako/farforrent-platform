/**
 * SignDocumentModal — підписання документа клієнтом у кабінеті.
 * Використовує нативний HTML5 canvas (без зовнішніх бібліотек).
 *
 * POST /event/orders/{orderId}/documents/{documentId}/sign
 * Body: { signature_png_base64, signer_name }
 */
import React, { useRef, useState, useEffect } from 'react';
import api from '../api/axios';

const SignDocumentModal = ({ orderId, document, user, onClose, onSigned }) => {
  const canvasRef = useRef(null);
  const [hasInk, setHasInk] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [agreed, setAgreed] = useState(false);
  const [signerName, setSignerName] = useState(
    user ? `${user.firstname || ''} ${user.lastname || ''}`.trim() : ''
  );

  const isMobile = typeof window !== 'undefined' && window.innerWidth < 768;

  // Canvas setup
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.lineWidth = 2.5;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = '#0f172a';

    let drawing = false;
    let last = null;

    const getPos = (e) => {
      const rect = canvas.getBoundingClientRect();
      const x = (e.touches?.[0]?.clientX ?? e.clientX) - rect.left;
      const y = (e.touches?.[0]?.clientY ?? e.clientY) - rect.top;
      return {
        x: x * (canvas.width / rect.width),
        y: y * (canvas.height / rect.height),
      };
    };

    const start = (e) => {
      e.preventDefault();
      drawing = true;
      last = getPos(e);
      setHasInk(true);
    };
    const move = (e) => {
      if (!drawing) return;
      e.preventDefault();
      const p = getPos(e);
      ctx.beginPath();
      ctx.moveTo(last.x, last.y);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
      last = p;
    };
    const end = () => { drawing = false; };

    canvas.addEventListener('mousedown', start);
    canvas.addEventListener('mousemove', move);
    window.addEventListener('mouseup', end);
    canvas.addEventListener('touchstart', start, {passive: false});
    canvas.addEventListener('touchmove', move, {passive: false});
    canvas.addEventListener('touchend', end);

    return () => {
      canvas.removeEventListener('mousedown', start);
      canvas.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', end);
      canvas.removeEventListener('touchstart', start);
      canvas.removeEventListener('touchmove', move);
      canvas.removeEventListener('touchend', end);
    };
  }, []);

  const clearSig = () => {
    const canvas = canvasRef.current;
    canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
    setHasInk(false);
  };

  const submit = async () => {
    setError('');
    if (!agreed) {
      setError('Підтвердіть, що ви погоджуєтесь з умовами договору');
      return;
    }
    if (!hasInk) {
      setError('Поставте підпис у полі вище');
      return;
    }
    if (!signerName.trim()) {
      setError('Вкажіть ваше імʼя для підпису');
      return;
    }

    setSubmitting(true);
    try {
      const dataUrl = canvasRef.current.toDataURL('image/png');
      const res = await api.post(`/event/orders/${orderId}/documents/${document.id}/sign`, {
        signature_png_base64: dataUrl,
        signer_name: signerName.trim(),
      });
      if (onSigned) onSigned(res.data);
      onClose();
    } catch (err) {
      const d = err?.response?.data?.detail;
      setError(typeof d === 'string' ? d : (d?.message || 'Не вдалося підписати документ'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.6)',
        zIndex: 1200, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '12px',
      }}
      data-testid="sign-doc-overlay"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#fff', borderRadius: '12px', maxWidth: '560px', width: '100%',
          maxHeight: '95vh', overflowY: 'auto', padding: isMobile ? '20px' : '28px',
        }}
        data-testid="sign-doc-modal"
      >
        <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: '8px', marginBottom: '16px'}}>
          <div>
            <h2 style={{fontSize: '18px', fontWeight: '700', margin: 0, color: '#0f172a'}}>
              Підписати {document.doc_type_label?.toLowerCase() || 'документ'}
            </h2>
            <div style={{fontSize: '12px', color: '#64748b', marginTop: '4px'}}>
              {document.doc_type_label} {document.doc_number ? `№${document.doc_number}` : ''}
            </div>
          </div>
          <button
            onClick={onClose}
            style={{background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer', color: '#94a3b8'}}
            aria-label="Закрити"
          >×</button>
        </div>

        {/* Прев'ю PDF в iframe щоб клієнт прочитав */}
        <div style={{
          border: '1px solid #e2e8f0', borderRadius: '8px', overflow: 'hidden',
          marginBottom: '16px', height: isMobile ? '280px' : '380px', background: '#f8fafc',
        }}>
          <iframe
            title="document-preview"
            src={document.preview_url}
            style={{width: '100%', height: '100%', border: 'none'}}
            data-testid="doc-preview-iframe"
          />
        </div>

        <a
          href={document.pdf_url}
          target="_blank"
          rel="noopener noreferrer"
          style={{fontSize: '12px', color: '#0a3d2e', textDecoration: 'underline', display: 'inline-block', marginBottom: '14px'}}
        >
          📥 Відкрити повний PDF в новій вкладці
        </a>

        {/* Чек-бокс згоди */}
        <label style={{
          display: 'flex', alignItems: 'start', gap: '10px',
          padding: '12px', background: '#f0f9ff', border: '1px solid #bae6fd',
          borderRadius: '8px', cursor: 'pointer', marginBottom: '14px',
        }}>
          <input
            type="checkbox"
            checked={agreed}
            onChange={(e) => setAgreed(e.target.checked)}
            data-testid="sign-doc-agree"
            style={{marginTop: '2px', flexShrink: 0, width: '18px', height: '18px'}}
          />
          <span style={{fontSize: '13px', color: '#0c4a6e', lineHeight: 1.4}}>
            Я ознайомлений(а) з умовами договору і погоджуюсь з ними. Я уповноважений(а) підписати документ.
          </span>
        </label>

        {/* Імʼя підписанта */}
        <div style={{marginBottom: '12px'}}>
          <label style={{fontSize: '12px', color: '#475569', marginBottom: '6px', display: 'block', fontWeight: '500'}}>
            ПІБ підписанта
          </label>
          <input
            type="text"
            value={signerName}
            onChange={(e) => setSignerName(e.target.value)}
            data-testid="sign-doc-name"
            style={{
              width: '100%', padding: '10px 12px', border: '1px solid #cbd5e1',
              borderRadius: '6px', fontSize: '14px', boxSizing: 'border-box',
            }}
          />
        </div>

        {/* Canvas для підпису */}
        <div style={{marginBottom: '10px'}}>
          <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px'}}>
            <label style={{fontSize: '12px', color: '#475569', fontWeight: '500'}}>
              Поставте підпис нижче
            </label>
            <button
              onClick={clearSig}
              type="button"
              style={{background: 'none', border: 'none', fontSize: '12px', color: '#dc2626', cursor: 'pointer', textDecoration: 'underline'}}
              data-testid="sign-doc-clear"
            >
              Очистити
            </button>
          </div>
          <canvas
            ref={canvasRef}
            width={800}
            height={240}
            data-testid="sign-doc-canvas"
            style={{
              width: '100%', height: '180px', background: '#fff',
              border: '2px dashed #cbd5e1', borderRadius: '8px',
              touchAction: 'none', cursor: 'crosshair',
            }}
          />
        </div>

        {error && (
          <div style={{
            padding: '10px 12px', background: '#fee2e2', color: '#991b1b',
            borderRadius: '6px', fontSize: '13px', marginBottom: '12px',
          }} data-testid="sign-doc-error">
            ⚠️ {error}
          </div>
        )}

        <div style={{display: 'flex', gap: '8px', marginTop: '14px'}}>
          <button
            onClick={onClose}
            type="button"
            disabled={submitting}
            style={{
              flex: '0 0 30%', padding: '12px', borderRadius: '6px',
              background: '#fff', color: '#475569', border: '1px solid #cbd5e1',
              fontSize: '13px', fontWeight: '500', cursor: 'pointer',
            }}
            data-testid="sign-doc-cancel"
          >
            Скасувати
          </button>
          <button
            onClick={submit}
            type="button"
            disabled={submitting || !agreed || !hasInk}
            data-testid="sign-doc-submit"
            className="fd-btn fd-btn-black"
            style={{
              flex: 1, padding: '12px', fontSize: '13px',
              opacity: (submitting || !agreed || !hasInk) ? 0.55 : 1,
            }}
          >
            {submitting ? 'Підписуємо...' : '✍️ Підписати документ'}
          </button>
        </div>

        <div style={{marginTop: '10px', fontSize: '11px', color: '#94a3b8', textAlign: 'center'}}>
          Підпис зберігається разом з міткою часу і вашим імʼям згідно з договором.
        </div>
      </div>
    </div>
  );
};

export default SignDocumentModal;
