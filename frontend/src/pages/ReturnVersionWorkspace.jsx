/* eslint-disable */
/**
 * Return Version Workspace - Картка версії часткового повернення
 * Показує товари які залишились у клієнта та дозволяє:
 * - Прийняти повернуті товари
 * - Нарахувати прострочення (вручну)
 * - Створити наступну версію якщо не все повернуто
 */

import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useToast } from '../hooks/use-toast'
import axios from 'axios'
import CorporateHeader from '../components/CorporateHeader'
import ZonePackagingReturn from '../components/order-workspace/zones/ZonePackagingReturn'
import { ArrowLeft, Package, Clock, DollarSign, Check, AlertTriangle, Plus, X } from 'lucide-react'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''

const fmtMoney = (val) => {
  const num = parseFloat(val) || 0
  return num.toLocaleString('uk-UA', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

export default function ReturnVersionWorkspace() {
  const { id: versionId } = useParams()
  const navigate = useNavigate()
  const { toast } = useToast()
  
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [version, setVersion] = useState(null)
  const [items, setItems] = useState([])
  
  // Стан для прийняття товарів
  const [acceptMode, setAcceptMode] = useState(false)
  const [returnedItems, setReturnedItems] = useState({}) // { sku: qty }
  
  // Стан для нарахування
  const [chargeModal, setChargeModal] = useState(false)
  const [chargeAmount, setChargeAmount] = useState(0)
  const [chargeNotes, setChargeNotes] = useState('')

  // Завантаження даних
  const loadVersion = async () => {
    try {
      setLoading(true)
      const res = await axios.get(`${BACKEND_URL}/api/return-versions/${versionId}`)
      setVersion(res.data)
      setItems(res.data.items || [])
      setChargeAmount(res.data.calculated_total_fee || 0)
    } catch (err) {
      console.error('Error loading version:', err)
      toast({
        title: '❌ Помилка',
        description: 'Не вдалося завантажити дані',
        variant: 'destructive'
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (versionId) loadVersion()
  }, [versionId])

  // Оновити кількість повернутого товару
  const handleReturnQty = (sku, qty) => {
    setReturnedItems(prev => ({
      ...prev,
      [sku]: Math.max(0, qty)
    }))
  }

  // Прийняти товари
  const handleAcceptItems = async () => {
    const itemsToAccept = Object.entries(returnedItems)
      .filter(([_, qty]) => qty > 0)
      .map(([sku, qty]) => ({ sku, returned_qty: qty }))
    
    if (itemsToAccept.length === 0) {
      toast({
        title: 'Увага',
        description: 'Вкажіть кількість повернутих товарів',
        variant: 'destructive'
      })
      return
    }

    setSaving(true)
    try {
      const res = await axios.post(`${BACKEND_URL}/api/return-versions/${versionId}/accept-items`, {
        items: itemsToAccept
      })
      
      toast({
        title: 'Товари прийнято',
        description: res.data.message
      })
      
      if (res.data.all_returned) {
        // Все повернуто - повернутись на дашборд
        navigate('/manager')
      } else if (res.data.remaining_items?.length > 0) {
        // Є неповернені - запитати чи створити нову версію
        if (confirm(`Залишилось ${res.data.remaining_items.length} позицій.\n\nСтворити нову версію?`)) {
          const nextRes = await axios.post(`${BACKEND_URL}/api/return-versions/${versionId}/create-next`)
          toast({
            title: 'Створено нову версію',
            description: nextRes.data.new_order_number
          })
          navigate(`/return-version/${nextRes.data.new_version_id}`)
        } else {
          loadVersion()
        }
      } else {
        loadVersion()
      }
      
      setAcceptMode(false)
      setReturnedItems({})
    } catch (err) {
      console.error('Error accepting items:', err)
      toast({
        title: '❌ Помилка',
        description: err.response?.data?.detail || 'Не вдалося прийняти товари',
        variant: 'destructive'
      })
    } finally {
      setSaving(false)
    }
  }

  // Нарахувати прострочення
  const handleChargeFee = async () => {
    if (chargeAmount <= 0) {
      toast({
        title: 'Увага',
        description: 'Вкажіть суму для нарахування',
        variant: 'destructive'
      })
      return
    }

    setSaving(true)
    try {
      await axios.post(`${BACKEND_URL}/api/return-versions/${versionId}/charge-fee`, {
        amount: chargeAmount,
        notes: chargeNotes
      })
      
      toast({
        title: 'Прострочення нараховано',
        description: `₴${fmtMoney(chargeAmount)}`
      })
      
      setChargeModal(false)
      loadVersion()
    } catch (err) {
      console.error('Error charging fee:', err)
      toast({
        title: '❌ Помилка',
        description: err.response?.data?.detail || 'Не вдалося нарахувати',
        variant: 'destructive'
      })
    } finally {
      setSaving(false)
    }
  }

  // Списати прострочення
  const handleWaiveFee = async () => {
    const reason = prompt('Причина списання:')
    if (reason === null) return

    setSaving(true)
    try {
      await axios.post(`${BACKEND_URL}/api/return-versions/${versionId}/waive-fee`, {
        reason: reason || 'Без причини'
      })
      
      toast({
        title: 'Прострочення списано',
      })
      
      loadVersion()
    } catch (err) {
      console.error('Error waiving fee:', err)
      toast({
        title: '❌ Помилка',
        variant: 'destructive'
      })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-corp-bg-page">
        <CorporateHeader cabinetName="Часткове повернення" />
        <div className="max-w-4xl mx-auto p-6">
          <div className="animate-pulse space-y-4">
            <div className="h-8 bg-slate-200 rounded w-1/3" />
            <div className="h-64 bg-slate-200 rounded" />
          </div>
        </div>
      </div>
    )
  }

  if (!version) {
    return (
      <div className="min-h-screen bg-corp-bg-page">
        <CorporateHeader cabinetName="Часткове повернення" />
        <div className="max-w-4xl mx-auto p-6 text-center">
          <p className="text-slate-500">Версія не знайдена</p>
          <button onClick={() => (window.history.length > 1 ? navigate(-1) : navigate('/manager'))} className="mt-4 text-blue-600">
            ← Повернутись
          </button>
        </div>
      </div>
    )
  }

  const remainingItems = items.filter(it => it.remaining_qty > 0)
  const hasUnreturned = remainingItems.length > 0

  return (
    <div className="min-h-screen bg-corp-bg-page">
      <CorporateHeader cabinetName="Часткове повернення" />
      
      <div className="max-w-4xl mx-auto p-6">
        {/* Навігація */}
        <button 
          onClick={() => (window.history.length > 1 ? navigate(-1) : navigate('/manager'))}
          className="flex items-center gap-2 text-sm text-slate-600 hover:text-slate-800 mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          Назад
        </button>

        {/* Заголовок */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 mb-6">
          <div className="flex items-start justify-between gap-4 mb-4">
            <div>
              <h1 className="text-2xl font-bold text-slate-800">{version.order_number}</h1>
              <p className="text-slate-500">
                Батьківське: <a href="#" onClick={(e) => { e.preventDefault(); navigate(`/manager/orders/${version.parent_order_id}`) }} className="text-blue-600 hover:underline">{version.parent?.order_number}</a>
              </p>
            </div>
            <div className={`px-3 py-1.5 rounded-lg text-sm font-medium ${
              version.status === 'returned' 
                ? 'bg-green-100 text-green-700' 
                : 'bg-amber-100 text-amber-700'
            }`}>
              {version.status === 'returned' ? 'Повернено' : 'Очікує'}
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <div className="bg-slate-50 rounded-xl p-3">
              <div className="text-xs text-slate-500 mb-1">Клієнт</div>
              <div className="font-medium">{version.customer_name}</div>
              <div className="text-sm text-slate-500">{version.customer_phone}</div>
            </div>
            <div className="bg-slate-50 rounded-xl p-3">
              <div className="text-xs text-slate-500 mb-1">Дата повернення</div>
              <div className="font-medium">{version.original_return_date}</div>
            </div>
            {version.days_overdue > 0 && (
              <div className="bg-amber-50 rounded-xl p-3">
                <div className="text-xs text-amber-600 mb-1">Прострочення</div>
                <div className="font-bold text-amber-700">{version.days_overdue} днів</div>
              </div>
            )}
          </div>
        </div>

        {/* Товари */}
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden mb-6">
          <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
            <h2 className="font-semibold text-slate-800">
              Товари ({remainingItems.length} залишилось)
            </h2>
            {hasUnreturned && version.status === 'active' && (
              <button
                onClick={() => setAcceptMode(!acceptMode)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  acceptMode 
                    ? 'bg-slate-200 text-slate-700' 
                    : 'bg-blue-600 text-white hover:bg-blue-700'
                }`}
              >
                {acceptMode ? 'Скасувати' : 'Прийняти товари'}
              </button>
            )}
          </div>
          
          <div className="divide-y divide-slate-100">
            {items.map((item, idx) => {
              const isReturned = item.remaining_qty === 0
              const returnQty = returnedItems[item.sku] || 0
              
              return (
                <div 
                  key={idx}
                  className={`px-6 py-4 flex items-center gap-4 ${isReturned ? 'bg-green-50/50' : ''}`}
                >
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    isReturned ? 'bg-green-100' : 'bg-slate-100'
                  }`}>
                    {isReturned ? (
                      <Check className="w-5 h-5 text-green-600" />
                    ) : (
                      <Package className="w-5 h-5 text-slate-400" />
                    )}
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <div className={`font-medium ${isReturned ? 'text-green-700' : 'text-slate-800'}`}>
                      {item.sku}
                    </div>
                    <div className="text-sm text-slate-500 truncate">{item.name}</div>
                  </div>
                  
                  <div className="text-right">
                    <div className="text-sm text-slate-500">
                      {isReturned ? (
                        <span className="text-green-600">Повернуто</span>
                      ) : (
                        <>Залишилось: <b>{item.remaining_qty}</b> / {item.qty}</>
                      )}
                    </div>
                    <div className="text-xs text-slate-400">₴{fmtMoney(item.daily_rate)}/день</div>
                  </div>
                  
                  {/* Поле для вводу кількості при прийманні */}
                  {acceptMode && !isReturned && (
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleReturnQty(item.sku, returnQty - 1)}
                        className="w-8 h-8 rounded bg-slate-100 hover:bg-slate-200 flex items-center justify-center"
                      >
                        -
                      </button>
                      <input
                        type="number"
                        value={returnQty}
                        onChange={(e) => handleReturnQty(item.sku, parseInt(e.target.value) || 0)}
                        className="w-16 h-8 border rounded text-center"
                        min="0"
                        max={item.remaining_qty}
                      />
                      <button
                        onClick={() => handleReturnQty(item.sku, Math.min(returnQty + 1, item.remaining_qty))}
                        className="w-8 h-8 rounded bg-slate-100 hover:bg-slate-200 flex items-center justify-center"
                      >
                        +
                      </button>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* Повернення тари */}
        <ZonePackagingReturn
          orderId={version.parent_order_id || parseInt(versionId)}
          onChargeChange={() => {}}
        />

        {/* Кнопки дій */}
        {version.status === 'active' && (
          <div className="flex flex-wrap gap-3">
            {acceptMode ? (
              <button
                onClick={handleAcceptItems}
                disabled={saving}
                className="flex-1 py-3 bg-green-600 text-white rounded-xl font-medium hover:bg-green-700 disabled:opacity-50"
              >
                {saving ? 'Збереження...' : '✓ Підтвердити приймання'}
              </button>
            ) : null}
          </div>
        )}
      </div>
    </div>
  )
}
