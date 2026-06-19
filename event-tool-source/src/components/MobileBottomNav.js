/**
 * Нижня навігація — 3 пункти (Правила / Мудборд / Кабінет)
 * Іконки з lucide-react.
 */
import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { BookOpen, ShoppingBag, User, Heart } from 'lucide-react';
import { useFavorites } from '../context/FavoritesContext';

const Item = ({ Icon, label, active, onClick, badge, testid, large }) => (
  <button
    type="button"
    onClick={onClick}
    className={`mobile-bottom-nav-item ${active ? 'active' : ''} ${large ? 'is-large' : ''}`}
    data-testid={testid}
    aria-label={label}
  >
    <Icon size={large ? 24 : 22} strokeWidth={2} className="mobile-bottom-nav-icon" />
    <span className="mobile-bottom-nav-label">{label}</span>
    {badge ? <span className="mobile-bottom-nav-badge">{badge}</span> : null}
  </button>
);

const MobileBottomNav = ({ onOpenCart, cartCount = 0 }) => {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { favoriteIds } = useFavorites();
  const favCount = favoriteIds.length;

  return (
    <nav className="mobile-bottom-nav" data-testid="mobile-bottom-nav">
      <Item
        Icon={BookOpen}
        label="Правила"
        active={pathname === '/rules'}
        onClick={() => navigate('/rules')}
        testid="bnav-rules"
      />
      <Item
        Icon={Heart}
        label="Обране"
        active={pathname === '/favorites'}
        onClick={() => navigate('/favorites')}
        badge={favCount > 0 ? favCount : null}
        testid="bnav-favorites"
      />
      <Item
        Icon={ShoppingBag}
        label="Мудборд"
        active={false}
        onClick={onOpenCart}
        badge={cartCount > 0 ? cartCount : null}
        large
        testid="bnav-cart"
      />
      <Item
        Icon={User}
        label="Кабінет"
        active={pathname === '/profile'}
        onClick={() => navigate('/profile')}
        testid="bnav-profile"
      />
    </nav>
  );
};

export default MobileBottomNav;
