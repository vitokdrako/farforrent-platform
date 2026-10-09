/* eslint-disable */
/**
 * Order Workspace Demo - Демонстрація уніфікованої системи карток
 * Переключення між статусами для перегляду різних модулів
 */

import React, { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  OrderWorkspaceLayout,
  TonePill,
  STATUS_CONFIG,
} from '../components/order-workspace'
import {
  LeftRailClient,
  LeftRailFinance,
  LeftRailTimeline,
} from '../components/order-workspace'
import {
  ZoneClientSetup,
  ZonePlanDates,
  ZoneAvailabilityGate,
  ZoneCommercialSummary,
  ZoneItemsList,
  ZoneItemSearch,
  ZoneNotes,
  ZoneChecklist,
  ZonePaymentGate,
  ZoneConditionTriage,
  ZoneIssuedSnapshot,
} from '../components/order-workspace/zones'

const STATES = [
  'WAITING_CONFIRMATION',
  'PROCESSING',
  'READY_FOR_ISSUE',
  'ISSUED',
  'INTAKE',
  'CLOSED',
]

// Демо-дані
const DEMO_ORDER = {
  id: 'demo-1',
  orderNumber: 'OC-7890',
  status: 'WAITING_CONFIRMATION',
  client: {
    name: 'Марія Іванівна Петренко',
    phone: '+380991234567',
    email: 'maria@example.com',
    tier: 'regular',
    orderCount: 5,
  },
  dates: {
    issue: '2024-12-15',
    return: '2024-12-20',
    issueTime: '11:30–12:00',
    returnTime: 'до 17:00',
    rentalDays: 5,
  },
  finance: {
    rent: 5000,
    deposit: 2500,
    discount: 10,
    prepayment: 1000,
    rentPaid: false,
    depositPaid: false,
  },
  items: [
    { id: 1, name: 'Крісло велюрове "Барон"', sku: 'DI-001', quantity: 2, price_per_day: 450, deposit: 800, image: '' },
    { id: 2, name: 'Столик журнальний золотий', sku: 'DI-002', quantity: 1, price_per_day: 350, deposit: 600, image: '' },
    { id: 3, name: 'Ваза декоративна срібна', sku: 'DI-003', quantity: 3, price_per_day: 150, deposit: 400, image: '' },
  ],
  conflicts: [],
  notes: 'Клієнт просив доставку до 10:00',
  timeline: [
    { text: 'Замовлення створено', at: '14.12.2024 10:30', tone: 'blue', user: 'Система' },
    { text: 'Відправлено на підтвердження', at: '14.12.2024 11:00', tone: 'amber', user: 'Менеджер' },
  ],
}

export default function OrderWorkspaceDemo() {
  const navigate = useNavigate()
  const [currentStatus, setCurrentStatus] = useState('WAITING_CONFIRMATION')
  
  // Демо стани для гейтів
  const [rentPaid, setRentPaid] = useState(false)
  const [depositPaid, setDepositPaid] = useState(false)
  const [checklist, setChecklist] = useState([
    { id: 1, label: 'Клієнт підтверджений', checked: true, required: true },
    { id: 2, label: 'Дати погоджені', checked: true, required: true },
    { id: 3, label: 'Оплата отримана', checked: false, required: true },
    { id: 4, label: 'Документи підписані', checked: false, required: false },
  ])
  const [conditionItems, setConditionItems] = useState(
    DEMO_ORDER.items.map(i => ({ ...i, status: null, findings: [] }))
  )
  
  // Модулі для кожного статусу
  const renderWorkspaceContent = () => {
    switch (currentStatus) {
      case 'WAITING_CONFIRMATION':
        return (
          <>
            <ZoneClientSetup
              clientName={DEMO_ORDER.client.name}
              clientPhone={DEMO_ORDER.client.phone}
              clientEmail={DEMO_ORDER.client.email}
              discount={DEMO_ORDER.finance.discount}
              onUpdateDiscount={(d) => console.log('Discount:', d)}
            />
            <ZonePlanDates
              issueDate={DEMO_ORDER.dates.issue}
              returnDate={DEMO_ORDER.dates.return}
              issueTime={DEMO_ORDER.dates.issueTime}
              returnTime={DEMO_ORDER.dates.returnTime}
              rentalDays={DEMO_ORDER.dates.rentalDays}
              onUpdate={(dates) => console.log('Dates:', dates)}
            />
            <ZoneAvailabilityGate
              conflicts={DEMO_ORDER.conflicts}
              hasItems={DEMO_ORDER.items.length > 0}
              hasDates={true}
              onCheckConflicts={() => console.log('Check conflicts')}
            />
            <ZoneItemSearch
              onSearch={(q) => console.log('Search:', q)}
              onAddItem={(p) => console.log('Add:', p)}
              searchResults={[]}
            />
            <ZoneItemsList
              items={DEMO_ORDER.items}
              rentalDays={DEMO_ORDER.dates.rentalDays}
              mode="edit"
              onUpdateQuantity={(id, qty) => console.log('Update:', id, qty)}
              onRemoveItem={(id) => console.log('Remove:', id)}
            />
            <ZoneCommercialSummary
              rentAmount={DEMO_ORDER.finance.rent}
              depositAmount={DEMO_ORDER.finance.deposit}
              discountPercent={DEMO_ORDER.finance.discount}
              rentalDays={DEMO_ORDER.dates.rentalDays}
              itemsCount={DEMO_ORDER.items.length}
            />
            <ZoneNotes
              notes={DEMO_ORDER.notes}
              onUpdateNotes={(n) => console.log('Notes:', n)}
            />
          </>
        )
      
      case 'PROCESSING':
        return (
          <>
            <ZoneChecklist
              items={checklist}
              onToggle={(id) => setChecklist(prev => 
                prev.map(i => i.id === id ? { ...i, checked: !i.checked } : i)
              )}
              title="📋 Чеклист комплектації"
              hint="Перевірка перед видачею"
            />
            <ZoneItemsList
              items={DEMO_ORDER.items}
              rentalDays={DEMO_ORDER.dates.rentalDays}
              mode="pick"
              onTogglePicked={(id) => console.log('Toggle picked:', id)}
            />
            <ZoneCommercialSummary
              rentAmount={DEMO_ORDER.finance.rent}
              depositAmount={DEMO_ORDER.finance.deposit}
              discountPercent={DEMO_ORDER.finance.discount}
              rentalDays={DEMO_ORDER.dates.rentalDays}
              itemsCount={DEMO_ORDER.items.length}
            />
            <ZoneNotes
              notes={DEMO_ORDER.notes}
              title="📝 Нотатки комплектації"
            />
          </>
        )
      
      case 'READY_FOR_ISSUE':
        return (
          <>
            <ZonePaymentGate
              rentPaid={rentPaid}
              depositPaid={depositPaid}
              rentAmount={DEMO_ORDER.finance.rent}
              depositAmount={DEMO_ORDER.finance.deposit}
              onMarkRentPaid={() => setRentPaid(true)}
              onMarkDepositPaid={() => setDepositPaid(true)}
            />
            <ZoneChecklist
              items={checklist}
              onToggle={(id) => setChecklist(prev => 
                prev.map(i => i.id === id ? { ...i, checked: !i.checked } : i)
              )}
              title="✅ Чеклист видачі"
            />
            <ZoneItemsList
              items={DEMO_ORDER.items}
              rentalDays={DEMO_ORDER.dates.rentalDays}
              mode="view"
            />
          </>
        )
      
      case 'ISSUED':
        return (
          <>
            <ZoneIssuedSnapshot
              issuedAt="2024-12-15T11:45:00"
              issuedBy="Менеджер Олена"
              itemsCount={DEMO_ORDER.items.length}
              rentAmount={DEMO_ORDER.finance.rent}
              depositAmount={DEMO_ORDER.finance.deposit}
              onPrintInvoice={() => console.log('Print invoice')}
            />
            <ZoneItemsList
              items={DEMO_ORDER.items}
              rentalDays={DEMO_ORDER.dates.rentalDays}
              mode="view"
            />
            <ZoneNotes
              notes={DEMO_ORDER.notes}
              readOnly
              title="📝 Нотатки (read-only)"
            />
          </>
        )
      
      case 'INTAKE':
        return (
          <>
            <ZoneConditionTriage
              items={conditionItems}
              onSetStatus={(id, status) => setConditionItems(prev =>
                prev.map(i => i.id === id ? { ...i, status } : i)
              )}
              onOpenFinding={(id) => console.log('Open finding:', id)}
            />
            <ZoneCommercialSummary
              rentAmount={DEMO_ORDER.finance.rent}
              depositAmount={DEMO_ORDER.finance.deposit}
              discountPercent={0}
              rentalDays={DEMO_ORDER.dates.rentalDays}
              itemsCount={DEMO_ORDER.items.length}
            />
            <ZoneNotes
              notes=""
              title="📝 Нотатки приймання"
              hint="Коментарі щодо стану товарів"
            />
          </>
        )
      
      case 'CLOSED':
        return (
          <>
            <ZoneIssuedSnapshot
              issuedAt="2024-12-15T11:45:00"
              issuedBy="Менеджер Олена"
              itemsCount={DEMO_ORDER.items.length}
              rentAmount={DEMO_ORDER.finance.rent}
              depositAmount={DEMO_ORDER.finance.deposit}
            />
            <ZoneItemsList
              items={DEMO_ORDER.items}
              rentalDays={DEMO_ORDER.dates.rentalDays}
              mode="view"
            />
            <ZoneNotes
              notes="Замовлення завершено успішно. Всі товари повернуті в належному стані."
              readOnly
              title="📝 Підсумок"
            />
          </>
        )
      
      default:
        return <div className="text-center py-8 text-slate-400">Невідомий статус</div>
    }
  }
  
  // Визначення primary action disabled
  const primaryDisabled = currentStatus === 'READY_FOR_ISSUE' && (!rentPaid || !depositPaid)
  
  return (
    <div className="min-h-screen bg-slate-100">
      {/* Status Switcher */}
      <div className="bg-white border-b border-slate-200 px-4 py-3">
        <div className="mx-auto max-w-7xl">
          <div className="text-sm text-slate-500 mb-2">Demo: Переключення статусів</div>
          <div className="flex flex-wrap gap-2">
            {STATES.map((s) => (
              <button
                key={s}
                onClick={() => setCurrentStatus(s)}
                className={`
                  px-3 py-1.5 rounded-full text-sm font-medium border transition-colors
                  ${s === currentStatus 
                    ? 'bg-slate-900 text-white border-slate-900' 
                    : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                  }
                `}
              >
                {STATUS_CONFIG[s]?.title || s}
              </button>
            ))}
          </div>
        </div>
      </div>
      
      {/* Main Layout */}
      <OrderWorkspaceLayout
        orderId={DEMO_ORDER.id}
        orderNumber={DEMO_ORDER.orderNumber}
        status={currentStatus}
        issueDate={DEMO_ORDER.dates.issue}
        returnDate={DEMO_ORDER.dates.return}
        backUrl="/manager"
        leftRail={
          <>
            <LeftRailClient
              name={DEMO_ORDER.client.name}
              phone={DEMO_ORDER.client.phone}
              email={DEMO_ORDER.client.email}
              tier={DEMO_ORDER.client.tier}
              orderCount={DEMO_ORDER.client.orderCount}
            />
            <LeftRailFinance
              rentAmount={DEMO_ORDER.finance.rent}
              depositAmount={DEMO_ORDER.finance.deposit}
              discount={DEMO_ORDER.finance.discount}
              prepayment={DEMO_ORDER.finance.prepayment}
              isPaid={rentPaid && depositPaid}
              showGate={currentStatus === 'READY_FOR_ISSUE'}
              gateMessage={!rentPaid || !depositPaid ? 'Очікується оплата' : 'Все готово'}
              gateTone={rentPaid && depositPaid ? 'ok' : 'warn'}
            />
            <LeftRailTimeline
              events={DEMO_ORDER.timeline}
            />
          </>
        }
        onPrimaryAction={() => {
          const nextIdx = STATES.indexOf(currentStatus) + 1
          if (nextIdx < STATES.length) {
            setCurrentStatus(STATES[nextIdx])
          }
        }}
        onSave={() => console.log('Save')}
        primaryDisabled={primaryDisabled}
        primaryDisabledReason={primaryDisabled ? 'Очікується оплата' : ''}
        footerActions={[
          { label: '🚫 Скасувати', onClick: () => console.log('Cancel'), variant: 'danger' }
        ]}
      >
        {renderWorkspaceContent()}
      </OrderWorkspaceLayout>
    </div>
  )
}
