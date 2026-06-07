/**
 * Горизонтальні chips категорій + підкатегорій (як у шапці маркетплейсів).
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
  categories,
  subcategories,
  selectedCategory,
  selectedSubcategory,
  onSelectCategory,
  onSelectSubcategory,
}) => {
  return (
    <div className="category-chips-wrapper" data-testid="category-chips-wrapper">
      {/* Ряд 1: категорії */}
      <div className="category-chips" data-testid="category-chips">
        <Chip
          label="Все"
          active={!selectedCategory}
          onClick={() => onSelectCategory(null)}
          testid="category-chip-all"
        />
        {(categories || []).map((cat) => (
          <Chip
            key={cat.name}
            label={cat.name}
            active={selectedCategory === cat.name}
            onClick={() => onSelectCategory(cat.name)}
            testid={`category-chip-${cat.name}`}
          />
        ))}
      </div>

      {/* Ряд 2: підкатегорії — з'являється лише якщо обрана категорія і є підкатегорії */}
      {selectedCategory && subcategories && subcategories.length > 0 && (
        <div className="subcategory-chips" data-testid="subcategory-chips">
          <Chip
            label="Всі підкатегорії"
            active={!selectedSubcategory}
            onClick={() => onSelectSubcategory(null)}
            testid="subcategory-chip-all"
          />
          {subcategories.map((sub) => (
            <Chip
              key={sub}
              label={sub}
              active={selectedSubcategory === sub}
              onClick={() => onSelectSubcategory(sub)}
              testid={`subcategory-chip-${sub}`}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default CategoryChips;
