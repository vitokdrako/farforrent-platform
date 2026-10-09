/* eslint-disable */
/**
 * BarcodeScanner - Universal QR/Barcode scanner component
 * Uses device camera to scan QR codes and barcodes
 */
import React, { useEffect, useRef, useState } from 'react'
import { Html5QrcodeScanner } from 'html5-qrcode'

export default function BarcodeScanner({ 
  isOpen, 
  onClose, 
  onScan,
  title = "Сканування штрих-коду"
}) {
  const scannerRef = useRef(null)
  const [error, setError] = useState(null)
  const [scanning, setScanning] = useState(false)
  
  useEffect(() => {
    if (!isOpen) return
    
    setScanning(true)
    setError(null)
    
    const config = {
      fps: 10,
      qrbox: { width: 250, height: 250 },
      aspectRatio: 1.0,
      formatsToSupport: [
        0,  // QR_CODE
        11, // CODE_128
        8,  // EAN_13
        9,  // EAN_8
        13, // CODE_39
        14  // CODE_93
      ]
    }
    
    const html5QrcodeScanner = new Html5QrcodeScanner(
      "qr-reader",
      config,
      false
    )
    
    const onScanSuccess = (decodedText, decodedResult) => {
      console.log(`[Scanner] Scanned: ${decodedText}`, decodedResult)
      
      // Stop scanning
      html5QrcodeScanner.clear()
      setScanning(false)
      
      // Call parent callback
      if (onScan) {
        onScan(decodedText)
      }
      
      // Close modal
      onClose()
    }
    
    const onScanError = (errorMessage) => {
      // Ignore common scanning errors (happens frequently while scanning)
      if (!errorMessage.includes('NotFoundException')) {
        console.warn(`[Scanner] Error: ${errorMessage}`)
      }
    }
    
    try {
      html5QrcodeScanner.render(onScanSuccess, onScanError)
    } catch (err) {
      console.error('[Scanner] Failed to start:', err)
      setError('Не вдалося запустити камеру. Перевірте дозволи.')
      setScanning(false)
    }
    
    // Cleanup
    return () => {
      if (html5QrcodeScanner) {
        try {
          html5QrcodeScanner.clear()
        } catch (err) {
          console.warn('[Scanner] Cleanup error:', err)
        }
      }
    }
  }, [isOpen, onScan, onClose])
  
  if (!isOpen) return null
  
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">{title}</h3>
          <button 
            onClick={onClose}
            className="text-2xl text-slate-500 hover:text-slate-700"
          >
            ✕
          </button>
        </div>
        
        {/* Scanner Container */}
        <div className="mb-4">
          <div id="qr-reader" className="rounded-lg overflow-hidden"></div>
        </div>
        
        {/* Error Message */}
        {error && (
          <div className="mb-4 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
            ⚠️ {error}
          </div>
        )}
        
        {/* Instructions */}
        <div className="text-sm text-slate-600 space-y-2">
          <p className="font-medium">📱 Інструкція:</p>
          <ul className="list-disc list-inside space-y-1 text-xs">
            <li>Наведіть камеру на штрих-код або QR-код</li>
            <li>Тримайте камеру стабільно на відстані 10-20 см</li>
            <li>Переконайтеся що код чітко видно</li>
            <li>Сканування відбувається автоматично</li>
          </ul>
        </div>
        
        {/* Manual Input */}
        <div className="mt-4 pt-4 border-t">
          <p className="text-xs text-slate-500 mb-2">Або введіть вручну:</p>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="SKU або штрих-код..."
              className="flex-1 rounded-lg border px-3 py-2 text-sm"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && e.target.value.trim()) {
                  onScan(e.target.value.trim())
                  onClose()
                }
              }}
            />
            <button
              onClick={() => {
                const input = document.querySelector('input[placeholder*="SKU"]')
                if (input && input.value.trim()) {
                  onScan(input.value.trim())
                  onClose()
                }
              }}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
            >
              OK
            </button>
          </div>
        </div>
        
        {/* Close Button */}
        <button
          onClick={onClose}
          className="mt-4 w-full rounded-lg border border-slate-300 py-2 text-sm hover:bg-slate-50"
        >
          Скасувати
        </button>
      </div>
    </div>
  )
}
