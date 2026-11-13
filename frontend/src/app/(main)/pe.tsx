import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import {
  EarnedBadges,
  earnedKeys,
  NewBadges,
  newlyEarned,
  Stat,
  Stats,
} from '@/components/achievements';
import { ChoiceField, DateField, MultiChoiceField } from '@/components/form';
import {
  Button,
  Card,
  ConfirmCard,
  ErrorMessage,
  Loading,
  PageTitle,
  Screen,
  SectionTitle,
  TextField,
} from '@/components/ui';
import { Colors, Radius, Spacing } from '@/constants/theme';
import { api, errorMessage } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { formatDate } from '@/lib/dates';
import type { Activity, Badge, GradingPeriod, PELog, Student } from '@/lib/types';

// The API's MAX_MINUTES, in services/pe_service.py.
const MAX_MINUTES = 600;

// How many entries the list shows; every entry still counts in the totals.
const RECENT_COUNT = 30;

// How many earlier activities to offer as one-tap choices.
const SUGGESTION_COUNT = 8;

const QUICK_MINUTES = [15, 30, 45, 60];

/**
 * P.E.: a student's activities, minutes this week and all time, totals by
 * grading period, and hour badges. An activity can be logged for several
 * students at once. A mistaken entry is deleted, not archived.
 */
export default function PEScreen() {
  const [students, setStudents] = useState<Student[] | null>(null);
  const [chosen, setChosen] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Student[]>('/students')
      .then(setStudents)
      .catch((ex) => setError(errorMessage(ex)));
  }, []);

  // The first student until one is picked.
  const studentId = chosen ?? students?.[0]?.id ?? null;

  return (
    <Screen>
      <PageTitle>🏃 P.E.</PageTitle>

      {error ? <ErrorMessage message={error} /> : null}

      {!students && !error ? <Loading /> : null}

      {students && students.length === 0 ? (
        <Text style={styles.body}>Add a student on the Students screen first.</Text>
      ) : null}

      {students && students.length > 1 ? (
        <ChoiceField
          label="Student"
          options={students.map((s) => ({ value: s.id, label: s.name }))}
          value={studentId}
          onChange={setChosen}
        />
      ) : null}

      {students && studentId !== null ? (
        <ActivityLog key={studentId} studentId={studentId} students={students} />
      ) : null}
    </Screen>
  );
}

// "1 hr 30 min", like PEService.describe_minutes.
function describeMinutes(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;

  if (!hours) {
    return `${rest} min`;
  }

  return rest ? `${hours} hr ${rest} min` : `${hours} hr`;
}

/** One student's P.E. Kept apart so a student's own view can reuse it. */
function ActivityLog({ studentId, students }: { studentId: number; students: Student[] }) {
  const { me } = useAuth();
  const today = me?.today ?? null;

  const [data, setData] = useState<PELog | null>(null);
  const [periods, setPeriods] = useState<GradingPeriod[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [newBadges, setNewBadges] = useState<Badge[]>([]);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  // Goes up after each save, to start the form afresh.
  const [saves, setSaves] = useState(0);

  // The badges earned before a change, to spot new ones after it.
  const earned = useRef<Set<string> | null>(null);

  const load = useCallback(async () => {
    try {
      const [log, periodRows] = await Promise.all([
        api<PELog>(`/students/${studentId}/pe`),
        api<GradingPeriod[]>('/grading-periods'),
      ]);
      const fresh = newlyEarned(earned.current, log.summary.badges);

      if (fresh.length > 0) {
        setNewBadges(fresh);
      }

      earned.current = earnedKeys(log.summary.badges);
      setData(log);
      setPeriods(periodRows);
      setError(null);
    } catch (ex) {
      setError(errorMessage(ex));
    }
  }, [studentId]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  async function logActivity(values: ActivityValues) {
    setNotice(null);
    setNewBadges([]);
    await api('/pe', { method: 'POST', body: values });
    setSaves((n) => n + 1);
    setNotice(`${values.activity} saved.`);
    await load();
  }

  async function remove(entry: Activity) {
    await api(`/pe/${entry.id}`, { method: 'DELETE' });
    setDeletingId(null);
    setNewBadges([]);
    setNotice('Entry deleted.');
    await load();
  }

  if (!data || !today) {
    return error ? <ErrorMessage message={error} onRetry={load} /> : <Loading />;
  }

  const { summary } = data;
  const recent = data.logs.slice(0, RECENT_COUNT);

  return (
    <>
      {error ? <ErrorMessage message={error} onRetry={load} /> : null}

      <NewBadges badges={newBadges} />

      {notice ? (
        <Text style={styles.notice} accessibilityLiveRegion="polite">
          ✓ {notice}
        </Text>
      ) : null}

      <Stats>
        <Stat label="⏱️ This Week" value={describeMinutes(summary.minutes_this_week)} />
        <Stat label="📅 Active Days This Week" value={`${summary.active_days_this_week} of 7`} />
        <Stat label="🏅 All Time" value={describeMinutes(summary.total_minutes)} />
      </Stats>

      <EarnedBadges badges={summary.badges} />

      {periods.length > 0 ? (
        <Card>
          <Text style={styles.muted}>Totals by grading period</Text>
          {periods.map((period) => {
            const minutes = data.logs
              .filter((log) => log.date >= period.start_date && log.date <= period.end_date)
              .reduce((total, log) => total + log.minutes, 0);

            return (
              <View key={period.id} style={styles.periodRow}>
                <Text style={[styles.body, styles.flex]}>{period.name}</Text>
                <Text style={styles.strong}>{describeMinutes(minutes)}</Text>
              </View>
            );
          })}
        </Card>
      ) : null}

      <ActivityForm
        key={saves}
        studentId={studentId}
        students={students}
        today={today}
        known={data.known_activities}
        onSave={logActivity}
      />

      <SectionTitle>Recent Activities</SectionTitle>

      {recent.length === 0 ? <Text style={styles.body}>Nothing logged yet.</Text> : null}

      {recent.map((entry) =>
        deletingId === entry.id ? (
          <ConfirmCard
            key={entry.id}
            title={`Delete ${entry.activity}?`}
            confirmLabel="Delete"
            onConfirm={() => remove(entry)}
            onCancel={() => setDeletingId(null)}>
            This removes the entry for {formatDate(entry.date, true)} from the totals. It&apos;s
            for fixing a mistake and can&apos;t be undone.
          </ConfirmCard>
        ) : (
          <Card key={entry.id}>
            <View style={styles.row}>
              <View style={styles.flex}>
                <Text style={styles.entryTitle}>
                  {entry.activity}: {describeMinutes(entry.minutes)}
                </Text>
                <Text style={styles.muted}>
                  {formatDate(entry.date, true)}, {entry.date.slice(0, 4)}
                </Text>
              </View>
              <Button
                title="Delete"
                variant="secondary"
                onPress={() => {
                  setNotice(null);
                  setDeletingId(entry.id);
                }}
              />
            </View>
          </Card>
        ),
      )}

      {data.logs.length > recent.length ? (
        <Text style={styles.muted}>
          Showing the latest {recent.length} of {data.logs.length} entries. Every entry still
          counts towards the totals.
        </Text>
      ) : null}
    </>
  );
}

interface ActivityValues {
  student_ids: number[];
  date: string;
  activity: string;
  minutes: number;
}

function ActivityForm({
  studentId,
  students,
  today,
  known,
  onSave,
}: {
  studentId: number;
  students: Student[];
  today: string;
  known: string[];
  onSave: (values: ActivityValues) => Promise<void>;
}) {
  const [who, setWho] = useState<number[]>([studentId]);
  const [activity, setActivity] = useState('');
  const [date, setDate] = useState(today);
  const [minutesText, setMinutesText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    const text = minutesText.trim();
    const minutes = Number(text);

    if (who.length === 0) {
      setError('Please choose who did it.');
      return;
    }

    if (!activity.trim()) {
      setError('Please enter an activity.');
      return;
    }

    if (!/^\d+$/.test(text) || minutes < 1 || minutes > MAX_MINUTES) {
      setError(`Please enter the minutes, from 1 to ${MAX_MINUTES}.`);
      return;
    }

    setBusy(true);
    setError(null);

    try {
      await onSave({ student_ids: who, date, activity: activity.trim(), minutes });
    } catch (ex) {
      setError(errorMessage(ex));
      setBusy(false);
    }
  }

  const suggestions = known.slice(0, SUGGESTION_COUNT);

  return (
    <Card>
      <Text style={styles.cardTitle}>➕ Log an Activity</Text>

      <View style={styles.form}>
        {students.length > 1 ? (
          <MultiChoiceField
            label="Who Did It?"
            hint="Pick more than one for something you did together."
            options={students.map((s) => ({ value: s.id, label: s.name }))}
            value={who}
            onChange={setWho}
          />
        ) : null}

        <View style={styles.field}>
          <TextField
            label="Activity"
            placeholder="For example, Swimming"
            value={activity}
            onChangeText={setActivity}
            autoCapitalize="sentences"
            maxLength={100}
          />
          {suggestions.length > 0 ? (
            <View style={styles.chips} accessibilityLabel="Activities done before">
              {suggestions.map((name) => (
                <QuickChip
                  key={name}
                  label={name}
                  selected={activity.trim() === name}
                  onPress={() => setActivity(name)}
                />
              ))}
            </View>
          ) : null}
        </View>

        <DateField
          label="Date"
          value={date}
          onChange={setDate}
          today={today}
          isEnabled={(d) => d <= today}
        />

        <View style={styles.field}>
          <TextField
            label="Minutes"
            value={minutesText}
            onChangeText={setMinutesText}
            placeholder="30"
            keyboardType="number-pad"
            inputMode="numeric"
            maxLength={3}
            returnKeyType="done"
            onSubmitEditing={submit}
          />
          <View style={styles.chips} accessibilityLabel="Common lengths">
            {QUICK_MINUTES.map((m) => (
              <QuickChip
                key={m}
                label={`${m} min`}
                selected={minutesText.trim() === String(m)}
                onPress={() => setMinutesText(String(m))}
              />
            ))}
          </View>
        </View>

        {error ? <ErrorMessage message={error} /> : null}

        <Button title="Save Activity" busy={busy} onPress={submit} />
      </View>
    </Card>
  );
}

/** A small tap target that fills in a box. */
function QuickChip({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ selected }}
      onPress={onPress}
      style={({ pressed }) => [
        styles.chip,
        selected && styles.chipSelected,
        pressed && styles.dim,
      ]}>
      <Text style={[styles.chipText, selected && styles.chipTextSelected]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  flex: {
    flex: 1,
  },
  dim: {
    opacity: 0.7,
  },
  body: {
    color: Colors.text,
    fontSize: 16,
  },
  strong: {
    color: Colors.navy,
    fontSize: 16,
    fontWeight: '700',
  },
  muted: {
    color: Colors.textMuted,
    fontSize: 14,
  },
  notice: {
    color: Colors.done,
    fontSize: 16,
    fontWeight: '600',
  },
  cardTitle: {
    color: Colors.navy,
    fontSize: 18,
    fontWeight: '700',
  },
  entryTitle: {
    color: Colors.navy,
    fontSize: 16,
    fontWeight: '700',
  },
  periodRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    paddingVertical: Spacing.xs,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
  },
  form: {
    gap: Spacing.md,
  },
  field: {
    gap: Spacing.sm,
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
  },
  chip: {
    minHeight: 44,
    justifyContent: 'center',
    paddingHorizontal: Spacing.md,
    borderRadius: Radius * 2,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.surface,
  },
  chipSelected: {
    backgroundColor: Colors.navy,
    borderColor: Colors.navy,
  },
  chipText: {
    color: Colors.navy,
    fontSize: 14,
  },
  chipTextSelected: {
    color: '#FFFFFF',
    fontWeight: '600',
  },
});
