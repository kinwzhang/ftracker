import React, { useState } from 'react';
import type { GroupBlock, DayInfo } from '../../types';

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

interface GanttChartProps {
  groupBlocks: GroupBlock[];
  daysInMonth: DayInfo[];
  todayPct: number | null;
}

function getTaskStatus(task: { finished: boolean; scheduled_date: string }): 'completed' | 'overdue' | 'pending' {
  if (task.finished) return 'completed';
  if (new Date(task.scheduled_date) < new Date()) return 'overdue';
  return 'pending';
}

function getWeekdayIndex(weekday: string): number {
  const idx = WEEKDAYS.indexOf(weekday);
  return idx >= 0 ? idx : -1;
}

const GanttChart: React.FC<GanttChartProps> = ({ groupBlocks, daysInMonth, todayPct }) => {
  const totalDays = daysInMonth.length;
  const [openGroups, setOpenGroups] = useState<Set<number>>(() => {
    return new Set(groupBlocks.map((b) => b.id));
  });

  const toggleGroup = (id: number) => {
    setOpenGroups((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const expandAll = () => setOpenGroups(new Set(groupBlocks.map((b) => b.id)));
  const collapseAll = () => setOpenGroups(new Set());

  return (
    <div className="glass-card card mb-4">
      <div className="card-header d-flex align-items-center justify-content-between">
        <span>Gantt Chart</span>
        <div className="d-flex gap-1">
          <button className="btn btn-sm btn-outline-primary" onClick={expandAll}>
            Expand All
          </button>
          <button className="btn btn-sm btn-outline-secondary" onClick={collapseAll}>
            Collapse All
          </button>
        </div>
      </div>
      <div className="card-body p-0">
        <div className="gantt-chart">
          <div className="gantt-canvas">
            <div className="day-header">
              <div className="day-header-spacer" />
              {daysInMonth.map((day) => {
                const dow = getWeekdayIndex(day.weekday);
                const isWeekend = dow === 0 || dow === 6;
                let cls = 'day-cell';
                if (isWeekend) cls += ' weekend';
                if (day.is_holiday) cls += ' holiday';
                if (todayPct !== null && daysInMonth.indexOf(day) === Math.round((todayPct / 100) * totalDays) - 1) {
                  cls += ' today';
                }
                return (
                  <div key={day.date} className={cls}>
                    <div>{parseInt(day.date.substring(8, 10), 10)}</div>
                    <div className="day-cell-wday">{day.weekday}</div>
                  </div>
                );
              })}
            </div>

            {groupBlocks.map((block) => {
              const isOpen = openGroups.has(block.id);
              return (
                <details
                  key={block.id}
                  className="gantt-group-block"
                  open={isOpen}
                  onToggle={(e) => {
                    if (e.target instanceof HTMLDetailsElement) return;
                    toggleGroup(block.id);
                  }}
                >
                  <summary
                    className="gantt-row gantt-group-summary"
                    onClick={(e) => {
                      e.preventDefault();
                      toggleGroup(block.id);
                    }}
                  >
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
                    const status = getTaskStatus(gt.task);
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
                          {todayPct !== null && (
                            <div
                              className="today-line"
                              style={{ left: `${todayPct}%` }}
                            />
                          )}
                        </div>
                      </div>
                    );
                  })}
                </details>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

export default GanttChart;
