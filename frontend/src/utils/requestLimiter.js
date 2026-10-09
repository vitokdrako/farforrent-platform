/**
 * Request Limiter - обмежує кількість паралельних запитів
 * Вирішує проблему ERR_HTTP2_SERVER_REFUSED_STREAM
 */

class RequestLimiter {
  constructor(maxConcurrent = 4, delayBetween = 100) {
    this.maxConcurrent = maxConcurrent;
    this.delayBetween = delayBetween;
    this.queue = [];
    this.activeCount = 0;
  }

  async add(requestFn) {
    return new Promise((resolve, reject) => {
      this.queue.push({ requestFn, resolve, reject });
      this.processQueue();
    });
  }

  async processQueue() {
    if (this.activeCount >= this.maxConcurrent || this.queue.length === 0) {
      return;
    }

    this.activeCount++;
    const { requestFn, resolve, reject } = this.queue.shift();

    try {
      const result = await requestFn();
      resolve(result);
    } catch (error) {
      reject(error);
    } finally {
      this.activeCount--;
      
      // Затримка між запитами
      if (this.queue.length > 0) {
        setTimeout(() => this.processQueue(), this.delayBetween);
      }
    }
  }

  // Скинути чергу (при unmount компонента)
  clear() {
    this.queue.forEach(item => item.reject(new Error('Request cancelled')));
    this.queue = [];
  }
}

// Глобальний екземпляр - обмеження на 4 паралельні запити
export const globalLimiter = new RequestLimiter(4, 100);

// Хелпер для fetch з лімітером
export const limitedFetch = (url, options = {}) => {
  return globalLimiter.add(() => fetch(url, options));
};

// Хелпер для authenticated fetch з лімітером
export const limitedAuthFetch = (url, options = {}) => {
  const token = localStorage.getItem('token');
  return globalLimiter.add(() => 
    fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        ...options.headers,
      },
    })
  );
};

export default RequestLimiter;
