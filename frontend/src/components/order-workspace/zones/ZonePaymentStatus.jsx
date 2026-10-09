/* eslint-disable */
import React, { useState, useEffect } from 'react'
import ZoneCard from '../ZoneCard'
import { CreditCard, Banknote, Building2, ChevronDown, ChevronUp, Plus, Check, X } from 'lucide-react'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL

/**
 * Zone: Payment Status - Фінансовий статус замовлення
 * Показує прогрес оплати, дозволяє вносити оплати, показує історію
 */
export default function ZonePaymentStatus({
  orderId,
  orderNumber,
  customerName,
  totalRent = 0,
  totalDeposit = 0,
  paidRent = 0,
  paidDeposit = 0,
  payments = [],
  onPaymentSuccess,
  readOnly = false
}) {
  const [showPaymentForm, setShowPaymentForm] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [paymentType, setPaymentType] = useState('rent')
  const [paymentAmount, setPaymentAmount] = useState('')
  const [paymentMethod, setPaymentMethod] = useState('cash')
  const [paymentNote, setPaymentNote] = useState('')
  const [paymentCurrency, setPaymentCurrency] = useState('UAH')
  const [exchangeRate, setExchangeRate] = useState(41.5)
  const [isProcessing, setIsProcessing] = useState(false)
  
  const fmtUA = (n) => (Number(n) || 0).toLocaleString('uk-UA', { maximumFractionDigits: 0 })
  const fmtDate = (d) => d ? new Date(d).toLocaleString('uk-UA', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—'
  
  // Розрахунки
  const remainingRent = Math.max(0, totalRent - paidRent)
  const remainingDeposit = Math.max(0, totalDeposit - paidDeposit)
  const rentProgress = totalRent > 0 ? Math.min(100, (paidRent / totalRent) * 100) : 0
  const depositProgress = totalDeposit > 0 ? Math.min(100, (paidDeposit / totalDeposit) * 100) : 0
  const isFullyPaid = paidRent >= totalRent && paidDeposit >= totalDeposit
  
  // Тон картки
  const tone = isFullyPaid ? 'ok' : (paidRent > 0 || paidDeposit > 0) ? 'warn' : 'neutral'
  
  // Автозаповнення суми при зміні типу
  useEffect(() => {
    if (paymentType === 'rent' && remainingRent > 0) {
      setPaymentAmount(remainingRent.toString())
    } else if (paymentType === 'deposit' && remainingDeposit > 0) {
      setPaymentAmount(remainingDeposit.toString())
    }
  }, [paymentType, remainingRent, remainingDeposit])
  
  // Відправка оплати
  const handleSubmitPayment = async () => {
    if (!paymentAmount || parseFloat(paymentAmount) <= 0) {
      alert('Введіть суму оплати')
      return
    }
    
    setIsProcessing(true)
    try {
      const token = localStorage.getItem('token')
      const user = JSON.parse(localStorage.getItem('user') || '{}')
      
      if (paymentType === 'deposit') {
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
    } finally {
      setIsProcessing(false)
    }
  }
  
  const methodLabels = {
    'cash': { icon: Banknote, label: 'Готівка', color: 'emerald' },
    'card': { icon: CreditCard, label: 'Картка', color: 'blue' },
    'bank': { icon: Building2, label: 'IBAN', color: 'purple' }
  }

  return (
    <ZoneCard
      title="💳 Фінансовий статус"
      hint={isFullyPaid ? 'Повністю оплачено' : `Залишок: ₴${fmtUA(remainingRent + remainingDeposit)}`}
      tone={tone}
    >
      <div className="space-y-4">
        {/* Progress Bars */}
        <div className="space-y-3">
          {/* Rent */}
          <div>
            <div className="flex items-center justify-between text-sm mb-1.5">
              <span className="text-slate-600 font-medium">Оренда</span>
              <span className={`font-semibold ${paidRent >= totalRent ? 'text-emerald-600' : 'text-slate-700'}`}>
                ₴{fmtUA(paidRent)} / ₴{fmtUA(totalRent)}
              </span>
            </div>
            <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  paidRent >= totalRent ? 'bg-emerald-500' : 'bg-blue-500'
                }`}
                style={{ width: `${rentProgress}%` }}
              />
            </div>
            {paidRent >= totalRent && (
              <div className="flex items-center gap-1 text-xs text-emerald-600 mt-1">
                <Check className="w-3 h-3" /> Оплачено повністю
              </div>
            )}
          </div>
          
          {/* Deposit */}
          <div>
            <div className="flex items-center justify-between text-sm mb-1.5">
              <span className="text-slate-600 font-medium">Застава</span>
              <span className={`font-semibold ${paidDeposit >= totalDeposit ? 'text-emerald-600' : 'text-amber-600'}`}>
                ₴{fmtUA(paidDeposit)} / ₴{fmtUA(totalDeposit)}
              </span>
            </div>
            <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  paidDeposit >= totalDeposit ? 'bg-emerald-500' : 'bg-amber-500'
                }`}
                style={{ width: `${depositProgress}%` }}
              />
            </div>
            {paidDeposit >= totalDeposit && (
              <div className="flex items-center gap-1 text-xs text-emerald-600 mt-1">
                <Check className="w-3 h-3" /> Оплачено повністю
              </div>
            )}
          </div>
        </div>
        
        {/* Payment Form Toggle */}
        {!readOnly && !isFullyPaid && (
          <div>
            {!showPaymentForm ? (
              <button
                onClick={() => setShowPaymentForm(true)}
                className="w-full py-2.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-xl transition-colors flex items-center justify-center gap-2"
              >
                <Plus className="w-4 h-4" />
                Прийняти оплату
              </button>
            ) : (
              <div className="bg-slate-50 rounded-xl p-4 space-y-4 border border-slate-200">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-slate-800">Нова оплата</span>
                  <button
                    onClick={() => setShowPaymentForm(false)}
                    className="p-1 hover:bg-slate-200 rounded-lg transition-colors"
                  >
                    <X className="w-4 h-4 text-slate-500" />
                  </button>
                </div>
                
                {/* Payment Type */}
                <div className="flex gap-2">
                  <button
                    onClick={() => setPaymentType('rent')}
                    className={`flex-1 py-2.5 text-sm font-medium rounded-xl transition-all ${
                      paymentType === 'rent'
                        ? 'bg-blue-600 text-white shadow-lg shadow-blue-200'
                        : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    Оренда
                    {remainingRent > 0 && (
                      <span className="block text-xs opacity-80">₴{fmtUA(remainingRent)}</span>
                    )}
                  </button>
                  <button
                    onClick={() => setPaymentType('deposit')}
                    className={`flex-1 py-2.5 text-sm font-medium rounded-xl transition-all ${
                      paymentType === 'deposit'
                        ? 'bg-amber-500 text-white shadow-lg shadow-amber-200'
                        : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    Застава
                    {remainingDeposit > 0 && (
                      <span className="block text-xs opacity-80">₴{fmtUA(remainingDeposit)}</span>
                    )}
                  </button>
                </div>
                
                {/* Currency (only for deposit) */}
                {paymentType === 'deposit' && (
                  <div className="space-y-2">
                    <label className="text-xs text-slate-500 block">Валюта</label>
                    <div className="flex gap-2">
                      {['UAH', 'USD', 'EUR'].map(cur => (
                        <button
                          key={cur}
                          onClick={() => setPaymentCurrency(cur)}
                          className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-all ${
                            paymentCurrency === cur
                              ? 'bg-amber-100 text-amber-700 border-2 border-amber-300'
                              : 'bg-white border border-slate-200 text-slate-500 hover:bg-slate-50'
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
                <div>
                  <label className="text-xs text-slate-500 block mb-1">Сума оплати</label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
                      {{ UAH: '₴', USD: '$', EUR: '€' }[paymentType === 'deposit' ? paymentCurrency : 'UAH']}
                    </span>
                    <input
                      type="number"
                      value={paymentAmount}
                      onChange={(e) => setPaymentAmount(e.target.value)}
                      placeholder="0"
                      className="w-full pl-8 pr-4 py-2.5 text-lg font-semibold border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                </div>
                
                {/* Payment Method */}
                <div>
                  <label className="text-xs text-slate-500 block mb-2">Спосіб оплати</label>
                  <div className="flex gap-2">
                    {Object.entries(methodLabels).map(([key, { icon: Icon, label, color }]) => (
                      <button
                        key={key}
                        onClick={() => setPaymentMethod(key)}
                        className={`flex-1 py-2 text-xs rounded-xl flex items-center justify-center gap-1.5 transition-all ${
                          paymentMethod === key
                            ? `bg-${color}-100 text-${color}-700 border-2 border-${color}-300 font-medium`
                            : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
                        }`}
                      >
                        <Icon className="w-4 h-4" />
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
                
                {/* Note */}
                <div>
                  <label className="text-xs text-slate-500 block mb-1">Коментар</label>
                  <input
                    type="text"
                    value={paymentNote}
                    onChange={(e) => setPaymentNote(e.target.value)}
                    placeholder="Опціонально"
                    className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl"
                  />
                </div>
                
                {/* Submit */}
                <button
                  onClick={handleSubmitPayment}
                  disabled={isProcessing || !paymentAmount || parseFloat(paymentAmount) <= 0}
                  className="w-full py-3 text-sm font-semibold text-white bg-emerald-600 rounded-xl hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
                >
                  {isProcessing ? (
                    <>
                      <span className="animate-spin">⏳</span> Обробка...
                    </>
                  ) : (
                    <>
                      <Check className="w-4 h-4" /> Підтвердити оплату
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
        )}
        
        {/* Full Payment Badge */}
        {isFullyPaid && (
          <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 text-center">
            <div className="text-emerald-700 font-semibold flex items-center justify-center gap-2">
              <Check className="w-5 h-5" />
              Замовлення повністю оплачено
            </div>
          </div>
        )}
        
        {/* Payment History Toggle */}
        {payments && payments.length > 0 && (
          <div className="border-t border-slate-100 pt-3">
            <button
              onClick={() => setShowHistory(!showHistory)}
              className="w-full flex items-center justify-between text-sm text-slate-600 hover:text-slate-800 transition-colors"
            >
              <span className="font-medium">Історія оплат ({payments.length})</span>
              {showHistory ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
            
            {showHistory && (
              <div className="mt-3 space-y-2 max-h-48 overflow-y-auto">
                {payments.map((p, idx) => (
                  <div key={idx} className="flex items-center justify-between text-sm bg-slate-50 rounded-lg p-2">
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${
                        p.payment_type === 'rent' ? 'bg-blue-500' : 'bg-amber-500'
                      }`} />
                      <span className="text-slate-600">
                        {p.payment_type === 'rent' ? 'Оренда' : 'Застава'}
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-slate-400">{fmtDate(p.created_at)}</span>
                      <span className="font-semibold text-emerald-600">+₴{fmtUA(p.amount)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </ZoneCard>
  )
}
