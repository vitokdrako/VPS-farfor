/**
 * Горизонтальні chips категорій — мобільний UX як на референсі.
 */
import React from 'react';

const CategoryChips = ({ categories, selectedCategory, onSelect }) => {
  return (
    <div className="category-chips" data-testid="category-chips">
      <button
        className={`category-chip ${!selectedCategory ? 'active' : ''}`}
        onClick={() => onSelect(null)}
        data-testid="category-chip-all"
      >
        Все
      </button>
      {(categories || []).map((cat) => (
        <button
          key={cat.name}
          className={`category-chip ${selectedCategory === cat.name ? 'active' : ''}`}
          onClick={() => onSelect(cat.name)}
          data-testid={`category-chip-${cat.name}`}
        >
          {cat.name}
        </button>
      ))}
    </div>
  );
};

export default CategoryChips;
