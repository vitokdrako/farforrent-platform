/* eslint-disable */
import React, { useState } from 'react'
import ZoneCard from '../ZoneCard'

/**
 * Zone: Items Editor - Редагування позицій замовлення
 * Для статусу: DRAFT
 * Повний редактор з пошуком SKU
 */
export default function ZoneItemsEditor({
  items = [],
  inventory = [],
  rentalDays = 1,
  onAddItem,
  onRemoveItem,
  onUpdateItem,
  onOpenCatalog,
  loadingInventory = false,
}) {
  const fmtUA = (n) => (Number(n) || 0).toLocaleString('uk-UA', { maximumFractionDigits: 0 })
  
  // Розрахунок сум
  const totals = items.reduce((acc, item) => {
    const qty = parseInt(item.qty || item.quantity) || 0
    const price = parseFloat(item.price || item.price_per_day) || 0
    acc.rent += price * qty * rentalDays
    acc.items += qty
    return acc
  }, { rent: 0, items: 0 })
  
  // Пошук по SKU
  const handleSKUSearch = async (index, sku) => {
    onUpdateItem?.(index, 'sku', sku)
    
    if (sku.length >= 3 && inventory.length > 0) {
      const found = inventory.find(item => 
        item.article?.toLowerCase() === sku.toLowerCase() ||
        item.sku?.toLowerCase() === sku.toLowerCase() ||
        item.id?.toLowerCase() === sku.toLowerCase()
      )
      
      if (found) {
        onUpdateItem?.(index, 'name', found.name)
        // Використовуємо rent_price або price_per_day для ціни оренди
        const rentPrice = found.rent_price || found.rental_price || found.price_per_day || 0
        onUpdateItem?.(index, 'price', rentPrice)
        // damage_cost - вартість товару для розрахунку застави
        const damageCost = found.damage_cost || found.replacement_price || found.price || 0
        onUpdateItem?.(index, 'damage_cost', damageCost)
        onUpdateItem?.(index, 'depositTier', found.deposit_tier || 'medium')
      }
    }
  }
  
  return (
    <ZoneCard
      title={`Позиції замовлення (${items.length})`}
      hint={`Всього ${totals.items} од. • Оренда за ${rentalDays} дн.: ₴${fmtUA(totals.rent)}`}
      tone="neutral"
      actions={[
        { label: '+ Додати позицію', onClick: onAddItem },
        ...(onOpenCatalog ? [{ label: 'Каталог', onClick: onOpenCatalog }] : [])
      ]}
    >
      {items.length === 0 ? (
        <div className="text-center py-6 text-slate-400">
          Додайте позиції до замовлення
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="px-3 py-2 text-left font-medium">SKU</th>
                <th className="px-3 py-2 text-left font-medium">Назва</th>
                <th className="px-3 py-2 text-center font-medium">К-сть</th>
                <th className="px-3 py-2 text-right font-medium">Ціна/дн.</th>
                <th className="px-3 py-2 text-right font-medium">Сума</th>
                <th className="px-3 py-2 text-center font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((item, idx) => (
                <tr key={idx} className="hover:bg-slate-50">
                  <td className="px-3 py-2">
                    <input
                      type="text"
                      value={item.sku || ''}
                      onChange={(e) => handleSKUSearch(idx, e.target.value)}
                      placeholder="SKU..."
                      list={`sku-list-${idx}`}
                      className="w-24 rounded border border-slate-200 px-2 py-1 text-sm focus:border-blue-400 outline-none"
                    />
                    <datalist id={`sku-list-${idx}`}>
                      {inventory.map((inv) => (
                        <option key={inv.id || inv.article} value={inv.article}>
                          {inv.name}
                        </option>
                      ))}
                    </datalist>
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="text"
                      value={item.name || ''}
                      onChange={(e) => onUpdateItem?.(idx, 'name', e.target.value)}
                      placeholder="Назва товару"
                      className="w-full min-w-[200px] rounded border border-slate-200 px-2 py-1 text-sm focus:border-blue-400 outline-none"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center justify-center gap-1">
                      <button
                        onClick={() => onUpdateItem?.(idx, 'qty', Math.max(1, (item.qty || 1) - 1))}
                        className="w-7 h-7 rounded bg-slate-100 hover:bg-slate-200 text-slate-600"
                      >
                        −
                      </button>
                      <span className="w-8 text-center font-medium">{item.qty || 1}</span>
                      <button
                        onClick={() => onUpdateItem?.(idx, 'qty', (item.qty || 1) + 1)}
                        className="w-7 h-7 rounded bg-slate-100 hover:bg-slate-200 text-slate-600"
                      >
                        +
                      </button>
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      value={item.price || 0}
                      onChange={(e) => onUpdateItem?.(idx, 'price', parseFloat(e.target.value) || 0)}
                      className="w-20 rounded border border-slate-200 px-2 py-1 text-sm text-right tabular-nums focus:border-blue-400 outline-none"
                    />
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums font-medium">
                    ₴ {fmtUA((item.price || 0) * (item.qty || 1) * rentalDays)}
                  </td>
                  <td className="px-3 py-2 text-center">
                    <button
                      onClick={() => onRemoveItem?.(idx)}
                      className="text-rose-500 hover:text-rose-700"
                      title="Видалити"
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot className="bg-slate-50 font-medium">
              <tr>
                <td colSpan="4" className="px-3 py-2 text-right">Всього:</td>
                <td className="px-3 py-2 text-right tabular-nums">₴ {fmtUA(totals.rent)}</td>
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </ZoneCard>
  )
}
