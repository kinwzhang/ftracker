import React from 'react';
import type { AuditLog } from '../../types';

interface AuditTrailProps {
  logs: AuditLog[];
}

const AuditTrail: React.FC<AuditTrailProps> = ({ logs }) => {
  return (
    <div className="glass-card card mt-4 mb-4">
      <div className="card-header">Audit Trail</div>
      <div className="card-body p-0">
        <div className="table-responsive">
          <table className="table table-hover mb-0">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 ? (
                <tr>
                  <td colSpan={2} className="text-center text-muted py-3">No audit logs yet</td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id}>
                    <td className="text-muted" style={{ whiteSpace: 'nowrap', fontSize: '0.82rem' }}>
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td style={{ fontSize: '0.85rem' }}>{log.readable_message}</td>
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

export default AuditTrail;
