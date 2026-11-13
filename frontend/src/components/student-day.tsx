/**
 * A student's day: today's work first, with a progress bar for today only,
 * then anything overdue, and what's coming up. Shared by a parent's look at
 * one student and the student's own Today screen.
 */
import { useCallback, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { EarnedBadges, Stat, Stats } from '@/components/achievements';
import { Card, SectionTitle } from '@/components/ui';
import { Colors, Radius, Spacing } from '@/constants/theme';
import { api, errorMessage } from '@/lib/api';
import { formatDate } from '@/lib/dates';
import type { Badge, CheckOffResult, StudentDashboard, WorkItem } from '@/lib/types';

/**
 * Loads a student's day and checks work on and off. A tap shows at once and
 * saves in the background; the day reloads once every save has finished,
 * for streaks and badges, and to put back anything that didn't save.
 */
export function useStudentDay(studentId: number | string | null) {
  const [data, setData] = useState<StudentDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  // The work being saved right now.
  const [saving, setSaving] = useState<number[]>([]);
  const [celebrate, setCelebrate] = useState<Badge[]>([]);

  // Only the latest load's answer is shown, and none while saves are going.
  const latest = useRef(0);
  const pending = useRef(0);

  const load = useCallback(async () => {
    if (studentId === null) {
      return;
    }

    const request = ++latest.current;

    try {
      const day = await api<StudentDashboard>(`/students/${studentId}/dashboard`);

      if (request === latest.current && pending.current === 0) {
        setData(day);
        setError(null);
      }
    } catch (ex) {
      if (request === latest.current) {
        setError(errorMessage(ex));
      }
    }
  }, [studentId]);

  async function toggle(item: WorkItem) {
    const completed = !item.completed;

    pending.current += 1;
    setSaving((ids) => [...ids, item.occurrence_id]);
    setError(null);
    setData((day) => (day ? withCompleted(day, item.occurrence_id, completed) : day));

    try {
      const result = await api<CheckOffResult>(`/occurrences/${item.occurrence_id}/completed`, {
        method: 'PUT',
        body: { completed },
      });

      if (result.new_badges.length > 0) {
        setCelebrate(result.new_badges);
      }
    } catch (ex) {
      setError(`“${item.title}” didn't save. ${errorMessage(ex)}`);
    } finally {
      pending.current -= 1;
      setSaving((ids) => ids.filter((id) => id !== item.occurrence_id));
    }

    if (pending.current === 0) {
      await load();
    }
  }

  return { data, error, saving, celebrate, load, toggle };
}

/**
 * The day with one piece of work checked on or off, before the API answers.
 * Today's progress moves with it; the reload afterwards sorts it into the
 * right section.
 */
function withCompleted(day: StudentDashboard, id: number, completed: boolean): StudentDashboard {
  const mark = (items: WorkItem[]) =>
    items.map((w) => (w.occurrence_id === id ? { ...w, completed } : w));

  const isToday = [...day.today_work, ...day.completed_today].some(
    (w) => w.occurrence_id === id && w.completed !== completed,
  );

  return {
    ...day,
    today_work: mark(day.today_work),
    completed_today: mark(day.completed_today),
    overdue: mark(day.overdue),
    upcoming: mark(day.upcoming),
    missed: mark(day.missed),
    recently_completed: mark(day.recently_completed),
    recently_missed: mark(day.recently_missed),
    progress: isToday
      ? { ...day.progress, done: day.progress.done + (completed ? 1 : -1) }
      : day.progress,
  };
}

export function StudentDayView({
  data,
  saving,
  celebrate,
  onToggle,
}: {
  data: StudentDashboard;
  saving: number[];
  celebrate: Badge[];
  onToggle: (item: WorkItem) => void;
}) {
  const { done, total } = data.progress;
  const [showMissed, setShowMissed] = useState(false);
  const [showCompleted, setShowCompleted] = useState(false);
  const [showToEarn, setShowToEarn] = useState(false);

  const allDone = total > 0 && done === total;
  const { achievements, reading, pe } = data;
  const badges = [...achievements.badges, ...reading.badges, ...pe.badges];
  const toEarn = badges.filter((b) => !b.earned);
  const earnedCount = badges.length - toEarn.length;

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

      {data.recently_missed.length > 0 ? (
        <>
          <Toggle
            open={showMissed}
            onPress={() => setShowMissed(!showMissed)}
            title={`🕓 Missed (${data.recently_missed.length})`}
          />
          {showMissed ? (
            <>
              <Text style={styles.muted}>
                Repeating work from the last 30 days. You can still check these off if they got
                done.
              </Text>
              {data.recently_missed.map((item) => (
                <WorkRow
                  key={item.occurrence_id}
                  item={item}
                  saving={saving}
                  onToggle={onToggle}
                  showDate
                />
              ))}
            </>
          ) : null}
        </>
      ) : null}

      <SectionTitle>🔥 Streaks</SectionTitle>
      <Stats>
        <Stat
          label={`🔥 Streak (best ${achievements.best_streak})`}
          value={days(achievements.streak)}
        />
        <Stat
          label={`📖 Reading (${reading.pages_this_week} pages this week)`}
          value={days(reading.streak)}
        />
        <Stat
          label={`🏃 P.E. This Week (${pe.active_days_this_week} of 7 days)`}
          value={minutes(pe.minutes_this_week)}
        />
      </Stats>
      <Text style={styles.muted}>
        Days with no work don&apos;t break a streak, and catching up repairs it.
      </Text>

      <SectionTitle>
        🏅 Badges ({earnedCount} of {badges.length})
      </SectionTitle>
      {earnedCount > 0 ? (
        <EarnedBadges badges={badges} />
      ) : (
        <Text style={styles.muted}>Finish your first piece of work to earn your first badge.</Text>
      )}
      {toEarn.length > 0 ? (
        <>
          <Toggle
            open={showToEarn}
            onPress={() => setShowToEarn(!showToEarn)}
            title="Badges to earn"
          />
          {showToEarn
            ? toEarn.map((badge) => (
                <Text key={badge.key} style={styles.body}>
                  {badge.icon} {badge.name}: {badge.description}
                </Text>
              ))
            : null}
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

      {data.recently_completed.length > 0 ? (
        <>
          <Toggle
            open={showCompleted}
            onPress={() => setShowCompleted(!showCompleted)}
            title={`✅ Completed in the Last 30 Days (${data.recently_completed.length})`}
          />
          {showCompleted ? (
            <>
              <Text style={styles.muted}>Tap one to uncheck it, if it was checked by mistake.</Text>
              {data.recently_completed.map((item) => (
                <WorkRow
                  key={item.occurrence_id}
                  item={item}
                  saving={saving}
                  onToggle={onToggle}
                  showDate
                />
              ))}
            </>
          ) : null}
        </>
      ) : null}
    </>
  );
}

function days(count: number): string {
  return count === 1 ? '1 day' : `${count} days`;
}

// "1 hr 30 min", like PEService.describe_minutes.
function minutes(total: number): string {
  const hours = Math.floor(total / 60);
  const rest = total % 60;

  if (!hours) {
    return `${rest} min`;
  }

  return rest ? `${hours} hr ${rest} min` : `${hours} hr`;
}

function Toggle({ open, onPress, title }: { open: boolean; onPress: () => void; title: string }) {
  return (
    <Pressable accessibilityRole="button" accessibilityState={{ expanded: open }} onPress={onPress}>
      <SectionTitle>
        {open ? '▾' : '▸'} {title}
      </SectionTitle>
    </Pressable>
  );
}

function WorkRow({
  item,
  saving,
  onToggle,
  showDate = false,
}: {
  item: WorkItem;
  saving: number[];
  onToggle: (item: WorkItem) => void;
  showDate?: boolean;
}) {
  const busy = saving.includes(item.occurrence_id);

  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityState={{ checked: item.completed, busy }}
      accessibilityLabel={item.title}
      disabled={busy}
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
});
