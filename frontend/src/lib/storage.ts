/**
 * Where the login is kept on the web: the browser's own storage. Phones use
 * storage.native.ts instead.
 */
export const authStorage: Storage | undefined =
  typeof window !== 'undefined' ? window.localStorage : undefined;
