/**
 * EventBus - простий механізм для оновлення UI в реальному часі
 * 
 * Використання:
 * 
 * 1. Підписатись на подію:
 *    useEffect(() => {
 *      const unsubscribe = eventBus.on('finance:updated', (data) => {
 *        refetchData();
 *      });
 *      return () => unsubscribe();
 *    }, []);
 * 
 * 2. Викликати подію:
 *    eventBus.emit('finance:updated', { orderId: 123 });
 */

class EventBus {
  constructor() {
    this.events = {};
  }

  /**
   * Підписатись на подію
   * @param {string} event - назва події
   * @param {Function} callback - функція-обробник
   * @returns {Function} - функція для відписки
   */
  on(event, callback) {
    if (!this.events[event]) {
      this.events[event] = [];
    }
    this.events[event].push(callback);
    
    // Повернути функцію для відписки
    return () => {
      this.events[event] = this.events[event].filter(cb => cb !== callback);
    };
  }

  /**
   * Викликати подію
   * @param {string} event - назва події
   * @param {any} data - дані події
   */
  emit(event, data) {
    if (this.events[event]) {
      this.events[event].forEach(callback => {
        try {
          callback(data);
        } catch (err) {
          console.error(`EventBus error in ${event}:`, err);
        }
      });
    }
  }

  /**
   * Відписатись від всіх обробників події
   * @param {string} event - назва події
   */
  off(event) {
    delete this.events[event];
  }
}

// Singleton instance
const eventBus = new EventBus();

// Стандартні події
export const EVENTS = {
  // Фінанси
  FINANCE_UPDATED: 'finance:updated',
  PAYMENT_CREATED: 'finance:payment_created',
  DEPOSIT_CREATED: 'finance:deposit_created',
  DEPOSIT_REFUNDED: 'finance:deposit_refunded',
  
  // Замовлення
  ORDER_UPDATED: 'order:updated',
  ORDER_STATUS_CHANGED: 'order:status_changed',
  
  // Issue cards
  ISSUE_CARD_UPDATED: 'issue:updated',
  
  // Глобальний refetch
  REFETCH_ALL: 'global:refetch',
};

export default eventBus;
