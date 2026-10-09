/* eslint-disable */
import React from 'react'

const TONE_STYLES = {
  neutral: 'bg-slate-100 text-slate-700 border-slate-200',
  info: 'bg-blue-100 text-blue-800 border-blue-200',
  ok: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  warn: 'bg-amber-100 text-amber-900 border-amber-200',
  danger: 'bg-rose-100 text-rose-800 border-rose-200',
  violet: 'bg-violet-100 text-violet-800 border-violet-200'
}

export default function TonePill({ tone = 'neutral', children, icon, className = '', compact = false }) {
  const styles = TONE_STYLES[tone] || TONE_STYLES.neutral
  
  return (
    <span 
      className={`
        inline-flex items-center gap-1 rounded-full border font-semibold flex-shrink-0
        ${compact ? 'px-2 py-0.5 text-[10px]' : 'px-3 py-1 text-xs'}
        ${styles} ${className}
      `}
    >
      {icon && <span className={compact ? 'text-xs' : ''}>{icon}</span>}
      {children}
    </span>
  )
}

export { TONE_STYLES }
