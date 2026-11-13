import type { Session } from '@supabase/supabase-js';
import { router, useLocalSearchParams } from 'expo-router';
import { useRef, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { AuthShell } from '@/components/auth-shell';
import { Button, Card, ErrorMessage, TextField } from '@/components/ui';
import { Colors, Spacing } from '@/constants/theme';
import { useAuth } from '@/lib/auth';
import { createLinkClient } from '@/lib/supabase';

const MIN_PASSWORD_LENGTH = 8;

type LinkType = 'invite' | 'recovery';

const TEXT: Record<
  LinkType,
  { title: string; intro: string; button: string; done: string; expired: string }
> = {
  invite: {
    title: 'Finish setting up your account',
    intro: 'Choose a password for your new tally account.',
    button: 'Save My Password',
    done: 'Your password is saved. You can now log in with it.',
    expired:
      'This invitation link has expired or has already been used. Please ask a parent to send a new one.',
  },
  recovery: {
    title: 'Choose a new password',
    intro: 'Enter a new password for your tally account.',
    button: 'Save New Password',
    done: 'Your password is changed, and any devices that were logged in have been logged out. You can now log in with your new password.',
    expired:
      'This password reset link has expired or has already been used. Please ask for a new one.',
  },
};

/**
 * Where the invite and password reset emails' links lead:
 * ?token_hash=…&type=invite or type=recovery.
 *
 * The link's token is used only when the password is submitted, never when
 * the page opens, because it works once and email scanners open links before
 * people do. It runs on its own Supabase client, so a login already saved on
 * this device (a parent opening their student's invite) is never touched.
 */
export default function CompleteAccountScreen() {
  const params = useLocalSearchParams<{ token_hash?: string; type?: string }>();
  const { signedIn, signOut } = useAuth();

  const tokenHash = typeof params.token_hash === 'string' ? params.token_hash : null;
  const linkType: LinkType | null =
    params.type === 'invite' || params.type === 'recovery' ? params.type : null;

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  // The link's own client, and its session once the token is used, so a
  // rejected password can be tried again without the (used-up) token.
  const client = useRef<ReturnType<typeof createLinkClient> | null>(null);
  const session = useRef<Session | null>(null);

  if (!tokenHash || !linkType) {
    return (
      <AuthShell title="This link isn't valid">
        <Text style={styles.body}>Please use the link in your email, or ask for a new one.</Text>
        <Button title="Go to Log In" onPress={() => router.replace('/login')} />
      </AuthShell>
    );
  }

  const text = TEXT[linkType];

  async function submit() {
    if (password.length < MIN_PASSWORD_LENGTH) {
      setError(`Your password needs at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }

    if (password !== confirmPassword) {
      setError("The two passwords don't match.");
      return;
    }

    setBusy(true);
    setError(null);

    try {
      client.current ??= createLinkClient();
      const auth = client.current.auth;

      if (!session.current) {
        const { data, error: failed } = await auth.verifyOtp({
          token_hash: tokenHash!,
          type: linkType!,
        });

        if (failed || !data.session) {
          console.warn('Verifying an email link failed:', failed?.code);
          setError(text.expired);
          setBusy(false);
          return;
        }

        session.current = data.session;
      }

      const { error: rejected } = await auth.updateUser({ password });

      if (rejected) {
        console.warn('Setting a password from an email link failed:', rejected.code);
        setError(
          rejected.code === 'weak_password'
            ? 'That password is too easy to guess. Please choose a stronger one.'
            : rejected.code === 'same_password'
              ? 'Please choose a password you haven’t used before.'
              : "We couldn't save that password. Please try again or choose a different one.",
        );
        setBusy(false);
        return;
      }

      // They log in themselves next. A reset ends every login, in case the
      // old password was stolen; an invite only ends the link's own.
      await auth.signOut({ scope: linkType === 'recovery' ? 'global' : 'local' });
      session.current = null;
      setDone(true);
    } catch {
      setError("We couldn't finish this right now. Please try again in a moment.");
      setBusy(false);
    }
  }

  async function goToLogin() {
    // Someone else may be logged in on this device, e.g. the parent who
    // opened their student's invite.
    if (signedIn) {
      await signOut();
    }

    router.replace('/login');
  }

  if (done) {
    return (
      <AuthShell title={text.title}>
        <Card>
          <Text style={styles.body}>✓ {text.done}</Text>
          {signedIn ? (
            <Text style={styles.muted}>
              Someone else is logged in on this device. Going to the login logs them out.
            </Text>
          ) : null}
        </Card>
        <Button title="Go to Log In" onPress={goToLogin} />
      </AuthShell>
    );
  }

  return (
    <AuthShell title={text.title} intro={text.intro}>
      <View style={styles.form}>
        <TextField
          label="Password"
          hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          autoComplete="new-password"
          textContentType="newPassword"
          maxLength={200}
          autoFocus
        />
        <TextField
          label="Type It Again"
          value={confirmPassword}
          onChangeText={setConfirmPassword}
          secureTextEntry
          autoComplete="new-password"
          textContentType="newPassword"
          maxLength={200}
          returnKeyType="done"
          onSubmitEditing={submit}
        />

        {error ? <ErrorMessage message={error} /> : null}

        <Button title={text.button} busy={busy} onPress={submit} />
      </View>
    </AuthShell>
  );
}

const styles = StyleSheet.create({
  form: {
    gap: Spacing.md,
  },
  body: {
    color: Colors.text,
    fontSize: 16,
  },
  muted: {
    color: Colors.textMuted,
    fontSize: 14,
  },
});
