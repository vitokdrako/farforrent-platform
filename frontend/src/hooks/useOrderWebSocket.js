/* eslint-disable */
/**
 * useOrderWebSocket - Real-time WebSocket синхронізація замовлення
 * 
 * Функціонал:
 * - Підключення до WebSocket при відкритті замовлення
 * - Отримання сповіщень про зміни від інших користувачів
 * - Показ активних користувачів в замовленні
 * - Індикатор "хтось друкує"
 * - Звукові сповіщення
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { playIfEnabled } from '../utils/notificationSound'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''

// Конвертувати HTTP URL в WebSocket URL
function getWebSocketUrl(baseUrl) {
  if (!baseUrl) return null
  return baseUrl.replace(/^http/, 'ws').replace(/^https/, 'wss')
}

/**
 * Хук для WebSocket підключення до замовлення
 * @param {number|string} orderId - ID замовлення
 * @param {object} options - Опції
 * @param {boolean} options.enabled - Чи включено синхронізацію
 * @param {function} options.onSectionUpdate - Callback при оновленні секції
 * @param {function} options.onUserJoined - Callback при підключенні користувача
 * @param {function} options.onUserLeft - Callback при відключенні користувача
 * @param {function} options.onCommentAdded - Callback при новому коментарі
 */
export function useOrderWebSocket(orderId, options = {}) {
  const {
    enabled = true,
    onSectionUpdate,
    onUserJoined,
    onUserLeft,
    onCommentAdded,
  } = options

  // Стан
  const [connected, setConnected] = useState(false)
  const [activeUsers, setActiveUsers] = useState([])
  const [typingUsers, setTypingUsers] = useState([])
  const [pendingUpdates, setPendingUpdates] = useState({}) // { section: { version, updatedBy, changedFields } }
  const [connectionError, setConnectionError] = useState(null)

  // Refs
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const pingIntervalRef = useRef(null)
  const typingTimeoutRef = useRef({})

  // Отримати дані користувача
  const getUser = useCallback(() => {
    try {
      const userData = localStorage.getItem('user')
      if (userData) {
        const user = JSON.parse(userData)
        return {
          id: user.id || user.user_id || 0,
          name: user.name || user.username || user.firstname || 'Анонім',
          role: user.role || 'manager'
        }
      }
    } catch (e) {}
    return { id: 0, name: 'Анонім', role: 'manager' }
  }, [])

  // Підключитися до WebSocket
  const connect = useCallback(() => {
    if (!orderId || !enabled) return

    const wsBaseUrl = getWebSocketUrl(BACKEND_URL)
    if (!wsBaseUrl) {
      console.warn('[WS] No WebSocket URL available')
      return
    }

    const user = getUser()
    const wsUrl = `${wsBaseUrl}/api/orders/${orderId}/ws?user_id=${user.id}&user_name=${encodeURIComponent(user.name)}&role=${user.role}`

    console.log('[WS] Connecting to:', wsUrl)

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('[WS] Connected to order', orderId)
        setConnected(true)
        setConnectionError(null)

        // Ping кожні 30 секунд
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }))
          }
        }, 30000)
      }

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          handleMessage(message)
        } catch (e) {
          console.warn('[WS] Invalid message:', event.data)
        }
      }

      ws.onclose = (event) => {
        console.log('[WS] Disconnected:', event.code, event.reason)
        setConnected(false)
        cleanup()

        // Автоматичне перепідключення (тільки якщо не закрили навмисно)
        if (enabled && event.code !== 1000) {
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log('[WS] Reconnecting...')
            connect()
          }, 3000)
        }
      }

      ws.onerror = (error) => {
        console.error('[WS] Error:', error)
        setConnectionError('WebSocket connection error')
      }

    } catch (error) {
      console.error('[WS] Failed to create WebSocket:', error)
      setConnectionError(error.message)
    }
  }, [orderId, enabled, getUser])

  // Обробка повідомлень
  const handleMessage = useCallback((message) => {
    const { type } = message

    switch (type) {
      case 'sync.connected':
        // Початкове підключення - отримали список користувачів
        setActiveUsers(message.users || [])
        break

      case 'user.joined':
        setActiveUsers(message.users || [])
        playIfEnabled('join')  // 🔊 Звук приєднання
        onUserJoined?.(message)
        break

      case 'user.left':
        setActiveUsers(message.users || [])
        onUserLeft?.(message)
        break

      case 'user.typing':
        // Хтось друкує - показати на 3 секунди
        setTypingUsers(prev => {
          const newList = prev.filter(u => u.user_id !== message.user_id)
          newList.push({ user_id: message.user_id, user_name: message.user_name })
          return newList
        })
        
        // Прибрати через 3 секунди
        if (typingTimeoutRef.current[message.user_id]) {
          clearTimeout(typingTimeoutRef.current[message.user_id])
        }
        typingTimeoutRef.current[message.user_id] = setTimeout(() => {
          setTypingUsers(prev => prev.filter(u => u.user_id !== message.user_id))
        }, 3000)
        break

      case 'order.section.updated':
        // Секція оновлена іншим користувачем
        setPendingUpdates(prev => ({
          ...prev,
          [message.section]: {
            version: message.version,
            updatedBy: message.updated_by_name,
            updatedById: message.updated_by_id,
            changedFields: message.changed_fields || [],
            changesSummary: message.changes_summary || '',
            timestamp: message.timestamp
          }
        }))
        playIfEnabled('update')  // 🔊 Звук оновлення
        onSectionUpdate?.(message)
        break

      case 'order.comment.added':
        playIfEnabled('update')  // 🔊 Звук нового коментаря
        onCommentAdded?.(message)
        break

      case 'pong':
        // Відповідь на ping - все ок
        break

      default:
        console.log('[WS] Unknown message type:', type, message)
    }
  }, [onSectionUpdate, onUserJoined, onUserLeft, onCommentAdded])

  // Відправити повідомлення про друкування
  const sendTyping = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'typing' }))
    }
  }, [])

  // Підтвердити що бачимо оновлення (dismiss)
  const dismissSectionUpdate = useCallback((section) => {
    setPendingUpdates(prev => {
      const newState = { ...prev }
      delete newState[section]
      return newState
    })
  }, [])

  // Підтвердити всі оновлення
  const dismissAllUpdates = useCallback(() => {
    setPendingUpdates({})
  }, [])

  // Cleanup
  const cleanup = useCallback(() => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current)
      pingIntervalRef.current = null
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    Object.values(typingTimeoutRef.current).forEach(t => clearTimeout(t))
    typingTimeoutRef.current = {}
  }, [])

  // Disconnect
  const disconnect = useCallback(() => {
    cleanup()
    if (wsRef.current) {
      wsRef.current.close(1000, 'User left')
      wsRef.current = null
    }
    setConnected(false)
    setActiveUsers([])
    setTypingUsers([])
    setPendingUpdates({})
  }, [cleanup])

  // Effect: Connect/Disconnect
  useEffect(() => {
    if (enabled && orderId) {
      connect()
    } else {
      disconnect()
    }

    return () => {
      disconnect()
    }
  }, [orderId, enabled])

  // Перевірка чи є непрочитані оновлення
  const hasUpdates = Object.keys(pendingUpdates).length > 0

  return {
    // Стан підключення
    connected,
    connectionError,
    
    // Активні користувачі
    activeUsers,
    typingUsers,
    
    // Оновлення
    pendingUpdates,
    hasUpdates,
    
    // Методи
    sendTyping,
    dismissSectionUpdate,
    dismissAllUpdates,
    disconnect,
    reconnect: connect,
  }
}

/**
 * Хук для повідомлення сервера про збережені зміни
 * (викликати після успішного збереження)
 */
export function useOrderSectionUpdate() {
  const updateSection = useCallback(async (orderId, section, options = {}) => {
    const {
      clientVersion = 0,
      changesSummary = '',
      changedFields = [],
    } = options

    try {
      const user = JSON.parse(localStorage.getItem('user') || '{}')
      const userId = user.id || user.user_id || 0
      const userName = user.name || user.username || 'Анонім'

      const params = new URLSearchParams({
        client_version: clientVersion,
        user_id: userId,
        user_name: userName,
        changes_summary: changesSummary,
        changed_fields: changedFields.join(','),
      })

      const response = await fetch(
        `${BACKEND_URL}/api/orders/${orderId}/sections/${section}/update?${params}`,
        { method: 'POST' }
      )

      const result = await response.json()

      if (result.conflict) {
        // Конфлікт версій!
        playIfEnabled('conflict')  // 🔊 Звук конфлікту
        return {
          success: false,
          conflict: true,
          serverVersion: result.server_version,
          message: result.message
        }
      }

      return {
        success: true,
        newVersion: result.new_version,
        conflict: false
      }

    } catch (error) {
      console.error('[updateSection] Error:', error)
      return {
        success: false,
        error: error.message
      }
    }
  }, [])

  return { updateSection }
}

/**
 * Компонент для відображення індикатора оновлень
 */
export function UpdateIndicator({ 
  pendingUpdates, 
  onRefresh, 
  onDismiss,
  className = ''
}) {
  if (!pendingUpdates || Object.keys(pendingUpdates).length === 0) {
    return null
  }

  const sections = Object.keys(pendingUpdates)
  const latestUpdate = Object.values(pendingUpdates).sort(
    (a, b) => new Date(b.timestamp) - new Date(a.timestamp)
  )[0]

  return (
    <div className={`flex items-center gap-2 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 ${className}`}>
      <span className="relative flex h-3 w-3">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
        <span className="relative inline-flex rounded-full h-3 w-3 bg-amber-500"></span>
      </span>
      <span className="text-sm text-amber-800">
        {latestUpdate?.updatedBy || 'Хтось'} оновив {sections.length > 1 ? 'дані' : sections[0]}
      </span>
      {onRefresh && (
        <button 
          onClick={onRefresh}
          className="text-xs text-amber-700 underline hover:text-amber-900"
        >
          Оновити
        </button>
      )}
      {onDismiss && (
        <button 
          onClick={onDismiss}
          className="text-xs text-amber-500 hover:text-amber-700 ml-1"
        >
          ✕
        </button>
      )}
    </div>
  )
}

/**
 * Компонент для відображення активних користувачів
 */
export function ActiveUsersIndicator({ users, typingUsers = [] }) {
  if (!users || users.length <= 1) {
    return null
  }

  // Показати інших користувачів (без себе)
  const currentUser = JSON.parse(localStorage.getItem('user') || '{}')
  const otherUsers = users.filter(u => u.user_id !== (currentUser.id || currentUser.user_id))

  if (otherUsers.length === 0) {
    return null
  }

  return (
    <div className="flex items-center gap-2 text-sm text-slate-600">
      <div className="flex -space-x-2">
        {otherUsers.slice(0, 3).map((user, i) => (
          <div 
            key={user.user_id} 
            className="w-6 h-6 rounded-full bg-blue-500 border-2 border-white flex items-center justify-center text-xs text-white font-medium"
            title={user.user_name}
          >
            {user.user_name?.charAt(0)?.toUpperCase() || '?'}
          </div>
        ))}
        {otherUsers.length > 3 && (
          <div className="w-6 h-6 rounded-full bg-slate-400 border-2 border-white flex items-center justify-center text-xs text-white font-medium">
            +{otherUsers.length - 3}
          </div>
        )}
      </div>
      <span>
        {typingUsers.length > 0 ? (
          <span className="text-amber-600">
            {typingUsers[0].user_name} друкує...
          </span>
        ) : (
          <span>Також працюють</span>
        )}
      </span>
    </div>
  )
}

export default useOrderWebSocket
