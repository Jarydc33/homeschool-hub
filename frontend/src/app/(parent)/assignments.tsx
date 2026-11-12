import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import {
  Button,
  Card,
  ConfirmCard,
  ErrorMessage,
  Loading,
  PageTitle,
  Screen,
  SectionTitle,
} from '@/components/ui';
import { Colors, Spacing } from '@/constants/theme';
import { api, errorMessage } from '@/lib/api';
import { formatDate } from '@/lib/dates';
import type { Assignment } from '@/lib/types';

/**
 * Assignments: the family's work, with its students, schedule and progress.
 * Creating and editing open their own screen, as do notes for a date.
 */
export default function AssignmentsScreen() {
  const [assignments, setAssignments] = useState<Assignment[] | null>(null);
  const [archived, setArchived] = useState<Assignment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const [archivingId, setArchivingId] = useState<number | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [restoringId, setRestoringId] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const [active, old] = await Promise.all([
        api<Assignment[]>('/assignments'),
        api<Assignment[]>('/assignments/archived'),
      ]);
      setAssignments(active);
      setArchived(old);
      setError(null);
    } catch (ex) {
      setError(errorMessage(ex));
    }
  }, []);

  // Reload when coming back from creating or editing one.
  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  async function refresh() {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }

  async function archive(assignment: Assignment) {
    await api(`/assignments/${assignment.id}/archive`, { method: 'POST' });
    setArchivingId(null);
    setNotice(`${assignment.title} archived. You can restore it below.`);
    await load();
  }

  async function restore(assignment: Assignment) {
    setRestoringId(assignment.id);
    try {
      await api(`/assignments/${assignment.id}/restore`, { method: 'POST' });
      setNotice(`${assignment.title} restored.`);
      await load();
    } catch (ex) {
      setError(errorMessage(ex));
    } finally {
      setRestoringId(null);
    }
  }

  function open(path: '/assignment/edit' | '/assignment/notes', id?: number) {
    setNotice(null);
    setArchivingId(null);
    router.push(id ? { pathname: path, params: { id: String(id) } } : path);
  }

  return (
    <Screen refreshing={refreshing} onRefresh={refresh}>
      <PageTitle>✅ Assignments</PageTitle>

      {error ? <ErrorMessage message={error} onRetry={load} /> : null}

      {notice ? (
        <Text style={styles.notice} accessibilityLiveRegion="polite">
          ✓ {notice}
        </Text>
      ) : null}

      {!assignments && !error ? <Loading /> : null}

      {assignments ? (
        <>
          <Button title="+ New Assignment" onPress={() => open('/assignment/edit')} />

          {assignments.length === 0 ? (
            <Text style={styles.body}>No assignments yet. Create your first one above.</Text>
          ) : null}

          {assignments.map((assignment) =>
            archivingId === assignment.id ? (
              <ConfirmCard
                key={assignment.id}
                title={`Archive ${assignment.title}?`}
                confirmLabel="Archive"
                onConfirm={() => archive(assignment)}
                onCancel={() => setArchivingId(null)}>
                It will be hidden everywhere, including students&apos; dashboards. Check-offs,
                notes and grades are kept, and you can restore it at any time.
              </ConfirmCard>
            ) : (
              <AssignmentCard
                key={assignment.id}
                assignment={assignment}
                onEdit={() => open('/assignment/edit', assignment.id)}
                onNotes={() => open('/assignment/notes', assignment.id)}
                onArchive={() => {
                  setNotice(null);
                  setArchivingId(assignment.id);
                }}
              />
            ),
          )}

          {archived.length > 0 ? (
            <>
              <Pressable
                accessibilityRole="button"
                accessibilityState={{ expanded: showArchived }}
                onPress={() => setShowArchived(!showArchived)}>
                <SectionTitle>
                  {showArchived ? '▾' : '▸'} Archived Assignments ({archived.length})
                </SectionTitle>
              </Pressable>

              {showArchived ? (
                <>
                  <Text style={styles.muted}>
                    Restoring an assignment brings back its dates, students, check-offs, notes
                    and grades. Dates that passed while it was archived show as overdue or
                    missed, and Missed a Day? on the dashboard can move curriculum lessons
                    forward.
                  </Text>
                  {archived.map((assignment) => (
                    <Card key={assignment.id}>
                      <View style={styles.row}>
                        <View style={styles.flex}>
                          <Text style={styles.title}>{assignment.title}</Text>
                          <Text style={styles.muted}>
                            {[assignment.subject?.name, assignment.assignment_type]
                              .filter(Boolean)
                              .join('  ·  ')}
                          </Text>
                        </View>
                        <Button
                          title="Restore"
                          variant="secondary"
                          busy={restoringId === assignment.id}
                          onPress={() => restore(assignment)}
                        />
                      </View>
                    </Card>
                  ))}
                </>
              ) : null}
            </>
          ) : null}
        </>
      ) : null}
    </Screen>
  );
}

function AssignmentCard({
  assignment,
  onEdit,
  onNotes,
  onArchive,
}: {
  assignment: Assignment;
  onEdit: () => void;
  onNotes: () => void;
  onArchive: () => void;
}) {
  const { subject, students, progress } = assignment;

  return (
    <Card>
      <Text style={styles.title}>{assignment.title}</Text>

      {subject ? (
        <View style={styles.row}>
          <View style={[styles.dot, { backgroundColor: subject.color ?? Colors.blueGrey }]} />
          <Text style={styles.muted}>{subject.name}</Text>
        </View>
      ) : null}

      <Text style={styles.detail}>
        👨‍🎓 {students.length > 0 ? students.map((s) => s.name).join(', ') : 'No students'}
      </Text>
      <Text style={styles.detail}>{schedule(assignment)}</Text>
      {progress ? (
        <Text style={styles.detail}>
          ✅ {progress.done} of {progress.total} done so far
        </Text>
      ) : null}
      {assignment.graded ? <Text style={styles.detail}>📊 Graded</Text> : null}
      {assignment.description ? (
        <Text style={styles.muted} numberOfLines={3}>
          {assignment.description}
        </Text>
      ) : null}

      <View style={styles.actions}>
        <Button title="Edit" variant="secondary" style={styles.action} onPress={onEdit} />
        <Button title="Notes" variant="secondary" style={styles.action} onPress={onNotes} />
        <Button title="Archive" variant="secondary" style={styles.action} onPress={onArchive} />
      </View>
    </Card>
  );
}

function schedule(assignment: Assignment): string {
  const start = formatDate(assignment.due_date, true);

  if (assignment.assignment_type === 'Recurring') {
    const end = assignment.end_date ? formatDate(assignment.end_date, true) : '?';

    return `🔁 ${assignment.recurrence_pattern}, ${start} to ${end}`;
  }

  if (assignment.assignment_type === 'Curriculum') {
    const days = (assignment.recurrence_pattern ?? '').split(',').join(', ');
    const finish = assignment.finish_date ? formatDate(assignment.finish_date, true) : '?';

    return `📖 ${assignment.lesson_count ?? 0} lessons on ${days}, ${start} to ${finish}`;
  }

  return `📅 Due ${start}`;
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
  detail: {
    color: Colors.text,
    fontSize: 15,
  },
  notice: {
    color: Colors.done,
    fontSize: 16,
    fontWeight: '600',
  },
  title: {
    color: Colors.navy,
    fontSize: 18,
    fontWeight: '700',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  flex: {
    flex: 1,
  },
  dot: {
    width: 12,
    height: 12,
    borderRadius: 6,
  },
  actions: {
    flexDirection: 'row',
    gap: Spacing.sm,
    marginTop: Spacing.xs,
  },
  action: {
    flex: 1,
    paddingHorizontal: Spacing.sm,
  },
});
