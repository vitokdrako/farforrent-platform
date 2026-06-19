import React, { useEffect, useRef, useState } from 'react';
import { Send, Loader2, MessageCircle } from 'lucide-react';
import { chatAPI } from '../api/chat';

const formatTime = (iso) => {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return d.toLocaleString('uk-UA', {
      day: '2-digit', month: '2-digit',
      hour: '2-digit', minute: '2-digit'
    });
  } catch { return ''; }
};

const OrderChat = ({ orderId, orderNumber }) => {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  const scrollRef = useRef(null);
  const pollRef = useRef(null);

  const load = async () => {
    try {
      const msgs = await chatAPI.list(orderId);
      setMessages(msgs);
      setError('');
    } catch (e) {
      console.error(e);
      setError('Не вдалося завантажити повідомлення');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // Poll every 10s while chat is open
    pollRef.current = setInterval(load, 10000);
    return () => pollRef.current && clearInterval(pollRef.current);
  }, [orderId]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = async (e) => {
    e?.preventDefault();
    const msg = text.trim();
    if (!msg || sending) return;
    setSending(true);
    try {
      const updated = await chatAPI.send(orderId, msg);
      setMessages(updated);
      setText('');
    } catch (err) {
      setError(err?.response?.data?.detail || 'Не вдалося надіслати');
    } finally {
      setSending(false);
    }
  };

  return (
    <div
      data-testid={`order-chat-${orderId}`}
      style={{
        background: '#fff', border: '1px solid #e6e1d2',
        borderRadius: 12, overflow: 'hidden', display: 'flex',
        flexDirection: 'column', maxHeight: 460,
      }}
    >
      <div style={{
        padding: '10px 14px', background: '#0a3d2e', color: '#fff',
        display: 'flex', alignItems: 'center', gap: 8, fontSize: 14, fontWeight: 600,
      }}>
        <MessageCircle size={16} />
        Чат з менеджером {orderNumber ? `· ${orderNumber}` : ''}
      </div>

      <div
        ref={scrollRef}
        style={{
          flex: 1, padding: 12, overflowY: 'auto', minHeight: 220,
          background: '#fbf9f3', display: 'flex', flexDirection: 'column', gap: 8,
        }}
      >
        {loading ? (
          <div style={{ textAlign: 'center', color: '#888', padding: 20 }}>
            <Loader2 size={20} className="animate-spin" />
          </div>
        ) : messages.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#888', padding: 30, fontSize: 13 }}>
            Поки немає повідомлень. Напишіть менеджеру першим!
          </div>
        ) : (
          messages.map((m) => {
            const mine = m.sender_type === 'client';
            return (
              <div
                key={m.id}
                data-testid={`chat-msg-${m.id}`}
                style={{
                  alignSelf: mine ? 'flex-end' : 'flex-start',
                  maxWidth: '78%',
                  background: mine ? '#0a3d2e' : '#fff',
                  color: mine ? '#fff' : '#222',
                  borderRadius: mine ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
                  padding: '8px 12px',
                  fontSize: 14,
                  border: mine ? 'none' : '1px solid #e6e1d2',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
                }}
              >
                {!mine && (
                  <div style={{ fontSize: 11, color: '#888', marginBottom: 2 }}>
                    {m.sender_name || 'Менеджер'}
                  </div>
                )}
                <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                  {m.message}
                </div>
                <div style={{
                  fontSize: 10, marginTop: 4,
                  textAlign: 'right', opacity: 0.7,
                }}>
                  {formatTime(m.created_at)}
                </div>
              </div>
            );
          })
        )}
      </div>

      {error && (
        <div style={{
          padding: '6px 12px', background: '#ffebee', color: '#c62828',
          fontSize: 12, borderTop: '1px solid #ffcdd2',
        }}>
          {error}
        </div>
      )}

      <form
        onSubmit={handleSend}
        style={{
          display: 'flex', gap: 8, padding: 10, borderTop: '1px solid #e6e1d2',
          background: '#fff',
        }}
      >
        <textarea
          rows={1}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
          }}
          placeholder="Напишіть повідомлення…"
          data-testid={`chat-input-${orderId}`}
          style={{
            flex: 1, resize: 'none', border: '1px solid #ddd', borderRadius: 8,
            padding: '8px 10px', fontSize: 14, fontFamily: 'inherit', minHeight: 38,
            maxHeight: 100,
          }}
        />
        <button
          type="submit"
          disabled={sending || !text.trim()}
          data-testid={`chat-send-${orderId}`}
          style={{
            background: '#0a3d2e', color: '#fff', border: 'none', borderRadius: 8,
            padding: '0 14px', cursor: sending ? 'wait' : 'pointer',
            display: 'inline-flex', alignItems: 'center', gap: 6,
            opacity: sending || !text.trim() ? 0.6 : 1,
          }}
        >
          {sending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
        </button>
      </form>
    </div>
  );
};

export default OrderChat;
