import { useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { DateField, formatYear, MultiChoiceField } from '@/components/form';
import { Button, Card, ErrorMessage, Loading, Screen, SectionTitle, TextField } from '@/components/ui';
import { Colors, Spacing } from '@/constants/theme';
import { api, errorMessage } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { formatDate } from '@/lib/dates';
import type { Assignment, NoteRow } from '@/lib/types';

/**
 * Notes for one date of an assignment, e.g. "Pages 40 to 45". Students see
 * them on that date. A blank note removes it.
 */
export default function AssignmentNotesScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { me } = useAuth();
  const today = me?.today ?? null;

  const [assignment, setAssignment] = useState<Assignment | null>(null);
  const [rows, setRows] = useState<NoteRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [found, notes] = await Promise.all([
        api<Assignment>(`/assignments/${id}`),
        api<NoteRow[]>(`/assignments/${id}/notes`),
      ]);
      setAssignment(found);
      setRows(notes);
      setError(null);
    } catch (ex) {
      setError(errorMessage(ex));
    }
  }, [id]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  return (
    <Screen>
      {error ? <ErrorMessage message={error} onRetry={load} /> : null}

      {(!assignment || !rows || !today) && !error ? <Loading /> : null}

      {assignment && rows && today ? (
        <NoteEditor assignment={assignment} rows={rows} today={today} onSaved={load} />
      ) : null}
    </Screen>
  );
}

function NoteEditor({
  assignment,
  rows,
  today,
  onSaved,
}: {
  assignment: Assignment;
  rows: NoteRow[];
  today: string;
  onSaved: () => Promise<void>;
}) {
  const dates = useMemo(() => [...new Set(rows.map((r) => r.date))].sort(), [rows]);

  // The next date from today on, or the last one if they've all passed.
  const [day, setDay] = useState(
    () => dates.find((d) => d >= today) ?? dates[dates.length - 1] ?? today,
  );

  const rowsOnDay = rows.filter((r) => r.date === day);

  const [chosen, setChosen] = useState<number[]>(rowsOnDay.map((r) => r.student.id));
  const [note, setNote] = useState(() => savedNotes(rows, day, chosen).note);
  const [mixed, setMixed] = useState(() => savedNotes(rows, day, chosen).mixed);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Show the saved note for the chosen day and students.
  function fill(forDay: string, studentIds: number[]) {
    const saved = savedNotes(rows, forDay, studentIds);

    setNote(saved.note);
    setMixed(saved.mixed);
  }

  function pickDay(next: string) {
    const ids = rows.filter((r) => r.date === next).map((r) => r.student.id);

    setDay(next);
    setChosen(ids);
    setNotice(null);
    setError(null);
    fill(next, ids);
  }

  function pickStudents(ids: number[]) {
    setChosen(ids);
    fill(day, ids);
  }

  function step(by: number) {
    const index = dates.indexOf(day) + by;

    if (index >= 0 && index < dates.length) {
      pickDay(dates[index]);
    }
  }

  async function save() {
    if (chosen.length === 0) {
      setError('Please choose at least one student.');
      return;
    }

    setBusy(true);
    setError(null);

    try {
      await api(`/assignments/${assignment.id}/notes`, {
        method: 'PUT',
        body: { date: day, student_ids: chosen, note: note.trim() },
      });
      setNotice(note.trim() ? 'Note saved.' : 'Note removed.');
      setMixed(false);
      await onSaved();
    } catch (ex) {
      setError(errorMessage(ex));
    } finally {
      setBusy(false);
    }
  }

  const withNotes = rows.filter((r) => r.notes);

  if (dates.length === 0) {
    return (
      <>
        <Text style={styles.heading}>{assignment.title}</Text>
        <Text style={styles.body}>This assignment has no students to add a note for.</Text>
      </>
    );
  }

  const index = dates.indexOf(day);

  return (
    <>
      <View>
        <Text style={styles.heading} accessibilityRole="header">
          {assignment.title}
        </Text>
        <Text style={styles.muted}>
          Students see a note with the work on that date. Leave it blank to remove it.
        </Text>
      </View>

      <Card>
        <DateField
          label="Date"
          value={day}
          onChange={pickDay}
          today={today}
          isEnabled={(d) => dates.includes(d)}
        />

        <View style={styles.stepper}>
          <Button
            title="‹ Previous"
            variant="secondary"
            style={styles.flex}
            disabled={index <= 0}
            onPress={() => step(-1)}
          />
          <Button
            title="Next ›"
            variant="secondary"
            style={styles.flex}
            disabled={index >= dates.length - 1}
            onPress={() => step(1)}
          />
        </View>

        {rowsOnDay.length > 1 ? (
          <MultiChoiceField
            label="For"
            options={rowsOnDay.map((r) => ({ value: r.student.id, label: r.student.name }))}
            value={chosen}
            onChange={pickStudents}
          />
        ) : (
          <Text style={styles.muted}>For {rowsOnDay[0]?.student.name}</Text>
        )}

        <TextField
          label="Note"
          hint={mixed ? 'These students have different notes. Saving replaces them all.' : undefined}
          value={note}
          onChangeText={(text) => {
            setNote(text);
            setNotice(null);
          }}
          multiline
          maxLength={5000}
          style={styles.multiline}
        />

        {error ? <ErrorMessage message={error} /> : null}

        {notice ? (
          <Text style={styles.notice} accessibilityLiveRegion="polite">
            ✓ {notice}
          </Text>
        ) : null}

        <Button title="Save Note" busy={busy} onPress={save} />
      </Card>

      {withNotes.length > 0 ? (
        <>
          <SectionTitle>Saved Notes</SectionTitle>
          {withNotes.map((row) => (
            <Pressable
              key={row.occurrence_id}
              accessibilityRole="button"
              accessibilityLabel={`${formatYear(row.date)}, ${row.student.name}: ${row.notes}. Edit`}
              onPress={() => pickDay(row.date)}>
              {({ pressed }) => (
                <Card style={[row.date === day && styles.current, pressed && styles.pressed]}>
                  <Text style={styles.noteDate}>
                    {formatDate(row.date, true)}  ·  {row.student.name}
                  </Text>
                  <Text style={styles.body}>{row.notes}</Text>
                </Card>
              )}
            </Pressable>
          ))}
        </>
      ) : null}
    </>
  );
}

// The note saved for these students on this day; mixed if they differ.
function savedNotes(rows: NoteRow[], day: string, studentIds: number[]) {
  const notes = new Set(
    rows
      .filter((r) => r.date === day && studentIds.includes(r.student.id))
      .map((r) => r.notes ?? ''),
  );

  return { note: [...notes].sort()[0] ?? '', mixed: notes.size > 1 };
}

const styles = StyleSheet.create({
  heading: {
    color: Colors.navy,
    fontSize: 24,
    fontWeight: '700',
  },
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
    fontSize: 16,
    fontWeight: '600',
  },
  stepper: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  flex: {
    flex: 1,
  },
  multiline: {
    minHeight: 96,
    paddingTop: Spacing.sm,
    textAlignVertical: 'top',
  },
  noteDate: {
    color: Colors.navy,
    fontSize: 14,
    fontWeight: '700',
  },
  current: {
    borderColor: Colors.orange,
  },
  pressed: {
    backgroundColor: Colors.surface,
  },
});
