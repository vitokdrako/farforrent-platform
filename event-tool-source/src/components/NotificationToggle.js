import React, { useEffect, useState } from 'react';
import { Bell, BellOff, Loader2 } from 'lucide-react';
import { pushAPI } from '../api/push';

const NotificationToggle = () => {
  const [supported, setSupported] = useState(false);
  const [permission, setPermission] = useState('default');
  const [subscribed, setSubscribed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    (async () => {
      const ok = await pushAPI.isSupported();
      setSupported(ok);
      if (!ok) return;
      setPermission(await pushAPI.getPermission());
      if ('serviceWorker' in navigator) {
        const reg = await navigator.serviceWorker.getRegistration();
        if (reg) {
          const sub = await reg.pushManager.getSubscription();
          setSubscribed(!!sub);
        }
      }
    })();
  }, []);

  const handleToggle = async () => {
    setBusy(true); setMsg('');
    try {
      if (subscribed) {
        await pushAPI.unsubscribe();
        setSubscribed(false);
        setMsg('Push-сповіщення вимкнено');
      } else {
        await pushAPI.subscribe();
        setSubscribed(true);
        setPermission('granted');
        setMsg('Push-сповіщення увімкнено!');
      }
    } catch (e) {
      setMsg(e.message || 'Помилка');
    } finally {
      setBusy(false);
      setTimeout(() => setMsg(''), 4000);
    }
  };

  const handleTest = async () => {
    setBusy(true);
    try {
      const r = await pushAPI.sendTest();
      setMsg(r.sent ? `Відправлено: ${r.sent}` : 'Не вдалось — перевірте дозволи');
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
      setTimeout(() => setMsg(''), 4000);
    }
  };

  if (!supported) {
    return (
      <div data-testid="push-not-supported" style={{
        padding: 12, borderRadius: 8, background: '#fff3e0', color: '#7c5e1e', fontSize: 13,
      }}>
        Цей браузер не підтримує push-сповіщення
      </div>
    );
  }

  return (
    <div data-testid="notification-toggle" style={{
      padding: 16, borderRadius: 8, background: '#fafafa', border: '1px solid #ececec',
      display: 'flex', flexDirection: 'column', gap: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        {subscribed ? (
          <Bell size={20} color="#2e7d32" />
        ) : (
          <BellOff size={20} color="#888" />
        )}
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: 14, color: '#222' }}>
            Push-сповіщення
          </div>
          <div style={{ fontSize: 12, color: '#888' }}>
            {subscribed
              ? 'Отримуйте оновлення про статус замовлень'
              : 'Будьте в курсі змін по замовленню одразу'}
          </div>
        </div>
        <button
          onClick={handleToggle}
          disabled={busy || permission === 'denied'}
          data-testid="push-toggle-btn"
          style={{
            background: subscribed ? '#fff' : '#222',
            color: subscribed ? '#222' : '#fff',
            border: subscribed ? '1px solid #ccc' : 'none',
            borderRadius: 999, padding: '8px 16px', fontSize: 13, fontWeight: 500,
            cursor: busy ? 'wait' : 'pointer',
            display: 'inline-flex', alignItems: 'center', gap: 6,
          }}
        >
          {busy ? <Loader2 size={14} className="animate-spin" /> : null}
          {subscribed ? 'Вимкнути' : 'Увімкнути'}
        </button>
      </div>
      {subscribed && (
        <button
          onClick={handleTest}
          disabled={busy}
          data-testid="push-test-btn"
          style={{
            alignSelf: 'flex-start', background: 'none', border: 'none',
            color: '#1565c0', fontSize: 12, cursor: 'pointer', padding: 0,
          }}
        >
          Надіслати тестове сповіщення →
        </button>
      )}
      {permission === 'denied' && (
        <div style={{ fontSize: 12, color: '#c62828' }}>
          Сповіщення заблоковано в налаштуваннях браузера. Дозвольте їх вручну і перезавантажте сторінку.
        </div>
      )}
      {msg && (
        <div style={{ fontSize: 12, color: '#2e7d32' }} data-testid="push-msg">
          {msg}
        </div>
      )}
    </div>
  );
};

export default NotificationToggle;
