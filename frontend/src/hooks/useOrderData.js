/* eslint-disable */
/**
 * useOrderData - Уніфікований хук для завантаження даних замовлення
 * Підтримує як OC- так і IT- замовлення
 */

import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''

export function useOrderData(orderId, options = {}) {
  const {
    loadIssueCard = false,
    loadItems = true,
    loadDocuments = false,
    onError
  } = options
  
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [order, setOrder] = useState(null)
  const [items, setItems] = useState([])
  const [issueCard, setIssueCard] = useState(null)
  const [documents, setDocuments] = useState([])
  
  // Визначити тип замовлення
  const orderSource = order?.order_number?.startsWith('IT-') 
    ? 'event_tool' 
    : order?.order_number?.startsWith('OC-') 
      ? 'opencart' 
      : 'manual'
  
  const isEventToolOrder = orderSource === 'event_tool'
  
  // Завантажити замовлення
  const fetchOrder = useCallback(async () => {
    if (!orderId) return
    
    setLoading(true)
    setError(null)
    
    try {
      const response = await axios.get(`${BACKEND_URL}/api/orders/${orderId}`)
      const orderData = response.data
      setOrder(orderData)
      
      // Якщо є items в замовленні
      if (loadItems && orderData.items) {
        setItems(orderData.items)
      } else if (loadItems) {
        // Завантажити окремо
        const itemsRes = await axios.get(`${BACKEND_URL}/api/orders/${orderId}/items`)
        setItems(itemsRes.data || [])
      }
      
      // Завантажити issue card якщо потрібно
      if (loadIssueCard && orderData.issue_card_id) {
        try {
          const icRes = await axios.get(`${BACKEND_URL}/api/orders/${orderId}/issue-card`)
          setIssueCard(icRes.data)
        } catch (e) {
          console.warn('Issue card not found')
        }
      }
      
      // Завантажити документи
      if (loadDocuments) {
        try {
          const docsRes = await axios.get(`${BACKEND_URL}/api/orders/${orderId}/documents`)
          setDocuments(docsRes.data || [])
        } catch (e) {
          console.warn('Documents not found')
        }
      }
      
    } catch (err) {
      console.error('Error loading order:', err)
      setError(err.response?.data?.detail || 'Помилка завантаження замовлення')
      onError?.(err)
    } finally {
      setLoading(false)
    }
  }, [orderId, loadIssueCard, loadItems, loadDocuments, onError])
  
  // Оновити замовлення
  const updateOrder = useCallback(async (updates) => {
    if (!orderId) return
    
    try {
      const response = await axios.patch(`${BACKEND_URL}/api/orders/${orderId}`, updates)
      setOrder(prev => ({ ...prev, ...response.data }))
      return response.data
    } catch (err) {
      console.error('Error updating order:', err)
      throw err
    }
  }, [orderId])
  
  // Оновити item
  const updateItem = useCallback(async (itemId, updates) => {
    if (!orderId) return
    
    try {
      const response = await axios.patch(`${BACKEND_URL}/api/orders/${orderId}/items/${itemId}`, updates)
      setItems(prev => prev.map(item => 
        item.id === itemId ? { ...item, ...response.data } : item
      ))
      return response.data
    } catch (err) {
      console.error('Error updating item:', err)
      throw err
    }
  }, [orderId])
  
  // Додати item
  const addItem = useCallback(async (itemData) => {
    if (!orderId) return
    
    try {
      const response = await axios.post(`${BACKEND_URL}/api/orders/${orderId}/items`, itemData)
      setItems(prev => [...prev, response.data])
      return response.data
    } catch (err) {
      console.error('Error adding item:', err)
      throw err
    }
  }, [orderId])
  
  // Видалити item
  const removeItem = useCallback(async (itemId) => {
    if (!orderId) return
    
    try {
      await axios.delete(`${BACKEND_URL}/api/orders/${orderId}/items/${itemId}`)
      setItems(prev => prev.filter(item => item.id !== itemId))
    } catch (err) {
      console.error('Error removing item:', err)
      throw err
    }
  }, [orderId])
  
  // Перезавантажити
  const refresh = useCallback(() => {
    fetchOrder()
  }, [fetchOrder])
  
  useEffect(() => {
    fetchOrder()
  }, [fetchOrder])
  
  return {
    // State
    loading,
    error,
    order,
    items,
    issueCard,
    documents,
    
    // Computed
    orderSource,
    isEventToolOrder,
    
    // Actions
    setOrder,
    setItems,
    updateOrder,
    updateItem,
    addItem,
    removeItem,
    refresh
  }
}

/**
 * Парсинг notes з Ivent-tool замовлення
 * Notes містять структуровану інформацію
 */
export function parseEventToolNotes(notes) {
  if (!notes) return {}
  
  const parsed = {
    source: null,
    deliveryType: null,
    deliveryAddress: null,
    eventName: null,
    eventType: null,
    guestsCount: null,
    setupRequired: false,
    setupNotes: null,
    payerCompany: null,
    payerEdrpou: null,
    customerComment: null
  }
  
  const lines = notes.split('\n')
  
  for (const line of lines) {
    if (line.includes('[Джерело: Ivent-tool]')) {
      parsed.source = 'event_tool'
    } else if (line.startsWith('Доставка:')) {
      parsed.deliveryType = line.replace('Доставка:', '').trim()
    } else if (line.startsWith('Адреса:')) {
      parsed.deliveryAddress = line.replace('Адреса:', '').trim()
    } else if (line.startsWith('Місто:')) {
      parsed.deliveryAddress = line.replace('Місто:', '').trim()
    } else if (line.startsWith('Назва події:')) {
      parsed.eventName = line.replace('Назва події:', '').trim()
    } else if (line.startsWith('Тип події:')) {
      parsed.eventType = line.replace('Тип події:', '').trim()
    } else if (line.startsWith('Кількість гостей:')) {
      parsed.guestsCount = parseInt(line.replace('Кількість гостей:', '').trim())
    } else if (line.startsWith('Потрібен монтаж: Так')) {
      parsed.setupRequired = true
    } else if (line.startsWith('Деталі монтажу:')) {
      parsed.setupNotes = line.replace('Деталі монтажу:', '').trim()
    } else if (line.startsWith('Платник:')) {
      parsed.payerCompany = line.replace('Платник:', '').trim()
    } else if (line.startsWith('ЄДРПОУ:')) {
      parsed.payerEdrpou = line.replace('ЄДРПОУ:', '').trim()
    } else if (line.startsWith('Коментар клієнта:')) {
      parsed.customerComment = line.replace('Коментар клієнта:', '').trim()
    }
  }
  
  return parsed
}

export default useOrderData
