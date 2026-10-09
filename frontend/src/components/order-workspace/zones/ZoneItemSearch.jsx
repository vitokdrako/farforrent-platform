/* eslint-disable */
import React, { useState } from 'react'
import ZoneCard from '../ZoneCard'

/**
 * Zone: Item Search - Пошук та додавання товарів
 * Для статусу: WAITING_CONFIRMATION
 */
export default function ZoneItemSearch({
  onSearch,
  onAddItem,
  searchResults = [],
  isSearching = false,
}) {
  const [query, setQuery] = useState('')
  
  const handleSearch = (value) => {
    setQuery(value)
    if (value.length >= 2) {
      onSearch?.(value)
    }
  }
  
  const fmtUA = (n) => (Number(n) || 0).toLocaleString('uk-UA', { maximumFractionDigits: 0 })
  
  return (
    <ZoneCard
      title="🔍 Додати товари"
      hint="Пошук по SKU або назві"
      tone="neutral"
    >
      {/* Пошукове поле */}
      <div className="relative mb-4">
        <input
          type="text"
          value={query}
          onChange={(e) => handleSearch(e.target.value)}
          placeholder="Введіть SKU або назву товару..."
          className="w-full rounded-lg border border-slate-200 px-4 py-3 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
        />
        {isSearching && (
          <div className="absolute right-3 top-3 text-slate-400 text-sm">
            Пошук...
          </div>
        )}
      </div>
      
      {/* Результати */}
      {searchResults.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-80 overflow-auto">
          {searchResults.map((product) => (
            <div 
              key={product.product_id || product.id}
              className="rounded-xl border border-slate-200 bg-white p-3 hover:border-blue-300 transition-colors"
            >
              <div className="flex items-start justify-between mb-2">
                <div className="min-w-0">
                  <div className="font-medium text-sm text-slate-800 truncate">{product.name}</div>
                  <div className="text-xs text-slate-500">SKU: {product.sku}</div>
                </div>
                <div className="text-right flex-shrink-0">
                  <div className="text-sm font-medium text-slate-800">₴ {fmtUA(product.price_per_day)}/д</div>
                  <div className="text-xs text-slate-500">Заст: ₴{fmtUA(product.deposit)}</div>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <div className="text-xs text-slate-500">
                  На складі: {product.total_quantity || product.available || 0} шт
                </div>
                <button
                  onClick={() => onAddItem?.(product)}
                  className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-medium hover:bg-blue-700 transition-colors"
                >
                  + Додати
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : query.length >= 2 && !isSearching ? (
        <div className="text-center py-4 text-slate-400">
          Товарів не знайдено
        </div>
      ) : (
        <div className="text-center py-4 text-slate-400">
          Введіть мінімум 2 символи для пошуку
        </div>
      )}
    </ZoneCard>
  )
}
