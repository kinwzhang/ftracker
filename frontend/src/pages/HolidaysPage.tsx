import React, { useState, useCallback } from 'react';
import Alert from '../components/common/Alert';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { fetchHolidays } from '../api/holidays';
import type { Holiday } from '../types';

const HolidaysPage: React.FC = () => {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(0);
  const [holidays, setHolidays] = useState<Holiday[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const loadHolidays = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data: any = await fetchHolidays(year, month);
      setHolidays(Array.isArray(data) ? data : data.holidays || []);
      setHasSearched(true);
    } catch (e: any) {
      setError(e?.response?.data?.error || e.message || 'Failed to load holidays');
      setHolidays([]);
    } finally {
      setLoading(false);
    }
  }, [year, month]);

  const handleFilter = (e: React.FormEvent) => {
    e.preventDefault();
    loadHolidays();
  };

  return (
    <div>
      <h3 className="mb-3">Holidays</h3>

      <form onSubmit={handleFilter} className="mb-4">
        <div className="d-flex align-items-end gap-2 flex-wrap">
          <div>
            <label className="form-label form-label-sm">Year</label>
            <select
              className="form-select form-select-sm"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              style={{ width: '100px' }}
            >
              {Array.from({ length: 6 }, (_, i) => 2025 + i).map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="form-label form-label-sm">Month</label>
            <select
              className="form-select form-select-sm"
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
              style={{ width: '140px' }}
            >
              <option value={0}>All Year</option>
              {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
          <button type="submit" className="btn btn-sm btn-primary">
            Filter
          </button>
        </div>
      </form>

      {error && <Alert type="danger" message={error} onDismiss={() => setError(null)} />}

      {loading ? (
        <LoadingSpinner message="Loading holidays..." />
      ) : hasSearched ? (
        <div className="glass-card card">
          <div className="card-header">
            Holidays — {year}{month > 0 ? ` / ${month}` : ' (All Year)'} ({holidays.length} found)
          </div>
          <div className="card-body p-0">
            <div className="table-responsive">
              <table className="table table-hover mb-0">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Day of Week</th>
                    <th>Holiday Name</th>
                  </tr>
                </thead>
                <tbody>
                  {holidays.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="text-center text-muted py-4">
                        No holidays found for this period.
                      </td>
                    </tr>
                  ) : (
                    holidays.map((h, i) => (
                      <tr key={`${h.date}-${i}`}>
                        <td className="fw-semibold">{h.date}</td>
                        <td>{h.weekday}</td>
                        <td>{h.name}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        <div className="text-center text-muted py-5">
          Select a year and month, then click Filter to view holidays.
        </div>
      )}
    </div>
  );
};

export default HolidaysPage;
