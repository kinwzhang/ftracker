import client from './client';

export function fetchTemplates() {
  return client.get('/api/v1/templates/');
}

export function addTemplate(data: Record<string, unknown>) {
  return client.post('/api/v1/templates/', data);
}

export function updateTemplate(id: number, data: Record<string, unknown>) {
  return client.patch(`/api/v1/templates/${id}/`, data);
}

export function deleteTemplate(id: number) {
  return client.delete(`/api/v1/templates/${id}/`);
}

export function templateInlineSave(id: number, data: Record<string, unknown>) {
  return client.post(`/api/v1/templates/${id}/inline-save/`, data);
}

export function templateBulkSave(updates: Record<string, unknown>[]) {
  return client.post('/api/v1/templates/bulk-save/', { updates });
}

export function templateBulkUpload(formData: FormData) {
  return client.post('/api/v1/templates/bulk-upload/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
}

export function fetchGroups() {
  return client.get('/api/v1/groups/');
}

export function addGroup(data: Record<string, unknown>) {
  return client.post('/api/v1/groups/', data);
}

export function updateGroup(id: number, data: Record<string, unknown>) {
  return client.patch(`/api/v1/groups/${id}/`, data);
}

export function deleteGroup(id: number) {
  return client.delete(`/api/v1/groups/${id}/`);
}

export function groupInlineSave(id: number, data: Record<string, unknown>) {
  return client.post(`/api/v1/groups/${id}/inline-save/`, data);
}
