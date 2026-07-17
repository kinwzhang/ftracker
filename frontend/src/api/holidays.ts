import client from './client';

export function fetchHolidays(year: number, month: number) {
  return client.get('/api/v1/holidays/', { params: { year, month } });
}
