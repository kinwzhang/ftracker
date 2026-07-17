import React, { useState } from 'react';

interface CSVUploadProps {
  show: boolean;
  onClose: () => void;
  onSubmit: (formData: FormData) => void;
}

const CSVUpload: React.FC<CSVUploadProps> = ({ show, onClose, onSubmit }) => {
  const [tab, setTab] = useState<'upload' | 'paste'>('upload');
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState('');

  if (!show) return null;

  const handleSubmit = () => {
    if (tab === 'upload' && file) {
      const formData = new FormData();
      formData.append('file', file);
      onSubmit(formData);
      setFile(null);
    } else if (tab === 'paste' && text.trim()) {
      const blob = new Blob([text], { type: 'text/csv' });
      const csvFile = new File([blob], 'pasted.csv', { type: 'text/csv' });
      const formData = new FormData();
      formData.append('file', csvFile);
      onSubmit(formData);
      setText('');
    }
  };

  const handleClose = () => {
    setFile(null);
    setText('');
    onClose();
  };

  return (
    <div className="modal d-block" tabIndex={-1} style={{ background: 'rgba(0,0,0,0.4)' }}>
      <div className="modal-dialog modal-lg">
        <div className="modal-content glass-card">
          <div className="modal-header">
            <h6 className="modal-title fw-semibold">Bulk Upload Templates (CSV)</h6>
            <button type="button" className="btn-close" onClick={handleClose} />
          </div>
          <div className="modal-body">
            <ul className="nav nav-tabs mb-3">
              <li className="nav-item">
                <button className={`nav-link${tab === 'upload' ? ' active' : ''}`} onClick={() => setTab('upload')}>
                  Upload CSV File
                </button>
              </li>
              <li className="nav-item">
                <button className={`nav-link${tab === 'paste' ? ' active' : ''}`} onClick={() => setTab('paste')}>
                  Paste CSV
                </button>
              </li>
            </ul>

            {tab === 'upload' ? (
              <div>
                <p className="text-muted mb-2" style={{ fontSize: '0.85rem' }}>
                  CSV columns: task_name, assigned_to, sla_days, sla_type, sort_order, group_name
                </p>
                <input type="file" accept=".csv" className="form-control" onChange={(e) => setFile(e.target.files?.[0] || null)} />
              </div>
            ) : (
              <div>
                <p className="text-muted mb-2" style={{ fontSize: '0.85rem' }}>
                  Paste CSV content below (with header row):
                </p>
                <textarea className="form-control" rows={10} value={text} onChange={(e) => setText(e.target.value)} placeholder="task_name,assigned_to,sla_days,sla_type,sort_order,group_name&#10;Monthly Report,John,5,Working Day,1,Reporting" />
              </div>
            )}
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-sm btn-secondary" onClick={handleClose}>Cancel</button>
            <button type="button" className="btn btn-sm btn-primary" onClick={handleSubmit} disabled={(tab === 'upload' && !file) || (tab === 'paste' && !text.trim())}>
              Upload
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CSVUpload;
