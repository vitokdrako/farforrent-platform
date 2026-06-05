import React, { useState } from 'react';
import './CreateBoardModal.css';

const CreateBoardModal = ({ onClose, onCreateBoard }) => {
  const [formData, setFormData] = useState({
    board_name: '',
    event_date: '',
    event_type: '',
    rental_start_date: '',
    rental_end_date: '',
    notes: '',
    cover_image: ''
  });

  const [imagePreview, setImagePreview] = useState(null);
  const [imageFile, setImageFile] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Create board data object, excluding empty values
    const boardData = {};
    Object.keys(formData).forEach(key => {
      if (formData[key]) {
        boardData[key] = formData[key];
      }
    });
    
    // Add image preview if exists (either from URL or file upload)
    if (imagePreview) {
      boardData.cover_image = imagePreview;
    }
    
    console.log('📤 Sending board data:', boardData);
    console.log('🖼️ Image preview:', imagePreview);
    
    onCreateBoard(boardData);
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleImageChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      // Validate file type
      if (!file.type.startsWith('image/')) {
        alert('Будь ласка, оберіть файл зображення');
        return;
      }
      
      // Validate file size (max 5MB)
      if (file.size > 5 * 1024 * 1024) {
        alert('Розмір файлу не повинен перевищувати 5MB');
        return;
      }
      
      setImageFile(file);
      
      // Create preview
      const reader = new FileReader();
      reader.onloadend = () => {
        setImagePreview(reader.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleImageUrlChange = (e) => {
    const url = e.target.value;
    
    // Clear preview if URL is empty
    if (!url) {
      setImagePreview(null);
      setImageFile(null);
      setFormData({
        ...formData,
        cover_image: ''
      });
      return;
    }
    
    // Set formData and preview
    setFormData({
      ...formData,
      cover_image: url
    });
    setImagePreview(url);
    setImageFile(null);
  };

  const handleRemoveImage = () => {
    setImagePreview(null);
    setImageFile(null);
    setFormData({
      ...formData,
      cover_image: ''
    });
  };

  return (
    <div className="modal-overlay">
      <div className="modal-container">
        <button 
          type="button"
          onClick={onClose}
          className="modal-close-btn"
        >
          ✕
        </button>
        
        <h2 className="modal-title">Створити новий івент</h2>
        
        <form onSubmit={handleSubmit} className="board-form">
          <div className="form-group">
            <label className="form-label">
              Назва івенту <span className="required">*</span>
            </label>
            <input
              type="text"
              name="board_name"
              value={formData.board_name}
              onChange={handleChange}
              placeholder="напр. Весілля Марії"
              className="form-input"
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Дата івенту</label>
            <input
              type="date"
              name="event_date"
              value={formData.event_date}
              onChange={handleChange}
              className="form-input"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Тип івенту</label>
            <select
              name="event_type"
              value={formData.event_type}
              onChange={handleChange}
              className="form-select"
            >
              <option value="">Оберіть тип</option>
              <option value="wedding">Весілля</option>
              <option value="birthday">День народження</option>
              <option value="photoshoot">Фотосесія</option>
              <option value="corporate">Корпоратив</option>
              <option value="anniversary">Ювілей</option>
              <option value="party">Вечірка</option>
              <option value="other">Інше</option>
            </select>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Початок оренди</label>
              <input
                type="date"
                name="rental_start_date"
                value={formData.rental_start_date}
                onChange={handleChange}
                className="form-input"
              />
            </div>
            <div className="form-group">
              <label className="form-label">Кінець оренди</label>
              <input
                type="date"
                name="rental_end_date"
                value={formData.rental_end_date}
                onChange={handleChange}
                className="form-input"
                min={formData.rental_start_date}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Нотатки</label>
            <textarea
              name="notes"
              value={formData.notes}
              onChange={handleChange}
              rows="3"
              className="form-textarea"
              placeholder="Додаткова інформація про івент..."
            />
          </div>

          <div className="form-group">
            <label className="form-label">Обкладинка івенту</label>
            
            {imagePreview ? (
              <div className="image-preview-container">
                <img 
                  src={imagePreview} 
                  alt="Preview" 
                  className="image-preview"
                />
                <button
                  type="button"
                  onClick={handleRemoveImage}
                  className="image-remove-btn"
                  title="Видалити зображення"
                >
                  ✕
                </button>
              </div>
            ) : (
              <div className="image-upload-area">
                <div className="upload-options">
                  <div className="upload-option">
                    <label className="upload-label">
                      <input
                        type="file"
                        accept="image/*"
                        onChange={handleImageChange}
                        className="upload-input"
                      />
                      <span className="upload-btn">
                        Завантажити з комп'ютера
                      </span>
                    </label>
                  </div>
                  
                  <div className="upload-divider">або</div>
                  
                  <div className="upload-option">
                    <input
                      type="url"
                      placeholder="https://example.com/image.jpg"
                      className="form-input"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          handleImageUrlChange({ target: { value: e.target.value } });
                        }
                      }}
                      onBlur={(e) => handleImageUrlChange(e)}
                    />
                    <span className="upload-hint">Вставте URL зображення (натисніть Enter)</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="form-actions">
            <button
              type="button"
              onClick={onClose}
              className="btn-secondary"
            >
              Скасувати
            </button>
            <button
              type="submit"
              className="btn-primary"
            >
              Створити івент
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default CreateBoardModal;
