/* eslint-disable */
import React, { useState } from 'react';

/**
 * Уніфікована картка замовлення для Dashboard
 * 
 * Єдиний стиль для всіх статусів:
 * - awaiting (Очікує підтвердження)
 * - processing (В обробці) 
 * - preparation (На комплектації)
 * - ready (Готово до видачі)
 * - issued (Видано)
 * - return (Повернення)
 * - closed (Закрито)
 */

// Мапа статусів до візуальних стилів
const STATUS_CONFIG = {
  awaiting: {
    label: 'Очікує',
    tone: 'warn',
    bgClass: 'bg-amber-50',
    textClass: 'text-amber-800',
    borderClass: 'border-amber-200',
    icon: '⏳'
  },
  new: {
    label: 'Нове',
    tone: 'info',
    bgClass: 'bg-blue-50',
    textClass: 'text-blue-800',
    borderClass: 'border-blue-200',
    icon: '🆕'
  },
  processing: {
    label: 'В обробці',
    tone: 'info',
    bgClass: 'bg-blue-50',
    textClass: 'text-blue-800',
    borderClass: 'border-blue-200',
    icon: '⚙️'
  },
  preparation: {
    label: 'Комплектація',
    tone: 'info',
    bgClass: 'bg-indigo-50',
    textClass: 'text-indigo-800',
    borderClass: 'border-indigo-200',
    icon: '📦'
  },
  ready: {
    label: 'Готово',
    tone: 'ok',
    bgClass: 'bg-emerald-50',
    textClass: 'text-emerald-800',
    borderClass: 'border-emerald-200',
    icon: '✅'
  },
  issue: {
    label: 'Видача',
    tone: 'ok',
    bgClass: 'bg-emerald-50',
    textClass: 'text-emerald-800',
    borderClass: 'border-emerald-200',
    icon: '📤'
  },
  issued: {
    label: 'Видано',
    tone: 'ok',
    bgClass: 'bg-teal-50',
    textClass: 'text-teal-800',
    borderClass: 'border-teal-200',
    icon: '✓'
  },
  return: {
    label: 'Повернення',
    tone: 'warn',
    bgClass: 'bg-orange-50',
    textClass: 'text-orange-800',
    borderClass: 'border-orange-200',
    icon: '🔙'
  },
  closed: {
    label: 'Закрито',
    tone: 'neutral',
    bgClass: 'bg-slate-100',
    textClass: 'text-slate-700',
    borderClass: 'border-slate-200',
    icon: '📁'
  }
};

// Компонент статусної мітки
function StatusBadge({ status }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.awaiting;
  
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold ${config.bgClass} ${config.textClass} ${config.borderClass}`}>
      <span>{config.icon}</span>
      <span>{config.label}</span>
    </span>
  );
}

// Компонент для відображення таймлайну
function TimelineHint({ issueDate, returnDate, status }) {
  if (!issueDate && !returnDate) return null;
  
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  
  let hint = null;
  let hintClass = 'text-slate-500';
  
  if (status === 'return' || status === 'issued') {
    // Для повернень - рахуємо до дати повернення
    if (returnDate) {
      const retDate = new Date(returnDate);
      retDate.setHours(0, 0, 0, 0);
      const diffDays = Math.ceil((retDate - today) / (1000 * 60 * 60 * 24));
      
      if (diffDays < 0) {
        hint = `⚠️ Прострочено на ${Math.abs(diffDays)} дн.`;
        hintClass = 'text-rose-600 font-medium';
      } else if (diffDays === 0) {
        hint = '📍 Повернення сьогодні';
        hintClass = 'text-amber-600 font-medium';
      } else if (diffDays === 1) {
        hint = '⏱ Повернення завтра';
        hintClass = 'text-amber-600';
      } else if (diffDays <= 3) {
        hint = `⏱ ${diffDays} дн. до повернення`;
        hintClass = 'text-slate-600';
      }
    }
  } else {
    // Для інших статусів - до дати видачі
    if (issueDate) {
      const issDate = new Date(issueDate);
      issDate.setHours(0, 0, 0, 0);
      const diffDays = Math.ceil((issDate - today) / (1000 * 60 * 60 * 24));
      
      if (diffDays < 0) {
        hint = `⚠️ Видача прострочена`;
        hintClass = 'text-rose-600 font-medium';
      } else if (diffDays === 0) {
        hint = '📍 Видача сьогодні';
        hintClass = 'text-emerald-600 font-medium';
      } else if (diffDays === 1) {
        hint = '⏱ Видача завтра';
        hintClass = 'text-blue-600';
      } else if (diffDays <= 3) {
        hint = `⏱ ${diffDays} дн. до видачі`;
        hintClass = 'text-slate-600';
      }
    }
  }
  
  if (!hint) return null;
  
  return (
    <div className={`text-xs ${hintClass}`}>
      {hint}
    </div>
  );
}

/**
 * Уніфікована картка замовлення
 */
export default function UnifiedOrderCard({
  id,                    // Номер замовлення (відображається як #ID)
  status,                // Статус: awaiting | processing | preparation | ready | issued | return | closed
  customerName,          // Ім'я клієнта
  customerPhone,         // Телефон клієнта
  rentAmount,            // Сума оренди (число або рядок з ₴)
  depositAmount,         // Сума застави (число або рядок з ₴)
  issueDate,             // Дата видачі (YYYY-MM-DD)
  returnDate,            // Дата повернення (YYYY-MM-DD)
  itemsCount,            // Кількість позицій (опціонально)
  isPaid,                // Чи оплачено (опціонально)
  order,                 // Повний об'єкт замовлення (для додаткових дій)
  onClick,               // Callback при кліку на картку
  onCancelByClient,      // Callback для кнопки "Клієнт відмовився"
  onArchive,             // Callback для архівування
  onDateUpdate,          // Callback для оновлення дат
  showDates = true,      // Показувати блок з датами
  showFinance = true,    // Показувати фінансовий блок
  showTimeline = true,   // Показувати підказку таймлайну
  compact = false,       // Компактний режим (менше інформації)
  hasUpdate = false,     // Індикатор що є нові зміни
  updatedBy = null,      // Хто оновив
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [editIssueDate, setEditIssueDate] = useState(issueDate || '');
  const [editReturnDate, setEditReturnDate] = useState(returnDate || '');
  const [isSaving, setIsSaving] = useState(false);
  
  // Форматування сум
  const formatAmount = (amount) => {
    if (typeof amount === 'string') return amount;
    if (typeof amount === 'number') return `₴ ${amount.toFixed(0)}`;
    return '₴ 0';
  };
  
  // Форматування дати
  const formatDate = (dateStr) => {
    if (!dateStr) return null;
    const date = new Date(dateStr);
    return date.toLocaleDateString('uk-UA', { day: 'numeric', month: 'short' });
  };
  
  // Обробка збереження дат
  const handleSaveDates = async (e) => {
    e.stopPropagation();
    if (!onDateUpdate) return;
    
    setIsSaving(true);
    try {
      await onDateUpdate(order?.id || id, editIssueDate, editReturnDate);
      setIsEditing(false);
    } catch (error) {
      console.error('Error updating dates:', error);
      alert('Помилка оновлення дат');
    } finally {
      setIsSaving(false);
    }
  };
  
  // Скасування редагування
  const handleCancelEdit = (e) => {
    e.stopPropagation();
    setIsEditing(false);
    setEditIssueDate(issueDate || '');
    setEditReturnDate(returnDate || '');
  };
  
  // Клік на телефон
  const handlePhoneClick = (e) => {
    e.stopPropagation();
    window.location.href = `tel:${customerPhone}`;
  };
  
  // Визначаємо чи показувати кнопку скасування
  const showCancelButton = onCancelByClient && 
    ['awaiting', 'new', 'processing', 'preparation', 'ready'].includes(status);
  
  // Визначаємо чи показувати кнопку архівування
  const showArchiveButton = onArchive && status === 'closed';
  
  // Визначаємо чи можна редагувати дати
  const canEditDates = onDateUpdate && ['awaiting', 'new'].includes(status);

  return (
    <article 
      className={`
        relative rounded-xl border bg-white p-4 
        transition-all duration-200
        ${onClick ? 'cursor-pointer hover:shadow-md hover:border-slate-300 active:bg-slate-50' : ''}
        ${compact ? 'p-3' : 'p-4'}
        ${hasUpdate ? 'ring-2 ring-red-200' : ''}
      `}
      onClick={isEditing ? undefined : onClick}
    >
      {/* Індикатор оновлень (червона крапка) */}
      {hasUpdate && (
        <span 
          className="absolute top-2 right-2 flex h-3 w-3"
          title={updatedBy ? `Оновлено: ${updatedBy}` : 'Є нові зміни'}
        >
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
        </span>
      )}
      {/* === HEADER: Статус + Номер замовлення === */}
      <div className="flex items-center justify-between mb-3">
        <StatusBadge status={status} />
        <div className="flex items-center gap-2">
          {canEditDates && !isEditing && (
            <button 
              onClick={(e) => { e.stopPropagation(); setIsEditing(true); }}
              className="text-xs text-blue-600 hover:text-blue-800 font-medium px-2 py-1 rounded-lg bg-blue-50 hover:bg-blue-100 active:bg-blue-200 transition-colors"
              title="Редагувати дати"
            >
              📅
            </button>
          )}
          <span className="text-sm font-medium text-slate-500">#{id}</span>
        </div>
      </div>
      
      {/* === CLIENT INFO === */}
      <div className="mb-3">
        <div className="font-semibold text-slate-800 text-base truncate">{customerName || '—'}</div>
        {customerPhone && (
          <a 
            href={`tel:${customerPhone}`}
            onClick={handlePhoneClick}
            className="text-blue-600 hover:text-blue-800 font-medium text-sm flex items-center gap-1 mt-1"
          >
            📞 {customerPhone}
          </a>
        )}
      </div>
      
      {/* === DATES SECTION === */}
      {showDates && (issueDate || returnDate || isEditing) && (
        isEditing ? (
          <div className="mb-3 space-y-3 bg-slate-50 p-3 rounded-xl" onClick={(e) => e.stopPropagation()}>
            <div>
              <label className="text-xs text-slate-500 uppercase tracking-wide block mb-1">Дата видачі</label>
              <input 
                type="date" 
                value={editIssueDate}
                onChange={(e) => setEditIssueDate(e.target.value)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
                disabled={isSaving}
              />
            </div>
            <div>
              <label className="text-xs text-slate-500 uppercase tracking-wide block mb-1">Дата повернення</label>
              <input 
                type="date" 
                value={editReturnDate}
                onChange={(e) => setEditReturnDate(e.target.value)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
                disabled={isSaving}
              />
            </div>
            <div className="flex gap-2">
              <button 
                onClick={handleSaveDates}
                disabled={isSaving}
                className="flex-1 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white font-medium text-sm disabled:opacity-50 active:bg-emerald-700 transition-colors"
              >
                {isSaving ? '⏳ ...' : '✓ Зберегти'}
              </button>
              <button 
                onClick={handleCancelEdit}
                disabled={isSaving}
                className="px-4 py-2.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 font-medium text-sm disabled:opacity-50 active:bg-slate-100 transition-colors"
              >
                ✕
              </button>
            </div>
          </div>
        ) : (
          <div className="mb-3 bg-slate-50 rounded-lg p-2.5 text-sm">
            <div className="flex flex-wrap gap-x-4 gap-y-1">
              {issueDate && (
                <span className="text-slate-600">
                  📅 Видача: <span className="font-medium text-slate-800">{formatDate(issueDate)}</span>
                </span>
              )}
              {returnDate && (
                <span className="text-slate-600">
                  📆 Поверн.: <span className="font-medium text-slate-800">{formatDate(returnDate)}</span>
                </span>
              )}
            </div>
          </div>
        )
      )}
      
      {/* === FINANCE ROW === */}
      {showFinance && (
        <div className="grid grid-cols-2 gap-2 text-sm mb-3">
          <div className="rounded-lg bg-slate-50 px-3 py-2.5 text-center">
            <div className="text-xs text-slate-500">Сума</div>
            <div className="font-bold text-slate-800 tabular-nums">{formatAmount(rentAmount)}</div>
          </div>
          <div className={`rounded-lg px-3 py-2.5 text-center ${isPaid ? 'bg-emerald-50' : 'bg-amber-50'}`}>
            <div className="text-xs text-slate-500">Застава</div>
            <div className={`font-bold tabular-nums ${isPaid ? 'text-emerald-700' : 'text-amber-700'}`}>
              {formatAmount(depositAmount)}
              {isPaid && <span className="ml-1 text-xs">✓</span>}
            </div>
          </div>
        </div>
      )}
      
      {/* === META INFO (Items count + Timeline) === */}
      {(itemsCount || showTimeline) && (
        <div className="flex items-center justify-between text-xs text-slate-500 mb-3">
          {itemsCount && (
            <span>📦 {itemsCount} поз.</span>
          )}
          {showTimeline && (
            <TimelineHint 
              issueDate={issueDate} 
              returnDate={returnDate} 
              status={status} 
            />
          )}
        </div>
      )}
      
      {/* === ACTION BUTTONS === */}
      {showCancelButton && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onCancelByClient(order?.order_id || order?.id, id);
          }}
          className="w-full text-sm text-rose-600 border-2 border-rose-200 rounded-xl px-3 py-2.5 font-medium hover:bg-rose-50 active:bg-rose-100 transition-colors"
        >
          🚫 Клієнт відмовився
        </button>
      )}
      
      {showArchiveButton && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onArchive(order?.order_id || order?.id, id);
          }}
          className="w-full text-sm text-slate-600 border border-slate-300 rounded-xl px-3 py-2.5 font-medium hover:bg-slate-50 active:bg-slate-100 transition-colors"
        >
          📂 В архів
        </button>
      )}
    </article>
  );
}

// Експортуємо також StatusBadge для використання в інших місцях
export { StatusBadge, STATUS_CONFIG };
