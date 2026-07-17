import { useState, useCallback } from 'react';
import * as tasksApi from '../api/tasks';
import type { Task, GroupBlock, MonthStats } from '../types';

interface UseTasksResult {
  tasks: Task[];
  groupBlocks: GroupBlock[];
  stats: MonthStats | null;
  loading: boolean;
  error: string | null;
  fetchTasks: (month: string) => Promise<void>;
  addTask: (data: Record<string, unknown>) => Promise<void>;
  updateTask: (id: number, data: Record<string, unknown>) => Promise<void>;
  deleteTask: (id: number) => Promise<void>;
  toggleTask: (id: number) => Promise<void>;
  saveComment: (id: number, comments: string) => Promise<void>;
  inlineSave: (id: number, data: Record<string, unknown>) => Promise<void>;
  bulkSave: (updates: Record<string, unknown>[]) => Promise<void>;
  generateNextMonth: () => Promise<void>;
}

export function useTasks(): UseTasksResult {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [groupBlocks, setGroupBlocks] = useState<GroupBlock[]>([]);
  const [stats, setStats] = useState<MonthStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTasks = useCallback(async (month: string) => {
    setLoading(true);
    setError(null);
    try {
      const data: any = await tasksApi.fetchTaskData(month);
      setTasks(data.tasks || []);
      setGroupBlocks(data.group_blocks || []);
      setStats(data.stats || null);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to fetch tasks');
    } finally {
      setLoading(false);
    }
  }, []);

  const addTask = useCallback(async (data: Record<string, unknown>) => {
    await tasksApi.addTask(data);
  }, []);

  const updateTask = useCallback(async (id: number, data: Record<string, unknown>) => {
    await tasksApi.updateTask(id, data);
  }, []);

  const deleteTask = useCallback(async (id: number) => {
    await tasksApi.deleteTask(id);
  }, []);

  const toggleTask = useCallback(async (id: number) => {
    await tasksApi.toggleTask(id);
  }, []);

  const saveComment = useCallback(async (id: number, comments: string) => {
    await tasksApi.saveComment(id, comments);
  }, []);

  const inlineSave = useCallback(async (id: number, data: Record<string, unknown>) => {
    await tasksApi.inlineSave(id, data);
  }, []);

  const bulkSave = useCallback(async (updates: Record<string, unknown>[]) => {
    await tasksApi.bulkSave(updates);
  }, []);

  const generateNextMonth = useCallback(async () => {
    await tasksApi.generateNextMonth();
  }, []);

  return {
    tasks,
    groupBlocks,
    stats,
    loading,
    error,
    fetchTasks,
    addTask,
    updateTask,
    deleteTask,
    toggleTask,
    saveComment,
    inlineSave,
    bulkSave,
    generateNextMonth,
  };
}
