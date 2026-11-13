import { router } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { Button, ErrorMessage, Screen, TextField } from '@/components/ui';
import { Colors, Spacing } from '@/constants/theme';
import { errorMessage } from '@/lib/api';
import { useAuth } from '@/lib/auth';

/**
 * Unpairs a student's own device with the family PIN, sending it back to
 * the login. Parents can also end it from Settings without being here. The
 * API limits wrong tries and says so in its message.
 */
export default function UnpairDeviceScreen() {
  const { unpair } = useAuth();
  const [pin, setPin] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!/^\d{4}$/.test(pin)) {
      setError('Please enter the 4-digit family PIN.');
      return;
    }

    setBusy(true);
    setError(null);

    try {
      // Once unpaired, the layout sends this device to the login by itself.
      await unpair(pin);
    } catch (ex) {
      setError(errorMessage(ex));
      setPin('');
      setBusy(false);
    }
  }

  return (
    <Screen>
      <View style={styles.form}>
        <Text style={styles.heading} accessibilityRole="header">
          🔓 Unpair This Device
        </Text>
        <Text style={styles.body}>
          A parent enters the family PIN. This device goes back to the login, and needs a new
          pairing code to show this student&apos;s view again.
        </Text>

        <TextField
          label="Family PIN"
          value={pin}
          onChangeText={setPin}
          secureTextEntry
          keyboardType="number-pad"
          inputMode="numeric"
          maxLength={4}
          autoComplete="off"
          autoFocus
          returnKeyType="done"
          onSubmitEditing={submit}
        />

        {error ? <ErrorMessage message={error} /> : null}

        <View style={styles.actions}>
          <Button
            title="Cancel"
            variant="secondary"
            style={styles.action}
            onPress={() => (router.canGoBack() ? router.back() : router.replace('/today'))}
          />
          <Button title="Unpair" style={styles.action} busy={busy} onPress={submit} />
        </View>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  form: {
    gap: Spacing.lg,
  },
  heading: {
    color: Colors.navy,
    fontSize: 24,
    fontWeight: '700',
  },
  body: {
    color: Colors.text,
    fontSize: 16,
  },
  actions: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  action: {
    flex: 1,
  },
});
