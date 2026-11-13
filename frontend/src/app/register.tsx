import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { AuthShell } from '@/components/auth-shell';
import { deviceTimeZone, TimeZoneField } from '@/components/time-zone-field';
import { Button, Card, ErrorMessage, Loading, TextField } from '@/components/ui';
import { Colors, Spacing } from '@/constants/theme';
import { api, errorMessage } from '@/lib/api';
import { supabase } from '@/lib/supabase';
import type { TimeZoneChoice } from '@/lib/types';

// The API's MIN_PASSWORD_LENGTH.
const MIN_PASSWORD_LENGTH = 8;

interface Registered {
  // True while Supabase waits for the email to be confirmed: no login yet.
  confirm_email: boolean;
  access_token: string | null;
  refresh_token: string | null;
}

/**
 * Signing up: a new family and its first parent. With Supabase's "Confirm
 * email" on, it ends at "check your email"; otherwise it signs straight in.
 */
export default function RegisterScreen() {
  const [zones, setZones] = useState<TimeZoneChoice[] | null>(null);
  const [familyName, setFamilyName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [chosenZone, setZone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sentTo, setSentTo] = useState<string | null>(null);

  useEffect(() => {
    api<TimeZoneChoice[]>('/timezones')
      .then(setZones)
      .catch(() => setZones([]));
  }, []);

  // The device's own zone until one is picked.
  const timezone = chosenZone ?? (zones ? deviceTimeZone(zones) : null);

  async function submit() {
    const cleanEmail = email.trim().toLowerCase();

    if (!familyName.trim()) {
      setError('Please enter your family name.');
      return;
    }

    if (!cleanEmail) {
      setError('Please enter your email address.');
      return;
    }

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
      const result = await api<Registered>('/register', {
        method: 'POST',
        body: {
          family_name: familyName.trim(),
          email: cleanEmail,
          password,
          ...(timezone ? { timezone } : {}),
        },
      });

      if (result.confirm_email || !result.access_token || !result.refresh_token) {
        setSentTo(cleanEmail);
        setBusy(false);
        return;
      }

      // Signed in: the layout opens the Dashboard by itself.
      await supabase.auth.setSession({
        access_token: result.access_token,
        refresh_token: result.refresh_token,
      });
    } catch (ex) {
      setError(errorMessage(ex));
      setBusy(false);
    }
  }

  if (sentTo) {
    return (
      <AuthShell title="Check your email">
        <Card>
          <Text style={styles.body}>
            We sent a link to <Text style={styles.strong}>{sentTo}</Text>. Open it to confirm your
            email, then log in with your new password.
          </Text>
          <Text style={styles.muted}>
            It can take a few minutes to arrive. If you don&apos;t see it, check your spam folder.
          </Text>
        </Card>
        <Button title="Go to Log In" onPress={() => router.replace('/login')} />
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Create your family account"
      intro="One account for your family. You'll add your students next.">
      {!zones ? <Loading /> : null}

      <View style={styles.form}>
        <TextField
          label="Family Name"
          placeholder="For example, The Carters"
          value={familyName}
          onChangeText={setFamilyName}
          autoCapitalize="words"
          maxLength={100}
        />
        <TextField
          label="Your Email"
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          inputMode="email"
          autoCapitalize="none"
          autoCorrect={false}
          autoComplete="email"
          textContentType="emailAddress"
          maxLength={254}
        />
        <TextField
          label="Password"
          hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          autoComplete="new-password"
          textContentType="newPassword"
          maxLength={200}
        />
        <TextField
          label="Type It Again"
          value={confirmPassword}
          onChangeText={setConfirmPassword}
          secureTextEntry
          autoComplete="new-password"
          textContentType="newPassword"
          maxLength={200}
          returnKeyType="next"
        />

        {zones && zones.length > 0 && timezone ? (
          <TimeZoneField
            zones={zones}
            value={timezone}
            onChange={setZone}
            hint="Decides when your family's school day starts and ends."
          />
        ) : null}

        {error ? <ErrorMessage message={error} /> : null}

        <Button title="Create Account" busy={busy} onPress={submit} />
        <Button
          title="I already have an account"
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
  strong: {
    fontWeight: '700',
  },
  muted: {
    color: Colors.textMuted,
    fontSize: 14,
  },
});
