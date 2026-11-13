/**
 * Calls the Tally API as the signed-in person, or the paired device. Errors come back as ApiError,
 * whose message is the API's friendly text, ready to show.
 */
import { API_URL } from './config';
import { getDeviceToken } from './device';
import { supabase } from './supabase';

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

/** Text for an error caught from api(), ready to show. */
export function errorMessage(ex: unknown): string {
  return ex instanceof ApiError ? ex.message : 'Something went wrong. Please try again.';
}

// Told when the API refuses a paired device's key, e.g. a parent ended it.
let deviceRefused: (() => void) | null = null;

export function onDeviceRefused(handler: (() => void) | null): void {
  deviceRefused = handler;
}

const CONNECTION_MESSAGE = "We couldn't reach Tally. Check your connection and try again.";

function messageFrom(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;

  if (typeof detail === 'string') {
    return detail;
  }

  // A form check failed before reaching Tally's own checks.
  if (status === 422) {
    return 'Please check what you entered and try again.';
  }

  return 'Something went wrong. Please try again.';
}

export async function api<T>(
  path: string,
  options: { method?: string; body?: unknown } = {},
): Promise<T> {
  const { data } = await supabase.auth.getSession();

  const headers: Record<string, string> = { Accept: 'application/json' };

  // An email login wins; a paired device has only its key.
  if (data.session) {
    headers.Authorization = `Bearer ${data.session.access_token}`;
  } else {
    const deviceToken = getDeviceToken();

    if (deviceToken) {
      headers['X-Device-Token'] = deviceToken;
    }
  }

  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }

  let response: Response;

  try {
    response = await fetch(`${API_URL}${path}`, {
      method: options.method ?? 'GET',
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch {
    throw new ApiError(CONNECTION_MESSAGE, 0);
  }

  const body = await response.json().catch(() => null);

  if (response.status === 401 && headers['X-Device-Token']) {
    deviceRefused?.();
  }

  if (!response.ok) {
    throw new ApiError(messageFrom(body, response.status), response.status);
  }

  return body as T;
}
