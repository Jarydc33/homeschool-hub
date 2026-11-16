import { router, useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Stat, Stats } from '@/components/achievements';
import { ChoiceField, DateField } from '@/components/form';
import {
  Button,
  Card,
  ErrorMessage,
  Loading,
  PageTitle,
  Screen,
  SectionTitle,
  TextField,
} from '@/components/ui';
import { Colors, Fonts, Radius, Spacing } from '@/constants/theme';
import { api, errorMessage } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { addDays, formatDate, parseDate, toDateString } from '@/lib/dates';
import { formatHours, formatMinutes, parseMinutes } from '@/lib/hours';
import type { GradingPeriod, HoursDay, HoursReport, HoursWork, Student } from '@/lib/types';

// Stretches to pick from. Grading periods are added by their id (> 0).
const WEEK = -1;
const MONTH = -2;
const SCHOOL_YEAR = -3;
const CUSTOM = -4;

// Days shown in the log before "Show all".
const DAYS_SHOWN = 14;

/**
 * Hours: the time each student spent, from finished work's minutes and P.E.
 * logs, by subject and by day. Parents adjust a day's minutes here; students
 * see their own.
 */
export default function HoursScreen() {
  const { me } = useAuth();
  const today = me?.today ?? null;
  const isParent = me?.role === 'parent';

  const [students, setStudents] = useState<Student[] | null>(null);
  const [periods, setPeriods] = useState<GradingPeriod[]>([]);
  const [chosenStudent, setStudentId] = useState<number | null>(null);
  const [range, setRange] = useState<number>(SCHOOL_YEAR);
  const [customStart, setCustomStart] = useState<string | null>(null);
  const [customEnd, setCustomEnd] = useState<string | null>(null);

  const [report, setReport] = useState<HoursReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const latest = useRef(0);

  // Students see only their own.
  const studentId = isParent ? (chosenStudent ?? students?.[0]?.id ?? null) : (me?.student_id ?? null);
  const dates = today ? rangeDates(range, today, periods, customStart, customEnd) : null;

  useEffect(() => {
    Promise.all([
      isParent ? api<Student[]>('/students') : Promise.resolve([]),
      api<GradingPeriod[]>('/grading-periods'),
    ])
      .then(([studentRows, periodRows]) => {
        setStudents(studentRows);
        setPeriods(periodRows);
      })
      .catch((ex) => setError(errorMessage(ex)));
  }, [isParent]);

  const load = useCallback(async () => {
    if (studentId === null || !dates) {
      return;
    }

    const request = ++latest.current;

    try {
      const data = await api<HoursReport>(
        `/students/${studentId}/hours?start=${dates.start}&end=${dates.end}`,
      );

      if (request === latest.current) {
        setReport(data);
        setError(null);
      }
    } catch (ex) {
      if (request === latest.current) {
        setError(errorMessage(ex));
      }
    }
  }, [studentId, dates?.start, dates?.end]); // eslint-disable-line react-hooks/exhaustive-deps

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

  async function saveMinutes(work: HoursWork, minutes: number) {
    await api(`/occurrences/${work.occurrence_id}/minutes`, {
      method: 'PUT',
      body: { minutes },
    });
    await load();
  }

  if (isParent && students && students.length === 0) {
    return (
      <Screen>
        <PageTitle>⏱️ Hours</PageTitle>
        <Text style={styles.body}>Add a student on the Students screen first.</Text>
      </Screen>
    );
  }

  const rangeOptions = [
    { value: WEEK, label: 'This week' },
    { value: MONTH, label: 'This month' },
    { value: SCHOOL_YEAR, label: 'This school year' },
    ...periods.map((p) => ({ value: p.id, label: p.name })),
    { value: CUSTOM, label: 'Choose dates' },
  ];

  return (
    <Screen refreshing={refreshing} onRefresh={refresh}>
      <PageTitle>⏱️ Hours</PageTitle>

      {isParent && students && students.length > 1 ? (
        <ChoiceField
          label="Student"
          options={students.map((s) => ({ value: s.id, label: s.name }))}
          value={studentId}
          onChange={setStudentId}
        />
      ) : null}

      <ChoiceField
        label="Dates"
        options={rangeOptions}
        value={range}
        onChange={(value) => {
          setRange(value);
          if (value === CUSTOM && dates) {
            setCustomStart(dates.start);
            setCustomEnd(dates.end);
          }
        }}
      />

      {range === CUSTOM && dates && today ? (
        <View style={styles.dateRow}>
          <View style={styles.flex}>
            <DateField label="From" value={dates.start} onChange={setCustomStart} today={today} />
          </View>
          <View style={styles.flex}>
            <DateField
              label="To"
              value={dates.end}
              onChange={setCustomEnd}
              today={today}
              isEnabled={(day) => day >= dates.start}
            />
          </View>
        </View>
      ) : null}

      {dates ? (
        <Text style={styles.muted}>
          {formatDate(dates.start, true)} to {formatDate(dates.end, true)}
        </Text>
      ) : null}

      {error ? <ErrorMessage message={error} onRetry={load} /> : null}

      {!report && !error ? <Loading /> : null}

      {report ? <Report report={report} isParent={isParent} onSave={saveMinutes} /> : null}
    </Screen>
  );
}

/**
 * The first and last day of a stretch. The school year runs August to July;
 * a grading period uses its own dates.
 */
function rangeDates(
  range: number,
  today: string,
  periods: GradingPeriod[],
  customStart: string | null,
  customEnd: string | null,
): { start: string; end: string } {
  const now = parseDate(today);

  if (range === WEEK) {
    // Weeks start on Sunday, like the calendar.
    return { start: addDays(today, -now.getDay()), end: today };
  }

  if (range === MONTH) {
    return { start: toDateString(new Date(now.getFullYear(), now.getMonth(), 1)), end: today };
  }

  if (range === CUSTOM) {
    const start = customStart ?? today;
    const end = customEnd && customEnd >= start ? customEnd : start;
    return { start, end };
  }

  const period = periods.find((p) => p.id === range);

  if (period) {
    return { start: period.start_date, end: period.end_date };
  }

  // The school year: from August 1, this year's or last year's.
  const year = now.getMonth() >= 7 ? now.getFullYear() : now.getFullYear() - 1;

  return { start: toDateString(new Date(year, 7, 1)), end: today };
}

function Report({
  report,
  isParent,
  onSave,
}: {
  report: HoursReport;
  isParent: boolean;
  onSave: (work: HoursWork, minutes: number) => Promise<void>;
}) {
  const [showAllDays, setShowAllDays] = useState(false);

  const days = showAllDays ? report.days : report.days.slice(0, DAYS_SHOWN);
  const most = report.subjects[0]?.minutes ?? 0;
  const average = report.school_days > 0 ? report.total_minutes / report.school_days : 0;

  return (
    <>
      <Stats>
        <Stat label="Total hours" value={formatHours(report.total_minutes)} />
        <Stat label="Core hours" value={formatHours(report.core_minutes)} />
        <Stat label="School days" value={String(report.school_days)} />
        <Stat label="Average a school day" value={formatMinutes(Math.round(average))} />
      </Stats>

      {report.total_minutes === 0 ? (
        <Card>
          <Text style={styles.body}>No time counted for these dates yet.</Text>
          <Text style={styles.muted}>
            Give each subject its usual minutes a day on the Subjects screen. From then on, checking
            work off counts its time, and P.E. logs count too.
          </Text>
          {isParent ? (
            <Button
              title="Go to Subjects"
              variant="secondary"
              onPress={() => router.push('/subjects')}
            />
          ) : null}
        </Card>
      ) : (
        <>
          <SectionTitle>By Subject</SectionTitle>
          <Card style={styles.list}>
            {report.subjects.map((line, index) => (
              <View
                key={line.pe ? 'pe' : (line.subject?.id ?? 'none')}
                style={[styles.listRow, index > 0 && styles.divided]}
                accessible
                accessibilityLabel={`${line.name}${line.is_core ? ', core' : ''}: ${formatMinutes(
                  line.minutes,
                )}`}>
                <View style={styles.row}>
                  <Text style={[styles.title, styles.flex]}>
                    {line.pe ? '🏃 ' : ''}
                    {line.name}
                    {line.is_core ? <Text style={styles.core}>  Core</Text> : null}
                  </Text>
                  <Text style={styles.amount}>{formatMinutes(line.minutes)}</Text>
                </View>
                <View style={styles.track}>
                  <View
                    style={[
                      styles.fill,
                      {
                        width: `${(line.minutes / most) * 100}%`,
                        backgroundColor: line.subject?.color ?? Colors.orange,
                      },
                    ]}
                  />
                </View>
              </View>
            ))}
          </Card>

          <SectionTitle>Day by Day</SectionTitle>
          {isParent ? (
            <Text style={styles.muted}>
              Tap a time to change it, for a day that ran long or short.
            </Text>
          ) : null}

          {days.map((day) => (
            <DayCard key={day.date} day={day} isParent={isParent} onSave={onSave} />
          ))}

          {report.days.length > DAYS_SHOWN ? (
            <Pressable accessibilityRole="button" onPress={() => setShowAllDays(!showAllDays)}>
              <Text style={styles.more}>
                {showAllDays ? 'Show fewer days' : `Show all ${report.days.length} days`}
              </Text>
            </Pressable>
          ) : null}
        </>
      )}
    </>
  );
}

function DayCard({
  day,
  isParent,
  onSave,
}: {
  day: HoursDay;
  isParent: boolean;
  onSave: (work: HoursWork, minutes: number) => Promise<void>;
}) {
  return (
    <Card style={styles.list}>
      <View style={[styles.listRow, styles.row, styles.dayHead]}>
        <Text style={[styles.title, styles.flex]}>{formatDate(day.date)}</Text>
        <Text style={styles.amount}>{formatMinutes(day.minutes)}</Text>
      </View>

      {day.work.map((work) => (
        <WorkMinutes key={work.occurrence_id} work={work} isParent={isParent} onSave={onSave} />
      ))}

      {day.pe.map((entry, index) => (
        <View key={`pe-${index}`} style={[styles.listRow, styles.row, styles.divided]}>
          <View style={styles.flex}>
            <Text style={styles.body}>🏃 {entry.activity}</Text>
            <Text style={styles.muted}>P.E. log</Text>
          </View>
          <Text style={styles.body}>{formatMinutes(entry.minutes)}</Text>
        </View>
      ))}
    </Card>
  );
}

/** One piece of work's time; a parent can tap it to change it. */
function WorkMinutes({
  work,
  isParent,
  onSave,
}: {
  work: HoursWork;
  isParent: boolean;
  onSave: (work: HoursWork, minutes: number) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(String(work.minutes));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function save() {
    const parsed = parseMinutes(text, true);

    if ('error' in parsed || parsed.minutes === null) {
      setError('error' in parsed ? parsed.error : 'Please enter the minutes, or 0 for none.');
      return;
    }

    setBusy(true);
    setError(null);

    try {
      await onSave(work, parsed.minutes);
      setEditing(false);
    } catch (ex) {
      setError(errorMessage(ex));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={[styles.listRow, styles.divided, styles.workRow, workStripe(work)]}>
      <View style={styles.row}>
        <View style={styles.flex}>
          <Text style={styles.body}>{work.title}</Text>
          {work.subject ? <Text style={styles.muted}>{work.subject.name}</Text> : null}
        </View>

        {isParent && !editing ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`${work.title}: ${formatMinutes(work.minutes)}. Change time`}
            onPress={() => {
              setText(String(work.minutes));
              setEditing(true);
            }}
            style={({ pressed }) => [styles.timeButton, pressed && styles.pressed]}>
            <Text style={styles.timeText}>{formatMinutes(work.minutes)} ✎</Text>
          </Pressable>
        ) : null}

        {!isParent ? <Text style={styles.body}>{formatMinutes(work.minutes)}</Text> : null}
      </View>

      {editing ? (
        <View style={styles.editor}>
          <TextField
            label="Minutes"
            hint="0 counts it as no time."
            value={text}
            onChangeText={setText}
            keyboardType="number-pad"
            inputMode="numeric"
            maxLength={3}
            autoFocus
            onSubmitEditing={save}
          />
          {error ? <ErrorMessage message={error} /> : null}
          <View style={styles.actions}>
            <Button
              title="Cancel"
              variant="secondary"
              style={styles.flex}
              onPress={() => {
                setEditing(false);
                setError(null);
              }}
            />
            <Button title="Save" style={styles.flex} busy={busy} onPress={save} />
          </View>
        </View>
      ) : null}
    </View>
  );
}

function workStripe(work: HoursWork) {
  return { borderLeftColor: work.subject?.color ?? Colors.blueGrey };
}

const styles = StyleSheet.create({
  flex: {
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
  title: {
    color: Colors.navy,
    fontSize: 16,
    fontFamily: Fonts.semibold,
  },
  amount: {
    color: Colors.navy,
    fontSize: 16,
    fontFamily: Fonts.bold,
  },
  core: {
    color: Colors.orangeText,
    fontSize: 13,
    fontFamily: Fonts.bold,
  },
  more: {
    color: Colors.orangeText,
    fontSize: 15,
    fontFamily: Fonts.semibold,
    paddingVertical: Spacing.xs,
  },
  dateRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.md,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  list: {
    padding: 0,
    gap: 0,
    overflow: 'hidden',
  },
  listRow: {
    paddingVertical: Spacing.md - 4,
    paddingHorizontal: Spacing.md,
    gap: Spacing.xs,
  },
  divided: {
    borderTopWidth: 1,
    borderTopColor: Colors.border,
  },
  dayHead: {
    backgroundColor: Colors.surface,
  },
  workRow: {
    borderLeftWidth: 5,
  },
  track: {
    height: 8,
    borderRadius: 4,
    backgroundColor: Colors.surface,
    overflow: 'hidden',
  },
  fill: {
    height: '100%',
    borderRadius: 4,
  },
  timeButton: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
    borderRadius: Radius,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  pressed: {
    backgroundColor: Colors.surface,
  },
  timeText: {
    color: Colors.navy,
    fontSize: 15,
    fontFamily: Fonts.semibold,
  },
  editor: {
    gap: Spacing.sm,
    marginTop: Spacing.sm,
  },
  actions: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
});
