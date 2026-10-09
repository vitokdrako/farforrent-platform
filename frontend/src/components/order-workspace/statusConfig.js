// Конфігурація статусів замовлень

export const STATUS_CONFIG = {
  // Чернетка / Нове замовлення
  DRAFT: {
    key: 'DRAFT',
    title: 'Чернетка',
    mode: 'Режим створення',
    tone: 'neutral',
    color: 'bg-slate-50',
    borderColor: 'border-slate-200',
    icon: '📝',
    primaryAction: 'Створити замовлення',
    secondaryActions: ['Зберегти чернетку']
  },
  
  // Нове замовлення / Очікує підтвердження
  WAITING_CONFIRMATION: {
    key: 'WAITING_CONFIRMATION',
    title: 'Очікує підтвердження',
    mode: 'Режим підтвердження',
    tone: 'warn',
    color: 'bg-amber-50',
    borderColor: 'border-amber-200',
    icon: '⏳',
    primaryAction: 'Підтвердити та прийняти',
    secondaryActions: ['Зберегти', 'Скасувати']
  },
  
  // В обробці / На комплектації
  PROCESSING: {
    key: 'PROCESSING',
    title: 'В обробці',
    mode: 'Режим комплектації',
    tone: 'info',
    color: 'bg-blue-50',
    borderColor: 'border-blue-200',
    icon: '⚙️',
    primaryAction: 'Завершити комплектацію',
    secondaryActions: ['Зберегти']
  },
  
  // Готово до видачі
  READY_FOR_ISSUE: {
    key: 'READY_FOR_ISSUE',
    title: 'Готово до видачі',
    mode: 'Режим видачі',
    tone: 'ok',
    color: 'bg-emerald-50',
    borderColor: 'border-emerald-200',
    icon: '✅',
    primaryAction: 'Видати клієнту',
    secondaryActions: ['Друк накладної', 'Друк QR']
  },
  
  // Видано / В оренді
  ISSUED: {
    key: 'ISSUED',
    title: 'Видано',
    mode: 'Режим оренди (read-only)',
    tone: 'info',
    color: 'bg-indigo-50',
    borderColor: 'border-indigo-200',
    icon: '📤',
    primaryAction: 'Розпочати повернення',
    secondaryActions: ['Надіслати нагадування']
  },
  
  // Повернення / Приймання
  INTAKE: {
    key: 'INTAKE',
    title: 'Повернення',
    mode: 'Режим приймання',
    tone: 'warn',
    color: 'bg-orange-50',
    borderColor: 'border-orange-200',
    icon: '🔙',
    primaryAction: 'Завершити приймання',
    secondaryActions: ['Зберегти стан']
  },
  
  // Закрито / Архів
  CLOSED: {
    key: 'CLOSED',
    title: 'Закрито',
    mode: 'Архів',
    tone: 'neutral',
    color: 'bg-slate-100',
    borderColor: 'border-slate-200',
    icon: '📁',
    primaryAction: null,
    secondaryActions: ['Експорт', 'Відкрити кейс']
  }
}

// Мапа з backend статусів на наші
export const STATUS_MAP = {
  // DecorOrder statuses
  'draft': 'DRAFT',
  'awaiting_customer': 'WAITING_CONFIRMATION',
  'processing': 'PROCESSING',
  'ready_for_issue': 'READY_FOR_ISSUE',
  'ready': 'READY_FOR_ISSUE',
  'issued': 'ISSUED',
  'on_rent': 'ISSUED',
  'returning': 'INTAKE',
  'completed': 'CLOSED',
  'archived': 'CLOSED',
  'cancelled': 'CLOSED',
  
  // IssueCard statuses
  'preparation': 'PROCESSING',
  
  // Legacy numeric statuses
  2: 'WAITING_CONFIRMATION',
  19: 'PROCESSING',
  24: 'INTAKE',
  5: 'CLOSED'
}

export function getStatusConfig(backendStatus) {
  // Якщо передано напряму ключ з STATUS_CONFIG - використовуємо його
  if (STATUS_CONFIG[backendStatus]) {
    return STATUS_CONFIG[backendStatus]
  }
  // Інакше маппимо через STATUS_MAP
  const mappedKey = STATUS_MAP[backendStatus] || 'WAITING_CONFIRMATION'
  return STATUS_CONFIG[mappedKey] || STATUS_CONFIG.WAITING_CONFIRMATION
}

export function getStatusKey(backendStatus) {
  // Якщо передано напряму ключ з STATUS_CONFIG - повертаємо його
  if (STATUS_CONFIG[backendStatus]) {
    return backendStatus
  }
  return STATUS_MAP[backendStatus] || 'WAITING_CONFIRMATION'
}
