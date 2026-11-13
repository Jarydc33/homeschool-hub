import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ChoiceField, type Choice } from '@/components/form';
import { Button, Card, ErrorMessage, Loading, PageTitle, Screen } from '@/components/ui';
import { Colors, Radius, Spacing } from '@/constants/theme';
import { api, errorMessage } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { formatDate, monthWeeks, parseDate, shiftDate, weekDays } from '@/lib/dates';
import type { CalendarDay, CalendarItem, CalendarStatus, Student } from '@/lib/types';

const STATUS: Record<CalendarStatus, { icon: string; label: string; color: string }> = {
  event: { icon: '🎉', label: 'Event', color: '#8E24AA' },
  to_do: { icon: '📋', label: 'To do', color: '#2196F3' },
  done: { icon: '✅', label: 'Done', color: Colors.done },
  overdue: { icon: '⚠️', label: 'Overdue', color: Colors.danger },
  missed: { icon: '🕓', label: 'Missed', color: Colors.textMuted },
};

const LEGEND: CalendarStatus[] = ['event', 'to_do', 'done', 'overdue', 'missed'];

// How many dots a month's day shows before "+3".
const MONTH_DAY_DOTS = 3;

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

type CalendarView = 'week' | 'month';

// 0 stands for the whole family in the student picker.
const WHOLE_FAMILY = 0;

/**
 * The family's schedule by week or month: assignments with their status, and
 * events. A parent can narrow it to one student.
 */
export default function CalendarScreen() {
  const { me } = useAuth();
  const today = me?.today ?? null;

  const [view, setView] = useState<CalendarView>('week');
  const [studentId, setStudentId] = useState<number>(WHOLE_FAMILY);
  const [students, setStudents] = useState<Student[]>([]);
  // The date the calendar is showing (its week or month), and the day picked
  // in the month view, whose items are listed below it. Both start as today.
  const [shownChoice, setShown] = useState<string | null>(null);
  const [pickedChoice, setPicked] = useState<string | null>(null);
  const shown = shownChoice ?? today;
  const picked = pickedChoice ?? today;

  const [items, setItems] = useState<Record<string, CalendarItem[]> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // Only the latest request's answer is shown, if the user taps ahead quickly.
  const latest = useRef(0);

  useEffect(() => {
    api<Student[]>('/students')
      .then(setStudents)
      .catch(() => setStudents([]));
  }, []);

  const weeks = shown ? (view === 'month' ? monthWeeks(shown) : [weekDays(shown)]) : [];
  const first = shown ? firstDay(view, shown) : null;
  const last = shown ? lastDay(view, shown) : null;

  const load = useCallback(async () => {
    if (!first || !last) {
      return;
    }

    const request = ++latest.current;
    const who = studentId === WHOLE_FAMILY ? '' : `&student_id=${studentId}`;

    try {
      const days = await api<CalendarDay[]>(
        `/calendar?first=${first}&last=${last}${who}`,
      );

      if (request === latest.current) {
        setItems(Object.fromEntries(days.map((day) => [day.date, day.items])));
        setError(null);
      }
    } catch (ex) {
      if (request === latest.current) {
        setError(errorMessage(ex));
      }
    }
  }, [first, last, studentId]);

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

  function move(step: number) {
    if (!shown) {
      return;
    }

    const next = shiftDate(shown, view === 'month', step);
    setShown(next);
    setPicked(view === 'month' ? next : picked);
  }

  function goToToday() {
    setShown(null);
    setPicked(null);
  }

  // Keep the same place: a month opens with the week's day picked, and a
  // week opens on the month's picked day.
  function changeView(next: CalendarView) {
    if (next === 'week') {
      setShown(picked);
    } else {
      setPicked(shown);
    }

    setView(next);
  }

  const showStudent = studentId === WHOLE_FAMILY;

  const studentChoices: Choice<number>[] = [
    { value: WHOLE_FAMILY, label: 'Whole family' },
    ...students.map((student) => ({ value: student.id, label: student.name })),
  ];

  const title = shown
    ? view === 'month'
      ? parseDate(shown).toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
      : weekTitle(first!, last!)
    : '';

  return (
    <Screen refreshing={refreshing} onRefresh={refresh}>
      <PageTitle>📆 Calendar</PageTitle>

      <ChoiceField
        label="View"
        options={[
          { value: 'week', label: 'Week' },
          { value: 'month', label: 'Month' },
        ]}
        value={view}
        onChange={changeView}
      />

      {students.length > 1 ? (
        <ChoiceField
          label="Whose schedule?"
          options={studentChoices}
          value={studentId}
          onChange={setStudentId}
        />
      ) : null}

      <View style={styles.nav}>
        <Button
          title={view === 'month' ? '‹ Previous month' : '‹ Previous week'}
          variant="secondary"
          style={styles.navButton}
          onPress={() => move(-1)}
        />
        <Button title="Today" variant="secondary" onPress={goToToday} />
        <Button
          title={view === 'month' ? 'Next month ›' : 'Next week ›'}
          variant="secondary"
          style={styles.navButton}
          onPress={() => move(1)}
        />
      </View>

      <Text style={styles.title} accessibilityRole="header" accessibilityLiveRegion="polite">
        {title}
      </Text>

      <View style={styles.legend}>
        {LEGEND.map((status) => (
          <Text key={status} style={styles.legendItem}>
            {STATUS[status].icon} {STATUS[status].label}
          </Text>
        ))}
      </View>

      {error ? <ErrorMessage message={error} onRetry={load} /> : null}

      {!items && !error ? <Loading /> : null}

      {items && view === 'week'
        ? weeks[0].map((day) => (
            <DayCard
              key={day}
              day={day}
              today={today}
              items={items[day] ?? []}
              showStudent={showStudent}
            />
          ))
        : null}

      {items && view === 'month' && shown ? (
        <>
          <MonthGrid
            weeks={weeks}
            month={parseDate(shown).getMonth()}
            today={today}
            picked={picked}
            items={items}
            onPick={setPicked}
          />
          {picked && picked >= first! && picked <= last! ? (
            <DayCard
              day={picked}
              today={today}
              items={items[picked] ?? []}
              showStudent={showStudent}
            />
          ) : null}
        </>
      ) : null}

      {items && view === 'month' && Object.keys(items).length === 0 ? (
        <Text style={styles.muted}>Nothing is scheduled here.</Text>
      ) : null}
    </Screen>
  );
}

// The first and last dates the view shows, to ask the API for.
function firstDay(view: CalendarView, day: string): string {
  return view === 'month' ? monthWeeks(day)[0][0] : weekDays(day)[0];
}

function lastDay(view: CalendarView, day: string): string {
  return view === 'month' ? monthWeeks(day).at(-1)![6] : weekDays(day)[6];
}

// "Nov 8 to Nov 14, 2026".
function weekTitle(first: string, last: string): string {
  const short = (day: string) =>
    parseDate(day).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });

  return `${short(first)} to ${short(last)}, ${parseDate(last).getFullYear()}`;
}

function DayCard({
  day,
  today,
  items,
  showStudent,
}: {
  day: string;
  today: string | null;
  items: CalendarItem[];
  showStudent: boolean;
}) {
  const isToday = day === today;

  return (
    <Card style={isToday ? styles.todayCard : undefined}>
      <Text style={[styles.dayTitle, isToday && styles.todayText]} accessibilityRole="header">
        {formatDate(day)}
        {isToday ? ' (Today)' : ''}
      </Text>

      {items.length === 0 ? <Text style={styles.muted}>Nothing scheduled.</Text> : null}

      {items.map((item, index) => (
        <View
          key={index}
          style={styles.item}
          accessible
          accessibilityLabel={`${STATUS[item.status].label}: ${item.title}${
            showStudent && item.student ? `, ${item.student}` : ''
          }${item.detail ? `. ${item.detail}` : ''}`}>
          <Text style={styles.itemIcon}>{STATUS[item.status].icon}</Text>
          <View style={styles.flex}>
            <Text style={[styles.itemTitle, item.status === 'done' && styles.doneText]}>
              {item.title}
              {showStudent && item.student ? (
                <Text style={styles.student}> ({item.student})</Text>
              ) : null}
            </Text>
            {item.detail ? <Text style={styles.muted}>{item.detail}</Text> : null}
          </View>
        </View>
      ))}
    </Card>
  );
}

function MonthGrid({
  weeks,
  month,
  today,
  picked,
  items,
  onPick,
}: {
  weeks: string[][];
  month: number;
  today: string | null;
  picked: string | null;
  items: Record<string, CalendarItem[]>;
  onPick: (day: string) => void;
}) {
  return (
    <View style={styles.grid}>
      <View style={styles.week}>
        {WEEKDAYS.map((name) => (
          <Text key={name} style={styles.weekday}>
            {name}
          </Text>
        ))}
      </View>

      {weeks.map((week) => (
        <View key={week[0]} style={styles.week}>
          {week.map((day) => {
            const dayItems = items[day] ?? [];
            const outside = parseDate(day).getMonth() !== month;
            const selected = day === picked;
            const hidden = dayItems.length - MONTH_DAY_DOTS;

            return (
              <Pressable
                key={day}
                accessibilityRole="button"
                accessibilityLabel={`${formatDate(day)}${day === today ? ', today' : ''}: ${
                  dayItems.length === 0
                    ? 'nothing scheduled'
                    : dayItems.length === 1
                      ? '1 item'
                      : `${dayItems.length} items`
                }`}
                accessibilityState={{ selected }}
                onPress={() => onPick(day)}
                style={({ pressed }) => [
                  styles.cell,
                  day === today && styles.todayCell,
                  selected && styles.pickedCell,
                  pressed && styles.dim,
                ]}>
                <Text
                  style={[
                    styles.cellNumber,
                    outside && styles.outside,
                    day === today && styles.todayText,
                  ]}>
                  {parseDate(day).getDate()}
                </Text>
                <View style={styles.dots}>
                  {dayItems.slice(0, MONTH_DAY_DOTS).map((item, index) => (
                    <View
                      key={index}
                      style={[styles.dot, { backgroundColor: STATUS[item.status].color }]}
                    />
                  ))}
                </View>
                {hidden > 0 ? <Text style={styles.more}>+{hidden}</Text> : null}
              </Pressable>
            );
          })}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  flex: {
    flex: 1,
  },
  dim: {
    opacity: 0.7,
  },
  muted: {
    color: Colors.textMuted,
    fontSize: 14,
  },
  nav: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  navButton: {
    flex: 1,
    paddingHorizontal: Spacing.sm,
  },
  title: {
    color: Colors.navy,
    fontSize: 20,
    fontWeight: '700',
  },
  legend: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    columnGap: Spacing.md,
    rowGap: Spacing.xs,
  },
  legendItem: {
    color: Colors.textMuted,
    fontSize: 13,
  },
  todayCard: {
    borderColor: Colors.orange,
    borderWidth: 2,
  },
  dayTitle: {
    color: Colors.navy,
    fontSize: 16,
    fontWeight: '700',
  },
  todayText: {
    color: Colors.orangeText,
  },
  item: {
    flexDirection: 'row',
    gap: Spacing.sm,
    alignItems: 'flex-start',
  },
  itemIcon: {
    fontSize: 16,
    lineHeight: 22,
  },
  itemTitle: {
    color: Colors.text,
    fontSize: 16,
    lineHeight: 22,
  },
  doneText: {
    color: Colors.textMuted,
  },
  student: {
    color: Colors.textMuted,
  },
  grid: {
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius,
    padding: Spacing.xs,
    gap: 2,
  },
  week: {
    flexDirection: 'row',
    gap: 2,
  },
  weekday: {
    flex: 1,
    textAlign: 'center',
    color: Colors.textMuted,
    fontSize: 12,
    fontWeight: '600',
    paddingVertical: Spacing.xs,
  },
  cell: {
    flex: 1,
    minHeight: 56,
    alignItems: 'center',
    paddingVertical: Spacing.xs,
    borderRadius: 8,
    gap: 3,
  },
  todayCell: {
    borderWidth: 1,
    borderColor: Colors.orange,
  },
  pickedCell: {
    backgroundColor: Colors.surface,
  },
  cellNumber: {
    color: Colors.text,
    fontSize: 15,
    fontWeight: '600',
  },
  outside: {
    color: Colors.blueGrey,
  },
  dots: {
    flexDirection: 'row',
    gap: 3,
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },
  more: {
    color: Colors.textMuted,
    fontSize: 11,
  },
});
