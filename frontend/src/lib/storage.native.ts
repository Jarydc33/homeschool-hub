/**
 * Where the login is kept on phones: Expo's localStorage, backed by SQLite,
 * as Supabase's Expo guide sets it up. The web uses storage.ts instead.
 */
import 'expo-sqlite/localStorage/install';

export const authStorage: Storage | undefined = globalThis.localStorage;
