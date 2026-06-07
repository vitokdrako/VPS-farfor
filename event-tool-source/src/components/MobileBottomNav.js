/**
 * Нижня навігація (4 пункти) — як на референсі.
 * Показується тільки на mobile (<768px) через CSS.
 */
import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

const Item = ({ icon, label, active, onClick, badge, testid }) => (
  <button
    type="button"
    onClick={onClick}
    className={`mobile-bottom-nav-item ${active ? 'active' : ''}`}
    data-testid={testid}
    aria-label={label}
  >
    <span className="mobile-bottom-nav-icon">{icon}</span>
    {badge ? <span className="mobile-bottom-nav-badge">{badge}</span> : null}
  </button>
);

const MobileBottomNav = ({ onOpenCart, cartCount = 0 }) => {
  const navigate = useNavigate();
  const { pathname } = useLocation();

  return (
    <nav className="mobile-bottom-nav" data-testid="mobile-bottom-nav">
      <Item
        icon="⌂"
        label="Каталог"
        active={pathname === '/'}
        onClick={() => navigate('/')}
        testid="bnav-home"
      />
      <Item
        icon="🛍"
        label="Мудборд"
        active={false}
        onClick={onOpenCart}
        badge={cartCount > 0 ? cartCount : null}
        testid="bnav-cart"
      />
      <Item
        icon="♡"
        label="Обране"
        active={false}
        onClick={() => navigate('/profile')}
        testid="bnav-fav"
      />
      <Item
        icon="◯"
        label="Профіль"
        active={pathname === '/profile'}
        onClick={() => navigate('/profile')}
        testid="bnav-profile"
      />
    </nav>
  );
};

export default MobileBottomNav;
