/* eslint-disable */
import React, { useState } from 'react'
import ZoneCard from '../ZoneCard'

/**
 * Zone: Plan Dates - Планування дат
 * Для статусу: WAITING_CONFIRMATION
 */
export default function ZonePlanDates({
  issueDate,
  returnDate,
  issueTime = '11:30–12:00',
  returnTime = 'до 17:00',
  rentalDays = 1,
  onUpdate,
  readOnly = false,
}) {
  const [localIssueDate, setLocalIssueDate] = useState(issueDate || '')
  const [localReturnDate, setLocalReturnDate] = useState(returnDate || '')
  const [localIssueTime, setLocalIssueTime] = useState(issueTime)
  const [localReturnTime, setLocalReturnTime] = useState(returnTime)
  const [localRentalDays, setLocalRentalDays] = useState(rentalDays)
  
  const handleSave = () => {
    onUpdate?.({
      issueDate: localIssueDate,
      returnDate: localReturnDate,
      issueTime: localIssueTime,
      returnTime: localReturnTime,
      rentalDays: localRentalDays,
    })
  }
  
  // Розрахунок днів між датами
  const calculateDays = () => {
    if (!localIssueDate || !localReturnDate) return null
    const start = new Date(localIssueDate)
    const end = new Date(localReturnDate)
    const days = Math.ceil((end - start) / (1000 * 60 * 60 * 24))
    return days > 0 ? days : 1
  }
  
  const calculatedDays = calculateDays()
  
  const timeOptions = [
    '11:30–12:00',
    '12:00–12:30',
    '16:30–17:00',
  ]
  
  const returnTimeOptions = [
    'до 17:00',
    'до 16:00',
    'до 18:00',
  ]
  
  return (
    <ZoneCard
      title="📅 Дати оренди"
      hint="Видача / повернення • час • кількість діб"
      tone="neutral"
      actions={!readOnly ? [
        { label: '💾 Зберегти дати', onClick: handleSave, variant: 'primary' }
      ] : []}
    >
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {/* Дата видачі */}
        <div>
          <label className="text-xs text-slate-500 block mb-1">Дата видачі</label>
          {readOnly ? (
            <div className="font-medium text-slate-800">{localIssueDate || '—'}</div>
          ) : (
            <input
              type="date"
              value={localIssueDate}
              onChange={(e) => setLocalIssueDate(e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
            />
          )}
        </div>
        
        {/* Час видачі */}
        <div>
          <label className="text-xs text-slate-500 block mb-1">Час видачі</label>
          {readOnly ? (
            <div className="font-medium text-slate-800">{localIssueTime}</div>
          ) : (
            <select
              value={localIssueTime}
              onChange={(e) => setLocalIssueTime(e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
            >
              {timeOptions.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          )}
        </div>
        
        {/* Кількість діб */}
        <div>
          <label className="text-xs text-slate-500 block mb-1">Кількість діб</label>
          {readOnly ? (
            <div className="font-medium text-slate-800">{localRentalDays} дн.</div>
          ) : (
            <input
              type="number"
              min="1"
              value={localRentalDays}
              onChange={(e) => setLocalRentalDays(parseInt(e.target.value) || 1)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
            />
          )}
        </div>
        
        {/* Дата повернення */}
        <div>
          <label className="text-xs text-slate-500 block mb-1">Дата повернення</label>
          {readOnly ? (
            <div className="font-medium text-slate-800">{localReturnDate || '—'}</div>
          ) : (
            <input
              type="date"
              value={localReturnDate}
              onChange={(e) => setLocalReturnDate(e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
            />
          )}
        </div>
        
        {/* Час повернення */}
        <div>
          <label className="text-xs text-slate-500 block mb-1">Час повернення</label>
          {readOnly ? (
            <div className="font-medium text-slate-800">{localReturnTime}</div>
          ) : (
            <select
              value={localReturnTime}
              onChange={(e) => setLocalReturnTime(e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
            >
              {returnTimeOptions.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          )}
        </div>
        
        {/* Підказка */}
        {calculatedDays && calculatedDays !== localRentalDays && (
          <div className="col-span-full">
            <div className="text-xs text-amber-600 bg-amber-50 rounded-lg px-3 py-2">
              ⚠️ Між датами: {calculatedDays} дн., вказано: {localRentalDays} дн.
            </div>
          </div>
        )}
      </div>
    </ZoneCard>
  )
}
