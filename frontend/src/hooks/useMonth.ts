import { useState, useCallback } from 'react';

interface UseMonthResult {
  year: number;
  month: number;
  setYear: (year: number) => void;
  setMonth: (month: number) => void;
  stepMonth: (delta: number) => void;
  monthString: string;
}

export function useMonth(): UseMonthResult {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);

  const stepMonth = useCallback((delta: number) => {
    setMonth((prev) => {
      let newMonth = prev + delta;
      if (newMonth < 1) {
        setYear((y) => y - 1);
        return 12;
      }
      if (newMonth > 12) {
        setYear((y) => y + 1);
        return 1;
      }
      return newMonth;
    });
  }, []);

  const monthString = `${year}-${String(month).padStart(2, '0')}`;

  return { year, month, setYear, setMonth, stepMonth, monthString };
}
