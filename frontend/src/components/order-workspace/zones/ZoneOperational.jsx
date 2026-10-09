/* eslint-disable */
import React, { useState, useEffect } from 'react'
import ZoneCard from '../ZoneCard'
import axios from 'axios'
import { Plus, X, Percent, DollarSign, Banknote, Building2, Check, ChevronDown, ChevronUp } from 'lucide-react'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''

/**
 * Zone: Operational - Операційна інформація замовлення
 * Містить: менеджер, знижка (% або сума), додаткова послуга, оплата
 */
export default function ZoneOperational({
  orderId = null,
  orderNumber = '',
  customerName = '',
  managerId = null,
  managerName = '',
  discountPercent = 0,
  discountAmount = 0,
  serviceFee = 0,
  serviceFeeName = '',
  totalBeforeDiscount = 0,
  // Payment props
  totalRent = 0,
  totalDeposit = 0,
  paidRent = 0,
  paidDeposit = 0,
  payments = [],
  showPayment = false, // Показувати секцію оплати
  onPaymentSuccess,
  onUpdate,
  readOnly = false,
}) {
  // Локальні стани
  const [localManagerId, setLocalManagerId] = useState(managerId)
  const [localDiscountPercent, setLocalDiscountPercent] = useState(discountPercent)
  const [localDiscountAmount, setLocalDiscountAmount] = useState(discountAmount)
  const [discountMode, setDiscountMode] = useState(discountAmount > 0 ? 'amount' : 'percent') // 'percent' | 'amount'
  const [localServiceFee, setLocalServiceFee] = useState(serviceFee)
  const [localServiceFeeName, setLocalServiceFeeName] = useState(serviceFeeName)
  const [showServiceFeeForm, setShowServiceFeeForm] = useState(serviceFee > 0)
  
  // Payment states
  const [showPaymentForm, setShowPaymentForm] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [paymentType, setPaymentType] = useState('rent')
  const [paymentAmount, setPaymentAmount] = useState('')
  const [paymentMethod, setPaymentMethod] = useState('cash')
  const [paymentNote, setPaymentNote] = useState('')
  const [paymentCurrency, setPaymentCurrency] = useState('UAH')
  const [exchangeRate, setExchangeRate] = useState(41.5)
  const [isProcessingPayment, setIsProcessingPayment] = useState(false)
  
  // Список менеджерів
  const [managers, setManagers] = useState([])
  const [loadingManagers, setLoadingManagers] = useState(false)
  
  // Завантаження менеджерів
  useEffect(() => {
    loadManagers()
  }, [])
  
  const loadManagers = async () => {
    try {
      setLoadingManagers(true)
      const response = await axios.get(`${BACKEND_URL}/api/admin/staff`)
      if (response.data.managers) {
        setManagers(response.data.managers)
      }
    } catch (error) {
      console.error('Error loading managers:', error)
      setManagers([])
    } finally {
      setLoadingManagers(false)
    }
  }
  
  // Оновлення при зміні пропсів
  useEffect(() => {
    setLocalManagerId(managerId)
    setLocalDiscountPercent(discountPercent)
    setLocalDiscountAmount(discountAmount)
    setLocalServiceFee(serviceFee)
    setLocalServiceFeeName(serviceFeeName)
    if (discountAmount > 0 && discountPercent === 0) {
      setDiscountMode('amount')
    }
    if (serviceFee > 0) {
      setShowServiceFeeForm(true)
    }
  }, [managerId, discountPercent, discountAmount, serviceFee, serviceFeeName])
  
  // Розрахунок знижки
  const calculateDiscountAmount = () => {
    if (discountMode === 'percent') {
      return (totalBeforeDiscount * localDiscountPercent) / 100
    }
    return localDiscountAmount
  }
  
  const calculateDiscountPercent = () => {
    if (discountMode === 'amount' && totalBeforeDiscount > 0) {
      return (localDiscountAmount / totalBeforeDiscount) * 100
    }
    return localDiscountPercent
  }
  
  // Callback при зміні
  useEffect(() => {
    const selectedManager = managers.find(m => m.user_id === localManagerId)
    const finalDiscountPercent = discountMode === 'percent' ? localDiscountPercent : calculateDiscountPercent()
    const finalDiscountAmount = discountMode === 'amount' ? localDiscountAmount : calculateDiscountAmount()
    
    onUpdate?.({
      managerId: localManagerId,
      managerName: selectedManager?.full_name || '',
      discountPercent: finalDiscountPercent,
      discountAmount: finalDiscountAmount,
      serviceFee: serviceFee,
      serviceFeeName: serviceFeeName,
    })
  }, [localManagerId, localDiscountPercent, localDiscountAmount, discountMode, managers])
  
  // Payment calculations
  const remainingRent = Math.max(0, totalRent - paidRent)
  const remainingDeposit = Math.max(0, totalDeposit - paidDeposit)
  const rentProgress = totalRent > 0 ? Math.min(100, (paidRent / totalRent) * 100) : 0
  const depositProgress = totalDeposit > 0 ? Math.min(100, (paidDeposit / totalDeposit) * 100) : 0
  const isFullyPaid = paidRent >= totalRent && paidDeposit >= totalDeposit
  
  // Auto-fill payment amount
  useEffect(() => {
    if (showPaymentForm) {
      if (paymentType === 'rent' && remainingRent > 0) {
        setPaymentAmount(remainingRent.toString())
      } else if (paymentType === 'deposit' && remainingDeposit > 0) {
        setPaymentAmount(remainingDeposit.toString())
      }
    }
  }, [paymentType, remainingRent, remainingDeposit, showPaymentForm])
  
  // Submit payment
  const handleSubmitPayment = async () => {
    if (!paymentAmount || parseFloat(paymentAmount) <= 0) {
      alert('Введіть суму оплати')
      return
    }
    
    setIsProcessingPayment(true)
    try {
      const token = localStorage.getItem('token')
      const user = JSON.parse(localStorage.getItem('user') || '{}')
      
      if (paymentType === 'deposit') {
        // Deposit with currency support
        const depositRes = await fetch(`${BACKEND_URL}/api/finance/deposits/create`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
          body: JSON.stringify({
            order_id: orderId,
            expected_amount: totalDeposit,
            actual_amount: parseFloat(paymentAmount),
            currency: paymentCurrency,
            exchange_rate: paymentCurrency !== 'UAH' ? exchangeRate : null,
            method: paymentMethod,
            note: paymentCurrency !== 'UAH' 
              ? `${paymentAmount} ${paymentCurrency} @ ${exchangeRate}${paymentNote ? '. ' + paymentNote : ''}`
              : paymentNote || null,
            accepted_by_id: user.id || null,
            accepted_by_name: user.name || user.full_name || null
          })
        })
        if (!depositRes.ok) {
          const err = await depositRes.json().catch(() => ({}))
          throw new Error(err.detail || 'Помилка створення застави')
        }
      } else {
        const res = await fetch(`${BACKEND_URL}/api/finance/payments`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
          body: JSON.stringify({
            order_id: orderId,
            payment_type: paymentType,
            method: paymentMethod,
            amount: parseFloat(paymentAmount),
            note: paymentNote || null,
            payer_name: customerName,
            accepted_by_id: user.id || null,
            accepted_by_name: user.name || user.full_name || null
          })
        })
        if (!res.ok) {
          const err = await res.json().catch(() => ({}))
          throw new Error(err.detail || 'Помилка оплати')
        }
      }
      
      const currSymbol = { UAH: '₴', USD: '$', EUR: '€' }[paymentCurrency] || '₴'
      alert(`Оплату ${currSymbol}${fmtUA(paymentAmount)} прийнято!`)
      setShowPaymentForm(false)
      setPaymentAmount('')
      setPaymentNote('')
      setPaymentCurrency('UAH')
      onPaymentSuccess?.()
    } catch (e) {
      console.error('Payment error:', e)
      alert(`Помилка: ${e.message}`)
      alert(`❌ Помилка: ${e.message}`)
    } finally {
      setIsProcessingPayment(false)
    }
  }
  
  const fmtDate = (d) => d ? new Date(d).toLocaleString('uk-UA', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—'
  
  const selectedManagerName = managers.find(m => m.user_id === localManagerId)?.full_name || 'Не вибрано'
  const fmtUA = (n) => (Number(n) || 0).toLocaleString('uk-UA', { maximumFractionDigits: 0 })
  
  return (
    <ZoneCard
      title="⚙️ Операційна"
      hint="Менеджер • знижка • додаткові послуги"
      tone="neutral"
    >
      <div className="space-y-4">
        {/* Менеджер */}
        <div>
          <label className="text-xs text-slate-500 block mb-1.5">Менеджер замовлення</label>
          {readOnly ? (
            <div className="font-medium text-slate-800">{selectedManagerName}</div>
          ) : (
            <select
              value={localManagerId || ''}
              onChange={(e) => setLocalManagerId(parseInt(e.target.value) || null)}
              disabled={loadingManagers}
              className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm focus:border-blue-400 focus:ring-2 focus:ring-blue-100 outline-none disabled:bg-slate-100 transition-all"
            >
              {loadingManagers ? (
                <option>Завантаження...</option>
              ) : managers.length === 0 ? (
                <option value="">Немає менеджерів</option>
              ) : (
                managers.map(m => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.full_name} ({m.role === 'admin' ? 'Адмін' : m.role === 'manager' ? 'Менеджер' : m.role === 'office_manager' ? 'Офіс' : m.role})
                  </option>
                ))
              )}
            </select>
          )}
        </div>
        
        {/* Знижка — простий рядок */}
        <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-xl p-3 border border-amber-100">
          <label className="text-xs text-amber-700 font-medium block mb-2">Знижка</label>
          
          {readOnly ? (
            <div className="font-semibold text-amber-800 text-sm">
              {localDiscountAmount > 0 ? `₴${fmtUA(localDiscountAmount)}` : ''}
              {localDiscountAmount > 0 && localDiscountPercent > 0 ? ` (${Math.round(localDiscountPercent * 10) / 10}%)` : ''}
              {localDiscountPercent > 0 && localDiscountAmount === 0 ? `${localDiscountPercent}%` : ''}
              {localDiscountPercent === 0 && localDiscountAmount === 0 && 'Без знижки'}
            </div>
          ) : (
            <div className="flex items-center gap-2">
              {/* Сума */}
              <div className="relative flex-1">
                <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-amber-600 text-xs">₴</span>
                <input
                  type="number"
                  min="0"
                  step="100"
                  value={localDiscountAmount || ''}
                  onChange={(e) => {
                    const val = parseFloat(e.target.value) || 0
                    setLocalDiscountAmount(val)
                    setDiscountMode('amount')
                    if (totalBeforeDiscount > 0) {
                      setLocalDiscountPercent(Math.round((val / totalBeforeDiscount) * 1000) / 10)
                    }
                  }}
                  placeholder="0"
                  data-testid="discount-amount-input"
                  className="w-full rounded-lg border border-amber-200 pl-7 pr-2 py-1.5 text-sm font-medium focus:border-amber-400 focus:ring-1 focus:ring-amber-100 outline-none"
                />
              </div>
              {/* Відсоток */}
              <div className="relative" style={{width: '80px'}}>
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="0.5"
                  value={localDiscountPercent || ''}
                  onChange={(e) => {
                    const val = parseFloat(e.target.value) || 0
                    setLocalDiscountPercent(val)
                    setDiscountMode('percent')
                    if (totalBeforeDiscount > 0) {
                      setLocalDiscountAmount(Math.round(totalBeforeDiscount * val / 100))
                    }
                  }}
                  placeholder="0"
                  data-testid="discount-percent-input"
                  className="w-full rounded-lg border border-amber-200 px-2 pr-6 py-1.5 text-sm font-medium focus:border-amber-400 focus:ring-1 focus:ring-amber-100 outline-none"
                />
                <span className="absolute right-2 top-1/2 -translate-y-1/2 text-amber-600 text-xs">%</span>
              </div>
              {/* Зберегти */}
              <button
                onClick={() => {
                  const finalPercent = discountMode === 'percent' ? localDiscountPercent : calculateDiscountPercent()
                  const finalAmount = discountMode === 'amount' ? localDiscountAmount : calculateDiscountAmount()
                  onUpdate?.({
                    managerId: localManagerId,
                    managerName: managers.find(m => m.user_id === localManagerId)?.full_name || '',
                    discountPercent: finalPercent,
                    discountAmount: finalAmount,
                    serviceFee: localServiceFee,
                    serviceFeeName: localServiceFeeName,
                  })
                }}
                data-testid="discount-save-btn"
                className="px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-white text-xs font-medium transition-colors flex-shrink-0"
              >
                <Check className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>
        
        {/* === PAYMENT SECTION === */}
        {showPayment && (
          <div className="bg-gradient-to-r from-emerald-50 to-teal-50 rounded-xl p-4 border border-emerald-100">
            <div className="flex items-center justify-between mb-3">
              <label className="text-xs text-emerald-700 font-medium">💳 Оплата</label>
              {isFullyPaid && (
                <span className="text-xs bg-emerald-500 text-white px-2 py-0.5 rounded-full flex items-center gap-1">
                  <Check className="w-3 h-3" /> Оплачено
                </span>
              )}
            </div>
            
            {/* Progress bars */}
            <div className="space-y-2 mb-3">
              {/* Rent */}
              <div>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-slate-600">Оренда</span>
                  <span className={`font-medium ${paidRent >= totalRent ? 'text-emerald-600' : 'text-slate-700'}`}>
                    ₴{fmtUA(paidRent)} / ₴{fmtUA(totalRent)}
                  </span>
                </div>
                <div className="h-2 bg-white rounded-full overflow-hidden border border-emerald-100">
                  <div
                    className={`h-full rounded-full transition-all ${paidRent >= totalRent ? 'bg-emerald-500' : 'bg-blue-500'}`}
                    style={{ width: `${rentProgress}%` }}
                  />
                </div>
              </div>
              
              {/* Deposit */}
              <div>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-slate-600">Застава</span>
                  <span className={`font-medium ${paidDeposit >= totalDeposit ? 'text-emerald-600' : 'text-amber-600'}`}>
                    ₴{fmtUA(paidDeposit)} / ₴{fmtUA(totalDeposit)}
                  </span>
                </div>
                <div className="h-2 bg-white rounded-full overflow-hidden border border-emerald-100">
                  <div
                    className={`h-full rounded-full transition-all ${paidDeposit >= totalDeposit ? 'bg-emerald-500' : 'bg-amber-500'}`}
                    style={{ width: `${depositProgress}%` }}
                  />
                </div>
              </div>
            </div>
            
            {/* Payment Form */}
            {!readOnly && !isFullyPaid && (
              <>
                {!showPaymentForm ? (
                  <button
                    onClick={() => setShowPaymentForm(true)}
                    className="w-full py-2.5 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl transition-colors flex items-center justify-center gap-2"
                  >
                    <Plus className="w-4 h-4" />
                    Прийняти оплату
                  </button>
                ) : (
                  <div className="bg-white rounded-xl p-3 space-y-3 border border-emerald-200 mt-2">
                    {/* Payment Type */}
                    <div className="flex gap-2">
                      <button
                        onClick={() => setPaymentType('rent')}
                        className={`flex-1 py-2 text-xs font-medium rounded-lg transition-all ${
                          paymentType === 'rent'
                            ? 'bg-blue-600 text-white'
                            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                        }`}
                      >
                        Оренда
                        {remainingRent > 0 && <span className="block opacity-75">₴{fmtUA(remainingRent)}</span>}
                      </button>
                      <button
                        onClick={() => setPaymentType('deposit')}
                        className={`flex-1 py-2 text-xs font-medium rounded-lg transition-all ${
                          paymentType === 'deposit'
                            ? 'bg-amber-500 text-white'
                            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                        }`}
                      >
                        Застава
                        {remainingDeposit > 0 && <span className="block opacity-75">₴{fmtUA(remainingDeposit)}</span>}
                      </button>
                    </div>
                    
                    {/* Currency (only for deposit) */}
                    {paymentType === 'deposit' && (
                      <div className="space-y-2">
                        <div className="flex gap-2">
                          {['UAH', 'USD', 'EUR'].map(cur => (
                            <button
                              key={cur}
                              onClick={() => setPaymentCurrency(cur)}
                              className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-all ${
                                paymentCurrency === cur
                                  ? 'bg-amber-100 text-amber-700 border-2 border-amber-300'
                                  : 'bg-slate-50 border border-slate-200 text-slate-500 hover:bg-slate-100'
                              }`}
                            >
                              {{ UAH: '₴ UAH', USD: '$ USD', EUR: '€ EUR' }[cur]}
                            </button>
                          ))}
                        </div>
                        {paymentCurrency !== 'UAH' && (
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-slate-500">Курс:</span>
                            <input
                              type="number"
                              step="0.01"
                              value={exchangeRate}
                              onChange={(e) => setExchangeRate(Number(e.target.value))}
                              className="w-24 px-2 py-1 text-sm border border-slate-200 rounded-lg"
                            />
                            <span className="text-xs text-slate-400">
                              = ₴{fmtUA(parseFloat(paymentAmount || 0) * exchangeRate)}
                            </span>
                          </div>
                        )}
                      </div>
                    )}
                    
                    {/* Amount */}
                    <div className="relative">
                      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
                        {{ UAH: '₴', USD: '$', EUR: '€' }[paymentType === 'deposit' ? paymentCurrency : 'UAH']}
                      </span>
                      <input
                        type="number"
                        value={paymentAmount}
                        onChange={(e) => setPaymentAmount(e.target.value)}
                        placeholder="0"
                        className="w-full pl-8 pr-3 py-2 text-lg font-semibold border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                      />
                    </div>
                    
                    {/* Payment Method */}
                    <div className="flex gap-2">
                      {[
                        { key: 'cash', icon: Banknote, label: 'Готівка', color: 'emerald' },
                        { key: 'bank', icon: Building2, label: 'Безготівка', color: 'blue' }
                      ].map(({ key, icon: Icon, label, color }) => (
                        <button
                          key={key}
                          onClick={() => setPaymentMethod(key)}
                          className={`flex-1 py-2 text-sm rounded-lg flex items-center justify-center gap-1.5 transition-all ${
                            paymentMethod === key
                              ? `bg-${color}-100 text-${color}-700 border-2 border-${color}-300 font-medium`
                              : 'bg-slate-50 border border-slate-200 text-slate-500 hover:bg-slate-100'
                          }`}
                        >
                          <Icon className="w-4 h-4" />
                          {label}
                        </button>
                      ))}
                    </div>
                    
                    {/* Note */}
                    <input
                      type="text"
                      value={paymentNote}
                      onChange={(e) => setPaymentNote(e.target.value)}
                      placeholder="Коментар (опціонально)"
                      className="w-full px-3 py-2 text-xs border border-slate-200 rounded-lg"
                    />
                    
                    {/* Actions */}
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          setShowPaymentForm(false)
                          setPaymentAmount('')
                          setPaymentNote('')
                        }}
                        className="flex-1 py-2 text-sm text-slate-600 bg-slate-100 rounded-lg hover:bg-slate-200"
                      >
                        Скасувати
                      </button>
                      <button
                        onClick={handleSubmitPayment}
                        disabled={isProcessingPayment || !paymentAmount || parseFloat(paymentAmount) <= 0}
                        className="flex-1 py-2 text-sm font-semibold text-white bg-emerald-600 rounded-lg hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-1"
                      >
                        {isProcessingPayment ? '⏳' : <Check className="w-4 h-4" />}
                        Прийняти
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
            
            {/* Payment History */}
            {payments && payments.length > 0 && (
              <div className="mt-3 pt-3 border-t border-emerald-100">
                <button
                  onClick={() => setShowHistory(!showHistory)}
                  className="w-full flex items-center justify-between text-xs text-emerald-700 hover:text-emerald-900"
                >
                  <span className="font-medium">Історія ({payments.length})</span>
                  {showHistory ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
                
                {showHistory && (
                  <div className="mt-2 space-y-1.5 max-h-32 overflow-y-auto">
                    {payments.map((p, idx) => (
                      <div key={idx} className="flex items-center justify-between text-xs bg-white rounded-lg p-2 border border-emerald-50">
                        <div className="flex items-center gap-2">
                          <span className={`w-1.5 h-1.5 rounded-full ${p.payment_type === 'rent' ? 'bg-blue-500' : 'bg-amber-500'}`} />
                          <span className="text-slate-600">{p.payment_type === 'rent' ? 'Оренда' : 'Застава'}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-slate-400">{fmtDate(p.created_at)}</span>
                          <span className="font-semibold text-emerald-600">+₴{fmtUA(p.amount)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </ZoneCard>
  )
}
