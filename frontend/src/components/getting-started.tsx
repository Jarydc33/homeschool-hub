/**
 * The Parent Dashboard's Getting Started checklist, for a new family. Each
 * step ticks itself from what the family has done (the API's `setup`), so
 * nothing is stored for it. It goes away once every step is done, or when a
 * parent hides it, which is remembered on this device only.
 */
import { type Href, router } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Button, Card } from '@/components/ui';
import { Colors, Fonts, Spacing } from '@/constants/theme';
import { authStorage } from '@/lib/storage';
import type { SetupProgress } from '@/lib/types';

const HIDDEN_KEY = 'tally_getting_started_hidden';

const STEPS: {
  key: keyof SetupProgress;
  title: string;
  hint: string;
  action: string;
  href: Href;
}[] = [
  {
    key: 'students',
    title: 'Add your students',
    hint: 'Each child gets their own day of work to check off.',
    action: 'Add Students',
    href: '/students',
  },
  {
    key: 'subjects',
    title: 'Add the subjects you teach',
    hint: 'Math, reading, science and the rest, each with its own colour.',
    action: 'Add Subjects',
    href: '/subjects',
  },
  {
    key: 'work',
    title: 'Plan your first work',
    hint: 'A one-time assignment, one that repeats, or a whole curriculum.',
    action: 'Plan Work',
    href: '/assignment/edit',
  },
  {
    key: 'kids',
    title: 'Choose how your kids use tally',
    hint: 'Student Mode on your device, their own paired device, or a login of their own. Set a family PIN in Settings to start.',
    action: 'Go to Settings',
    href: '/settings',
  },
];

function isHidden(): boolean {
  try {
    return authStorage?.getItem(HIDDEN_KEY) === '1';
  } catch {
    return false;
  }
}

function rememberHidden(): void {
  try {
    authStorage?.setItem(HIDDEN_KEY, '1');
  } catch {
    // Storage blocked, e.g. a private window: hidden until the page reloads.
  }
}

// setup is missing only from an API older than this screen (the web app and
// the API deploy separately), and then the checklist waits.
export function GettingStarted({ setup }: { setup?: SetupProgress }) {
  const [hidden, setHidden] = useState(isHidden);

  if (!setup) {
    return null;
  }

  const done = STEPS.filter((step) => setup[step.key]).length;
  const next = STEPS.find((step) => !setup[step.key]);

  if (hidden || !next) {
    return null;
  }

  function hide() {
    rememberHidden();
    setHidden(true);
  }

  return (
    <Card style={styles.card}>
      <View style={styles.header}>
        <Text style={styles.title} accessibilityRole="header">
          Getting started
        </Text>
        <Text style={styles.count}>
          {done} of {STEPS.length} done
        </Text>
      </View>

      {STEPS.map((step, index) => {
        const isDone = setup[step.key];
        const isNext = step === next;

        return (
          <View
            key={step.key}
            style={[styles.step, isNext && styles.stepNext]}
            accessibilityLabel={`${step.title}${isDone ? ', done' : ''}`}>
            <View style={[styles.marker, isDone ? styles.markerDone : isNext && styles.markerNext]}>
              <Text style={[styles.markerText, (isDone || isNext) && styles.markerTextOn]}>
                {isDone ? '✓' : index + 1}
              </Text>
            </View>

            <View style={styles.stepBody}>
              <Text style={[styles.stepTitle, isDone && styles.stepTitleDone]}>{step.title}</Text>

              {isDone ? null : <Text style={styles.hint}>{step.hint}</Text>}

              {isNext ? (
                <Button
                  title={step.action}
                  style={styles.action}
                  onPress={() => router.push(step.href)}
                />
              ) : null}

              {!isDone && !isNext ? (
                <Pressable accessibilityRole="link" onPress={() => router.push(step.href)}>
                  <Text style={styles.link}>{step.action} →</Text>
                </Pressable>
              ) : null}
            </View>
          </View>
        );
      })}

      <Pressable accessibilityRole="button" onPress={hide} style={styles.hide}>
        <Text style={styles.hideText}>Hide this</Text>
      </Pressable>
    </Card>
  );
}

const styles = StyleSheet.create({
  card: {
    gap: Spacing.sm,
    borderColor: Colors.orange,
    borderWidth: 2,
  },
  header: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    gap: Spacing.sm,
  },
  title: {
    color: Colors.navy,
    fontSize: 20,
    fontFamily: Fonts.extrabold,
  },
  count: {
    color: Colors.textMuted,
    fontSize: 14,
    fontFamily: Fonts.semibold,
  },
  step: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Spacing.md,
    padding: Spacing.sm,
    borderRadius: 10,
  },
  stepNext: {
    backgroundColor: Colors.surface,
  },
  marker: {
    width: 30,
    height: 30,
    borderRadius: 15,
    borderWidth: 2,
    borderColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  markerDone: {
    backgroundColor: Colors.done,
    borderColor: Colors.done,
  },
  markerNext: {
    backgroundColor: Colors.orange,
    borderColor: Colors.orange,
  },
  markerText: {
    color: Colors.textMuted,
    fontSize: 14,
    fontFamily: Fonts.bold,
  },
  markerTextOn: {
    color: '#FFFFFF',
  },
  stepBody: {
    flex: 1,
    gap: Spacing.xs,
    paddingTop: 3,
  },
  stepTitle: {
    color: Colors.navy,
    fontSize: 17,
    fontFamily: Fonts.bold,
  },
  stepTitleDone: {
    color: Colors.textMuted,
    fontFamily: Fonts.semibold,
    textDecorationLine: 'line-through',
  },
  hint: {
    color: Colors.textMuted,
    fontSize: 15,
    lineHeight: 21,
    fontFamily: Fonts.regular,
  },
  action: {
    alignSelf: 'flex-start',
    marginTop: Spacing.xs,
  },
  link: {
    color: Colors.orangeText,
    fontSize: 15,
    fontFamily: Fonts.semibold,
    paddingVertical: Spacing.xs,
  },
  hide: {
    alignSelf: 'flex-end',
    paddingVertical: Spacing.xs,
  },
  hideText: {
    color: Colors.textMuted,
    fontSize: 14,
    fontFamily: Fonts.semibold,
    textDecorationLine: 'underline',
  },
});
