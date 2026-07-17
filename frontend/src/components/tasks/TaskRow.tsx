import React, { useState, useRef } from 'react';
import type { Task, Group } from '../../types';

interface TaskRowProps {
  task: Task;
  groups: Group[];
  isEditing: boolean;
  onEdit: () => void;
  onSave: (data: Record<string, unknown>) => void;
  onDelete: () => void;
  onToggle: () => void;
  onCommentSave: (comments: string) => void;
}

function isOverdue(task: Task): boolean {
  if (task.finished) return false;
  if (!task.scheduled_date) return false;
  return new Date(task.scheduled_date) < new Date();
}

function getRowClass(task: Task): string {
  if (task.finished) return 'row-completed';
  if (isOverdue(task)) return 'row-overdue';
  return 'row-pending';
}

function getStatusBadge(task: Task) {
  if (task.finished) return <span className="badge bg-success">Done</span>;
  if (isOverdue(task)) return <span className="badge bg-danger">Overdue</span>;
  return <span className="badge bg-primary">Pending</span>;
}

function truncate(text: string, max: number): string {
  if (!text) return '';
  return text.length > max ? text.substring(0, max) + '…' : text;
}

function toDatetimeLocal(dateStr: string | null): string {
  if (!dateStr) return '';
  return dateStr.substring(0, 16);
}

function fromDatetimeLocal(val: string): string {
  return val ? val.substring(0, 10) : '';
}

const TaskRow: React.FC<TaskRowProps> = ({
  task,
  groups,
  isEditing,
  onEdit,
  onSave,
  onDelete,
  onToggle,
  onCommentSave,
}) => {
  const [form, setForm] = useState({
    task_name: task.task_name,
    assigned_to: task.assigned_to,
    sla_days: task.sla_days,
    sla_type: task.sla_type,
    completion_date: task.completion_date || '',
    comments: task.comments || '',
    group_id: task.group_id ?? '',
  });

  const [commentValue, setCommentValue] = useState(task.comments || '');
  const [editingComment, setEditingComment] = useState(false);
  const commentRef = useRef<HTMLInputElement>(null);

  const handleSave = () => {
    onSave({
      task_name: form.task_name,
      assigned_to: form.assigned_to,
      sla_days: Number(form.sla_days),
      sla_type: form.sla_type,
      completion_date: form.completion_date || null,
      comments: form.comments,
      group_id: form.group_id !== '' ? Number(form.group_id) : null,
    });
  };

  const handleCommentBlur = () => {
    setEditingComment(false);
    if (commentValue !== (task.comments || '')) {
      onCommentSave(commentValue);
    }
  };

  const handleCommentKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      (e.target as HTMLInputElement).blur();
    }
    if (e.key === 'Escape') {
      setCommentValue(task.comments || '');
      setEditingComment(false);
    }
  };

  const slaTypeOptions = ['Working Day', 'Calendar Day'];

  if (isEditing) {
    return (
      <tr className={getRowClass(task)}>
        <td>
          <input
            className="form-control form-control-sm edit-mode"
            value={form.task_name}
            onChange={(e) => setForm({ ...form, task_name: e.target.value })}
          />
        </td>
        <td>
          <input
            className="form-control form-control-sm edit-mode"
            value={form.assigned_to}
            onChange={(e) => setForm({ ...form, assigned_to: e.target.value })}
          />
        </td>
        <td>
          <div className="d-flex gap-1">
            <input
              type="number"
              className="form-control form-control-sm edit-mode"
              value={form.sla_days}
              min={1}
              onChange={(e) => setForm({ ...form, sla_days: Number(e.target.value) })}
              style={{ width: '50px' }}
            />
            <select
              className="form-select form-select-sm edit-mode"
              value={form.sla_type}
              onChange={(e) => setForm({ ...form, sla_type: e.target.value as Task['sla_type'] })}
            >
              {slaTypeOptions.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          </div>
        </td>
        <td>{task.scheduled_date}</td>
        <td>
          <input
            type="datetime-local"
            className="form-control form-control-sm edit-mode"
            value={toDatetimeLocal(form.completion_date)}
            onChange={(e) => setForm({ ...form, completion_date: fromDatetimeLocal(e.target.value) })}
          />
        </td>
        <td>
          <input
            className="form-control form-control-sm edit-mode"
            value={commentValue}
            onChange={(e) => setCommentValue(e.target.value)}
          />
        </td>
        <td>
          <select
            className="form-select form-select-sm edit-mode"
            value={form.group_id}
            onChange={(e) => setForm({ ...form, group_id: e.target.value })}
          >
            <option value="">No Group</option>
            {groups.map((g) => (
              <option key={g.id} value={g.id}>{g.name}</option>
            ))}
          </select>
        </td>
        <td>
          <div className="d-flex gap-1">
            <button className="btn btn-sm btn-success view-mode" onClick={handleSave}>
              Save
            </button>
            <button className="btn btn-sm btn-outline-danger view-mode" onClick={onDelete}>
              Delete
            </button>
          </div>
        </td>
      </tr>
    );
  }

  return (
    <tr className={getRowClass(task)}>
      <td>{task.task_name}</td>
      <td>{task.assigned_to}</td>
      <td>
        {task.sla_days} {task.sla_type === 'Working Day' ? 'WD' : 'CD'}
      </td>
      <td>{task.scheduled_date}</td>
      <td>
        <span
          className="view-mode"
          style={{ cursor: 'pointer' }}
          onClick={onToggle}
          title="Click to toggle status"
        >
          {getStatusBadge(task)}
        </span>
        {task.completion_date && (
          <div className="text-muted" style={{ fontSize: '0.75rem' }}>
            {task.completion_date}
          </div>
        )}
      </td>
      <td className="comment-cell">
        {editingComment ? (
          <input
            ref={commentRef}
            className="form-control form-control-sm"
            value={commentValue}
            onChange={(e) => setCommentValue(e.target.value)}
            onBlur={handleCommentBlur}
            onKeyDown={handleCommentKeyDown}
            autoFocus
          />
        ) : (
          <span
            className="inline-comment view-mode"
            style={{ cursor: 'pointer' }}
            onClick={() => {
              setEditingComment(true);
              setTimeout(() => commentRef.current?.focus(), 0);
            }}
            title="Click to edit comment"
          >
            {truncate(task.comments, 20) || '—'}
          </span>
        )}
      </td>
      <td>{task.group_name || '—'}</td>
      <td>
        <div className="d-flex gap-1">
          <button className="btn btn-sm btn-outline-primary view-mode" onClick={onEdit}>
            Edit
          </button>
          <button className="btn btn-sm btn-outline-danger view-mode" onClick={onDelete}>
            Delete
          </button>
        </div>
      </td>
    </tr>
  );
};

export default TaskRow;
