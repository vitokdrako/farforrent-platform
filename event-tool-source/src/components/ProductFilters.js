import React from 'react';
import './ProductFilters.css';

const ProductFilters = ({ 
  categories,
  subcategories,
  colors,
  selectedCategory,
  selectedSubcategory,
  selectedColor,
  onCategoryChange,
  onSubcategoryChange,
  onColorChange
}) => {
  return (
    <div className="product-filters">
      <div className="filter-group">
        <label className="filter-label">
          Категорія
          {categories.length > 0 && (
            <span style={{marginLeft: '6px', color: '#999', fontWeight: 'normal'}}>
              ({categories.length})
            </span>
          )}
        </label>
        <select
          value={selectedCategory || ''}
          onChange={(e) => onCategoryChange(e.target.value || null)}
          className="filter-select filter-select-scrollable"
          size="1"
          title={`${categories.length} категорій доступно`}
        >
          <option value="">Всі категорії</option>
          {categories.map((cat, index) => (
            <option key={index} value={cat.name}>
              {cat.name}
            </option>
          ))}
        </select>
      </div>

      <div className="filter-group">
        <label className="filter-label">
          Підкатегорія
          {subcategories.length > 0 && (
            <span style={{marginLeft: '6px', color: '#999', fontWeight: 'normal'}}>
              ({subcategories.length})
            </span>
          )}
        </label>
        <select
          value={selectedSubcategory || ''}
          onChange={(e) => onSubcategoryChange(e.target.value || null)}
          className="filter-select filter-select-scrollable"
          disabled={!subcategories.length}
          size="1"
          title={!subcategories.length ? 'Спочатку виберіть категорію' : `${subcategories.length} підкатегорій доступно`}
        >
          <option value="">Всі підкатегорії</option>
          {subcategories.map((subcat, index) => (
            <option key={index} value={subcat}>
              {subcat}
            </option>
          ))}
        </select>
      </div>

      <div className="filter-group">
        <label className="filter-label">
          Колір
          {colors.length > 0 && (
            <span style={{marginLeft: '6px', color: '#999', fontWeight: 'normal'}}>
              ({colors.length})
            </span>
          )}
        </label>
        <select
          value={selectedColor || ''}
          onChange={(e) => onColorChange(e.target.value || null)}
          className="filter-select filter-select-scrollable"
          size="1"
          title={`${colors.length} кольорів доступно`}
        >
          <option value="">Всі кольори</option>
          {colors.map((color, index) => (
            <option key={index} value={color}>
              {color}
            </option>
          ))}
        </select>
      </div>

      {/* Active Filters Display */}
      <div className="filter-active-tags">
        {selectedCategory && (
          <button 
            className="filter-tag"
            onClick={() => onCategoryChange(null)}
            title="Видалити фільтр"
          >
            {selectedCategory} ✕
          </button>
        )}
        {selectedSubcategory && (
          <button 
            className="filter-tag"
            onClick={() => onSubcategoryChange(null)}
            title="Видалити фільтр"
          >
            {selectedSubcategory} ✕
          </button>
        )}
        {selectedColor && (
          <button 
            className="filter-tag"
            onClick={() => onColorChange(null)}
            title="Видалити фільтр"
          >
            {selectedColor} ✕
          </button>
        )}
        {(selectedCategory || selectedSubcategory || selectedColor) && (
          <button 
            className="filter-tag filter-tag-clear"
            onClick={() => {
              onCategoryChange(null);
              onSubcategoryChange(null);
              onColorChange(null);
            }}
            title="Очистити всі фільтри"
          >
            Очистити всі
          </button>
        )}
      </div>
    </div>
  );
};

export default ProductFilters;
