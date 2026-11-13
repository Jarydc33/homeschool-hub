/**
 * Who's signed in, for every screen: the Supabase session or a paired
 * device's key, and the API's /me answer (role, family, student) once there
 * is one.
 */
import type { Session } from '@supabase/supabase-js';
import { createContext, useCallback, useContext, useEffect, useState } from 'react';

import { api, ApiError, onDeviceRefused } from './api';
import { clearDeviceToken, getDeviceToken, setDeviceToken } from './device';
import { supabase } from './supabase';
import type { Me } from './types';

interface AuthState {
  // False until the saved login has been read.
  ready: boolean;
  session: Session | null;
  // An email login or a paired device.
  signedIn: boolean;
  me: Me | null;
  // A problem loading /me, such as no connection.
  error: string | null;
  // Why someone was sent back to the login, shown there.
  notice: string | null;
  signIn: (email: string, password: string) => Promise<string | null>;
  signOut: () => Promise<void>;
  // Pairs this device with a parent's code; an error message, or null.
  pair: (code: string) => Promise<string | null>;
  // Unpairs it with the family PIN; throws ApiError when refused.
  unpair: (pin: string) => Promise<void>;
  reloadMe: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

const SIGN_IN_FAILED = 'That email and password don’t match. Please try again.';

const DEVICE_ENDED =
  'This device isn’t paired anymore. Ask a parent for a new pairing code, or log in.';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [session, setSession] = useState<Session | null>(null);
  const [deviceToken, setDeviceState] = useState<string | null>(getDeviceToken);
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
        // The login was refused, e.g. an archived student or a device a
        // parent ended: start over, and say why on the login screen.
        console.warn('Tally refused this login:', ex.message);
        const { data } = await supabase.auth.getSession();

        if (data.session) {
          setNotice(ex.message);
          await supabase.auth.signOut();
        } else {
          setNotice(DEVICE_ENDED);
          clearDeviceToken();
          setDeviceState(null);
        }

        setMe(null);
        return;
      }
      setError(ex instanceof Error ? ex.message : 'Something went wrong.');
    }
  }, []);

  // A paired device a parent ended: forget it and go to the login, saying
  // why, as soon as any call is refused.
  useEffect(() => {
    onDeviceRefused(() => {
      clearDeviceToken();
      setDeviceState(null);
      setMe(null);
      setNotice(DEVICE_ENDED);
    });

    return () => onDeviceRefused(null);
  }, []);

  // Look up who this is whenever someone new signs in, by email or by
  // pairing. An email login wins, as it does in the API.
  const userId = session?.user.id;
  const who = userId ?? (deviceToken ? `device:${deviceToken}` : null);

  useEffect(() => {
    if (who) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- loads data when this opens; state changes only after the API answers.
      reloadMe();
    }
  }, [who, reloadMe]);

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

  const pair = useCallback(async (code: string) => {
    setNotice(null);

    try {
      const result = await api<{ device_token: string }>('/pairing/redeem', {
        method: 'POST',
        body: { code: code.replace(/\s/g, '') },
      });

      setDeviceToken(result.device_token);
      setDeviceState(result.device_token);
      return null;
    } catch (ex) {
      return ex instanceof ApiError ? ex.message : 'Something went wrong. Please try again.';
    }
  }, []);

  const unpair = useCallback(async (pin: string) => {
    await api('/pairing/unpair', { method: 'POST', body: { pin } });
    clearDeviceToken();
    setDeviceState(null);
    setMe(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        ready,
        session,
        signedIn: who !== null,
        // Only meaningful while someone's signed in.
        me: who ? me : null,
        error: who ? error : null,
        notice,
        signIn,
        signOut,
        pair,
        unpair,
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
