import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { LogOut, User, ChevronDown } from 'lucide-react';

interface CorporateHeaderProps {
  cabinetName?: string;
  showBackButton?: boolean;
  onBackClick?: () => void;
}

export default function CorporateHeader({ 
  cabinetName = 'Кабінет менеджера', 
  showBackButton = false, 
  onBackClick
}: CorporateHeaderProps) {
  const [user, setUser] = useState<any>(null);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const userData = localStorage.getItem('user');
    if (userData) {
      setUser(JSON.parse(userData));
    }
  }, []);

  // Закриття меню при кліку зовні
  useEffect(() => {
    const handleClickOutside = () => setShowUserMenu(false);
    if (showUserMenu) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [showUserMenu]);

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    navigate('/login');
  };

  const handleBack = () => {
    if (onBackClick) {
      onBackClick();
    } else if (window.history.length > 1) {
      // Step back in browser history (e.g. back to PickingList, Calendar, etc.)
      navigate(-1);
    } else {
      // Fallback if opened in a new tab without history
      navigate('/manager');
    }
  };

  const userInitial = user?.firstname?.[0] || user?.email?.[0]?.toUpperCase() || 'U';
  const userName = user?.firstname && user?.lastname 
    ? `${user.firstname} ${user.lastname}`
    : user?.email || 'Користувач';
  const userRole = user?.role === 'admin' ? 'Адмін' : user?.role === 'manager' ? 'Менеджер' : 'Реквізитор';

  return (
    <header className="corp-header sticky top-0 z-30">
      <div className="mx-auto max-w-7xl flex items-center justify-between gap-2 sm:gap-4">
        {/* Left: Logo + Title */}
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          <button 
            onClick={() => navigate('/manager')}
            className="h-8 w-8 sm:h-10 sm:w-10 rounded-full bg-corp-primary grid place-content-center text-white font-bold text-xs sm:text-sm flex-shrink-0 hover:bg-corp-primary/90 hover:scale-105 transition-all cursor-pointer"
            title="На головну"
          >
            RH
          </button>
          <button 
            onClick={() => navigate('/manager')}
            className="min-w-0 text-left hover:opacity-80 transition-opacity cursor-pointer hidden sm:block"
          >
            <h1 className="text-base sm:text-lg font-semibold text-corp-text-dark truncate">Rental Hub</h1>
            <p className="text-[10px] sm:text-xs text-corp-text-muted truncate">{cabinetName}</p>
          </button>
        </div>
        
        {/* Right: User Menu */}
        <div className="flex items-center gap-2">
          {/* Back button (if shown) */}
          {showBackButton && (
            <button 
              className="hidden sm:flex corp-btn corp-btn-secondary text-sm"
              onClick={handleBack}
            >
              ← Назад
            </button>
          )}
          
          {/* User dropdown - works on mobile and desktop */}
          <div className="relative">
            <button
              onClick={(e) => { e.stopPropagation(); setShowUserMenu(!showUserMenu); }}
              className="flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-1.5 sm:py-2 bg-corp-bg-light rounded-lg sm:rounded-corp border border-corp-border hover:bg-corp-border/50 transition-colors"
            >
              {/* Avatar */}
              <div className="h-6 w-6 sm:h-8 sm:w-8 rounded-full bg-corp-gold grid place-content-center text-white text-xs font-semibold flex-shrink-0">
                {userInitial}
              </div>
              {/* Name - hidden on very small screens */}
              <span className="hidden xs:block text-xs sm:text-sm font-medium text-corp-text-dark max-w-[80px] sm:max-w-[120px] truncate">
                {userName}
              </span>
              <ChevronDown className={`w-3.5 h-3.5 sm:w-4 sm:h-4 text-corp-text-muted transition-transform ${showUserMenu ? 'rotate-180' : ''}`} />
            </button>
            
            {/* Dropdown Menu */}
            {showUserMenu && (
              <div 
                className="absolute right-0 top-full mt-1 w-48 bg-white rounded-lg shadow-lg border border-corp-border py-1 z-50 animate-fade-in"
                onClick={(e) => e.stopPropagation()}
              >
                {/* User info */}
                <div className="px-3 py-2 border-b border-corp-border">
                  <div className="text-sm font-medium text-corp-text-dark truncate">{userName}</div>
                  <div className="text-xs text-corp-text-muted">{userRole}</div>
                </div>
                
                {/* Menu items */}
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-corp-error hover:bg-rose-50 transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                  Вийти
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
