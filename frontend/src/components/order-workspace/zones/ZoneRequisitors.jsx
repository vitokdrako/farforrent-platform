/* eslint-disable */
import React, { useState, useEffect } from 'react'
import axios from 'axios'
import ZoneCard from '../ZoneCard'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''

/**
 * Zone: Requisitors - Вибір комплектувальників (тільки реквізитори)
 * Дозволяє обрати кількох працівників для комплектації
 */
export default function ZoneRequisitors({
  selectedIds = [],
  onSelectionChange,
  readOnly = false,
  title = "Комплектувальники",
  hint = "Оберіть хто займається комплектацією"
}) {
  const [requisitors, setRequisitors] = useState([])
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    loadRequisitors()
  }, [])
  
  const loadRequisitors = async () => {
    try {
      // Завантажуємо працівників
      const response = await axios.get(`${BACKEND_URL}/api/admin/staff`)
      // Фільтруємо ТІЛЬКИ реквізиторів
      const allStaff = response.data?.all || response.data?.requisitors || []
      const onlyRequisitors = allStaff.filter(s => s.role === 'requisitor')
      setRequisitors(onlyRequisitors)
    } catch (err) {
      console.error('Error loading requisitors:', err)
      setRequisitors([])
    } finally {
      setLoading(false)
    }
  }
  
  const toggleRequisitor = (userId, fullName) => {
    if (readOnly) return
    
    // Зберігаємо об'єкти {user_id, name} замість просто ID
    const isSelected = selectedIds.some(r => 
      (typeof r === 'object' ? r.user_id : r) === userId
    )
    
    let newSelection
    if (isSelected) {
      newSelection = selectedIds.filter(r => 
        (typeof r === 'object' ? r.user_id : r) !== userId
      )
    } else {
      newSelection = [...selectedIds, { user_id: userId, name: fullName }]
    }
    
    onSelectionChange?.(newSelection)
  }
  
  // Отримуємо імена - підтримуємо і старий формат (просто ID) і новий (об'єкти)
  const selectedNames = selectedIds.map(r => {
    if (typeof r === 'object' && r.name) {
      // Прибираємо "Реквізитор" з імені
      return r.name.replace(/\s*реквізитор\s*/gi, '').trim()
    }
    // Старий формат - шукаємо в завантажених реквізиторах
    const found = requisitors.find(req => req.user_id === r)
    const name = found?.full_name || ''
    return name.replace(/\s*реквізитор\s*/gi, '').trim() || r
  }).filter(Boolean)
  
  // Перевірка чи обраний (підтримка обох форматів)
  const isUserSelected = (userId) => selectedIds.some(r => 
    (typeof r === 'object' ? r.user_id : r) === userId
  )
  
  const tone = selectedIds.length > 0 ? 'ok' : 'warn'
  
  return (
    <ZoneCard
      title={title}
      hint={selectedIds.length > 0 ? `Обрано: ${selectedNames.join(', ')}` : hint}
      tone={tone}
    >
      {loading ? (
        <div className="text-center py-4 text-corp-text-muted">Завантаження...</div>
      ) : requisitors.length === 0 ? (
        <div className="text-center py-4 text-corp-text-muted">Немає доступних комплектувальників</div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {requisitors.map((person) => {
            const isSelected = isUserSelected(person.user_id)
            // Прибираємо "Реквізитор" з імені для відображення
            const displayName = person.full_name?.replace(/\s*реквізитор\s*/gi, '').trim() || person.full_name
            
            return (
              <button
                key={person.user_id}
                onClick={() => toggleRequisitor(person.user_id, displayName)}
                disabled={readOnly}
                className={`
                  flex items-center gap-2 px-4 py-2.5 rounded-lg border font-medium text-sm
                  transition-all duration-150
                  ${isSelected 
                    ? 'bg-corp-primary/10 border-corp-primary text-corp-primary' 
                    : 'bg-white border-corp-border text-corp-text-main hover:border-corp-primary/50 hover:bg-corp-bg-light'
                  }
                  ${readOnly ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}
                `}
              >
                <span>{displayName}</span>
                {isSelected && <span className="text-corp-primary font-bold">✓</span>}
              </button>
            )
          })}
        </div>
      )}
      
      {/* Показати обраних - завжди якщо є */}
      {(selectedIds.length > 0 || selectedNames.length > 0) && (
        <div className="mt-3 pt-3 border-t border-corp-border">
          <div className="text-xs text-corp-text-muted mb-1">Відповідальні за комплектацію:</div>
          <div className="font-medium text-corp-text-dark">
            {selectedNames.length > 0 
              ? selectedNames.join(', ') 
              : `${selectedIds.length} обрано (завантаження...)`
            }
          </div>
        </div>
      )}
    </ZoneCard>
  )
}
