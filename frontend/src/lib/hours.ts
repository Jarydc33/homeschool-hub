/**
 * Minutes for hours tracking: reading them from a text box, and showing them.
 */

// The API's MAX_MINUTES: ten hours.
export const MAX_MINUTES = 600;

/**
 * A text box's minutes: a number, null when it's blank, or an error message.
 * allowZero is for adjusting a day's work, where 0 means no time.
 */
export function parseMinutes(
  text: string,
  allowZero = false,
): { minutes: number | null } | { error: string } {
  const trimmed = text.trim();

  if (!trimmed) {
    return { minutes: null };
  }

  const lowest = allowZero ? 0 : 1;
  const minutes = Number(trimmed);

  if (!/^\d+$/.test(trimmed) || minutes < lowest || minutes > MAX_MINUTES) {
    return { error: `Minutes must be a whole number from ${lowest} to ${MAX_MINUTES}.` };
  }

  return { minutes };
}

/** "45 min", "2 hr", "12 hr 30 min", like PEService.describe_minutes. */
export function formatMinutes(total: number): string {
  const hours = Math.floor(total / 60);
  const rest = total % 60;

  if (!hours) {
    return `${rest} min`;
  }

  return rest ? `${hours} hr ${rest} min` : `${hours} hr`;
}

/** Hours to one decimal place, for big totals: "12.5". */
export function formatHours(total: number): string {
  return (Math.round((total / 60) * 10) / 10).toString();
}
