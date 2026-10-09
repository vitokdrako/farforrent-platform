/* eslint-disable */
/**
 * ClientsTab - CRM Lite для управління клієнтами та платниками
 * Частина Finance Hub
 */
import React, { useState, useEffect, useCallback } from "react";
import { FileText, Receipt, ClipboardList, FileCheck, FileWarning, Truck, FilePlus, ScrollText, ExternalLink } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";

const cn = (...xs) => xs.filter(Boolean).join(" ");

const authFetch = async (url, options = {}) => {
  const token = localStorage.getItem("token");
  return fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
};

// ===== UI COMPONENTS =====
const Badge = ({ kind, children }) => (
  <span className={cn(
    "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
    kind === "ok" && "bg-emerald-50 text-emerald-700 border border-emerald-100",
    kind === "pending" && "bg-amber-50 text-amber-700 border border-amber-100",
    kind === "missing" && "bg-rose-50 text-rose-700 border border-rose-100",
    kind === "info" && "bg-blue-50 text-blue-700 border border-blue-100"
  )}>
    {children}
  </span>
);

const Card = ({ title, right, children, className }) => (
  <div className={cn("rounded-2xl border border-slate-200 bg-white shadow-sm", className)}>
    {(title || right) && (
      <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-slate-100">
        <div className="text-sm font-semibold text-slate-800">{title}</div>
        <div>{right}</div>
      </div>
    )}
    <div className="p-4">{children}</div>
  </div>
);

const Button = ({ children, variant = "primary", size = "md", ...props }) => (
  <button
    {...props}
    className={cn(
      "rounded-xl font-semibold transition active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed",
      size === "sm" && "h-8 px-3 text-xs",
      size === "md" && "h-10 px-4 text-sm",
      variant === "primary" && "bg-slate-900 text-white hover:bg-slate-800",
      variant === "ghost" && "bg-white text-slate-700 border border-slate-200 hover:bg-slate-50",
      variant === "success" && "bg-emerald-500 text-white hover:bg-emerald-600",
      variant === "danger" && "bg-rose-500 text-white hover:bg-rose-600",
      props.className
    )}
  >
    {children}
  </button>
);

const Input = (props) => (
  <input
    {...props}
    className={cn(
      "h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:ring-2 focus:ring-slate-200",
      props.className
    )}
  />
);

const Select = ({ value, onChange, options, placeholder }) => (
  <select
    className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:ring-2 focus:ring-slate-200"
    value={value}
    onChange={(e) => onChange(e.target.value)}
  >
    {placeholder && <option value="">{placeholder}</option>}
    {options.map((o) => (
      <option key={o.value} value={o.value}>{o.label}</option>
    ))}
  </select>
);

// ===== PAYER TYPES =====
const PAYER_TYPES = [
  { value: "individual", label: "Фізична особа" },
  { value: "fop", label: "ФОП" },
  { value: "tov", label: "ТОВ" },
  { value: "pending", label: "Вкажу пізніше" }
];

const TAX_MODES = [
  { value: "general", label: "Загальна система" },
  { value: "simplified", label: "Спрощена система" },
];

// ===== PAYER STATUS BADGE =====
const PayerStatusBadge = ({ status }) => {
  if (status === "ok") return <Badge kind="ok">✓ Є платник</Badge>;
  if (status === "pending") return <Badge kind="pending">⏳ Pending</Badge>;
  return <Badge kind="missing">⚠ Немає платника</Badge>;
};

// ===== CREATE/EDIT PAYER MODAL =====
const PayerModal = ({ isOpen, onClose, clientId, payer, onSave }) => {
  const [type, setType] = useState(payer?.type || "individual");
  const [displayName, setDisplayName] = useState(payer?.display_name || "");
  const [taxMode, setTaxMode] = useState(payer?.tax_mode || "none");
  const [legalName, setLegalName] = useState(payer?.legal_name || "");
  const [edrpou, setEdrpou] = useState(payer?.edrpou || "");
  const [iban, setIban] = useState(payer?.iban || "");
  const [bankName, setBankName] = useState(payer?.bank_name || "");
  const [address, setAddress] = useState(payer?.address || "");
  const [signatoryName, setSignatoryName] = useState(payer?.signatory_name || "");
  const [signatoryBasis, setSignatoryBasis] = useState(payer?.signatory_basis || "Статуту");
  const [emailForDocs, setEmailForDocs] = useState(payer?.email_for_docs || "");
  const [phoneForDocs, setPhoneForDocs] = useState(payer?.phone_for_docs || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (payer) {
      setType(payer.type || "individual");
      setDisplayName(payer.display_name || "");
      setTaxMode(payer.tax_mode || "none");
      setLegalName(payer.legal_name || "");
      setEdrpou(payer.edrpou || "");
      setIban(payer.iban || "");
      setBankName(payer.bank_name || "");
      setAddress(payer.address || "");
      setSignatoryName(payer.signatory_name || "");
      setSignatoryBasis(payer.signatory_basis || "Статуту");
      setEmailForDocs(payer.email_for_docs || "");
      setPhoneForDocs(payer.phone_for_docs || "");
    }
  }, [payer]);

  if (!isOpen) return null;

  const handleSave = async () => {
    if (!displayName.trim()) {
      setError("Введіть назву платника");
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const payload = {
        type,
        display_name: displayName.trim(),
        tax_mode: taxMode,
        legal_name: legalName.trim() || null,
        edrpou: edrpou.trim() || null,
        iban: iban.trim() || null,
        bank_name: bankName.trim() || null,
        address: address.trim() || null,
        signatory_name: signatoryName.trim() || null,
        signatory_basis: signatoryBasis.trim() || null,
        email_for_docs: emailForDocs.trim() || null,
        phone_for_docs: phoneForDocs.trim() || null
      };

      let res;
      if (payer?.id) {
        // Update existing
        res = await authFetch(`${BACKEND_URL}/api/payer-profiles/${payer.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload)
        });
      } else {
        // Create new
        res = await authFetch(`${BACKEND_URL}/api/payer-profiles`, {
          method: "POST",
          body: JSON.stringify(payload)
        });
      }

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Помилка збереження");
      }

      const savedPayer = await res.json();

      // If clientId provided, link payer to client
      if (clientId && !payer?.id) {
        await authFetch(`${BACKEND_URL}/api/clients/${clientId}/payers/${savedPayer.id}/link?is_default=true`, {
          method: "POST"
        });
      }

      onSave(savedPayer);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const showLegalFields = type === "fop" || type === "tov";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="bg-white rounded-2xl w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col">
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-lg font-semibold">{payer?.id ? "Редагувати платника" : "Новий платник"}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-xl">×</button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* Type */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Тип платника *</label>
            <Select value={type} onChange={setType} options={PAYER_TYPES} />
          </div>

          {/* Display Name */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Назва для відображення *</label>
            <Input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Іван Петренко / ТОВ Ромашка"
            />
          </div>

          {showLegalFields && (
            <>
              {/* Tax Mode */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Система оподаткування</label>
                <Select value={taxMode} onChange={setTaxMode} options={TAX_MODES} />
              </div>

              {/* Legal Name */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Юридична назва</label>
                <Input
                  value={legalName}
                  onChange={(e) => setLegalName(e.target.value)}
                  placeholder="ТОВ 'Ромашка'"
                />
              </div>

              {/* EDRPOU */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">ЄДРПОУ / ІПН</label>
                <Input
                  value={edrpou}
                  onChange={(e) => setEdrpou(e.target.value)}
                  placeholder="12345678"
                />
              </div>

              {/* IBAN */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">IBAN</label>
                <Input
                  value={iban}
                  onChange={(e) => setIban(e.target.value)}
                  placeholder="UA..."
                />
              </div>

              {/* Bank Name */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Назва банку</label>
                <Input
                  value={bankName}
                  onChange={(e) => setBankName(e.target.value)}
                  placeholder="ПриватБанк"
                />
              </div>

              {/* Address */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Адреса</label>
                <Input
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  placeholder="м. Київ, вул. ..."
                />
              </div>

              {/* Signatory */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Підписант</label>
                  <Input
                    value={signatoryName}
                    onChange={(e) => setSignatoryName(e.target.value)}
                    placeholder="Петренко І.І."
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">На підставі</label>
                  <Input
                    value={signatoryBasis}
                    onChange={(e) => setSignatoryBasis(e.target.value)}
                    placeholder="Статуту"
                  />
                </div>
              </div>
            </>
          )}

          {/* Contact for docs */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Email для документів</label>
              <Input
                type="email"
                value={emailForDocs}
                onChange={(e) => setEmailForDocs(e.target.value)}
                placeholder="docs@company.ua"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Телефон для документів</label>
              <Input
                value={phoneForDocs}
                onChange={(e) => setPhoneForDocs(e.target.value)}
                placeholder="+380..."
              />
            </div>
          </div>

          {error && (
            <div className="p-3 rounded-xl bg-rose-50 text-rose-700 text-sm">
              {error}
            </div>
          )}
        </div>

        <div className="px-5 py-4 border-t border-slate-100 flex gap-3">
          <Button variant="ghost" onClick={onClose} className="flex-1">Скасувати</Button>
          <Button variant="primary" onClick={handleSave} disabled={saving} className="flex-1">
            {saving ? "Збереження..." : "Зберегти"}
          </Button>
        </div>
      </div>
    </div>
  );
};

// ===== CLIENT DETAIL DRAWER =====
const ClientDetailDrawer = ({ client, onClose, onUpdate }) => {
  const [payers, setPayers] = useState([]);
  const [orders, setOrders] = useState([]);
  const [orderDocs, setOrderDocs] = useState({});
  const [showPayerModal, setShowPayerModal] = useState(false);
  const [editingPayer, setEditingPayer] = useState(null);
  const [loading, setLoading] = useState(true);
  
  // Edit client state
  const [isEditingClient, setIsEditingClient] = useState(false);
  const [editForm, setEditForm] = useState({
    full_name: '',
    phone: '',
    email: '',
    company_hint: '',
    company: '',
    notes: '',
    payer_type: '',
    tax_id: '',
    is_regular: false,
    rating: 0,
    internal_notes: '',
    instagram: ''
  });
  const [savingClient, setSavingClient] = useState(false);
  
  // Master Agreement state (client-based only)
  const [clientMA, setClientMA] = useState(null);
  const [creatingMA, setCreatingMA] = useState(false);
  const [showTerminateModal, setShowTerminateModal] = useState(false);
  const [terminateReason, setTerminateReason] = useState('');
  const [terminating, setTerminating] = useState(false);

  useEffect(() => {
    if (client?.id) {
      loadClientData();
      // Initialize edit form with client data
      setEditForm({
        full_name: client.full_name || client.name || '',
        phone: client.phone || '',
        email: client.email || '',
        company_hint: client.company_hint || '',
        company: client.company || '',
        notes: client.notes || '',
        payer_type: client.payer_type || '',
        tax_id: client.tax_id || '',
        is_regular: client.is_regular || false,
        rating: client.rating || 0,
        internal_notes: client.internal_notes || '',
        instagram: client.instagram || ''
      });
    }
  }, [client?.id]);

  // === SAVE CLIENT ===
  const handleSaveClient = async () => {
    setSavingClient(true);
    try {
      const res = await authFetch(`${BACKEND_URL}/api/clients/${client.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          full_name: editForm.full_name,
          phone: editForm.phone,
          email: editForm.email,
          company_hint: editForm.company_hint,
          company: editForm.company,
          notes: editForm.notes,
          payer_type: editForm.payer_type || null,
          tax_id: editForm.tax_id || null,
          is_regular: editForm.is_regular,
          rating: editForm.rating,
          internal_notes: editForm.internal_notes || null,
          instagram: editForm.instagram || null
        })
      });
      if (res.ok) {
        alert("✅ Клієнта оновлено");
        setIsEditingClient(false);
        onUpdate?.();
        loadClientData();
      } else {
        const err = await res.json();
        alert(`❌ Помилка: ${err.detail || 'Невідома помилка'}`);
      }
    } catch (err) {
      console.error("Error saving client:", err);
      alert("❌ Помилка збереження");
    } finally {
      setSavingClient(false);
    }
  };

  const loadClientData = async () => {
    setLoading(true);
    try {
      // Load payers (for display only, no MA logic)
      const payersRes = await authFetch(`${BACKEND_URL}/api/clients/${client.id}/payers`);
      if (payersRes.ok) {
        const data = await payersRes.json();
        setPayers(data);
      }

      // Load client's MA (new client-based approach)
      try {
        const clientMARes = await authFetch(`${BACKEND_URL}/api/agreements/client/${client.id}`);
        if (clientMARes.ok) {
          const ma = await clientMARes.json();
          setClientMA(ma);
        }
      } catch (e) {
        console.log("No client MA");
        setClientMA(null);
      }

      // Load client details with orders
      const detailRes = await authFetch(`${BACKEND_URL}/api/clients/${client.id}`);
      if (detailRes.ok) {
        const data = await detailRes.json();
        setOrders(data.recent_orders || []);
        
        // Load generated documents for all orders
        const orderIds = (data.recent_orders || []).map(o => String(o.order_id));
        if (orderIds.length > 0) {
          try {
            const docsRes = await authFetch(`${BACKEND_URL}/api/documents/batch-by-orders`, {
              method: 'POST',
              body: JSON.stringify({ order_ids: orderIds })
            });
            if (docsRes.ok) setOrderDocs(await docsRes.json());
          } catch (e) { console.warn('[ClientsTab] docs load error', e); }
        }// Merge new CRM fields from detail response into local client state
        Object.assign(client, {
          is_regular: data.is_regular,
          company: data.company,
          rating: data.rating,
          rating_labels: data.rating_labels,
          internal_notes: data.internal_notes,
          instagram: data.instagram,
          total_revenue: data.total_revenue,
          last_order_date: data.last_order_date,
          payer_type: data.payer_type,
          tax_id: data.tax_id,
          notes: data.notes
        });
        // Update edit form too
        setEditForm(prev => ({
          ...prev,
          is_regular: data.is_regular || false,
          company: data.company || '',
          rating: data.rating || 0,
          internal_notes: data.internal_notes || '',
          instagram: data.instagram || '',
          notes: data.notes || '',
          full_name: data.full_name || prev.full_name,
          phone: data.phone || prev.phone,
          email: data.email || prev.email,
          company_hint: data.company_hint || '',
          payer_type: data.payer_type || '',
          tax_id: data.tax_id || ''
        }));
      }
    } catch (err) {
      console.error("Error loading client data:", err);
    } finally {
      setLoading(false);
    }
  };

  // === MASTER AGREEMENT FUNCTIONS (Client-based) ===
  const handleCreateClientMA = async () => {
    // Show modal/prompt for executor type and date selection
    const executorChoice = window.confirm(
      "Виберіть Орендодавця:\n\n" +
      "OK = ФОП Николенко Наталя Станіславівна\n" +
      "Скасувати = ТОВ «ФАРФОР РЕНТ»"
    );
    
    const executorType = executorChoice ? "fop" : "tov";
    
    // Ask for custom date
    const today = new Date().toISOString().split('T')[0];
    const customDate = prompt("Дата договору (РРРР-ММ-ДД):", today);
    if (customDate === null) return; // Cancelled
    
    setCreatingMA(client.id);
    try {
      const res = await authFetch(`${BACKEND_URL}/api/agreements/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          client_user_id: client.id,
          executor_type: executorType,
          contract_date: customDate || today
        })
      });
      if (res.ok) {
        const data = await res.json();
        alert(`✅ Договір оренди № ${data.contract_number} створено\n\nОрендодавець: ${executorType === 'fop' ? 'ФОП Николенко' : 'ТОВ ФАРФОР РЕНТ'}`);
        loadClientData();
      } else {
        const err = await res.json();
        alert(`❌ Помилка: ${err.detail || 'Невідома помилка'}`);
      }
    } catch (err) {
      console.error("Error creating MA:", err);
      alert("❌ Помилка створення договору");
    } finally {
      setCreatingMA(null);
    }
  };

  const handleSignClientMA = async (maId) => {
    const signedBy = prompt("Хто підписує договір? (ПІБ)");
    if (!signedBy) return;
    
    try {
      const res = await authFetch(`${BACKEND_URL}/api/agreements/${maId}/sign`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ signed_by: signedBy })
      });
      if (res.ok) {
        alert("✅ Договір підписано!");
        loadClientData();
      } else {
        const err = await res.json();
        alert(`❌ Помилка: ${err.detail || 'Невідома помилка'}`);
      }
    } catch (err) {
      console.error("Error signing MA:", err);
      alert("❌ Помилка підписання");
    }
  };

  const handlePreviewMA = async (maId) => {
    // Open preview in new window
    window.open(`${BACKEND_URL}/api/agreements/${maId}/preview`, '_blank');
  };

  const handleSendMAEmail = async (maId) => {
    const email = prompt("Email для відправки:", client.email);
    if (!email) return;
    
    try {
      const res = await authFetch(`${BACKEND_URL}/api/agreements/${maId}/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email })
      });
      if (res.ok) {
        alert("✅ Договір відправлено на " + email);
      } else {
        const err = await res.json();
        alert(`❌ Помилка: ${err.detail || 'Невідома помилка'}`);
      }
    } catch (err) {
      console.error("Error sending MA:", err);
      alert("❌ Помилка відправки");
    }
  };

  const handleTerminateMA = async (maId) => {
    if (!terminateReason.trim()) {
      alert("Вкажіть причину припинення");
      return;
    }
    setTerminating(true);
    try {
      const res = await authFetch(`${BACKEND_URL}/api/agreements/${maId}/terminate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: terminateReason.trim() })
      });
      if (res.ok) {
        alert("✅ Договір припинено");
        setShowTerminateModal(false);
        setTerminateReason('');
        loadClientData();
      } else {
        const err = await res.json();
        alert(`❌ Помилка: ${err.detail || 'Невідома помилка'}`);
      }
    } catch (err) {
      console.error("Error terminating MA:", err);
      alert("❌ Помилка припинення");
    } finally {
      setTerminating(false);
    }
  };

  // === OTHER CLIENT FUNCTIONS ===
  const handleSetDefaultPayer = async (payerId) => {
    try {
      await authFetch(`${BACKEND_URL}/api/clients/${client.id}/payers/${payerId}/link?is_default=true`, {
        method: "POST"
      });
      loadClientData();
      onUpdate?.();
    } catch (err) {
      console.error("Error setting default payer:", err);
    }
  };

  const handleUnlinkPayer = async (payerId) => {
    if (!window.confirm("Відв'язати цього платника від клієнта?")) return;
    try {
      await authFetch(`${BACKEND_URL}/api/clients/${client.id}/payers/${payerId}/unlink`, {
        method: "DELETE"
      });
      loadClientData();
      onUpdate?.();
    } catch (err) {
      console.error("Error unlinking payer:", err);
    }
  };

  if (!client) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="bg-white w-full max-w-xl h-full overflow-hidden flex flex-col shadow-xl">
        {/* Header */}
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">{client.full_name || client.email}</h3>
            <p className="text-sm text-slate-500">{client.email}</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-2xl">×</button>
        </div>

        {/* Content - single scrollable view */}
        <div className="flex-1 overflow-y-auto p-5">
          {loading ? (
            <div className="flex items-center justify-center h-32 text-slate-400">
              Завантаження...
            </div>
          ) : (
            <div className="space-y-5">

              {/* === CONTACT SECTION === */}
              <div className="space-y-4">
                {/* Edit button */}
                <div className="flex justify-end">
                  <Button
                    variant={isEditingClient ? "danger" : "ghost"}
                    size="sm"
                    onClick={() => {
                      if (isEditingClient) {
                        setEditForm({
                          full_name: client.full_name || client.name || '',
                          phone: client.phone || '',
                          email: client.email || '',
                          company_hint: client.company_hint || '',
                          company: client.company || '',
                          notes: client.notes || '',
                          payer_type: client.payer_type || '',
                          tax_id: client.tax_id || '',
                          is_regular: client.is_regular || false,
                          rating: client.rating || 0,
                          internal_notes: client.internal_notes || '',
                          instagram: client.instagram || ''
                        });
                      }
                      setIsEditingClient(!isEditingClient);
                    }}
                  >
                    {isEditingClient ? "Скасувати" : "Редагувати"}
                  </Button>
                </div>

                {isEditingClient ? (
                    <div className="space-y-4 bg-blue-50 border border-blue-100 rounded-xl p-4">
                      <div className="text-sm font-medium text-blue-800 mb-2">Редагування клієнта</div>
                      
                      {/* Regular client toggle */}
                      <div className="flex items-center gap-3 bg-white rounded-lg p-3 border border-blue-100">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={editForm.is_regular}
                            onChange={(e) => setEditForm({...editForm, is_regular: e.target.checked})}
                            className="w-4 h-4 rounded border-slate-300"
                            data-testid="client-is-regular-checkbox"
                          />
                          <span className="text-sm font-medium text-slate-700">Постійний клієнт</span>
                        </label>
                        <div className="ml-auto flex items-center gap-1">
                          <span className="text-xs text-slate-500">Рейтинг:</span>
                          {[1,2,3,4,5].map(star => (
                            <button
                              key={star}
                              type="button"
                              onClick={() => setEditForm({...editForm, rating: editForm.rating === star ? 0 : star})}
                              className={cn("text-lg transition", star <= editForm.rating ? "text-amber-400" : "text-slate-300 hover:text-amber-200")}
                              data-testid={`client-rating-star-${star}`}
                            >
                              {"\u2605"}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="text-xs text-slate-600 block mb-1">Ім'я *</label>
                          <input
                            type="text"
                            value={editForm.full_name}
                            onChange={(e) => setEditForm({...editForm, full_name: e.target.value})}
                            className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm"
                            placeholder="ПІБ клієнта"
                            data-testid="client-edit-name"
                          />
                        </div>
                        <div>
                          <label className="text-xs text-slate-600 block mb-1">Телефон *</label>
                          <input
                            type="text"
                            value={editForm.phone}
                            onChange={(e) => setEditForm({...editForm, phone: e.target.value})}
                            className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm"
                            placeholder="+380..."
                            data-testid="client-edit-phone"
                          />
                        </div>
                        <div>
                          <label className="text-xs text-slate-600 block mb-1">Email</label>
                          <input
                            type="email"
                            value={editForm.email}
                            onChange={(e) => setEditForm({...editForm, email: e.target.value})}
                            className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm"
                            placeholder="email@example.com"
                            data-testid="client-edit-email"
                          />
                        </div>
                        <div>
                          <label className="text-xs text-slate-600 block mb-1">Instagram</label>
                          <input
                            type="text"
                            value={editForm.instagram}
                            onChange={(e) => setEditForm({...editForm, instagram: e.target.value})}
                            className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm"
                            placeholder="@username"
                            data-testid="client-edit-instagram"
                          />
                        </div>
                        <div>
                          <label className="text-xs text-slate-600 block mb-1">Компанія (офіційна)</label>
                          <input
                            type="text"
                            value={editForm.company}
                            onChange={(e) => setEditForm({...editForm, company: e.target.value})}
                            className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm"
                            placeholder="ТОВ / ФОП назва"
                            data-testid="client-edit-company"
                          />
                        </div>
                        <div>
                          <label className="text-xs text-slate-600 block mb-1">Компанія (підказка)</label>
                          <input
                            type="text"
                            value={editForm.company_hint}
                            onChange={(e) => setEditForm({...editForm, company_hint: e.target.value})}
                            className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm"
                            placeholder="Декор-студія Квіти"
                            data-testid="client-edit-company-hint"
                          />
                        </div>
                        <div>
                          <label className="text-xs text-slate-600 block mb-1">ЄДРПОУ/ІПН</label>
                          <input
                            type="text"
                            value={editForm.tax_id}
                            onChange={(e) => setEditForm({...editForm, tax_id: e.target.value})}
                            className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm font-mono"
                            placeholder="12345678"
                            data-testid="client-edit-tax-id"
                          />
                        </div>
                        <div>
                          <label className="text-xs text-slate-600 block mb-1">Тип платника</label>
                          <select
                            value={editForm.payer_type}
                            onChange={(e) => setEditForm({...editForm, payer_type: e.target.value})}
                            className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm"
                            data-testid="client-edit-payer-type"
                          >
                            <option value="">Не вказано</option>
                            <option value="individual">Фіз. особа</option>
                            <option value="fop">ФОП</option>
                            <option value="fop_simple">ФОП (спрощ.)</option>
                            <option value="tov">ТОВ</option>
                          </select>
                        </div>
                      </div>
                      
                      <div>
                        <label className="text-xs text-slate-600 block mb-1">Нотатки (видно в замовленнях)</label>
                        <textarea
                          value={editForm.notes}
                          onChange={(e) => setEditForm({...editForm, notes: e.target.value})}
                          className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm min-h-[60px]"
                          placeholder="Особливості клієнта..."
                          data-testid="client-edit-notes"
                        />
                      </div>
                      
                      <div>
                        <label className="text-xs text-slate-600 block mb-1">Внутрішні нотатки (тільки для менеджерів)</label>
                        <textarea
                          value={editForm.internal_notes}
                          onChange={(e) => setEditForm({...editForm, internal_notes: e.target.value})}
                          className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm min-h-[60px]"
                          placeholder="VIP, складний клієнт, потребує додаткової уваги..."
                          data-testid="client-edit-internal-notes"
                        />
                      </div>
                      
                      <Button
                        variant="success"
                        onClick={handleSaveClient}
                        disabled={savingClient || !editForm.full_name || !editForm.phone}
                        className="w-full"
                        data-testid="client-save-btn"
                      >
                        {savingClient ? "Збереження..." : "Зберегти зміни"}
                      </Button>
                    </div>
                  ) : (
                    <>
                      {/* Badges row */}
                      <div className="flex items-center gap-2 flex-wrap">
                        {client.is_regular && (
                          <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200" data-testid="client-regular-badge">
                            Постійний
                          </span>
                        )}
                        {client.payer_type && client.payer_type !== 'individual' && (
                          <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
                            {client.payer_type === 'fop' ? 'ФОП' : client.payer_type === 'fop_simple' ? 'ФОП спрощ.' : client.payer_type === 'tov' ? 'ТОВ' : client.payer_type}
                          </span>
                        )}
                        {client.rating > 0 && (
                          <span className="inline-flex items-center gap-0.5 text-sm" data-testid="client-rating-display">
                            {[1,2,3,4,5].map(s => (
                              <span key={s} className={s <= client.rating ? "text-amber-400" : "text-slate-200"}>{"\u2605"}</span>
                            ))}
                          </span>
                        )}
                        {client.total_revenue > 0 && (
                          <span className="text-xs text-slate-500 ml-auto" data-testid="client-revenue">
                            {client.total_revenue.toLocaleString('uk-UA')} грн
                          </span>
                        )}
                      </div>

                      {/* Contact info - compact grid */}
                      <div className="rounded-xl border border-slate-200 divide-y divide-slate-100 text-sm">
                        {[
                          { label: 'Телефон', value: client.phone },
                          { label: 'Email', value: client.email },
                          { label: 'Instagram', value: client.instagram },
                          { label: 'Компанія', value: client.company || client.company_hint },
                          { label: 'ЄДРПОУ/ІПН', value: client.tax_id, mono: true },
                          { label: 'Джерело', value: client.source },
                          { label: 'Останнє замовлення', value: client.last_order_date ? new Date(client.last_order_date).toLocaleDateString('uk-UA') : null },
                        ].filter(f => f.value).map(field => (
                          <div key={field.label} className="flex justify-between items-center px-4 py-2.5">
                            <span className="text-slate-500">{field.label}</span>
                            <span className={cn("text-slate-900 font-medium", field.mono && "font-mono")}>{field.value}</span>
                          </div>
                        ))}
                      </div>

                      {/* Notes - only if present */}
                      {(client.notes || client.internal_notes) && (
                        <div className="space-y-3">
                          {client.notes && (
                            <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
                              <div className="text-xs font-medium text-amber-700 mb-1">Нотатки</div>
                              <p className="text-sm text-amber-900 whitespace-pre-wrap">{client.notes}</p>
                            </div>
                          )}
                          {client.internal_notes && (
                            <div className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-3" data-testid="client-internal-notes-block">
                              <div className="text-xs font-medium text-slate-600 mb-1">Внутрішні нотатки</div>
                              <p className="text-sm text-slate-700 whitespace-pre-wrap">{client.internal_notes}</p>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Quick stats row */}
                      <div className="grid grid-cols-3 gap-3">
                        <div className="bg-slate-50 rounded-xl p-3 text-center">
                          <div className="text-xl font-bold text-slate-900">{client.orders_count || 0}</div>
                          <div className="text-xs text-slate-500">Замовлень</div>
                        </div>
                        <div className="bg-slate-50 rounded-xl p-3 text-center">
                          <div className="text-xl font-bold text-slate-900">{payers.length}</div>
                          <div className="text-xs text-slate-500">Платників</div>
                        </div>
                        <div className="bg-slate-50 rounded-xl p-3 text-center">
                          <PayerStatusBadge status={payers.some(p => p.type !== "pending") ? "ok" : (payers.length > 0 ? "pending" : "missing")} />
                        </div>
                      </div>

                      {/* MA Agreement - compact */}
                      <div className="rounded-xl border border-purple-200 bg-purple-50/50 px-4 py-3">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-medium text-purple-800">Рамковий договір</span>
                          {clientMA?.exists ? (
                            <span className={cn(
                              "text-xs px-2 py-0.5 rounded-full",
                              clientMA.status === 'signed' ? "bg-emerald-100 text-emerald-700" :
                              clientMA.status === 'sent' ? "bg-blue-100 text-blue-700" :
                              clientMA.status === 'terminated' ? "bg-rose-100 text-rose-700" :
                              "bg-amber-100 text-amber-700"
                            )}>
                              {clientMA.status === 'signed' ? 'Підписано' :
                               clientMA.status === 'sent' ? 'Відправлено' : 
                               clientMA.status === 'terminated' ? 'Припинено' : 'Чернетка'}
                            </span>
                          ) : (
                            <span className="text-xs text-slate-400">Не створено</span>
                          )}
                        </div>
                        
                        {clientMA?.exists && clientMA.status === 'terminated' ? (
                          /* Terminated agreement view */
                          <div className="mt-2">
                            <div className="text-sm font-medium text-slate-500 line-through">{clientMA.contract_number}</div>
                            {clientMA.termination_reason && (
                              <div className="text-xs text-rose-600 mt-1 bg-rose-50 rounded-lg px-2 py-1 border border-rose-100">
                                Причина: {clientMA.termination_reason}
                              </div>
                            )}
                            {clientMA.terminated_at && (
                              <div className="text-[10px] text-slate-400 mt-0.5">
                                Припинено: {new Date(clientMA.terminated_at).toLocaleDateString('uk-UA')}
                              </div>
                            )}
                            <div className="flex gap-2 mt-2">
                              <Button variant="ghost" size="sm" className="text-xs h-7" onClick={() => window.open(`${BACKEND_URL}/api/agreements/${clientMA.id}/termination-act`, '_blank')}
                                data-testid="termination-act-btn">
                                Акт розірвання
                              </Button>
                              <Button variant="ghost" size="sm" className="text-xs h-7" onClick={() => handlePreviewMA(clientMA.id)}>
                                Договір
                              </Button>
                            </div>
                            {/* Create new agreement button */}
                            <Button
                              variant="default"
                              size="sm"
                              onClick={handleCreateClientMA}
                              disabled={creatingMA === client.id}
                              className="w-full mt-3 text-xs h-9"
                              data-testid="create-new-agreement-btn"
                            >
                              {creatingMA === client.id ? "Створення..." : "Створити новий договір"}
                            </Button>
                          </div>
                        ) : clientMA?.exists ? (
                          /* Active agreement view */
                          <div className="mt-2">
                            <div className="text-sm font-medium text-slate-800">{clientMA.contract_number}</div>
                            {clientMA.valid_until && (
                              <div className="text-xs text-slate-500 mt-0.5">до {new Date(clientMA.valid_until).toLocaleDateString('uk-UA')}</div>
                            )}
                            <div className="flex gap-2 mt-2 flex-wrap">
                              <Button variant="ghost" size="sm" className="text-xs h-7" onClick={() => handlePreviewMA(clientMA.id)}>
                                Переглянути
                              </Button>
                              <Button variant="ghost" size="sm" className="text-xs h-7" onClick={() => window.open(`${BACKEND_URL}/api/agreements/${clientMA.id}/pdf`, '_blank')}>
                                PDF
                              </Button>
                              {clientMA.status === 'draft' && (
                                <Button variant="default" size="sm" className="text-xs h-7" onClick={() => handleSignClientMA(clientMA.id)}>
                                  Підписати
                                </Button>
                              )}
                              <Button variant="ghost" size="sm" className="text-xs h-7" onClick={() => handleSendMAEmail(clientMA.id)}>
                                Email
                              </Button>
                              {(clientMA.status === 'signed' || clientMA.status === 'draft' || clientMA.status === 'sent') && (
                                <Button 
                                  variant="destructive" 
                                  size="sm" 
                                  className="text-xs h-7"
                                  onClick={() => setShowTerminateModal(true)}
                                  data-testid="terminate-agreement-btn"
                                >
                                  Припинити
                                </Button>
                              )}
                            </div>
                          </div>
                        ) : (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleCreateClientMA}
                            disabled={creatingMA === client.id}
                            className="w-full mt-2 text-xs h-8 border-purple-200 text-purple-700 hover:bg-purple-100"
                          >
                            {creatingMA === client.id ? "Створення..." : "Створити договір"}
                          </Button>
                        )}
                      </div>
                      
                      {/* Terminate Modal */}
                      {showTerminateModal && clientMA?.exists && (
                        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4" onClick={(e) => e.target === e.currentTarget && setShowTerminateModal(false)}>
                          <div className="bg-white rounded-2xl w-full max-w-md shadow-xl" data-testid="terminate-modal">
                            <div className="px-5 py-4 border-b border-slate-100">
                              <h3 className="text-base font-semibold text-slate-900">Припинити договір</h3>
                              <p className="text-xs text-slate-500 mt-1">Договір №{clientMA.contract_number}</p>
                            </div>
                            <div className="p-5 space-y-4">
                              <div>
                                <label className="block text-sm font-medium text-slate-700 mb-1">Причина припинення *</label>
                                <textarea
                                  value={terminateReason}
                                  onChange={(e) => setTerminateReason(e.target.value)}
                                  placeholder="Вкажіть причину припинення договору..."
                                  className="w-full px-3 py-2 rounded-xl border border-slate-200 text-sm min-h-[80px] outline-none focus:ring-2 focus:ring-rose-200 focus:border-rose-300"
                                  data-testid="terminate-reason-input"
                                />
                              </div>
                              <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
                                <p className="text-xs text-amber-800">
                                  Після припинення буде згенеровано Акт розірвання. Ви зможете створити новий договір для цього клієнта.
                                </p>
                              </div>
                            </div>
                            <div className="px-5 py-4 border-t border-slate-100 flex gap-3">
                              <Button variant="ghost" onClick={() => { setShowTerminateModal(false); setTerminateReason(''); }} className="flex-1">
                                Скасувати
                              </Button>
                              <Button 
                                variant="destructive" 
                                onClick={() => handleTerminateMA(clientMA.id)} 
                                disabled={terminating || !terminateReason.trim()}
                                className="flex-1"
                                data-testid="terminate-confirm-btn"
                              >
                                {terminating ? "Припинення..." : "Припинити договір"}
                              </Button>
                            </div>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>

              {/* === PAYERS SECTION === */}
              <div className="border-t border-slate-100 pt-5">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-sm font-semibold text-slate-800">Платники ({payers.length})</h4>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => { setEditingPayer(null); setShowPayerModal(true); }}
                    data-testid="add-payer-drawer-btn"
                  >
                    + Додати
                  </Button>
                </div>

                {payers.length === 0 ? (
                  <div className="text-center py-4 text-slate-400 text-sm">
                    Немає платників. Додайте для генерації документів.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {payers.map((payer) => (
                      <div
                        key={payer.id}
                        className={cn(
                          "px-4 py-3 rounded-xl border transition",
                          payer.is_default
                            ? "border-emerald-200 bg-emerald-50/50"
                            : "border-slate-200"
                        )}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <span className="font-medium text-sm text-slate-900">{payer.display_name}</span>
                            <span className="text-xs text-slate-500 ml-2">
                              {PAYER_TYPES.find(t => t.value === payer.type)?.label}
                            </span>
                            {payer.edrpou && <span className="text-xs text-slate-400 ml-1 font-mono">({payer.edrpou})</span>}
                          </div>
                          {payer.is_default && <Badge kind="ok">Осн.</Badge>}
                        </div>
                        <div className="flex gap-3 mt-2">
                          <button onClick={() => { setEditingPayer(payer); setShowPayerModal(true); }} className="text-xs text-slate-500 hover:text-slate-800">
                            Редагувати
                          </button>
                          {!payer.is_default && (
                            <button onClick={() => handleSetDefaultPayer(payer.id)} className="text-xs text-emerald-600 hover:text-emerald-700">
                              Зробити основним
                            </button>
                          )}
                          <button onClick={() => handleUnlinkPayer(payer.id)} className="text-xs text-rose-500 hover:text-rose-700">
                            Відв'язати
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* === ORDERS SECTION === */}
              <div className="border-t border-slate-100 pt-5">
                <h4 className="text-sm font-semibold text-slate-800 mb-3">Замовлення ({orders.length})</h4>
                {orders.length === 0 ? (
                  <div className="text-center py-4 text-slate-400 text-sm">
                    Немає замовлень
                  </div>
                ) : (
                  <div className="space-y-2">
                    {orders.map((order) => {
                      const total = order.total_to_pay || (Number(order.total_price || 0) + Number(order.service_fee || 0));
                      const statusMap = {
                        new: "Новий", confirmed: "Підтверджений", processing: "В обробці",
                        ready: "Готовий", issued: "Видано", returned: "Повернуто",
                        completed: "Завершений", cancelled: "Скасований"
                      };
                      const statusColor = {
                        new: "bg-blue-100 text-blue-700", confirmed: "bg-indigo-100 text-indigo-700",
                        processing: "bg-yellow-100 text-yellow-700", ready: "bg-teal-100 text-teal-700",
                        issued: "bg-emerald-100 text-emerald-700", returned: "bg-slate-200 text-slate-700",
                        completed: "bg-green-100 text-green-700", cancelled: "bg-rose-100 text-rose-700"
                      };
                      return (
                        <div
                          key={order.order_id}
                          data-testid={`client-order-${order.order_id}`}
                          className="px-4 py-3 rounded-xl border border-slate-200 hover:border-slate-400 hover:shadow-sm transition"
                        >
                          <a href={`/order/${order.order_id}/estimate`} className="block cursor-pointer">
                            <div className="flex items-center justify-between">
                              <div>
                                <span className="font-mono font-semibold text-sm text-slate-900">#{order.order_number}</span>
                                <span className="text-xs text-slate-500 ml-2">
                                  {order.rental_start_date ? new Date(order.rental_start_date).toLocaleDateString("uk-UA") : "—"}
                                </span>
                              </div>
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-semibold text-slate-800">{total.toLocaleString()} грн</span>
                                <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium", statusColor[order.status] || "bg-slate-100 text-slate-600")}>
                                  {statusMap[order.status] || order.status}
                                </span>
                              </div>
                            </div>
                            {order.service_fee > 0 && (
                              <div className="text-xs text-amber-600 mt-1">
                                + {order.service_fee_name || "Дод. послуга"}: {Number(order.service_fee).toLocaleString()} грн
                              </div>
                            )}
                          </a>
                          {/* Document quick links */}
                          <div className="flex flex-wrap items-center gap-1.5 mt-2 pt-2 border-t border-slate-100">
                            <a
                              href={`${BACKEND_URL}/api/documents/estimate/${order.order_id}/preview`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-1 px-2 py-1 text-[11px] rounded-lg bg-slate-50 border border-slate-200 text-slate-600 hover:bg-slate-100 hover:text-slate-800 transition-colors"
                              data-testid={`order-${order.order_id}-estimate-link`}
                            >
                              <FileText className="w-3 h-3" />
                              Кошторис
                            </a>
                            <a
                              href={`${BACKEND_URL}/api/documents/invoice-offer/${order.order_id}/preview`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-1 px-2 py-1 text-[11px] rounded-lg bg-blue-50 border border-blue-200 text-blue-600 hover:bg-blue-100 hover:text-blue-800 transition-colors"
                              data-testid={`order-${order.order_id}-invoice-link`}
                            >
                              <Receipt className="w-3 h-3" />
                              Рахунок-оферта
                            </a>
                            {/* Generated documents (skip invoice_offer since it's shown separately above) */}
                            {(orderDocs[String(order.order_id)] || []).filter(doc => doc.doc_type !== 'invoice_offer').map(doc => {
                              const docStyles = {
                                issue_act: { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-700', hover: 'hover:bg-emerald-100 hover:text-emerald-800', Icon: ClipboardList },
                                return_act: { bg: 'bg-teal-50', border: 'border-teal-200', text: 'text-teal-700', hover: 'hover:bg-teal-100 hover:text-teal-800', Icon: FileCheck },
                                defect_act: { bg: 'bg-rose-50', border: 'border-rose-200', text: 'text-rose-600', hover: 'hover:bg-rose-100 hover:text-rose-800', Icon: FileWarning },
                                contract_rent: { bg: 'bg-violet-50', border: 'border-violet-200', text: 'text-violet-600', hover: 'hover:bg-violet-100 hover:text-violet-800', Icon: ScrollText },
                                delivery_note: { bg: 'bg-orange-50', border: 'border-orange-200', text: 'text-orange-600', hover: 'hover:bg-orange-100 hover:text-orange-800', Icon: Truck },
                                partial_return_act: { bg: 'bg-cyan-50', border: 'border-cyan-200', text: 'text-cyan-600', hover: 'hover:bg-cyan-100 hover:text-cyan-800', Icon: FilePlus },
                                deposit_refund_act: { bg: 'bg-green-50', border: 'border-green-200', text: 'text-green-600', hover: 'hover:bg-green-100 hover:text-green-800', Icon: FileCheck },
                                damage_settlement_act: { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-600', hover: 'hover:bg-amber-100 hover:text-amber-800', Icon: FileText },
                                deposit_settlement_act: { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-600', hover: 'hover:bg-amber-100 hover:text-amber-800', Icon: FileText },
                                invoice_additional: { bg: 'bg-indigo-50', border: 'border-indigo-200', text: 'text-indigo-600', hover: 'hover:bg-indigo-100 hover:text-indigo-800', Icon: Receipt },
                                invoice_legal: { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-600', hover: 'hover:bg-blue-100 hover:text-blue-800', Icon: Receipt },
                                service_act: { bg: 'bg-lime-50', border: 'border-lime-200', text: 'text-lime-600', hover: 'hover:bg-lime-100 hover:text-lime-800', Icon: FileText },
                              };
                              const s = docStyles[doc.doc_type] || { bg: 'bg-slate-50', border: 'border-slate-200', text: 'text-slate-600', hover: 'hover:bg-slate-100 hover:text-slate-800', Icon: FileText };
                              return (
                                <a
                                  key={doc.id}
                                  href={`${BACKEND_URL}${doc.preview_url}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className={cn("flex items-center gap-1 px-2 py-1 text-[11px] rounded-lg border transition-colors", s.bg, s.border, s.text, s.hover)}
                                  data-testid={`order-${order.order_id}-doc-${doc.doc_type}`}
                                >
                                  <s.Icon className="w-3 h-3" />
                                  {doc.label}
                                </a>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

            </div>
          )}
        </div>

        {/* Payer Modal */}
        <PayerModal
          isOpen={showPayerModal}
          onClose={() => { setShowPayerModal(false); setEditingPayer(null); }}
          clientId={client.id}
          payer={editingPayer}
          onSave={() => { loadClientData(); onUpdate?.(); }}
        />
      </div>
    </div>
  );
};

// ===== MAIN CLIENTS TAB COMPONENT =====
export default function ClientsTab({ onSelectClientForOrder }) {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingTimeout, setLoadingTimeout] = useState(false);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all"); // all, has_payer, no_payer
  const [selectedClient, setSelectedClient] = useState(null);
  const [showPayerModal, setShowPayerModal] = useState(false);
  const [quickCreateClientId, setQuickCreateClientId] = useState(null);

  // Loading timeout - show content after 5 seconds even if loading
  useEffect(() => {
    const timer = setTimeout(() => setLoadingTimeout(true), 5000);
    return () => clearTimeout(timer);
  }, []);

  const loadClients = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.append("search", search);
      
      const res = await authFetch(`${BACKEND_URL}/api/clients?${params}`);
      if (res.ok) {
        const data = await res.json();
        setClients(data);
      }
    } catch (err) {
      console.error("Error loading clients:", err);
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    const timeout = setTimeout(loadClients, 300);
    return () => clearTimeout(timeout);
  }, [loadClients]);

  const filteredClients = clients.filter(c => {
    if (filter === "regular") return c.is_regular;
    if (filter === "has_payer") return c.payers_count > 0;
    if (filter === "no_payer") return c.payers_count === 0;
    return true;
  });

  const getPayerStatus = (client) => {
    if (client.payers_count === 0) return "missing";
    // We don't have type info in list, assume ok if has payers
    return "ok";
  };

  return (
    <div className="space-y-4">
      {/* Header - Search & Filter */}
      <Card>
        <div className="flex flex-col sm:flex-row gap-3 items-center">
          <div className="relative flex-1 w-full">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400 pointer-events-none" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" /></svg>
            <input
              data-testid="clients-search-input"
              type="search"
              placeholder="Пошук: email, ім'я, телефон..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-11 w-full rounded-xl border-2 border-slate-300 bg-white pl-10 pr-4 text-sm outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200 placeholder:text-slate-400"
            />
          </div>
          <select
            data-testid="clients-filter-select"
            className="h-11 w-full sm:w-48 flex-shrink-0 rounded-xl border-2 border-slate-300 bg-white px-3 text-sm outline-none focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="all">Всі клієнти</option>
            <option value="regular">Постійні клієнти</option>
            <option value="has_payer">Є платник</option>
            <option value="no_payer">Без платника</option>
          </select>
        </div>
      </Card>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3">
        <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
          <div className="text-2xl font-bold text-slate-900">{clients.length}</div>
          <div className="text-xs text-slate-500">Всього</div>
        </div>
        <div className="bg-emerald-50 rounded-xl border border-emerald-200 p-4 text-center">
          <div className="text-2xl font-bold text-emerald-700">
            {clients.filter(c => c.is_regular).length}
          </div>
          <div className="text-xs text-emerald-600">Постійні</div>
        </div>
        <div className="bg-blue-50 rounded-xl border border-blue-200 p-4 text-center">
          <div className="text-2xl font-bold text-blue-700">
            {clients.filter(c => c.payers_count > 0).length}
          </div>
          <div className="text-xs text-blue-600">Є платники</div>
        </div>
        <div className="bg-rose-50 rounded-xl border border-rose-200 p-4 text-center">
          <div className="text-2xl font-bold text-rose-700">
            {clients.filter(c => c.payers_count === 0).length}
          </div>
          <div className="text-xs text-rose-600">Без платників</div>
        </div>
      </div>

      {/* Clients Table */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        {/* Table header */}
        <div className="grid grid-cols-[1fr_160px_100px_90px_100px] gap-2 px-4 py-2.5 bg-slate-50 border-b border-slate-200 text-xs font-medium text-slate-500 uppercase tracking-wide">
          <div>Клієнт</div>
          <div>Телефон</div>
          <div className="text-center">Замовл.</div>
          <div className="text-center">Платник</div>
          <div></div>
        </div>

        {loading && !loadingTimeout ? (
          <div className="flex items-center justify-center h-32 text-slate-400">
            Завантаження...
          </div>
        ) : filteredClients.length === 0 ? (
          <div className="text-center py-12 text-slate-400">
            <p className="text-sm">Клієнтів не знайдено</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {filteredClients.map((client) => (
              <div
                key={client.id}
                data-testid={`client-row-${client.id}`}
                className="grid grid-cols-[1fr_160px_100px_90px_100px] gap-2 px-4 py-2.5 hover:bg-slate-50/80 cursor-pointer transition items-center"
                onClick={() => setSelectedClient(client)}
              >
                {/* Name + badges */}
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="font-medium text-slate-900 text-sm truncate">
                      {client.full_name || client.email}
                    </span>
                    {client.is_regular && (
                      <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500 flex-shrink-0" title="Постійний" />
                    )}
                    {client.rating > 0 && (
                      <span className="text-amber-400 text-xs flex-shrink-0 leading-none" data-testid={`client-stars-${client.id}`}>
                        {Array.from({length: client.rating}, (_, i) => "\u2605").join("")}
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-slate-400 truncate">
                    {client.email}
                    {client.company && <span className="text-slate-500"> · {client.company}</span>}
                  </div>
                </div>

                {/* Phone */}
                <div className="text-sm text-slate-600 truncate">
                  {client.phone || <span className="text-slate-300">—</span>}
                </div>

                {/* Orders count */}
                <div className="text-center text-sm font-medium text-slate-700">
                  {client.orders_count || 0}
                </div>

                {/* Payer status */}
                <div className="text-center">
                  {client.payers_count > 0 ? (
                    <span className="inline-block w-5 h-5 rounded-full bg-emerald-100 text-emerald-600 text-xs leading-5 text-center" title="Є платник">&#10003;</span>
                  ) : (
                    <span className="inline-block w-5 h-5 rounded-full bg-rose-100 text-rose-500 text-xs leading-5 text-center" title="Немає платника">!</span>
                  )}
                </div>

                {/* Quick action */}
                <div className="text-right">
                  {client.payers_count === 0 && (
                    <button
                      data-testid={`add-payer-btn-${client.id}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        setQuickCreateClientId(client.id);
                        setShowPayerModal(true);
                      }}
                      className="px-2.5 py-1 text-xs font-medium bg-emerald-50 text-emerald-700 rounded-lg hover:bg-emerald-100 border border-emerald-200 transition"
                    >
                      + Платник
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
        
        {/* Footer with count */}
        {filteredClients.length > 0 && (
          <div className="px-4 py-2 bg-slate-50 border-t border-slate-200 text-xs text-slate-500">
            Показано {filteredClients.length} з {clients.length}
          </div>
        )}
      </div>

      {/* Client Detail Drawer */}
      {selectedClient && (
        <ClientDetailDrawer
          client={selectedClient}
          onClose={() => setSelectedClient(null)}
          onUpdate={loadClients}
        />
      )}

      {/* Quick Payer Modal */}
      <PayerModal
        isOpen={showPayerModal}
        onClose={() => { setShowPayerModal(false); setQuickCreateClientId(null); }}
        clientId={quickCreateClientId}
        payer={null}
        onSave={loadClients}
      />
    </div>
  );
}
