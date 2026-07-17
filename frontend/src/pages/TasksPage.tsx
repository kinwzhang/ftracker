import React, { useState, useEffect, useCallback, useMemo } from 'react';
import MonthSelector from '../components/common/MonthSelector';
import Alert from '../components/common/Alert';
import LoadingSpinner from '../components/common/LoadingSpinner';
import {
  fetchTaskData,
  addTask,
  deleteTask,
  toggleTask,
  inlineSave,
  bulkSave,
  generateNextMonth,
  exportCsv,
  exportHtml,
} from '../api/tasks';
import type { GroupBlock, MonthStats, Task } from '../types';

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MONTH_NAMES = [
  '', 'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

function daysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

function getDayOfWeek(year: number, month: number, day: number): number {
  return new Date(year, month - 1, day).getDay();
}

function downloadBlob(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

interface GanttChartProps {
  groupBlocks: GroupBlock[];
  year: number;
  month: number;
}

const GanttChart: React.FC<GanttChartProps> = ({ groupBlocks, year, month }) => {
  const totalDays = daysInMonth(year, month);
  const today = new Date();
  const isCurrentMonth = today.getFullYear() === year && today.getMonth() + 1 === month;
  const todayDay = today.getDate();

  const dayHeaders = useMemo(() => {
    const headers: { day: number; wday: string; isWeekend: boolean }[] = [];
    for (let d = 1; d <= totalDays; d++) {
      const dow = getDayOfWeek(year, month, d);
      headers.push({
        day: d,
        wday: WEEKDAYS[dow],
        isWeekend: dow === 0 || dow === 6,
      });
    }
    return headers;
  }, [year, month, totalDays]);

  return (
    <div className="glass-card card mb-4">
      <div className="card-header d-flex align-items-center justify-content-between">
        <span>Gantt Chart — {MONTH_NAMES[month]} {year}</span>
      </div>
      <div className="card-body p-0">
        <div className="gantt-chart">
          <div className="gantt-canvas">
            <div className="day-header">
              <div className="day-header-spacer" />
              {dayHeaders.map((dh) => (
                <div
                  key={dh.day}
                  className={`day-cell${dh.isWeekend ? ' weekend' : ''}${isCurrentMonth && dh.day === todayDay ? ' today' : ''}`}
                >
                  <div>{dh.day}</div>
                  <div className="day-cell-wday">{dh.wday}</div>
                </div>
              ))}
            </div>

            {groupBlocks.map((block) => (
              <details key={block.id} className="gantt-group-block" open>
                <summary className="gantt-row gantt-group-summary">
                  <div className="gantt-label">
                    <span className="gantt-group-chevron" />
                    {block.group?.name || 'Ungrouped'}
                  </div>
                  <div className="gantt-track" style={{ position: 'relative' }}>
                    {block.group_bar && (
                      <div
                        className={`gantt-bar group status-${block.group_bar.status}`}
                        style={{
                          left: `${(block.group_bar.start_offset / totalDays) * 100}%`,
                          width: `${Math.max((block.group_bar.width / totalDays) * 100, 2)}%`,
                        }}
                      >
                        <span className="gantt-bar-label">
                          {block.group?.name || 'Ungrouped'}
                          <span className="gantt-bar-count">
                            {block.summary.overdue > 0 && (
                              <span className="gantt-bar-count-overdue">
                                <strong>{block.summary.overdue}</strong> overdue
                              </span>
                            )}
                            {block.summary.pending > 0 && (
                              <span className="gantt-bar-count-pending">
                                <strong>{block.summary.pending}</strong> pending
                              </span>
                            )}
                            {block.summary.completed > 0 && (
                              <span className="gantt-bar-count-completed">
                                <strong>{block.summary.completed}</strong> done
                              </span>
                            )}
                          </span>
                        </span>
                      </div>
                    )}
                  </div>
                </summary>

                {block.gantt_tasks.map((gt) => {
                  const status = gt.task.finished
                    ? 'completed'
                    : new Date(gt.task.scheduled_date) < new Date()
                      ? 'overdue'
                      : 'pending';
                  return (
                    <div key={gt.task.id} className="gantt-row">
                      <div className="gantt-label" title={gt.task.task_name}>
                        {gt.task.task_name}
                      </div>
                      <div className="gantt-track" style={{ position: 'relative' }}>
                        <div
                          className={`gantt-bar ${status}`}
                          style={{
                            left: `${(gt.start_offset / totalDays) * 100}%`,
                            width: `${Math.max((gt.duration / totalDays) * 100, 2)}%`,
                          }}
                        />
                        {isCurrentMonth && (
                          <div
                            className="today-line"
                            style={{ left: `${((todayDay - 0.5) / totalDays) * 100}%` }}
                          />
                        )}
                      </div>
                    </div>
                  );
                })}
              </details>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

const TasksPage: React.FC = () => {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const monthStr = `${year}-${String(month).padStart(2, '0')}`;

  const [groupBlocks, setGroupBlocks] = useState<GroupBlock[]>([]);
  const [stats, setStats] = useState<MonthStats>({ total: 0, completed: 0, pending: 0, overdue: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [alertMsg, setAlertMsg] = useState<{ type: 'success' | 'danger'; text: string } | null>(null);

  const [bulkEditMode, setBulkEditMode] = useState(false);
  const [selectedTasks, setSelectedTasks] = useState<Set<number>>(new Set());
  const [bulkField, setBulkField] = useState('');
  const [bulkValue, setBulkValue] = useState('');

  const [editingCell, setEditingCell] = useState<{ taskId: number; field: string } | null>(null);
  const [editValue, setEditValue] = useState('');

  const [quickAdd, setQuickAdd] = useState({
    task_name: '',
    assigned_to: '',
    sla_days: 5,
    sla_type: 'Working Day',
    group_id: '',
  });

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data: any = await fetchTaskData(monthStr);
      setGroupBlocks(data.group_blocks || []);
      setStats(data.stats || { total: 0, completed: 0, pending: 0, overdue: 0 });
    } catch (e: any) {
      setError(e?.response?.data?.error || e.message || 'Failed to load tasks');
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

  const allTasks = useMemo(() => {
    const tasks: Task[] = [];
    groupBlocks.forEach((b) => tasks.push(...b.tasks));
    return tasks;
  }, [groupBlocks]);

  const handleToggle = async (id: number) => {
    try {
      await toggleTask(id);
      loadData();
    } catch (e: any) {
      setAlertMsg({ type: 'danger', text: e?.response?.data?.error || 'Toggle failed' });
    }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm('Delete this task?')) return;
    try {
      await deleteTask(id);
      setAlertMsg({ type: 'success', text: 'Task deleted' });
      loadData();
    } catch (e: any) {
      setAlertMsg({ type: 'danger', text: e?.response?.data?.error || 'Delete failed' });
    }
  };

  const handleInlineEditStart = (taskId: number, field: string, currentValue: string) => {
    setEditingCell({ taskId, field });
    setEditValue(currentValue ?? '');
  };

  const handleInlineEditSave = async (taskId: number, field: string) => {
    try {
      await inlineSave(taskId, { [field]: editValue });
      setEditingCell(null);
      loadData();
    } catch (e: any) {
      setAlertMsg({ type: 'danger', text: e?.response?.data?.error || 'Save failed' });
    }
  };

  const handleBulkToggle = (taskId: number) => {
    setSelectedTasks((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) next.delete(taskId);
      else next.add(taskId);
      return next;
    });
  };

  const handleSelectAll = () => {
    if (selectedTasks.size === allTasks.length) {
      setSelectedTasks(new Set());
    } else {
      setSelectedTasks(new Set(allTasks.map((t) => t.id)));
    }
  };

  const handleBulkSave = async () => {
    if (!bulkField || selectedTasks.size === 0) return;
    const updates = Array.from(selectedTasks).map((id) => ({
      id,
      [bulkField]: bulkValue,
    }));
    try {
      await bulkSave(updates);
      setAlertMsg({ type: 'success', text: `Updated ${updates.length} tasks` });
      setBulkEditMode(false);
      setSelectedTasks(new Set());
      setBulkField('');
      setBulkValue('');
      loadData();
    } catch (e: any) {
      setAlertMsg({ type: 'danger', text: e?.response?.data?.error || 'Bulk save failed' });
    }
  };

  const handleGenerateNextMonth = async () => {
    if (!window.confirm('Generate tasks for next month?')) return;
    try {
      await generateNextMonth();
      setAlertMsg({ type: 'success', text: 'Next month generated' });
      loadData();
    } catch (e: any) {
      setAlertMsg({ type: 'danger', text: e?.response?.data?.error || 'Generate failed' });
    }
  };

  const handleExportCsv = async () => {
    try {
      const data: any = await exportCsv(monthStr);
      downloadBlob(typeof data === 'string' ? data : JSON.stringify(data), `tasks-${monthStr}.csv`, 'text/csv');
    } catch (e: any) {
      setAlertMsg({ type: 'danger', text: e?.response?.data?.error || 'Export failed' });
    }
  };

  const handleExportHtml = async () => {
    try {
      const data: any = await exportHtml(monthStr);
      downloadBlob(typeof data === 'string' ? data : JSON.stringify(data), `tasks-${monthStr}.html`, 'text/html');
    } catch (e: any) {
      setAlertMsg({ type: 'danger', text: e?.response?.data?.error || 'Export failed' });
    }
  };

  const handleQuickAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickAdd.task_name.trim()) return;
    try {
      await addTask({
        ...quickAdd,
        sla_days: Number(quickAdd.sla_days),
        group_id: quickAdd.group_id ? Number(quickAdd.group_id) : null,
        month: monthStr,
      });
      setAlertMsg({ type: 'success', text: 'Task added' });
      setQuickAdd({ task_name: '', assigned_to: '', sla_days: 5, sla_type: 'Working Day', group_id: '' });
      loadData();
    } catch (e: any) {
      setAlertMsg({ type: 'danger', text: e?.response?.data?.error || 'Add failed' });
    }
  };

  const renderEditableCell = (task: Task, field: string, displayValue: string) => {
    const isEditing = editingCell?.taskId === task.id && editingCell?.field === field;
    if (bulkEditMode) {
      return <span className="view-mode">{displayValue}</span>;
    }
    if (isEditing) {
      return (
        <input
          className="form-control form-control-sm edit-mode"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onBlur={() => handleInlineEditSave(task.id, field)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleInlineEditSave(task.id, field);
            if (e.key === 'Escape') setEditingCell(null);
          }}
          autoFocus
        />
      );
    }
    return (
      <span
        className="view-mode"
        style={{ cursor: 'pointer' }}
        onClick={() => handleInlineEditStart(task.id, field, displayValue)}
        title="Click to edit"
      >
        {displayValue}
      </span>
    );
  };

  const renderStatusBadge = (task: Task) => {
    if (task.finished) return <span className="badge bg-success">Done</span>;
    const schedDate = new Date(task.scheduled_date);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    if (schedDate < today) return <span className="badge bg-danger">Overdue</span>;
    return <span className="badge bg-primary">Pending</span>;
  };

  return (
    <div>
      <MonthSelector currentYear={year} currentMonth={month} onChange={handleMonthChange} />

      {alertMsg && (
        <div className="mt-3">
          <Alert type={alertMsg.type} message={alertMsg.text} onDismiss={() => setAlertMsg(null)} />
        </div>
      )}

      <div className="row g-3 mt-2">
        <div className="col-md-4">
          <div className="stat-card glass-success glass-card">
            <p className="stat-number">{stats.completed}</p>
            <p className="stat-label">Completed</p>
          </div>
        </div>
        <div className="col-md-4">
          <div className="stat-card glass-warning glass-card">
            <p className="stat-number">{stats.pending}</p>
            <p className="stat-label">In Progress</p>
          </div>
        </div>
        <div className="col-md-4">
          <div className="stat-card glass-danger glass-card">
            <p className="stat-number">{stats.overdue}</p>
            <p className="stat-label">Overdue</p>
          </div>
        </div>
      </div>

      <div className="d-flex flex-wrap gap-2 mt-3 mb-3">
        <button className="btn btn-sm btn-primary" onClick={() => {
          setQuickAdd({ task_name: '', assigned_to: '', sla_days: 5, sla_type: 'Working Day', group_id: '' });
          document.getElementById('quick-add-form')?.scrollIntoView({ behavior: 'smooth' });
        }}>
          + Add Task
        </button>
        <button className="btn btn-sm btn-outline-primary" onClick={handleGenerateNextMonth}>
          Generate Next Month
        </button>
        <button className="btn btn-sm btn-outline-success" onClick={handleExportCsv}>
          Export CSV
        </button>
        <button className="btn btn-sm btn-outline-info" onClick={handleExportHtml}>
          Export HTML Report
        </button>
        <button
          className={`btn btn-sm ${bulkEditMode ? 'btn-warning' : 'btn-outline-secondary'}`}
          onClick={() => {
            setBulkEditMode(!bulkEditMode);
            setSelectedTasks(new Set());
            setBulkField('');
            setBulkValue('');
          }}
        >
          {bulkEditMode ? 'Cancel Bulk Edit' : 'Bulk Edit'}
        </button>
      </div>

      {bulkEditMode && selectedTasks.size > 0 && (
        <div className="glass-card card mb-3">
          <div className="card-body d-flex align-items-center gap-2 flex-wrap">
            <span className="fw-semibold">Bulk edit {selectedTasks.size} tasks:</span>
            <select className="form-select form-select-sm" style={{ width: '160px' }} value={bulkField} onChange={(e) => setBulkField(e.target.value)}>
              <option value="">Select field...</option>
              <option value="assigned_to">Assigned To</option>
              <option value="sla_days">SLA Days</option>
              <option value="sla_type">SLA Type</option>
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
                <button className="btn btn-sm btn-primary" onClick={handleBulkSave}>
                  Save Bulk
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {loading ? (
        <LoadingSpinner message="Loading tasks..." />
      ) : error ? (
        <Alert type="danger" message={error} onDismiss={() => setError(null)} />
      ) : (
        <>
          {groupBlocks.length > 0 && (
            <GanttChart groupBlocks={groupBlocks} year={year} month={month} />
          )}

          <div className="glass-card card mb-4">
            <div className="card-header">
              Tasks — {MONTH_NAMES[month]} {year} ({allTasks.length} total)
            </div>
            <div className="card-body p-0">
              <div className="table-responsive">
                <table className="table table-hover mb-0">
                  <thead>
                    <tr>
                      {bulkEditMode && <th style={{ width: '40px' }}><input type="checkbox" checked={selectedTasks.size === allTasks.length && allTasks.length > 0} onChange={handleSelectAll} /></th>}
                      <th>Task Name</th>
                      <th>Assigned To</th>
                      <th>SLA</th>
                      <th>Scheduled</th>
                      <th>Status</th>
                      <th>Comments</th>
                      <th style={{ width: '80px' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {groupBlocks.map((block) => (
                      <React.Fragment key={block.id}>
                        <tr className={`group-summary-row status-${block.summary.status}`}>
                          <td colSpan={bulkEditMode ? 8 : 7}>
                            <div className="d-flex align-items-center justify-content-between">
                              <div className="group-summary-counts">
                                <strong>{block.group?.name || 'Ungrouped'}</strong>
                                <span className="gantt-bar-count ms-3">
                                  {block.summary.overdue > 0 && (
                                    <span className="gantt-bar-count-overdue">
                                      <strong>{block.summary.overdue}</strong> overdue
                                    </span>
                                  )}
                                  {block.summary.pending > 0 && (
                                    <span className="gantt-bar-count-pending">
                                      <strong>{block.summary.pending}</strong> pending
                                    </span>
                                  )}
                                  {block.summary.completed > 0 && (
                                    <span className="gantt-bar-count-completed">
                                      <strong>{block.summary.completed}</strong> done
                                    </span>
                                  )}
                                </span>
                              </div>
                            </div>
                          </td>
                        </tr>
                        {block.tasks.map((task) => (
                          <tr key={task.id} className={task.finished ? 'row-completed' : (new Date(task.scheduled_date) < new Date() ? 'row-overdue' : 'row-pending')}>
                            {bulkEditMode && (
                              <td>
                                <input
                                  type="checkbox"
                                  checked={selectedTasks.has(task.id)}
                                  onChange={() => handleBulkToggle(task.id)}
                                />
                              </td>
                            )}
                            <td>{renderEditableCell(task, 'task_name', task.task_name)}</td>
                            <td>{renderEditableCell(task, 'assigned_to', task.assigned_to)}</td>
                            <td>{renderEditableCell(task, 'sla_days', `${task.sla_days} ${task.sla_type}`)}</td>
                            <td className="view-mode">{task.scheduled_date}</td>
                            <td>
                              <span className="view-mode" onClick={() => handleToggle(task.id)} style={{ cursor: 'pointer' }}>
                                {renderStatusBadge(task)}
                              </span>
                            </td>
                            <td>
                              {renderEditableCell(task, 'comments', task.comments || '—')}
                            </td>
                            <td>
                              <button
                                className="btn btn-sm btn-outline-danger view-mode"
                                onClick={() => handleDelete(task.id)}
                                title="Delete task"
                              >
                                ✕
                              </button>
                            </td>
                          </tr>
                        ))}
                      </React.Fragment>
                    ))}
                    {allTasks.length === 0 && (
                      <tr>
                        <td colSpan={bulkEditMode ? 8 : 7} className="text-center text-muted py-4">
                          No tasks for this month. Click "Generate Next Month" or add a task below.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div id="quick-add-form" className="glass-card card mb-4">
            <div className="card-header">Quick Add Task</div>
            <div className="card-body">
              <form onSubmit={handleQuickAdd}>
                <div className="row g-2 align-items-end">
                  <div className="col-md-3">
                    <label className="form-label form-label-sm">Task Name</label>
                    <input
                      className="form-control form-control-sm"
                      value={quickAdd.task_name}
                      onChange={(e) => setQuickAdd({ ...quickAdd, task_name: e.target.value })}
                      required
                    />
                  </div>
                  <div className="col-md-2">
                    <label className="form-label form-label-sm">Assigned To</label>
                    <input
                      className="form-control form-control-sm"
                      value={quickAdd.assigned_to}
                      onChange={(e) => setQuickAdd({ ...quickAdd, assigned_to: e.target.value })}
                    />
                  </div>
                  <div className="col-md-1">
                    <label className="form-label form-label-sm">SLA Days</label>
                    <input
                      type="number"
                      className="form-control form-control-sm"
                      value={quickAdd.sla_days}
                      onChange={(e) => setQuickAdd({ ...quickAdd, sla_days: Number(e.target.value) })}
                      min={1}
                    />
                  </div>
                  <div className="col-md-2">
                    <label className="form-label form-label-sm">SLA Type</label>
                    <select
                      className="form-select form-select-sm"
                      value={quickAdd.sla_type}
                      onChange={(e) => setQuickAdd({ ...quickAdd, sla_type: e.target.value })}
                    >
                      <option value="Working Day">Working Day</option>
                      <option value="Calendar Day">Calendar Day</option>
                    </select>
                  </div>
                  <div className="col-md-2">
                    <label className="form-label form-label-sm">Group ID</label>
                    <input
                      type="number"
                      className="form-control form-control-sm"
                      value={quickAdd.group_id}
                      onChange={(e) => setQuickAdd({ ...quickAdd, group_id: e.target.value })}
                      placeholder="Optional"
                    />
                  </div>
                  <div className="col-md-2">
                    <button type="submit" className="btn btn-sm btn-primary w-100">
                      Add Task
                    </button>
                  </div>
                </div>
              </form>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default TasksPage;
