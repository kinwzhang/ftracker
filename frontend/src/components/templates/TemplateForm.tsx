import React, { useState, useEffect } from 'react';
import type { Group, TaskTemplate } from '../../types';

interface TemplateFormProps {
  groups: Group[];
  initialData?: Partial<TaskTemplate>;
  onSubmit: (data: Record<string, unknown>) => void;
  loading: boolean;
}

const TemplateForm: React.FC<TemplateFormProps> = ({ groups, initialData, onSubmit, loading }) => {
  const [taskName, setTaskName] = useState('');
  const [assignedTo, setAssignedTo] = useState('');
  const [slaDays, setSlaDays] = useState(5);
  const [slaType, setSlaType] = useState<'Working Day' | 'Calendar Day'>('Working Day');
  const [sortOrder, setSortOrder] = useState(0);
  const [groupId, setGroupId] = useState<string>('');

  useEffect(() => {
    if (initialData) {
      setTaskName(initialData.task_name || '');
      setAssignedTo(initialData.assigned_to || '');
      setSlaDays(initialData.sla_days ?? 5);
      setSlaType(initialData.sla_type || 'Working Day');
      setSortOrder(initialData.sort_order ?? 0);
      setGroupId(initialData.group_id != null ? String(initialData.group_id) : '');
    }
  }, [initialData]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!taskName.trim()) return;
    onSubmit({
      task_name: taskName.trim(),
      assigned_to: assignedTo.trim(),
      sla_days: slaDays,
      sla_type: slaType,
      sort_order: sortOrder,
      group_id: groupId ? Number(groupId) : null,
    });
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="row g-2 align-items-end">
        <div className="col-md-2">
          <label className="form-label form-label-sm">Task Name</label>
          <input className="form-control form-control-sm" value={taskName} onChange={(e) => setTaskName(e.target.value)} required />
        </div>
        <div className="col-md-2">
          <label className="form-label form-label-sm">Assigned To</label>
          <input className="form-control form-control-sm" value={assignedTo} onChange={(e) => setAssignedTo(e.target.value)} />
        </div>
        <div className="col-md-1">
          <label className="form-label form-label-sm">SLA Days</label>
          <input type="number" className="form-control form-control-sm" value={slaDays} onChange={(e) => setSlaDays(Number(e.target.value))} min={1} />
        </div>
        <div className="col-md-2">
          <label className="form-label form-label-sm">SLA Type</label>
          <select className="form-select form-select-sm" value={slaType} onChange={(e) => setSlaType(e.target.value as 'Working Day' | 'Calendar Day')}>
            <option value="Working Day">Working Day</option>
            <option value="Calendar Day">Calendar Day</option>
          </select>
        </div>
        <div className="col-md-1">
          <label className="form-label form-label-sm">Order</label>
          <input type="number" className="form-control form-control-sm" value={sortOrder} onChange={(e) => setSortOrder(Number(e.target.value))} />
        </div>
        <div className="col-md-2">
          <label className="form-label form-label-sm">Group</label>
          <select className="form-select form-select-sm" value={groupId} onChange={(e) => setGroupId(e.target.value)}>
            <option value="">No Group</option>
            {groups.map((g) => (
              <option key={g.id} value={g.id}>{g.name}</option>
            ))}
          </select>
        </div>
        <div className="col-md-2">
          <button type="submit" className="btn btn-sm btn-primary w-100" disabled={loading}>
            {loading ? 'Saving...' : 'Submit'}
          </button>
        </div>
      </div>
    </form>
  );
};

export default TemplateForm;
