import { Link, router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ChoiceField } from '@/components/form';
import { Button, Card, ErrorMessage, Loading, PageTitle, Screen, SectionTitle } from '@/components/ui';
import { Colors, Radius, Spacing } from '@/constants/theme';
import { api, ApiError, errorMessage } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { formatDate } from '@/lib/dates';
import type { DueWork, FamilySettings, ParentDashboard, Student, StudentMetrics } from '@/lib/types';

/**
 * The Parent Dashboard: each student's progress, what needs attention, what's
 * due today, upcoming events and what was finished lately.
 */
export default function DashboardScreen() {
  const [data, setData] = useState<ParentDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await api<ParentDashboard>('/dashboard'));
      setError(null);
    } catch (ex) {
      setError(ex instanceof ApiError ? ex.message : 'Something went wrong.');
    }
  }, []);

  // Reload whenever this comes back into view, e.g. after a student's day
  // or "Missed a Day?".
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

  return (
    <Screen refreshing={refreshing} onRefresh={refresh}>
      <PageTitle>🏡 Dashboard</PageTitle>

      {error ? <ErrorMessage message={error} onRetry={load} /> : null}

      {!data && !error ? <Loading /> : null}

      {data ? <Dashboard data={data} /> : null}
    </Screen>
  );
}

function Dashboard({ data }: { data: ParentDashboard }) {
  const behind = data.students.filter((m) => data.students_behind.includes(m.student.id));

  return (
    <>
      <View>
        <Text style={styles.date}>{formatDate(data.today)}</Text>
        <Text style={styles.message}>{data.message}</Text>
      </View>

      {data.banners.map((banner) => (
        <Card key={banner.id} style={styles.banner}>
          <Text style={styles.bannerTitle}>📢 {banner.title}</Text>
          <Text style={styles.body}>{banner.message}</Text>
        </Card>
      ))}

      <SectionTitle>Students</SectionTitle>

      {data.students.length === 0 ? (
        <Card>
          <Text style={styles.body}>No students yet. Add your first one to get started.</Text>
          <Button
            title="Add a Student"
            variant="secondary"
            onPress={() => router.push('/students')}
          />
        </Card>
      ) : (
        <View style={styles.studentGrid}>
          {data.students.map((metrics) => (
            <StudentCard key={metrics.student.id} metrics={metrics} />
          ))}
        </View>
      )}

      {data.students.length > 0 ? (
        <StartStudentMode students={data.students.map((m) => m.student)} />
      ) : null}

      <SectionTitle>Needs Attention</SectionTitle>

      {data.has_curriculum ? (
        <Card style={behind.length > 0 ? styles.warning : undefined}>
          <Text style={styles.body}>
            {behind.length > 0
              ? `${listNames(behind.map((m) => m.student.name))} ${
                  behind.length === 1 ? 'has' : 'have'
                } unfinished lessons from before today.`
              : 'Sick day or a day off? Move unfinished lessons forward.'}
          </Text>
          <Button
            title="🤒 Missed a Day?"
            variant="secondary"
            onPress={() => router.push('/missed-day')}
          />
        </Card>
      ) : null}

      {data.overdue.length > 0 ? (
        data.overdue.map((work) => (
          <WorkCard
            key={`overdue-${work.assignment_id}`}
            work={work}
            who={`${listNames(work.student_names)} still ${
              work.student_names.length === 1 ? 'needs' : 'need'
            } to finish this`}
            overdue
          />
        ))
      ) : (
        <Text style={styles.good}>✓ Nothing overdue.</Text>
      )}

      <SectionTitle>Due Today</SectionTitle>

      {data.due_today.length > 0 ? (
        data.due_today.map((work) => (
          <WorkCard
            key={`today-${work.assignment_id}`}
            work={work}
            who={listNames(work.student_names)}
          />
        ))
      ) : (
        <Text style={styles.body}>Nothing due today.</Text>
      )}

      <SectionTitle>Upcoming Events</SectionTitle>

      {data.upcoming_events.length > 0 ? (
        data.upcoming_events.map((entry) => (
          <Card key={`${entry.event.id}-${entry.date}`}>
            <Text style={styles.title}>🎉 {entry.event.title}</Text>
            <Text style={styles.muted}>
              {entry.when}  ·  {entry.event.audience}
            </Text>
          </Card>
        ))
      ) : (
        <Text style={styles.body}>No events in the next 30 days.</Text>
      )}

      <SectionTitle>Recent Activity</SectionTitle>

      {data.recent_activity.length > 0 ? (
        data.recent_activity.map((day) => (
          <View key={day.date} style={styles.activityDay}>
            <Text style={styles.activityLabel}>{day.label}</Text>
            {day.items.map((item, index) => (
              <Text key={index} style={styles.body}>
                {item}
              </Text>
            ))}
          </View>
        ))
      ) : (
        <Text style={styles.body}>Nothing has been finished in the last 7 days yet.</Text>
      )}
    </>
  );
}

function StudentCard({ metrics }: { metrics: StudentMetrics }) {
  const { student, completed, total, percent, overdue_count } = metrics;

  return (
    <Link href={{ pathname: '/student/[id]', params: { id: String(student.id) } }} asChild>
      <Pressable
        accessibilityRole="link"
        accessibilityLabel={`${student.name}: ${completed} of ${total} done, ${overdue_count} overdue. Open their day.`}
        style={styles.studentCell}>
        {({ pressed }) => (
          <Card style={pressed && styles.pressed}>
            <View style={styles.row}>
              <Text style={styles.name}>{student.name}</Text>
              <Text style={styles.chevron}>{'›'}</Text>
            </View>

            <View style={styles.progressTrack}>
              <View style={[styles.progressFill, { width: `${percent}%` }]} />
            </View>

            <Text style={styles.muted}>
              {total > 0 ? `${completed} of ${total} done (${percent}%)` : 'No work due yet'}
            </Text>

            {overdue_count > 0 ? (
              <Text style={styles.overdueCount}>{overdue_count} overdue</Text>
            ) : null}
          </Card>
        )}
      </Pressable>
    </Link>
  );
}

function WorkCard({ work, who, overdue = false }: { work: DueWork; who: string; overdue?: boolean }) {
  return (
    <Card style={overdue ? styles.warning : undefined}>
      <View style={styles.row}>
        <Text style={[styles.title, styles.flex]}>{work.title}</Text>
        {work.subject?.color ? (
          <View style={[styles.subjectDot, { backgroundColor: work.subject.color }]} />
        ) : null}
      </View>
      <Text style={styles.muted}>
        {[work.subject?.name, who].filter(Boolean).join('  ·  ')}
      </Text>
    </Card>
  );
}

// "Ann", "Ann and Bob", "Ann, Bob and Cat".
function listNames(names: string[]): string {
  if (names.length <= 1) {
    return names[0] ?? '';
  }

  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

/**
 * Hands this device to a student: it shows only their view until a parent
 * enters the family PIN. Needs a PIN set first.
 */
function StartStudentMode({ students }: { students: Student[] }) {
  const { reloadMe } = useAuth();
  const [open, setOpen] = useState(false);
  const [hasPin, setHasPin] = useState<boolean | null>(null);
  const [chosen, setChosen] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const studentId = chosen ?? students[0].id;

  async function openCard() {
    setOpen(true);
    setError(null);

    try {
      const family = await api<FamilySettings>('/family');
      setHasPin(family.has_pin);
    } catch (ex) {
      setError(errorMessage(ex));
    }
  }

  async function start() {
    setBusy(true);
    setError(null);

    try {
      await api('/student-mode', { method: 'POST', body: { student_id: studentId } });
      await reloadMe();
      router.replace('/today');
    } catch (ex) {
      setError(errorMessage(ex));
      setBusy(false);
    }
  }

  if (!open) {
    return <Button title="🔒 Start Student Mode" variant="secondary" onPress={openCard} />;
  }

  const name = students.find((s) => s.id === studentId)?.name ?? 'the student';

  return (
    <Card>
      <Text style={styles.title}>🔒 Start Student Mode</Text>
      <Text style={styles.body}>
        Switch this device to one student&apos;s view, to hand it to them. Leaving Student Mode
        needs the family PIN.
      </Text>

      {hasPin === false ? (
        <>
          <Text style={styles.body}>First, set a family PIN in Settings.</Text>
          <Button title="Go to Settings" onPress={() => router.push('/settings')} />
        </>
      ) : null}

      {hasPin ? (
        <>
          {students.length > 1 ? (
            <ChoiceField
              label="Student"
              options={students.map((s) => ({ value: s.id, label: s.name }))}
              value={studentId}
              onChange={setChosen}
            />
          ) : null}
        </>
      ) : null}

      {hasPin === null && !error ? <Loading /> : null}

      {error ? <ErrorMessage message={error} /> : null}

      <View style={styles.actions}>
        <Button
          title="Cancel"
          variant="secondary"
          style={styles.action}
          onPress={() => setOpen(false)}
        />
        {hasPin ? (
          <Button title={`Start for ${name}`} style={styles.action} busy={busy} onPress={start} />
        ) : null}
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  actions: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  action: {
    flex: 1,
  },
  date: {
    color: Colors.textMuted,
    fontSize: 15,
    fontWeight: '600',
  },
  message: {
    color: Colors.text,
    fontSize: 16,
    marginTop: Spacing.xs,
  },
  banner: {
    backgroundColor: Colors.surface,
  },
  bannerTitle: {
    color: Colors.navy,
    fontSize: 16,
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
  good: {
    color: Colors.done,
    fontSize: 16,
    fontWeight: '600',
  },
  title: {
    color: Colors.navy,
    fontSize: 16,
    fontWeight: '600',
  },
  flex: {
    flex: 1,
  },
  studentGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.md,
  },
  studentCell: {
    flexGrow: 1,
    flexBasis: 260,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Spacing.sm,
  },
  name: {
    color: Colors.navy,
    fontSize: 18,
    fontWeight: '700',
  },
  chevron: {
    color: Colors.textMuted,
    fontSize: 24,
  },
  pressed: {
    backgroundColor: Colors.surface,
  },
  progressTrack: {
    height: 10,
    borderRadius: 5,
    backgroundColor: Colors.surface,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 5,
    backgroundColor: Colors.orange,
  },
  overdueCount: {
    color: Colors.danger,
    fontSize: 14,
    fontWeight: '600',
  },
  warning: {
    backgroundColor: '#FFF6EE',
    borderColor: '#F3C6A8',
  },
  subjectDot: {
    width: 12,
    height: 12,
    borderRadius: Radius,
  },
  activityDay: {
    gap: Spacing.xs,
  },
  activityLabel: {
    color: Colors.navy,
    fontSize: 15,
    fontWeight: '700',
  },
});
