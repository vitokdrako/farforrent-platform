import React, { useEffect, useState } from 'react';
import { X, Plus, Calendar, Loader2, CheckCircle } from 'lucide-react';
import { boardsAPI } from '../api/boards';

const formatDate = (iso) => {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString('uk-UA', {
      day: '2-digit', month: '2-digit', year: 'numeric',
    });
  } catch { return iso; }
};

const AddToBoardModal = ({ product, onClose, onAdded, quantity = 1 }) => {
  const [boards, setBoards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(null);     // boardId
  const [added, setAdded] = useState({});         // boardId → true
  const [error, setError] = useState('');
  const [showNewForm, setShowNewForm] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDate, setNewDate] = useState('');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const all = await boardsAPI.getBoards();
        const list = Array.isArray(all) ? all : (all?.boards || []);
        setBoards(list);
      } catch (e) {
        console.error('Failed to load boards:', e);
        setError(`Не вдалося завантажити проєкти: ${e?.response?.data?.detail || e?.message || 'Невідома помилка'}`);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const handleAdd = async (board) => {
    if (adding) return;
    setAdding(board.id);
    setError('');
    try {
      await boardsAPI.addItem(board.id, {
        product_id: product.product_id,
        quantity,
      });
      setAdded((prev) => ({ ...prev, [board.id]: true }));
      onAdded && onAdded(board);
      // Auto-close after 600ms
      setTimeout(() => onClose && onClose(), 600);
    } catch (e) {
      setError(e?.response?.data?.detail || 'Не вдалося додати в проєкт');
    } finally {
      setAdding(null);
    }
  };

  const handleCreateAndAdd = async (e) => {
    e?.preventDefault();
    if (!newName.trim() || !newDate || creating) return;
    setCreating(true);
    setError('');
    try {
      const created = await boardsAPI.create({
        board_name: newName.trim(),
        event_date: newDate,
        event_type: 'event',
        rental_start_date: newDate,
        rental_end_date: newDate,
      });
      await boardsAPI.addItem(created.id, {
        product_id: product.product_id,
        quantity,
      });
      setAdded({ [created.id]: true });
      onAdded && onAdded(created);
      setTimeout(() => onClose && onClose(), 600);
    } catch (e) {
      setError(e?.response?.data?.detail || 'Не вдалося створити проєкт');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div
      data-testid="add-to-board-modal"
      onClick={(e) => { if (e.target === e.currentTarget) onClose && onClose(); }}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', zIndex: 1000,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '16px', animation: 'fadeIn 0.2s ease',
      }}
    >
      <div
        style={{
          background: '#fff', borderRadius: '16px', width: '100%', maxWidth: 520,
          maxHeight: '85vh', overflow: 'hidden', display: 'flex', flexDirection: 'column',
          boxShadow: '0 8px 40px rgba(0,0,0,0.25)',
        }}
      >
        {/* Header */}
        <div style={{
          padding: '16px 20px', borderBottom: '1px solid #ececec',
          display: 'flex', alignItems: 'center', gap: 12,
        }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 16, fontWeight: 600, color: '#222' }}>
              Додати в проєкт
            </div>
            <div style={{ fontSize: 13, color: '#888', marginTop: 2 }}>
              {product.name}
            </div>
          </div>
          <button
            onClick={onClose}
            data-testid="add-to-board-close"
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}
            aria-label="Закрити"
          >
            <X size={22} color="#666" />
          </button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px' }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <Loader2 size={26} className="animate-spin" color="#888" />
            </div>
          ) : (
            <>
              {boards.length > 0 && (
                <div style={{ marginBottom: 16 }}>
                  <div style={{
                    fontSize: 11, fontWeight: 600, color: '#888',
                    textTransform: 'uppercase', letterSpacing: '0.06em',
                    marginBottom: 8, padding: '0 4px',
                  }}>
                    Ваші проєкти
                  </div>
                  {boards.map((b) => {
                    const isAdded = !!added[b.id];
                    const isAdding = adding === b.id;
                    return (
                      <button
                        key={b.id}
                        onClick={() => !isAdded && handleAdd(b)}
                        disabled={isAdded || isAdding}
                        data-testid={`add-to-board-${b.id}`}
                        style={{
                          width: '100%', display: 'flex', alignItems: 'center', gap: 12,
                          padding: '12px 14px', borderRadius: 10,
                          border: '1px solid #ececec', background: isAdded ? '#e8f5e9' : '#fff',
                          marginBottom: 8, cursor: isAdded ? 'default' : 'pointer',
                          textAlign: 'left', fontFamily: 'inherit',
                          transition: 'background 0.15s ease',
                        }}
                      >
                        <div style={{
                          width: 36, height: 36, borderRadius: 8,
                          background: '#0a3d2e', color: '#fff',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: 14, fontWeight: 600, flexShrink: 0,
                        }}>
                          {(b.board_name || 'P').charAt(0).toUpperCase()}
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{
                            fontSize: 14, fontWeight: 600, color: '#222',
                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                          }}>
                            {b.board_name}
                          </div>
                          <div style={{ fontSize: 12, color: '#888', display: 'flex', alignItems: 'center', gap: 6 }}>
                            <Calendar size={12} />
                            {b.event_date ? formatDate(b.event_date) : 'Дата не вказана'}
                            {b.items_count != null && (
                              <span style={{ marginLeft: 6 }}>· {b.items_count} поз.</span>
                            )}
                          </div>
                        </div>
                        {isAdded ? (
                          <CheckCircle size={20} color="#2e7d32" />
                        ) : isAdding ? (
                          <Loader2 size={18} className="animate-spin" color="#888" />
                        ) : (
                          <Plus size={20} color="#0a3d2e" />
                        )}
                      </button>
                    );
                  })}
                </div>
              )}

              {/* New project form */}
              {!showNewForm ? (
                <button
                  onClick={() => setShowNewForm(true)}
                  data-testid="show-new-board-form"
                  style={{
                    width: '100%', padding: '14px', borderRadius: 10,
                    border: '1.5px dashed #ccc', background: '#fafafa',
                    cursor: 'pointer', display: 'flex', alignItems: 'center',
                    justifyContent: 'center', gap: 8, color: '#666',
                    fontSize: 14, fontFamily: 'inherit',
                  }}
                >
                  <Plus size={16} />
                  Створити новий проєкт
                </button>
              ) : (
                <form
                  onSubmit={handleCreateAndAdd}
                  style={{
                    padding: 14, borderRadius: 10, background: '#fafafa',
                    border: '1px solid #ececec',
                  }}
                  data-testid="new-board-form"
                >
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#222', marginBottom: 10 }}>
                    Новий проєкт
                  </div>
                  <input
                    type="text"
                    placeholder="Назва події (наприклад, Весілля Лілії)"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    data-testid="new-board-name"
                    required
                    style={{
                      width: '100%', padding: '10px 12px', borderRadius: 8,
                      border: '1px solid #ddd', fontSize: 14, marginBottom: 8,
                      boxSizing: 'border-box', fontFamily: 'inherit',
                    }}
                  />
                  <input
                    type="date"
                    value={newDate}
                    onChange={(e) => setNewDate(e.target.value)}
                    data-testid="new-board-date"
                    min={new Date().toISOString().split('T')[0]}
                    required
                    style={{
                      width: '100%', padding: '10px 12px', borderRadius: 8,
                      border: '1px solid #ddd', fontSize: 14, marginBottom: 10,
                      boxSizing: 'border-box', fontFamily: 'inherit',
                    }}
                  />
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button
                      type="button"
                      onClick={() => setShowNewForm(false)}
                      style={{
                        flex: 1, padding: '10px', borderRadius: 8,
                        border: '1px solid #ccc', background: '#fff', cursor: 'pointer',
                        fontSize: 13, fontFamily: 'inherit',
                      }}
                    >
                      Скасувати
                    </button>
                    <button
                      type="submit"
                      disabled={creating || !newName.trim() || !newDate}
                      data-testid="create-board-submit"
                      style={{
                        flex: 1, padding: '10px', borderRadius: 8, border: 'none',
                        background: '#0a3d2e', color: '#fff', cursor: 'pointer',
                        fontSize: 13, fontWeight: 600, fontFamily: 'inherit',
                        opacity: creating || !newName.trim() || !newDate ? 0.6 : 1,
                      }}
                    >
                      {creating ? 'Створюю…' : 'Створити і додати'}
                    </button>
                  </div>
                </form>
              )}

              {error && (
                <div style={{
                  marginTop: 12, padding: '10px 12px', borderRadius: 8,
                  background: '#ffebee', color: '#c62828', fontSize: 13,
                }}>
                  {error}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default AddToBoardModal;
