/* eslint-disable */
/**
 * AdminPanel — Управління RentalHub
 * Вкладки: Користувачі, Документи, Категорії, Витрати, Налаштування
 */
import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import CorporateHeader from '../components/CorporateHeader'
import { Users, FileText, FolderTree, Receipt, Settings, Plus, Pencil, Trash2, Shield, X, Eye, EyeOff, Key, Save, RefreshCw, Check, ArrowLeft, RotateCcw, Code, BarChart3, CalendarCheck, ChevronDown, ChevronUp, ClipboardList, Grid3x3 } from 'lucide-react'
// Lightweight notification
const toast = {
  success: (msg) => { const el = document.createElement('div'); el.className = 'fixed top-4 right-4 z-[999] px-4 py-3 rounded-xl bg-emerald-600 text-white text-sm font-medium shadow-lg'; el.textContent = msg; document.body.appendChild(el); setTimeout(() => el.remove(), 2500) },
  error: (msg) => { const el = document.createElement('div'); el.className = 'fixed top-4 right-4 z-[999] px-4 py-3 rounded-xl bg-red-600 text-white text-sm font-medium shadow-lg'; el.textContent = msg; document.body.appendChild(el); setTimeout(() => el.remove(), 3000) },
}

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || ''
const cls = (...a) => a.filter(Boolean).join(' ')

const authFetch = async (url, opts = {}) => {
  const token = localStorage.getItem('token')
  return fetch(url, { ...opts, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...opts.headers } })
}

// ============================================================
// USERS TAB
// ============================================================
const ROLE_LABELS = { admin: 'Адмін', manager: 'Менеджер', requisitor: 'Реквізитор' }
const ROLE_COLORS = { admin: 'bg-red-50 text-red-700 border-red-200', manager: 'bg-blue-50 text-blue-700 border-blue-200', requisitor: 'bg-emerald-50 text-emerald-700 border-emerald-200' }

function UsersTab() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [editUser, setEditUser] = useState(null)
  const [resetPwUser, setResetPwUser] = useState(null)
  const [newPw, setNewPw] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try { const r = await authFetch(`${BACKEND_URL}/api/admin/users`); if (r.ok) setUsers(await r.json()) }
    catch (e) { console.error(e) }
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  const saveUser = async (data) => {
    const method = data.user_id ? 'PUT' : 'POST'
    const url = data.user_id ? `${BACKEND_URL}/api/admin/users/${data.user_id}` : `${BACKEND_URL}/api/admin/users`
    const r = await authFetch(url, { method, body: JSON.stringify(data) })
    if (r.ok) { toast.success(data.user_id ? 'Користувача оновлено' : 'Користувача створено'); setEditUser(null); load() }
    else { const d = await r.json().catch(() => ({})); toast.error(d.detail || 'Помилка') }
  }

  const resetPassword = async () => {
    if (!newPw.trim() || newPw.length < 4) { toast.error('Мінімум 4 символи'); return }
    const r = await authFetch(`${BACKEND_URL}/api/admin/users/${resetPwUser.user_id}/reset-password`, {
      method: 'POST', body: JSON.stringify({ new_password: newPw })
    })
    if (r.ok) { toast.success('Пароль змінено'); setResetPwUser(null); setNewPw('') }
    else toast.error('Помилка зміни пароля')
  }

  const deleteUser = async (id) => {
    if (!window.confirm('Видалити користувача?')) return
    const r = await authFetch(`${BACKEND_URL}/api/admin/users/${id}`, { method: 'DELETE' })
    if (r.ok) { toast.success('Видалено'); load() } else toast.error('Помилка видалення')
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-sm text-corp-text-muted">{users.length} користувачів</div>
        <button onClick={() => setEditUser({ username: '', email: '', role: 'manager', password: '', firstname: '', lastname: '' })}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-corp-primary text-white text-sm font-medium hover:bg-corp-primary-hover transition-colors"
          data-testid="add-user-btn"><Plus className="w-4 h-4" /> Новий</button>
      </div>

      {loading ? <div className="text-center py-8 text-corp-text-muted animate-pulse">Завантаження...</div> : (
        <div className="bg-white rounded-xl border border-corp-border overflow-hidden">
          <table className="w-full">
            <thead><tr className="bg-corp-bg-light border-b border-corp-border text-xs text-corp-text-muted">
              <th className="px-4 py-3 text-left">Ім'я</th><th className="px-4 py-3 text-left">Email</th>
              <th className="px-4 py-3 text-left">Роль</th><th className="px-4 py-3 text-right">Дії</th>
            </tr></thead>
            <tbody>
              {users.map(u => (
                <tr key={u.user_id} className="border-b border-corp-border/50 hover:bg-corp-bg-light/50 transition-colors" data-testid={`user-row-${u.user_id}`}>
                  <td className="px-4 py-3">
                    <div className="font-medium text-sm text-corp-text-dark">{u.firstname} {u.lastname}</div>
                    <div className="text-xs text-corp-text-muted">@{u.username}</div>
                  </td>
                  <td className="px-4 py-3 text-sm text-corp-text-main">{u.email}</td>
                  <td className="px-4 py-3">
                    <span className={cls('px-2.5 py-1 rounded-lg text-xs font-medium border', ROLE_COLORS[u.role] || 'bg-gray-50 text-gray-600 border-gray-200')}>
                      {ROLE_LABELS[u.role] || u.role}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button onClick={() => setEditUser(u)} className="p-2 rounded-lg hover:bg-corp-bg-light transition-colors" title="Редагувати">
                        <Pencil className="w-4 h-4 text-corp-text-muted" />
                      </button>
                      <button onClick={() => { setResetPwUser(u); setNewPw('') }} className="p-2 rounded-lg hover:bg-corp-bg-light transition-colors" title="Пароль">
                        <Key className="w-4 h-4 text-corp-text-muted" />
                      </button>
                      <button onClick={() => deleteUser(u.user_id)} className="p-2 rounded-lg hover:bg-red-50 transition-colors" title="Видалити">
                        <Trash2 className="w-4 h-4 text-red-400" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Edit/Create Modal */}
      {editUser && <UserModal user={editUser} onSave={saveUser} onClose={() => setEditUser(null)} />}

      {/* Reset Password Modal */}
      {resetPwUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" onClick={() => setResetPwUser(null)}>
          <div className="bg-white rounded-2xl shadow-xl max-w-sm w-full border border-corp-border p-5" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <div className="font-semibold text-corp-text-dark">Змінити пароль: {resetPwUser.username}</div>
              <button onClick={() => setResetPwUser(null)} className="p-1 rounded-lg hover:bg-corp-bg-light"><X className="w-4 h-4" /></button>
            </div>
            <input type="password" value={newPw} onChange={e => setNewPw(e.target.value)} placeholder="Новий пароль (мін. 4 символи)"
              className="w-full px-3 py-2.5 rounded-xl border border-corp-border text-sm mb-4 focus:outline-none focus:border-corp-primary" />
            <button onClick={resetPassword} disabled={newPw.length < 4}
              className="w-full py-2.5 rounded-xl bg-corp-primary text-white font-medium text-sm hover:bg-corp-primary-hover disabled:opacity-50">Зберегти</button>
          </div>
        </div>
      )}
    </div>
  )
}

function UserModal({ user, onSave, onClose }) {
  const [form, setForm] = useState({ ...user })
  const isNew = !user.user_id
  const set = (k, v) => setForm(p => ({ ...p, [k]: v }))
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full border border-corp-border" onClick={e => e.stopPropagation()}>
        <div className="px-5 py-4 border-b border-corp-border flex items-center justify-between">
          <span className="font-semibold text-corp-text-dark">{isNew ? 'Новий користувач' : 'Редагувати'}</span>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-corp-bg-light"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-5 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div><label className="text-xs text-corp-text-muted">Ім'я</label>
              <input value={form.firstname || ''} onChange={e => set('firstname', e.target.value)}
                className="mt-1 w-full px-3 py-2 rounded-xl border border-corp-border text-sm focus:outline-none focus:border-corp-primary" /></div>
            <div><label className="text-xs text-corp-text-muted">Прізвище</label>
              <input value={form.lastname || ''} onChange={e => set('lastname', e.target.value)}
                className="mt-1 w-full px-3 py-2 rounded-xl border border-corp-border text-sm focus:outline-none focus:border-corp-primary" /></div>
          </div>
          <div><label className="text-xs text-corp-text-muted">Username</label>
            <input value={form.username || ''} onChange={e => set('username', e.target.value)}
              className="mt-1 w-full px-3 py-2 rounded-xl border border-corp-border text-sm focus:outline-none focus:border-corp-primary" /></div>
          <div><label className="text-xs text-corp-text-muted">Email</label>
            <input value={form.email || ''} onChange={e => set('email', e.target.value)} type="email"
              className="mt-1 w-full px-3 py-2 rounded-xl border border-corp-border text-sm focus:outline-none focus:border-corp-primary" /></div>
          {isNew && <div><label className="text-xs text-corp-text-muted">Пароль</label>
            <input value={form.password || ''} onChange={e => set('password', e.target.value)} type="password"
              className="mt-1 w-full px-3 py-2 rounded-xl border border-corp-border text-sm focus:outline-none focus:border-corp-primary" /></div>}
          <div><label className="text-xs text-corp-text-muted">Роль</label>
            <div className="flex gap-2 mt-2">
              {Object.entries(ROLE_LABELS).map(([v, l]) => (
                <button key={v} onClick={() => set('role', v)}
                  className={cls('flex-1 py-2 rounded-xl text-xs font-medium border transition-colors',
                    form.role === v ? 'bg-corp-primary text-white border-corp-primary' : 'border-corp-border text-corp-text-main hover:bg-corp-bg-light')}>{l}</button>
              ))}
            </div>
          </div>
          <button onClick={() => onSave(form)} className="w-full py-2.5 rounded-xl bg-corp-primary text-white font-medium text-sm hover:bg-corp-primary-hover mt-2">
            {isNew ? 'Створити' : 'Зберегти'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ============================================================
// DOCUMENTS TAB
// ============================================================
const ALL_DOC_TYPES = [
  { key: 'quote', name: 'Кошторис', desc: 'Попередній розрахунок вартості оренди' },
  { key: 'invoice_offer', name: 'Рахунок-оферта', desc: 'Рахунок на оплату для клієнта' },
  { key: 'master_agreement', name: 'Генеральний договір', desc: 'Основний договір оренди' },
  { key: 'issue_act', name: 'Акт видачі', desc: 'Акт передачі товарів клієнту' },
  { key: 'picking_list', name: 'Лист комплектації', desc: 'Перелік товарів для збору на складі' },
  { key: 'settlement_act', name: 'Акт повернення', desc: 'Акт приймання товарів від клієнта' },
  { key: 'defect_act', name: 'Дефектний акт', desc: 'Фіксація дефектів/пошкоджень повернутого декору' },
  { key: 'deposit_settlement_act', name: 'Акт взаєморозрахунків', desc: 'Розрахунок по заставі' },
  { key: 'invoice_legal', name: 'Рахунок (юр. особа)', desc: 'Рахунок для ФОП/ТОВ з реквізитами' },
  { key: 'service_act', name: 'Акт надання послуг', desc: 'Підтвердження послуг для ФОП/ТОВ' },
  { key: 'goods_invoice', name: 'Видаткова накладна', desc: 'Накладна на товар для ФОП/ТОВ' },
]

function DocumentsTab() {
  const [docStats, setDocStats] = useState({})
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(null) // { doc_type, name, desc }
  const [editorContent, setEditorContent] = useState('')
  const [editorSource, setEditorSource] = useState('file')
  const [previewHtml, setPreviewHtml] = useState('')
  const [previewLoading, setPreviewLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [orderIdForPreview, setOrderIdForPreview] = useState('7403')
  const [editorTab, setEditorTab] = useState('code') // 'code' | 'preview'

  useEffect(() => {
    (async () => {
      try {
        const [statsRes, tplRes] = await Promise.all([
          authFetch(`${BACKEND_URL}/api/admin/document-stats`),
          authFetch(`${BACKEND_URL}/api/admin/templates`),
        ])
        if (statsRes.ok) setDocStats(await statsRes.json())
        if (tplRes.ok) setTemplates(await tplRes.json())
      } catch (e) { console.error(e) }
      setLoading(false)
    })()
  }, [])

  const openEditor = async (doc) => {
    setEditing(doc)
    setEditorTab('code')
    setPreviewHtml('')
    try {
      const r = await authFetch(`${BACKEND_URL}/api/admin/templates/${doc.key}`)
      if (r.ok) {
        const data = await r.json()
        setEditorContent(data.content || '')
        setEditorSource(data.source)
      }
    } catch (e) { console.error(e) }
  }

  const loadPreview = async () => {
    setPreviewLoading(true)
    try {
      const r = await authFetch(`${BACKEND_URL}/api/admin/templates/${editing.key}/preview?order_id=${orderIdForPreview}`)
      if (r.ok) {
        const data = await r.json()
        setPreviewHtml(data.html || data.error || '')
      }
    } catch (e) { setPreviewHtml(`<pre style="color:red">${e.message}</pre>`) }
    setPreviewLoading(false)
  }

  const saveTemplate = async () => {
    setSaving(true)
    try {
      const r = await authFetch(`${BACKEND_URL}/api/admin/templates/${editing.key}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: editorContent })
      })
      if (r.ok) {
        setEditorSource('db')
        setTemplates(prev => prev.map(t => t.doc_type === editing.key ? { ...t, source: 'db' } : t))
        toast.success('Шаблон збережено')
      }
    } catch (e) { toast.error('Помилка збереження') }
    setSaving(false)
  }

  const resetTemplate = async () => {
    if (!window.confirm('Скинути до оригінального файлу? Зміни в БД будуть видалені.')) return
    try {
      const r = await authFetch(`${BACKEND_URL}/api/admin/templates/${editing.key}/reset`, { method: 'POST' })
      if (r.ok) {
        const data = await r.json()
        setEditorContent(data.content || '')
        setEditorSource('file')
        setTemplates(prev => prev.map(t => t.doc_type === editing.key ? { ...t, source: 'file' } : t))
        toast.success('Шаблон скинуто до оригіналу')
      }
    } catch (e) { toast.error('Помилка скидання') }
  }

  if (loading) return <div className="text-center py-8 text-corp-text-muted animate-pulse">Завантаження...</div>

  // Full-screen template editor
  if (editing) {
    return (
      <div className="space-y-0" data-testid="template-editor">
        {/* Editor Header */}
        <div className="flex items-center justify-between gap-3 pb-4 border-b border-corp-border mb-4">
          <div className="flex items-center gap-3">
            <button onClick={() => setEditing(null)} className="p-2 hover:bg-corp-bg-light rounded-lg transition-colors" data-testid="template-editor-close">
              <ArrowLeft size={18} className="text-corp-text-muted" />
            </button>
            <div>
              <div className="text-sm font-semibold text-corp-text-dark flex items-center gap-2">
                {editing.name}
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${editorSource === 'db' ? 'bg-amber-50 text-amber-700 border border-amber-200' : 'bg-slate-50 text-slate-600 border border-slate-200'}`}>
                  {editorSource === 'db' ? 'Змінено (БД)' : 'Оригінал (файл)'}
                </span>
              </div>
              <div className="text-xs text-corp-text-muted">{editing.key}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {editorSource === 'db' && (
              <button onClick={resetTemplate} className="px-3 py-1.5 text-xs rounded-lg border border-corp-border text-corp-text-muted hover:bg-red-50 hover:text-red-600 hover:border-red-200 transition-colors" data-testid="template-reset-btn">
                <RotateCcw size={13} className="inline mr-1" />Скинути
              </button>
            )}
            <button onClick={saveTemplate} disabled={saving}
              className="px-4 py-1.5 text-xs rounded-lg bg-corp-primary text-white hover:bg-corp-primary-dark transition-colors disabled:opacity-50" data-testid="template-save-btn">
              <Save size={13} className="inline mr-1" />{saving ? 'Збереження...' : 'Зберегти'}
            </button>
          </div>
        </div>

        {/* Editor Tabs */}
        <div className="flex items-center gap-1 mb-3">
          <button onClick={() => setEditorTab('code')}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${editorTab === 'code' ? 'bg-corp-bg-dark text-white' : 'text-corp-text-muted hover:bg-corp-bg-light'}`}
            data-testid="tab-code">
            <Code size={13} className="inline mr-1" />Код шаблону
          </button>
          <button onClick={() => { setEditorTab('preview'); loadPreview() }}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${editorTab === 'preview' ? 'bg-corp-bg-dark text-white' : 'text-corp-text-muted hover:bg-corp-bg-light'}`}
            data-testid="tab-preview">
            <Eye size={13} className="inline mr-1" />Попередній перегляд
          </button>
          {editorTab === 'preview' && (
            <div className="ml-auto flex items-center gap-2">
              <label className="text-xs text-corp-text-muted">Замовлення #</label>
              <input value={orderIdForPreview} onChange={e => setOrderIdForPreview(e.target.value)}
                className="w-20 px-2 py-1 text-xs rounded-lg border border-corp-border focus:outline-none focus:border-corp-primary"
                data-testid="preview-order-id" />
              <button onClick={loadPreview} className="px-2 py-1 text-xs rounded-lg bg-corp-bg-light hover:bg-corp-bg-dark hover:text-white transition-colors" data-testid="preview-refresh-btn">
                <RefreshCw size={12} />
              </button>
            </div>
          )}
        </div>

        {/* Code Editor */}
        {editorTab === 'code' && (
          <div className="relative rounded-xl border border-corp-border overflow-hidden bg-[#1e1e2e]" data-testid="code-editor-container">
            <div className="flex items-center justify-between px-3 py-1.5 bg-[#181825] border-b border-[#313244]">
              <span className="text-[10px] text-[#6c7086] font-mono">HTML / Jinja2</span>
              <span className="text-[10px] text-[#6c7086]">{editorContent.length} символів</span>
            </div>
            <textarea
              value={editorContent}
              onChange={e => setEditorContent(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Tab') {
                  e.preventDefault()
                  const start = e.target.selectionStart
                  const end = e.target.selectionEnd
                  const val = e.target.value
                  setEditorContent(val.substring(0, start) + '  ' + val.substring(end))
                  setTimeout(() => { e.target.selectionStart = e.target.selectionEnd = start + 2 }, 0)
                }
              }}
              spellCheck={false}
              className="w-full font-mono text-xs leading-5 p-4 bg-[#1e1e2e] text-[#cdd6f4] resize-none focus:outline-none"
              style={{ minHeight: '500px', tabSize: 2, fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace" }}
              data-testid="code-editor-textarea"
            />
          </div>
        )}

        {/* Preview */}
        {editorTab === 'preview' && (
          <div className="rounded-xl border border-corp-border overflow-hidden bg-white" data-testid="preview-container">
            {previewLoading ? (
              <div className="p-8 text-center text-corp-text-muted animate-pulse">Рендеринг...</div>
            ) : previewHtml ? (
              <iframe
                srcDoc={previewHtml}
                className="w-full border-0"
                style={{ minHeight: '600px' }}
                title="Попередній перегляд"
                data-testid="preview-iframe"
              />
            ) : (
              <div className="p-8 text-center text-corp-text-muted text-sm">Натисніть "Попередній перегляд" для рендерингу</div>
            )}
          </div>
        )}
      </div>
    )
  }

  // Template grid
  const tplMap = {}
  templates.forEach(t => { tplMap[t.doc_type] = t })

  return (
    <div className="space-y-4">
      <div className="text-sm text-corp-text-muted">{ALL_DOC_TYPES.length} типів документів • Натисніть для редагування шаблону</div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {ALL_DOC_TYPES.map(doc => {
          const count = docStats[doc.key] || 0
          const tpl = tplMap[doc.key]
          const hasFile = tpl?.has_file ?? true
          const source = tpl?.source || 'file'
          return (
            <div key={doc.key}
              onClick={() => openEditor(doc)}
              className="bg-white rounded-xl border border-corp-border p-4 hover:shadow-md hover:border-corp-primary/40 transition-all cursor-pointer group"
              data-testid={`doc-${doc.key}`}>
              <div className="flex items-start justify-between gap-2 mb-2">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-corp-text-dark group-hover:text-corp-primary transition-colors">{doc.name}</div>
                  <div className="text-xs text-corp-text-muted mt-0.5">{doc.desc}</div>
                </div>
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  {source === 'db' && (
                    <div className="px-1.5 py-0.5 rounded-lg bg-amber-50 border border-amber-200 text-[10px] font-medium text-amber-700">Змінено</div>
                  )}
                  {hasFile && (
                    <div className="px-1.5 py-0.5 rounded-lg bg-emerald-50 border border-emerald-200 text-[10px] font-medium text-emerald-700">Шаблон</div>
                  )}
                </div>
              </div>
              <div className="flex items-center justify-between mt-3 pt-3 border-t border-corp-border/50">
                <span className="text-xs text-corp-text-muted">Створено: <span className="font-semibold text-corp-text-dark">{count}</span></span>
                <Pencil size={14} className="text-corp-text-muted opacity-0 group-hover:opacity-100 transition-opacity" />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ============================================================
// CATEGORIES TAB
// ============================================================
function CategoriesTab() {
  const [cats, setCats] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  useEffect(() => {
    (async () => {
      try { const r = await authFetch(`${BACKEND_URL}/api/admin/categories`); if (r.ok) setCats(await r.json()) }
      catch (e) { console.error(e) }
      setLoading(false)
    })()
  }, [])

  const filtered = cats.filter(c => !search || c.name?.toLowerCase().includes(search.toLowerCase()))

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm text-corp-text-muted">{cats.length} категорій</div>
        <div className="relative">
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Пошук..."
            className="pl-3 pr-3 py-2 rounded-xl border border-corp-border text-sm w-48 focus:outline-none focus:border-corp-primary" />
        </div>
      </div>
      {loading ? <div className="text-center py-8 text-corp-text-muted animate-pulse">Завантаження...</div> : (
        <div className="bg-white rounded-xl border border-corp-border overflow-hidden max-h-[500px] overflow-y-auto">
          <table className="w-full">
            <thead className="sticky top-0"><tr className="bg-corp-bg-light border-b border-corp-border text-xs text-corp-text-muted">
              <th className="px-4 py-3 text-left">ID</th><th className="px-4 py-3 text-left">Назва</th>
              <th className="px-4 py-3 text-left">Батьківська</th><th className="px-4 py-3 text-center">Статус</th>
            </tr></thead>
            <tbody>
              {filtered.map(c => (
                <tr key={c.category_id} className="border-b border-corp-border/50 hover:bg-corp-bg-light/50 text-sm">
                  <td className="px-4 py-2.5 text-corp-text-muted text-xs">{c.category_id}</td>
                  <td className="px-4 py-2.5 font-medium text-corp-text-dark">{c.name}</td>
                  <td className="px-4 py-2.5 text-corp-text-muted text-xs">{c.parent_id || '—'}</td>
                  <td className="px-4 py-2.5 text-center">
                    <span className={cls('px-2 py-0.5 rounded-lg text-[10px] font-medium border',
                      c.status === 1 ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-red-50 text-red-600 border-red-200'
                    )}>{c.status === 1 ? 'Активна' : 'Вимкнена'}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ============================================================
// EXPENSE CATEGORIES TAB
// ============================================================
function ExpenseCatsTab() {
  const [cats, setCats] = useState([])
  const [loading, setLoading] = useState(true)
  const [editCat, setEditCat] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try { const r = await authFetch(`${BACKEND_URL}/api/finance/admin/expense-categories`); if (r.ok) setCats(await r.json()) }
    catch (e) { console.error(e) }
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  const saveCat = async () => {
    if (!editCat?.name?.trim()) return
    const method = editCat.id ? 'PUT' : 'POST'
    const url = editCat.id ? `${BACKEND_URL}/api/finance/admin/expense-categories/${editCat.id}` : `${BACKEND_URL}/api/finance/admin/expense-categories`
    const r = await authFetch(url, { method, body: JSON.stringify(editCat) })
    if (r.ok) { toast.success('Збережено'); setEditCat(null); load() } else toast.error('Помилка')
  }

  const deleteCat = async (id) => {
    if (!window.confirm('Видалити категорію?')) return
    const r = await authFetch(`${BACKEND_URL}/api/finance/admin/expense-categories/${id}`, { method: 'DELETE' })
    if (r.ok) { toast.success('Видалено'); load() } else toast.error('Помилка')
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-sm text-corp-text-muted">{cats.length} категорій витрат</div>
        <button onClick={() => setEditCat({ name: '', description: '' })}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-corp-primary text-white text-sm font-medium hover:bg-corp-primary-hover"
          data-testid="add-expense-cat"><Plus className="w-4 h-4" /> Нова</button>
      </div>
      {loading ? <div className="text-center py-8 text-corp-text-muted animate-pulse">Завантаження...</div> : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {cats.map(c => (
            <div key={c.id} className="bg-white rounded-xl border border-corp-border p-4 hover:shadow-sm transition-shadow" data-testid={`expense-cat-${c.id}`}>
              <div className="flex items-start justify-between gap-2">
                <div><div className="text-sm font-semibold text-corp-text-dark">{c.name}</div>
                  {c.description && <div className="text-xs text-corp-text-muted mt-0.5">{c.description}</div>}</div>
                <div className="flex gap-1">
                  <button onClick={() => setEditCat(c)} className="p-1.5 rounded-lg hover:bg-corp-bg-light"><Pencil className="w-3.5 h-3.5 text-corp-text-muted" /></button>
                  <button onClick={() => deleteCat(c.id)} className="p-1.5 rounded-lg hover:bg-red-50"><Trash2 className="w-3.5 h-3.5 text-red-400" /></button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      {editCat && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" onClick={() => setEditCat(null)}>
          <div className="bg-white rounded-2xl shadow-xl max-w-sm w-full border border-corp-border p-5" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <span className="font-semibold text-corp-text-dark">{editCat.id ? 'Редагувати' : 'Нова категорія'}</span>
              <button onClick={() => setEditCat(null)} className="p-1 rounded-lg hover:bg-corp-bg-light"><X className="w-4 h-4" /></button>
            </div>
            <input value={editCat.name || ''} onChange={e => setEditCat(p => ({ ...p, name: e.target.value }))} placeholder="Назва"
              className="w-full px-3 py-2.5 rounded-xl border border-corp-border text-sm mb-3 focus:outline-none focus:border-corp-primary" />
            <input value={editCat.description || ''} onChange={e => setEditCat(p => ({ ...p, description: e.target.value }))} placeholder="Опис (опціонально)"
              className="w-full px-3 py-2.5 rounded-xl border border-corp-border text-sm mb-4 focus:outline-none focus:border-corp-primary" />
            <button onClick={saveCat} className="w-full py-2.5 rounded-xl bg-corp-primary text-white font-medium text-sm hover:bg-corp-primary-hover">Зберегти</button>
          </div>
        </div>
      )}
    </div>
  )
}

// ============================================================
// SETTINGS TAB
// ============================================================
function SettingsTab() {
  const [config, setConfig] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    (async () => {
      try {
        const r = await authFetch(`${BACKEND_URL}/api/admin/settings`)
        if (r.ok) setConfig(await r.json())
        else setConfig({
          name: 'ФОП Николенко Наталя Станіславівна', tax_status: 'платник єдиного податку',
          tax_id: '', iban: '', address: 'м. Київ', signer_name: 'Николенко Н.С.', signer_role: '',
          warehouse_address: 'м. Київ, вул. Будіндустрії 4'
        })
      } catch (e) { console.error(e); setConfig({}) }
      setLoading(false)
    })()
  }, [])

  const save = async () => {
    setSaving(true)
    try {
      const r = await authFetch(`${BACKEND_URL}/api/admin/settings`, { method: 'PUT', body: JSON.stringify(config) })
      if (r.ok) toast.success('Налаштування збережено')
      else toast.error('Помилка збереження')
    } catch (e) { toast.error('Помилка') }
    setSaving(false)
  }

  if (loading || !config) return <div className="text-center py-8 text-corp-text-muted animate-pulse">Завантаження...</div>

  const set = (k, v) => setConfig(p => ({ ...p, [k]: v }))

  const fields = [
    { key: 'name', label: 'Назва ФОП / Компанії' },
    { key: 'short_name', label: 'Коротка назва (бренд)' },
    { key: 'tax_status', label: 'Податковий статус' },
    { key: 'tax_id', label: 'Код за ДРФО (ІПН)' },
    { key: 'iban', label: 'IBAN (р/р)' },
    { key: 'mfo', label: 'МФО' },
    { key: 'bank_name', label: 'Банк' },
    { key: 'address', label: 'Юридична адреса' },
    { key: 'warehouse_address', label: 'Адреса складу' },
    { key: 'phone', label: 'Телефон' },
    { key: 'email', label: 'Email' },
    { key: 'website', label: 'Вебсайт' },
    { key: 'signer_name', label: 'Підписант (ПІБ)' },
    { key: 'signer_role', label: 'Посада підписанта' },
  ]

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl border border-corp-border p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-corp-primary/10 grid place-content-center"><Settings className="w-5 h-5 text-corp-primary" /></div>
          <div>
            <div className="font-semibold text-corp-text-dark">Дані компанії</div>
            <div className="text-xs text-corp-text-muted">Використовуються у документах (кошторис, договори, акти)</div>
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {fields.map(f => (
            <div key={f.key}>
              <label className="text-xs font-medium text-corp-text-muted">{f.label}</label>
              <input value={config[f.key] || ''} onChange={e => set(f.key, e.target.value)}
                className="mt-1 w-full px-3 py-2.5 rounded-xl border border-corp-border text-sm focus:outline-none focus:border-corp-primary" />
            </div>
          ))}
        </div>
        <button onClick={save} disabled={saving}
          className="mt-6 flex items-center gap-2 px-6 py-2.5 rounded-xl bg-corp-primary text-white font-medium text-sm hover:bg-corp-primary-hover disabled:opacity-50 transition-colors"
          data-testid="save-settings">
          <Save className="w-4 h-4" /> {saving ? 'Збереження...' : 'Зберегти'}
        </button>
      </div>
    </div>
  )
}

// ============================================================
// TAB: REPORTS (Звіти)
// ============================================================
function ReportsTab() {
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedReport, setSelectedReport] = useState(null)
  
  const monthNames = ['','Січень','Лютий','Березень','Квітень','Травень','Червень','Липень','Серпень','Вересень','Жовтень','Листопад','Грудень']

  const money = (v) => {
    const n = Number(v || 0)
    return n.toLocaleString('uk-UA', { minimumFractionDigits: 0, maximumFractionDigits: 2 }) + ' грн'
  }

  const load = async () => {
    setLoading(true)
    try {
      const res = await authFetch(`${BACKEND_URL}/api/finance/monthly-reports`)
      if (res.ok) setReports(await res.json())
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const handleDelete = async (id) => {
    if (!window.confirm('Видалити звіт і відкрити місяць для повторного закриття?')) return
    try {
      const res = await authFetch(`${BACKEND_URL}/api/finance/monthly-reports/${id}`, { method: 'DELETE' })
      if (res.ok) { load(); setSelectedReport(null) }
    } catch (e) { console.error(e) }
  }

  if (selectedReport) {
    const r = selectedReport.report
    return (
      <div className="space-y-4" data-testid="report-detail">
        <button onClick={() => setSelectedReport(null)} className="flex items-center gap-1 text-sm text-corp-primary hover:underline">
          <ArrowLeft className="w-4 h-4" /> Назад до списку
        </button>
        
        <div className="bg-white rounded-xl border border-corp-border overflow-hidden">
          <div className="px-6 py-4 border-b bg-slate-50 flex items-center justify-between">
            <div>
              <h3 className="font-bold text-lg">{monthNames[selectedReport.month]} {selectedReport.year}</h3>
              <p className="text-xs text-slate-500">
                Закрив: {selectedReport.closed_by} · {selectedReport.closed_at ? new Date(selectedReport.closed_at).toLocaleString('uk-UA') : ''}
              </p>
              {selectedReport.note && <p className="text-xs text-slate-500 mt-1">{selectedReport.note}</p>}
            </div>
            <button onClick={() => handleDelete(selectedReport.id)}
              className="text-xs text-red-500 hover:text-red-700 flex items-center gap-1 border border-red-200 px-2 py-1 rounded-lg hover:bg-red-50"
              data-testid="report-delete-btn">
              <Trash2 className="w-3 h-3" /> Видалити
            </button>
          </div>

          <div className="p-6 space-y-5">
            {/* Income */}
            <div>
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-2">Доходи</h4>
              <div className="grid grid-cols-3 gap-3">
                <div className="bg-emerald-50 rounded-xl p-3 border border-emerald-100">
                  <div className="text-xs text-emerald-600">Загалом</div>
                  <div className="font-bold text-emerald-800 text-lg">{money(r.income?.total)}</div>
                </div>
                <div className="bg-slate-50 rounded-xl p-3 border border-slate-200">
                  <div className="text-xs text-slate-500">Готівка</div>
                  <div className="font-bold">{money(r.income?.cash)}</div>
                </div>
                <div className="bg-slate-50 rounded-xl p-3 border border-slate-200">
                  <div className="text-xs text-slate-500">Безготівка</div>
                  <div className="font-bold">{money(r.income?.bank)}</div>
                </div>
              </div>
              <div className="mt-2 grid grid-cols-2 sm:grid-cols-4 gap-2">
                {[
                  { key: 'rent', label: 'Оренда' },
                  { key: 'damage', label: 'Шкода' },
                  { key: 'late', label: 'Прострочка' },
                  { key: 'additional', label: 'Додатково' },
                ].map(t => {
                  const d = r.income?.by_type?.[t.key] || {}
                  return (
                    <div key={t.key} className="bg-white rounded-lg p-2 border border-slate-100 text-center">
                      <div className="text-[10px] text-slate-400">{t.label}</div>
                      <div className="font-semibold text-sm">{money(d.total)}</div>
                      <div className="text-[10px] text-slate-400">нал. {money(d.cash)} · банк {money(d.bank)}</div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Deposits */}
            <div>
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-2">Застави</h4>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <div className="bg-amber-50 rounded-xl p-3 border border-amber-100">
                  <div className="text-xs text-amber-600">Отримано</div>
                  <div className="font-bold text-amber-800">{money(r.deposits?.total_held)}</div>
                  <div className="text-[10px] text-amber-500">{r.deposits?.opened_count || 0} застав</div>
                </div>
                <div className="bg-slate-50 rounded-xl p-3 border border-slate-200">
                  <div className="text-xs text-slate-500">Утримано</div>
                  <div className="font-bold">{money(r.deposits?.total_used)}</div>
                </div>
                <div className="bg-blue-50 rounded-xl p-3 border border-blue-100">
                  <div className="text-xs text-blue-600">Повернено</div>
                  <div className="font-bold text-blue-800">{money(r.deposits?.total_refunded)}</div>
                </div>
                <div className="bg-slate-50 rounded-xl p-3 border border-slate-200">
                  <div className="text-xs text-slate-500">Закритих</div>
                  <div className="font-bold">{r.deposits?.closed_count || 0}</div>
                </div>
              </div>
            </div>

            {/* Expenses */}
            <div>
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-2">Витрати</h4>
              <div className="grid grid-cols-3 gap-3 mb-2">
                <div className="bg-rose-50 rounded-xl p-3 border border-rose-100">
                  <div className="text-xs text-rose-600">Загалом</div>
                  <div className="font-bold text-rose-800 text-lg">{money(r.expenses?.total)}</div>
                </div>
                <div className="bg-slate-50 rounded-xl p-3 border border-slate-200">
                  <div className="text-xs text-slate-500">Готівка</div>
                  <div className="font-bold">{money(r.expenses?.cash)}</div>
                </div>
                <div className="bg-slate-50 rounded-xl p-3 border border-slate-200">
                  <div className="text-xs text-slate-500">Безготівка</div>
                  <div className="font-bold">{money(r.expenses?.bank)}</div>
                </div>
              </div>
              {r.expenses?.by_category && Object.keys(r.expenses.by_category).length > 0 && (
                <div className="bg-slate-50 rounded-lg p-3 border border-slate-100 space-y-1">
                  {Object.entries(r.expenses.by_category).map(([cat, d]) => (
                    <div key={cat} className="flex justify-between text-sm">
                      <span className="text-slate-600">{cat}</span>
                      <span className="font-semibold">{money(d.total)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Refunds */}
            {(r.refunds?.total || 0) > 0 && (
              <div>
                <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-2">Повернення</h4>
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-orange-50 rounded-xl p-3 border border-orange-100">
                    <div className="text-xs text-orange-600">Загалом</div>
                    <div className="font-bold text-orange-800">{money(r.refunds?.total)}</div>
                  </div>
                  <div className="bg-slate-50 rounded-xl p-3 border border-slate-200">
                    <div className="text-xs text-slate-500">Готівка</div>
                    <div className="font-bold">{money(r.refunds?.cash)}</div>
                  </div>
                  <div className="bg-slate-50 rounded-xl p-3 border border-slate-200">
                    <div className="text-xs text-slate-500">Безготівка</div>
                    <div className="font-bold">{money(r.refunds?.bank)}</div>
                  </div>
                </div>
              </div>
            )}

            {/* Summary */}
            <div className="bg-slate-900 rounded-xl p-5 text-white">
              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wide mb-3">Підсумок</h4>
              <div className="grid grid-cols-3 gap-3">
                <div className="text-center">
                  <div className="text-xs text-slate-400">Готівка</div>
                  <div className="font-bold text-lg">{money(r.summary?.net_cash)}</div>
                </div>
                <div className="text-center">
                  <div className="text-xs text-slate-400">Безготівка</div>
                  <div className="font-bold text-lg">{money(r.summary?.net_bank)}</div>
                </div>
                <div className="text-center">
                  <div className="text-xs text-slate-400">Чистий дохід</div>
                  <div className="font-extrabold text-2xl text-emerald-400">{money(r.summary?.net_total)}</div>
                </div>
              </div>
              <div className="mt-3 text-center text-xs text-slate-400">
                Замовлень за місяць: {r.orders_count || 0} · Операцій доходу: {r.income?.count || 0}
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4" data-testid="reports-tab">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-corp-text-main flex items-center gap-2">
          <BarChart3 className="w-5 h-5" /> Місячні звіти
        </h2>
        <button onClick={load} className="text-xs text-slate-500 hover:text-slate-700 flex items-center gap-1">
          <RefreshCw className="w-3 h-3" /> Оновити
        </button>
      </div>

      {loading ? (
        <div className="text-center py-10 text-slate-500">Завантаження...</div>
      ) : reports.length === 0 ? (
        <div className="text-center py-10 bg-white rounded-xl border border-corp-border">
          <CalendarCheck className="w-10 h-10 text-slate-300 mx-auto mb-2" />
          <p className="text-sm text-slate-500">Ще немає закритих місяців</p>
          <p className="text-xs text-slate-400">Закрийте місяць у касі → "Закрити місяць"</p>
        </div>
      ) : (
        <div className="grid gap-3">
          {reports.map(report => (
            <button key={report.id}
              onClick={() => setSelectedReport(report)}
              className="w-full bg-white rounded-xl border border-corp-border p-4 hover:border-corp-primary/40 hover:shadow-sm transition-all text-left"
              data-testid={`report-item-${report.id}`}>
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-bold text-corp-text-main">{monthNames[report.month]} {report.year}</span>
                  <span className="ml-3 text-xs text-slate-400">
                    Закрив: {report.closed_by} · {report.closed_at ? new Date(report.closed_at).toLocaleDateString('uk-UA') : ''}
                  </span>
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-emerald-600 font-semibold">{money(report.report?.income?.total || 0)}</span>
                  <span className="text-rose-500">{money(report.report?.expenses?.total || 0)}</span>
                  <span className="font-bold">{money(report.report?.summary?.net_total || 0)}</span>
                  <ChevronDown className="w-4 h-4 text-slate-400" />
                </div>
              </div>
              {report.note && <p className="text-xs text-slate-400 mt-1">{report.note}</p>}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}


// ============================================================
// MAIN
// ============================================================
import OrdersManagementTab from '../components/admin/OrdersManagementTab'
import BulkProductEditor from '../components/admin/BulkProductEditor'

const TABS = [
  { key: 'orders', label: 'Замовлення', Icon: ClipboardList },
  { key: 'bulk', label: 'Масове редагування', Icon: Grid3x3 },
  { key: 'users', label: 'Користувачі', Icon: Users },
  { key: 'documents', label: 'Документи', Icon: FileText },
  { key: 'categories', label: 'Категорії', Icon: FolderTree },
  { key: 'expenses', label: 'Витрати', Icon: Receipt },
  { key: 'reports', label: 'Звіти', Icon: BarChart3 },
  { key: 'settings', label: 'Налаштування', Icon: Settings },
]

export default function AdminPanel() {
  const nav = useNavigate()
  const [activeTab, setActiveTab] = useState('orders')

  return (
    <div className="min-h-screen bg-corp-bg-page" data-testid="admin-panel">
      <CorporateHeader cabinetName="Адмін-панель" showBackButton onBackClick={() => nav('/manager')} />

      <div className="mx-auto max-w-6xl px-3 sm:px-6 py-4">
        {/* Tabs */}
        <div className="flex flex-wrap items-center gap-1 bg-white rounded-xl p-1.5 border border-corp-border mb-6">
          {TABS.map(tab => {
            const TIcon = tab.Icon; const active = activeTab === tab.key
            return (
              <button key={tab.key} onClick={() => setActiveTab(tab.key)}
                className={cls('flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all',
                  active ? 'bg-corp-primary text-white shadow-sm' : 'text-corp-text-main hover:bg-corp-bg-light'
                )} data-testid={`admin-tab-${tab.key}`}>
                <TIcon className="w-4 h-4" /> <span className="hidden sm:inline">{tab.label}</span>
              </button>
            )
          })}
        </div>

        {/* Content */}
        {activeTab === 'orders' && <OrdersManagementTab />}
        {activeTab === 'bulk' && <BulkProductEditor />}
        {activeTab === 'users' && <UsersTab />}
        {activeTab === 'documents' && <DocumentsTab />}
        {activeTab === 'categories' && <CategoriesTab />}
        {activeTab === 'expenses' && <ExpenseCatsTab />}
        {activeTab === 'reports' && <ReportsTab />}
        {activeTab === 'settings' && <SettingsTab />}
      </div>
    </div>
  )
}
