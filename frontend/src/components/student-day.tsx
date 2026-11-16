/**
 * A student's day: today's work first, with a progress bar for today only,
 * then anything overdue, and what's coming up. Shared by a parent's look at
 * one student and the student's own Today screen.
 */
import { useCallback, useRef, useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';

import { EarnedBadges, Stat, Stats } from '@/components/achievements';
import { Button, Card, SectionTitle } from '@/components/ui';
import { Colors, Fonts, Radius, Spacing } from '@/constants/theme';
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

// "Coming Up" shows this many until it's opened.
const UPCOMING_SHOWN = 5;

export function StudentDayView({
  data,
  saving,
  celebrate,
  onToggle,
  own = false,
}: {
  data: StudentDashboard;
  saving: number[];
  celebrate: Badge[];
  onToggle: (item: WorkItem) => void;
  // The student's own view, which greets them by name.
  own?: boolean;
}) {
  const [showMissed, setShowMissed] = useState(false);
  const [showCompleted, setShowCompleted] = useState(false);
  const [showProgress, setShowProgress] = useState(false);
  const [showToEarn, setShowToEarn] = useState(false);
  const [showAllUpcoming, setShowAllUpcoming] = useState(false);
  // New badges already closed, by key.
  const [seen, setSeen] = useState<string[]>([]);

  const { achievements, reading, pe } = data;
  const badges = [...achievements.badges, ...reading.badges, ...pe.badges];
  const toEarn = badges.filter((b) => !b.earned);
  const earnedCount = badges.length - toEarn.length;
  const upcoming = showAllUpcoming ? data.upcoming : data.upcoming.slice(0, UPCOMING_SHOWN);

  return (
    <>
      {data.banners.map((banner) => (
        <Card key={banner.id} style={styles.banner}>
          <Text style={styles.bannerTitle}>{banner.title}</Text>
          <Text style={styles.body}>{banner.message}</Text>
        </Card>
      ))}

      <DayHero data={data} own={own} />

      <NewBadgePopup
        badges={celebrate.filter((b) => !seen.includes(b.key))}
        onClose={() => setSeen([...seen, ...celebrate.map((b) => b.key)])}
      />

      {data.today_work.length + data.completed_today.length > 0 ? (
        <>
          <SectionTitle>Today&apos;s Work</SectionTitle>
          {data.today_work.map((item) => (
            <WorkRow key={item.occurrence_id} item={item} saving={saving} onToggle={onToggle} />
          ))}
          {data.completed_today.map((item) => (
            <WorkRow key={item.occurrence_id} item={item} saving={saving} onToggle={onToggle} />
          ))}
        </>
      ) : null}

      {data.overdue.length > 0 ? (
        <>
          <SectionTitle>Catch Up</SectionTitle>
          <Text style={styles.muted}>Work from earlier days that isn&apos;t finished yet.</Text>
          {data.overdue.map((item) => (
            <WorkRow key={item.occurrence_id} item={item} saving={saving} onToggle={onToggle} showDate />
          ))}
        </>
      ) : null}

      {data.upcoming.length > 0 ? (
        <>
          <SectionTitle>Coming Up</SectionTitle>
          {upcoming.map((item) => (
            <WorkRow key={item.occurrence_id} item={item} saving={saving} onToggle={onToggle} showDate />
          ))}
          {data.upcoming.length > UPCOMING_SHOWN ? (
            <Pressable
              accessibilityRole="button"
              onPress={() => setShowAllUpcoming(!showAllUpcoming)}
              style={styles.more}>
              <Text style={styles.moreText}>
                {showAllUpcoming ? 'Show less' : `Show all ${data.upcoming.length}`}
              </Text>
            </Pressable>
          ) : null}
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

      <SectionTitle>Streaks and Badges</SectionTitle>
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ expanded: showProgress }}
        accessibilityLabel={`Streak ${days(achievements.streak)}, reading streak ${days(
          reading.streak,
        )}, P.E. ${minutes(pe.minutes_this_week)} this week, ${earnedCount} of ${
          badges.length
        } badges. ${showProgress ? 'Hide' : 'Show'} details.`}
        onPress={() => setShowProgress(!showProgress)}
        style={({ pressed }) => [styles.pills, pressed && styles.pillsPressed]}>
        <Pill text={`🔥 ${days(achievements.streak)}`} />
        <Pill text={`📖 ${days(reading.streak)}`} />
        <Pill text={`🏃 ${minutes(pe.minutes_this_week)}`} />
        <Pill text={`🏅 ${earnedCount} of ${badges.length}`} />
        <Text style={styles.pillsToggle}>{showProgress ? 'Hide ▴' : 'Details ▾'}</Text>
      </Pressable>

      {showProgress ? (
        <>
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

          {earnedCount > 0 ? (
            <EarnedBadges badges={badges} />
          ) : (
            <Text style={styles.muted}>
              Finish your first piece of work to earn your first badge.
            </Text>
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

/**
 * The top of the day: who and when, the daily message, the streak, and
 * today's progress. Turns green once today's work is all done.
 */
function DayHero({ data, own }: { data: StudentDashboard; own: boolean }) {
  const { done, total } = data.progress;
  const allDone = total > 0 && done === total;
  const name = data.student.name;
  const streak = data.achievements.streak;

  const title = allDone
    ? own
      ? `All done, ${name}! 🎉`
      : 'All done for today! 🎉'
    : own
      ? `Hi, ${name}!`
      : `${name}'s Day`;

  const summary =
    total === 0
      ? 'Nothing due today.'
      : allDone
        ? `${total} of ${total} done. Great work!`
        : `${done} of ${total} done  ·  ${total - done} to go`;

  return (
    <View
      style={[styles.hero, allDone && styles.heroDone]}
      accessible
      accessibilityLabel={[
        title,
        formatDate(data.today),
        summary,
        streak > 0 ? `${days(streak)} streak` : null,
        data.message,
      ]
        .filter(Boolean)
        .join('. ')}>
      <View style={styles.heroTop}>
        <View style={styles.flex}>
          <Text style={styles.heroDate}>{formatDate(data.today)}</Text>
          <Text style={styles.heroTitle}>{title}</Text>
        </View>

        {streak > 0 ? (
          <View style={styles.streak}>
            <Text style={styles.streakNumber}>🔥 {streak}</Text>
            <Text style={styles.streakLabel}>day streak</Text>
          </View>
        ) : null}
      </View>

      <Text style={styles.heroMessage}>{data.message}</Text>

      {total > 0 ? <DayProgress done={done} total={total} allDone={allDone} /> : null}

      <Text style={styles.heroSummary}>{summary}</Text>
    </View>
  );
}

// Up to this many pieces of work show as blocks; more show as a bar.
const MAX_BLOCKS = 12;

/** One block per piece of work, filling as each is checked off. */
function DayProgress({ done, total, allDone }: { done: number; total: number; allDone: boolean }) {
  const filled = allDone ? styles.blockFilledDone : styles.blockFilled;

  if (total > MAX_BLOCKS) {
    return (
      <View style={styles.block}>
        <View style={[styles.barFill, filled, { width: `${(done / total) * 100}%` }]} />
      </View>
    );
  }

  return (
    <View style={styles.blocks}>
      {Array.from({ length: total }, (_, index) => (
        <View key={index} style={[styles.block, index < done && filled]} />
      ))}
    </View>
  );
}

function Pill({ text }: { text: string }) {
  return (
    <View style={styles.pill}>
      <Text style={styles.pillText}>{text}</Text>
    </View>
  );
}

/** Shows badges just earned over the screen until closed. */
function NewBadgePopup({ badges, onClose }: { badges: Badge[]; onClose: () => void }) {
  return (
    <Modal transparent animationType="fade" visible={badges.length > 0} onRequestClose={onClose}>
      <View style={styles.overlay}>
        <View style={styles.popup} accessibilityViewIsModal accessibilityLiveRegion="polite">
          <Text style={styles.popupKicker}>
            {badges.length === 1 ? 'New badge!' : `${badges.length} new badges!`}
          </Text>

          {badges.map((badge) => (
            <View key={badge.key} style={styles.popupBadge}>
              <Text style={styles.popupIcon}>{badge.icon}</Text>
              <Text style={styles.popupName}>{badge.name}</Text>
              <Text style={styles.popupDescription}>{badge.description}</Text>
            </View>
          ))}

          <Button title="Yay!" onPress={onClose} style={styles.popupButton} />
        </View>
      </View>
    </Modal>
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
        <Card
          style={[
            styles.workRow,
            { borderLeftColor: item.subject?.color ?? Colors.blueGrey },
            item.completed && styles.workRowDone,
            pressed && styles.pressed,
          ]}>
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
        </Card>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  flex: {
    flex: 1,
  },
  body: {
    color: Colors.text,
    fontSize: 15,
    fontFamily: Fonts.regular,
  },
  muted: {
    color: Colors.textMuted,
    fontSize: 14,
    fontFamily: Fonts.regular,
  },
  banner: {
    backgroundColor: Colors.surface,
  },
  bannerTitle: {
    color: Colors.navy,
    fontSize: 16,
    fontFamily: Fonts.bold,
  },
  // The top card.
  hero: {
    backgroundColor: Colors.navy,
    borderRadius: 16,
    padding: Spacing.lg,
    gap: Spacing.md,
  },
  heroDone: {
    backgroundColor: Colors.done,
  },
  heroTop: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Spacing.md,
  },
  heroDate: {
    color: 'rgba(255, 255, 255, 0.78)',
    fontSize: 14,
    fontFamily: Fonts.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  heroTitle: {
    color: '#FFFFFF',
    fontSize: 30,
    lineHeight: 36,
    fontFamily: Fonts.extrabold,
    letterSpacing: -0.6,
    marginTop: Spacing.xs,
  },
  heroMessage: {
    color: Colors.onNavy,
    fontSize: 16,
    lineHeight: 23,
    fontFamily: Fonts.regular,
    fontStyle: 'italic',
  },
  heroSummary: {
    color: '#FFFFFF',
    fontSize: 16,
    fontFamily: Fonts.semibold,
  },
  streak: {
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: 12,
    backgroundColor: 'rgba(255, 255, 255, 0.12)',
  },
  streakNumber: {
    color: '#FFFFFF',
    fontSize: 22,
    fontFamily: Fonts.extrabold,
  },
  streakLabel: {
    color: 'rgba(255, 255, 255, 0.78)',
    fontSize: 12,
    fontFamily: Fonts.semibold,
  },
  blocks: {
    flexDirection: 'row',
    gap: 6,
  },
  block: {
    flex: 1,
    height: 16,
    borderRadius: 8,
    backgroundColor: 'rgba(255, 255, 255, 0.18)',
    overflow: 'hidden',
  },
  blockFilled: {
    backgroundColor: Colors.orange,
  },
  blockFilledDone: {
    backgroundColor: '#FFFFFF',
  },
  barFill: {
    height: '100%',
  },
  // Streaks and badges, folded.
  pills: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: Spacing.sm,
    padding: Spacing.sm,
    borderRadius: Radius,
  },
  pillsPressed: {
    backgroundColor: Colors.surface,
  },
  pill: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: 20,
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  pillText: {
    color: Colors.navy,
    fontSize: 15,
    fontFamily: Fonts.bold,
  },
  pillsToggle: {
    color: Colors.orangeText,
    fontSize: 14,
    fontFamily: Fonts.semibold,
    marginLeft: Spacing.xs,
  },
  more: {
    alignSelf: 'flex-start',
    paddingVertical: Spacing.sm,
  },
  moreText: {
    color: Colors.orangeText,
    fontSize: 15,
    fontFamily: Fonts.semibold,
  },
  // The new badge pop-up.
  overlay: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: Spacing.lg,
    backgroundColor: 'rgba(27, 37, 64, 0.55)',
  },
  popup: {
    width: '100%',
    maxWidth: 360,
    alignItems: 'center',
    gap: Spacing.md,
    padding: Spacing.lg,
    borderRadius: 16,
    backgroundColor: Colors.background,
  },
  popupKicker: {
    color: Colors.orangeText,
    fontSize: 14,
    fontFamily: Fonts.bold,
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  popupBadge: {
    alignItems: 'center',
    gap: Spacing.xs,
  },
  popupIcon: {
    fontSize: 56,
    fontFamily: Fonts.regular,
  },
  popupName: {
    color: Colors.navy,
    fontSize: 22,
    fontFamily: Fonts.extrabold,
    textAlign: 'center',
  },
  popupDescription: {
    color: Colors.textMuted,
    fontSize: 15,
    fontFamily: Fonts.regular,
    textAlign: 'center',
  },
  popupButton: {
    alignSelf: 'stretch',
  },
  // A piece of work: the subject's colour down the left edge.
  workRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    minHeight: 68,
    paddingVertical: Spacing.md,
    borderLeftWidth: 6,
  },
  workRowDone: {
    backgroundColor: Colors.surface,
  },
  pressed: {
    backgroundColor: Colors.surface,
  },
  box: {
    width: 32,
    height: 32,
    borderRadius: 9,
    borderWidth: 2,
    borderColor: Colors.blueGrey,
    backgroundColor: Colors.background,
    alignItems: 'center',
    justifyContent: 'center',
  },
  boxChecked: {
    backgroundColor: Colors.done,
    borderColor: Colors.done,
  },
  check: {
    color: '#FFFFFF',
    fontSize: 20,
    fontFamily: Fonts.bold,
  },
  workText: {
    flex: 1,
    gap: 2,
  },
  title: {
    color: Colors.navy,
    fontSize: 17,
    fontFamily: Fonts.semibold,
  },
  titleDone: {
    color: Colors.textMuted,
    textDecorationLine: 'line-through',
  },
  note: {
    color: Colors.text,
    fontSize: 14,
    fontFamily: Fonts.regular,
    marginTop: Spacing.xs,
  },
});
