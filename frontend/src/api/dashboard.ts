import client from './client';

export function fetchDashboard(month: string) {
  return client.get('/api/v1/dashboard/', { params: { month } });
}
