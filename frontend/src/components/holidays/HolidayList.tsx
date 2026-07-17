import React from 'react';
import type { Holiday } from '../../types';

interface HolidayListProps {
  holidays: Holiday[];
}

const HolidayList: React.FC<HolidayListProps> = ({ holidays }) => {
  return (
    <div className="glass-card card">
      <div className="card-header">Holidays ({holidays.length} found)</div>
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
                  <td colSpan={3} className="text-center text-muted py-4">No holidays found</td>
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
  );
};

export default HolidayList;
