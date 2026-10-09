/* eslint-disable */
import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import TonePill from './TonePill'
import { getStatusConfig } from './statusConfig'
import { Info, ChevronDown, ChevronUp, Volume2, VolumeX } from 'lucide-react'
import { isSoundEnabled, toggleSound, playNotificationSound } from '../../utils/notificationSound'

/**
 * WorkspaceHeader - Компактний sticky хедер з collapse функціоналом
 * Mobile: 1 рядок (назва + чіп), деталі в expandable блок
 * Desktop: повна версія
 */
export default function WorkspaceHeader({
  orderId,
  orderNumber,
  status,
  issueDate,
  returnDate,
  createdAt,
  title,
  backUrl = '/manager',
  // Progress info
  progressInfo, // { label, value, percent }
  // Real-time sync
  activeUsers = [],    // Список активних користувачів
  hasUpdates = false,  // Є непрочитані оновлення
  onRefresh,           // Callback для оновлення
}) {
  const navigate = useNavigate()
  const config = getStatusConfig(status)
  const [expanded, setExpanded] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const [soundOn, setSoundOn] = useState(isSoundEnabled())
  
  // Перемикач звуку
  const handleToggleSound = () => {
    const newState = !soundOn
    setSoundOn(newState)
    toggleSound(newState)
    // Демо-звук при увімкненні
    if (newState) {
      playNotificationSound('update')
    }
  }
  
  // Відстеження скролу для компактного хедера
  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20)
    }
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])
  
  const formatDate = (dateStr) => {
    if (!dateStr) return '—'
    const date = new Date(dateStr)
    return date.toLocaleDateString('uk-UA', { day: 'numeric', month: 'short' })
  }
  
  const calculateDays = () => {
    if (!issueDate || !returnDate) return null
    const start = new Date(issueDate)
    const end = new Date(returnDate)
    const days = Math.ceil((end - start) / (1000 * 60 * 60 * 24))
    return days > 0 ? days : 1
  }
  
  const rentalDays = calculateDays()
  
  // Отримати поточного користувача для фільтрації
  const currentUser = (() => {
    try {
      const userData = localStorage.getItem('user')
      return userData ? JSON.parse(userData) : {}
    } catch { return {} }
  })()
  const otherUsers = activeUsers.filter(u => u.user_id !== (currentUser.id || currentUser.user_id))
  
  return (
    <div className={`
      bg-white border-b border-slate-200 sticky top-0 z-30 transition-all duration-200
      ${scrolled ? 'shadow-md' : ''}
    `}>
      <div className="mx-auto max-w-7xl px-3 sm:px-6">
        {/* Mobile: компактний 1-рядковий хедер */}
        <div className="flex items-center justify-between py-2 sm:py-3 gap-2">
          {/* Назад */}
          <button 
            onClick={() => navigate(backUrl)}
            className="flex-shrink-0 p-1.5 -ml-1.5 rounded-lg text-slate-600 hover:bg-slate-100 active:bg-slate-200"
          >
            <span className="text-lg">←</span>
          </button>
          
          {/* Центр: Назва + статус */}
          <div className="flex-1 flex items-center justify-center gap-2 min-w-0">
            <h1 className={`font-bold text-slate-900 truncate transition-all ${scrolled ? 'text-sm' : 'text-base sm:text-xl'}`}>
              {title || `#${orderNumber || orderId}`}
            </h1>
            {/* Badge для Ivent-tool замовлень */}
            {orderNumber?.startsWith('IT-') && (
              <span className="px-1.5 py-0.5 text-[10px] font-medium bg-purple-100 text-purple-700 rounded">
                Ivent-tool
              </span>
            )}
            <TonePill tone={config.tone} icon={config.icon} compact>
              {scrolled ? '' : config.title}
            </TonePill>
          </div>
          
          {/* Info кнопка для розкриття деталей (mobile) */}
          <button 
            onClick={() => setExpanded(!expanded)}
            className="flex-shrink-0 p-1.5 -mr-1.5 rounded-lg text-slate-500 hover:bg-slate-100 active:bg-slate-200 sm:hidden"
          >
            {expanded ? <ChevronUp className="w-5 h-5" /> : <Info className="w-5 h-5" />}
          </button>
          
          {/* Desktop: показуємо дати inline */}
          <div className="hidden sm:flex items-center gap-2">
            {/* Активні користувачі */}
            {otherUsers.length > 0 && (
              <div className="flex items-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 px-2.5 py-1.5 text-xs">
                <div className="flex -space-x-1.5">
                  {otherUsers.slice(0, 3).map((user) => (
                    <div 
                      key={user.user_id}
                      className="w-5 h-5 rounded-full bg-blue-500 border-2 border-white flex items-center justify-center text-[10px] text-white font-medium"
                      title={user.user_name}
                    >
                      {user.user_name?.charAt(0)?.toUpperCase() || '?'}
                    </div>
                  ))}
                  {otherUsers.length > 3 && (
                    <div className="w-5 h-5 rounded-full bg-slate-400 border-2 border-white flex items-center justify-center text-[10px] text-white">
                      +{otherUsers.length - 3}
                    </div>
                  )}
                </div>
                <span className="text-blue-700">Також тут</span>
              </div>
            )}
            
            {/* Індикатор оновлень */}
            {hasUpdates && (
              <button
                onClick={onRefresh}
                className="flex items-center gap-1.5 rounded-lg border border-amber-300 bg-amber-50 px-2.5 py-1.5 text-xs text-amber-700 hover:bg-amber-100 active:bg-amber-200 transition-colors"
              >
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
                </span>
                Оновити
              </button>
            )}
            
            {/* Кнопка звуку */}
            <button
              onClick={handleToggleSound}
              className={`p-1.5 rounded-lg transition-colors ${
                soundOn 
                  ? 'text-blue-600 hover:bg-blue-50' 
                  : 'text-slate-400 hover:bg-slate-100'
              }`}
              title={soundOn ? 'Вимкнути звук' : 'Увімкнути звук'}
            >
              {soundOn ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
            </button>
            
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs">
              <span className="text-slate-500">Дати: </span>
              <span className="font-medium text-slate-800">
                {formatDate(issueDate)} — {formatDate(returnDate)}
                {rentalDays && <span className="text-slate-500"> • {rentalDays}д</span>}
              </span>
            </div>
            {progressInfo && (
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs">
                <span className="font-medium text-slate-800">{progressInfo.label}</span>
              </div>
            )}
          </div>
        </div>
        
        {/* Expandable details (mobile) */}
        <div className={`
          overflow-hidden transition-all duration-200 sm:hidden
          ${expanded ? 'max-h-40 pb-3' : 'max-h-0'}
        `}>
          <div className="space-y-2 pt-1">
            {/* Дати */}
            <div className="flex items-center gap-2 text-xs">
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 flex-1">
                <span className="text-slate-500">📅 </span>
                <span className="font-medium">{formatDate(issueDate)} — {formatDate(returnDate)}</span>
                {rentalDays && <span className="text-slate-400"> • {rentalDays}д</span>}
              </div>
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5">
                <span className="font-medium">{config.mode}</span>
              </div>
            </div>
            
            {/* Progress info */}
            {progressInfo && (
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-2.5 py-2">
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-emerald-700 font-medium">📦 Прогрес збору</span>
                  <span className="font-bold text-emerald-800">{progressInfo.label}</span>
                </div>
                {progressInfo.percent !== undefined && (
                  <div className="h-1.5 bg-emerald-200 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-emerald-500 rounded-full transition-all duration-300"
                      style={{ width: `${progressInfo.percent}%` }}
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
