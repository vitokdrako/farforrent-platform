/**
 * Плаваюча кнопка-лупа для пошуку на мобільному + модалка з полем.
 */
import React, { useState, useEffect, useRef } from 'react';
import { Search, X } from 'lucide-react';

const MobileSearchFab = ({ value, onChange, placeholder }) => {
  const [open, setOpen] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    if (open && inputRef.current) inputRef.current.focus();
  }, [open]);

  // Закриваємо ESC
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    if (open) window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  return (
    <>
      {/* FAB-кнопка лупа */}
      <button
        type="button"
        className="mobile-search-fab"
        onClick={() => setOpen(true)}
        aria-label="Пошук"
        data-testid="mobile-search-fab"
      >
        <Search size={20} strokeWidth={2.4} />
        {value ? <span className="mobile-search-fab-dot" /> : null}
      </button>

      {/* Модалка з полем пошуку */}
      {open && (
        <div className="mobile-search-modal" data-testid="mobile-search-modal" onClick={() => setOpen(false)}>
          <div className="mobile-search-modal-inner" onClick={(e) => e.stopPropagation()}>
            <div className="mobile-search-input-row">
              <Search size={18} strokeWidth={2.2} style={{color: '#94a3b8'}} />
              <input
                ref={inputRef}
                type="text"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder={placeholder || 'Назва, артикул, категорія...'}
                className="mobile-search-input"
                data-testid="mobile-search-input"
              />
              {value && (
                <button
                  type="button"
                  onClick={() => onChange('')}
                  className="mobile-search-clear"
                  aria-label="Очистити"
                  data-testid="mobile-search-clear"
                >
                  <X size={18} />
                </button>
              )}
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="mobile-search-close"
                data-testid="mobile-search-close"
              >
                Готово
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default MobileSearchFab;
