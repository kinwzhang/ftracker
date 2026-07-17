import React, { useState, useEffect, useCallback } from 'react';
import MonthSelector from '../components/common/MonthSelector';
import Alert from '../components/common/Alert';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { fetchDashboard } from '../api/dashboard';
import type { DashboardData } from '../types';

const DashboardPage: React.FC = () => {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const monthStr = `${year}-${String(month).padStart(2, '0')}`;

  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result: any = await fetchDashboard(monthStr);
      setData(result);
    } catch (e: any) {
      setError(e?.response?.data?.error || e.message || 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  }, [monthStr]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleMonthChange = (y: number, m: number) => {
    setYear(y);
    setMonth(m);
  };

  const stats = data?.stats || { total: 0, completed: 0, pending: 0, overdue: 0 };
  const completionRate = data?.completion_rate ?? 0;
  const monthsData = data?.months_data || [];
  const auditLogs = data?.audit_logs || [];

  return (
    <div>
      <MonthSelector currentYear={year} currentMonth={month} onChange={handleMonthChange} />

      {error && (
        <div className="mt-3">
          <Alert type="danger" message={error} onDismiss={() => setError(null)} />
        </div>
      )}

      {loading ? (
        <LoadingSpinner message="Loading dashboard..." />
      ) : (
        <>
          <div className="row g-3 mt-2">
            <div className="col-md-3">
              <div className="stat-card glass-card">
                <p className="stat-number">{stats.total}</p>
                <p className="stat-label">Total Tasks</p>
              </div>
            </div>
            <div className="col-md-3">
              <div className="stat-card glass-success glass-card">
                <p className="stat-number">{stats.completed}</p>
                <p className="stat-label">Completed</p>
              </div>
            </div>
            <div className="col-md-3">
              <div className="stat-card glass-warning glass-card">
                <p className="stat-number">{stats.pending}</p>
                <p className="stat-label">In Progress</p>
              </div>
            </div>
            <div className="col-md-3">
              <div className="stat-card glass-danger glass-card">
                <p className="stat-number">{stats.overdue}</p>
                <p className="stat-label">Overdue</p>
              </div>
            </div>
          </div>

          <div className="glass-card card mt-4">
            <div className="card-header">Completion Rate</div>
            <div className="card-body">
              <div className="d-flex align-items-center gap-3">
                <div className="progress flex-grow-1" style={{ height: '24px' }}>
                  <div
                    className="progress-bar bg-success"
                    role="progressbar"
                    style={{ width: `${completionRate}%` }}
                    aria-valuenow={completionRate}
                    aria-valuemin={0}
                    aria-valuemax={100}
                  >
                    {completionRate.toFixed(1)}%
                  </div>
                </div>
                <span className="fw-semibold" style={{ minWidth: '60px', textAlign: 'right' }}>
                  {stats.completed}/{stats.total}
                </span>
              </div>
            </div>
          </div>

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
                      <th style={{ width: '40%' }}>Progress</th>
                      <th>Rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {monthsData.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="text-center text-muted py-3">No trend data available</td>
                      </tr>
                    ) : (
                      monthsData.map((m, i) => (
                        <tr key={i}>
                          <td className="fw-semibold">{m.label}</td>
                          <td>{m.total}</td>
                          <td>{m.completed}</td>
                          <td>
                            <div className="progress" style={{ height: '16px' }}>
                              <div
                                className="progress-bar bg-success"
                                role="progressbar"
                                style={{ width: `${m.rate}%` }}
                              />
                            </div>
                          </td>
                          <td className="fw-semibold">{m.rate.toFixed(1)}%</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div className="glass-card card mt-4 mb-4">
            <div className="card-header">Audit Trail (Last 50 Entries)</div>
            <div className="card-body p-0">
              <div className="table-responsive">
                <table className="table table-hover mb-0">
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Task</th>
                      <th>Action</th>
                      <th>Changes</th>
                      <th>Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditLogs.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="text-center text-muted py-3">No audit entries</td>
                      </tr>
                    ) : (
                      auditLogs.map((log) => (
                        <tr key={log.id}>
                          <td className="text-muted" style={{ whiteSpace: 'nowrap', fontSize: '0.82rem' }}>
                            {new Date(log.timestamp).toLocaleString()}
                          </td>
                          <td className="fw-semibold">{log.task_name}</td>
                          <td><span className="badge bg-secondary">{log.action}</span></td>
                          <td style={{ fontSize: '0.82rem' }}>{log.changes}</td>
                          <td style={{ fontSize: '0.82rem' }}>{log.readable_message}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default DashboardPage;
