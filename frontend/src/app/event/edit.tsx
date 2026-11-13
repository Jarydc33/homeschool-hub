import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { ChoiceField, DateField, MultiChoiceField, SwitchField } from '@/components/form';
import { Button, Card, ErrorMessage, Loading, Screen, TextField } from '@/components/ui';
import { Colors, Spacing } from '@/constants/theme';
import { api, errorMessage } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { formatTime, parseTime } from '@/lib/dates';
import type { Event, Student } from '@/lib/types';

// The API's REPEAT_OPTIONS, in services/event_service.py.
const REPEATS = [
  'Every Day',
  'Weekly',
  'Monthly',
  'Weekdays',
  'Every Monday',
  'Every Tuesday',
  'Every Wednesday',
  'Every Thursday',
  'Every Friday',
];

const NO_REPEAT = '';

/**
 * Creating an event, or editing one when opened with ?id=. Changes to a
 * repeating event apply to every date.
 */
export default function EventEditScreen() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const { me } = useAuth();
  const today = me?.today ?? null;

  const [students, setStudents] = useState<Student[] | null>(null);
  const [existing, setExisting] = useState<Event | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [studentRows, event] = await Promise.all([
          api<Student[]>('/students'),
          id ? api<Event>(`/events/${id}`) : Promise.resolve(null),
        ]);

        setStudents(studentRows);
        setExisting(event);
      } catch (ex) {
        setLoadError(errorMessage(ex));
      }
    }

    load();
  }, [id]);

  const ready = students && today && (!id || existing);

  return (
    <Screen>
      {loadError ? <ErrorMessage message={loadError} /> : null}

      {!ready && !loadError ? <Loading /> : null}

      {ready ? <EventForm today={today} students={students} existing={existing} /> : null}
    </Screen>
  );
}

function EventForm({
  today,
  students,
  existing,
}: {
  today: string;
  students: Student[];
  existing: Event | null;
}) {
  const editing = existing !== null;
  const defaultUntil = `${today.slice(0, 4)}-12-31`;

  const [title, setTitle] = useState(existing?.title ?? '');
  const [description, setDescription] = useState(existing?.description ?? '');
  // Archived students aren't offered, so they drop off when saved.
  const [studentIds, setStudentIds] = useState<number[]>(
    (existing?.student_ids ?? []).filter((sid) => students.some((s) => s.id === sid)),
  );
  const [repeat, setRepeat] = useState(existing?.recurrence_pattern ?? NO_REPEAT);
  const [startDate, setStartDate] = useState(existing?.start_date ?? today);
  const [multiDay, setMultiDay] = useState(
    !!existing?.end_date && existing.end_date !== existing.start_date,
  );
  const [endDate, setEndDate] = useState(existing?.end_date ?? existing?.start_date ?? today);
  const [repeatUntil, setRepeatUntil] = useState(existing?.repeat_until ?? defaultUntil);
  const [time, setTime] = useState(existing?.start_time ? formatTime(existing.start_time) : '');

  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const repeats = repeat !== NO_REPEAT;

  function check(): string | null {
    if (!title.trim()) {
      return 'Please enter a title.';
    }

    if (!repeats && multiDay && endDate < startDate) {
      return "The last day can't be before the first day.";
    }

    if (repeats && repeatUntil < startDate) {
      return "It can't stop repeating before its first date.";
    }

    if (time.trim() && !parseTime(time)) {
      return 'Please enter the start time like 9:30 AM, or leave it empty for all day.';
    }

    return null;
  }

  async function save() {
    const problem = check();

    if (problem) {
      setError(problem);
      return;
    }

    const body = {
      title: title.trim(),
      description: description.trim() || null,
      student_ids: studentIds,
      start_date: startDate,
      end_date: !repeats && multiDay ? endDate : null,
      start_time: time.trim() ? parseTime(time) : null,
      recurrence_pattern: repeats ? repeat : null,
      repeat_until: repeats ? repeatUntil : null,
    };

    setBusy(true);
    setError(null);

    try {
      await api(editing ? `/events/${existing.id}` : '/events', {
        method: editing ? 'PUT' : 'POST',
        body,
      });

      close();
    } catch (ex) {
      setError(errorMessage(ex));
      setBusy(false);
    }
  }

  return (
    <View style={styles.form}>
      <Text style={styles.heading} accessibilityRole="header">
        {editing ? `Edit ${existing.title}` : 'New Event'}
      </Text>

      <TextField label="Title" value={title} onChangeText={setTitle} maxLength={200} />

      <TextField
        label="Details"
        hint="Optional. Where to go, what to bring, anything else."
        value={description}
        onChangeText={setDescription}
        multiline
        maxLength={5000}
        style={styles.multiline}
      />

      {students.length > 1 ? (
        <MultiChoiceField
          label="Who's It For?"
          hint="Choose none for the whole family, including students added later."
          options={students.map((s) => ({ value: s.id, label: s.name }))}
          value={studentIds}
          onChange={setStudentIds}
        />
      ) : null}

      <Card style={styles.schedule}>
        <Text style={styles.subheading}>When</Text>

        <ChoiceField
          label="Repeats"
          options={[
            { value: NO_REPEAT, label: 'Does not repeat' },
            ...REPEATS.map((r) => ({ value: r, label: r })),
          ]}
          value={repeat}
          onChange={setRepeat}
        />

        <DateField
          label={repeats ? 'First Date' : 'Date'}
          value={startDate}
          onChange={setStartDate}
          today={today}
        />

        {repeats ? (
          <DateField
            label="Repeats Until"
            value={repeatUntil}
            onChange={setRepeatUntil}
            today={today}
          />
        ) : (
          <>
            <SwitchField
              label="More than one day"
              hint="For a trip or camp that runs several days."
              value={multiDay}
              onChange={setMultiDay}
            />
            {multiDay ? (
              <DateField label="Last Day" value={endDate} onChange={setEndDate} today={today} />
            ) : null}
          </>
        )}

        <TextField
          label="Start Time"
          hint="Optional. Leave empty for all day."
          placeholder="For example, 9:30 AM"
          value={time}
          onChangeText={setTime}
          autoCapitalize="none"
          autoCorrect={false}
          maxLength={10}
        />
      </Card>

      {error ? <ErrorMessage message={error} /> : null}

      <View style={styles.actions}>
        <Button title="Cancel" variant="secondary" style={styles.action} onPress={close} />
        <Button
          title={editing ? 'Save Changes' : 'Create Event'}
          style={styles.action}
          busy={busy}
          onPress={save}
        />
      </View>
    </View>
  );
}

function close() {
  if (router.canGoBack()) {
    router.back();
  } else {
    router.replace('/events');
  }
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
  subheading: {
    color: Colors.navy,
    fontSize: 17,
    fontWeight: '700',
  },
  multiline: {
    minHeight: 96,
    paddingVertical: Spacing.sm,
    textAlignVertical: 'top',
  },
  schedule: {
    gap: Spacing.md,
    backgroundColor: Colors.surface,
  },
  actions: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  action: {
    flex: 1,
  },
});
