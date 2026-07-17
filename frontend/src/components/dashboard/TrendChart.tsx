import React from 'react';

interface TrendData {
  label: string;
  total: number;
  completed: number;
  rate: number;
}

interface TrendChartProps {
  data: TrendData[];
}

const TrendChart: React.FC<TrendChartProps> = ({ data }) => {
  return (
    <div className="glass-card card mt-4">
      <div className="card-header">Monthly Trend (Last 6 Months)</div>
      <div className="card-body p-0">
        <div className="table-responsive">
          <table className="table table-hover mb-0">
            <thead>
              <tr>
                <th>Month</th>
                <th>Total</th>
                <th>Completed</th>
                <th style={{ width: '40%' }}>Rate</th>
              </tr>
            </thead>
            <tbody>
              {data.length === 0 ? (
                <tr>
                  <td colSpan={4} className="text-center text-muted py-3">No trend data available</td>
                </tr>
              ) : (
                data.map((m, i) => (
                  <tr key={i}>
                    <td className="fw-semibold">{m.label}</td>
                    <td>{m.total}</td>
                    <td>{m.completed}</td>
                    <td>
                      <div className="d-flex align-items-center gap-2">
                        <div className="progress flex-grow-1" style={{ height: '16px' }}>
                          <div className="progress-bar bg-success" role="progressbar" style={{ width: `${m.rate}%` }} />
                        </div>
                        <span className="fw-semibold" style={{ minWidth: '48px', textAlign: 'right' }}>{m.rate.toFixed(1)}%</span>
                      </div>
                    </td>
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

export default TrendChart;
