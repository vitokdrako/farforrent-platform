/* eslint-disable */
import React from 'react'
import TonePill from './TonePill'

/**
 * ZoneCard - Уніфікована картка зони в Workspace
 */
export default function ZoneCard({ 
  title,
  hint,
  tone = 'neutral',
  icon,
  children,
  actions = [],
  collapsible = false,
  defaultCollapsed = false,
  className = '',
  rightContent,
  compact = false, // Компактний режим для мобільних
}) {
  const [collapsed, setCollapsed] = React.useState(defaultCollapsed)
  
  return (
    <div className={`rounded-xl border bg-white shadow-sm ${compact ? 'p-2 sm:p-4' : 'p-4'} ${className}`}>
      {/* Header */}
      <div className={`flex items-start justify-between gap-2 ${compact ? 'mb-2' : 'mb-3'}`}>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {collapsible && (
              <button 
                onClick={() => setCollapsed(!collapsed)}
                className="text-slate-400 hover:text-slate-600 transition-colors"
              >
                {collapsed ? '▶' : '▼'}
              </button>
            )}
            <h3 className={`font-semibold text-slate-800 ${compact ? 'text-sm' : ''}`}>{title}</h3>
            {tone !== 'neutral' && (
              <TonePill tone={tone} icon={icon} compact={compact}>
                {tone === 'ok' ? '✓' : tone === 'warn' ? '!' : tone === 'danger' ? '!!' : ''}
              </TonePill>
            )}
          </div>
          {hint && !collapsed && (
            <p className={`mt-0.5 text-slate-500 ${compact ? 'text-xs' : 'text-sm'}`}>{hint}</p>
          )}
        </div>
        {rightContent && (
          <div className="flex-shrink-0">
            {rightContent}
          </div>
        )}
      </div>
      
      {/* Content */}
      {!collapsed && children && (
        <div className={compact ? 'mb-2' : 'mb-3'}>
          {children}
        </div>
      )}
      
      {/* Actions */}
      {!collapsed && actions.length > 0 && (
        <div className={`flex flex-wrap gap-2 pt-2 border-t border-slate-100`}>
          {actions.map((action, idx) => (
            <button
              key={idx}
              onClick={action.onClick}
              disabled={action.disabled}
              className={`
                rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors
                disabled:opacity-50 disabled:cursor-not-allowed
                ${action.variant === 'primary' 
                  ? 'bg-slate-900 text-white border-slate-900 hover:bg-slate-800' 
                  : action.variant === 'success'
                  ? 'bg-emerald-600 text-white border-emerald-600 hover:bg-emerald-700'
                  : action.variant === 'danger'
                  ? 'bg-rose-600 text-white border-rose-600 hover:bg-rose-700'
                  : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                }
              `}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
