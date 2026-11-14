import { router } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { Button, ErrorMessage, Screen, TextField } from '@/components/ui';
import { Colors, Spacing } from '@/constants/theme';
import { api, errorMessage } from '@/lib/api';
import { FEEDBACK_EMAIL } from '@/lib/nav';

/**
 * Feedback from a parent. The API saves it and emails it to Tally, so it
 * doesn't depend on the device having an email app set up.
 */
export default function FeedbackScreen() {
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  async function send() {
    if (!message.trim()) {
      setError('Please write a message.');
      return;
    }

    setBusy(true);
    setError(null);

    try {
      await api('/feedback', { method: 'POST', body: { message } });
      setSent(true);
    } catch (ex) {
      setError(errorMessage(ex));
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <Screen>
        <Text style={styles.notice} accessibilityLiveRegion="polite">
          ✓ Thanks! Your feedback was sent.
        </Text>
        <Text style={styles.body}>We read every message, and we&apos;ll reply by email if we have questions.</Text>
        <Button title="Done" onPress={() => router.back()} />
      </Screen>
    );
  }

  return (
    <Screen>
      <Text style={styles.body}>
        Something confusing, broken or missing? An idea? Tell us here and it comes straight to us.
      </Text>

      <TextField
        label="Your feedback"
        value={message}
        onChangeText={(text) => {
          setMessage(text);
          setError(null);
        }}
        multiline
        maxLength={5000}
        autoFocus
        style={styles.multiline}
      />

      {error ? <ErrorMessage message={error} /> : null}

      <View style={styles.actions}>
        <Button title="Send Feedback" busy={busy} onPress={send} />
        <Button title="Cancel" variant="secondary" onPress={() => router.back()} />
      </View>

      <Text style={styles.muted}>Or email us at {FEEDBACK_EMAIL}.</Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  body: {
    color: Colors.text,
    fontSize: 16,
  },
  muted: {
    color: Colors.textMuted,
    fontSize: 14,
  },
  notice: {
    color: Colors.done,
    fontSize: 18,
    fontWeight: '600',
  },
  multiline: {
    minHeight: 160,
    paddingTop: Spacing.sm,
    textAlignVertical: 'top',
  },
  actions: {
    gap: Spacing.sm,
  },
});
