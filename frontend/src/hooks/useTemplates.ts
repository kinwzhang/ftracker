import { useState, useCallback } from 'react';
import * as templatesApi from '../api/templates';
import type { TaskTemplate, Group } from '../types';

interface UseTemplatesResult {
  templates: TaskTemplate[];
  groups: Group[];
  loading: boolean;
  error: string | null;
  fetchTemplates: () => Promise<void>;
  fetchGroups: () => Promise<void>;
  addTemplate: (data: Record<string, unknown>) => Promise<void>;
  updateTemplate: (id: number, data: Record<string, unknown>) => Promise<void>;
  deleteTemplate: (id: number) => Promise<void>;
  templateInlineSave: (id: number, data: Record<string, unknown>) => Promise<void>;
  templateBulkSave: (updates: Record<string, unknown>[]) => Promise<void>;
  templateBulkUpload: (formData: FormData) => Promise<void>;
  addGroup: (data: Record<string, unknown>) => Promise<void>;
  updateGroup: (id: number, data: Record<string, unknown>) => Promise<void>;
  deleteGroup: (id: number) => Promise<void>;
  groupInlineSave: (id: number, data: Record<string, unknown>) => Promise<void>;
}

export function useTemplates(): UseTemplatesResult {
  const [templates, setTemplates] = useState<TaskTemplate[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data: any = await templatesApi.fetchTemplates();
      setTemplates(data.templates || data || []);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to fetch templates');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchGroups = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data: any = await templatesApi.fetchGroups();
      setGroups(data.groups || data || []);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to fetch groups');
    } finally {
      setLoading(false);
    }
  }, []);

  const addTemplate = useCallback(async (data: Record<string, unknown>) => {
    await templatesApi.addTemplate(data);
  }, []);

  const updateTemplate = useCallback(async (id: number, data: Record<string, unknown>) => {
    await templatesApi.updateTemplate(id, data);
  }, []);

  const deleteTemplate = useCallback(async (id: number) => {
    await templatesApi.deleteTemplate(id);
  }, []);

  const templateInlineSave = useCallback(async (id: number, data: Record<string, unknown>) => {
    await templatesApi.templateInlineSave(id, data);
  }, []);

  const templateBulkSave = useCallback(async (updates: Record<string, unknown>[]) => {
    await templatesApi.templateBulkSave(updates);
  }, []);

  const templateBulkUpload = useCallback(async (formData: FormData) => {
    await templatesApi.templateBulkUpload(formData);
  }, []);

  const addGroup = useCallback(async (data: Record<string, unknown>) => {
    await templatesApi.addGroup(data);
  }, []);

  const updateGroup = useCallback(async (id: number, data: Record<string, unknown>) => {
    await templatesApi.updateGroup(id, data);
  }, []);

  const deleteGroup = useCallback(async (id: number) => {
    await templatesApi.deleteGroup(id);
  }, []);

  const groupInlineSave = useCallback(async (id: number, data: Record<string, unknown>) => {
    await templatesApi.groupInlineSave(id, data);
  }, []);

  return {
    templates,
    groups,
    loading,
    error,
    fetchTemplates,
    fetchGroups,
    addTemplate,
    updateTemplate,
    deleteTemplate,
    templateInlineSave,
    templateBulkSave,
    templateBulkUpload,
    addGroup,
    updateGroup,
    deleteGroup,
    groupInlineSave,
  };
}
