/* eslint-disable */
/**
 * DocumentTemplatesAdmin - Адмін-панель для управління шаблонами документів
 */
import React, { useState, useEffect, useCallback } from 'react';
import { FileText, Save, RotateCcw, Eye, Code, History, ChevronDown, ChevronRight, AlertCircle, Check, Copy, X } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

// ============================================
// UI Components
// ============================================

const Card = ({ children, className = '', title, subtitle, right }) => (
  <div className={`bg-white rounded-2xl border border-gray-200 shadow-sm ${className}`}>
    {(title || right) && (
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
        <div>
          {title && <h3 className="font-semibold text-gray-900">{title}</h3>}
          {subtitle && <p className="text-sm text-gray-500 mt-0.5">{subtitle}</p>}
        </div>
        {right}
      </div>
    )}
    <div className="p-6">{children}</div>
  </div>
);

const Badge = ({ children, tone = 'neutral' }) => {
  const colors = {
    neutral: 'bg-gray-100 text-gray-700',
    success: 'bg-emerald-100 text-emerald-700',
    warning: 'bg-amber-100 text-amber-700',
    danger: 'bg-rose-100 text-rose-700',
    info: 'bg-blue-100 text-blue-700'
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colors[tone]}`}>
      {children}
    </span>
  );
};

const PrimaryBtn = ({ children, onClick, disabled, className = '' }) => (
  <button
    onClick={onClick}
    disabled={disabled}
    className={`px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-xl font-medium text-sm transition disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
  >
    {children}
  </button>
);

const GhostBtn = ({ children, onClick, disabled, className = '' }) => (
  <button
    onClick={onClick}
    disabled={disabled}
    className={`px-4 py-2 border border-gray-200 hover:bg-gray-50 text-gray-700 rounded-xl font-medium text-sm transition disabled:opacity-50 ${className}`}
  >
    {children}
  </button>
);

// ============================================
// Template Editor Component
// ============================================

const TemplateEditor = ({ template, onClose, onSave }) => {
  const [content, setContent] = useState('');
  const [originalContent, setOriginalContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [previewHtml, setPreviewHtml] = useState('');
  const [showPreview, setShowPreview] = useState(false);
  const [variables, setVariables] = useState({});
  const [backups, setBackups] = useState([]);
  const [showBackups, setShowBackups] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const getToken = () => localStorage.getItem('token');

  // Load template content
  useEffect(() => {
    const loadTemplate = async () => {
      setLoading(true);
      try {
        const response = await fetch(
          `${BACKEND_URL}/api/admin/templates/${template.doc_type}`,
          { headers: { Authorization: `Bearer ${getToken()}` } }
        );
        const data = await response.json();
        setContent(data.content);
        setOriginalContent(data.content);
        setVariables(data.variables || {});
      } catch (e) {
        setError('Помилка завантаження шаблону');
      } finally {
        setLoading(false);
      }
    };
    
    if (template) loadTemplate();
  }, [template]);

  // Load backups
  const loadBackups = async () => {
    try {
      const response = await fetch(
        `${BACKEND_URL}/api/admin/templates/${template.doc_type}/backups`,
        { headers: { Authorization: `Bearer ${getToken()}` } }
      );
      const data = await response.json();
      setBackups(data.backups || []);
    } catch (e) {
      console.error('Failed to load backups', e);
    }
  };

  // Save template
  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    
    try {
      const response = await fetch(
        `${BACKEND_URL}/api/admin/templates/${template.doc_type}`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${getToken()}`
          },
          body: JSON.stringify({ content, create_backup: true })
        }
      );
      
      if (response.ok) {
        setSuccess('Шаблон збережено');
        setOriginalContent(content);
        onSave?.();
        loadBackups();
      } else {
        throw new Error('Failed to save');
      }
    } catch (e) {
      setError('Помилка збереження');
    } finally {
      setSaving(false);
    }
  };

  // Preview template
  const handlePreview = async () => {
    try {
      const response = await fetch(
        `${BACKEND_URL}/api/admin/templates/${template.doc_type}/preview`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${getToken()}`
          },
          body: JSON.stringify({ content })
        }
      );
      const data = await response.json();
      
      if (data.success) {
        setPreviewHtml(data.html);
        setShowPreview(true);
      } else {
        setError(`Помилка превью: ${data.error}`);
      }
    } catch (e) {
      setError('Помилка генерації превью');
    }
  };

  // Restore from backup
  const handleRestore = async (backupFilename) => {
    if (!window.confirm(`Відновити з резервної копії ${backupFilename}?`)) return;
    
    try {
      const response = await fetch(
        `${BACKEND_URL}/api/admin/templates/${template.doc_type}/restore/${backupFilename}`,
        {
          method: 'POST',
          headers: { Authorization: `Bearer ${getToken()}` }
        }
      );
      
      if (response.ok) {
        setSuccess('Шаблон відновлено');
        // Reload template
        const loadResponse = await fetch(
          `${BACKEND_URL}/api/admin/templates/${template.doc_type}`,
          { headers: { Authorization: `Bearer ${getToken()}` } }
        );
        const data = await loadResponse.json();
        setContent(data.content);
        setOriginalContent(data.content);
        loadBackups();
      }
    } catch (e) {
      setError('Помилка відновлення');
    }
  };

  const hasChanges = content !== originalContent;

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-white rounded-2xl p-8">Завантаження...</div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl w-full max-w-6xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{template.name}</h2>
            <p className="text-sm text-gray-500">{template.doc_type} • {template.entity_type}</p>
          </div>
          <div className="flex items-center gap-2">
            <GhostBtn onClick={() => { loadBackups(); setShowBackups(!showBackups); }}>
              <History className="w-4 h-4 mr-1" /> Історія
            </GhostBtn>
            <GhostBtn onClick={handlePreview}>
              <Eye className="w-4 h-4 mr-1" /> Превью
            </GhostBtn>
            <PrimaryBtn onClick={handleSave} disabled={saving || !hasChanges}>
              <Save className="w-4 h-4 mr-1" /> {saving ? 'Збереження...' : 'Зберегти'}
            </PrimaryBtn>
            <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Messages */}
        {error && (
          <div className="mx-6 mt-4 p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-sm flex items-center gap-2">
            <AlertCircle className="w-4 h-4" /> {error}
            <button onClick={() => setError(null)} className="ml-auto"><X className="w-4 h-4" /></button>
          </div>
        )}
        {success && (
          <div className="mx-6 mt-4 p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-700 text-sm flex items-center gap-2">
            <Check className="w-4 h-4" /> {success}
            <button onClick={() => setSuccess(null)} className="ml-auto"><X className="w-4 h-4" /></button>
          </div>
        )}

        {/* Content */}
        <div className="flex-1 flex overflow-hidden">
          {/* Editor */}
          <div className="flex-1 flex flex-col border-r border-gray-200">
            <div className="px-4 py-2 bg-gray-50 border-b border-gray-200 text-xs font-medium text-gray-500 flex items-center gap-2">
              <Code className="w-4 h-4" /> HTML / Jinja2 Template
              {hasChanges && <Badge tone="warning">Не збережено</Badge>}
            </div>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              className="flex-1 p-4 font-mono text-sm resize-none focus:outline-none"
              placeholder="{% extends '_base.html' %}..."
              spellCheck={false}
            />
          </div>

          {/* Sidebar - Variables or Backups */}
          <div className="w-80 flex flex-col bg-gray-50">
            {showBackups ? (
              <>
                <div className="px-4 py-2 border-b border-gray-200 text-xs font-medium text-gray-500 flex items-center justify-between">
                  Резервні копії
                  <button onClick={() => setShowBackups(false)} className="text-gray-400 hover:text-gray-600">
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="flex-1 overflow-auto p-4">
                  {backups.length === 0 ? (
                    <p className="text-sm text-gray-500">Немає резервних копій</p>
                  ) : (
                    <div className="space-y-2">
                      {backups.map((b, i) => (
                        <div key={i} className="p-3 bg-white rounded-lg border border-gray-200 text-sm">
                          <div className="font-medium text-gray-700 truncate">{b.filename}</div>
                          <div className="text-xs text-gray-500 mt-1">
                            {new Date(b.created_at).toLocaleString('uk-UA')}
                          </div>
                          <button
                            onClick={() => handleRestore(b.filename)}
                            className="mt-2 text-xs text-amber-600 hover:text-amber-700"
                          >
                            <RotateCcw className="w-3 h-3 inline mr-1" /> Відновити
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </>
            ) : (
              <>
                <div className="px-4 py-2 border-b border-gray-200 text-xs font-medium text-gray-500">
                  Доступні змінні
                </div>
                <div className="flex-1 overflow-auto p-4">
                  <div className="space-y-2">
                    {Object.entries(variables).map(([key, desc]) => (
                      <div key={key} className="text-sm">
                        <code className="px-1.5 py-0.5 bg-amber-100 text-amber-800 rounded text-xs font-mono">
                          {'{{ ' + key + ' }}'}
                        </code>
                        <p className="text-xs text-gray-500 mt-0.5">{desc}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Preview Modal */}
        {showPreview && (
          <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-60 p-4">
            <div className="bg-white rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col">
              <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
                <h3 className="font-semibold">Превью документа</h3>
                <button onClick={() => setShowPreview(false)} className="p-2 hover:bg-gray-100 rounded-lg">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="flex-1 overflow-auto p-4">
                <iframe
                  srcDoc={previewHtml}
                  className="w-full h-full min-h-[600px] border border-gray-200 rounded-lg"
                  title="Preview"
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// ============================================
// Main Component
// ============================================

export default function DocumentTemplatesAdmin() {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [filter, setFilter] = useState('all');
  const [expandedTypes, setExpandedTypes] = useState({});
  const [previewTemplate, setPreviewTemplate] = useState(null);
  const [previewHtml, setPreviewHtml] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);

  const getToken = () => localStorage.getItem('token');

  // Group templates by entity_type
  const groupedTemplates = React.useMemo(() => {
    const groups = {
      order: { name: '📋 Замовлення', templates: [] },
      issue: { name: '📦 Видача', templates: [] },
      return: { name: '📥 Повернення', templates: [] },
      damage_case: { name: '⚠️ Шкода', templates: [] },
      vendor_task: { name: '🔧 Підрядники', templates: [] }
    };
    
    templates.forEach(t => {
      const type = t.entity_type || 'other';
      if (groups[type]) {
        groups[type].templates.push(t);
      }
    });
    
    return groups;
  }, [templates]);

  // Load templates
  const loadTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(
        `${BACKEND_URL}/api/admin/templates`,
        { headers: { Authorization: `Bearer ${getToken()}` } }
      );
      const data = await response.json();
      setTemplates(data.templates || []);
    } catch (e) {
      console.error('Failed to load templates', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  const toggleGroup = (type) => {
    setExpandedTypes(prev => ({ ...prev, [type]: !prev[type] }));
  };

  // Quick preview function
  const handleQuickPreview = async (template) => {
    setPreviewTemplate(template);
    setPreviewLoading(true);
    setPreviewHtml('');
    
    try {
      // Get template content
      const contentResponse = await fetch(
        `${BACKEND_URL}/api/admin/templates/${template.doc_type}`,
        { headers: { Authorization: `Bearer ${getToken()}` } }
      );
      const contentData = await contentResponse.json();
      
      // Generate preview
      const previewResponse = await fetch(
        `${BACKEND_URL}/api/admin/templates/${template.doc_type}/preview`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${getToken()}`
          },
          body: JSON.stringify({ content: contentData.content })
        }
      );
      const previewData = await previewResponse.json();
      
      if (previewData.success) {
        setPreviewHtml(previewData.html);
      } else {
        setPreviewHtml(`<div style="padding: 20px; color: red;">Помилка: ${previewData.error}</div>`);
      }
    } catch (e) {
      setPreviewHtml(`<div style="padding: 20px; color: red;">Помилка завантаження: ${e.message}</div>`);
    } finally {
      setPreviewLoading(false);
    }
  };

  const filteredTemplates = (list) => {
    if (filter === 'all') return list;
    if (filter === 'print') return list.filter(t => t.print_required);
    if (filter === 'legal') return list.filter(t => t.critical_for?.includes('legal'));
    if (filter === 'finance') return list.filter(t => t.critical_for?.includes('finance'));
    return list;
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <FileText className="w-7 h-7 text-amber-500" />
            Шаблони документів
          </h1>
          <p className="text-gray-500 mt-1">
            Редагування HTML/Jinja2 шаблонів для генерації PDF документів
          </p>
        </div>

        {/* Filters */}
        <div className="mb-6 flex gap-2">
          {[
            { value: 'all', label: 'Всі' },
            { value: 'print', label: '🖨️ З друком' },
            { value: 'legal', label: '⚖️ Юридичні' },
            { value: 'finance', label: '💰 Фінансові' },
          ].map(f => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition ${
                filter === f.value
                  ? 'bg-amber-500 text-white'
                  : 'bg-white border border-gray-200 text-gray-700 hover:bg-gray-50'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Templates List */}
        {loading ? (
          <Card>
            <div className="text-center py-8 text-gray-500">Завантаження...</div>
          </Card>
        ) : (
          <div className="space-y-4">
            {Object.entries(groupedTemplates).map(([type, group]) => {
              const filtered = filteredTemplates(group.templates);
              if (filtered.length === 0) return null;
              
              const isExpanded = expandedTypes[type] !== false;
              
              return (
                <Card key={type} className="overflow-hidden">
                  <button
                    onClick={() => toggleGroup(type)}
                    className="w-full flex items-center justify-between p-4 hover:bg-gray-50 transition"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-lg">{group.name}</span>
                      <Badge tone="neutral">{filtered.length}</Badge>
                    </div>
                    {isExpanded ? <ChevronDown className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
                  </button>
                  
                  {isExpanded && (
                    <div className="border-t border-gray-100">
                      {filtered.map((t, i) => (
                        <div
                          key={t.doc_type}
                          className={`flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition ${
                            i < filtered.length - 1 ? 'border-b border-gray-100' : ''
                          }`}
                        >
                          <div className="flex-1">
                            <div className="font-medium text-gray-900">{t.name}</div>
                            <div className="text-sm text-gray-500 flex items-center gap-2 mt-0.5">
                              <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded">{t.doc_type}</code>
                              <span>•</span>
                              <span>{t.description || 'Без опису'}</span>
                            </div>
                          </div>
                          
                          <div className="flex items-center gap-2">
                            {t.print_required && <Badge tone="info">🖨️ Друк</Badge>}
                            {t.critical_for?.includes('legal') && <Badge tone="warning">⚖️</Badge>}
                            {t.critical_for?.includes('finance') && <Badge tone="success">💰</Badge>}
                            {!t.template_exists && <Badge tone="danger">Немає шаблону</Badge>}
                            
                            {t.template_exists && (
                              <GhostBtn onClick={() => handleQuickPreview(t)}>
                                <Eye className="w-4 h-4 mr-1" /> Перегляд
                              </GhostBtn>
                            )}
                            <GhostBtn onClick={() => setSelectedTemplate(t)}>
                              <Code className="w-4 h-4 mr-1" /> Редагувати
                            </GhostBtn>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        )}

        {/* Stats */}
        <div className="mt-6 grid grid-cols-4 gap-4">
          <Card>
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-900">{templates.length}</div>
              <div className="text-sm text-gray-500">Всього шаблонів</div>
            </div>
          </Card>
          <Card>
            <div className="text-center">
              <div className="text-2xl font-bold text-amber-600">
                {templates.filter(t => t.print_required).length}
              </div>
              <div className="text-sm text-gray-500">Потребують друку</div>
            </div>
          </Card>
          <Card>
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">
                {templates.filter(t => t.critical_for?.includes('legal')).length}
              </div>
              <div className="text-sm text-gray-500">Юридичні</div>
            </div>
          </Card>
          <Card>
            <div className="text-center">
              <div className="text-2xl font-bold text-emerald-600">
                {templates.filter(t => t.template_exists).length}
              </div>
              <div className="text-sm text-gray-500">Є шаблон</div>
            </div>
          </Card>
        </div>
      </div>

      {/* Template Editor Modal */}
      {selectedTemplate && (
        <TemplateEditor
          template={selectedTemplate}
          onClose={() => setSelectedTemplate(null)}
          onSave={loadTemplates}
        />
      )}

      {/* Quick Preview Modal */}
      {previewTemplate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl w-full max-w-5xl max-h-[90vh] flex flex-col overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
              <div>
                <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <Eye className="w-5 h-5 text-amber-500" />
                  {previewTemplate.name}
                </h2>
                <p className="text-sm text-gray-500">{previewTemplate.doc_type} • Превью з тестовими даними</p>
              </div>
              <div className="flex items-center gap-2">
                <GhostBtn onClick={() => setSelectedTemplate(previewTemplate)}>
                  <Code className="w-4 h-4 mr-1" /> Редагувати
                </GhostBtn>
                <button 
                  onClick={() => { setPreviewTemplate(null); setPreviewHtml(''); }}
                  className="p-2 hover:bg-gray-100 rounded-lg"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Preview Content */}
            <div className="flex-1 overflow-auto bg-gray-100 p-4">
              {previewLoading ? (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center">
                    <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-amber-500 mx-auto mb-3"></div>
                    <p className="text-gray-500">Генерація превью...</p>
                  </div>
                </div>
              ) : (
                <div className="bg-white rounded-lg shadow-lg mx-auto" style={{ maxWidth: '210mm' }}>
                  <iframe
                    srcDoc={previewHtml}
                    className="w-full border-0"
                    style={{ minHeight: '800px' }}
                    title="Document Preview"
                  />
                </div>
              )}
            </div>

            {/* Footer with print button */}
            <div className="px-6 py-3 border-t border-gray-200 bg-gray-50 flex justify-between items-center">
              <p className="text-sm text-gray-500">
                ℹ️ Це превью з тестовими даними. Реальні документи генеруються з актуальними даними замовлення.
              </p>
              <div className="flex gap-2">
                <GhostBtn onClick={() => {
                  const printWindow = window.open('', '_blank');
                  printWindow.document.write(previewHtml);
                  printWindow.document.close();
                  printWindow.focus();
                  setTimeout(() => printWindow.print(), 500);
                }}>
                  🖨️ Друк
                </GhostBtn>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
