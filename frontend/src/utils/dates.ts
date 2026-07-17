export function formatDate(dateStr: string): string {
  if (!dateStr) return '';
  return dateStr.substring(0, 10);
}

export function formatDateTime(dateStr: string, timeStr: string | null): string {
  if (!dateStr) return '';
  const date = dateStr.substring(0, 10);
  if (timeStr) {
    return `${date} ${timeStr.substring(0, 5)}`;
  }
  return date;
}

export function isBeforeToday(dateStr: string): boolean {
  if (!dateStr) return false;
  const d = new Date(dateStr.substring(0, 10));
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return d < today;
}

export function getTodayISO(): string {
  return new Date().toISOString().substring(0, 10);
}
