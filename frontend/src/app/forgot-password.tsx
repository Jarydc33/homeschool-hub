import { router } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { AuthShell } from '@/components/auth-shell';
import { Button, Card, ErrorMessage, TextField } from '@/components/ui';
import { Colors, Spacing } from '@/constants/theme';
import { supabase } from '@/lib/supabase';

/**
 * Emails a link to choose a new password. Unknown emails get the same answer
 * as known ones, so this can't be used to find out who has an account.
 */
export default function ForgotPasswordScreen() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  async function submit() {
    const cleanEmail = email.trim().toLowerCase();

    if (!cleanEmail) {
      setError('Please enter your email address.');
      return;
    }

    setBusy(true);
    setError(null);

    try {
      // The email's link comes from Supabase's Reset Password template.
      const { error: failed } = await supabase.auth.resetPasswordForEmail(cleanEmail);

      if (failed && failed.status === 429) {
        setError('Too many reset emails were asked for. Please wait a few minutes and try again.');
        setBusy(false);
        return;
      }

      if (failed) {
        // Most failures would give away whether the email has an account.
        console.warn('Sending a password reset failed:', failed.status, failed.code);
      }

      setSent(true);
    } catch {
      setError("We couldn't send that right now. Check your connection and try again.");
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <AuthShell title="Check your email">
        <Card>
          <Text style={styles.body}>
            If that email has a tally account, a link to choose a new password is on its way.
          </Text>
          <Text style={styles.muted}>
            It can take a few minutes to arrive. If you don&apos;t see it, check your spam folder.
          </Text>
        </Card>
        <Button title="Back to Log In" onPress={() => router.replace('/login')} />
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Forgot your password?"
      intro="Enter your email and we'll send you a link to choose a new one.">
      <View style={styles.form}>
        <TextField
          label="Email"
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          inputMode="email"
          autoCapitalize="none"
          autoCorrect={false}
          autoComplete="email"
          textContentType="emailAddress"
          maxLength={254}
          autoFocus
          returnKeyType="send"
          onSubmitEditing={submit}
        />

        {error ? <ErrorMessage message={error} /> : null}

        <Button title="Send Reset Link" busy={busy} onPress={submit} />
        <Button
          title="Back to Log In"
          variant="secondary"
          onPress={() => router.replace('/login')}
        />
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
