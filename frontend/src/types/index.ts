export interface Task {
  id: number;
  task_name: string;
  assigned_to: string;
  sla_days: number;
  sla_type: 'Working Day' | 'Calendar Day';
  scheduled_date: string;
  finished: boolean;
  completion_date: string | null;
  completion_time: string | null;
  comments: string;
  month: string;
  group_id: number | null;
  group_name: string | null;
}

export interface TaskTemplate {
  id: number;
  task_name: string;
  assigned_to: string;
  sla_days: number;
  sla_type: 'Working Day' | 'Calendar Day';
  sort_order: number;
  group_id: number | null;
  group_name: string | null;
}

export interface Group {
  id: number;
  name: string;
  sort_order: number;
  template_count?: number;
}

export interface AuditLog {
  id: number;
  task_id: number;
  task_name: string;
  action: string;
  changes: string;
  timestamp: string;
  readable_message: string;
}

export interface Holiday {
  date: string;
  name: string;
  weekday: string;
}

export interface DayInfo {
  date: string;
  weekday: string;
  is_holiday: boolean;
}

export interface GanttTask {
  task: Task;
  start_offset: number;
  duration: number;
}

export interface GroupSummary {
  total: number;
  completed: number;
  pending: number;
  overdue: number;
  status: 'completed' | 'pending' | 'overdue';
}

export interface GroupBlock {
  id: number;
  group: Group | null;
  tasks: Task[];
  gantt_tasks: GanttTask[];
  summary: GroupSummary;
  group_bar: {
    start_offset: number;
    width: number;
    status: string;
  } | null;
}

export interface MonthStats {
  total: number;
  completed: number;
  pending: number;
  overdue: number;
}

export interface DashboardData {
  stats: MonthStats;
  completion_rate: number;
  months_data: Array<{
    label: string;
    total: number;
    completed: number;
    rate: number;
  }>;
  audit_logs: AuditLog[];
}

export interface ApiResponse {
  ok: boolean;
  error?: string;
}