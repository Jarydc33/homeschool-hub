import { Image } from 'expo-image';
import { Link } from 'expo-router';
import { useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { Button, ErrorMessage, Screen } from '@/components/ui';
import { Colors, Radius, Spacing } from '@/constants/theme';
import { useAuth } from '@/lib/auth';

/**
 * Logging in: a parent or student with their email and password, or a
 * student's own device with a pairing code a parent made in Settings.
 */
export default function LoginScreen() {
  const { signIn, notice } = useAuth();
  const [pairing, setPairing] = useState(false);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!email.trim() || !password) {
      setError('Please enter your email and password.');
      return;
    }

    setBusy(true);
    setError(null);

    // On success the layout switches to the home screen by itself.
    const failed = await signIn(email, password);

    setBusy(false);

    if (failed) {
      setError(failed);
    }
  }

  return (
    <Screen>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.wrap}>
        <View style={styles.brand}>
          <Image
            source={require('../../assets/images/tally-logo.png')}
            style={styles.logo}
            contentFit="contain"
            accessibilityLabel="tally"
          />
          <Text style={styles.tagline}>Less logging, more learning.</Text>
        </View>

        {pairing ? (
          <PairingForm onCancel={() => setPairing(false)} />
        ) : (
          <View style={styles.form}>
            <Text style={styles.label}>Email</Text>
            <TextInput
              style={styles.input}
              value={email}
              onChangeText={setEmail}
              autoCapitalize="none"
              autoComplete="email"
              keyboardType="email-address"
              textContentType="emailAddress"
              inputMode="email"
              returnKeyType="next"
            />

            <Text style={styles.label}>Password</Text>
            <TextInput
              style={styles.input}
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              autoComplete="current-password"
              textContentType="password"
              returnKeyType="go"
              onSubmitEditing={submit}
            />

            {(error ?? notice) ? <ErrorMessage message={(error ?? notice) as string} /> : null}

            <Button title="Log In" onPress={submit} busy={busy} style={styles.submit} />

            <View style={styles.links}>
              <Link href="/forgot-password" style={styles.link}>
                Forgot your password?
              </Link>
              <Link href="/register" style={styles.link}>
                New to tally? Create an account
              </Link>
            </View>

            <Pressable
              accessibilityRole="button"
              onPress={() => {
                setError(null);
                setPairing(true);
              }}
              style={styles.switch}>
              <Text style={styles.switchText}>Have a pairing code?</Text>
              <Text style={styles.switchHint}>For a student&apos;s own device, with no email.</Text>
            </Pressable>
          </View>
        )}
      </KeyboardAvoidingView>
    </Screen>
  );
}

/** Pairs this device with a 6-digit code from a parent's Settings. */
function PairingForm({ onCancel }: { onCancel: () => void }) {
  const { pair, notice } = useAuth();
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    const digits = code.replace(/\s/g, '');

    if (!/^\d{6}$/.test(digits)) {
      setError('Please enter the 6-digit code.');
      return;
    }

    setBusy(true);
    setError(null);

    // On success the layout switches to the student's Today by itself.
    const failed = await pair(digits);

    if (failed) {
      setError(failed);
      setBusy(false);
    }
  }

  return (
    <View style={styles.form}>
      <Text style={styles.heading} accessibilityRole="header">
        Pair This Device
      </Text>
      <Text style={styles.body}>
        A parent makes a code in Settings, under Pair a Device. Once paired, this device shows only
        that student&apos;s view, with no email or password.
      </Text>

      <Text style={styles.label}>Pairing Code</Text>
      <TextInput
        style={[styles.input, styles.codeInput]}
        value={code}
        onChangeText={setCode}
        placeholder="123 456"
        placeholderTextColor={Colors.blueGrey}
        keyboardType="number-pad"
        inputMode="numeric"
        autoComplete="one-time-code"
        textContentType="oneTimeCode"
        maxLength={7}
        autoFocus
        returnKeyType="go"
        onSubmitEditing={submit}
        accessibilityLabel="Pairing code"
      />

      {(error ?? notice) ? <ErrorMessage message={(error ?? notice) as string} /> : null}

      <Button title="Pair This Device" onPress={submit} busy={busy} style={styles.submit} />
      <Button title="Back to Log In" variant="secondary" onPress={onCancel} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    justifyContent: 'center',
    gap: Spacing.xl,
    paddingVertical: Spacing.xl,
  },
  brand: {
    alignItems: 'center',
    gap: Spacing.sm,
  },
  logo: {
    width: 220,
    height: 90,
  },
  tagline: {
    color: Colors.textMuted,
    fontSize: 16,
  },
  form: {
    gap: Spacing.sm,
  },
  label: {
    color: Colors.navy,
    fontSize: 15,
    fontWeight: '600',
    marginTop: Spacing.sm,
  },
  input: {
    minHeight: 48,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius,
    paddingHorizontal: Spacing.md,
    fontSize: 16,
    color: Colors.text,
    backgroundColor: Colors.background,
  },
  submit: {
    marginTop: Spacing.md,
  },
  links: {
    alignItems: 'center',
    gap: Spacing.sm,
    marginTop: Spacing.sm,
  },
  link: {
    color: Colors.orangeText,
    fontSize: 15,
    fontWeight: '600',
    paddingVertical: Spacing.xs,
  },
  switch: {
    alignItems: 'center',
    paddingVertical: Spacing.md,
    marginTop: Spacing.sm,
  },
  switchText: {
    color: Colors.orangeText,
    fontSize: 16,
    fontWeight: '600',
  },
  switchHint: {
    color: Colors.textMuted,
    fontSize: 13,
  },
  heading: {
    color: Colors.navy,
    fontSize: 22,
    fontWeight: '700',
  },
  body: {
    color: Colors.text,
    fontSize: 15,
  },
  codeInput: {
    fontSize: 24,
    letterSpacing: 4,
    textAlign: 'center',
  },
});
