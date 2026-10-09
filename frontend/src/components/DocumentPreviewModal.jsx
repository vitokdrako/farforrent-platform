/* eslint-disable */
/**
 * DocumentPreviewModal Component
 * 
 * Full-screen modal for document preview with:
 * - HTML iframe preview
 * - Sign, Download PDF, Send Email actions
 * - Manual fields form (before generation)
 */
import React, { useState, useEffect, useCallback } from 'react';
import { SignatureModal } from './SignatureCanvas';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

// Helper for auth headers
const getAuthHeaders = () => {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
};

/**
 * Manual Fields Form for document generation
 */
function ManualFieldsForm({ docType, onSubmit, onCancel, loading, initialValues = {} }) {
  const [fields, setFields] = useState({
    // Annex fields
    contact_person: initialValues.contact_person || "",
    contact_channel: initialValues.contact_channel || "Telegram",
    contact_value: initialValues.contact_value || "",
    pickup_time: initialValues.pickup_time || "17:00",
    return_time: initialValues.return_time || "10:00",
    // Return act fields
    condition_mode: initialValues.condition_mode || "ok",
    return_notes: initialValues.return_notes || "",
    defect_act_number: initialValues.defect_act_number || "",
    // Issue act fields
    issue_notes: initialValues.issue_notes || "",
    // Defect act fields
    defect_notes: initialValues.defect_notes || "",
    tenant_refused_to_sign: initialValues.tenant_refused_to_sign || false,
    refusal_witnesses: initialValues.refusal_witnesses || ""
  });
  
  const channelOptions = ["Telegram", "Viber", "WhatsApp", "Email", "Телефон"];
  const conditionOptions = [
    { value: "excellent", label: "Відмінний стан" },
    { value: "ok", label: "Справний / без зауважень" },
    { value: "damaged", label: "Є пошкодження (див. дефектний акт)" }
  ];
  
  const handleChange = (key, value) => {
    setFields(prev => ({ ...prev, [key]: value }));
  };
  
  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(fields);
  };
  
  // Document type field visibility
  const isAnnex = docType === "annex_to_contract";
  const isReturnAct = docType === "return_act";
  const isDefectAct = docType === "defect_act";
  const isIssueAct = docType === "issue_act";
  
  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* === ANNEX TO CONTRACT FIELDS === */}
      {isAnnex && (
        <>
          <div className="p-3 bg-blue-50 rounded-lg mb-4">
            <div className="text-sm font-medium text-blue-800">Додаток до договору</div>
            <div className="text-xs text-blue-600">Юридично важливі поля для додатку</div>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Контактна особа
            </label>
            <input
              type="text"
              value={fields.contact_person}
              onChange={(e) => handleChange("contact_person", e.target.value)}
              placeholder="Прізвище Ім'я"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Канал зв'язку
              </label>
              <select
                value={fields.contact_channel}
                onChange={(e) => handleChange("contact_channel", e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                {channelOptions.map(ch => (
                  <option key={ch} value={ch}>{ch}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Номер / Username
              </label>
              <input
                type="text"
                value={fields.contact_value}
                onChange={(e) => handleChange("contact_value", e.target.value)}
                placeholder="@username або +380..."
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Час отримання <span className="text-rose-500">*</span>
              </label>
              <input
                type="time"
                value={fields.pickup_time}
                onChange={(e) => handleChange("pickup_time", e.target.value)}
                required
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Час повернення <span className="text-rose-500">*</span>
              </label>
              <input
                type="time"
                value={fields.return_time}
                onChange={(e) => handleChange("return_time", e.target.value)}
                required
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </>
      )}
      
      {/* === RETURN ACT FIELDS === */}
      {isReturnAct && (
        <>
          <div className="p-3 bg-emerald-50 rounded-lg mb-4">
            <div className="text-sm font-medium text-emerald-800">Акт повернення</div>
            <div className="text-xs text-emerald-600">Зафіксуйте стан товару при поверненні</div>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Стан товару при поверненні <span className="text-rose-500">*</span>
            </label>
            <div className="space-y-2">
              {conditionOptions.map(opt => (
                <label key={opt.value} className="flex items-center gap-3 cursor-pointer p-2 rounded-lg hover:bg-slate-50">
                  <input
                    type="radio"
                    name="condition_mode"
                    value={opt.value}
                    checked={fields.condition_mode === opt.value}
                    onChange={(e) => handleChange("condition_mode", e.target.value)}
                    className="w-4 h-4 text-blue-600"
                  />
                  <span className="text-sm">{opt.label}</span>
                </label>
              ))}
            </div>
          </div>
          
          {fields.condition_mode === "damaged" && (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Номер дефектного акту
              </label>
              <input
                type="text"
                value={fields.defect_act_number}
                onChange={(e) => handleChange("defect_act_number", e.target.value)}
                placeholder="DEF-2026XXXX-XXXX"
                className="w-full px-3 py-2 border border-amber-300 bg-amber-50 rounded-lg focus:ring-2 focus:ring-amber-500"
              />
            </div>
          )}
          
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Примітки при поверненні
            </label>
            <textarea
              value={fields.return_notes}
              onChange={(e) => handleChange("return_notes", e.target.value)}
              rows={3}
              placeholder="Зауваження, коментарі щодо стану..."
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </>
      )}
      
      {/* === DEFECT ACT FIELDS === */}
      {isDefectAct && (
        <>
          <div className="p-3 bg-rose-50 rounded-lg mb-4">
            <div className="text-sm font-medium text-rose-800">Дефектний акт</div>
            <div className="text-xs text-rose-600">Фіксація пошкоджень для юридичних цілей</div>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Загальні примітки щодо пошкоджень
            </label>
            <textarea
              value={fields.defect_notes}
              onChange={(e) => handleChange("defect_notes", e.target.value)}
              rows={3}
              placeholder="Опис обставин, загальний стан товару..."
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div className="p-3 border-2 border-dashed border-amber-300 rounded-lg bg-amber-50">
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={fields.tenant_refused_to_sign}
                onChange={(e) => handleChange("tenant_refused_to_sign", e.target.checked)}
                className="w-5 h-5 text-amber-600 rounded mt-0.5"
              />
              <div>
                <span className="text-sm font-medium text-amber-800">
                  Орендар відмовився підписувати акт
                </span>
                <p className="text-xs text-amber-600 mt-1">
                  Позначте, якщо орендар відмовляється визнавати пошкодження
                </p>
              </div>
            </label>
          </div>
          
          {fields.tenant_refused_to_sign && (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Свідки відмови <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                value={fields.refusal_witnesses}
                onChange={(e) => handleChange("refusal_witnesses", e.target.value)}
                placeholder="ПІБ свідків (через кому)"
                required={fields.tenant_refused_to_sign}
                className="w-full px-3 py-2 border border-rose-300 bg-rose-50 rounded-lg focus:ring-2 focus:ring-rose-500"
              />
              <p className="text-xs text-rose-600 mt-1">
                При відмові підписувати обов'язкові свідки
              </p>
            </div>
          )}
        </>
      )}
      
      {/* === ISSUE ACT FIELDS === */}
      {isIssueAct && (
        <>
          <div className="p-3 bg-violet-50 rounded-lg mb-4">
            <div className="text-sm font-medium text-violet-800">Акт передачі</div>
            <div className="text-xs text-violet-600">Зафіксуйте стан при видачі</div>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Час видачі
            </label>
            <input
              type="time"
              value={fields.pickup_time}
              onChange={(e) => handleChange("pickup_time", e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Примітки при видачі
            </label>
            <textarea
              value={fields.issue_notes}
              onChange={(e) => handleChange("issue_notes", e.target.value)}
              rows={3}
              placeholder="Особливості стану, комплектація, зауваження..."
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </>
      )}
      
      {/* Submit */}
      <div className="flex justify-end gap-3 pt-4 border-t border-slate-200">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-lg transition"
        >
          Скасувати
        </button>
        <button
          type="submit"
          disabled={loading}
          className="px-6 py-2 text-sm font-semibold bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50"
        >
          {loading ? "Генерація..." : "Згенерувати документ"}
        </button>
      </div>
    </form>
  );
}

/**
 * Main Document Preview Modal
 */
export function DocumentPreviewModal({
  isOpen,
  onClose,
  docType,
  orderId,
  payerProfileId,
  agreementId,
  annexId,
  documentId,
  onDocumentGenerated,
  onDocumentSigned
}) {
  const [step, setStep] = useState("form"); // form | preview | signing
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [htmlContent, setHtmlContent] = useState("");
  const [docNumber, setDocNumber] = useState("");
  const [pdfUrl, setPdfUrl] = useState(null);
  const [showSignModal, setShowSignModal] = useState(false);
  const [signerRole, setSignerRole] = useState("tenant");
  
  // Email modal state
  const [showEmailModal, setShowEmailModal] = useState(false);
  const [emailForm, setEmailForm] = useState({
    to: "",
    subject: "",
    message: "",
    attachPdf: true
  });
  const [emailSending, setEmailSending] = useState(false);
  
  const DOC_TYPE_LABELS = {
    master_agreement: "Рамковий договір",
    annex_to_contract: "Додаток до договору",
    issue_act: "Акт передачі",
    return_act: "Акт повернення",
    defect_act: "Дефектний акт",
    quote: "Кошторис",
    invoice_offer: "Рахунок-оферта",
    contract_rent: "Договір оренди"
  };
  
  // Documents that need manual fields
  const NEEDS_MANUAL_FIELDS = ["annex_to_contract", "issue_act", "return_act", "defect_act"];
  
  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setError(null);
      setPdfUrl(null);
      setHtmlContent("");
      
      // If document needs manual fields, start with form
      if (NEEDS_MANUAL_FIELDS.includes(docType)) {
        setStep("form");
      } else {
        // Otherwise, generate immediately
        generateDocument({});
      }
    }
  }, [isOpen, docType]);
  
  // Generate document with manual fields
  const generateDocument = async (manualFields) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${BACKEND_URL}/api/documents/render`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getAuthHeaders()
        },
        body: JSON.stringify({
          doc_type: docType,
          order_id: orderId,
          payer_profile_id: payerProfileId,
          agreement_id: agreementId,
          annex_id: annexId,
          manual_fields: manualFields,
          include_watermark: true
        })
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || "Помилка генерації документа");
      }
      
      setHtmlContent(data.html);
      setDocNumber(data.doc_number);
      setStep("preview");
      
      if (onDocumentGenerated) {
        onDocumentGenerated(data);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  
  // Generate PDF
  const generatePdf = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${BACKEND_URL}/api/documents/generate-pdf`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getAuthHeaders()
        },
        body: JSON.stringify({
          doc_type: docType,
          order_id: orderId,
          payer_profile_id: payerProfileId,
          agreement_id: agreementId,
          annex_id: annexId
        })
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || "Помилка генерації PDF");
      }
      
      setPdfUrl(data.pdf_url);
      
      // Open PDF in new tab
      if (data.pdf_url) {
        window.open(data.pdf_url, "_blank");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  
  // Handle signature completion
  const handleSigned = (signData) => {
    setShowSignModal(false);
    
    if (onDocumentSigned) {
      onDocumentSigned(signData);
    }
    
    // Regenerate preview with signed watermark
    if (signData.fully_signed) {
      generateDocument({});
    }
  };
  
  // Send document via email
  const sendEmail = async () => {
    if (!emailForm.to) {
      setError("Вкажіть email отримувача");
      return;
    }
    
    setEmailSending(true);
    setError(null);
    
    try {
      // Get user info from localStorage
      const userStr = localStorage.getItem("user");
      const user = userStr ? JSON.parse(userStr) : {};
      
      // Use preview-email endpoint which doesn't require document in DB
      const response = await fetch(`${BACKEND_URL}/api/documents/send-preview-email`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getAuthHeaders()
        },
        body: JSON.stringify({
          to: emailForm.to,
          subject: emailForm.subject || `${DOC_TYPE_LABELS[docType]} #${docNumber}`,
          html_content: htmlContent,
          doc_type: docType,
          order_id: orderId,
          sent_by_user_id: user.id,
          sent_by_user_name: user.name || user.email
        })
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || "Помилка відправки email");
      }
      
      setShowEmailModal(false);
      setEmailForm({ to: "", subject: "", message: "", attachPdf: true });
      
      // Show success toast or notification
      alert(`Email успішно надіслано на ${emailForm.to}`);
      
    } catch (err) {
      setError(err.message);
    } finally {
      setEmailSending(false);
    }
  };
  
  if (!isOpen) return null;
  
  return (
    <div 
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div 
        className="bg-white rounded-2xl shadow-2xl w-full max-w-5xl h-[90vh] flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between shrink-0">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">
              {DOC_TYPE_LABELS[docType] || docType}
            </h2>
            {docNumber && (
              <p className="text-sm text-slate-500">№ {docNumber}</p>
            )}
          </div>
          <button 
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 transition p-2"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        
        {/* Content */}
        <div className="flex-1 overflow-hidden p-6">
          {error && (
            <div className="mb-4 p-4 bg-rose-50 border border-rose-200 rounded-xl text-sm text-rose-700">
              {error}
            </div>
          )}
          
          {/* Form Step */}
          {step === "form" && (
            <div className="max-w-lg mx-auto">
              <div className="text-center mb-6">
                <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-3">
                  <span className="text-3xl">📝</span>
                </div>
                <h3 className="text-lg font-semibold text-slate-900">
                  Заповніть додаткові поля
                </h3>
                <p className="text-sm text-slate-500 mt-1">
                  Ці дані будуть збережені в документі
                </p>
              </div>
              
              <ManualFieldsForm
                docType={docType}
                onSubmit={generateDocument}
                onCancel={onClose}
                loading={loading}
              />
            </div>
          )}
          
          {/* Preview Step */}
          {step === "preview" && (
            <div className="h-full flex flex-col">
              {/* Preview iframe */}
              <div className="flex-1 border border-slate-200 rounded-xl overflow-hidden bg-white">
                {htmlContent ? (
                  <iframe
                    srcDoc={htmlContent}
                    className="w-full h-full"
                    title="Document Preview"
                    sandbox="allow-same-origin"
                  />
                ) : (
                  <div className="flex items-center justify-center h-full text-slate-500">
                    {loading ? "Завантаження..." : "Немає даних для відображення"}
                  </div>
                )}
              </div>
            </div>
          )}
          
          {/* Loading Overlay */}
          {loading && step !== "form" && (
            <div className="absolute inset-0 bg-white/80 flex items-center justify-center">
              <div className="text-center">
                <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
                <p className="mt-3 text-slate-600">Генерація документа...</p>
              </div>
            </div>
          )}
        </div>
        
        {/* Footer Actions */}
        {step === "preview" && (
          <div className="px-6 py-4 border-t border-slate-200 flex items-center justify-between shrink-0">
            <div className="flex gap-2">
              <button
                onClick={() => setStep("form")}
                className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-lg transition"
              >
                ← Редагувати
              </button>
            </div>
            
            <div className="flex gap-3">
              {/* Email Button */}
              <button
                onClick={() => setShowEmailModal(true)}
                data-testid="send-email-btn"
                className="px-4 py-2 text-sm font-medium bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 transition"
              >
                📧 Надіслати email
              </button>
              
              {/* Print / PDF Button */}
              <button
                onClick={() => {
                  // Open HTML in new window for printing
                  const printWindow = window.open('', '_blank', 'width=800,height=600');
                  printWindow.document.write(htmlContent);
                  printWindow.document.close();
                  printWindow.focus();
                  // Auto-trigger print dialog after a short delay
                  setTimeout(() => {
                    printWindow.print();
                  }, 500);
                }}
                disabled={!htmlContent}
                data-testid="print-pdf-btn"
                className="px-4 py-2 text-sm font-medium bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition disabled:opacity-50"
              >
                🖨️ Друк / PDF
              </button>
              
              <div className="relative">
                <button
                  onClick={() => setShowSignModal(true)}
                  className="px-5 py-2 text-sm font-semibold bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition"
                >
                  ✍️ Підписати
                </button>
              </div>
            </div>
          </div>
        )}
        
        {/* Email Modal */}
        {showEmailModal && (
          <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-[60]">
            <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
              <h3 className="text-lg font-semibold mb-4">📧 Надіслати документ</h3>
              
              {error && (
                <div className="mb-4 p-3 bg-rose-50 border border-rose-200 rounded-lg text-sm text-rose-700">
                  {error}
                </div>
              )}
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Email отримувача <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="email"
                    value={emailForm.to}
                    onChange={(e) => setEmailForm(prev => ({ ...prev, to: e.target.value }))}
                    placeholder="client@example.com"
                    data-testid="email-to-input"
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Тема листа
                  </label>
                  <input
                    type="text"
                    value={emailForm.subject}
                    onChange={(e) => setEmailForm(prev => ({ ...prev, subject: e.target.value }))}
                    placeholder={`${DOC_TYPE_LABELS[docType]} #${docNumber}`}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Повідомлення
                  </label>
                  <textarea
                    value={emailForm.message}
                    onChange={(e) => setEmailForm(prev => ({ ...prev, message: e.target.value }))}
                    rows={3}
                    placeholder="Документ від FarforRent..."
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={emailForm.attachPdf}
                    onChange={(e) => setEmailForm(prev => ({ ...prev, attachPdf: e.target.checked }))}
                    className="w-4 h-4 text-blue-600 rounded"
                  />
                  <span className="text-sm text-slate-700">Додати PDF як вкладення</span>
                </label>
              </div>
              
              <div className="flex justify-end gap-3 mt-6">
                <button
                  onClick={() => {
                    setShowEmailModal(false);
                    setError(null);
                  }}
                  className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Скасувати
                </button>
                <button
                  onClick={sendEmail}
                  disabled={emailSending || !emailForm.to}
                  data-testid="send-email-submit"
                  className="px-6 py-2 text-sm font-semibold bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {emailSending ? "Надсилання..." : "Надіслати"}
                </button>
              </div>
            </div>
          </div>
        )}
        
        {/* Signature Modal */}
        <SignatureModal
          isOpen={showSignModal}
          onClose={() => setShowSignModal(false)}
          onSign={handleSigned}
          documentId={documentId || docNumber}
          signerRole={signerRole}
          title={`Підпис: ${DOC_TYPE_LABELS[docType]}`}
        />
      </div>
    </div>
  );
}

export default DocumentPreviewModal;
