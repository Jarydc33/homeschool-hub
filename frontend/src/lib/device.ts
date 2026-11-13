/**
 * A paired device's key: a student's own device, signed in with a pairing
 * code instead of an email and password. It's kept where the login is kept
 * (storage.ts) and sent to the API as X-Device-Token whenever there's no
 * email login. The name matches the Streamlit app's.
 */
import { authStorage } from './storage';

const KEY = 'homeschoolhub_device';

export function getDeviceToken(): string | null {
  try {
    return authStorage?.getItem(KEY) ?? null;
  } catch {
    return null;
  }
}

export function setDeviceToken(token: string): void {
  try {
    authStorage?.setItem(KEY, token);
  } catch {
    // Storage blocked, e.g. a private window: the pairing lasts until closed.
  }
}

export function clearDeviceToken(): void {
  try {
    authStorage?.removeItem(KEY);
  } catch {
    // Nothing kept, so nothing to forget.
  }
}
