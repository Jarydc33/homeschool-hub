/**
 * The frame for screens used before signing in (sign-up, Forgot Password,
 * finishing an email link): the logo, then the form.
 */
import { Image } from 'expo-image';
import { KeyboardAvoidingView, Platform, StyleSheet, Text, View } from 'react-native';

import { Screen } from '@/components/ui';
import { Colors, Spacing } from '@/constants/theme';

export function AuthShell({
  title,
  intro,
  children,
}: {
  title: string;
  intro?: string;
  children: React.ReactNode;
}) {
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
        </View>

        <View style={styles.body}>
          <Text style={styles.title} accessibilityRole="header">
            {title}
          </Text>
          {intro ? <Text style={styles.intro}>{intro}</Text> : null}
          {children}
        </View>
      </KeyboardAvoidingView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    justifyContent: 'center',
    gap: Spacing.lg,
    paddingVertical: Spacing.xl,
    width: '100%',
    maxWidth: 480,
    alignSelf: 'center',
  },
  brand: {
    alignItems: 'center',
  },
  logo: {
    width: 160,
    height: 64,
  },
  body: {
    gap: Spacing.md,
  },
  title: {
    color: Colors.navy,
    fontSize: 26,
    fontWeight: '700',
  },
  intro: {
    color: Colors.textMuted,
    fontSize: 16,
  },
});
