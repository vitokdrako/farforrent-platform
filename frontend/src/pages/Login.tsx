import React, { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''

export default function Login() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [sessionExpired, setSessionExpired] = useState(false)
  
  // ✅ Перевірка чи сесія закінчилась
  useEffect(() => {
    if (searchParams.get('session_expired') === 'true') {
      setSessionExpired(true)
    }
  }, [searchParams])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSessionExpired(false)
    setLoading(true)

    try {
      const response = await fetch(`${BACKEND_URL}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      })

      const data = await response.json()

      if (!response.ok) {
        // FastAPI може повернути detail як string, об'єкт або масив об'єктів (validation errors)
        let msg = 'Помилка авторизації'
        if (typeof data?.detail === 'string') {
          msg = data.detail
        } else if (Array.isArray(data?.detail)) {
          msg = data.detail.map((d: any) => d?.msg || JSON.stringify(d)).join('; ')
        } else if (data?.detail && typeof data.detail === 'object') {
          msg = data.detail.msg || JSON.stringify(data.detail)
        }
        throw new Error(msg)
      }

      // Save token to localStorage
      localStorage.setItem('token', data.access_token)
      localStorage.setItem('user', JSON.stringify(data.user))

      // Role-based redirect
      const role = data.user?.role;
      const startPage = role === 'manager' ? '/manager-cabinet'
                       : '/manager';
      window.location.href = startPage;
    } catch (err: any) {
      setError(err.message || 'Помилка авторизації')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-corp-bg-page flex items-center justify-center p-4 font-montserrat">
      <div className="corp-card shadow-corp-lg w-full max-w-md">
        {/* Logo/Title */}
        <div className="text-center mb-8">
          <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-corp-primary">
            <span className="text-4xl font-bold text-white">R</span>
          </div>
          <h1 className="text-3xl font-bold text-corp-text-dark">Rental Hub</h1>
          <p className="text-sm text-corp-text-muted mt-2">Увійдіть у свій акаунт</p>
        </div>
        
        {/* ✅ Повідомлення про закінчення сесії */}
        {sessionExpired && (
          <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-700 text-sm text-center">
            ⏰ Ваша сесія закінчилась. Будь ласка, увійдіть знову.
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label htmlFor="email" className="text-xs text-corp-text-muted uppercase tracking-wide mb-2 block font-medium">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="corp-input"
              placeholder="your@email.com"
              autoComplete="email"
            />
          </div>

          <div>
            <label htmlFor="password" className="text-xs text-corp-text-muted uppercase tracking-wide mb-2 block font-medium">
              Пароль
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="corp-input"
              placeholder="••••••••"
              autoComplete="current-password"
            />
          </div>

          {error && (
            <div className="corp-badge corp-badge-error p-3 text-center w-full">
              ⚠️ {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full corp-btn corp-btn-primary py-3 text-base disabled:opacity-50"
          >
            {loading ? 'Завантаження...' : 'Увійти'}
          </button>
        </form>

        {/* Footer */}
        <div className="mt-8 text-center text-xs text-corp-text-muted">
          <p className="mb-2">Для отримання доступу зверніться до адміністратора</p>
          <p>© 2024 Rental Hub • Powered by <span className="text-corp-primary font-semibold">FarforRent</span></p>
        </div>
      </div>
    </div>
  )
}
