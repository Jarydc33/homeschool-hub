import { router } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Button, Card, ErrorMessage, Loading, Screen, SectionTitle } from '@/components/ui';
import { Colors, Radius, Spacing } from '@/constants/theme';
import { api, ApiError } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { addDays, formatDate } from '@/lib/dates';
import type { ParentDashboard, RecoveryStep, Student } from '@/lib/types';

// How far ahead the pick-up day can be chosen.
const DAYS_AHEAD = 14;

/**
 * "Missed a Day?": unfinished curriculum lessons pick up on the chosen day,
 * and the rest follow on their school days. Other work stays put.
 */
export default function MissedDayScreen() {
  const { me } = useAuth();
  const today = me?.today ?? null;

  const [students, setStudents] = useState<Student[] | null>(null);
  const [chosen, setChosen] = useState<number[]>([]);
  const [resumeOn, setResumeOn] = useState<string | null>(today);
  const [plan, setPlan] = useState<RecoveryStep[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Who's in the family, with anyone behind already chosen.
  useEffect(() => {
    api<ParentDashboard>('/dashboard')
      .then((data) => {
        setStudents(data.students.map((m) => m.student));
        setChosen(data.students_behind);
      })
      .catch((ex) => setError(ex instanceof ApiError ? ex.message : 'Something went wrong.'));
  }, []);

  const loadPlan = useCallback(async () => {
    if (chosen.length === 0 || !resumeOn) {
      setPlan([]);
      return;
    }

    const query = chosen.map((id) => `student_ids=${id}`).join('&');

    try {
      setPlan(null);
      setPlan(await api<RecoveryStep[]>(`/missed-day/plan?resume_on=${resumeOn}&${query}`));
      setError(null);
    } catch (ex) {
      setError(ex instanceof ApiError ? ex.message : 'Something went wrong.');
    }
  }, [chosen, resumeOn]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- previews the change whenever the choice changes.
    loadPlan();
  }, [loadPlan]);

  function toggle(id: number) {
    setChosen((current) =>
      current.includes(id) ? current.filter((x) => x !== id) : [...current, id],
    );
  }

  async function shift() {
    setSaving(true);
    setError(null);

    try {
      await api('/missed-day', {
        method: 'POST',
        body: { student_ids: chosen, resume_on: resumeOn },
      });
      router.back();
    } catch (ex) {
      setError(ex instanceof ApiError ? ex.message : 'Something went wrong.');
      setSaving(false);
    }
  }

  if (!today) {
    return <Loading />;
  }

  const days = Array.from({ length: DAYS_AHEAD }, (_, i) => addDays(today, i));

  return (
    <Screen>
      <Text style={styles.body}>
        Unfinished curriculum lessons pick up on the day you choose, and the rest follow in
        order on their school days. Other assignments stay as they are.
      </Text>

      <SectionTitle>Who missed?</SectionTitle>

      {students === null && !error ? <Loading /> : null}

      <View style={styles.chips}>
        {students?.map((student) => (
          <Chip
            key={student.id}
            label={student.name}
            selected={chosen.includes(student.id)}
            onPress={() => toggle(student.id)}
            checkbox
          />
        ))}
      </View>

      <SectionTitle>Pick up on</SectionTitle>

      <View style={styles.chips}>
        {days.map((day, i) => (
          <Chip
            key={day}
            label={i === 0 ? 'Today' : i === 1 ? 'Tomorrow' : formatDate(day, true)}
            selected={resumeOn === day}
            onPress={() => setResumeOn(day)}
          />
        ))}
      </View>

      <SectionTitle>What moves</SectionTitle>

      {error ? <ErrorMessage message={error} onRetry={loadPlan} /> : null}

      {plan === null && !error ? <Loading /> : null}

      {plan?.length === 0 ? (
        <Text style={styles.body}>
          {chosen.length === 0 ? 'Choose who missed.' : 'Nothing needs to move for that choice.'}
        </Text>
      ) : null}

      {plan?.map((step, index) => (
        <Card key={index}>
          <Text style={styles.title}>
            {step.student_name}: {step.title}
          </Text>
          <Text style={styles.muted}>
            {step.next_date
              ? `Lesson ${step.next_lesson} moves to ${formatDate(step.next_date, true)}.`
              : ''}
            {step.old_finish && step.new_finish
              ? ` Finish: ${formatDate(step.old_finish, true)} → ${formatDate(step.new_finish, true)}`
              : ''}
          </Text>
        </Card>
      ))}

      <View style={styles.actions}>
        <Button
          title="Shift Schedule"
          onPress={shift}
          busy={saving}
          disabled={!plan || plan.length === 0}
        />
        <Button title="Cancel" variant="secondary" onPress={() => router.back()} />
      </View>
    </Screen>
  );
}

function Chip({
  label,
  selected,
  onPress,
  checkbox = false,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
  checkbox?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole={checkbox ? 'checkbox' : 'radio'}
      accessibilityState={checkbox ? { checked: selected } : { selected }}
      onPress={onPress}
      style={[styles.chip, selected && styles.chipSelected]}>
      <Text style={[styles.chipText, selected && styles.chipTextSelected]}>
        {checkbox && selected ? '✓ ' : ''}
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  body: {
    color: Colors.text,
    fontSize: 16,
  },
  title: {
    color: Colors.navy,
    fontSize: 16,
    fontWeight: '600',
  },
  muted: {
    color: Colors.textMuted,
    fontSize: 14,
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
  },
  chip: {
    minHeight: 40,
    justifyContent: 'center',
    paddingHorizontal: Spacing.md,
    borderRadius: Radius,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.background,
  },
  chipSelected: {
    backgroundColor: Colors.navy,
    borderColor: Colors.navy,
  },
  chipText: {
    color: Colors.navy,
    fontSize: 15,
    fontWeight: '500',
  },
  chipTextSelected: {
    color: '#FFFFFF',
  },
  actions: {
    gap: Spacing.sm,
    marginTop: Spacing.md,
  },
});
