import React, { useState, useEffect, useCallback } from 'react';
import Alert from '../components/common/Alert';
import LoadingSpinner from '../components/common/LoadingSpinner';
import {
  fetchTemplates,
  addTemplate,
  deleteTemplate,
  templateInlineSave,
  templateBulkSave,
  templateBulkUpload,
  fetchGroups,
  addGroup,
  deleteGroup,
  groupInlineSave,
} from '../api/templates';
import type { TaskTemplate, Group } from '../types';

const TemplatesPage: React.FC = () => {
  const [templates, setTemplates] = useState<TaskTemplate[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [alertMsg, setAlertMsg] = useState<{ type: 'success' | 'danger'; text: string } | null>(null);

  const [groupsExpanded, setGroupsExpanded] = useState(false);
  const [editingGroup, setEditingGroup] = useState<number | null>(null);
  const [groupEditName, setGroupEditName] = useState('');
  const [newGroupName, setNewGroupName] = useState('');

  const [editingTemplate, setEditingTemplate] = useState<{ id: number; field: string } | null>(null);
  const [templateEditValue, setTemplateEditValue] = useState('');

  const [bulkEditMode, setBulkEditMode] = useState(false);
  const [selectedTemplates, setSelectedTemplates] = useState<Set<number>>(new Set());
  const [bulkField, setBulkField] = useState('');
  const [bulkValue, setBulkValue] = useState('');

  const [showAddTemplate, setShowAddTemplate] = useState(false);
  const [newTemplate, setNewTemplate] = useState({
    task_name: '',
    assigned_to: '',
    sla_days: 5,
    sla_type: 'Working Day',
    sort_order: 0,
    group_id: '',
  });

  const [showCsvModal, setShowCsvModal] = useState(false);
  const [csvTab, setCsvTab] = useState<'upload' | 'paste'>('upload');
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvText, setCsvText] = useState('');
  const [csvUploading, setCsvUploading] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [tData, gData]: any[] = await Promise.all([fetchTemplates(), fetchGroups()]);
      setTemplates(Array.isArray(tData) ? tData : tData.templates || []);
      setGroups(Array.isArray(gData) ? gData : gData.groups || []);
    } catch (e: any) {
      setError(e?.response?.data?.error || e.message || 'Failed to load templates');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleAddGroup = async () => {
    if (!newGroupName.trim()) return;
    try {
      await addGroup({ name: newGroupName.trim(), sort_order: groups.length });
      setNewGroupName('');
      setAlertMsg({ type: 'success', text: 'Group added' });
      loadData();
    } catch (e: any) {
      setAlertMsg({ type: 'danger', text: e?.response?.data?.error || 'Add group failed' });
    }
  };

  const handleGroupInlineEditStart = (group: Group) => {
    setEditingGroup(group.id);
    setGroupEditName(group.name);
  };

  const handleGroupInlineSave = async (groupId: number) => {
    if (!groupEditName.trim()) return;
    try {
      await groupInlineSave(groupId, { name: groupEditName.trim() });
      setEditingGroup(null);
      loadData();
    } catch (e: any) {
      setAlertMsg({ type: 'danger', text: e?.response?.data?.error || 'Save failed' });
    }
  };

  const handleDeleteGroup = async (groupId: number) => {
    if (!window.confirm('Delete this group?')) return;
    try {
      await deleteGroup(groupId);
      setAlertMsg({ type: 'success', text: 'Group deleted' });
      loadData();
    } catch (e: any) {
      setAlertMsg({ type: 'danger', text: e?.response?.data?.error || 'Delete failed' });
    }
  };

  const handleAddTemplate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTemplate.task_name.trim()) return;
    try {
      await addTemplate({
        ...newTemplate,
        sla_days: Number(newTemplate.sla_days),
        sort_order: Number(newTemplate.sort_order),
        group_id: newTemplate.group_id ? Number(newTemplate.group_id) : null,
      });
      setAlertMsg({ type: 'success', text: 'Template added' });
      setShowAddTemplate(false);
      setNewTemplate({ task_name: '', assigned_to: '', sla_days: 5, sla_type: 'Working Day', sort_order: 0, group_id: '' });
      loadData();
    } catch (e: any) {
      setAlertMsg({ type: 'danger', text: e?.response?.data?.error || 'Add template failed' });
    }
  };

  const handleTemplateInlineEditStart = (id: number, field: string, value: string) => {
    setEditingTemplate({ id, field });
    setTemplateEditValue(value ?? '');
  };

  const handleTemplateInlineSave = async (id: number, field: string) => {
    try {
      await templateInlineSave(id, { [field]: templateEditValue });
      setEditingTemplate(null);
      loadData();
    } catch (e: any) {
      setAlertMsg({ type: 'danger', text: e?.response?.data?.error || 'Save failed' });
    }
  };

  const handleDeleteTemplate = async (id: number) => {
    if (!window.confirm('Delete this template?')) return;
    try {
      await deleteTemplate(id);
      setAlertMsg({ type: 'success', text: 'Template deleted' });
      loadData();
    } catch (e: any) {
      setAlertMsg({ type: 'danger', text: e?.response?.data?.error || 'Delete failed' });
    }
  };

  const handleBulkToggle = (id: number) => {
    setSelectedTemplates((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSelectAll = () => {
    if (selectedTemplates.size === templates.length) {
      setSelectedTemplates(new Set());
    } else {
      setSelectedTemplates(new Set(templates.map((t) => t.id)));
    }
  };

  const handleBulkSave = async () => {
    if (!bulkField || selectedTemplates.size === 0) return;
    const updates = Array.from(selectedTemplates).map((id) => ({
      id,
      [bulkField]: bulkValue,
    }));
    try {
      await templateBulkSave(updates);
      setAlertMsg({ type: 'success', text: `Updated ${updates.length} templates` });
      setBulkEditMode(false);
      setSelectedTemplates(new Set());
      setBulkField('');
      setBulkValue('');
      loadData();
    } catch (e: any) {
      setAlertMsg({ type: 'danger', text: e?.response?.data?.error || 'Bulk save failed' });
    }
  };

  const handleCsvUpload = async () => {
    setCsvUploading(true);
    try {
      if (csvTab === 'upload' && csvFile) {
        const formData = new FormData();
        formData.append('file', csvFile);
        await templateBulkUpload(formData);
      } else if (csvTab === 'paste' && csvText.trim()) {
        const blob = new Blob([csvText], { type: 'text/csv' });
        const file = new File([blob], 'pasted.csv', { type: 'text/csv' });
        const formData = new FormData();
        formData.append('file', file);
        await templateBulkUpload(formData);
      } else {
        setAlertMsg({ type: 'danger', text: 'No data to upload' });
        setCsvUploading(false);
        return;
      }
      setAlertMsg({ type: 'success', text: 'CSV uploaded successfully' });
      setShowCsvModal(false);
      setCsvFile(null);
      setCsvText('');
      loadData();
    } catch (e: any) {
      setAlertMsg({ type: 'danger', text: e?.response?.data?.error || 'Upload failed' });
    } finally {
      setCsvUploading(false);
    }
  };

  const renderTemplateCell = (id: number, field: string, displayValue: string) => {
    const isEditing = editingTemplate?.id === id && editingTemplate?.field === field;
    if (bulkEditMode) return <span className="view-mode">{displayValue}</span>;
    if (isEditing) {
      return (
        <input
          className="form-control form-control-sm edit-mode"
          value={templateEditValue}
          onChange={(e) => setTemplateEditValue(e.target.value)}
          onBlur={() => handleTemplateInlineSave(id, field)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleTemplateInlineSave(id, field);
            if (e.key === 'Escape') setEditingTemplate(null);
          }}
          autoFocus
        />
      );
    }
    return (
      <span
        className="view-mode"
        style={{ cursor: 'pointer' }}
        onClick={() => handleTemplateInlineEditStart(id, field, displayValue)}
        title="Click to edit"
      >
        {displayValue}
      </span>
    );
  };

  return (
    <div>
      {alertMsg && (
        <div className="mb-3">
          <Alert type={alertMsg.type} message={alertMsg.text} onDismiss={() => setAlertMsg(null)} />
        </div>
      )}

      <div className="d-flex flex-wrap gap-2 mb-3">
        <button className="btn btn-sm btn-primary" onClick={() => setShowAddTemplate(!showAddTemplate)}>
          + Add Task
        </button>
        <button className="btn btn-sm btn-outline-success" onClick={() => setShowCsvModal(true)}>
          Bulk Upload
        </button>
        <button
          className="btn btn-sm btn-outline-secondary"
          onClick={() => setGroupsExpanded(!groupsExpanded)}
        >
          {groupsExpanded ? 'Hide Groups' : 'Manage Groups'}
        </button>
      </div>

      {showAddTemplate && (
        <div className="glass-card card mb-3">
          <div className="card-header">Add New Template</div>
          <div className="card-body">
            <form onSubmit={handleAddTemplate}>
              <div className="row g-2 align-items-end">
                <div className="col-md-2">
                  <label className="form-label form-label-sm">Task Name</label>
                  <input
                    className="form-control form-control-sm"
                    value={newTemplate.task_name}
                    onChange={(e) => setNewTemplate({ ...newTemplate, task_name: e.target.value })}
                    required
                  />
                </div>
                <div className="col-md-2">
                  <label className="form-label form-label-sm">Assigned To</label>
                  <input
                    className="form-control form-control-sm"
                    value={newTemplate.assigned_to}
                    onChange={(e) => setNewTemplate({ ...newTemplate, assigned_to: e.target.value })}
                  />
                </div>
                <div className="col-md-1">
                  <label className="form-label form-label-sm">SLA Days</label>
                  <input
                    type="number"
                    className="form-control form-control-sm"
                    value={newTemplate.sla_days}
                    onChange={(e) => setNewTemplate({ ...newTemplate, sla_days: Number(e.target.value) })}
                    min={1}
                  />
                </div>
                <div className="col-md-2">
                  <label className="form-label form-label-sm">SLA Type</label>
                  <select
                    className="form-select form-select-sm"
                    value={newTemplate.sla_type}
                    onChange={(e) => setNewTemplate({ ...newTemplate, sla_type: e.target.value as 'Working Day' | 'Calendar Day' })}
                  >
                    <option value="Working Day">Working Day</option>
                    <option value="Calendar Day">Calendar Day</option>
                  </select>
                </div>
                <div className="col-md-1">
                  <label className="form-label form-label-sm">Order</label>
                  <input
                    type="number"
                    className="form-control form-control-sm"
                    value={newTemplate.sort_order}
                    onChange={(e) => setNewTemplate({ ...newTemplate, sort_order: Number(e.target.value) })}
                  />
                </div>
                <div className="col-md-2">
                  <label className="form-label form-label-sm">Group</label>
                  <select
                    className="form-select form-select-sm"
                    value={newTemplate.group_id}
                    onChange={(e) => setNewTemplate({ ...newTemplate, group_id: e.target.value })}
                  >
                    <option value="">No Group</option>
                    {groups.map((g) => (
                      <option key={g.id} value={g.id}>{g.name}</option>
                    ))}
                  </select>
                </div>
                <div className="col-md-2">
                  <button type="submit" className="btn btn-sm btn-primary w-100">Save</button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {groupsExpanded && (
        <div className="glass-card card mb-3">
          <div className="card-header">Groups</div>
          <div className="card-body">
            <div className="d-flex gap-2 mb-3">
              <input
                className="form-control form-control-sm"
                style={{ maxWidth: '300px' }}
                value={newGroupName}
                onChange={(e) => setNewGroupName(e.target.value)}
                placeholder="New group name"
                onKeyDown={(e) => { if (e.key === 'Enter') handleAddGroup(); }}
              />
              <button className="btn btn-sm btn-primary" onClick={handleAddGroup}>Add Group</button>
            </div>
            <div className="table-responsive">
              <table className="table table-sm table-hover mb-0">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Order</th>
                    <th>Templates</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {groups.map((g) => (
                    <tr key={g.id}>
                      <td>{g.id}</td>
                      <td>
                        {editingGroup === g.id ? (
                          <input
                            className="form-control form-control-sm"
                            value={groupEditName}
                            onChange={(e) => setGroupEditName(e.target.value)}
                            onBlur={() => handleGroupInlineSave(g.id)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') handleGroupInlineSave(g.id);
                              if (e.key === 'Escape') setEditingGroup(null);
                            }}
                            autoFocus
                          />
                        ) : (
                          <span style={{ cursor: 'pointer' }} onClick={() => handleGroupInlineEditStart(g)}>
                            {g.name}
                          </span>
                        )}
                      </td>
                      <td>{g.sort_order}</td>
                      <td>{g.template_count ?? '—'}</td>
                      <td>
                        <button
                          className="btn btn-sm btn-outline-danger"
                          onClick={() => handleDeleteGroup(g.id)}
                        >
                          ✕
                        </button>
                      </td>
                    </tr>
                  ))}
                  {groups.length === 0 && (
                    <tr><td colSpan={5} className="text-center text-muted">No groups</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {bulkEditMode && selectedTemplates.size > 0 && (
        <div className="glass-card card mb-3">
          <div className="card-body d-flex align-items-center gap-2 flex-wrap">
            <span className="fw-semibold">Bulk edit {selectedTemplates.size} templates:</span>
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
                <input
                  className="form-control form-control-sm"
                  style={{ width: '160px' }}
                  value={bulkValue}
                  onChange={(e) => setBulkValue(e.target.value)}
                  placeholder="New value"
                />
                <button className="btn btn-sm btn-primary" onClick={handleBulkSave}>Save Bulk</button>
              </>
            )}
          </div>
        </div>
      )}

      <div className="glass-card card mb-4">
        <div className="card-header d-flex justify-content-between align-items-center">
          <span>Task Templates ({templates.length})</span>
          <button
            className={`btn btn-sm ${bulkEditMode ? 'btn-warning' : 'btn-outline-secondary'}`}
            onClick={() => {
              setBulkEditMode(!bulkEditMode);
              setSelectedTemplates(new Set());
              setBulkField('');
              setBulkValue('');
            }}
          >
            {bulkEditMode ? 'Cancel Bulk' : 'Bulk Edit'}
          </button>
        </div>
        <div className="card-body p-0">
          {loading ? (
            <LoadingSpinner message="Loading templates..." />
          ) : error ? (
            <div className="p-3"><Alert type="danger" message={error} onDismiss={() => setError(null)} /></div>
          ) : (
            <div className="table-responsive">
              <table className="table table-hover mb-0">
                <thead>
                  <tr>
                    {bulkEditMode && <th style={{ width: '40px' }}><input type="checkbox" checked={selectedTemplates.size === templates.length && templates.length > 0} onChange={handleSelectAll} /></th>}
                    <th>#</th>
                    <th>Task Name</th>
                    <th>Assigned To</th>
                    <th>SLA</th>
                    <th>Order</th>
                    <th>Group</th>
                    <th style={{ width: '60px' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {templates.map((t, i) => (
                    <tr key={t.id}>
                      {bulkEditMode && (
                        <td>
                          <input
                            type="checkbox"
                            checked={selectedTemplates.has(t.id)}
                            onChange={() => handleBulkToggle(t.id)}
                          />
                        </td>
                      )}
                      <td className="text-muted">{i + 1}</td>
                      <td>{renderTemplateCell(t.id, 'task_name', t.task_name)}</td>
                      <td>{renderTemplateCell(t.id, 'assigned_to', t.assigned_to)}</td>
                      <td>{renderTemplateCell(t.id, 'sla_days', `${t.sla_days} ${t.sla_type}`)}</td>
                      <td>{renderTemplateCell(t.id, 'sort_order', String(t.sort_order))}</td>
                      <td>{t.group_name || '—'}</td>
                      <td>
                        <button
                          className="btn btn-sm btn-outline-danger view-mode"
                          onClick={() => handleDeleteTemplate(t.id)}
                          title="Delete template"
                        >
                          ✕
                        </button>
                      </td>
                    </tr>
                  ))}
                  {templates.length === 0 && (
                    <tr>
                      <td colSpan={bulkEditMode ? 8 : 7} className="text-center text-muted py-4">
                        No templates yet. Add one or upload a CSV.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {showCsvModal && (
        <div className="modal d-block" tabIndex={-1} style={{ background: 'rgba(0,0,0,0.4)' }}>
          <div className="modal-dialog modal-lg">
            <div className="modal-content glass-card">
              <div className="modal-header">
                <h6 className="modal-title fw-semibold">Bulk Upload Templates (CSV)</h6>
                <button type="button" className="btn-close" onClick={() => { setShowCsvModal(false); setCsvFile(null); setCsvText(''); }} />
              </div>
              <div className="modal-body">
                <ul className="nav nav-tabs mb-3">
                  <li className="nav-item">
                    <button
                      className={`nav-link${csvTab === 'upload' ? ' active' : ''}`}
                      onClick={() => setCsvTab('upload')}
                    >
                      Upload File
                    </button>
                  </li>
                  <li className="nav-item">
                    <button
                      className={`nav-link${csvTab === 'paste' ? ' active' : ''}`}
                      onClick={() => setCsvTab('paste')}
                    >
                      Paste CSV Text
                    </button>
                  </li>
                </ul>

                {csvTab === 'upload' ? (
                  <div>
                    <p className="text-muted mb-2" style={{ fontSize: '0.85rem' }}>
                      CSV columns: task_name, assigned_to, sla_days, sla_type, sort_order, group_name
                    </p>
                    <input
                      type="file"
                      accept=".csv"
                      className="form-control"
                      onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
                    />
                  </div>
                ) : (
                  <div>
                    <p className="text-muted mb-2" style={{ fontSize: '0.85rem' }}>
                      Paste CSV content below (with header row):
                    </p>
                    <textarea
                      className="form-control"
                      rows={10}
                      value={csvText}
                      onChange={(e) => setCsvText(e.target.value)}
                      placeholder="task_name,assigned_to,sla_days,sla_type,sort_order,group_name&#10;Monthly Report,John,5,Working Day,1,Reporting"
                    />
                  </div>
                )}
              </div>
              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-sm btn-secondary"
                  onClick={() => { setShowCsvModal(false); setCsvFile(null); setCsvText(''); }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn btn-sm btn-primary"
                  onClick={handleCsvUpload}
                  disabled={csvUploading || (csvTab === 'upload' && !csvFile) || (csvTab === 'paste' && !csvText.trim())}
                >
                  {csvUploading ? 'Uploading...' : 'Upload'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TemplatesPage;
