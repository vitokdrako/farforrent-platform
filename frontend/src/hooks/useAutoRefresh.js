/* eslint-disable */
import { useState, useEffect, useCallback, useRef } from 'react'
import axios from 'axios'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''

/**
 * useOrderSync - Хук для синхронізації змін між користувачами
 * Перевіряє тільки timestamp - легкий запит кожні N секунд
 * Оновлює дані тільки якщо хтось інший зберіг зміни
 * 
 * ОПТИМІЗАЦІЯ P0.2:
 * - Коли WebSocket підключений (wsConnected: true), polling вимикається
 * - Fallback polling збільшено до 60 секунд (замість 10)
 * 
 * @param {string} orderId - ID замовлення
 * @param {Function} onUpdate - Callback коли потрібно оновити дані
 * @param {number} intervalMs - Інтервал перевірки (default: 10000 = 10 сек)
 * @param {boolean} enabled - Чи включено синхронізацію
 * @param {Object} options - Додаткові опції
 * @param {boolean} options.wsConnected - Чи підключений WebSocket (вимикає polling)
 */
export function useOrderSync(orderId, onUpdate, intervalMs = 10000, enabled = true, options = {}) {
  const { wsConnected = false } = options
  
  const [lastKnownModified, setLastKnownModified] = useState(null)
  const [lastModifiedBy, setLastModifiedBy] = useState(null)
  const [hasNewChanges, setHasNewChanges] = useState(false)
  const intervalRef = useRef(null)
  const isMyUpdate = useRef(false)

  // ОПТИМІЗАЦІЯ P0.2: Визначаємо чи потрібен polling
  // Якщо WS активний - polling вимкнено повністю (або рідкий fallback 60с)
  const pollingEnabled = enabled && !wsConnected
  const effectiveInterval = wsConnected ? 60000 : intervalMs  // 60s fallback якщо WS

  // Перевірка timestamp
  const checkForUpdates = useCallback(async () => {
    if (!orderId || !pollingEnabled) return
    
    try {
      const response = await axios.get(`${BACKEND_URL}/api/orders/${orderId}/last-modified`)
      const { last_modified, modified_by } = response.data
      
      if (last_modified && lastKnownModified) {
        // Порівнюємо timestamps
        if (last_modified !== lastKnownModified && !isMyUpdate.current) {
          // Хтось інший зберіг зміни!
          setHasNewChanges(true)
          setLastModifiedBy(modified_by)
          
          // Автоматично оновлюємо дані
          if (onUpdate) {
            onUpdate()
          }
        }
      }
      
      setLastKnownModified(last_modified)
      isMyUpdate.current = false
      
    } catch (err) {
      // Тихо ігноруємо помилки - це фоновий процес
    }
  }, [orderId, pollingEnabled, lastKnownModified, onUpdate])

  // Позначити що ми самі зберегли (щоб не реагувати на свої зміни)
  const markMyUpdate = useCallback(async () => {
    isMyUpdate.current = true
    
    // Оновлюємо timestamp на сервері
    try {
      const user = JSON.parse(localStorage.getItem('user') || '{}')
      await axios.post(`${BACKEND_URL}/api/orders/${orderId}/touch`, null, {
        params: {
          user_id: user.id || user.user_id,
          user_name: user.name || user.username || 'Невідомий'
        }
      })
    } catch (err) {
      console.warn('[useOrderSync] Failed to touch order:', err)
    }
  }, [orderId])

  // Скинути прапорець нових змін
  const dismissChanges = useCallback(() => {
    setHasNewChanges(false)
    setLastModifiedBy(null)
  }, [])

  // Запуск polling - ОПТИМІЗОВАНО
  useEffect(() => {
    // Очистити попередній interval
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    
    // ОПТИМІЗАЦІЯ P0.2: Не запускаємо polling якщо WS активний
    if (!pollingEnabled || !orderId) {
      return
    }

    // Перша перевірка одразу
    checkForUpdates()

    // Запускаємо interval з ефективним інтервалом
    intervalRef.current = setInterval(checkForUpdates, effectiveInterval)

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [pollingEnabled, orderId, effectiveInterval, checkForUpdates])

  return {
    hasNewChanges,
    lastModifiedBy,
    markMyUpdate,
    dismissChanges,
    checkForUpdates,
    pollingActive: pollingEnabled,  // Експортуємо для дебагу
  }
}

/**
 * useAutoRefresh - Оригінальний хук (залишаємо для зворотної сумісності)
 * Але тепер він НЕ робить автоматичне оновлення
 */
export function useAutoRefresh(fetchFn, intervalMs = 30000, enabled = true, deps = []) {
  const [lastUpdate, setLastUpdate] = useState(null)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const fetchFnRef = useRef(fetchFn)
  
  useEffect(() => {
    fetchFnRef.current = fetchFn
  }, [fetchFn])

  const refresh = useCallback(async (silent = true) => {
    try {
      if (!silent) setIsRefreshing(true)
      await fetchFnRef.current()
      setLastUpdate(new Date())
    } catch (err) {
      console.error('[useAutoRefresh] Error refreshing:', err)
    } finally {
      setIsRefreshing(false)
    }
  }, [])

  return {
    refresh,
    lastUpdate,
    isRefreshing,
  }
}

/**
 * Форматування часу останнього оновлення
 */
export function formatLastUpdate(date) {
  if (!date) return ''
  
  const now = new Date()
  const diff = Math.floor((now - date) / 1000)
  
  if (diff < 10) return 'щойно'
  if (diff < 60) return `${diff} сек тому`
  if (diff < 3600) return `${Math.floor(diff / 60)} хв тому`
  
  return date.toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' })
}

export default useOrderSync

