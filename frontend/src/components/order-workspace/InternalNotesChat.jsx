/* eslint-disable */
import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import ZoneCard from './ZoneCard'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''

/**
 * InternalNotesChat - Внутрішній месенджер команди
 * Показує нотатки від різних департаментів як чат
 * Користувач визначається автоматично з токена авторизації
 */
export default function InternalNotesChat({
  orderId,
  clientComment = '',  // Окремий коментар клієнта (read-only)
  readOnly = false,
}) {
  const [notes, setNotes] = useState([])
  const [newMessage, setNewMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const [shouldScrollToBottom, setShouldScrollToBottom] = useState(false)
  const chatEndRef = useRef(null)
  const prevNotesCountRef = useRef(0)

  // Завантаження нотаток
  useEffect(() => {
    if (orderId) {
      loadNotes()
    }
  }, [orderId])

  // Автоскрол тільки коли додано НОВЕ повідомлення (не при оновленні)
  useEffect(() => {
    // Скролимо тільки якщо кількість нотаток збільшилась
    if (notes.length > prevNotesCountRef.current && shouldScrollToBottom) {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
      setShouldScrollToBottom(false)
    }
    prevNotesCountRef.current = notes.length
  }, [notes, shouldScrollToBottom])

  const loadNotes = async () => {
    if (!orderId) {
      console.warn('[InternalNotesChat] No orderId provided')
      return
    }
    try {
      setLoading(true)
      const response = await axios.get(`${BACKEND_URL}/api/orders/${orderId}/internal-notes`, {
        headers: { 'Content-Type': 'application/json' }
      })
      if (response.data.success) {
        setNotes(response.data.notes)
      }
    } catch (err) {
      console.error('[InternalNotesChat] Error loading notes:', err)
    } finally {
      setLoading(false)
    }
  }


  const handleSend = async () => {
    if (!newMessage.trim() || sending || !orderId) return

    try {
      setSending(true)
      
      // Отримуємо токен авторизації
      const token = localStorage.getItem('token')
      
      if (!token) {
        alert('Сесія закінчилась. Будь ласка, перелогіньтесь.')
        window.location.href = '/login'
        return
      }
      
      const response = await axios.post(
        `${BACKEND_URL}/api/orders/${orderId}/internal-notes`,
        { message: newMessage.trim() },
        { 
          headers: { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          } 
        }
      )

      if (response.data.success) {
        setShouldScrollToBottom(true)
        setNotes([...notes, response.data.note])
        setNewMessage('')
      }
    } catch (err) {
      if (err.response?.status === 401) {
        alert('Сесія закінчилась. Будь ласка, перелогіньтесь.')
        localStorage.removeItem('token')
        window.location.href = '/login'
      } else {
        console.error('[InternalNotesChat] Error sending note:', err)
        alert('Помилка відправки повідомлення. Спробуйте ще раз.')
      }
    } finally {
      setSending(false)
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // Кольори для різних користувачів
  const getUserColor = (userName) => {
    const colors = [
      'bg-blue-100 border-blue-300',
      'bg-green-100 border-green-300',
      'bg-purple-100 border-purple-300',
      'bg-amber-100 border-amber-300',
      'bg-pink-100 border-pink-300',
      'bg-cyan-100 border-cyan-300',
    ]
    const hash = (userName || '').split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)
    return colors[hash % colors.length]
  }

  return (
    <ZoneCard
      title="💬 Внутрішній чат команди"
      hint="Нотатки видимі всім департаментам"
      tone="neutral"
    >
      {/* Коментар клієнта - окремо, read-only */}
      {clientComment && (
        <div className="mb-4 rounded-lg bg-yellow-50 border border-yellow-200 p-3">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-lg">👤</span>
            <span className="text-xs font-semibold text-yellow-700">Коментар клієнта</span>
          </div>
          <div className="text-sm text-slate-700 whitespace-pre-wrap">{clientComment}</div>
        </div>
      )}

      {/* Чат з нотатками */}
      <div className="bg-slate-50 rounded-lg border border-slate-200 p-3 mb-3 max-h-[300px] overflow-y-auto">
        {loading ? (
          <div className="text-center text-slate-400 py-4">
            <span className="animate-pulse">Завантаження...</span>
          </div>
        ) : notes.length === 0 ? (
          <div className="text-center text-slate-400 py-4">
            <span className="text-2xl mb-2 block">💭</span>
            <span className="text-sm">Поки немає нотаток</span>
          </div>
        ) : (
          <div className="space-y-3">
            {notes.map((note) => (
              <div
                key={note.id}
                className={`rounded-lg border p-3 ${getUserColor(note.user_name)}`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-semibold text-slate-700">
                    👤 {note.user_name}
                  </span>
                  <span className="text-xs text-slate-500">
                    {note.created_at}
                  </span>
                </div>
                <div className="text-sm text-slate-800 whitespace-pre-wrap">
                  {note.message}
                </div>
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>
        )}
      </div>

      {/* Поле введення */}
      {!readOnly && (
        <div className="flex gap-2">
          <textarea
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Нотатка для команди..."
            rows={2}
            className="flex-1 min-w-0 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none resize-none"
          />
          <button
            onClick={handleSend}
            disabled={!newMessage.trim() || sending}
            className="px-3 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-lg text-sm font-medium transition-colors self-end flex-shrink-0"
          >
            {sending ? '...' : '📤'}
          </button>
        </div>
      )}
    </ZoneCard>
  )
}
