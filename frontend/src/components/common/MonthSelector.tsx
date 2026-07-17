import React, { useState, useEffect } from 'react';

interface MonthSelectorProps {
  currentYear: number;
  currentMonth: number;
  onChange: (year: number, month: number) => void;
}

const MonthSelector: React.FC<MonthSelectorProps> = ({ currentYear, currentMonth, onChange }) => {
  const [year, setYear] = useState(currentYear);
  const [month, setMonth] = useState(currentMonth);

  useEffect(() => {
    setYear(currentYear);
    setMonth(currentMonth);
  }, [currentYear, currentMonth]);

  const handleYearChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseInt(e.target.value, 10);
    if (!isNaN(val)) {
      setYear(val);
    }
  };

  const handleMonthChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setMonth(parseInt(e.target.value, 10));
  };

  const handleSubmit = () => {
    if (year >= 2020 && year <= 2040 && month >= 1 && month <= 12) {
      onChange(year, month);
    }
  };

  const handleGo = (e: React.FormEvent) => {
    e.preventDefault();
    handleSubmit();
  };

  const stepMonth = (delta: number) => {
    let newMonth = month + delta;
    let newYear = year;
    if (newMonth < 1) {
      newMonth = 12;
      newYear -= 1;
    } else if (newMonth > 12) {
      newMonth = 1;
      newYear += 1;
    }
    if (newYear >= 2020 && newYear <= 2040) {
      setYear(newYear);
      setMonth(newMonth);
      onChange(newYear, newMonth);
    }
  };

  return (
    <form onSubmit={handleGo} className="d-flex align-items-center gap-2">
      <input
        type="number"
        className="form-control form-control-sm"
        style={{ width: '85px' }}
        min={2020}
        max={2040}
        value={year}
        onChange={handleYearChange}
      />
      <select
        className="form-select form-select-sm"
        style={{ width: '70px' }}
        value={month}
        onChange={handleMonthChange}
      >
        {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
          <option key={m} value={m}>
            {m}
          </option>
        ))}
      </select>
      <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => stepMonth(-1)}>
        &laquo;
      </button>
      <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => stepMonth(1)}>
        &raquo;
      </button>
      <button type="submit" className="btn btn-sm btn-primary">
        Go
      </button>
    </form>
  );
};

export default MonthSelector;
