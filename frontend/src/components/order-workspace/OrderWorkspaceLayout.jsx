/* eslint-disable */
import React from 'react'
import WorkspaceHeader from './WorkspaceHeader'
import FooterActions from './FooterActions'
import DocumentsFooter from './DocumentsFooter'
import { getStatusConfig } from './statusConfig'

/**
 * OrderWorkspaceLayout - Основний layout для розгорнутих карток
 * Оптимізовано для мобільних пристроїв
 */
export default function OrderWorkspaceLayout({
  // Header props
  orderId,
  orderNumber,
  status,
  issueDate,
  returnDate,
  createdAt,
  headerTitle,
  backUrl,
  
  // Left Rail content
  leftRail,
  
  // Workspace content (ZoneCards)
  children,
  
  // Footer props
  onPrimaryAction,
  onSave,
  primaryLabel,
  primaryDisabled,
  primaryDisabledReason,
  saving,
  showSave,
  footerActions,
  footerChildren,
  progressInfo, // { label, value, percent }
  
  // Documents props
  issueCardId,
  deliveryType,
  showDocuments = true,
  
  // Loading state
  loading,
  
  // Real-time sync props
  activeUsers = [],
  hasUpdates = false,
  onRefresh,
}) {
  const config = getStatusConfig(status)
  
  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-slate-500">Завантаження...</div>
      </div>
    )
  }
  
  return (
    <div className={`min-h-screen bg-slate-50 flex flex-col pb-16 sm:pb-20`}>
      {/* A. Header */}
      <WorkspaceHeader
        orderId={orderId}
        orderNumber={orderNumber}
        status={status}
        issueDate={issueDate}
        returnDate={returnDate}
        createdAt={createdAt}
        title={headerTitle}
        backUrl={backUrl}
        progressInfo={progressInfo}
        activeUsers={activeUsers}
        hasUpdates={hasUpdates}
        onRefresh={onRefresh}
      />
      
      {/* Main content area */}
      <div className="flex-1 mx-auto max-w-7xl w-full px-2 sm:px-6 py-2 sm:py-6">
        <div className="grid grid-cols-12 gap-2 sm:gap-6">
          {/* B. Left Rail - collapsed on mobile */}
          <aside className="col-span-12 lg:col-span-4 space-y-2 sm:space-y-4">
            {leftRail}
          </aside>
          
          {/* C. Workspace */}
          <main className={`col-span-12 lg:col-span-8 rounded-xl sm:rounded-2xl border p-2 sm:p-5 shadow-sm ${config.color} ${config.borderColor}`}>
            {/* Mobile: hide zone header */}
            <div className="hidden sm:flex items-center justify-between gap-3 mb-4">
              <div>
                <div className="text-sm text-slate-500">Центральна зона</div>
                <div className="text-lg font-semibold text-slate-800">{config.title}</div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">{config.mode}</span>
              </div>
            </div>
            
            <div className="space-y-2 sm:space-y-4">
              {children}
            </div>
          </main>
        </div>
      </div>
      
      {/* D. Footer Actions - без progressInfo на mobile (він в хедері) */}
      <FooterActions
        status={status}
        onPrimaryAction={onPrimaryAction}
        onSave={onSave}
        primaryLabel={primaryLabel}
        primaryDisabled={primaryDisabled}
        primaryDisabledReason={primaryDisabledReason}
        saving={saving}
        showSave={showSave}
        additionalActions={footerActions}
      >
        {footerChildren}
      </FooterActions>
    </div>
  )
}
