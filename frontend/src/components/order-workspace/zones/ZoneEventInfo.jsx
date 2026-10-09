/* eslint-disable */
/**
 * ZoneEventInfo - Інформація про подію (для Ivent-tool замовлень)
 * Показується тільки для IT- замовлень
 */

import React from 'react'
import { parseEventToolNotes } from '../../../hooks/useOrderData'

const EVENT_TYPE_LABELS = {
  wedding: 'Весілля',
  corporate: 'Корпоратив',
  birthday: 'День народження',
  baby_shower: 'Baby Shower',
  graduation: 'Випускний',
  anniversary: 'Річниця',
  photoshoot: 'Фотосесія',
  other: 'Інше'
}

export default function ZoneEventInfo({ order }) {
  // Перевіряємо чи це IT- замовлення
  if (!order?.order_number?.startsWith('IT-')) {
    return null
  }
  
  // Парсимо notes
  const eventData = parseEventToolNotes(order.notes)
  
  // Якщо немає даних про подію
  if (!eventData.source && !order.event_date && !order.event_location) {
    return null
  }
  
  return (
    <div className="bg-purple-50 border border-purple-200 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-lg">🎪</span>
        <h3 className="font-semibold text-purple-900">Інформація про подію</h3>
        <span className="px-2 py-0.5 text-xs bg-purple-200 text-purple-800 rounded-full">
          Ivent-tool
        </span>
      </div>
      
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
        {/* Назва події */}
        {eventData.eventName && (
          <div className="col-span-full">
            <span className="text-purple-600">Назва: </span>
            <span className="font-medium text-purple-900">{eventData.eventName}</span>
          </div>
        )}
        
        {/* Тип події */}
        {eventData.eventType && (
          <div>
            <span className="text-purple-600">Тип: </span>
            <span className="font-medium text-purple-900">
              {EVENT_TYPE_LABELS[eventData.eventType] || eventData.eventType}
            </span>
          </div>
        )}
        
        {/* Дата події */}
        {order.event_date && (
          <div>
            <span className="text-purple-600">Дата події: </span>
            <span className="font-medium text-purple-900">
              {new Date(order.event_date).toLocaleDateString('uk-UA')}
              {order.event_time && ` о ${order.event_time}`}
            </span>
          </div>
        )}
        
        {/* Місце проведення */}
        {order.event_location && (
          <div className="col-span-full">
            <span className="text-purple-600">Місце: </span>
            <span className="font-medium text-purple-900">{order.event_location}</span>
          </div>
        )}
        
        {/* Кількість гостей */}
        {eventData.guestsCount && (
          <div>
            <span className="text-purple-600">Гостей: </span>
            <span className="font-medium text-purple-900">{eventData.guestsCount}</span>
          </div>
        )}
        
        {/* Доставка */}
        {eventData.deliveryType && (
          <div>
            <span className="text-purple-600">Доставка: </span>
            <span className="font-medium text-purple-900">{eventData.deliveryType}</span>
          </div>
        )}
        
        {/* Адреса доставки */}
        {eventData.deliveryAddress && (
          <div className="col-span-full">
            <span className="text-purple-600">Адреса: </span>
            <span className="font-medium text-purple-900">{eventData.deliveryAddress}</span>
          </div>
        )}
        
        {/* Монтаж */}
        {eventData.setupRequired && (
          <div className="col-span-full bg-amber-100 rounded-lg p-2 border border-amber-200">
            <span className="text-amber-700 font-medium">⚠️ Потрібен монтаж</span>
            {eventData.setupNotes && (
              <p className="text-amber-800 text-xs mt-1">{eventData.setupNotes}</p>
            )}
          </div>
        )}
        
        {/* Платник (юр. особа) */}
        {eventData.payerCompany && (
          <div className="col-span-full">
            <span className="text-purple-600">Платник: </span>
            <span className="font-medium text-purple-900">
              {eventData.payerCompany}
              {eventData.payerEdrpou && ` (ЄДРПОУ: ${eventData.payerEdrpou})`}
            </span>
          </div>
        )}
        
        {/* Коментар клієнта */}
        {eventData.customerComment && (
          <div className="col-span-full bg-white rounded-lg p-3 border border-purple-200">
            <div className="text-xs text-purple-600 mb-1">💬 Коментар клієнта:</div>
            <p className="text-purple-900">{eventData.customerComment}</p>
          </div>
        )}
      </div>
    </div>
  )
}
