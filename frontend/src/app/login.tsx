import { Image } from 'expo-image';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, StyleSheet, Text, TextInput, View } from 'react-native';

import { Button, ErrorMessage, Screen } from '@/components/ui';
import { Colors, Radius, Spacing } from '@/constants/theme';
import { useAuth } from '@/lib/auth';

export default function LoginScreen() {
  const { signIn } = useAuth();

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

          {error ? <ErrorMessage message={error} /> : null}

          <Button title="Log In" onPress={submit} busy={busy} style={styles.submit} />
        </View>
      </KeyboardAvoidingView>
    </Screen>
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
});
