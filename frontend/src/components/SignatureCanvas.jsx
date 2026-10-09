/* eslint-disable */
/**
 * SignatureCanvas Component
 * 
 * Touch/mouse signature capture for document signing.
 * Uses react-signature-canvas library.
 */
import React, { useRef, useState, useCallback } from 'react';
import SignatureCanvas from 'react-signature-canvas';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

/**
 * Signature Pad Modal Component
 */
export function SignatureModal({ 
  isOpen, 
  onClose, 
  onSign, 
  documentId,
  signerRole = "tenant",
  signerName = "",
  title = "Підпис документа"
}) {
  const sigCanvasRef = useRef(null);
  const [isEmpty, setIsEmpty] = useState(true);
  const [signing, setSigning] = useState(false);
  const [error, setError] = useState(null);
  
  const clearSignature = useCallback(() => {
    if (sigCanvasRef.current) {
      sigCanvasRef.current.clear();
      setIsEmpty(true);
      setError(null);
    }
  }, []);
  
  const handleEnd = useCallback(() => {
    if (sigCanvasRef.current) {
      setIsEmpty(sigCanvasRef.current.isEmpty());
    }
  }, []);
  
  const handleSign = useCallback(async () => {
    if (!sigCanvasRef.current || sigCanvasRef.current.isEmpty()) {
      setError("Будь ласка, поставте підпис");
      return;
    }
    
    setSigning(true);
    setError(null);
    
    try {
      // Get signature as base64 PNG
      const signatureDataUrl = sigCanvasRef.current.toDataURL("image/png");
      
      // Send to backend
      const token = localStorage.getItem("token");
      const response = await fetch(`${BACKEND_URL}/api/documents/signatures/sign`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({
          document_id: documentId,
          signer_role: signerRole,
          signature_png_base64: signatureDataUrl,
          signer_name: signerName
        })
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || "Помилка підпису");
      }
      
      if (onSign) {
        onSign(data);
      }
      
      onClose();
    } catch (err) {
      setError(err.message || "Помилка підпису документа");
    } finally {
      setSigning(false);
    }
  }, [documentId, signerRole, signerName, onSign, onClose]);
  
  if (!isOpen) return null;
  
  return (
    <div 
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
            <button 
              onClick={onClose}
              className="text-slate-400 hover:text-slate-600 transition"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            {signerRole === "tenant" ? "Підпис орендаря" : "Підпис орендодавця"}
          </p>
        </div>
        
        {/* Signature Canvas */}
        <div className="p-6">
          <div className="border-2 border-dashed border-slate-300 rounded-xl overflow-hidden bg-slate-50">
            <SignatureCanvas
              ref={sigCanvasRef}
              penColor="#1e293b"
              canvasProps={{
                width: 450,
                height: 200,
                className: "signature-canvas w-full touch-none",
                style: { 
                  width: "100%", 
                  height: "200px",
                  touchAction: "none"
                }
              }}
              onEnd={handleEnd}
            />
          </div>
          
          <p className="text-xs text-slate-500 text-center mt-2">
            Поставте підпис у полі вище (мишкою або пальцем)
          </p>
          
          {error && (
            <div className="mt-3 p-3 bg-rose-50 border border-rose-200 rounded-lg text-sm text-rose-700">
              {error}
            </div>
          )}
        </div>
        
        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-200 flex items-center justify-between">
          <button
            onClick={clearSignature}
            className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 transition"
          >
            🗑️ Очистити
          </button>
          
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-lg transition"
            >
              Скасувати
            </button>
            <button
              onClick={handleSign}
              disabled={isEmpty || signing}
              className={`px-6 py-2 text-sm font-semibold rounded-lg transition ${
                isEmpty || signing
                  ? "bg-slate-200 text-slate-400 cursor-not-allowed"
                  : "bg-emerald-600 text-white hover:bg-emerald-700"
              }`}
            >
              {signing ? "Підписання..." : "✍️ Підписати"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Inline Signature Display (for showing existing signatures)
 */
export function SignatureDisplay({ imageUrl, signerName, signedAt, role }) {
  if (!imageUrl) {
    return (
      <div className="border border-dashed border-slate-300 rounded-lg p-4 text-center">
        <div className="text-slate-400 text-sm">Підпис відсутній</div>
        <div className="text-xs text-slate-400 mt-1">
          {role === "tenant" ? "Орендар" : "Орендодавець"}
        </div>
      </div>
    );
  }
  
  return (
    <div className="border border-slate-200 rounded-lg p-3">
      <img 
        src={imageUrl} 
        alt={`Підпис ${signerName || role}`} 
        className="max-h-16 mx-auto"
      />
      {signerName && (
        <div className="text-xs text-slate-600 text-center mt-2">{signerName}</div>
      )}
      {signedAt && (
        <div className="text-xs text-slate-400 text-center">
          Підписано: {new Date(signedAt).toLocaleString("uk-UA")}
        </div>
      )}
    </div>
  );
}

export default SignatureModal;
