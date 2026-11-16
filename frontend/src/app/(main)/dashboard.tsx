import { Link, router, useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { ChoiceField } from '@/components/form';
import { Button, Card, ErrorMessage, Loading, PageTitle, Screen, SectionTitle } from '@/components/ui';
import { Colors, Fonts, Spacing } from '@/constants/theme';
import { api, ApiError, errorMessage } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { formatDate } from '@/lib/dates';
import type { DueWork, FamilySettings, ParentDashboard, Student, StudentMetrics } from '@/lib/types';

// From this window width, the Dashboard splits into two columns (the
// sidebar takes 248 of it).
const TWO_COLUMNS = 1100;

// Overdue work shows this many until opened.
const OVERDUE_SHOWN = 5;

// Each student's initial sits on one of these, in order.
const STUDENT_COLOURS = ['#E2672F', '#2F6FB3', '#2E7D4F', '#7A4FB3', '#B3452F', '#1F8A8A'];

/**
 * The Parent Dashboard: how everyone is doing today, each student's day,
 * what needs attention, then events and what was finished lately.
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
    <Screen refreshing={refreshing} onRefresh={refresh} wide>
      {data ? null : <PageTitle>🏡 Dashboard</PageTitle>}

      {error ? <ErrorMessage message={error} onRetry={load} /> : null}

      {!data && !error ? <Loading /> : null}

      {data ? <Dashboard data={data} /> : null}
    </Screen>
  );
}

function Dashboard({ data }: { data: ParentDashboard }) {
  const { width } = useWindowDimensions();
  const [studentMode, setStudentMode] = useState(false);
  const twoColumns = width >= TWO_COLUMNS;
  const hasStudents = data.students.length > 0;

  const main = (
    <View style={styles.column}>
      {studentMode ? (
        <StudentModeCard
          students={data.students.map((m) => m.student)}
          onClose={() => setStudentMode(false)}
        />
      ) : null}

      <SectionTitle>Students</SectionTitle>

      {hasStudents ? (
        <View style={styles.studentGrid}>
          {data.students.map((metrics, index) => (
            <StudentCard
              key={metrics.student.id}
              metrics={metrics}
              colour={STUDENT_COLOURS[index % STUDENT_COLOURS.length]}
            />
          ))}
        </View>
      ) : (
        <Card>
          <Text style={styles.body}>No students yet. Add your first one to get started.</Text>
          <Button
            title="Add a Student"
            variant="secondary"
            onPress={() => router.push('/students')}
          />
        </Card>
      )}

      <NeedsAttention data={data} />

      <SectionTitle>Due Today</SectionTitle>

      {data.due_today.length > 0 ? (
        <WorkList work={data.due_today} who={(work) => listNames(work.student_names)} />
      ) : (
        <Text style={styles.body}>Nothing left to do today.</Text>
      )}
    </View>
  );

  const side = (
    <View style={[styles.column, twoColumns && styles.side]}>
      <SectionTitle>Upcoming Events</SectionTitle>

      {data.upcoming_events.length > 0 ? (
        <Card style={styles.list}>
          {data.upcoming_events.map((entry, index) => (
            <View
              key={`${entry.event.id}-${entry.date}`}
              style={[styles.listRow, index > 0 && styles.listRowDivided]}>
              <Text style={styles.title}>🎉 {entry.event.title}</Text>
              <Text style={styles.muted}>
                {entry.when}  ·  {entry.event.audience}
              </Text>
            </View>
          ))}
        </Card>
      ) : (
        <Text style={styles.body}>No events in the next 30 days.</Text>
      )}

      <SectionTitle>Recent Activity</SectionTitle>

      {data.recent_activity.length > 0 ? (
        data.recent_activity.map((day) => (
          <View key={day.date} style={styles.activityDay}>
            <Text style={styles.activityLabel}>{day.label}</Text>
            {day.items.map((item, index) => (
              <Text key={index} style={styles.activityItem}>
                {item}
              </Text>
            ))}
          </View>
        ))
      ) : (
        <Text style={styles.body}>Nothing has been finished in the last 7 days yet.</Text>
      )}
    </View>
  );

  return (
    <>
      <View style={styles.header}>
        <PageTitle>🏡 Dashboard</PageTitle>
        {hasStudents && !studentMode ? (
          <Button
            title="🔒 Student Mode"
            variant="secondary"
            style={styles.headerButton}
            onPress={() => setStudentMode(true)}
          />
        ) : null}
      </View>

      <Summary data={data} />

      {data.banners.map((banner) => (
        <Card key={banner.id} style={styles.banner}>
          <Text style={styles.bannerTitle}>📢 {banner.title}</Text>
          <Text style={styles.body}>{banner.message}</Text>
        </Card>
      ))}

      {twoColumns ? (
        <View style={styles.columns}>
          {main}
          {side}
        </View>
      ) : (
        <>
          {main}
          {side}
        </>
      )}
    </>
  );
}

/** The answer at a glance: is everyone on track today? */
function Summary({ data }: { data: ParentDashboard }) {
  const students = data.students;
  const onTrack = students.filter((m) => m.overdue_count === 0).length;
  const overdue = students.reduce((sum, m) => sum + m.overdue_count, 0);
  const done = students.reduce((sum, m) => sum + m.today_done, 0);
  const total = students.reduce((sum, m) => sum + m.today_total, 0);
  const allDone = total > 0 && done === total && overdue === 0;

  let title: string;

  if (students.length === 0) {
    title = 'Welcome to tally!';
  } else if (allDone) {
    title = 'Everyone is done for today! 🎉';
  } else if (onTrack === students.length) {
    title = students.length === 1 ? 'On track today' : 'Everyone is on track';
  } else {
    title = `${onTrack} of ${students.length} on track`;
  }

  const details = [
    total > 0 ? `${done} of ${total} done today` : students.length > 0 ? 'No work due today' : null,
    overdue > 0 ? `${overdue} overdue` : null,
  ]
    .filter(Boolean)
    .join('  ·  ');

  return (
    <View
      style={[styles.summary, allDone && styles.summaryDone]}
      accessible
      accessibilityLabel={[formatDate(data.today), title, details, data.message]
        .filter(Boolean)
        .join('. ')}>
      <Text style={styles.summaryDate}>{formatDate(data.today)}</Text>
      <Text style={styles.summaryTitle}>{title}</Text>
      {details ? <Text style={styles.summaryDetails}>{details}</Text> : null}
      <Text style={styles.summaryMessage}>{data.message}</Text>
    </View>
  );
}

function StudentCard({ metrics, colour }: { metrics: StudentMetrics; colour: string }) {
  const { student, today_done, today_total, overdue_count, streak, next_up } = metrics;
  const allDone = today_total > 0 && today_done === today_total;

  const status =
    today_total === 0
      ? 'No work today'
      : allDone
        ? '✓ All done today'
        : `${today_done} of ${today_total} done today`;

  return (
    <Link href={{ pathname: '/student/[id]', params: { id: String(student.id) } }} asChild>
      <Pressable
        accessibilityRole="link"
        accessibilityLabel={[
          student.name,
          status,
          overdue_count > 0 ? `${overdue_count} overdue` : null,
          streak > 0 ? `${streak}-day streak` : null,
          next_up ? `Next up: ${next_up}` : null,
          'Open their day.',
        ]
          .filter(Boolean)
          .join('. ')}
        style={styles.studentCell}>
        {({ pressed }) => (
          <Card style={[styles.studentCard, pressed && styles.pressed]}>
            <View style={styles.row}>
              <View style={[styles.initial, { backgroundColor: colour }]}>
                <Text style={styles.initialText}>{student.name.charAt(0).toUpperCase()}</Text>
              </View>
              <Text style={[styles.name, styles.flex]} numberOfLines={1}>
                {student.name}
              </Text>
              {streak > 0 ? <Text style={styles.streak}>🔥 {streak}</Text> : null}
              <Text style={styles.chevron}>{'›'}</Text>
            </View>

            {today_total > 0 ? (
              <View style={styles.progressTrack}>
                <View
                  style={[
                    styles.progressFill,
                    allDone && styles.progressDone,
                    { width: `${(today_done / today_total) * 100}%` },
                  ]}
                />
              </View>
            ) : null}

            <View style={styles.row}>
              <Text style={[styles.status, allDone && styles.good]}>{status}</Text>
              {overdue_count > 0 ? (
                <Text style={styles.overdueCount}>{overdue_count} overdue</Text>
              ) : null}
            </View>

            {next_up ? (
              <Text style={styles.muted} numberOfLines={1}>
                Next up: {next_up}
              </Text>
            ) : null}
          </Card>
        )}
      </Pressable>
    </Link>
  );
}

/** "Missed a Day?" and overdue work, folded after the first few. */
function NeedsAttention({ data }: { data: ParentDashboard }) {
  const [showAll, setShowAll] = useState(false);
  const behind = data.students.filter((m) => data.students_behind.includes(m.student.id));
  const overdue = showAll ? data.overdue : data.overdue.slice(0, OVERDUE_SHOWN);

  return (
    <>
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
        <>
          <WorkList
            work={overdue}
            who={(work) =>
              `${listNames(work.student_names)} still ${
                work.student_names.length === 1 ? 'needs' : 'need'
              } to finish this`
            }
            overdue
          />
          {data.overdue.length > OVERDUE_SHOWN ? (
            <Pressable accessibilityRole="button" onPress={() => setShowAll(!showAll)}>
              <Text style={styles.more}>
                {showAll ? 'Show less' : `Show all ${data.overdue.length} overdue`}
              </Text>
            </Pressable>
          ) : null}
        </>
      ) : (
        <Text style={styles.good}>✓ Nothing overdue.</Text>
      )}
    </>
  );
}

/** Work as one card of rows, each with its subject's colour down the left. */
function WorkList({
  work,
  who,
  overdue = false,
}: {
  work: DueWork[];
  who: (work: DueWork) => string;
  overdue?: boolean;
}) {
  return (
    <Card style={[styles.list, overdue && styles.warning]}>
      {work.map((item, index) => (
        <View
          key={item.assignment_id}
          style={[
            styles.listRow,
            styles.workRow,
            { borderLeftColor: item.subject?.color ?? Colors.blueGrey },
            index > 0 && styles.listRowDivided,
            index > 0 && overdue && styles.listRowDividedWarning,
          ]}>
          <Text style={styles.title}>{item.title}</Text>
          <Text style={styles.muted}>
            {[item.subject?.name, who(item)].filter(Boolean).join('  ·  ')}
          </Text>
        </View>
      ))}
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
function StudentModeCard({ students, onClose }: { students: Student[]; onClose: () => void }) {
  const { reloadMe } = useAuth();
  const [hasPin, setHasPin] = useState<boolean | null>(null);
  const [chosen, setChosen] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const studentId = chosen ?? students[0].id;

  useEffect(() => {
    api<FamilySettings>('/family')
      .then((family) => setHasPin(family.has_pin))
      .catch((ex) => setError(errorMessage(ex)));
  }, []);

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

  const name = students.find((s) => s.id === studentId)?.name ?? 'the student';

  return (
    <Card>
      <Text style={styles.cardTitle}>🔒 Start Student Mode</Text>
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

      {hasPin && students.length > 1 ? (
        <ChoiceField
          label="Student"
          options={students.map((s) => ({ value: s.id, label: s.name }))}
          value={studentId}
          onChange={setChosen}
        />
      ) : null}

      {hasPin === null && !error ? <Loading /> : null}

      {error ? <ErrorMessage message={error} /> : null}

      <View style={styles.actions}>
        <Button title="Cancel" variant="secondary" style={styles.action} onPress={onClose} />
        {hasPin ? (
          <Button title={`Start for ${name}`} style={styles.action} busy={busy} onPress={start} />
        ) : null}
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  flex: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Spacing.sm,
  },
  headerButton: {
    minHeight: 40,
    marginTop: Spacing.sm,
    paddingHorizontal: Spacing.md,
  },
  // The navy card at the top.
  summary: {
    backgroundColor: Colors.navy,
    borderRadius: 16,
    padding: Spacing.lg,
    gap: Spacing.xs,
  },
  summaryDone: {
    backgroundColor: Colors.done,
  },
  summaryDate: {
    color: 'rgba(255, 255, 255, 0.78)',
    fontSize: 14,
    fontFamily: Fonts.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  summaryTitle: {
    color: '#FFFFFF',
    fontSize: 28,
    lineHeight: 34,
    fontFamily: Fonts.extrabold,
    letterSpacing: -0.5,
  },
  summaryDetails: {
    color: '#FFFFFF',
    fontSize: 16,
    fontFamily: Fonts.semibold,
  },
  summaryMessage: {
    color: Colors.onNavy,
    fontSize: 15,
    lineHeight: 22,
    fontFamily: Fonts.regular,
    fontStyle: 'italic',
    marginTop: Spacing.sm,
  },
  banner: {
    backgroundColor: Colors.surface,
  },
  bannerTitle: {
    color: Colors.navy,
    fontSize: 16,
    fontFamily: Fonts.bold,
  },
  columns: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Spacing.xl,
  },
  column: {
    flex: 2,
    gap: Spacing.md,
  },
  side: {
    flex: 1,
  },
  body: {
    color: Colors.text,
    fontSize: 16,
    fontFamily: Fonts.regular,
  },
  muted: {
    color: Colors.textMuted,
    fontSize: 14,
    fontFamily: Fonts.regular,
  },
  good: {
    color: Colors.done,
    fontSize: 16,
    fontFamily: Fonts.semibold,
  },
  title: {
    color: Colors.navy,
    fontSize: 16,
    fontFamily: Fonts.semibold,
  },
  cardTitle: {
    color: Colors.navy,
    fontSize: 17,
    fontFamily: Fonts.bold,
  },
  more: {
    color: Colors.orangeText,
    fontSize: 15,
    fontFamily: Fonts.semibold,
    paddingVertical: Spacing.xs,
  },
  // Student cards.
  studentGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.md,
  },
  studentCell: {
    flexGrow: 1,
    flexBasis: 280,
  },
  studentCard: {
    gap: Spacing.sm,
    padding: Spacing.md,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Spacing.sm,
  },
  initial: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  initialText: {
    color: '#FFFFFF',
    fontSize: 18,
    fontFamily: Fonts.extrabold,
  },
  name: {
    color: Colors.navy,
    fontSize: 19,
    fontFamily: Fonts.bold,
  },
  streak: {
    color: Colors.navy,
    fontSize: 15,
    fontFamily: Fonts.bold,
  },
  chevron: {
    color: Colors.textMuted,
    fontSize: 24,
    fontFamily: Fonts.regular,
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
  progressDone: {
    backgroundColor: Colors.done,
  },
  status: {
    color: Colors.text,
    fontSize: 15,
    fontFamily: Fonts.semibold,
  },
  overdueCount: {
    color: Colors.danger,
    fontSize: 14,
    fontFamily: Fonts.semibold,
  },
  warning: {
    backgroundColor: '#FFF6EE',
    borderColor: '#F3C6A8',
  },
  // A card of rows.
  list: {
    padding: 0,
    gap: 0,
    overflow: 'hidden',
  },
  listRow: {
    paddingVertical: Spacing.md - 4,
    paddingHorizontal: Spacing.md,
    gap: 2,
  },
  listRowDivided: {
    borderTopWidth: 1,
    borderTopColor: Colors.border,
  },
  listRowDividedWarning: {
    borderTopColor: '#F3C6A8',
  },
  workRow: {
    borderLeftWidth: 5,
  },
  activityDay: {
    gap: Spacing.xs,
  },
  activityLabel: {
    color: Colors.navy,
    fontSize: 15,
    fontFamily: Fonts.bold,
  },
  activityItem: {
    color: Colors.text,
    fontSize: 15,
    fontFamily: Fonts.regular,
  },
  actions: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  action: {
    flex: 1,
  },
});
