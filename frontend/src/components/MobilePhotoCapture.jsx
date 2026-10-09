import React, { useState, useRef } from 'react';
import { Camera, Upload, X, Check } from 'lucide-react';

/**
 * Universal Mobile Photo Capture Component
 * Supports:
 * - Direct camera capture (mobile)
 * - File picker (desktop/mobile)
 * - Preview before upload
 * - Multiple photos
 */

const MobilePhotoCapture = ({ 
  onPhotosCapture, 
  maxPhotos = 5,
  label = "Додати фото",
  allowMultiple = true,
  compact = false
}) => {
  const [photos, setPhotos] = useState([]);
  const [previews, setPreviews] = useState([]);
  const [isCapturing, setIsCapturing] = useState(false);
  const fileInputRef = useRef(null);
  const cameraInputRef = useRef(null);

  // Handle file selection from gallery/file picker
  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files);
    processFiles(files);
  };

  // Process selected files
  const processFiles = (files) => {
    if (!files || files.length === 0) return;

    const validFiles = files.filter(file => {
      const isImage = file.type.startsWith('image/');
      const isUnder10MB = file.size <= 10 * 1024 * 1024;
      return isImage && isUnder10MB;
    });

    if (validFiles.length === 0) {
      alert('Будь ласка, виберіть зображення до 10MB');
      return;
    }

    // Limit to maxPhotos
    const remainingSlots = maxPhotos - photos.length;
    const filesToAdd = allowMultiple 
      ? validFiles.slice(0, remainingSlots)
      : [validFiles[0]];

    // Create previews
    const newPreviews = [];
    const newPhotos = [];

    filesToAdd.forEach((file) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        newPreviews.push(reader.result);
        newPhotos.push(file);

        // When all files are read
        if (newPreviews.length === filesToAdd.length) {
          const updatedPhotos = allowMultiple ? [...photos, ...newPhotos] : newPhotos;
          const updatedPreviews = allowMultiple ? [...previews, ...newPreviews] : newPreviews;
          
          setPhotos(updatedPhotos);
          setPreviews(updatedPreviews);

          // Callback to parent
          if (onPhotosCapture) {
            onPhotosCapture(updatedPhotos);
          }
        }
      };
      reader.readAsDataURL(file);
    });
  };

  // Remove photo from list
  const removePhoto = (index) => {
    const updatedPhotos = photos.filter((_, i) => i !== index);
    const updatedPreviews = previews.filter((_, i) => i !== index);
    
    setPhotos(updatedPhotos);
    setPreviews(updatedPreviews);

    if (onPhotosCapture) {
      onPhotosCapture(updatedPhotos);
    }
  };

  // Open file picker
  const openFilePicker = () => {
    fileInputRef.current?.click();
  };

  // Open camera (mobile only)
  const openCamera = () => {
    cameraInputRef.current?.click();
  };

  const canAddMore = photos.length < maxPhotos;

  if (compact) {
    // Compact mode - inline buttons
    return (
      <div className="flex flex-wrap gap-2">
        {/* Hidden inputs */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple={allowMultiple}
          onChange={handleFileSelect}
          className="hidden"
        />
        <input
          ref={cameraInputRef}
          type="file"
          accept="image/*"
          capture="environment"
          onChange={handleFileSelect}
          className="hidden"
        />

        {/* Camera button (mobile) */}
        {canAddMore && (
          <button
            type="button"
            onClick={openCamera}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
          >
            <Camera className="w-4 h-4" />
            <span className="hidden sm:inline">Камера</span>
          </button>
        )}

        {/* Gallery button */}
        {canAddMore && (
          <button
            type="button"
            onClick={openFilePicker}
            className="flex items-center gap-2 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors text-sm"
          >
            <Upload className="w-4 h-4" />
            <span className="hidden sm:inline">Галерея</span>
          </button>
        )}

        {/* Preview thumbnails */}
        {previews.map((preview, index) => (
          <div key={index} className="relative w-16 h-16 rounded-lg overflow-hidden border-2 border-green-500">
            <img src={preview} alt={`Preview ${index + 1}`} className="w-full h-full object-cover" />
            <button
              type="button"
              onClick={() => removePhoto(index)}
              className="absolute top-0 right-0 bg-red-500 text-white p-1 rounded-bl-lg hover:bg-red-600"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        ))}

        {photos.length > 0 && (
          <div className="flex items-center text-sm text-gray-600 px-2">
            <Check className="w-4 h-4 text-green-600 mr-1" />
            {photos.length} фото
          </div>
        )}
      </div>
    );
  }

  // Full mode - card layout
  return (
    <div className="space-y-4">
      {/* Label */}
      {label && (
        <h3 className="text-lg font-semibold text-gray-900">{label}</h3>
      )}

      {/* Hidden inputs */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        multiple={allowMultiple}
        onChange={handleFileSelect}
        className="hidden"
      />
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={handleFileSelect}
        className="hidden"
      />

      {/* Buttons */}
      {canAddMore && (
        <div className="grid grid-cols-2 gap-3">
          {/* Camera button */}
          <button
            type="button"
            onClick={openCamera}
            className="flex flex-col items-center justify-center p-6 border-2 border-dashed border-blue-300 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-all"
          >
            <Camera className="w-12 h-12 text-blue-600 mb-2" />
            <span className="text-sm font-medium text-gray-700">Камера</span>
            <span className="text-xs text-gray-500 mt-1">Зробити фото</span>
          </button>

          {/* Gallery button */}
          <button
            type="button"
            onClick={openFilePicker}
            className="flex flex-col items-center justify-center p-6 border-2 border-dashed border-gray-300 rounded-lg hover:border-gray-400 hover:bg-gray-50 transition-all"
          >
            <Upload className="w-12 h-12 text-gray-600 mb-2" />
            <span className="text-sm font-medium text-gray-700">Галерея</span>
            <span className="text-xs text-gray-500 mt-1">Вибрати файл</span>
          </button>
        </div>
      )}

      {/* Photo previews */}
      {previews.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-600">
              Додано фото: {photos.length}/{maxPhotos}
            </p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
            {previews.map((preview, index) => (
              <div key={index} className="relative group">
                <div className="aspect-square rounded-lg overflow-hidden border-2 border-gray-200 hover:border-blue-500 transition-colors">
                  <img 
                    src={preview} 
                    alt={`Preview ${index + 1}`} 
                    className="w-full h-full object-cover"
                  />
                </div>
                <button
                  type="button"
                  onClick={() => removePhoto(index)}
                  className="absolute -top-2 -right-2 bg-red-500 text-white p-2 rounded-full hover:bg-red-600 transition-colors shadow-lg"
                >
                  <X className="w-4 h-4" />
                </button>
                <div className="absolute bottom-2 left-2 bg-black bg-opacity-60 text-white text-xs px-2 py-1 rounded">
                  #{index + 1}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Info */}
      {photos.length === 0 && (
        <div className="text-center py-4">
          <p className="text-sm text-gray-500">
            📸 Зробіть фото камерою або виберіть з галереї
          </p>
          <p className="text-xs text-gray-400 mt-1">
            Максимум {maxPhotos} фото, до 10MB кожне
          </p>
        </div>
      )}

      {/* Max reached */}
      {!canAddMore && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
          <p className="text-sm text-yellow-800">
            ⚠️ Досягнуто максимум фото ({maxPhotos})
          </p>
        </div>
      )}
    </div>
  );
};

export default MobilePhotoCapture;
