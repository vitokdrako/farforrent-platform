/* eslint-disable */
import React, { useState, useEffect } from 'react'
import axios from 'axios'
import ZoneCard from '../ZoneCard'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''

/**
 * Zone: Documents - Документи замовлення
 * Генерація та перегляд документів (рахунки, договори, акти)
 */
export default function ZoneDocuments({
  orderId,
  issueCardId,
  entityType = 'order', // 'order' | 'issue' | 'return'
  title = 'Документи',
  hint = 'Генерація та завантаження документів',
  readOnly = false,
  allowedDocTypes = null, // Масив дозволених типів документів (null = всі)
}) {
  const [documents, setDocuments] = useState([])
  const [availableTypes, setAvailableTypes] = useState([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(null)
  const [previewDoc, setPreviewDoc] = useState(null)
  
  // Завантажити документи
  useEffect(() => {
    loadDocuments()
  }, [orderId, issueCardId, entityType])
  
  const getEntityId = () => {
    if (entityType === 'issue' && issueCardId) return issueCardId
    return orderId
  }
  
  const loadDocuments = async () => {
    try {
      setLoading(true)
      const entityId = getEntityId()
      if (!entityId) return
      
      const response = await axios.get(
        `${BACKEND_URL}/api/documents/entity/${entityType}/${entityId}`
      )
      
      setDocuments(response.data.documents || [])
      
      // Фільтруємо типи документів якщо вказано allowedDocTypes
      let types = response.data.available_types || []
      if (allowedDocTypes && allowedDocTypes.length > 0) {
        types = types.filter(t => allowedDocTypes.includes(t.type))
      }
      setAvailableTypes(types)
    } catch (error) {
      console.error('Error loading documents:', error)
    } finally {
      setLoading(false)
    }
  }
  
  // Згенерувати документ
  const handleGenerate = async (docType) => {
    try {
      setGenerating(docType)
      const entityId = getEntityId()
      
      const response = await axios.post(
        `${BACKEND_URL}/api/documents/generate`,
        {},
        { params: { doc_type: docType, entity_id: entityId } }
      )
      
      if (response.data.success) {
        // Оновити список документів
        await loadDocuments()
        // Відкрити preview
        setPreviewDoc({
          id: response.data.document_id,
          doc_number: response.data.doc_number,
          preview_url: response.data.preview_url,
          pdf_url: response.data.pdf_url
        })
      }
    } catch (error) {
      console.error('Error generating document:', error)
    } finally {
      setGenerating(null)
    }
  }
  
  // Завантажити PDF
  const handleDownloadPdf = async (doc) => {
    window.open(`${BACKEND_URL}${doc.pdf_url}`, '_blank')
  }
  
  // Показати preview
  const handlePreview = (doc) => {
    setPreviewDoc(doc)
  }
  
  // Іконки для типів документів
  const getDocIcon = (docType) => {
    const icons = {
      invoice_offer: '📄',
      contract_rent: '📋',
      issue_act: '📦',
      return_act: '📥',
      picking_list: '📝',
      return_intake_checklist: '✅',
      damage_report_client: '⚠️',
      deposit_settlement_act: '💰',
      invoice_additional: '💵'
    }
    return icons[docType] || '📄'
  }
  
  // Статус документа
  const getStatusBadge = (status) => {
    const badges = {
      draft: { label: 'Чернетка', className: 'bg-slate-100 text-slate-600' },
      signed: { label: 'Підписано', className: 'bg-emerald-100 text-emerald-700' },
      void: { label: 'Анульовано', className: 'bg-rose-100 text-rose-700' }
    }
    return badges[status] || badges.draft
  }
  
  if (loading) {
    return (
      <ZoneCard title={title} hint={hint}>
        <div className="text-center py-4 text-slate-500">Завантаження...</div>
      </ZoneCard>
    )
  }
  
  return (
    <>
      <ZoneCard title={title} hint={hint} tone="neutral">
        {/* Доступні типи документів для генерації */}
        {!readOnly && availableTypes.length > 0 && (
          <div className="mb-4">
            <div className="text-xs text-slate-500 mb-2">Створити документ:</div>
            <div className="flex flex-wrap gap-2">
              {availableTypes.map((type) => (
                <button
                  key={type.doc_type}
                  onClick={() => handleGenerate(type.doc_type)}
                  disabled={generating === type.doc_type}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 
                           bg-white px-3 py-1.5 text-sm font-medium text-slate-700 
                           hover:bg-slate-50 hover:border-slate-300 transition-colors
                           disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <span>{getDocIcon(type.doc_type)}</span>
                  <span>{type.name}</span>
                  {generating === type.doc_type && (
                    <span className="animate-spin">⏳</span>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}
        
        {/* Список існуючих документів */}
        {documents.length > 0 ? (
          <div className="space-y-2">
            <div className="text-xs text-slate-500 mb-2">Створені документи:</div>
            {documents.map((doc) => {
              const statusBadge = getStatusBadge(doc.status)
              return (
                <div 
                  key={doc.id}
                  className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-lg flex-shrink-0">{getDocIcon(doc.doc_type)}</span>
                    <div className="min-w-0">
                      <div className="font-medium text-slate-800 text-sm truncate">
                        {doc.doc_type_name}
                      </div>
                      <div className="text-xs text-slate-500 truncate">
                        {doc.doc_number}
                        {doc.created_at && (
                          <span className="ml-2">
                            {new Date(doc.created_at).toLocaleDateString('uk-UA')}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${statusBadge.className}`}>
                      {statusBadge.label}
                    </span>
                    <button
                      onClick={() => handlePreview(doc)}
                      className="p-1.5 rounded text-slate-500 hover:text-blue-600 hover:bg-blue-50 transition-colors"
                      title="Переглянути"
                    >
                      👁️
                    </button>
                    <button
                      onClick={() => handleDownloadPdf(doc)}
                      className="p-1.5 rounded text-slate-500 hover:text-emerald-600 hover:bg-emerald-50 transition-colors"
                      title="Завантажити PDF"
                    >
                      📥
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="text-center py-4 text-slate-400 text-sm">
            Документів ще немає
          </div>
        )}
      </ZoneCard>
      
      {/* Preview Modal */}
      {previewDoc && (
        <div 
          className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
          onClick={() => setPreviewDoc(null)}
        >
          <div 
            className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between gap-4 px-6 py-4 border-b">
              <div>
                <h3 className="font-semibold text-slate-800">{previewDoc.doc_number}</h3>
                <p className="text-sm text-slate-500">Перегляд документа</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleDownloadPdf(previewDoc)}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 
                           px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 transition-colors"
                >
                  📥 Завантажити PDF
                </button>
                <button
                  onClick={() => setPreviewDoc(null)}
                  className="p-2 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
                >
                  ✕
                </button>
              </div>
            </div>
            
            {/* Modal Content - iframe with document preview */}
            <div className="flex-1 overflow-auto p-4 bg-slate-100">
              <iframe
                src={`${BACKEND_URL}${previewDoc.preview_url}`}
                className="w-full h-full min-h-[600px] bg-white rounded-lg shadow-inner"
                title="Document Preview"
              />
            </div>
          </div>
        </div>
      )}
    </>
  )
}
