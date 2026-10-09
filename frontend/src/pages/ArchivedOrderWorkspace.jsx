/* eslint-disable */
/**
 * Archived Order Workspace - Перегляд закритого/архівного замовлення
 * Використовує уніфіковану систему Order Workspace
 */

import React, { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useToast } from '../hooks/use-toast'
import axios from 'axios'

import {
  OrderWorkspaceLayout,
  LeftRailClient,
  LeftRailFinance,
  LeftRailTimeline,
  InternalNotesChat,
} from '../components/order-workspace'

import {
  ZoneItemsList,
  ZoneOrderHistory,
  ZoneFinanceHistory,
  ZoneNotes,
  ZoneDocuments,
} from '../components/order-workspace/zones'
// FinanceStatusCard тепер тільки в LeftRailFinance

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''

export default function ArchivedOrderWorkspace() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { toast } = useToast()
  
  // === СТАН ===
  const [loading, setLoading] = useState(true)
  const [order, setOrder] = useState(null)
  const [items, setItems] = useState([])
  
  // Клієнт
  const [clientName, setClientName] = useState('')
  const [clientPhone, setClientPhone] = useState('')
  const [clientEmail, setClientEmail] = useState('')
  
  // Дати
  const [issueDate, setIssueDate] = useState('')
  const [returnDate, setReturnDate] = useState('')
  
  // Фінанси
  const [totalRent, setTotalRent] = useState(0)
  const [totalDeposit, setTotalDeposit] = useState(0)
  const [discount, setDiscount] = useState(0)
  
  // Історія
  const [lifecycle, setLifecycle] = useState([])
  const [financeHistory, setFinanceHistory] = useState([])
  
  // Нотатки
  const [notes, setNotes] = useState('')

  // === ЗАВАНТАЖЕННЯ ===
  useEffect(() => {
    if (!id) return
    loadOrder()
  }, [id])

  const loadOrder = async () => {
    try {
      setLoading(true)
      
      // Завантажуємо замовлення
      let orderData
      try {
        const res = await axios.get(`${BACKEND_URL}/api/decor-orders/${id}`)
        orderData = res.data
      } catch {
        const res = await axios.get(`${BACKEND_URL}/api/orders/${id}`)
        orderData = res.data
      }
      
      setOrder(orderData)
      
      // Клієнт
      setClientName(orderData.client_name || orderData.customer_name || '')
      setClientPhone(orderData.client_phone || orderData.telephone || '')
      setClientEmail(orderData.client_email || orderData.email || '')
      
      // Дати
      setIssueDate(orderData.issue_date || orderData.rental_start_date || orderData.rent_date || '')
      setReturnDate(orderData.return_date || orderData.rental_end_date || orderData.rent_return_date || '')
      
      // Фінанси
      setTotalRent(parseFloat(orderData.total_rental || orderData.total || 0))
      setTotalDeposit(parseFloat(orderData.total_deposit || orderData.deposit_held || 0))
      setDiscount(parseFloat(orderData.discount || orderData.discount_amount || 0))
      
      // Нотатки
      setNotes(orderData.manager_comment || orderData.notes || '')
      
      // Товари
      const itemsData = orderData.items || []
      const transformedItems = itemsData.map((p, idx) => ({
        id: p.id || p.order_product_id || p.inventory_id || idx,
        inventory_id: p.inventory_id || p.product_id || p.id,
        sku: p.article || p.sku || p.model || '',
        name: p.name || p.product_name || '',
        image: p.image || p.photo || '',
        quantity: parseInt(p.quantity || p.qty) || 0,
        price_per_day: parseFloat(p.price_per_day || p.rent_price || 0),
        deposit: parseFloat(p.deposit || p.damage_cost || 0),
        subtotal: parseFloat(p.subtotal || 0)
      }))
      
      setItems(transformedItems)
      
      // Завантажуємо історію
      const orderId = orderData.order_id || parseInt(id)
      
      try {
        const lifecycleRes = await axios.get(`${BACKEND_URL}/api/orders/${orderId}/lifecycle`)
        setLifecycle(lifecycleRes.data || [])
      } catch {
        setLifecycle([])
      }
      
      try {
        const financeRes = await axios.get(`${BACKEND_URL}/api/manager/finance/ledger?order_id=${orderId}`)
        setFinanceHistory(financeRes.data || [])
      } catch {
        setFinanceHistory([])
      }
      
    } catch (err) {
      console.error('[ArchivedOrderWorkspace] Error loading:', err)
      toast({
        title: '❌ Помилка',
        description: 'Не вдалося завантажити замовлення',
        variant: 'destructive',
      })
    } finally {
      setLoading(false)
    }
  }

  // === ДІЇ ===
  const handleUnarchive = async () => {
    if (!window.confirm('Розархівувати це замовлення?')) return
    
    try {
      await axios.post(`${BACKEND_URL}/api/decor-orders/${id}/unarchive`)
      toast({ title: '✅ Успіх', description: 'Замовлення розархівовано' })
      navigate('/manager')
    } catch (err) {
      toast({ title: '❌ Помилка', description: 'Не вдалося розархівувати', variant: 'destructive' })
    }
  }

  const handleExportPDF = () => {
    window.open(`${BACKEND_URL}/api/pdf/invoice/${order?.order_id || id}`, '_blank')
  }

  // === РОЗРАХУНКИ ===
  const rentalDays = useMemo(() => {
    if (!issueDate || !returnDate) return 1
    const start = new Date(issueDate)
    const end = new Date(returnDate)
    const diff = Math.ceil((end - start) / (1000 * 60 * 60 * 24))
    return Math.max(1, diff)
  }, [issueDate, returnDate])

  const statusLabel = useMemo(() => {
    const status = order?.status
    const labels = {
      'completed': '✓ Завершено',
      'archived': '📂 Архівовано',
      'cancelled': '❌ Скасовано',
      'returned': '↩️ Повернуто'
    }
    return labels[status] || status
  }, [order?.status])

  // Timeline для LeftRail
  const timelineEvents = useMemo(() => {
    return lifecycle.map(evt => ({
      text: evt.notes || evt.stage,
      at: evt.created_at,
      tone: evt.stage === 'completed' || evt.stage === 'returned' ? 'green' : 'blue',
      user: evt.created_by
    }))
  }, [lifecycle])

  return (
    <OrderWorkspaceLayout
      orderId={order?.order_id || id}
      orderNumber={order?.order_number || `#${id}`}
      status="CLOSED"
      issueDate={issueDate}
      returnDate={returnDate}
      createdAt={order?.created_at}
      headerTitle={`Архів: ${order?.order_number || `#${id}`}`}
      backUrl="/orders/archive"
      loading={loading}
      
      // Left Rail
      leftRail={
        <>
          <LeftRailClient
            name={clientName}
            phone={clientPhone}
            email={clientEmail}
            tier="regular"
          />
          <LeftRailFinance
            orderId={order?.order_id}
            rentAmount={totalRent}
            depositAmount={totalDeposit}
          />
          <LeftRailTimeline orderId={order?.order_id} events={timelineEvents} />
        </>
      }
      
      // Footer
      onPrimaryAction={null}
      primaryLabel={null}
      showSave={false}
      footerActions={[
        { label: '📄 Експорт PDF', onClick: handleExportPDF },
        { label: '↩️ Розархівувати', onClick: handleUnarchive },
      ]}
      footerChildren={
        <div className="text-sm text-slate-600">
          Статус: <b>{statusLabel}</b> · 
          Позицій: <b>{items.length}</b> · 
          Днів оренди: <b>{rentalDays}</b>
        </div>
      }
    >
      {/* === WORKSPACE ZONES === */}
      
      {/* Товари (read-only) */}
      <ZoneItemsList
        items={items}
        showPrices={true}
        showImages={true}
        canEdit={false}
        title="📦 Товари замовлення"
        hint={`${items.length} позицій`}
      />
      
      {/* Історія статусів */}
      <ZoneOrderHistory
        events={lifecycle}
        title="🕐 Історія статусів"
        hint="Хронологія змін замовлення"
      />
      
      {/* Фінансова історія */}
      <ZoneFinanceHistory
        transactions={financeHistory}
        title="💰 Фінансова історія"
        hint="Усі платежі та транзакції"
      />
      
      {/* Документи (архів) */}
      <ZoneDocuments
        orderId={order?.order_id}
        entityType="order"
        title="Документи"
        hint="Історія документів замовлення"
        readOnly={true}
      />
      
      {/* Внутрішній чат команди (read-only в архіві) */}
      <InternalNotesChat
        orderId={orderId}
        clientComment={order?.customer_comment || order?.client_comment}
        readOnly={true}
      />
    </OrderWorkspaceLayout>
  )
}
