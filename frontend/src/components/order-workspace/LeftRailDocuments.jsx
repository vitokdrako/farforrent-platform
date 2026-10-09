/* eslint-disable */
import React, { useState, useEffect } from 'react'
import { FileText, Printer, Download, Mail, Eye, ChevronDown, ChevronUp, RefreshCw, History, Clock, Receipt } from 'lucide-react'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''

/**
 * LeftRailDocuments - Документи з версіонуванням
 * 
 * Нова логіка:
 * - "Перегляд" - показує ОСТАННІЙ згенерований документ
 * - "Генерувати" - створює НОВУ версію документа
 * - "Історія" - показує всі версії
 * - Рахунки - через випадаючий список з вибором типу
 */

// Типи рахунків тепер завантажуються з бекенду динамічно

// Документи по статусах замовлення
const DOCS_BY_STATUS = {
  'pending': [
    { type: 'estimate', name: 'Кошторис', icon: '📋', emailRequired: true },
    { type: 'invoice_offer', name: 'Рахунок-оферта', icon: '📄', emailRequired: true },
  ],
  'awaiting_customer': [
    { type: 'estimate', name: 'Кошторис', icon: '📋', emailRequired: true },
    { type: 'invoice_offer', name: 'Рахунок-оферта', icon: '📄', emailRequired: true },
  ],
  'draft': [
    { type: 'estimate', name: 'Кошторис', icon: '📋', emailRequired: true },
    { type: 'invoice_offer', name: 'Рахунок-оферта', icon: '📄', emailRequired: true },
  ],
  'confirmed': [
    { type: 'estimate', name: 'Кошторис', icon: '📋', emailRequired: true },
    { type: 'invoice_offer', name: 'Рахунок-оферта', icon: '📄', emailRequired: true },
  ],
  'processing': [
    { type: 'estimate', name: 'Кошторис', icon: '📋', emailRequired: true },
    { type: 'invoice_offer', name: 'Рахунок-оферта', icon: '📄', emailRequired: true },
    { type: 'picking_list', name: 'Лист комплектації', icon: '📦', printRequired: true, internal: true },
  ],
  'ready_for_issue': [
    { type: 'estimate', name: 'Кошторис', icon: '📋', emailRequired: true },
    { type: 'issue_act', name: 'Акт передачі', icon: '📤', printRequired: true, critical: true, emailRequired: true },
  ],
  'issued': [
    { type: 'issue_act', name: 'Акт передачі', icon: '📤', emailRequired: true },
  ],
  'on_rent': [
    { type: 'issue_act', name: 'Акт передачі', icon: '📤', emailRequired: true },
  ],
  'returning': [
    { type: 'return_act', name: 'Акт приймання', icon: '📥', printRequired: true, critical: true, emailRequired: true },
    { type: 'settlement_act', name: 'Акт взаєморозрахунків', icon: '📊', printRequired: true, emailRequired: true, settlement: true },
  ],
  'returned': [
    { type: 'return_act', name: 'Акт приймання', icon: '📥', printRequired: true, emailRequired: true },
    { type: 'damage_report', name: 'Акт пошкоджень', icon: '⚠️', emailRequired: true },
    { type: 'settlement_act', name: 'Акт взаєморозрахунків', icon: '📊', printRequired: true, emailRequired: true, settlement: true },
  ],
  'completed': [
    { type: 'return_act', name: 'Акт приймання', icon: '📥', emailRequired: true },
    { type: 'deposit_refund_act', name: 'Акт поверн. застави', icon: '✅', emailRequired: true },
    { type: 'settlement_act', name: 'Акт взаєморозрахунків', icon: '📊', printRequired: true, emailRequired: true, settlement: true },
  ],
  'cancelled': [],
}

// Документи які потребують issueCardId
const ISSUE_CARD_DOCS = ['issue_act', 'picking_list', 'issue_checklist']

export default function LeftRailDocuments({ 
  orderId, 
  orderNumber,
  orderStatus = 'pending',
  issueCardId = null,
  customerEmail = '',
  onDocumentGenerated = () => {},
  requisitorMode = false,
}) {
  const [expanded, setExpanded] = useState(true)
  const [generating, setGenerating] = useState(null)
  const [sending, setSending] = useState(null)
  const [error, setError] = useState(null)
  const [docVersions, setDocVersions] = useState({}) // { docType: { exists, version, id, ... } }
  const [historyModal, setHistoryModal] = useState(null) // docType для показу історії
  const [historyData, setHistoryData] = useState([])
  const [invoiceDropdownOpen, setInvoiceDropdownOpen] = useState(false)
  const [generatingInvoice, setGeneratingInvoice] = useState(false)
  const [availableInvoices, setAvailableInvoices] = useState({ has_payer: false, payer: null, available_types: [] })
  const getToken = () => localStorage.getItem('token')

  // ОПТИМІЗАЦІЯ Phase 2: Використовуємо batch endpoint замість N окремих запитів
  const loadDocumentVersions = async () => {
    const docs = DOCS_BY_STATUS[orderStatus] || []
    if (docs.length === 0) {
      setDocVersions({})
      return
    }
    
    // Групуємо документи за entity_type для batch запитів
    const orderDocs = docs.filter(d => !ISSUE_CARD_DOCS.includes(d.type)).map(d => d.type)
    const issueDocs = docs.filter(d => ISSUE_CARD_DOCS.includes(d.type)).map(d => d.type)
    
    const batchPromises = []
    
    // Batch для order документів
    if (orderDocs.length > 0 && orderId) {
      batchPromises.push(
        fetch(`${BACKEND_URL}/api/documents/latest-batch`, {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getToken()}` 
          },
          body: JSON.stringify({
            entity_type: 'order',
            entity_id: String(orderId),
            doc_types: orderDocs
          })
        }).then(r => r.json()).catch(() => ({ documents: {} }))
      )
    }
    
    // Batch для issue документів
    const effectiveIssueId = issueCardId || orderId
    if (issueDocs.length > 0 && effectiveIssueId) {
      batchPromises.push(
        fetch(`${BACKEND_URL}/api/documents/latest-batch`, {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getToken()}` 
          },
          body: JSON.stringify({
            entity_type: 'issue',
            entity_id: String(effectiveIssueId),
            doc_types: issueDocs
          })
        }).then(r => r.json()).catch(() => ({ documents: {} }))
      )
    }
    
    // Виконуємо batch запити паралельно
    const results = await Promise.all(batchPromises)
    
    // Об'єднуємо результати
    const versions = {}
    results.forEach(result => {
      if (result?.documents) {
        Object.assign(versions, result.documents)
      }
    })
    
    setDocVersions(versions)
  }

  useEffect(() => {
    if (orderId && orderStatus) {
      loadDocumentVersions()
      // Load available invoice types based on payer profile
      if (!requisitorMode && ['confirmed', 'processing', 'ready_for_issue', 'issued', 'on_rent', 'completed'].includes(orderStatus)) {
        fetch(`${BACKEND_URL}/api/documents/available-invoices/${orderId}`, {
          headers: { 'Authorization': `Bearer ${getToken()}` }
        })
          .then(r => r.json())
          .then(data => setAvailableInvoices(data))
          .catch(() => {})
      }
    }
  }, [orderId, orderStatus, issueCardId])

  // Переглянути ОСТАННІЙ документ (без генерації)
  const viewLastDocument = async (docType) => {
    // Для Кошторису - завжди відкриваємо прямий preview
    if (docType === 'estimate') {
      window.open(`${BACKEND_URL}/api/documents/estimate/${orderId}/preview`, '_blank')
      return
    }
    
    // Для Рахунку-оферти - завжди відкриваємо прямий preview
    if (docType === 'invoice_offer') {
      window.open(`${BACKEND_URL}/api/documents/invoice-offer/${orderId}/preview`, '_blank')
      return
    }
    
    // Для Акту передачі - завжди відкриваємо прямий preview
    if (docType === 'issue_act') {
      window.open(`${BACKEND_URL}/api/documents/issue-act/${orderId}/preview?executor_type=fop`, '_blank')
      return
    }
    
    // Для Листа комплектації - завжди відкриваємо прямий preview
    if (docType === 'picking_list') {
      window.open(`${BACKEND_URL}/api/documents/picking-list/${orderId}/preview`, '_blank')
      return
    }
    
    // Для Акту взаєморозрахунків - відкриваємо прямо
    if (docType === 'settlement_act') {
      window.open(`${BACKEND_URL}/api/documents/settlement-act/${orderId}/preview`, '_blank')
      return
    }
    
    const docInfo = docVersions[docType]
    
    if (!docInfo?.exists) {
      alert('Документ ще не згенеровано. Натисніть "Генерувати" для створення.')
      return
    }
    
    // Відкрити preview
    const win = window.open('', '_blank')
    if (win) {
      win.document.write(docInfo.html_content)
      win.document.close()
    } else {
      const blob = new Blob([docInfo.html_content], { type: 'text/html' })
      const url = URL.createObjectURL(blob)
      window.open(url, '_blank')
    }
  }

  // Генерувати НОВИЙ документ
  // ОПТИМІЗАЦІЯ P1.2: Повертає data для використання в sendEmail (fix race condition)
  const generateNewDocument = async (docType, openPreview = true) => {
    setGenerating(docType)
    setError(null)
    
    // Для Кошторису - використовуємо прямий endpoint
    if (docType === 'estimate') {
      try {
        if (openPreview) {
          window.open(`${BACKEND_URL}/api/documents/estimate/${orderId}/preview`, '_blank')
        }
        setGenerating(null)
        return { id: null, doc_type: 'estimate', entity_id: orderId }
      } catch (err) {
        setError(err.message)
        setGenerating(null)
        return null
      }
    }
    
    // Для Рахунку-оферти - використовуємо прямий endpoint
    if (docType === 'invoice_offer') {
      try {
        if (openPreview) {
          window.open(`${BACKEND_URL}/api/documents/invoice-offer/${orderId}/preview`, '_blank')
        }
        setGenerating(null)
        return { id: null, doc_type: 'invoice_offer', entity_id: orderId }
      } catch (err) {
        setError(err.message)
        setGenerating(null)
        return null
      }
    }
    
    // Для Акту передачі - використовуємо прямий endpoint
    if (docType === 'issue_act') {
      try {
        if (openPreview) {
          window.open(`${BACKEND_URL}/api/documents/issue-act/${orderId}/preview?executor_type=fop`, '_blank')
        }
        setGenerating(null)
        return { id: null, doc_type: 'issue_act', entity_id: orderId }
      } catch (err) {
        setError(err.message)
        setGenerating(null)
        return null
      }
    }
    
    // Для Листа комплектації - використовуємо прямий endpoint
    if (docType === 'picking_list') {
      try {
        if (openPreview) {
          window.open(`${BACKEND_URL}/api/documents/picking-list/${orderId}/preview`, '_blank')
        }
        setGenerating(null)
        return { id: null, doc_type: 'picking_list', entity_id: orderId }
      } catch (err) {
        setError(err.message)
        setGenerating(null)
        return null
      }
    }
    
    // Для Акту взаєморозрахунків - відкриваємо прямо
    if (docType === 'settlement_act') {
      setGenerating(null)
      window.open(`${BACKEND_URL}/api/documents/settlement-act/${orderId}/preview`, '_blank')
      return null
    }
    
    const entityType = ISSUE_CARD_DOCS.includes(docType) ? 'issue' : 'order'
    const entityId = ISSUE_CARD_DOCS.includes(docType) ? (issueCardId || orderId) : orderId
    
    if (!entityId) {
      setError('ID не знайдено')
      setGenerating(null)
      return null  // Повертаємо null замість undefined
    }
    
    try {
      const response = await fetch(`${BACKEND_URL}/api/documents/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getToken()}`
        },
        body: JSON.stringify({
          doc_type: docType,
          entity_id: String(entityId),
          format: 'html',
          options: {}
        })
      })
      
      if (!response.ok) {
        throw new Error(`Помилка: ${response.status}`)
      }
      
      const data = await response.json()
      
      // Оновити версію в state
      await loadDocumentVersions()
      
      // Показати новий документ (тільки якщо openPreview = true)
      if (openPreview && data.html_content) {
        const win = window.open('', '_blank')
        if (win) {
          win.document.write(data.html_content)
          win.document.close()
        }
      }
      
      onDocumentGenerated(docType, data)
      
      // ОПТИМІЗАЦІЯ P1.2: Повертаємо data для використання в sendEmail
      return data
      
    } catch (err) {
      console.error('Document error:', err)
      setError(err.message)
      return null
    } finally {
      setGenerating(null)
    }
  }

  // Друк останнього документа
  const printDocument = async (docType) => {
    const docInfo = docVersions[docType]
    
    if (!docInfo?.exists) {
      // Якщо немає - генеруємо
      await generateNewDocument(docType)
      return
    }
    
    const printWin = window.open('', '_blank')
    if (printWin) {
      printWin.document.write(`
        <!DOCTYPE html>
        <html><head><title>Друк</title>
        <style>@media print { @page { size: A4; margin: 15mm; } }</style>
        </head><body>${docInfo.html_content}
        <script>window.onload=function(){window.print();}</script>
        </body></html>
      `)
      printWin.document.close()
    }
  }

  // Завантажити історію версій
  const loadHistory = async (docType) => {
    const entityType = ISSUE_CARD_DOCS.includes(docType) ? 'issue' : 'order'
    const entityId = ISSUE_CARD_DOCS.includes(docType) ? (issueCardId || orderId) : orderId
    
    try {
      const res = await fetch(`${BACKEND_URL}/api/documents/history/${entityType}/${entityId}/${docType}`, {
        headers: { 'Authorization': `Bearer ${getToken()}` }
      })
      if (res.ok) {
        const data = await res.json()
        setHistoryData(data.versions || [])
        setHistoryModal(docType)
      }
    } catch (e) {
      console.error('Error loading history:', e)
    }
  }

  // Переглянути конкретну версію
  const viewVersion = async (docId) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/documents/${docId}/preview`, {
        headers: { 'Authorization': `Bearer ${getToken()}` }
      })
      if (res.ok) {
        const html = await res.text()
        const win = window.open('', '_blank')
        if (win) {
          win.document.write(html)
          win.document.close()
        }
      }
    } catch (e) {
      console.error('Error viewing version:', e)
    }
  }

  // Email - ОПТИМІЗОВАНО P1.2: Виправлено race condition
  const sendEmail = async (docType) => {
    if (!customerEmail) {
      alert('Email клієнта не вказано')
      return
    }
    
    setSending(docType)
    setError(null)
    
    try {
      // Для Кошторису - використовуємо спеціальний endpoint
      if (docType === 'estimate') {
        const emailResponse = await fetch(`${BACKEND_URL}/api/documents/estimate/${orderId}/send-email`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getToken()}`
          },
          body: JSON.stringify({
            recipient_email: customerEmail,
            recipient_name: ''
          })
        })
        
        if (!emailResponse.ok) {
          const errData = await emailResponse.json()
          throw new Error(errData.detail || 'Помилка відправки email')
        }
        
        const emailResult = await emailResponse.json()
        alert(`✅ ${emailResult.message}`)
        setSending(null)
        return
      }
      
      let docInfo = docVersions[docType]
      let generatedData = null
      
      // Якщо документ не існує - спочатку генеруємо
      // ОПТИМІЗАЦІЯ P1.2: Використовуємо повернені дані напряму, а не state
      if (!docInfo?.exists) {
        generatedData = await generateNewDocument(docType, false)  // false = не відкривати preview
        if (!generatedData) {
          alert('❌ Не вдалося згенерувати документ')
          setSending(null)
          return
        }
      }
      
      // ОПТИМІЗАЦІЯ P1.2: Використовуємо ID з generatedData якщо щойно згенерували
      // Це вирішує race condition коли state ще не оновився
      const documentId = generatedData?.id || docInfo?.id
      
      if (!documentId) {
        // Якщо немає збереженого документа - використовуємо новий endpoint
        const entityType = ISSUE_CARD_DOCS.includes(docType) ? 'issue' : 'order'
        const entityId = ISSUE_CARD_DOCS.includes(docType) ? (issueCardId || orderId) : orderId
        
        const emailResponse = await fetch(`${BACKEND_URL}/api/email/send-document-by-type`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getToken()}`
          },
          body: JSON.stringify({
            doc_type: docType,
            entity_id: String(entityId),
            entity_type: entityType,
            recipient_email: customerEmail,
            recipient_name: '',
            order_number: orderNumber
          })
        })
        
        if (!emailResponse.ok) {
          const errData = await emailResponse.json()
          throw new Error(errData.detail || 'Помилка відправки email')
        }
        
        const emailResult = await emailResponse.json()
        alert(`✅ ${emailResult.message}`)
      } else {
        // Відправляємо збережений документ
        const emailResponse = await fetch(`${BACKEND_URL}/api/documents/${documentId}/send-email`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getToken()}`
          },
          body: JSON.stringify({
            email: customerEmail
          })
        })
        
        if (!emailResponse.ok) {
          const errData = await emailResponse.json()
          throw new Error(errData.detail || 'Помилка відправки email')
        }
        
        const emailResult = await emailResponse.json()
        alert(`✅ ${emailResult.message || 'Документ відправлено'}`)
      }
      
    } catch (err) {
      console.error('[LeftRailDocuments] Email error:', err)
      setError(err.message)
      alert(`❌ Помилка: ${err.message}`)
    } finally {
      setSending(null)
    }
  }

  // Генерація рахунку/акту за типом (нові ендпоінти)
  const generateInvoice = async (invoiceType) => {
    const inv = availableInvoices.available_types.find(t => t.value === invoiceType)
    if (!inv || !orderId) return
    
    setGeneratingInvoice(true)
    setInvoiceDropdownOpen(false)
    setError(null)
    
    try {
      const payerId = availableInvoices.payer?.id
      const url = `${BACKEND_URL}/api/documents/${inv.endpoint}/${orderId}/preview?executor_type=${inv.executor_type}${payerId ? `&payer_id=${payerId}` : ''}`
      window.open(url, '_blank')
      onDocumentGenerated()
    } catch (e) {
      setError(e.message)
    } finally {
      setGeneratingInvoice(false)
    }
  }

  // Чи показувати блок рахунків — тепер перевіряємо наявність платника
  const showInvoiceSection = !requisitorMode && ['confirmed', 'processing', 'ready_for_issue', 'issued', 'on_rent', 'completed'].includes(orderStatus)

  // Фільтрація документів для режиму реквізитора
  const REQUISITOR_DOCS = {
    'processing': ['picking_list'],
    'ready_for_issue': ['issue_act'],
  }
  
  let availableDocs = DOCS_BY_STATUS[orderStatus] || []
  if (requisitorMode && REQUISITOR_DOCS[orderStatus]) {
    const allowed = REQUISITOR_DOCS[orderStatus]
    availableDocs = availableDocs.filter(d => allowed.includes(d.type))
  }
  
  if (availableDocs.length === 0) {
    return null
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-slate-600" />
          <span className="font-medium text-slate-800">Документи</span>
          <span className="text-xs text-slate-500">({availableDocs.length})</span>
        </div>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-slate-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-slate-400" />
        )}
      </button>
      
      {/* Content */}
      {expanded && (
        <div className="px-4 pb-4 space-y-2">
          {error && (
            <div className="p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
              {error}
            </div>
          )}
          
          {availableDocs.map((doc) => {
            const versionInfo = docVersions[doc.type]
            const hasVersion = versionInfo?.exists
            
            // invoice_offer тепер показується як прямий документ (без секції рахунків)
            
            return (
              <div 
                key={doc.type}
                className={`
                  p-3 rounded-xl border transition-all
                  ${doc.critical ? 'border-amber-300 bg-amber-50' : 'border-slate-200 bg-slate-50'}
                `}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span>{doc.icon}</span>
                    <span className="text-sm font-medium">{doc.name}</span>
                  </div>
                  {doc.critical && (
                    <span className="text-xs text-amber-600 font-medium">обов'язк.</span>
                  )}
                </div>
                
                {/* Версія - для документів на льоту завжди показуємо "Актуальний" */}
                {['estimate', 'invoice_offer', 'issue_act', 'picking_list', 'settlement_act'].includes(doc.type) && (
                  <div className="flex items-center gap-2 text-xs text-green-600 mb-2">
                    <span>✓ Актуальний</span>
                    <span className="text-slate-400">•</span>
                    <span className="text-slate-500">Генерується на льоту</span>
                  </div>
                )}
                
                {!['estimate', 'invoice_offer', 'issue_act', 'picking_list', 'settlement_act'].includes(doc.type) && hasVersion && (
                  <div className="flex items-center gap-2 text-xs text-green-600 mb-2">
                    <span>✓ v{versionInfo.version}</span>
                    <span className="text-slate-400">•</span>
                    <span className="text-slate-500">{versionInfo.doc_number}</span>
                  </div>
                )}
                
                {!['estimate', 'invoice_offer', 'issue_act', 'picking_list', 'settlement_act'].includes(doc.type) && !hasVersion && (
                  <div className="text-xs text-slate-400 mb-2">
                    Документ ще не згенеровано
                  </div>
                )}
                
                <div className="flex flex-wrap gap-1">
                  {/* Перегляд - для документів на льоту завжди активний */}
                  <button
                    onClick={() => viewLastDocument(doc.type)}
                    disabled={!['estimate', 'invoice_offer', 'issue_act', 'picking_list', 'settlement_act'].includes(doc.type) && !hasVersion}
                    className={`
                      flex items-center gap-1 px-2 py-1 text-xs rounded
                      ${['estimate', 'invoice_offer', 'issue_act', 'picking_list', 'settlement_act'].includes(doc.type) || hasVersion 
                        ? 'bg-white border hover:bg-slate-100' 
                        : 'bg-slate-100 text-slate-400 cursor-not-allowed'}
                    `}
                    title={['estimate', 'invoice_offer', 'issue_act', 'picking_list', 'settlement_act'].includes(doc.type) ? 'Переглянути документ' : (hasVersion ? 'Переглянути останню версію' : 'Спочатку згенеруйте документ')}
                  >
                    <Eye className="w-3 h-3" />
                    Перегляд
                  </button>
                  
                  {/* Генерувати - для Кошторису теж "Генерувати" */}
                  <button
                    onClick={() => generateNewDocument(doc.type)}
                    disabled={generating === doc.type}
                    className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 disabled:opacity-50"
                    title={doc.type === 'estimate' ? 'Генерувати актуальний кошторис' : 'Генерувати нову версію'}
                  >
                    <RefreshCw className={`w-3 h-3 ${generating === doc.type ? 'animate-spin' : ''}`} />
                    {generating === doc.type ? '...' : 'Генерувати'}
                  </button>
                  
                  {/* Друк */}
                  {doc.printRequired && (
                    <button
                      onClick={() => printDocument(doc.type)}
                      disabled={generating === doc.type}
                      className="flex items-center gap-1 px-2 py-1 text-xs bg-slate-100 rounded hover:bg-slate-200 disabled:opacity-50"
                      title="Друк"
                    >
                      <Printer className="w-3 h-3" />
                    </button>
                  )}
                  
                  {/* Історія (якщо є хоча б 1 версія) */}
                  {hasVersion && (
                    <button
                      onClick={() => loadHistory(doc.type)}
                      className="flex items-center gap-1 px-2 py-1 text-xs bg-white border rounded hover:bg-slate-100"
                      title="Історія версій"
                    >
                      <History className="w-3 h-3" />
                    </button>
                  )}
                  
                  {/* Email */}
                  {doc.emailRequired && (
                    <button
                      onClick={() => sendEmail(doc.type)}
                      disabled={sending === doc.type}
                      className="flex items-center gap-1 px-2 py-1 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200 disabled:opacity-50"
                      title="Надіслати email"
                    >
                      <Mail className="w-3 h-3" />
                      {sending === doc.type ? '...' : ''}
                    </button>
                  )}
                </div>
              </div>
            )
          })}
          
          {/* === СЕКЦІЯ РАХУНКІВ === */}
          {showInvoiceSection && (
            <div className="mt-3 pt-3 border-t border-slate-200" data-testid="invoice-section">
              <div className="p-3 rounded-xl border border-amber-200 bg-amber-50/50">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Receipt className="w-4 h-4 text-amber-600" />
                    <span className="text-sm font-medium text-slate-800">Рахунки</span>
                  </div>
                  {availableInvoices.payer && (
                    <span className="text-xs text-slate-500 truncate max-w-[180px]" title={availableInvoices.payer.display_name}>
                      {availableInvoices.payer.display_name}
                    </span>
                  )}
                </div>
                
                {!availableInvoices.has_payer ? (
                  <div className="text-xs text-slate-500 py-2 text-center">
                    Платника не знайдено. Додайте платника в картці клієнта.
                  </div>
                ) : (
                  <div className="relative">
                    <button
                      onClick={() => setInvoiceDropdownOpen(!invoiceDropdownOpen)}
                      disabled={generatingInvoice}
                      className="w-full flex items-center justify-between px-3 py-2 text-xs bg-white border border-amber-300 rounded-lg hover:bg-amber-50 transition-colors"
                      data-testid="invoice-dropdown-btn"
                    >
                      <span className="text-slate-700">
                        {generatingInvoice ? 'Генерую...' : 'Виставити рахунок...'}
                      </span>
                      <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${invoiceDropdownOpen ? 'rotate-180' : ''}`} />
                    </button>
                    
                    {invoiceDropdownOpen && (
                      <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-lg z-30 overflow-hidden" data-testid="invoice-dropdown-list">
                        {availableInvoices.available_types.map(inv => (
                          <button
                            key={inv.value}
                            onClick={() => generateInvoice(inv.value)}
                            className="w-full px-3 py-2.5 text-left text-xs hover:bg-amber-50 transition-colors border-b border-slate-100 last:border-0 flex items-center gap-2"
                            data-testid={`invoice-type-${inv.value}`}
                          >
                            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" />
                            <span className="text-slate-700">{inv.label}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* History Modal */}
      {historyModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setHistoryModal(null)}>
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full mx-4" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b flex items-center justify-between">
              <h3 className="font-semibold">📋 Історія документа</h3>
              <button 
                onClick={() => setHistoryModal(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>
            <div className="p-4 max-h-80 overflow-y-auto">
              {historyData.length === 0 ? (
                <p className="text-slate-500 text-center py-4">Немає версій</p>
              ) : (
                <div className="space-y-2">
                  {historyData.map((ver, i) => (
                    <div 
                      key={ver.id}
                      className={`
                        p-3 rounded-lg border cursor-pointer hover:bg-slate-50
                        ${i === 0 ? 'border-blue-300 bg-blue-50' : 'border-slate-200'}
                      `}
                      onClick={() => viewVersion(ver.id)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">v{ver.version}</span>
                          {i === 0 && (
                            <span className="text-xs bg-blue-500 text-white px-1.5 py-0.5 rounded">Остання</span>
                          )}
                        </div>
                        <span className="text-xs text-slate-500">{ver.doc_number}</span>
                      </div>
                      <div className="flex items-center gap-2 mt-1 text-xs text-slate-500">
                        <Clock className="w-3 h-3" />
                        {new Date(ver.created_at).toLocaleString('uk-UA')}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
