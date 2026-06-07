/**
 * Нижня навігація — 3 пункти (Профіль / Мудборд / Правила оренди).
 * Показується тільки на мобільному (<768px) через CSS.
 */
import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

const Item = ({ icon, label, active, onClick, badge, testid, large }) => (
  <button
    type="button"
    onClick={onClick}
    className={`mobile-bottom-nav-item ${active ? 'active' : ''} ${large ? 'is-large' : ''}`}
    data-testid={testid}
    aria-label={label}
  >
    <span className="mobile-bottom-nav-icon">{icon}</span>
    <span className="mobile-bottom-nav-label">{label}</span>
    {badge ? <span className="mobile-bottom-nav-badge">{badge}</span> : null}
  </button>
);

const MobileBottomNav = ({ onOpenCart, cartCount = 0 }) => {
  const navigate = useNavigate();
  const { pathname } = useLocation();

  return (
    <nav className="mobile-bottom-nav" data-testid="mobile-bottom-nav">
      <Item
        icon="📖"
        label="Правила"
        active={pathname === '/rules'}
        onClick={() => navigate('/rules')}
        testid="bnav-rules"
      />
      <Item
        icon="🛍"
        label="Мудборд"
        active={false}
        onClick={onOpenCart}
        badge={cartCount > 0 ? cartCount : null}
        large
        testid="bnav-cart"
      />
      <Item
        icon="👤"
        label="Кабінет"
        active={pathname === '/profile'}
        onClick={() => navigate('/profile')}
        testid="bnav-profile"
      />
    </nav>
  );
};

export default MobileBottomNav;
