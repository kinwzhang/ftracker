import type { Task, GroupSummary } from '../types';
import { isBeforeToday } from './dates';

function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

function parseScheduledDay(task: Task): number {
  if (!task.scheduled_date) return 0;
  const day = parseInt(task.scheduled_date.substring(8, 10), 10);
  return isNaN(day) ? 0 : day;
}

export function calculateGanttBar(task: Task, month: string): { start_offset: number; duration: number } {
  const [yearStr, monthStr] = month.split('-');
  const year = parseInt(yearStr, 10);
  const monthNum = parseInt(monthStr, 10);
  const totalDays = getDaysInMonth(year, monthNum);

  const scheduledDay = parseScheduledDay(task);
  if (scheduledDay === 0) {
    return { start_offset: 0, duration: 0 };
  }

  const start_offset = scheduledDay - 1;

  let duration: number;
  if (task.finished && task.completion_date) {
    const completionDay = parseInt(task.completion_date.substring(8, 10), 10);
    duration = completionDay - scheduledDay + 1;
  } else {
    duration = Math.min(task.sla_days, totalDays - scheduledDay + 1);
  }

  if (duration < 1) duration = 1;

  return { start_offset, duration };
}

export function calculateGroupBar(
  tasks: Task[],
  month: string
): { start_offset: number; width: number; status: string } | null {
  if (tasks.length === 0) return null;

  let minOffset = Infinity;
  let maxEnd = 0;

  for (const task of tasks) {
    const bar = calculateGanttBar(task, month);
    if (bar.duration > 0) {
      minOffset = Math.min(minOffset, bar.start_offset);
      maxEnd = Math.max(maxEnd, bar.start_offset + bar.duration);
    }
  }

  if (minOffset === Infinity) return null;

  const summary = getGroupSummary(tasks);

  return {
    start_offset: minOffset,
    width: maxEnd - minOffset,
    status: summary.status,
  };
}

export function getGroupSummary(tasks: Task[]): GroupSummary {
  let total = 0;
  let completed = 0;
  let pending = 0;
  let overdue = 0;

  for (const task of tasks) {
    total++;
    if (task.finished) {
      completed++;
    } else if (isBeforeToday(task.scheduled_date)) {
      overdue++;
    } else {
      pending++;
    }
  }

  let status: GroupSummary['status'] = 'pending';
  if (overdue > 0) status = 'overdue';
  else if (completed === total && total > 0) status = 'completed';

  return { total, completed, pending, overdue, status };
}

export function calculateTodayPercentage(month: string, totalDays: number): number | null {
  const today = new Date();
  const [yearStr, monthStr] = month.split('-');
  const year = parseInt(yearStr, 10);
  const monthNum = parseInt(monthStr, 10);

  if (today.getFullYear() !== year || today.getMonth() + 1 !== monthNum) {
    return null;
  }

  const dayOfMonth = today.getDate();
  return (dayOfMonth / totalDays) * 100;
}
