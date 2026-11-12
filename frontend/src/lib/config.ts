/**
 * Settings, from EXPO_PUBLIC_ environment variables (frontend/.env locally).
 * They're built into the app, so only public values belong here: the
 * Supabase anon key is meant to be public (Supabase's row-level security
 * blocks its direct table access). Never put the service key here.
 */

function required(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(`${name} is not set. Add it to frontend/.env (see .env.example).`);
  }
  return value;
}

export const API_URL = (
  process.env.EXPO_PUBLIC_API_URL ?? 'https://api.tallyhomeschool.com'
).replace(/\/$/, '');

export const SUPABASE_URL = required(
  'EXPO_PUBLIC_SUPABASE_URL',
  process.env.EXPO_PUBLIC_SUPABASE_URL,
);

export const SUPABASE_KEY = required(
  'EXPO_PUBLIC_SUPABASE_KEY',
  process.env.EXPO_PUBLIC_SUPABASE_KEY,
);
