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

/** The seven dates of day's week, Sunday first, as the Streamlit app shows. */
export function weekDays(day: string): string[] {
  const sunday = addDays(day, -parseDate(day).getDay());

  return Array.from({ length: 7 }, (_, i) => addDays(sunday, i));
}

/**
 * The weeks that show day's month, each seven dates. The first and last can
 * include days from the months around it.
 */
export function monthWeeks(day: string): string[][] {
  const date = parseDate(day);
  const last = toDateString(new Date(date.getFullYear(), date.getMonth() + 1, 0));
  const weeks: string[][] = [];
  let current = toDateString(new Date(date.getFullYear(), date.getMonth(), 1));

  while (current <= last) {
    weeks.push(weekDays(current));
    current = addDays(weeks[weeks.length - 1][6], 1);
  }

  return weeks;
}

/**
 * The date step weeks (or months) from day. Moving by month lands on the
 * 1st, since not every month has a 31st.
 */
export function shiftDate(day: string, months: boolean, step: number): string {
  if (!months) {
    return addDays(day, 7 * step);
  }

  const date = parseDate(day);

  return toDateString(new Date(date.getFullYear(), date.getMonth() + step, 1));
}
