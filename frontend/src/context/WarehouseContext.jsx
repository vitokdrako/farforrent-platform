/**
 * WarehouseContext — глобальний стан активного складу.
 * Повертає обраний склад, список доступних, і хелпер для API URL із warehouse_id.
 *
 * Використання:
 *   const { active, warehouses, switchTo, withWh } = useWarehouse()
 *   fetch(withWh('/api/manager/dashboard/overview'))  // → '...?warehouse_id=1'
 */
import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''
const LS_KEY = 'active_warehouse_code'

const Ctx = createContext({
  active: null,         // {id, code, name, country, city, currency}
  warehouses: [],       // список доступних
  loading: true,
  switchTo: () => {},   // (code: string) => void
  withWh: (u) => u,     // (url) → url with ?warehouse_id=X
})

export function WarehouseProvider({ children }) {
  const [warehouses, setWarehouses] = useState([])
  const [active, setActive] = useState(null)
  const [loading, setLoading] = useState(true)

  const loadWarehouses = useCallback(async () => {
    const token = localStorage.getItem('token')
    if (!token) { setLoading(false); return }
    try {
      const res = await fetch(`${BACKEND_URL}/api/admin/warehouses/_me/accessible`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) { setLoading(false); return }
      const list = await res.json()
      setWarehouses(list)

      // Відновлюємо з localStorage або беремо default/перший
      const savedCode = localStorage.getItem(LS_KEY)
      const saved = savedCode && list.find(w => w.code === savedCode)
      const def = list.find(w => w.is_default)
      setActive(saved || def || list[0] || null)
    } catch (e) {
      console.warn('[WarehouseContext] load failed', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadWarehouses() }, [loadWarehouses])

  const switchTo = useCallback((code) => {
    const found = warehouses.find(w => w.code === code)
    if (found) {
      setActive(found)
      localStorage.setItem(LS_KEY, code)
    }
  }, [warehouses])

  const withWh = useCallback((url) => {
    if (!active) return url
    const sep = url.includes('?') ? '&' : '?'
    return `${url}${sep}warehouse_id=${active.id}`
  }, [active])

  return (
    <Ctx.Provider value={{ active, warehouses, loading, switchTo, withWh, reload: loadWarehouses }}>
      {children}
    </Ctx.Provider>
  )
}

export function useWarehouse() {
  return useContext(Ctx)
}
