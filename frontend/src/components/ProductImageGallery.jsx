import React, { useState, useEffect, useRef } from 'react';
import { Upload, X, Star, Loader2, Image as ImageIcon, Trash2 } from 'lucide-react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL || '';

/**
 * ProductImageGallery — drag&drop кількох фото для товару
 * Props:
 *   productId (number) — обов'язково
 *   onChange (fn)      — викликається після успіх. операції
 *   compact (bool)     — компактний режим без заголовку
 */
export default function ProductImageGallery({ productId, onChange = null, compact = false }) {
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (productId) loadImages();
  }, [productId]);

  async function loadImages() {
    if (!productId) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/products/${productId}/images`);
      setImages(r.data?.images || []);
    } catch (e) {
      console.error('Load images error:', e);
    } finally {
      setLoading(false);
    }
  }

  async function uploadFiles(files) {
    if (!productId || !files?.length) return;
    setUploading(true);
    try {
      const formData = new FormData();
      Array.from(files).forEach((f) => formData.append('files', f));

      const r = await axios.post(
        `${API}/api/products/${productId}/images`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );

      if (r.data?.failed?.length > 0) {
        const errs = r.data.failed.map((e) => `${e.filename}: ${e.error}`).join('\n');
        alert(`Деякі файли не завантажились:\n${errs}`);
      }

      await loadImages();
      onChange?.();
    } catch (e) {
      console.error('Upload error:', e);
      alert(`Помилка завантаження: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setUploading(false);
    }
  }

  async function deleteImage(imageId) {
    if (!window.confirm('Видалити це фото?')) return;
    try {
      await axios.delete(`${API}/api/product-images/${imageId}`);
      await loadImages();
      onChange?.();
    } catch (e) {
      alert(`Помилка видалення: ${e?.response?.data?.detail || e.message}`);
    }
  }

  async function setPrimary(imageId) {
    try {
      await axios.put(`${API}/api/product-images/${imageId}/primary`);
      await loadImages();
      onChange?.();
    } catch (e) {
      alert(`Помилка: ${e?.response?.data?.detail || e.message}`);
    }
  }

  function handleDrop(e) {
    e.preventDefault();
    setDragOver(false);
    uploadFiles(e.dataTransfer.files);
  }

  function getImageUrl(url) {
    if (!url) return null;
    if (url.startsWith('http')) return url;
    if (url.startsWith('/')) return `${API}${url}`;
    return `${API}/${url}`;
  }

  return (
    <div className="space-y-3" data-testid="product-image-gallery">
      {!compact && (
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
            <ImageIcon className="w-4 h-4" /> Фотографії товару ({images.length})
          </h3>
        </div>
      )}

      {/* Drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`
          border-2 border-dashed rounded-lg p-4 sm:p-6 text-center cursor-pointer transition-colors
          ${dragOver ? 'border-corp-primary bg-corp-primary/5' : 'border-slate-300 bg-slate-50 hover:bg-slate-100'}
        `}
        data-testid="image-drop-zone"
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/*"
          className="hidden"
          onChange={(e) => uploadFiles(e.target.files)}
        />
        {uploading ? (
          <div className="flex items-center justify-center gap-2 text-slate-600">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span className="text-sm">Завантаження…</span>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-1 text-slate-600">
            <Upload className="w-6 h-6" />
            <p className="text-sm font-medium">Перетягніть фото сюди або натисніть</p>
            <p className="text-xs text-slate-500">Можна кілька файлів одразу. JPG, PNG, WebP до 10 MB.</p>
          </div>
        )}
      </div>

      {/* Image grid */}
      {loading ? (
        <div className="text-center py-6 text-slate-500 text-sm">Завантаження фото…</div>
      ) : images.length === 0 ? (
        <div className="text-center py-6 text-slate-400 text-sm italic">Поки немає фото</div>
      ) : (
        <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-2 sm:gap-3">
          {images.map((img) => (
            <div
              key={img.id}
              className={`
                relative group rounded-lg overflow-hidden border-2 transition-all
                ${img.is_primary ? 'border-corp-primary ring-2 ring-corp-primary/30' : 'border-slate-200 hover:border-slate-400'}
              `}
              data-testid={`image-tile-${img.id}`}
            >
              <div className="aspect-square bg-slate-100">
                <img
                  src={getImageUrl(img.image_url)}
                  alt=""
                  className="w-full h-full object-cover"
                  loading="lazy"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none';
                  }}
                />
              </div>

              {/* Primary badge */}
              {img.is_primary && (
                <span className="absolute top-1 left-1 inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-corp-primary text-white shadow">
                  <Star className="w-3 h-3 fill-current" /> Гол.
                </span>
              )}

              {/* Source badge */}
              {img.source === 'opencart' && (
                <span className="absolute top-1 right-1 px-1.5 py-0.5 rounded text-[9px] font-semibold bg-sky-600 text-white shadow">
                  OC
                </span>
              )}

              {/* Hover actions */}
              <div className="absolute inset-0 bg-black/0 group-hover:bg-black/50 transition-colors flex items-center justify-center gap-1 opacity-0 group-hover:opacity-100">
                {!img.is_primary && img.id > 0 && (
                  <button
                    onClick={() => setPrimary(img.id)}
                    className="p-1.5 rounded bg-white text-corp-primary hover:bg-corp-primary hover:text-white transition-colors"
                    title="Зробити головним"
                    data-testid={`btn-primary-${img.id}`}
                  >
                    <Star className="w-3.5 h-3.5" />
                  </button>
                )}
                {img.id > 0 && (
                  <button
                    onClick={() => deleteImage(img.id)}
                    className="p-1.5 rounded bg-white text-red-600 hover:bg-red-600 hover:text-white transition-colors"
                    title="Видалити"
                    data-testid={`btn-delete-${img.id}`}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
