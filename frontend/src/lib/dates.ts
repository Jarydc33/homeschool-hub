/**
 * Dates from the API are the family's own dates as "YYYY-MM-DD", so they're
 * read as local dates, never UTC (which could shift them by a day).
 */

export function parseDate(value: string): Date {
  const [year, month, day] = value.split('-').map(Number);

  return new Date(year, month - 1, day);
}

export function toDateString(value: Date): string {
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');

  return `${value.getFullYear()}-${month}-${day}`;
}

export function addDays(value: string, days: number): string {
  const date = parseDate(value);

  date.setDate(date.getDate() + days);

  return toDateString(date);
}

// "Thursday, November 12", or "Thu, Nov 12" when short.
export function formatDate(value: string, short = false): string {
  return parseDate(value).toLocaleDateString(undefined, {
    weekday: short ? 'short' : 'long',
    month: short ? 'short' : 'long',
    day: 'numeric',
  });
}
