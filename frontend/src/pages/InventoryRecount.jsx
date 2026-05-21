/* eslint-disable */
import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'
import { getImageUrl } from '../utils/imageHelper'
import DamageModal from '../components/DamageModal'
import ImageUpload from '../components/ImageUpload'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''

export default function InventoryRecount() {
  const { sku } = useParams()
  const navigate = useNavigate()
  const [product, setProduct] = useState(null)
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState('available') // available, damaged, missing
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [familyProducts, setFamilyProducts] = useState([]) // Товари з набору
  const [damageHistory, setDamageHistory] = useState([]) // Історія пошкоджень
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [damageModalOpen, setDamageModalOpen] = useState(false) // Для відкриття DamageModal
  const [processingQty, setProcessingQty] = useState(1) // Кількість для обробки
  const [sendingToProcessing, setSendingToProcessing] = useState(false)

  useEffect(() => {
    loadProduct()
    loadDamageHistory()
  }, [sku])
  
  const loadDamageHistory = async () => {
    if (!sku) return
    
    try {
      setLoadingHistory(true)
      const res = await axios.get(`${BACKEND_URL}/api/product-damage-history/by-sku?sku=${encodeURIComponent(sku)}`)
      setDamageHistory(res.data.history || [])
    } catch (err) {
      console.error('Error loading damage history:', err)
      setDamageHistory([])
    } finally {
      setLoadingHistory(false)
    }
  }

  const loadProduct = async () => {
    try {
      setLoading(true)
      const res = await axios.get(`${BACKEND_URL}/api/products/${sku}`)
      setProduct(res.data)
      
      // Якщо товар входить у набір, завантажити інші товари з набору
      if (res.data.family_id) {
        try {
          const familyRes = await axios.get(`${BACKEND_URL}/api/catalog/families/${res.data.family_id}/products`)
          setFamilyProducts(familyRes.data.filter(p => p.sku !== sku)) // Виключити поточний товар
        } catch (familyErr) {
          console.error('Error loading family products:', familyErr)
        }
      }
    } catch (err) {
      console.error('Error loading product:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async () => {
    // Якщо статус "пошкоджено", спочатку відкрити DamageModal
    if (status === 'damaged') {
      setDamageModalOpen(true)
      return
    }
    
    // Інакше зберегти дані переобліку
    await saveRecount()
  }
  
  const saveRecount = async () => {
    try {
      setSaving(true)
      
      // Зберегти дані переобліку
      await axios.post(`${BACKEND_URL}/api/inventory/recount`, {
        sku: sku,
        product_id: product?.product_id,
        status: status,
        notes: notes,
        timestamp: new Date().toISOString()
      })

      alert('✅ Переобік успішно збережено!')
      navigate('/')
    } catch (err) {
      console.error('Error saving recount:', err)
      alert('❌ Помилка збереження')
    } finally {
      setSaving(false)
    }
  }
  
  const handleDamageSaved = async (damageRecord) => {
    // DamageModal вже зберіг пошкодження, тепер зберігаємо переобік
    setDamageModalOpen(false)
    await loadDamageHistory() // Оновити історію
    await saveRecount()
  }
  
  // Швидка дія - відправити на обробку
  const handleQuickAction = async (actionType) => {
    const qty = product.quantity > 1 ? processingQty : 1
    const actionLabels = {
      wash: 'мийку',
      repair: 'реставрацію', 
      laundry: 'хімчистку',
      write_off: 'списання'
    }
    
    const confirmMsg = actionType === 'write_off' 
      ? `Списати ${qty} шт?\n\nЦю дію НЕ можна скасувати!`
      : `Відправити ${qty} шт на ${actionLabels[actionType]}?\n\nТовар буде заморожено до завершення обробки.`
    
    if (!window.confirm(confirmMsg)) {
      return
    }
    
    try {
      setSendingToProcessing(true)
      
      // Відправляємо на обробку через API
      await axios.post(`${BACKEND_URL}/api/inventory/send-to-processing`, {
        product_id: product.product_id,
        sku: product.sku,
        quantity: qty,
        action_type: actionType,
        notes: notes || `Відправлено з кабінету переобліку`,
        source: 'reaudit'
      })
      
      const successMsg = actionType === 'write_off'
        ? `✅ ${qty} шт списано!`
        : `✅ ${qty} шт відправлено на ${actionLabels[actionType]}!`
      alert(successMsg)
      
      // Оновити дані товару
      await loadProduct()
      setProcessingQty(1)
      
    } catch (err) {
      console.error('Error sending to processing:', err)
      const errorMsg = err.response?.data?.detail || err.message || 'Невідома помилка'
      alert(`❌ Помилка: ${errorMsg}`)
    } finally {
      setSendingToProcessing(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-corp-text-main">Завантаження...</div>
      </div>
    )
  }

  if (!product) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-2xl border border-slate-200 p-6 text-center">
          <div className="text-6xl mb-4">📦</div>
          <h2 className="text-xl font-semibold mb-2">Товар не знайдено</h2>
          <p className="text-corp-text-main mb-4">SKU: {sku}</p>
          <button 
            onClick={() => (window.history.length > 1 ? navigate(-1) : navigate('/'))}
            className="px-4 py-2 bg-slate-800 text-white rounded-lg hover:bg-slate-700"
          >
            Повернутися
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50 p-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 mb-4">
          <div className="flex items-center gap-4 mb-4">
            <div className="text-5xl">📋</div>
            <div className="flex-1">
              <h1 className="text-2xl font-bold text-corp-text-dark">Кабінет переобліку</h1>
              <p className="text-corp-text-main">Швидка фіксація стану товару</p>
            </div>
          </div>
        </div>

        {/* Family Group Info (якщо є) */}
        {product.family_id && (
          <div className="bg-blue-50 border border-blue-200 rounded-2xl p-6 mb-4">
            <h2 className="text-lg font-semibold mb-3 text-blue-900">🔗 Товар входить у набір</h2>
            <div className="text-sm text-blue-800 mb-3">
              <strong>Назва набору:</strong> {product.family?.name || 'Не вказано'}
            </div>
            {product.family?.description && (
              <div className="text-sm text-blue-700 mb-3">
                {product.family.description}
              </div>
            )}
            
            {familyProducts.length > 0 && (
              <>
                <div className="text-sm font-medium text-blue-900 mb-2">
                  Інші товари з набору:
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {familyProducts.map(fp => (
                    <div 
                      key={fp.sku} 
                      className="flex items-center gap-2 p-2 bg-white rounded-lg border border-blue-200 hover:border-blue-400 transition cursor-pointer"
                      onClick={() => navigate(`/inventory/${fp.sku}`)}
                    >
                      {fp.image && (
                        <img src={getImageUrl(fp.image)} alt={fp.name} className="w-10 h-10 object-cover rounded" />
                      )}
                      <div className="flex-1">
                        <div className="text-sm font-medium text-corp-text-dark">{fp.name}</div>
                        <div className="text-xs text-corp-text-muted">SKU: {fp.sku} • Є: {fp.quantity} шт</div>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {/* Product Info */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 mb-4">
          <h2 className="text-lg font-semibold mb-3">Інформація про товар</h2>
          
          {/* Image Upload Component */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Фото товару
            </label>
            <ImageUpload 
              sku={product.sku}
              currentImageUrl={product.image_url}
              onUploadSuccess={(newImageUrl) => {
                setProduct({ ...product, image_url: newImageUrl });
              }}
            />
          </div>

          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-corp-text-main">SKU:</span>
              <span className="font-semibold">{product.sku}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-corp-text-main">Назва:</span>
              <span className="font-semibold">{product.name}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-corp-text-main">В наявності:</span>
              <span className="font-semibold">{product.quantity || 0} шт</span>
            </div>
            <div className="flex justify-between">
              <span className="text-corp-text-main">Локація:</span>
              <span className="font-semibold">
                {product.zone || '—'} / {product.aisle || '—'} / {product.shelf || '—'}
              </span>
            </div>
          </div>
        </div>

        {/* Damage History */}
        {damageHistory.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-2xl p-6 mb-4">
            <h2 className="text-lg font-semibold mb-3 text-amber-900">
              🔨 Історія пошкоджень ({damageHistory.length})
            </h2>
            <div className="space-y-2">
              {damageHistory.map(d => (
                <div key={d.id} className="bg-white rounded-lg border border-amber-300 p-3">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="font-medium text-corp-text-dark">{d.damage_type}</div>
                      <div className="text-xs text-corp-text-muted mt-1">
                        {d.stage_label} · Замовлення #{d.order_number}
                      </div>
                      {d.note && (
                        <div className="text-sm text-corp-text-main mt-1">{d.note}</div>
                      )}
                      <div className="text-xs text-slate-400 mt-1">
                        {d.created_by} · {new Date(d.created_at).toLocaleString('uk-UA')}
                      </div>
                    </div>
                    <div className="text-right ml-3">
                      <div className={`text-sm font-semibold ${
                        d.severity === 'high' ? 'text-red-600' : 
                        d.severity === 'medium' ? 'text-amber-600' : 
                        'text-green-600'
                      }`}>
                        ₴{d.fee}
                      </div>
                      <div className="text-xs text-corp-text-muted mt-1">
                        {d.severity === 'high' ? '🔴 Високе' : 
                         d.severity === 'medium' ? '🟡 Середнє' : 
                         '🟢 Низьке'}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 text-sm text-amber-800">
              💡 При виявленні нового пошкодження оберіть "⚠️ Пошкоджено" нижче
            </div>
          </div>
        )}

        {/* Recount Form */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 mb-4">
          <h2 className="text-lg font-semibold mb-4">Результат перевірки</h2>

          {/* Status Selection */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Статус товару
            </label>
            <div className="grid grid-cols-3 gap-2">
              <button
                onClick={() => setStatus('available')}
                className={`p-3 rounded-lg border-2 text-sm font-medium transition-colors ${
                  status === 'available'
                    ? 'border-emerald-500 bg-emerald-50 text-emerald-700'
                    : 'border-slate-200 bg-white text-corp-text-main hover:border-slate-300'
                }`}
              >
                ✅ В нормі
              </button>
              <button
                onClick={() => setStatus('damaged')}
                className={`p-3 rounded-lg border-2 text-sm font-medium transition-colors ${
                  status === 'damaged'
                    ? 'border-amber-500 bg-amber-50 text-amber-700'
                    : 'border-slate-200 bg-white text-corp-text-main hover:border-slate-300'
                }`}
              >
                ⚠️ Пошкоджено
              </button>
              <button
                onClick={() => setStatus('missing')}
                className={`p-3 rounded-lg border-2 text-sm font-medium transition-colors ${
                  status === 'missing'
                    ? 'border-rose-500 bg-rose-50 text-rose-700'
                    : 'border-slate-200 bg-white text-corp-text-main hover:border-slate-300'
                }`}
              >
                ❌ Відсутній
              </button>
            </div>
          </div>

          {/* Damage Note (if damaged) */}
          {status === 'damaged' && (
            <div className="mb-4 p-3 bg-amber-50 rounded-lg border border-amber-200">
              <div className="text-sm text-amber-800 mb-2">
                ⚠️ При збереженні відкриється модальне вікно для детальної фіксації пошкодження.
              </div>
            </div>
          )}

          {/* Notes */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Примітки (опціонально)
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Додаткова інформація про стан товару..."
              rows={3}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Actions */}
          <div className="flex gap-2">
            <button
              onClick={handleSubmit}
              disabled={saving}
              className="flex-1 py-3 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? 'Збереження...' : '💾 Зберегти переобік'}
            </button>
            <button
              onClick={() => (window.history.length > 1 ? navigate(-1) : navigate('/'))}
              className="px-4 py-3 bg-slate-100 text-slate-700 rounded-lg font-medium hover:bg-slate-200"
            >
              Скасувати
            </button>
          </div>
        </div>

        {/* Quick Processing Actions */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 mb-4">
          <h2 className="text-lg font-semibold mb-3">Швидкі дії</h2>
          <p className="text-sm text-slate-500 mb-4">
            Відправити товар напряму на обробку (заморозить {product.quantity > 1 ? 'вказану кількість' : 'товар'})
          </p>
          
          {/* Quantity selector for multi-quantity items */}
          {product.quantity > 1 && (
            <div className="mb-4">
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Кількість для обробки
              </label>
              <div className="flex items-center gap-2">
                <button 
                  onClick={() => setProcessingQty(Math.max(1, processingQty - 1))}
                  className="w-10 h-10 rounded-lg border border-slate-200 text-lg font-bold hover:bg-slate-50"
                >
                  −
                </button>
                <input 
                  type="number" 
                  value={processingQty}
                  onChange={(e) => setProcessingQty(Math.min(product.quantity, Math.max(1, parseInt(e.target.value) || 1)))}
                  className="w-20 h-10 text-center border border-slate-200 rounded-lg"
                  min="1"
                  max={product.quantity}
                />
                <button 
                  onClick={() => setProcessingQty(Math.min(product.quantity, processingQty + 1))}
                  className="w-10 h-10 rounded-lg border border-slate-200 text-lg font-bold hover:bg-slate-50"
                >
                  +
                </button>
                <span className="text-sm text-slate-500 ml-2">з {product.quantity} шт</span>
              </div>
            </div>
          )}
          
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => handleQuickAction('wash')}
              disabled={sendingToProcessing}
              className="p-4 rounded-xl border-2 border-blue-200 bg-blue-50 hover:bg-blue-100 hover:border-blue-300 transition-all disabled:opacity-50"
            >
              <div className="text-2xl mb-1">🧽</div>
              <div className="text-sm font-medium text-blue-800">На мийку</div>
            </button>
            <button
              onClick={() => handleQuickAction('repair')}
              disabled={sendingToProcessing}
              className="p-4 rounded-xl border-2 border-amber-200 bg-amber-50 hover:bg-amber-100 hover:border-amber-300 transition-all disabled:opacity-50"
            >
              <div className="text-2xl mb-1">🔧</div>
              <div className="text-sm font-medium text-amber-800">На реставрацію</div>
            </button>
            <button
              onClick={() => handleQuickAction('laundry')}
              disabled={sendingToProcessing}
              className="p-4 rounded-xl border-2 border-purple-200 bg-purple-50 hover:bg-purple-100 hover:border-purple-300 transition-all disabled:opacity-50"
            >
              <div className="text-2xl mb-1">👔</div>
              <div className="text-sm font-medium text-purple-800">На хімчистку</div>
            </button>
            <button
              onClick={() => handleQuickAction('write_off')}
              disabled={sendingToProcessing}
              className="p-4 rounded-xl border-2 border-red-200 bg-red-50 hover:bg-red-100 hover:border-red-300 transition-all disabled:opacity-50"
            >
              <div className="text-2xl mb-1">🗑️</div>
              <div className="text-sm font-medium text-red-800">Списати</div>
            </button>
          </div>
          
          {sendingToProcessing && (
            <div className="mt-3 text-center text-sm text-slate-500">
              Відправляємо...
            </div>
          )}
        </div>

        {/* Quick Info */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-800">
          <div className="flex items-start gap-2">
            <span className="text-lg">💡</span>
            <div>
              <strong>Підказка:</strong> Відскануйте QR код на товарі щоб швидко потрапити на цю сторінку. 
              Всі дані переобліку зберігаються в систему для аналізу та звітності.
            </div>
          </div>
        </div>
      </div>
      
      {/* Damage Modal */}
      <DamageModal 
        isOpen={damageModalOpen}
        onClose={() => setDamageModalOpen(false)}
        item={{
          id: product?.product_id,
          sku: product?.sku,
          name: product?.name,
          inventory_id: product?.product_id
        }}
        order={null}
        stage='audit'
        onSave={handleDamageSaved}
        existingHistory={damageHistory}
      />
    </div>
  )
}
