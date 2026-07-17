import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import MonthSelector from '../components/common/MonthSelector';
import Alert from '../components/common/Alert';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ConfirmDialog from '../components/common/ConfirmDialog';
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

function isBeforeToday(dateStr: string): boolean {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const d = new Date(dateStr);
  return d < today;
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

interface GanttChartProps {
  groupBlocks: GroupBlock[];
  year: number;
  month: number;
  expandedGroups: Set<number>;
  onToggleGroup: (id: number) => void;
  onExpandAll: () => void;
  onCollapseAll: () => void;
}

const GanttChart: React.FC<GanttChartProps> = ({
  groupBlocks,
  year,
  month,
  expandedGroups,
  onToggleGroup,
  onExpandAll,
  onCollapseAll,
}) => {
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
        <span className="d-flex gap-2">
          <button type="button" className="btn btn-sm btn-outline-secondary" onClick={onExpandAll}>Expand all</button>
          <button type="button" className="btn btn-sm btn-outline-secondary" onClick={onCollapseAll}>Collapse all</button>
        </span>
      </div>
      <div className="card-body gantt-chart">
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

          <div className="gantt-tracks-wrapper">
            {isCurrentMonth && (
              <div
                className="today-line"
                style={{ left: `calc(200px + (100% - 200px) * ${((todayDay - 0.5) / totalDays) * 100} / 100)` }}
              />
            )}

            {groupBlocks.map((block) => {
              const isOpen = expandedGroups.has(block.id);
              return (
                <div key={block.id} className="gantt-group-block">
                  <div
                    className={`gantt-row gantt-group-summary status-${block.summary.status}`}
                    style={{ cursor: 'pointer' }}
                    onClick={() => onToggleGroup(block.id)}
                  >
                    <div className="gantt-label">
                      <span className="gantt-group-chevron" style={{ display: 'inline-block' }}>
                        {isOpen ? '\u25BE' : '\u25B8'}
                      </span>
                      <strong>{block.group?.name || 'Ungrouped'}</strong>
                      <span className="badge bg-secondary ms-1">{block.summary.completed}/{block.summary.total}</span>
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
                            {block.summary.overdue > 0 && (
                              <span className="gantt-bar-count gantt-bar-count-overdue">
                                <strong>{block.summary.overdue}</strong> overdue
                              </span>
                            )}
                            {block.summary.pending > 0 && (
                              <span className="gantt-bar-count gantt-bar-count-pending">
                                <strong>{block.summary.pending}</strong> in progress
                              </span>
                            )}
                            {block.summary.completed > 0 && (
                              <span className="gantt-bar-count gantt-bar-count-completed">
                                <strong>{block.summary.completed}</strong> completed
                              </span>
                            )}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  {isOpen && block.gantt_tasks.map((gt) => {
                    const status = gt.task.finished
                      ? 'completed'
                      : isBeforeToday(gt.task.scheduled_date)
                        ? 'overdue'
                        : 'pending';
                    return (
                      <div key={gt.task.id} className="gantt-row">
                        <div className="gantt-label" title={`${gt.task.task_name} (${gt.task.scheduled_date})`}>
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
                        </div>
                      </div>
                    );
                  })}
                </div>
              );
            })}
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

  const [editingRow, setEditingRow] = useState<number | null>(null);
  const [editData, setEditData] = useState<Record<string, string>>({});

  const [ganttExpanded, setGanttExpanded] = useState<Set<number>>(new Set());
  const [tableExpanded, setTableExpanded] = useState<Set<number>>(new Set());

  const [bulkEditMode, setBulkEditMode] = useState(false);
  const [selectedTasks, setSelectedTasks] = useState<Set<number>>(new Set());
  const [bulkEditData, setBulkEditData] = useState<Record<number, Record<string, string>>>({});

  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);
  const [confirmGenerate, setConfirmGenerate] = useState(false);

  const [quickAdd, setQuickAdd] = useState({
    task_name: '',
    assigned_to: '',
    sla_days: 5,
    sla_type: 'Working Day',
    comments: '',
    group: '',
  });

  const quickAddRef = useRef<HTMLDivElement>(null);

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
    setEditingRow(null);
    setBulkEditMode(false);
    setSelectedTasks(new Set());
    setBulkEditData({});
  };

  const allTasks = useMemo(() => {
    const tasks: Task[] = [];
    groupBlocks.forEach((b) => tasks.push(...b.tasks));
    return tasks;
  }, [groupBlocks]);

  const groups = useMemo(() => {
    const map = new Map<number, string>();
    groupBlocks.forEach((b) => {
      if (b.group) map.set(b.group.id, b.group.name);
    });
    return Array.from(map.entries()).map(([id, name]) => ({ id, name }));
  }, [groupBlocks]);

  const toggleGanttGroup = (id: number) => {
    setGanttExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const expandAllGantt = () => setGanttExpanded(new Set(groupBlocks.map((b) => b.id)));
  const collapseAllGantt = () => setGanttExpanded(new Set());

  const toggleTableGroup = (id: number) => {
    setTableExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const expandAllTable = () => setTableExpanded(new Set(groupBlocks.map((b) => b.id)));
  const collapseAllTable = () => setTableExpanded(new Set());

  const handleToggle = async (id: number) => {
    try {
      await toggleTask(id);
      loadData();
    } catch (e: any) {
      setAlertMsg({ type: 'danger', text: e?.response?.data?.error || 'Toggle failed' });
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteTask(id);
      setAlertMsg({ type: 'success', text: 'Task deleted' });
      setConfirmDelete(null);
      loadData();
    } catch (e: any) {
      setAlertMsg({ type: 'danger', text: e?.response?.data?.error || 'Delete failed' });
    }
  };

  const startEditRow = (task: Task) => {
    setEditingRow(task.id);
    setEditData({
      task_name: task.task_name,
      assigned_to: task.assigned_to,
      sla_days: String(task.sla_days),
      sla_type: task.sla_type,
      completion_date: task.completion_date
        ? `${task.completion_date}T${task.completion_time || '00:00'}`
        : '',
      comments: task.comments || '',
      group: task.group_id != null ? String(task.group_id) : '',
    });
  };

  const cancelEditRow = () => {
    setEditingRow(null);
    setEditData({});
  };

  const saveEditRow = async (taskId: number) => {
    try {
      const payload: Record<string, unknown> = {
        task_name: editData.task_name,
        assigned_to: editData.assigned_to,
        sla_days: Number(editData.sla_days),
        sla_type: editData.sla_type,
        comments: editData.comments,
        group: editData.group || '',
      };
      if (editData.completion_date) {
        const dt = editData.completion_date;
        if (dt.includes('T')) {
          const [d, t] = dt.split('T');
          payload.completion_date = d;
          payload.completion_time = t;
        } else {
          payload.completion_date = dt;
        }
      }
      await inlineSave(taskId, payload);
      setEditingRow(null);
      setEditData({});
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

  const enterBulkEdit = () => {
    const initial: Record<number, Record<string, string>> = {};
    allTasks.forEach((t) => {
      initial[t.id] = {
        task_name: t.task_name,
        assigned_to: t.assigned_to,
        sla_days: String(t.sla_days),
        sla_type: t.sla_type,
        completion_date: t.completion_date
          ? `${t.completion_date}T${t.completion_time || '00:00'}`
          : '',
        comments: t.comments || '',
        group: t.group_id != null ? String(t.group_id) : '',
      };
    });
    setBulkEditData(initial);
    setBulkEditMode(true);
  };

  const exitBulkEdit = () => {
    setBulkEditMode(false);
    setSelectedTasks(new Set());
    setBulkEditData({});
  };

  const handleBulkSave = async () => {
    const updates: Record<string, unknown>[] = [];
    selectedTasks.forEach((id) => {
      const data = bulkEditData[id];
      if (data) {
        updates.push({
          id,
          task_name: data.task_name,
          assigned_to: data.assigned_to,
          sla_days: Number(data.sla_days),
          sla_type: data.sla_type,
          comments: data.comments,
          group: data.group || '',
          completion_date: data.completion_date || '',
        });
      }
    });
    if (updates.length === 0) return;
    try {
      await bulkSave(updates);
      setAlertMsg({ type: 'success', text: `Updated ${updates.length} tasks` });
      exitBulkEdit();
      loadData();
    } catch (e: any) {
      setAlertMsg({ type: 'danger', text: e?.response?.data?.error || 'Bulk save failed' });
    }
  };

  const handleGenerateNextMonth = async () => {
    try {
      await generateNextMonth();
      setAlertMsg({ type: 'success', text: 'Next month generated' });
      setConfirmGenerate(false);
      loadData();
    } catch (e: any) {
      setAlertMsg({ type: 'danger', text: e?.response?.data?.error || 'Generate failed' });
    }
  };

  const handleExportCsv = async () => {
    try {
      const data: any = await exportCsv(monthStr);
      const blob = new Blob([typeof data === 'string' ? data : JSON.stringify(data)], { type: 'text/csv' });
      triggerDownload(blob, `tasks-${monthStr}.csv`);
    } catch (e: any) {
      setAlertMsg({ type: 'danger', text: e?.response?.data?.error || 'Export failed' });
    }
  };

  const handleExportHtml = async () => {
    try {
      const data: any = await exportHtml(monthStr);
      const blob = new Blob([typeof data === 'string' ? data : JSON.stringify(data)], { type: 'text/html' });
      triggerDownload(blob, `tasks-${monthStr}.html`);
    } catch (e: any) {
      setAlertMsg({ type: 'danger', text: e?.response?.data?.error || 'Export failed' });
    }
  };

  const handleQuickAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickAdd.task_name.trim()) return;
    try {
      await addTask({
        task_name: quickAdd.task_name,
        assigned_to: quickAdd.assigned_to,
        sla_days: Number(quickAdd.sla_days),
        sla_type: quickAdd.sla_type,
        comments: quickAdd.comments,
        group: quickAdd.group || '',
        month: monthStr,
      });
      setAlertMsg({ type: 'success', text: 'Task added' });
      setQuickAdd({ task_name: '', assigned_to: '', sla_days: 5, sla_type: 'Working Day', comments: '', group: '' });
      loadData();
    } catch (e: any) {
      setAlertMsg({ type: 'danger', text: e?.response?.data?.error || 'Add failed' });
    }
  };

  const scrollToQuickAdd = () => {
    quickAddRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h3>Tasks for {MONTH_NAMES[month]} {year}</h3>
        <MonthSelector currentYear={year} currentMonth={month} onChange={handleMonthChange} />
      </div>

      {alertMsg && (
        <div className="mb-3">
          <Alert type={alertMsg.type} message={alertMsg.text} onDismiss={() => setAlertMsg(null)} />
        </div>
      )}

      <div className="row g-3 mb-4">
        <div className="col-md-4">
          <div className="stat-card glass-success">
            <p className="stat-number">{stats.completed}</p>
            <p className="stat-label">Completed</p>
          </div>
        </div>
        <div className="col-md-4">
          <div className="stat-card glass-warning">
            <p className="stat-number">{stats.pending}</p>
            <p className="stat-label">In Progress</p>
          </div>
        </div>
        <div className="col-md-4">
          <div className="stat-card glass-danger">
            <p className="stat-number">{stats.overdue}</p>
            <p className="stat-label">Overdue</p>
          </div>
        </div>
      </div>

      <div className="d-flex gap-2 mb-4 flex-wrap">
        <button className="btn btn-primary btn-sm px-3" onClick={() => { setQuickAdd({ task_name: '', assigned_to: '', sla_days: 5, sla_type: 'Working Day', comments: '', group: '' }); scrollToQuickAdd(); }}>
          + Add Task
        </button>
        <button className="btn btn-success btn-sm px-3" onClick={() => setConfirmGenerate(true)}>
          Generate Next Month
        </button>
        <button className="btn btn-sm btn-outline-secondary px-3" onClick={handleExportCsv}>Export CSV</button>
        <button className="btn btn-sm btn-outline-secondary px-3" onClick={handleExportHtml}>Export HTML Report</button>
      </div>

      {loading ? (
        <LoadingSpinner message="Loading tasks..." />
      ) : error ? (
        <Alert type="danger" message={error} onDismiss={() => setError(null)} />
      ) : (
        <>
          {groupBlocks.length > 0 && (
            <GanttChart
              groupBlocks={groupBlocks}
              year={year}
              month={month}
              expandedGroups={ganttExpanded}
              onToggleGroup={toggleGanttGroup}
              onExpandAll={expandAllGantt}
              onCollapseAll={collapseAllGantt}
            />
          )}

          <div className="glass-card">
            <div className="card-header d-flex justify-content-between align-items-center">
              <span>Task List</span>
              <span className="d-flex align-items-center gap-2 flex-wrap">
                {editingRow != null && (
                  <span className="text-muted small px-2">
                    Editing — <a href="#" onClick={(e) => { e.preventDefault(); cancelEditRow(); }}>Done</a>
                  </span>
                )}
                <button type="button" className="btn btn-sm btn-outline-secondary" onClick={expandAllTable}>Expand all</button>
                <button type="button" className="btn btn-sm btn-outline-secondary" onClick={collapseAllTable}>Collapse all</button>
                <button
                  type="button"
                  className={`btn btn-sm ${bulkEditMode ? 'btn-outline-secondary' : 'btn-outline-primary'}`}
                  onClick={bulkEditMode ? exitBulkEdit : enterBulkEdit}
                >
                  {bulkEditMode ? 'Cancel' : 'Edit All'}
                </button>
                {bulkEditMode && (
                  <button type="button" className="btn btn-sm btn-primary" onClick={handleBulkSave}>
                    Save All
                  </button>
                )}
              </span>
            </div>
            <div className="card-body p-0">
              <table className="table table-sm mb-0" id="task-table">
                <thead>
                  <tr>
                    {bulkEditMode && <th style={{ width: '40px' }}><input type="checkbox" checked={selectedTasks.size === allTasks.length && allTasks.length > 0} onChange={() => { if (selectedTasks.size === allTasks.length) setSelectedTasks(new Set()); else setSelectedTasks(new Set(allTasks.map((t) => t.id))); }} /></th>}
                    <th style={{ width: '40px' }}>Done</th>
                    <th>Task Name</th>
                    <th>Assigned To</th>
                    <th style={{ width: '90px' }}>SLA</th>
                    <th style={{ width: '120px' }}>Scheduled</th>
                    <th>Comments</th>
                    <th style={{ width: '120px' }}>Group</th>
                    <th style={{ width: '220px' }}></th>
                  </tr>
                </thead>
                <tbody>
                  {groupBlocks.map((block) => {
                    const isTableOpen = tableExpanded.has(block.id);
                    return (
                      <React.Fragment key={block.id}>
                        <tr
                          className={`group-summary-row status-${block.summary.status}`}
                          style={{ cursor: 'pointer' }}
                          onClick={() => toggleTableGroup(block.id)}
                        >
                          <td colSpan={bulkEditMode ? 9 : 8}>
                            <span className="gantt-group-chevron" style={{ display: 'inline-block' }}>
                              {isTableOpen ? '\u25BE' : '\u25B8'}
                            </span>
                            <strong>{block.group?.name || 'Ungrouped'}</strong>
                            <span className="group-summary-counts ms-2">
                              {block.summary.overdue > 0 && (
                                <span className="gantt-bar-count gantt-bar-count-overdue">
                                  <strong>{block.summary.overdue}</strong> overdue
                                </span>
                              )}
                              {block.summary.pending > 0 && (
                                <span className="gantt-bar-count gantt-bar-count-pending">
                                  <strong>{block.summary.pending}</strong> in progress
                                </span>
                              )}
                              {block.summary.completed > 0 && (
                                <span className="gantt-bar-count gantt-bar-count-completed">
                                  <strong>{block.summary.completed}</strong> completed
                                </span>
                              )}
                            </span>
                          </td>
                        </tr>
                        {isTableOpen && block.tasks.map((task) => {
                          const rowClass = task.finished
                            ? 'row-completed'
                            : isBeforeToday(task.scheduled_date)
                              ? 'row-overdue'
                              : 'row-pending';
                          const slaShort = task.sla_type === 'Working Day' ? 'WD' : 'CD';
                          const isEditing = editingRow === task.id;
                          return (
                            <tr
                              key={task.id}
                              data-scheduled-date={task.scheduled_date}
                              className={rowClass}
                            >
                              {bulkEditMode && (
                                <td>
                                  <input
                                    type="checkbox"
                                    className="form-check-input"
                                    checked={selectedTasks.has(task.id)}
                                    onChange={() => handleBulkToggle(task.id)}
                                  />
                                </td>
                              )}
                              <td>
                                <input
                                  type="checkbox"
                                  className="form-check-input toggle-finished"
                                  checked={task.finished}
                                  onChange={() => handleToggle(task.id)}
                                />
                              </td>
                              <td>
                                {bulkEditMode ? (
                                  <span className="view-mode">{task.task_name}</span>
                                ) : isEditing ? (
                                  <input
                                    type="text"
                                    className="form-control form-control-sm edit-mode"
                                    value={editData.task_name ?? ''}
                                    onChange={(e) => setEditData({ ...editData, task_name: e.target.value })}
                                  />
                                ) : (
                                  <span className="view-mode">{task.task_name}</span>
                                )}
                              </td>
                              <td>
                                {bulkEditMode ? (
                                  <span className="view-mode">{task.assigned_to}</span>
                                ) : isEditing ? (
                                  <input
                                    type="text"
                                    className="form-control form-control-sm edit-mode"
                                    value={editData.assigned_to ?? ''}
                                    onChange={(e) => setEditData({ ...editData, assigned_to: e.target.value })}
                                  />
                                ) : (
                                  <span className="view-mode">{task.assigned_to}</span>
                                )}
                              </td>
                              <td>
                                {bulkEditMode ? (
                                  <span className="view-mode">{slaShort} {task.sla_days}</span>
                                ) : isEditing ? (
                                  <span className="edit-mode" style={{ display: 'inline-flex', gap: '4px', alignItems: 'center' }}>
                                    <select
                                      className="form-select form-select-sm"
                                      style={{ width: 'auto', display: 'inline-block' }}
                                      value={editData.sla_type ?? task.sla_type}
                                      onChange={(e) => setEditData({ ...editData, sla_type: e.target.value })}
                                    >
                                      <option value="Working Day">Working Day</option>
                                      <option value="Calendar Day">Calendar Day</option>
                                    </select>
                                    <input
                                      type="number"
                                      className="form-control form-control-sm"
                                      style={{ width: '60px', display: 'inline-block' }}
                                      value={editData.sla_days ?? task.sla_days}
                                      onChange={(e) => setEditData({ ...editData, sla_days: e.target.value })}
                                      min={0}
                                    />
                                  </span>
                                ) : (
                                  <span className="view-mode">{slaShort} {task.sla_days}</span>
                                )}
                              </td>
                              <td className="view-mode">{task.scheduled_date}</td>
                              <td className="comment-cell">
                                {bulkEditMode ? (
                                  <span className="view-mode">{task.comments || ''}</span>
                                ) : isEditing ? (
                                  <input
                                    type="text"
                                    className="form-control form-control-sm edit-mode"
                                    value={editData.comments ?? ''}
                                    onChange={(e) => setEditData({ ...editData, comments: e.target.value })}
                                  />
                                ) : (
                                  <span className="view-mode">{task.comments || ''}</span>
                                )}
                              </td>
                              <td>
                                {bulkEditMode ? (
                                  <span className="view-mode">{block.group?.name || '—'}</span>
                                ) : isEditing ? (
                                  <select
                                    className="form-select form-select-sm edit-mode"
                                    value={editData.group ?? ''}
                                    onChange={(e) => setEditData({ ...editData, group: e.target.value })}
                                  >
                                    <option value="">— Ungrouped —</option>
                                    {groups.map((g) => (
                                      <option key={g.id} value={g.id}>{g.name}</option>
                                    ))}
                                  </select>
                                ) : (
                                  <span className="view-mode">{block.group?.name || '—'}</span>
                                )}
                              </td>
                              <td className="actions-cell" style={{ whiteSpace: 'nowrap' }}>
                                {bulkEditMode ? null : isEditing ? (
                                  <span className="edit-buttons edit-mode">
                                    <button className="btn btn-sm btn-primary save-btn" onClick={() => saveEditRow(task.id)}>Save</button>
                                    <button className="btn btn-sm btn-outline-secondary ms-1" onClick={cancelEditRow}>Cancel</button>
                                    <button
                                      className="btn btn-sm btn-outline-danger ms-1 delete-btn"
                                      onClick={() => setConfirmDelete(task.id)}
                                    >
                                      Del
                                    </button>
                                  </span>
                                ) : (
                                  <button
                                    className="btn btn-sm btn-outline-secondary edit-btn view-mode"
                                    onClick={() => startEditRow(task)}
                                  >
                                    Edit
                                  </button>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </React.Fragment>
                    );
                  })}
                  {allTasks.length === 0 && (
                    <tr>
                      <td colSpan={bulkEditMode ? 9 : 8} className="text-center text-muted py-4">
                        No tasks for this month. Click "Generate Next Month" or add a task below.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div ref={quickAddRef} className="glass-card mt-4">
            <div className="card-header">Quick Add Task</div>
            <div className="card-body">
              <form onSubmit={handleQuickAdd} className="row g-2">
                <div className="col-md-3">
                  <input
                    type="text"
                    name="task_name"
                    className="form-control form-control-sm"
                    placeholder="Task name"
                    value={quickAdd.task_name}
                    onChange={(e) => setQuickAdd({ ...quickAdd, task_name: e.target.value })}
                    required
                  />
                </div>
                <div className="col-md-2">
                  <input
                    type="text"
                    name="assigned_to"
                    className="form-control form-control-sm"
                    placeholder="Assigned to"
                    value={quickAdd.assigned_to}
                    onChange={(e) => setQuickAdd({ ...quickAdd, assigned_to: e.target.value })}
                    required
                  />
                </div>
                <div className="col-md-1">
                  <input
                    type="number"
                    name="sla_days"
                    className="form-control form-control-sm"
                    placeholder="SLA"
                    min={0}
                    value={quickAdd.sla_days}
                    onChange={(e) => setQuickAdd({ ...quickAdd, sla_days: Number(e.target.value) })}
                    required
                  />
                </div>
                <div className="col-md-2">
                  <select
                    name="sla_type"
                    className="form-select form-select-sm"
                    value={quickAdd.sla_type}
                    onChange={(e) => setQuickAdd({ ...quickAdd, sla_type: e.target.value })}
                  >
                    <option value="Working Day">Working Day</option>
                    <option value="Calendar Day">Calendar Day</option>
                  </select>
                </div>
                <div className="col-md-2">
                  <input
                    type="text"
                    name="comments"
                    className="form-control form-control-sm"
                    placeholder="Comments"
                    value={quickAdd.comments}
                    onChange={(e) => setQuickAdd({ ...quickAdd, comments: e.target.value })}
                  />
                </div>
                <div className="col-md-1">
                  <select
                    name="group"
                    className="form-select form-select-sm"
                    value={quickAdd.group}
                    onChange={(e) => setQuickAdd({ ...quickAdd, group: e.target.value })}
                  >
                    <option value="">No group</option>
                    {groups.map((g) => (
                      <option key={g.id} value={g.id}>{g.name}</option>
                    ))}
                  </select>
                </div>
                <div className="col-md-1">
                  <button type="submit" className="btn btn-sm btn-primary w-100">Add Task</button>
                </div>
              </form>
            </div>
          </div>
        </>
      )}

      <ConfirmDialog
        show={confirmDelete != null}
        title="Delete Task"
        message="Are you sure you want to delete this task?"
        onConfirm={() => { if (confirmDelete != null) handleDelete(confirmDelete); }}
        onCancel={() => setConfirmDelete(null)}
      />

      <ConfirmDialog
        show={confirmGenerate}
        title="Generate Next Month"
        message="Generate tasks for the next month?"
        onConfirm={handleGenerateNextMonth}
        onCancel={() => setConfirmGenerate(false)}
      />
    </div>
  );
};

export default TasksPage;
