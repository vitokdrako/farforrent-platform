import React from 'react';

const AvailabilityBadge = ({ available, total, requested = 1, compact = false }) => {
  const getStatus = () => {
    if (available >= requested) {
      if (available === total) {
        return { icon: '✅', text: `Доступно ${available} шт`, color: 'bg-green-100 text-green-800', iconColor: 'text-green-600' };
      }
      return { icon: '⚠️', text: `Доступно ${available} шт`, color: 'bg-yellow-100 text-yellow-800', iconColor: 'text-yellow-600' };
    } else if (available > 0) {
      return { icon: '⚠️', text: `Лише ${available} шт`, color: 'bg-orange-100 text-orange-800', iconColor: 'text-orange-600' };
    } else {
      return { icon: '❌', text: 'Недоступно', color: 'bg-red-100 text-red-800', iconColor: 'text-red-600' };
    }
  };

  const status = getStatus();

  const badgeClass = available >= requested 
    ? (available === total ? 'fd-badge-success' : 'fd-badge-warning')
    : (available > 0 ? 'fd-badge-warning' : 'fd-badge-error');

  if (compact) {
    return (
      <span className={`fd-badge ${badgeClass}`}>
        <span>{status.icon}</span>
        {available}/{total}
      </span>
    );
  }

  return (
    <div className={`fd-badge ${badgeClass}`} style={{padding: '6px 10px', fontSize: '11px'}}>
      <span>{status.icon}</span>
      <span>{status.text}</span>
    </div>
  );
};

export default AvailabilityBadge;