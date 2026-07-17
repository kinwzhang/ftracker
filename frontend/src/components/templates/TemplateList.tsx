import React, { useState } from 'react';
import type { TaskTemplate, Group } from '../../types';
import ConfirmDialog from '../common/ConfirmDialog';

interface TemplateListProps {
  templates: TaskTemplate[];
  groups: Group[];
  isBulkEditing: boolean;
  onSave: (id: number, data: Record<string, unknown>) => void;
  onDelete: (id: number) => void;
  onBulkEdit: (ids: number[], field: string, value: string) => void;
  onBulkSave: () => void;
  onBulkCancel: () => void;
}

const TemplateList: React.FC<TemplateListProps> = ({
  templates,
  groups,
  isBulkEditing,
  onSave,
  onDelete,
  onBulkEdit,
  onBulkSave,
  onBulkCancel,
}) => {
  const [editRow, setEditRow] = useState<number | null>(null);
  const [editData, setEditData] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkField, setBulkField] = useState('');
  const [bulkValue, setBulkValue] = useState('');
  const [deleteId, setDeleteId] = useState<number | null>(null);

  const startEdit = (t: TaskTemplate) => {
    setEditRow(t.id);
    setEditData({
      task_name: t.task_name,
      assigned_to: t.assigned_to,
      sla_days: String(t.sla_days),
      sla_type: t.sla_type,
      sort_order: String(t.sort_order),
      group_id: t.group_id != null ? String(t.group_id) : '',
    });
  };

  const handleSave = () => {
    if (editRow == null) return;
    onSave(editRow, { ...editData, sla_days: Number(editData.sla_days), sort_order: Number(editData.sort_order), group_id: editData.group_id ? Number(editData.group_id) : null });
    setEditRow(null);
    setEditData({});
  };

  const cancelEdit = () => {
    setEditRow(null);
    setEditData({});
  };

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    if (selected.size === templates.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(templates.map((t) => t.id)));
    }
  };

  const handleBulkSave = () => {
    if (!bulkField || selected.size === 0) return;
    onBulkEdit(Array.from(selected), bulkField, bulkValue);
    onBulkSave();
    setSelected(new Set());
    setBulkField('');
    setBulkValue('');
  };

  const handleBulkCancel = () => {
    setSelected(new Set());
    setBulkField('');
    setBulkValue('');
    onBulkCancel();
  };

  return (
    <div>
      {isBulkEditing && selected.size > 0 && (
        <div className="glass-card card mb-3">
          <div className="card-body d-flex align-items-center gap-2 flex-wrap">
            <span className="fw-semibold">Bulk edit {selected.size} templates:</span>
            <select className="form-select form-select-sm" style={{ width: '160px' }} value={bulkField} onChange={(e) => setBulkField(e.target.value)}>
              <option value="">Select field...</option>
              <option value="assigned_to">Assigned To</option>
              <option value="sla_days">SLA Days</option>
              <option value="sla_type">SLA Type</option>
              <option value="sort_order">Sort Order</option>
              <option value="group_id">Group ID</option>
            </select>
            {bulkField && (
              <>
                <input className="form-control form-control-sm" style={{ width: '160px' }} value={bulkValue} onChange={(e) => setBulkValue(e.target.value)} placeholder="New value" />
                <button className="btn btn-sm btn-primary" onClick={handleBulkSave}>Save Bulk</button>
              </>
            )}
          </div>
        </div>
      )}

      <div className="glass-card card mb-4">
        <div className="card-header d-flex justify-content-between align-items-center">
          <span>Task Templates ({templates.length})</span>
          {isBulkEditing && (
            <button className="btn btn-sm btn-outline-secondary" onClick={handleBulkCancel}>
              Cancel Bulk
            </button>
          )}
        </div>
        <div className="card-body p-0">
          <div className="table-responsive">
            <table className="table table-hover mb-0">
              <thead>
                <tr>
                  {isBulkEditing && <th style={{ width: '40px' }}><input type="checkbox" checked={selected.size === templates.length && templates.length > 0} onChange={selectAll} /></th>}
                  <th>Order</th>
                  <th>Task Name</th>
                  <th>Assigned To</th>
                  <th>SLA Days</th>
                  <th>SLA Type</th>
                  <th>Group</th>
                  <th style={{ width: '100px' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {templates.map((t) => (
                  <tr key={t.id}>
                    {isBulkEditing && (
                      <td><input type="checkbox" checked={selected.has(t.id)} onChange={() => toggleSelect(t.id)} /></td>
                    )}
                    <td className="text-muted">{t.sort_order}</td>
                    {editRow === t.id ? (
                      <>
                        <td>
                          <input className="form-control form-control-sm edit-mode" value={editData.task_name} onChange={(e) => setEditData({ ...editData, task_name: e.target.value })} />
                        </td>
                        <td>
                          <input className="form-control form-control-sm edit-mode" value={editData.assigned_to} onChange={(e) => setEditData({ ...editData, assigned_to: e.target.value })} />
                        </td>
                        <td>
                          <input type="number" className="form-control form-control-sm edit-mode" value={editData.sla_days} onChange={(e) => setEditData({ ...editData, sla_days: e.target.value })} min={1} />
                        </td>
                        <td>
                          <select className="form-select form-select-sm edit-mode" value={editData.sla_type} onChange={(e) => setEditData({ ...editData, sla_type: e.target.value })}>
                            <option value="Working Day">Working Day</option>
                            <option value="Calendar Day">Calendar Day</option>
                          </select>
                        </td>
                        <td>
                          <select className="form-select form-select-sm edit-mode" value={editData.group_id} onChange={(e) => setEditData({ ...editData, group_id: e.target.value })}>
                            <option value="">No Group</option>
                            {groups.map((g) => (
                              <option key={g.id} value={g.id}>{g.name}</option>
                            ))}
                          </select>
                        </td>
                        <td>
                          <button className="btn btn-sm btn-success me-1" onClick={handleSave}>Save</button>
                          <button className="btn btn-sm btn-secondary" onClick={cancelEdit}>Cancel</button>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="view-mode">{t.task_name}</td>
                        <td className="view-mode">{t.assigned_to}</td>
                        <td className="view-mode">{t.sla_days}</td>
                        <td className="view-mode">{t.sla_type}</td>
                        <td className="view-mode">{t.group_name || '—'}</td>
                        <td className="view-mode">
                          <button className="btn btn-sm btn-outline-primary me-1" onClick={() => startEdit(t)}>Edit</button>
                          <button className="btn btn-sm btn-outline-danger" onClick={() => setDeleteId(t.id)}>Delete</button>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
                {templates.length === 0 && (
                  <tr>
                    <td colSpan={isBulkEditing ? 9 : 8} className="text-center text-muted py-4">
                      No templates yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <ConfirmDialog
        show={deleteId != null}
        title="Delete Template"
        message="Are you sure you want to delete this template? This action cannot be undone."
        onConfirm={() => { if (deleteId != null) onDelete(deleteId); setDeleteId(null); }}
        onCancel={() => setDeleteId(null)}
      />
    </div>
  );
};

export default TemplateList;
