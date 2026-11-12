/**
 * Who's signed in, for every screen: the Supabase session, and the API's
 * /me answer (role, family, student) once there is one.
 */
import type { Session } from '@supabase/supabase-js';
import { createContext, useCallback, useContext, useEffect, useState } from 'react';

import { api, ApiError } from './api';
import { supabase } from './supabase';
import type { Me } from './types';

interface AuthState {
  // False until the saved login has been read.
  ready: boolean;
  session: Session | null;
  me: Me | null;
  // A problem loading /me, such as no connection.
  error: string | null;
  // Why someone was sent back to the login, shown there.
  notice: string | null;
  signIn: (email: string, password: string) => Promise<string | null>;
  signOut: () => Promise<void>;
  reloadMe: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

const SIGN_IN_FAILED = 'That email and password don’t match. Please try again.';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [session, setSession] = useState<Session | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setReady(true);
    });

    const { data } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next);
    });

    return () => data.subscription.unsubscribe();
  }, []);

  const reloadMe = useCallback(async () => {
    try {
      const found = await api<Me>('/me');
      setMe(found);
      setError(null);
    } catch (ex) {
      if (ex instanceof ApiError && ex.status === 401) {
        // The login was refused, e.g. an archived student: start over,
        // and say why on the login screen.
        console.warn('Tally refused this login:', ex.message);
        setNotice(ex.message);
        await supabase.auth.signOut();
        setMe(null);
        return;
      }
      setError(ex instanceof Error ? ex.message : 'Something went wrong.');
    }
  }, []);

  // Look up who this is whenever someone new signs in.
  const userId = session?.user.id;

  useEffect(() => {
    if (userId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- loads data when this opens; state changes only after the API answers.
      reloadMe();
    }
  }, [userId, reloadMe]);

  const signIn = useCallback(async (email: string, password: string) => {
    setNotice(null);
    const { error: failed } = await supabase.auth.signInWithPassword({
      email: email.trim().toLowerCase(),
      password,
    });

    return failed ? SIGN_IN_FAILED : null;
  }, []);

  const signOut = useCallback(async () => {
    // Ends Student Mode on this login first, which needs the login.
    await api('/logout', { method: 'POST' }).catch(() => undefined);
    await supabase.auth.signOut();
    setMe(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        ready,
        session,
        // Only meaningful while someone's signed in.
        me: userId ? me : null,
        error: userId ? error : null,
        notice,
        signIn,
        signOut,
        reloadMe,
      }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const state = useContext(AuthContext);

  if (!state) {
    throw new Error('useAuth must be used inside AuthProvider');
  }

  return state;
}
