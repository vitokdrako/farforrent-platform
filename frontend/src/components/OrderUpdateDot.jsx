/* eslint-disable */
/**
 * OrderUpdateDot - Компактний індикатор оновлень для карток замовлень
 * 
 * Показує червону крапку коли замовлення має нові зміни
 * від інших користувачів
 */

import React, { useState, useEffect, useCallback } from 'react'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''

/**
 * Хук для перевірки оновлень замовлення (без WebSocket - просто перевірка timestamp)
 */
export function useOrderUpdateCheck(orderId, lastKnownTimestamp) {
  const [hasUpdate, setHasUpdate] = useState(false)
  const [lastModifiedBy, setLastModifiedBy] = useState(null)
  const [serverTimestamp, setServerTimestamp] = useState(null)

  const checkUpdate = useCallback(async () => {
    if (!orderId) return

    try {
      const response = await fetch(`${BACKEND_URL}/api/orders/${orderId}/last-modified`)
      const data = await response.json()
      
      if (data.last_modified) {
        setServerTimestamp(data.last_modified)
        setLastModifiedBy(data.modified_by)
        
        // Якщо є lastKnownTimestamp і сервер має новіший - є оновлення
        if (lastKnownTimestamp && data.last_modified > lastKnownTimestamp) {
          setHasUpdate(true)
        }
      }
    } catch (e) {
      // Silent fail
    }
  }, [orderId, lastKnownTimestamp])

  useEffect(() => {
    checkUpdate()
    // Перевіряти кожні 30 секунд
    const interval = setInterval(checkUpdate, 30000)
    return () => clearInterval(interval)
  }, [checkUpdate])

  const dismiss = useCallback(() => {
    setHasUpdate(false)
  }, [])

  return { hasUpdate, lastModifiedBy, serverTimestamp, dismiss, checkUpdate }
}

/**
 * Компонент червоної крапки - показує що є оновлення
 */
export function OrderUpdateDot({ 
  show, 
  position = 'top-right', 
  size = 'sm',
  pulse = true,
  tooltip,
  onClick 
}) {
  if (!show) return null

  const positionClasses = {
    'top-right': 'top-0 right-0 -mt-1 -mr-1',
    'top-left': 'top-0 left-0 -mt-1 -ml-1',
    'bottom-right': 'bottom-0 right-0 -mb-1 -mr-1',
    'bottom-left': 'bottom-0 left-0 -mb-1 -ml-1',
    'inline': 'relative'
  }

  const sizeClasses = {
    'xs': 'h-2 w-2',
    'sm': 'h-2.5 w-2.5',
    'md': 'h-3 w-3',
    'lg': 'h-4 w-4'
  }

  const posClass = positionClasses[position] || positionClasses['top-right']
  const sizeClass = sizeClasses[size] || sizeClasses['sm']

  return (
    <span 
      className={`absolute ${posClass} flex ${sizeClass}`}
      title={tooltip || 'Є нові зміни'}
      onClick={onClick}
    >
      {pulse && (
        <span className={`animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75`}></span>
      )}
      <span className={`relative inline-flex rounded-full ${sizeClass} bg-red-500`}></span>
    </span>
  )
}

/**
 * Обгортка для картки з індикатором оновлень
 */
export function OrderCardWithUpdateIndicator({ 
  orderId, 
  children, 
  lastKnownTimestamp,
  onUpdateClick,
  className = ''
}) {
  const { hasUpdate, lastModifiedBy } = useOrderUpdateCheck(orderId, lastKnownTimestamp)

  return (
    <div className={`relative ${className}`}>
      {children}
      <OrderUpdateDot 
        show={hasUpdate} 
        tooltip={lastModifiedBy ? `Оновлено: ${lastModifiedBy}` : 'Є нові зміни'}
        onClick={onUpdateClick}
      />
    </div>
  )
}

/**
 * Батч перевірка оновлень для списку замовлень
 * (оптимізовано для Dashboard - один запит замість багатьох)
 */
export function useBatchOrderUpdates(orderIds, knownTimestamps = {}) {
  const [updates, setUpdates] = useState({}) // { orderId: { hasUpdate, modifiedBy, timestamp } }

  const checkUpdates = useCallback(async () => {
    if (!orderIds || orderIds.length === 0) return

    try {
      // Можна зробити batch endpoint, але поки просто перевіряємо перші 10
      const checkIds = orderIds.slice(0, 10)
      
      const results = await Promise.allSettled(
        checkIds.map(id => 
          fetch(`${BACKEND_URL}/api/orders/${id}/last-modified`)
            .then(r => r.json())
            .then(data => ({ id, ...data }))
        )
      )

      const newUpdates = {}
      results.forEach(result => {
        if (result.status === 'fulfilled' && result.value) {
          const { id, last_modified, modified_by } = result.value
          const knownTs = knownTimestamps[id]
          
          if (last_modified && knownTs && last_modified > knownTs) {
            newUpdates[id] = {
              hasUpdate: true,
              modifiedBy: modified_by,
              timestamp: last_modified
            }
          }
        }
      })

      setUpdates(newUpdates)
    } catch (e) {
      // Silent fail
    }
  }, [orderIds, knownTimestamps])

  useEffect(() => {
    checkUpdates()
    const interval = setInterval(checkUpdates, 60000) // Раз на хвилину для dashboard
    return () => clearInterval(interval)
  }, [checkUpdates])

  return { updates, checkUpdates }
}

export default OrderUpdateDot
