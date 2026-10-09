import api from './axios';

const SW_URL = '/sw.js';

const urlBase64ToUint8Array = (base64String) => {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)));
};

export const pushAPI = {
  async getPublicKey() {
    const { data } = await api.get('/event/push/public-key');
    return data.public_key;
  },

  async isSupported() {
    return (
      'serviceWorker' in navigator &&
      'PushManager' in window &&
      'Notification' in window
    );
  },

  async getPermission() {
    if (!('Notification' in window)) return 'denied';
    return Notification.permission;
  },

  async requestPermission() {
    if (!('Notification' in window)) return 'denied';
    return await Notification.requestPermission();
  },

  async registerSW() {
    if (!('serviceWorker' in navigator)) throw new Error('No SW support');
    return await navigator.serviceWorker.register(SW_URL);
  },

  async subscribe() {
    if (!(await this.isSupported())) throw new Error('Push не підтримується цим браузером');
    const perm = await this.requestPermission();
    if (perm !== 'granted') throw new Error('Дозвіл на сповіщення відхилено');

    const reg = await this.registerSW();
    await navigator.serviceWorker.ready;

    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
      const publicKey = await this.getPublicKey();
      if (!publicKey) throw new Error('VAPID ключ не налаштовано на сервері');
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicKey),
      });
    }

    const subData = sub.toJSON();
    await api.post('/event/push/subscribe', {
      endpoint: subData.endpoint,
      keys: subData.keys,
      user_agent: navigator.userAgent.slice(0, 200),
    });
    return sub;
  },

  async unsubscribe() {
    if (!('serviceWorker' in navigator)) return;
    const reg = await navigator.serviceWorker.getRegistration();
    if (!reg) return;
    const sub = await reg.pushManager.getSubscription();
    if (sub) {
      await api.post('/event/push/unsubscribe', { endpoint: sub.endpoint });
      await sub.unsubscribe();
    }
  },

  async sendTest() {
    const { data } = await api.post('/event/push/test');
    return data;
  },
};

export default pushAPI;
