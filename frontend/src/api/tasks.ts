import client from './client';

export function fetchTasks(month: string) {
  return client.get('/api/v1/tasks/', { params: { month } });
}

export function fetchTaskData(month: string) {
  return client.get('/api/v1/tasks/data/', { params: { month } });
}

export function addTask(data: Record<string, unknown>) {
  return client.post('/api/v1/tasks/', data);
}

export function updateTask(id: number, data: Record<string, unknown>) {
  return client.patch(`/api/v1/tasks/${id}/`, data);
}

export function deleteTask(id: number) {
  return client.delete(`/api/v1/tasks/${id}/`);
}

export function toggleTask(id: number) {
  return client.post(`/api/v1/tasks/${id}/toggle/`);
}

export function saveComment(id: number, comments: string) {
  return client.post(`/api/v1/tasks/${id}/comment/`, { comments });
}

export function inlineSave(id: number, data: Record<string, unknown>) {
  return client.post(`/api/v1/tasks/${id}/inline-save/`, data);
}

export function bulkSave(updates: Record<string, unknown>[]) {
  return client.post('/api/v1/tasks/bulk-save/', { updates });
}

export function generateNextMonth() {
  return client.post('/api/v1/generate-next-month/');
}

export function setMonth(year: number, month: number) {
  return client.post('/api/v1/set-month/', { year, month });
}

export function exportCsv(month: string) {
  return client.get('/api/v1/export/csv/', { params: { month } });
}

export function exportHtml(month: string) {
  return client.get('/api/v1/export/html/', { params: { month } });
}
