import React from 'react';
import { format } from 'date-fns';
import { uk } from 'date-fns/locale';

const DateRangePicker = ({ startDate, endDate, onStartDateChange, onEndDateChange, className = '' }) => {
  const today = format(new Date(), 'yyyy-MM-dd');

  return (
    <div className={`grid grid-cols-2 gap-3 ${className}`}>
      <div>
        <label className="fd-label">
          📅 Початок оренди
        </label>
        <input
          type="date"
          value={startDate || ''}
          min={today}
          onChange={(e) => onStartDateChange(e.target.value)}
          className="w-full fd-input"
        />
      </div>
      <div>
        <label className="fd-label">
          📅 Кінець оренди
        </label>
        <input
          type="date"
          value={endDate || ''}
          min={startDate || today}
          onChange={(e) => onEndDateChange(e.target.value)}
          className="w-full fd-input"
        />
      </div>
    </div>
  );
};

export default DateRangePicker;