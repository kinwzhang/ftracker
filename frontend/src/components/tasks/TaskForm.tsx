import React, { useState } from 'react';
import type { Group } from '../../types';

interface TaskFormProps {
  groups: Group[];
  onSubmit: (data: {
    task_name: string;
    assigned_to: string;
    sla_days: number;
    sla_type: 'Working Day' | 'Calendar Day';
    comments: string;
    group_id: number | null;
  }) => void;
  loading: boolean;
}

const TaskForm: React.FC<TaskFormProps> = ({ groups, onSubmit, loading }) => {
  const [form, setForm] = useState({
    task_name: '',
    assigned_to: '',
    sla_days: 5,
    sla_type: 'Working Day' as 'Working Day' | 'Calendar Day',
    comments: '',
    group_id: '',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.task_name.trim()) return;
    onSubmit({
      task_name: form.task_name.trim(),
      assigned_to: form.assigned_to.trim(),
      sla_days: Number(form.sla_days),
      sla_type: form.sla_type,
      comments: form.comments.trim(),
      group_id: form.group_id !== '' ? Number(form.group_id) : null,
    });
    setForm({ task_name: '', assigned_to: '', sla_days: 5, sla_type: 'Working Day', comments: '', group_id: '' });
  };

  return (
    <div id="quick-add-form" className="glass-card card mb-4">
      <div className="card-header">Quick Add Task</div>
      <div className="card-body">
        <form onSubmit={handleSubmit}>
          <div className="row g-2 align-items-end">
            <div className="col-md-3">
              <label className="form-label form-label-sm">Task Name</label>
              <input
                className="form-control form-control-sm"
                value={form.task_name}
                onChange={(e) => setForm({ ...form, task_name: e.target.value })}
                required
              />
            </div>
            <div className="col-md-2">
              <label className="form-label form-label-sm">Assigned To</label>
              <input
                className="form-control form-control-sm"
                value={form.assigned_to}
                onChange={(e) => setForm({ ...form, assigned_to: e.target.value })}
              />
            </div>
            <div className="col-md-1">
              <label className="form-label form-label-sm">SLA Days</label>
              <input
                type="number"
                className="form-control form-control-sm"
                value={form.sla_days}
                onChange={(e) => setForm({ ...form, sla_days: Number(e.target.value) })}
                min={1}
              />
            </div>
            <div className="col-md-2">
              <label className="form-label form-label-sm">SLA Type</label>
              <select
                className="form-select form-select-sm"
                value={form.sla_type}
                onChange={(e) => setForm({ ...form, sla_type: e.target.value as 'Working Day' | 'Calendar Day' })}
              >
                <option value="Working Day">Working Day</option>
                <option value="Calendar Day">Calendar Day</option>
              </select>
            </div>
            <div className="col-md-2">
              <label className="form-label form-label-sm">Comments</label>
              <input
                className="form-control form-control-sm"
                value={form.comments}
                onChange={(e) => setForm({ ...form, comments: e.target.value })}
              />
            </div>
            <div className="col-md-1">
              <label className="form-label form-label-sm">Group</label>
              <select
                className="form-select form-select-sm"
                value={form.group_id}
                onChange={(e) => setForm({ ...form, group_id: e.target.value })}
              >
                <option value="">None</option>
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>{g.name}</option>
                ))}
              </select>
            </div>
            <div className="col-md-1">
              <button type="submit" className="btn btn-sm btn-primary w-100" disabled={loading}>
                {loading ? 'Adding…' : 'Add'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

export default TaskForm;
