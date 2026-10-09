/* eslint-disable */
/**
 * ProductConditionPanel - Панель журналу стану декору
 * Показує історію стану товару та дозволяє додавати нові записи
 */
import React, { useState, useEffect } from 'react'
import { X, Plus, Camera, Calendar, User, FileText, AlertTriangle, Check, Loader2, Trash2 } from 'lucide-react'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''

// Типи дефектів
const DEFECT_TYPES = [
  { code: 'scratch', name: 'Подряпина', icon: '📏', severity: 'low' },
  { code: 'chip', name: 'Скол', icon: '💔', severity: 'medium' },
  { code: 'stain', name: 'Пляма', icon: '🔵', severity: 'low' },
  { code: 'crack', name: 'Тріщина', icon: '⚡', severity: 'high' },
  { code: 'dent', name: 'Вм\'ятина', icon: '🔘', severity: 'medium' },
  { code: 'tear', name: 'Розрив', icon: '🧵', severity: 'high' },
  { code: 'discolor', name: 'Вицвітання', icon: '🌫️', severity: 'low' },
  { code: 'missing_part', name: 'Відсутня деталь', icon: '❓', severity: 'critical' },
  { code: 'other', name: 'Інше', icon: '📝', severity: 'low' },
]

const SEVERITY_LABELS = {
  low: { label: 'Незначний', color: 'bg-green-100 text-green-700' },
  medium: { label: 'Помірний', color: 'bg-amber-100 text-amber-700' },
  high: { label: 'Значний', color: 'bg-orange-100 text-orange-700' },
  critical: { label: 'Критичний', color: 'bg-red-100 text-red-700' },
}

export default function ProductConditionPanel({ 
  product, 
  isOpen, 
  onClose,
  onRecordAdded 
}) {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(false)
  const [showAddForm, setShowAddForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deletingId, setDeletingId] = useState(null) // ID запису, що видаляється
  
  // Форма нового запису
  const [newRecord, setNewRecord] = useState({
    damage_type: '',
    damage_code: '',
    severity: 'low',
    note: '',
    photo_url: '',
  })

  // Завантажити історію
  const loadHistory = async () => {
    if (!product?.product_id && !product?.code) return
    
    setLoading(true)
    try {
      const endpoint = product.product_id 
        ? `/api/product-damage-history/product/${product.product_id}`
        : `/api/product-damage-history/by-sku?sku=${encodeURIComponent(product.code)}`
      
      const response = await fetch(`${BACKEND_URL}${endpoint}`)
      if (response.ok) {
        const data = await response.json()
        setHistory(data.history || [])
      }
    } catch (err) {
      console.error('Error loading history:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (isOpen && product) {
      loadHistory()
    }
  }, [isOpen, product?.product_id, product?.code])

  // Додати новий запис
  const handleAddRecord = async () => {
    if (!newRecord.damage_type) {
      alert('Оберіть тип дефекту')
      return
    }
    
    setSaving(true)
    try {
      const response = await fetch(`${BACKEND_URL}/api/product-damage-history/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          product_id: product.product_id,
          sku: product.code,
          product_name: product.name,
          category: product.category,
          stage: 'inventory', // Переоблік - не пов'язано з замовленням
          damage_type: newRecord.damage_type,
          damage_code: newRecord.damage_code,
          severity: newRecord.severity,
          note: newRecord.note,
          photo_url: newRecord.photo_url,
          created_by: localStorage.getItem('userName') || 'Користувач',
        })
      })
      
      if (response.ok) {
        setShowAddForm(false)
        setNewRecord({ damage_type: '', damage_code: '', severity: 'low', note: '', photo_url: '' })
        loadHistory()
        onRecordAdded?.()
      } else {
        const err = await response.json()
        alert('Помилка: ' + (err.detail || 'Невідома помилка'))
      }
    } catch (err) {
      alert('Помилка збереження: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  // Завантаження фото
  const handlePhotoUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    
    const formData = new FormData()
    formData.append('file', file)
    formData.append('sku', product.code || product.sku || 'unknown')
    formData.append('order_number', '') // Для переобліку - без замовлення
    
    try {
      // Використовуємо правильний endpoint для damage photos
      const response = await fetch(`${BACKEND_URL}/api/product-damage-history/upload-photo`, {
        method: 'POST',
        body: formData
      })
      
      if (response.ok) {
        const data = await response.json()
        setNewRecord(prev => ({ ...prev, photo_url: data.url || data.path }))
      } else {
        const error = await response.json()
        alert(`Помилка: ${error.detail || 'Не вдалося завантажити фото'}`)
      }
    } catch (err) {
      alert('Помилка завантаження фото')
    }
  }

  // Видалення запису про пошкодження
  const handleDeleteRecord = async (recordId) => {
    if (!window.confirm('Видалити цей запис про пошкодження? Цю дію не можна скасувати.')) {
      return
    }
    
    setDeletingId(recordId)
    try {
      const response = await fetch(`${BACKEND_URL}/api/product-damage-history/${recordId}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          deleted_by: localStorage.getItem('userName') || 'Користувач',
          reason: 'Видалено вручну (відремонтовано)'
        })
      })
      
      if (response.ok) {
        // Оновити локальний список
        setHistory(prev => prev.filter(r => r.id !== recordId))
        onRecordAdded?.() // Оновити батьківський компонент
      } else {
        const err = await response.json()
        alert('Помилка видалення: ' + (err.detail || 'Невідома помилка'))
      }
    } catch (err) {
      alert('Помилка видалення: ' + err.message)
    } finally {
      setDeletingId(null)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-y-0 right-0 w-[420px] bg-white shadow-2xl z-50 flex flex-col border-l border-slate-200">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 bg-slate-50">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">📋 Журнал стану</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {product?.name} ({product?.code})
          </p>
        </div>
        <button 
          onClick={onClose}
          className="p-2 hover:bg-slate-200 rounded-lg transition-colors"
        >
          <X className="w-5 h-5 text-slate-600" />
        </button>
      </div>
      
      {/* Content */}
      <div className="flex-1 overflow-y-auto p-5">
        {/* Кнопка додати */}
        {!showAddForm && (
          <button
            onClick={() => setShowAddForm(true)}
            className="w-full mb-4 flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Додати запис про стан
          </button>
        )}
        
        {/* Форма додавання */}
        {showAddForm && (
          <div className="mb-4 p-4 rounded-xl border border-blue-200 bg-blue-50 space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-medium text-blue-800">Новий запис</span>
              <button 
                onClick={() => setShowAddForm(false)}
                className="text-blue-600 hover:text-blue-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            
            {/* Тип дефекту */}
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Тип дефекту *
              </label>
              <div className="grid grid-cols-3 gap-1">
                {DEFECT_TYPES.map(dt => (
                  <button
                    key={dt.code}
                    onClick={() => setNewRecord(prev => ({ 
                      ...prev, 
                      damage_type: dt.name,
                      damage_code: dt.code,
                      severity: dt.severity 
                    }))}
                    className={`
                      px-2 py-1.5 text-xs rounded-lg border transition-colors
                      ${newRecord.damage_code === dt.code 
                        ? 'bg-blue-600 text-white border-blue-600' 
                        : 'bg-white border-slate-200 hover:border-blue-400'}
                    `}
                  >
                    {dt.icon} {dt.name}
                  </button>
                ))}
              </div>
            </div>
            
            {/* Серйозність */}
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Серйозність
              </label>
              <div className="flex gap-1">
                {Object.entries(SEVERITY_LABELS).map(([key, val]) => (
                  <button
                    key={key}
                    onClick={() => setNewRecord(prev => ({ ...prev, severity: key }))}
                    className={`
                      flex-1 px-2 py-1.5 text-xs rounded-lg border transition-colors
                      ${newRecord.severity === key 
                        ? val.color + ' border-current' 
                        : 'bg-white border-slate-200'}
                    `}
                  >
                    {val.label}
                  </button>
                ))}
              </div>
            </div>
            
            {/* Опис */}
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Опис дефекту
              </label>
              <textarea
                value={newRecord.note}
                onChange={(e) => setNewRecord(prev => ({ ...prev, note: e.target.value }))}
                placeholder="Детальний опис..."
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg resize-none"
                rows={2}
              />
            </div>
            
            {/* Фото */}
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Фото (опціонально)
              </label>
              <div className="flex items-center gap-2">
                <label className="flex items-center gap-2 px-3 py-2 bg-white border border-slate-200 rounded-lg cursor-pointer hover:bg-slate-50">
                  <Camera className="w-4 h-4 text-slate-500" />
                  <span className="text-xs">Завантажити</span>
                  <input 
                    type="file" 
                    accept="image/*" 
                    className="hidden" 
                    onChange={handlePhotoUpload}
                  />
                </label>
                {newRecord.photo_url && (
                  <img 
                    src={newRecord.photo_url.startsWith('http') ? newRecord.photo_url : `${BACKEND_URL}/${newRecord.photo_url}`}
                    alt="Preview" 
                    className="w-10 h-10 rounded object-cover"
                  />
                )}
              </div>
            </div>
            
            {/* Кнопки */}
            <div className="flex gap-2 pt-2">
              <button
                onClick={() => setShowAddForm(false)}
                className="flex-1 px-3 py-2 text-sm border border-slate-200 rounded-lg hover:bg-slate-50"
              >
                Скасувати
              </button>
              <button
                onClick={handleAddRecord}
                disabled={saving || !newRecord.damage_type}
                className="flex-1 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                Зберегти
              </button>
            </div>
          </div>
        )}
        
        {/* Історія */}
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-slate-700">
            Історія стану ({history.length})
          </h3>
          
          {loading ? (
            <div className="text-center py-8 text-slate-400">
              <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2" />
              Завантаження...
            </div>
          ) : history.length === 0 ? (
            <div className="text-center py-8 text-slate-400">
              <FileText className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>Записів поки немає</p>
              <p className="text-xs mt-1">Декор у відмінному стані ✨</p>
            </div>
          ) : (
            history.map((record) => (
              <div 
                key={record.id}
                className="p-3 rounded-xl border border-slate-200 bg-white hover:shadow-sm transition-shadow relative group"
              >
                {/* Кнопка видалення */}
                <button
                  onClick={() => handleDeleteRecord(record.id)}
                  disabled={deletingId === record.id}
                  className="absolute top-2 right-2 p-1.5 rounded-lg bg-red-50 text-red-500 opacity-0 group-hover:opacity-100 hover:bg-red-100 transition-all disabled:opacity-50"
                  title="Видалити запис (відремонтовано)"
                >
                  {deletingId === record.id ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Trash2 className="w-4 h-4" />
                  )}
                </button>
                
                <div className="flex items-start justify-between pr-8">
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 text-xs rounded-full ${SEVERITY_LABELS[record.severity]?.color || 'bg-slate-100'}`}>
                      {record.damage_type}
                    </span>
                    {record.order_number && (
                      <span className="text-xs text-slate-500">
                        #{record.order_number}
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-slate-400">
                    {record.stage_label || record.stage}
                  </span>
                </div>
                
                {/* Показати кількість та суму */}
                {(record.qty > 1 || record.fee > 0) && (
                  <div className="mt-2 flex items-center gap-2 text-xs">
                    {record.qty > 1 && (
                      <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-700">
                        {record.qty} шт
                      </span>
                    )}
                    {record.fee > 0 && (
                      <span className="px-2 py-0.5 rounded bg-amber-50 text-amber-700">
                        ₴{record.fee.toLocaleString('uk-UA')}
                        {record.qty > 1 && record.fee_per_item && (
                          <span className="text-amber-500 ml-1">
                            ({record.qty}×₴{record.fee_per_item})
                          </span>
                        )}
                      </span>
                    )}
                  </div>
                )}
                
                {record.note && (
                  <p className="mt-2 text-sm text-slate-600">{record.note}</p>
                )}
                
                {record.photo_url && (
                  <img 
                    src={record.photo_url.startsWith('http') ? record.photo_url : `${BACKEND_URL}${record.photo_url.startsWith('/') ? '' : '/'}${record.photo_url}`}
                    alt="Фото пошкодження" 
                    className="mt-2 w-full h-32 object-cover rounded-lg cursor-pointer"
                    onClick={() => window.open(record.photo_url.startsWith('http') ? record.photo_url : `${BACKEND_URL}${record.photo_url.startsWith('/') ? '' : '/'}${record.photo_url}`, '_blank')}
                  />
                )}
                
                <div className="mt-2 flex items-center gap-3 text-xs text-slate-400">
                  <span className="flex items-center gap-1">
                    <Calendar className="w-3 h-3" />
                    {new Date(record.created_at).toLocaleDateString('uk-UA')}
                  </span>
                  {record.created_by && (
                    <span className="flex items-center gap-1">
                      <User className="w-3 h-3" />
                      {record.created_by}
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
