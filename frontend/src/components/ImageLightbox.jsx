/**
 * ImageLightbox — повноекранне збільшене зображення.
 * Використання:
 *   const [lightbox, setLightbox] = useState(null)
 *   <img onClick={() => setLightbox({ src, alt })} />
 *   {lightbox && <ImageLightbox {...lightbox} onClose={() => setLightbox(null)} />}
 */
import React, { useEffect } from 'react'
import { X } from 'lucide-react'

export default function ImageLightbox({ src, alt, onClose }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    // блокуємо скрол фону
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
    }
  }, [onClose])

  if (!src) return null

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4 print:hidden"
      onClick={onClose}
      data-testid="image-lightbox"
    >
      <div className="absolute inset-0 bg-black/85 backdrop-blur-sm" />
      <button
        onClick={onClose}
        className="absolute top-4 right-4 z-10 bg-white/10 hover:bg-white/20 text-white rounded-full p-2 transition"
        aria-label="Закрити"
        data-testid="image-lightbox-close"
      >
        <X className="w-6 h-6" />
      </button>
      <img
        src={src}
        alt={alt || ''}
        onClick={(e) => e.stopPropagation()}
        className="relative max-w-full max-h-[90vh] object-contain rounded-lg shadow-2xl"
        data-testid="image-lightbox-img"
      />
      {alt && (
        <div
          onClick={(e) => e.stopPropagation()}
          className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-black/60 text-white text-sm px-4 py-2 rounded-full max-w-[90vw] truncate"
        >
          {alt}
        </div>
      )}
    </div>
  )
}
