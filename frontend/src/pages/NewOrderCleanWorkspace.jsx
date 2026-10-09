/* eslint-disable */
/**
 * New Order Clean - Створення нового замовлення (DRAFT)
 * Використовує уніфіковану систему Order Workspace
 */

import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useToast } from '../hooks/use-toast'
import axios from 'axios'

import {
  OrderWorkspaceLayout,
  LeftRailClient,
  LeftRailFinance,
  LeftRailTimeline,
} from '../components/order-workspace'

import {
  ZoneClientForm,
  ZonePlanDates,
  ZoneItemsEditor,
  ZoneDeliverySetup,
  ZoneNotes,
} from '../components/order-workspace/zones'
// FinanceStatusCard тепер тільки в LeftRailFinance

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''

export default function NewOrderClean() {
  const navigate = useNavigate()
  const { toast } = useToast()
  
  // === СТАН ФОРМИ ===
  // Клієнт
  const [clientName, setClientName] = useState('')
  const [clientPhone, setClientPhone] = useState('')
  const [clientEmail, setClientEmail] = useState('')
  const [clientType, setClientType] = useState('retail')
  const [discount, setDiscount] = useState(0)
  const [managerId, setManagerId] = useState(null)
  const [managerName, setManagerName] = useState('')
  
  // Дати
  const [issueDate, setIssueDate] = useState('')
  const [issueTime, setIssueTime] = useState('11:30–12:00')
  const [returnDate, setReturnDate] = useState('')
  const [returnTime, setReturnTime] = useState('до 17:00')
  const [rentalDays, setRentalDays] = useState(1)
  
  // Позиції
  const [items, setItems] = useState([{ sku: '', name: '', qty: 1, price: 0 }])
  const [inventory, setInventory] = useState([])
  const [loadingInventory, setLoadingInventory] = useState(false)
  
  // Доставка
  const [deliveryType, setDeliveryType] = useState('pickup')
  const [deliveryAddress, setDeliveryAddress] = useState('')
  const [deliveryInstructions, setDeliveryInstructions] = useState('')
  
  // Нотатки
  const [notes, setNotes] = useState('')
  
  // Стан збереження
  const [saving, setSaving] = useState(false)
  
  // Таймлайн подій
  const [events] = useState([
    { text: 'Створено чернетку', at: new Date().toLocaleString('uk-UA'), tone: 'blue', user: 'Система' }
  ])
  
  // === ЗАВАНТАЖЕННЯ ІНВЕНТАРЮ ===
  useEffect(() => {
    loadInventory()
  }, [])
  
  const loadInventory = async () => {
    try {
      setLoadingInventory(true)
      const response = await axios.get(`${BACKEND_URL}/api/inventory`)
      // Трансформуємо дані: rent_price -> price_per_day
      const transformedInventory = (response.data || []).map(item => ({
        ...item,
        price_per_day: item.rent_price || item.rental_price || item.price_per_day || 0,
        damage_cost: item.price || item.damage_cost || 0  // Ціна купівлі = вартість збитків
      }))
      setInventory(transformedInventory)
    } catch (error) {
      console.error('Error loading inventory:', error)
    } finally {
      setLoadingInventory(false)
    }
  }
  
  // === РОЗРАХУНКИ ===
  const calculations = useMemo(() => {
    const days = rentalDays || 1
    
    const totalRent = items.reduce((sum, item) => {
      return sum + ((item.price || 0) * (item.qty || 1) * days)
    }, 0)
    
    const discountAmount = (totalRent * discount) / 100
    const rentAfterDiscount = totalRent - discountAmount
    
    // Застава = 50% від вартості товару (damage_cost/price) * кількість
    // damage_cost береться з інвентарю, або якщо немає - price * 2
    const estimatedDeposit = items.reduce((sum, item) => {
      const damageCost = item.damage_cost || (item.price || 0) * 2
      return sum + (damageCost * 0.5 * (item.qty || 1))
    }, 0)
    
    return {
      totalRent,
      discountAmount,
      totalDiscount: discountAmount,
      rentAfterDiscount,
      estimatedDeposit,
      itemsCount: items.filter(i => i.name).length
    }
  }, [items, rentalDays, discount])
  
  // Removed deposit amount auto-update
  
  // === ОБРОБНИКИ ===
  const handleAddItem = () => {
    setItems([...items, { sku: '', name: '', qty: 1, price: 0 }])
  }
  
  const handleRemoveItem = (index) => {
    setItems(items.filter((_, i) => i !== index))
  }
  
  const handleUpdateItem = (index, field, value) => {
    const newItems = [...items]
    newItems[index][field] = value
    setItems(newItems)
  }
  
  const handleDatesUpdate = (dates) => {
    setIssueDate(dates.issueDate)
    setReturnDate(dates.returnDate)
    setIssueTime(dates.issueTime)
    setReturnTime(dates.returnTime)
    setRentalDays(dates.rentalDays)
  }
  
  const handleDeliveryUpdate = (delivery) => {
    setDeliveryType(delivery.deliveryType)
    setDeliveryAddress(delivery.address)
    setDeliveryInstructions(delivery.instructions)
  }
  
  // === СТВОРЕННЯ ЗАМОВЛЕННЯ ===
  const handleCreateOrder = async () => {
    // Валідація
    if (!clientName || !clientPhone) {
      toast({
        title: '❌ Помилка',
        description: 'Заповніть ім\'я та телефон клієнта',
        variant: 'destructive',
      })
      return
    }
    
    if (!issueDate || !returnDate) {
      toast({
        title: '❌ Помилка',
        description: 'Виберіть дати видачі та повернення',
        variant: 'destructive',
      })
      return
    }
    
    const validItems = items.filter(i => i.name && i.price > 0)
    if (validItems.length === 0) {
      toast({
        title: '❌ Помилка',
        description: 'Додайте хоча б одну позицію',
        variant: 'destructive',
      })
      return
    }
    
    setSaving(true)
    
    try {
      const days = rentalDays || 1
      
      // Розрахунок сум
      const totalRentAmount = validItems.reduce((sum, i) => 
        sum + ((i.price || 0) * (i.qty || 1) * days), 0)
      const totalDepositAmount = validItems.reduce((sum, i) => {
        const damageCost = i.damage_cost || (i.price || 0) * 2
        return sum + (damageCost * 0.5 * (i.qty || 1))
      }, 0)
      
      const orderData = {
        customer_name: clientName,
        customer_phone: clientPhone,
        customer_email: clientEmail || undefined,
        rental_start_date: issueDate,
        rental_end_date: returnDate,
        notes: notes || undefined,
        total_amount: totalRentAmount,
        deposit_amount: totalDepositAmount,
        items: validItems.map(i => {
          const totalRental = (i.price || 0) * (i.qty || 1) * days
          const damageCost = i.damage_cost || (i.price || 0) * 2
          const depositPerItem = damageCost * 0.5
          const totalDeposit = depositPerItem * (i.qty || 1)
          
          return {
            inventory_id: i.sku || `TEMP-${Date.now()}`,
            name: i.name,
            article: i.sku || 'CUSTOM',
            quantity: i.qty || 1,
            price_per_day: i.price || 0,
            deposit: depositPerItem,
            total_rental: totalRental,
            total_deposit: totalDeposit
          }
        })
      }
      
      const response = await axios.post(`${BACKEND_URL}/api/orders`, orderData)
      
      toast({
        title: '✅ Успіх',
        description: `Замовлення #${response.data.order_number} створено`,
      })
      
      setTimeout(() => navigate('/'), 1000)
    } catch (error) {
      console.error('Error creating order:', error)
      const errorMsg = error.response?.data?.detail || 'Не вдалося створити замовлення'
      toast({
        title: '❌ Помилка',
        description: errorMsg,
        variant: 'destructive',
      })
    } finally {
      setSaving(false)
    }
  }
  
  // === РЕНДЕР ===
  return (
    <OrderWorkspaceLayout
      orderId="new"
      orderNumber="НОВЕ"
      status="DRAFT"
      issueDate={issueDate}
      returnDate={returnDate}
      headerTitle="Нове замовлення"
      backUrl="/manager"
      loading={false}
      
      // Left Rail
      leftRail={
        <>
          <LeftRailClient
            name={clientName || 'Новий клієнт'}
            phone={clientPhone}
            email={clientEmail}
            tier="new"
          />
          <LeftRailFinance
            orderId={null}
            rentAmount={calculations.rentAfterDiscount}
            depositAmount={calculations.estimatedDeposit}
            discountPercent={discount}
            discountAmount={calculations.totalDiscount}
          />
          <LeftRailTimeline orderId={null} events={events} />
          
          {/* Додаткова панель: Доставка */}
          <ZoneDeliverySetup
            deliveryType={deliveryType}
            address={deliveryAddress}
            instructions={deliveryInstructions}
            onUpdate={handleDeliveryUpdate}
          />
        </>
      }
      
      // Footer
      onPrimaryAction={handleCreateOrder}
      primaryLabel="Створити замовлення"
      primaryDisabled={saving || !clientName || !clientPhone || !issueDate || !returnDate}
      primaryDisabledReason={!clientName ? 'Вкажіть клієнта' : !issueDate ? 'Вкажіть дати' : ''}
      onSave={() => toast({ title: 'Чернетка збережена' })}
      saving={saving}
      footerActions={[
        { label: '📄 Попередній перегляд', onClick: () => {} }
      ]}
    >
      {/* === WORKSPACE ZONES === */}
      
      {/* Клієнт */}
      <ZoneClientForm
        clientName={clientName}
        clientPhone={clientPhone}
        clientEmail={clientEmail}
        clientType={clientType}
        managerId={managerId}
        managerName={managerName}
        discount={discount}
        onUpdate={(data) => {
          setClientName(data.name)
          setClientPhone(data.phone)
          setClientEmail(data.email)
          setClientType(data.type)
          setManagerId(data.managerId)
          setManagerName(data.managerName)
          setDiscount(data.discount)
        }}
      />
      
      {/* Дати */}
      <ZonePlanDates
        issueDate={issueDate}
        returnDate={returnDate}
        issueTime={issueTime}
        returnTime={returnTime}
        rentalDays={rentalDays}
        onUpdate={handleDatesUpdate}
      />
      
      {/* Позиції */}
      <ZoneItemsEditor
        items={items}
        inventory={inventory}
        rentalDays={rentalDays}
        onAddItem={handleAddItem}
        onRemoveItem={handleRemoveItem}
        onUpdateItem={handleUpdateItem}
        loadingInventory={loadingInventory}
      />
      
      {/* Нотатки */}
      <ZoneNotes
        notes={notes}
        onUpdateNotes={setNotes}
        title="📝 Коментар до замовлення"
        hint="Текст для складу / менеджера"
      />
    </OrderWorkspaceLayout>
  )
}
