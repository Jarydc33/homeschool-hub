/**
 * Supabase, for logging in only. All of Tally's data goes through the API,
 * never Supabase's tables directly.
 *
 * Unlike the Streamlit app, the login lives here on the device, so the
 * client refreshes its own tokens (autoRefreshToken). Each refresh token
 * works once, and only this one client uses it.
 */
import 'react-native-url-polyfill/auto';

import { createClient } from '@supabase/supabase-js';
import { AppState, Platform } from 'react-native';

import { SUPABASE_KEY, SUPABASE_URL } from './config';
import { authStorage } from './storage';

export const supabase = createClient(SUPABASE_URL, SUPABASE_KEY, {
  auth: {
    storage: authStorage,
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
  },
});

// On phones, refresh only while the app is open. The web refreshes on its own.
if (Platform.OS !== 'web') {
  AppState.addEventListener('change', (state) => {
    if (state === 'active') {
      supabase.auth.startAutoRefresh();
    } else {
      supabase.auth.stopAutoRefresh();
    }
  });
}

/**
 * A separate client for finishing an invite or password reset link. It keeps
 * nothing in storage, so using a link never touches a login already saved on
 * this device (a parent may open their student's invite while logged in).
 */
export function createLinkClient() {
  return createClient(SUPABASE_URL, SUPABASE_KEY, {
    auth: {
      storageKey: 'tally-email-link',
      persistSession: false,
      autoRefreshToken: false,
      detectSessionInUrl: false,
    },
  });
}
