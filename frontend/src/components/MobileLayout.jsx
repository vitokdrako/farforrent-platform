import React from 'react';
import { Menu, X, Home, Calendar, Package, FileText, Settings, DollarSign, AlertTriangle } from 'lucide-react';

/**
 * Mobile-responsive layout wrapper
 * Provides:
 * - Responsive navigation
 * - Mobile menu
 * - Adaptive grid layouts
 */

const MobileLayout = ({ children, currentPage = 'dashboard' }) => {
  const [mobileMenuOpen, setMobileMenuOpen] = React.useState(false);

  const navigation = [
    { name: 'Головна', href: '/manager', icon: Home, id: 'dashboard' },
    { name: 'Календар', href: '/calendar', icon: Calendar, id: 'calendar' },
    { name: 'Видача', href: '/issue', icon: Package, id: 'issue' },
    { name: 'Каса', href: '/kasa', icon: DollarSign, id: 'finance' },
    { name: 'Пошкодження', href: '/damage', icon: AlertTriangle, id: 'damage' },
  ];

  return (
    <div className="min-h-screen bg-corp-bg-page font-montserrat">
      {/* Mobile header */}
      <div className="lg:hidden corp-header">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-2 rounded-lg hover:bg-corp-bg-light"
          >
            {mobileMenuOpen ? <X className="w-6 h-6 text-corp-text-dark" /> : <Menu className="w-6 h-6 text-corp-text-dark" />}
          </button>
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-full bg-corp-primary grid place-content-center text-white font-bold text-sm">R</div>
            <h1 className="text-lg font-semibold text-corp-text-dark">Rental Hub</h1>
          </div>
        </div>
      </div>

      {/* Mobile menu overlay */}
      {mobileMenuOpen && (
        <div 
          className="lg:hidden fixed inset-0 z-40 bg-black bg-opacity-50"
          onClick={() => setMobileMenuOpen(false)}
        >
          <div 
            className="absolute left-0 top-14 bottom-0 w-64 bg-white shadow-xl p-4"
            onClick={(e) => e.stopPropagation()}
          >
            <nav className="space-y-2">
              {navigation.map((item) => {
                const Icon = item.icon;
                const isActive = currentPage === item.id;
                return (
                  <a
                    key={item.name}
                    href={item.href}
                    className={`flex items-center gap-3 px-4 py-3 rounded-corp transition-colors ${
                      isActive
                        ? 'bg-corp-primary text-white'
                        : 'text-corp-text-dark hover:bg-corp-bg-light'
                    }`}
                  >
                    <Icon className="w-5 h-5" />
                    <span className="font-medium">{item.name}</span>
                  </a>
                );
              })}
            </nav>
          </div>
        </div>
      )}

      {/* Content */}
      <main className="px-4 py-4 lg:px-8 lg:py-6">
        {children}
      </main>
    </div>
  );
};

/**
 * Responsive Card Component
 */
export const MobileCard = ({ children, className = '' }) => {
  return (
    <div className={`corp-card ${className}`}>
      {children}
    </div>
  );
};

/**
 * Responsive Grid Component
 */
export const MobileGrid = ({ children, cols = 2, className = '' }) => {
  const colsClass = {
    1: 'grid-cols-1',
    2: 'grid-cols-1 sm:grid-cols-2',
    3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
    4: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4',
  };

  return (
    <div className={`grid ${colsClass[cols] || colsClass[2]} gap-4 ${className}`}>
      {children}
    </div>
  );
};

/**
 * Responsive Button
 */
export const MobileButton = ({ 
  children, 
  onClick, 
  variant = 'primary', 
  icon: Icon,
  fullWidth = false,
  className = '' 
}) => {
  const variants = {
    primary: 'corp-btn corp-btn-primary',
    secondary: 'corp-btn corp-btn-secondary',
    success: 'corp-btn corp-btn-primary',
    danger: 'corp-btn corp-btn-secondary text-corp-error hover:bg-corp-error hover:text-white',
    outline: 'corp-btn corp-btn-outline',
  };

  return (
    <button
      onClick={onClick}
      className={`
        flex items-center justify-center gap-2 
        px-4 py-2.5 rounded-lg font-medium text-sm
        transition-colors
        ${variants[variant] || variants.primary}
        ${fullWidth ? 'w-full' : ''}
        ${className}
      `}
    >
      {Icon && <Icon className="w-4 h-4" />}
      <span className="whitespace-nowrap">{children}</span>
    </button>
  );
};

/**
 * Mobile-friendly table
 */
export const MobileTable = ({ headers, rows, mobileCard = true }) => {
  if (mobileCard) {
    // Card view for mobile
    return (
      <>
        {/* Desktop table */}
        <div className="hidden lg:block overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                {headers.map((header, i) => (
                  <th key={i} className="px-4 py-3 text-left text-sm font-semibold text-gray-700">
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y">
              {rows.map((row, i) => (
                <tr key={i} className="hover:bg-gray-50">
                  {row.map((cell, j) => (
                    <td key={j} className="px-4 py-3 text-sm">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Mobile cards */}
        <div className="lg:hidden space-y-3">
          {rows.map((row, i) => (
            <div key={i} className="bg-white rounded-lg border p-4 space-y-2">
              {row.map((cell, j) => (
                <div key={j} className="flex justify-between items-start">
                  <span className="text-sm font-medium text-gray-600">{headers[j]}:</span>
                  <span className="text-sm text-gray-900 text-right">{cell}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </>
    );
  }

  // Regular table with horizontal scroll
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[600px]">
        <thead className="bg-gray-50 border-b">
          <tr>
            {headers.map((header, i) => (
              <th key={i} className="px-4 py-3 text-left text-sm font-semibold text-gray-700">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.map((row, i) => (
            <tr key={i} className="hover:bg-gray-50">
              {row.map((cell, j) => (
                <td key={j} className="px-4 py-3 text-sm">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default MobileLayout;
