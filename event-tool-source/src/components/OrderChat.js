import React, { useEffect, useRef, useState } from 'react';
import { Send, Loader2, MessageCircle, Wifi, WifiOff } from 'lucide-react';
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

const wsUrl = (orderId, token) => {
  // REACT_APP_BACKEND_URL → https://x.com  → wss://x.com/api/ws/...
  const base = (process.env.REACT_APP_BACKEND_URL || window.location.origin)
    .replace(/^http(s?):\/\//, (m, s) => `ws${s}://`);
  return `${base}/api/ws/chat/client/${orderId}?token=${encodeURIComponent(token)}`;
};

const OrderChat = ({ orderId, orderNumber }) => {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  const [wsConnected, setWsConnected] = useState(false);
  const [typingPeer, setTypingPeer] = useState(false);

  const scrollRef = useRef(null);
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);
  const pollRef = useRef(null);
  const typingTimerRef = useRef(null);
  const heartbeatRef = useRef(null);

  // --- WebSocket connection ---
  const connectWS = () => {
    const token = localStorage.getItem('access_token');
    if (!token) return;
    try {
      const ws = new WebSocket(wsUrl(orderId, token));
      wsRef.current = ws;

      ws.onopen = () => {
        setWsConnected(true);
        setError('');
        // Stop polling fallback
        if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
        // Start heartbeat
        heartbeatRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' }));
        }, 25000);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          switch (data.type) {
            case 'init':
              setMessages(data.messages || []);
              setLoading(false);
              break;
            case 'new_message':
              setMessages((prev) => [...prev, data.message]);
              break;
            case 'typing':
              setTypingPeer(!!data.is_typing);
              if (data.is_typing) {
                setTimeout(() => setTypingPeer(false), 3000);
              }
              break;
            case 'read_receipt':
              // Could update UI indicating peer has read messages
              break;
            case 'error':
              setError(data.message || 'WS error');
              break;
            case 'pong':
              // No-op heartbeat
              break;
            default:
              break;
          }
        } catch (e) {
          console.warn('Bad WS message:', e);
        }
      };

      ws.onclose = (ev) => {
        setWsConnected(false);
        if (heartbeatRef.current) { clearInterval(heartbeatRef.current); heartbeatRef.current = null; }
        // Auth-related close codes → fallback to polling, don't reconnect
        if (ev.code === 4401 || ev.code === 4403 || ev.code === 4404) {
          startPolling();
          return;
        }
        // Reconnect with backoff
        reconnectRef.current = setTimeout(connectWS, 3000);
      };

      ws.onerror = (e) => {
        console.warn('WS error:', e);
      };
    } catch (e) {
      console.warn('connectWS failed:', e);
      startPolling();
    }
  };

  // --- Polling fallback (when WS unavailable) ---
  const loadHttp = async () => {
    try {
      const msgs = await chatAPI.list(orderId);
      setMessages(msgs);
      setLoading(false);
      setError('');
    } catch (e) {
      setError('Не вдалося завантажити повідомлення');
    }
  };
  const startPolling = () => {
    if (pollRef.current) return;
    loadHttp();
    pollRef.current = setInterval(loadHttp, 10000);
  };

  useEffect(() => {
    if (typeof window !== 'undefined' && 'WebSocket' in window) {
      connectWS();
    } else {
      startPolling();
    }
    return () => {
      if (wsRef.current) {
        try { wsRef.current.close(); } catch (e) { /* noop */ }
        wsRef.current = null;
      }
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      if (pollRef.current) clearInterval(pollRef.current);
      if (heartbeatRef.current) clearInterval(heartbeatRef.current);
    };
  }, [orderId]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // --- Send message ---
  const handleSend = async (e) => {
    e?.preventDefault();
    const msg = text.trim();
    if (!msg || sending) return;
    setSending(true);
    try {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'send', message: msg }));
        setText('');
      } else {
        const updated = await chatAPI.send(orderId, msg);
        setMessages(updated);
        setText('');
      }
    } catch (err) {
      setError(err?.response?.data?.detail || 'Не вдалося надіслати');
    } finally {
      setSending(false);
    }
  };

  // --- Typing indicator (debounced) ---
  const handleTyping = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'typing', is_typing: true }));
      if (typingTimerRef.current) clearTimeout(typingTimerRef.current);
      typingTimerRef.current = setTimeout(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: 'typing', is_typing: false }));
        }
      }, 2000);
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
        <span style={{ flex: 1 }}>
          Чат з менеджером {orderNumber ? `· ${orderNumber}` : ''}
        </span>
        <span title={wsConnected ? 'Real-time підключено' : 'Працює через опитування'}>
          {wsConnected ? <Wifi size={14} /> : <WifiOff size={14} style={{ opacity: 0.5 }} />}
        </span>
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
        {typingPeer && (
          <div
            data-testid="typing-indicator"
            style={{ alignSelf: 'flex-start', color: '#888', fontSize: 12, padding: '4px 8px' }}
          >
            Менеджер пише…
          </div>
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
          onChange={(e) => { setText(e.target.value); handleTyping(); }}
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
