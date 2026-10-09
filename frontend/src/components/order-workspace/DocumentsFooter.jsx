/* eslint-disable */
import React, { useState } from 'react'
import { FileText, Printer, Download, ChevronDown, ChevronUp, AlertCircle, Check } from 'lucide-react'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''

// Повний реєстр документів відповідно до Document Engine
const DOCUMENT_REGISTRY = {
  // Order-based documents
  order: [
    { type: 'invoice_offer', name: 'Рахунок-оферта', icon: '📄', printRequired: false, critical: ['legal', 'finance'] },
    { type: 'contract_rent', name: 'Договір оренди', icon: '📋', printRequired: true, critical: ['legal'] },
    { type: 'delivery_note', name: 'ТТН / Накладна доставки', icon: '🚚', printRequired: true, critical: ['legal', 'operations'], condition: 'delivery' },
    { type: 'rental_extension', name: 'Додаткова угода', icon: '📝', printRequired: false, critical: ['legal', 'finance'] },
    { type: 'return_act', name: 'Акт приймання', icon: '📥', printRequired: true, critical: ['legal'] },
    { type: 'partial_return_act', name: 'Акт часткового повернення', icon: '📦', printRequired: true, critical: ['legal'] },
    { type: 'damage_settlement_act', name: 'Акт утримання із застави', icon: '⚠️', printRequired: true, critical: ['legal', 'finance'] },
    { type: 'deposit_refund_act', name: 'Акт повернення застави', icon: '💰', printRequired: true, critical: ['legal', 'finance'] },
    { type: 'invoice_additional', name: 'Додатковий рахунок', icon: '💵', printRequired: false, critical: ['finance'] },
  ],
  // Issue card documents
  issue: [
    { type: 'issue_act', name: 'Акт передачі', icon: '📤', printRequired: true, critical: ['legal'] },
    { type: 'issue_checklist', name: 'Чеклист видачі', icon: '✅', printRequired: true, critical: ['operations'] },
    { type: 'picking_list', name: 'Лист комплектації', icon: '📦', printRequired: true, critical: ['operations'] },
  ],
  // Damage documents
  damage: [
    { type: 'damage_report', name: 'Акт фіксації пошкоджень', icon: '🔍', printRequired: false, critical: ['legal'] },
    { type: 'damage_invoice', name: 'Рахунок на пошкодження', icon: '💳', printRequired: false, critical: ['finance'] },
  ],
  // Vendor documents
  vendor: [
    { type: 'vendor_work_act', name: 'Акт виконаних робіт', icon: '🔧', printRequired: false, critical: ['finance'] },
  ]
}

// Стадії замовлення та відповідні документи
const STAGE_DOCUMENTS = {
  'pending': ['invoice_offer'],
  'awaiting_customer': ['invoice_offer', 'contract_rent'],
  'confirmed': ['invoice_offer', 'contract_rent'],
  'processing': ['invoice_offer', 'contract_rent', 'picking_list', 'issue_checklist'],
  'ready_for_issue': ['invoice_offer', 'contract_rent', 'picking_list', 'issue_checklist', 'issue_act', 'delivery_note'],
  'issued': ['invoice_offer', 'contract_rent', 'issue_act', 'delivery_note'],
  'on_rent': ['invoice_offer', 'contract_rent', 'issue_act', 'rental_extension'],
  'returned': ['return_act', 'damage_report', 'damage_settlement_act'],
  'completed': ['return_act', 'damage_settlement_act', 'deposit_refund_act', 'invoice_additional'],
  'cancelled': ['invoice_offer'],
}

export default function DocumentsFooter({ 
  orderId, 
  orderNumber,
  orderStatus = 'pending',
  issueCardId = null,
  deliveryType = 'pickup',
  onDocumentGenerated = () => {}
}) {
  const [expanded, setExpanded] = useState(false)
  const [generating, setGenerating] = useState(null)
  const [error, setError] = useState(null)
  const [generatedDocs, setGeneratedDocs] = useState({})

  const getToken = () => localStorage.getItem('token')

  // Генерація документа
  const generateDocument = async (docType, format = 'html') => {
    setGenerating(docType)
    setError(null)
    
    try {
      const entityType = DOCUMENT_REGISTRY.issue.some(d => d.type === docType) ? 'issue' : 'order'
      const entityId = entityType === 'issue' && issueCardId ? issueCardId : orderId
      
      const response = await fetch(`${BACKEND_URL}/api/documents/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getToken()}`
        },
        body: JSON.stringify({
          doc_type: docType,
          entity_id: String(entityId),
          format: format,
          options: {}
        })
      })
      
      if (!response.ok) {
        throw new Error(`Помилка генерації: ${response.status}`)
      }
      
      const data = await response.json()
      
      // Відкрити документ
      if (format === 'html' && data.html_content) {
        const newWindow = window.open('', '_blank')
        newWindow.document.write(data.html_content)
        newWindow.document.close()
      } else if (format === 'pdf' && data.download_url) {
        window.open(`${BACKEND_URL}${data.download_url}`, '_blank')
      }
      
      setGeneratedDocs(prev => ({ ...prev, [docType]: true }))
      onDocumentGenerated(docType, data)
      
    } catch (err) {
      console.error('Document generation error:', err)
      setError(err.message)
    } finally {
      setGenerating(null)
    }
  }

  // Друк документа
  const printDocument = async (docType) => {
    setGenerating(docType)
    try {
      const entityType = DOCUMENT_REGISTRY.issue.some(d => d.type === docType) ? 'issue' : 'order'
      const entityId = entityType === 'issue' && issueCardId ? issueCardId : orderId
      
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
      
      if (!response.ok) throw new Error('Помилка генерації')
      
      const data = await response.json()
      
      // Відкрити для друку
      const printWindow = window.open('', '_blank')
      printWindow.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
          <title>Друк - ${docType}</title>
          <style>
            @media print {
              @page { size: A4; margin: 15mm; }
              body { font-family: Arial, sans-serif; }
            }
          </style>
        </head>
        <body>
          ${data.html_content}
          <script>window.onload = function() { window.print(); }</script>
        </body>
        </html>
      `)
      printWindow.document.close()
      
    } catch (err) {
      setError(err.message)
    } finally {
      setGenerating(null)
    }
  }

  // Отримати доступні документи для поточного статусу
  const getAvailableDocuments = () => {
    const availableTypes = STAGE_DOCUMENTS[orderStatus] || ['invoice_offer']
    const allDocs = [...DOCUMENT_REGISTRY.order, ...DOCUMENT_REGISTRY.issue]
    
    return allDocs.filter(doc => {
      // Перевірка за статусом
      if (!availableTypes.includes(doc.type)) return false
      
      // Умова для ТТН - тільки при доставці
      if (doc.condition === 'delivery' && deliveryType === 'pickup') return false
      
      // Для issue документів потрібен issueCardId
      if (DOCUMENT_REGISTRY.issue.some(d => d.type === doc.type) && !issueCardId) return false
      
      return true
    })
  }

  const availableDocs = getAvailableDocuments()
  const criticalDocs = availableDocs.filter(d => d.printRequired)
  
  if (!orderId) return null

  return (
    <div className="border-t border-slate-200 bg-slate-50 mt-4">
      {/* Заголовок футера */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-slate-600" />
          <span className="font-medium text-slate-700">Документи</span>
          <span className="text-sm text-slate-500">({availableDocs.length})</span>
          {criticalDocs.length > 0 && (
            <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">
              {criticalDocs.length} обов'язкових
            </span>
          )}
        </div>
        {expanded ? <ChevronUp className="w-5 h-5 text-slate-400" /> : <ChevronDown className="w-5 h-5 text-slate-400" />}
      </button>
      
      {/* Розгорнутий список документів */}
      {expanded && (
        <div className="px-4 pb-4">
          {error && (
            <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded flex items-center gap-2 text-sm text-red-700">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          )}
          
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {availableDocs.map((doc) => (
              <div 
                key={doc.type}
                className={`
                  p-3 rounded-lg border transition-all
                  ${doc.printRequired ? 'border-amber-300 bg-amber-50' : 'border-slate-200 bg-white'}
                  ${generatedDocs[doc.type] ? 'ring-2 ring-green-400' : ''}
                `}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{doc.icon}</span>
                    <span className="text-sm font-medium text-slate-700">{doc.name}</span>
                  </div>
                  {generatedDocs[doc.type] && (
                    <Check className="w-4 h-4 text-green-500" />
                  )}
                </div>
                
                {doc.printRequired && (
                  <div className="text-xs text-amber-600 mb-2 flex items-center gap-1">
                    <Printer className="w-3 h-3" />
                    Обов'язковий друк
                  </div>
                )}
                
                <div className="flex gap-1">
                  <button
                    onClick={() => generateDocument(doc.type, 'html')}
                    disabled={generating === doc.type}
                    className="flex-1 px-2 py-1.5 text-xs bg-slate-100 hover:bg-slate-200 rounded flex items-center justify-center gap-1 disabled:opacity-50"
                  >
                    <FileText className="w-3 h-3" />
                    {generating === doc.type ? '...' : 'Переглянути'}
                  </button>
                  <button
                    onClick={() => printDocument(doc.type)}
                    disabled={generating === doc.type}
                    className="px-2 py-1.5 text-xs bg-blue-100 hover:bg-blue-200 text-blue-700 rounded flex items-center gap-1 disabled:opacity-50"
                  >
                    <Printer className="w-3 h-3" />
                  </button>
                  <button
                    onClick={() => generateDocument(doc.type, 'pdf')}
                    disabled={generating === doc.type}
                    className="px-2 py-1.5 text-xs bg-green-100 hover:bg-green-200 text-green-700 rounded flex items-center gap-1 disabled:opacity-50"
                  >
                    <Download className="w-3 h-3" />
                  </button>
                </div>
              </div>
            ))}
          </div>
          
          {/* Легенда */}
          <div className="mt-3 pt-3 border-t border-slate-200 flex flex-wrap gap-4 text-xs text-slate-500">
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 bg-amber-50 border border-amber-300 rounded"></span>
              Обов'язковий друк
            </span>
            <span className="flex items-center gap-1">
              <Check className="w-3 h-3 text-green-500" />
              Згенеровано
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
