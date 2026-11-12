import { Stack, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, Card, ErrorMessage, Loading, SectionTitle } from '@/components/ui';
import { Colors, MaxContentWidth, Radius, Spacing } from '@/constants/theme';
import { api, ApiError } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { formatDate } from '@/lib/dates';
import type { Badge, CheckOffResult, StudentDashboard, WorkItem } from '@/lib/types';

/**
 * A student's day: today's work first, with a progress bar for today only,
 * then anything overdue, what's done, and what's coming up.
 */
export default function StudentDashboardScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { me, signOut } = useAuth();

  const [data, setData] = useState<StudentDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState<number | null>(null);
  const [celebrate, setCelebrate] = useState<Badge[]>([]);

  const load = useCallback(async () => {
    try {
      const dashboard = await api<StudentDashboard>(`/students/${id}/dashboard`);
      setData(dashboard);
      setError(null);
    } catch (ex) {
      setError(ex instanceof ApiError ? ex.message : 'Something went wrong.');
    }
  }, [id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- loads data when this opens; state changes only after the API answers.
    load();
  }, [load]);

  async function refresh() {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }

  async function toggle(item: WorkItem) {
    setSaving(item.occurrence_id);
    setError(null);

    try {
      const result = await api<CheckOffResult>(
        `/occurrences/${item.occurrence_id}/completed`,
        { method: 'PUT', body: { completed: !item.completed } },
      );

      setCelebrate(result.new_badges);
      await load();
    } catch (ex) {
      setError(ex instanceof ApiError ? ex.message : 'Something went wrong.');
    } finally {
      setSaving(null);
    }
  }

  // A student on their own login can't leave; a parent goes back to the list.
  const isStudent = me?.role === 'student';

  return (
    <SafeAreaView style={styles.screen} edges={['left', 'right']}>
      <Stack.Screen options={{ title: data ? data.student.name : 'Today', headerBackVisible: !isStudent }} />

      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}>
        <View style={styles.content}>
          {error ? <ErrorMessage message={error} onRetry={load} /> : null}

          {!data && !error ? <Loading /> : null}

          {data ? (
            <Dashboard data={data} saving={saving} celebrate={celebrate} onToggle={toggle} />
          ) : null}

          {isStudent ? (
            <Button title="Log Out" variant="secondary" onPress={signOut} style={styles.logout} />
          ) : null}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function Dashboard({
  data,
  saving,
  celebrate,
  onToggle,
}: {
  data: StudentDashboard;
  saving: number | null;
  celebrate: Badge[];
  onToggle: (item: WorkItem) => void;
}) {
  const { done, total } = data.progress;

  const allDone = total > 0 && done === total;

  return (
    <>
      {data.banners.map((banner) => (
        <Card key={banner.id} style={styles.banner}>
          <Text style={styles.bannerTitle}>{banner.title}</Text>
          <Text style={styles.body}>{banner.message}</Text>
        </Card>
      ))}

      <Text style={styles.date}>{formatDate(data.today)}</Text>
      <Text style={styles.message}>{data.message}</Text>

      {celebrate.map((badge) => (
        <Card key={badge.key} style={styles.celebrate}>
          <Text style={styles.celebrateText}>
            {badge.icon} New badge: {badge.name}
          </Text>
          <Text style={styles.body}>{badge.description}</Text>
        </Card>
      ))}

      <SectionTitle>Today</SectionTitle>

      {total > 0 ? (
        <View accessible accessibilityLabel={`${done} of ${total} done today`}>
          <View style={styles.progressTrack}>
            <View style={[styles.progressFill, { width: `${(done / total) * 100}%` }]} />
          </View>
          <Text style={styles.muted}>
            {allDone ? 'All done for today!' : `${done} of ${total} done`}
            {data.achievements.streak > 0 ? `  ·  ${data.achievements.streak}-day streak` : ''}
          </Text>
        </View>
      ) : (
        <Text style={styles.body}>Nothing due today.</Text>
      )}

      {data.today_work.map((item) => (
        <WorkRow key={item.occurrence_id} item={item} saving={saving} onToggle={onToggle} />
      ))}

      {data.completed_today.map((item) => (
        <WorkRow key={item.occurrence_id} item={item} saving={saving} onToggle={onToggle} />
      ))}

      {data.overdue.length > 0 ? (
        <>
          <SectionTitle>Overdue</SectionTitle>
          {data.overdue.map((item) => (
            <WorkRow key={item.occurrence_id} item={item} saving={saving} onToggle={onToggle} showDate />
          ))}
        </>
      ) : null}

      {data.upcoming.length > 0 ? (
        <>
          <SectionTitle>Coming Up</SectionTitle>
          {data.upcoming.map((item) => (
            <WorkRow key={item.occurrence_id} item={item} saving={saving} onToggle={onToggle} showDate />
          ))}
        </>
      ) : null}

      {data.upcoming_events.length > 0 ? (
        <>
          <SectionTitle>Events</SectionTitle>
          {data.upcoming_events.map((entry) => (
            <Card key={`${entry.event.id}-${entry.date}`}>
              <Text style={styles.title}>{entry.event.title}</Text>
              <Text style={styles.muted}>{entry.when}</Text>
            </Card>
          ))}
        </>
      ) : null}
    </>
  );
}

function WorkRow({
  item,
  saving,
  onToggle,
  showDate = false,
}: {
  item: WorkItem;
  saving: number | null;
  onToggle: (item: WorkItem) => void;
  showDate?: boolean;
}) {
  const busy = saving === item.occurrence_id;

  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityState={{ checked: item.completed, busy }}
      accessibilityLabel={item.title}
      disabled={saving !== null}
      onPress={() => onToggle(item)}>
      {({ pressed }) => (
        <Card style={[styles.workRow, pressed && styles.pressed]}>
          <View style={[styles.box, item.completed && styles.boxChecked]}>
            {item.completed ? <Text style={styles.check}>{'✓'}</Text> : null}
          </View>

          <View style={styles.workText}>
            <Text style={[styles.title, item.completed && styles.titleDone]}>{item.title}</Text>
            <Text style={styles.muted}>
              {[item.subject?.name, showDate ? formatDate(item.date, true) : null]
                .filter(Boolean)
                .join('  ·  ')}
            </Text>
            {item.notes ? <Text style={styles.note}>{item.notes}</Text> : null}
          </View>

          {item.subject?.color ? (
            <View style={[styles.subjectDot, { backgroundColor: item.subject.color }]} />
          ) : null}
        </Card>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  scroll: {
    flexGrow: 1,
  },
  content: {
    width: '100%',
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
    padding: Spacing.md,
    gap: Spacing.sm,
  },
  date: {
    color: Colors.navy,
    fontSize: 22,
    fontWeight: '700',
  },
  message: {
    color: Colors.textMuted,
    fontSize: 16,
    fontStyle: 'italic',
  },
  body: {
    color: Colors.text,
    fontSize: 15,
  },
  muted: {
    color: Colors.textMuted,
    fontSize: 14,
  },
  banner: {
    backgroundColor: Colors.surface,
  },
  bannerTitle: {
    color: Colors.navy,
    fontSize: 16,
    fontWeight: '700',
  },
  celebrate: {
    backgroundColor: '#FFF3EC',
    borderColor: Colors.orange,
  },
  celebrateText: {
    color: Colors.orangeText,
    fontSize: 16,
    fontWeight: '700',
  },
  progressTrack: {
    height: 12,
    borderRadius: 6,
    backgroundColor: Colors.surface,
    overflow: 'hidden',
    marginBottom: Spacing.xs,
  },
  progressFill: {
    height: '100%',
    backgroundColor: Colors.orange,
  },
  workRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
  },
  pressed: {
    backgroundColor: Colors.surface,
  },
  box: {
    width: 28,
    height: 28,
    borderRadius: 8,
    borderWidth: 2,
    borderColor: Colors.blueGrey,
    alignItems: 'center',
    justifyContent: 'center',
  },
  boxChecked: {
    backgroundColor: Colors.done,
    borderColor: Colors.done,
  },
  check: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '700',
  },
  workText: {
    flex: 1,
    gap: 2,
  },
  title: {
    color: Colors.navy,
    fontSize: 16,
    fontWeight: '600',
  },
  titleDone: {
    color: Colors.textMuted,
    textDecorationLine: 'line-through',
  },
  note: {
    color: Colors.text,
    fontSize: 14,
    marginTop: Spacing.xs,
  },
  subjectDot: {
    width: 10,
    height: 10,
    borderRadius: Radius,
  },
  logout: {
    marginTop: Spacing.lg,
  },
});
