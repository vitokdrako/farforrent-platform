/**
 * Горизонтальні chips категорій + підкатегорій + кольорів.
 * Підкатегорії з'являються тільки якщо активна категорія.
 */
import React from 'react';

const Chip = ({ label, active, onClick, testid }) => (
  <button
    type="button"
    className={`category-chip ${active ? 'active' : ''}`}
    onClick={onClick}
    data-testid={testid}
  >
    {label}
  </button>
);

const CategoryChips = ({
  categories, subcategories, colors,
  selectedCategory, selectedSubcategory, selectedColor,
  onSelectCategory, onSelectSubcategory, onSelectColor,
  minQuantity = 0, onMinQuantityChange, maxQuantity = 100,
}) => {
  return (
    <div className="category-chips-wrapper" data-testid="category-chips-wrapper">
      {/* Ряд 1: категорії */}
      <div className="category-chips" data-testid="category-chips">
        <Chip label="Все" active={!selectedCategory} onClick={() => onSelectCategory(null)} testid="category-chip-all" />
        {(categories || []).map((cat) => (
          <Chip key={cat.name} label={cat.name} active={selectedCategory === cat.name}
            onClick={() => onSelectCategory(cat.name)} testid={`category-chip-${cat.name}`} />
        ))}
      </div>

      {/* Ряд 2: підкатегорії — якщо є активна категорія */}
      {selectedCategory && subcategories && subcategories.length > 0 && (
        <div className="subcategory-chips" data-testid="subcategory-chips">
          <Chip label="Всі підкатегорії" active={!selectedSubcategory}
            onClick={() => onSelectSubcategory(null)} testid="subcategory-chip-all" />
          {subcategories.map((sub) => (
            <Chip key={sub} label={sub} active={selectedSubcategory === sub}
              onClick={() => onSelectSubcategory(sub)} testid={`subcategory-chip-${sub}`} />
          ))}
        </div>
      )}

      {/* Ряд 3: кольори */}
      {colors && colors.length > 0 && (
        <div className="color-chips" data-testid="color-chips">
          <Chip label="Усі кольори" active={!selectedColor}
            onClick={() => onSelectColor(null)} testid="color-chip-all" />
          {colors.map((color) => (
            <Chip key={color} label={color} active={selectedColor === color}
              onClick={() => onSelectColor(color)} testid={`color-chip-${color}`} />
          ))}
        </div>
      )}

      {/* Ряд 4: повзунок мін. кількості */}
      {onMinQuantityChange && (
        <div className="quantity-slider-row" data-testid="quantity-slider-row">
          <span className="quantity-slider-label">
            На складі: <strong>{minQuantity > 0 ? `≥ ${minQuantity}` : 'будь-яка'}</strong>
          </span>
          <input
            type="range"
            min={0}
            max={maxQuantity}
            step={1}
            value={minQuantity}
            onChange={(e) => onMinQuantityChange(Number(e.target.value))}
            data-testid="mobile-min-quantity-slider"
            className="filter-range quantity-slider-input"
            style={{ '--fill': `${(minQuantity / Math.max(1, maxQuantity)) * 100}%` }}
          />
        </div>
      )}
    </div>
  );
};

export default CategoryChips;
