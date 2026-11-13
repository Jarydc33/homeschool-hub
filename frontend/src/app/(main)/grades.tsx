import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { ChoiceField, DateField } from '@/components/form';
import {
  Button,
  Card,
  ConfirmCard,
  ErrorMessage,
  Loading,
  PageTitle,
  Screen,
  SectionTitle,
  TextField,
} from '@/components/ui';
import { Colors, Spacing } from '@/constants/theme';
import { api, errorMessage } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { formatDate } from '@/lib/dates';
import type {
  Grade,
  GradeReport,
  GradingPeriod,
  GradingQueue,
  Student,
  WorkItem,
} from '@/lib/types';

// The API's DEFAULT_POINTS: the total suggested when nothing better is known.
const DEFAULT_POINTS = 100;

// 0 stands for all time in the period picker.
const ALL_TIME = 0;

/**
 * Grades: a student's grades by subject for a grading period or all time,
 * grading their finished work, and the family's grading periods. Percentages
 * and letters come from the API; a blank score never counts.
 */
export default function GradesScreen() {
  const { me } = useAuth();
  const today = me?.today ?? null;
  // Students see their own grades; grading and periods are a parent's job.
  const isParent = me?.role === 'parent';

  const [students, setStudents] = useState<Student[] | null>(null);
  const [periods, setPeriods] = useState<GradingPeriod[]>([]);
  const [chosenStudent, setStudentId] = useState<number | null>(null);
  const [periodId, setPeriodId] = useState<number>(ALL_TIME);

  const [report, setReport] = useState<GradeReport | null>(null);
  const [queue, setQueue] = useState<GradingQueue | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const [showUnfinished, setShowUnfinished] = useState(false);
  const [showGraded, setShowGraded] = useState(false);

  // Only the latest request's answer is shown, if the user switches quickly.
  const latest = useRef(0);

  // The first student until one is picked.
  const studentId = chosenStudent ?? students?.[0]?.id ?? null;

  useEffect(() => {
    api<Student[]>('/students')
      .then(setStudents)
      .catch((ex) => setError(errorMessage(ex)));
  }, []);

  const load = useCallback(async () => {
    if (studentId === null) {
      return;
    }

    const request = ++latest.current;
    const period = periodId === ALL_TIME ? '' : `?period_id=${periodId}`;

    try {
      const [periodRows, reportData, queueData] = await Promise.all([
        api<GradingPeriod[]>('/grading-periods'),
        api<GradeReport>(`/students/${studentId}/grades${period}`),
        isParent ? api<GradingQueue>(`/students/${studentId}/grading`) : Promise.resolve(null),
      ]);

      if (request === latest.current) {
        setPeriods(periodRows);
        setReport(reportData);
        setQueue(queueData);
        setError(null);
      }
    } catch (ex) {
      if (request === latest.current) {
        setError(errorMessage(ex));
      }
    }
  }, [studentId, periodId, isParent]);

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

  async function saveGrade(work: WorkItem, score: number, total: number) {
    await api(`/occurrences/${work.occurrence_id}/grade`, {
      method: 'PUT',
      body: { score, points_possible: total },
    });
    setNotice(`Grade saved for ${work.title}.`);
    await load();
  }

  async function clearGrade(work: WorkItem) {
    await api(`/occurrences/${work.occurrence_id}/grade`, { method: 'DELETE' });
    setNotice(`Grade removed from ${work.title}.`);
    await load();
  }

  // After a period changes, the one being shown may be gone.
  async function periodsChanged(message: string) {
    setNotice(message);
    setPeriodId(ALL_TIME);
    await load();
  }

  function suggested(work: WorkItem): number {
    return queue?.suggested_totals[String(work.assignment_id)] ?? DEFAULT_POINTS;
  }

  if (students && students.length === 0) {
    return (
      <Screen>
        <PageTitle>📊 Grades</PageTitle>
        <Text style={styles.body}>Add a student on the Students screen first.</Text>
      </Screen>
    );
  }

  const ready = report && (queue || !isParent) && today;

  return (
    <Screen refreshing={refreshing} onRefresh={refresh}>
      <PageTitle>📊 Grades</PageTitle>

      {students && students.length > 1 ? (
        <ChoiceField
          label="Student"
          options={students.map((s) => ({ value: s.id, label: s.name }))}
          value={studentId}
          onChange={setStudentId}
        />
      ) : null}

      {periods.length > 0 ? (
        <ChoiceField
          label="Period"
          options={[
            { value: ALL_TIME, label: 'All time' },
            ...periods.map((p) => ({ value: p.id, label: p.name })),
          ]}
          value={periodId}
          onChange={setPeriodId}
        />
      ) : null}

      {error ? <ErrorMessage message={error} onRetry={load} /> : null}

      {notice ? (
        <Text style={styles.notice} accessibilityLiveRegion="polite">
          ✓ {notice}
        </Text>
      ) : null}

      {!ready && !error ? <Loading /> : null}

      {ready ? (
        <>
          <ReportCard report={report} />

          <Comparison report={report} periods={periods} />

          {queue ? (
            <>
              <SectionTitle>📝 To Grade ({queue.finished.length})</SectionTitle>

              {queue.finished.length === 0 ? (
                <Text style={styles.muted}>
                  Nothing is waiting for a grade. Mark an assignment as Graded on the Assignments
                  screen to see its finished work here.
                </Text>
              ) : (
                <Text style={styles.muted}>
                  Finished work on graded assignments. For a plain percentage, use a total of 100.
                </Text>
              )}

              {queue.finished.map((work) => (
                <GradeRow
                  key={work.occurrence_id}
                  work={work}
                  total={suggested(work)}
                  onSave={saveGrade}
                />
              ))}

              {queue.unfinished.length > 0 ? (
                <>
                  <Toggle
                    open={showUnfinished}
                    onPress={() => setShowUnfinished(!showUnfinished)}
                    title={`Grade Work Not Checked Off (${queue.unfinished.length})`}
                  />
                  {showUnfinished ? (
                    <>
                      <Text style={styles.muted}>
                        Work from the last 30 days and the next 7, so you can grade something early.
                        Grading doesn&apos;t check it off, and blank scores never count.
                      </Text>
                      {queue.unfinished.map((work) => (
                        <GradeRow
                          key={work.occurrence_id}
                          work={work}
                          total={suggested(work)}
                          onSave={saveGrade}
                        />
                      ))}
                    </>
                  ) : null}
                </>
              ) : null}
            </>
          ) : null}

          {report.work.length > 0 ? (
            <>
              <Toggle
                open={showGraded}
                onPress={() => setShowGraded(!showGraded)}
                title={`Graded Work (${report.work.length})`}
              />
              {showGraded
                ? report.work.map((graded) =>
                    !isParent ? (
                      <Card key={graded.work.occurrence_id}>
                        <View style={styles.titleRow}>
                          <Text style={[styles.workTitle, styles.flex]}>{graded.work.title}</Text>
                          <Text style={styles.subjectGrade}>{describe(graded.grade)}</Text>
                        </View>
                        <Text style={styles.muted}>
                          {graded.work.subject?.name ?? 'No subject'} ·{' '}
                          {formatDate(graded.work.date, true)} · {graded.score} out of{' '}
                          {graded.points_possible}
                        </Text>
                      </Card>
                    ) : (
                      <GradeRow
                        // A new key after a save resets the boxes to the saved grade.
                        key={`${graded.work.occurrence_id}-${graded.score}-${graded.points_possible}`}
                        work={graded.work}
                        score={graded.score}
                        total={graded.points_possible}
                        grade={graded.grade}
                        onSave={saveGrade}
                        onClear={clearGrade}
                      />
                    ),
                  )
                : null}
            </>
          ) : null}

          {isParent ? (
            <GradingPeriods periods={periods} today={today} onChanged={periodsChanged} />
          ) : null}
        </>
      ) : null}
    </Screen>
  );
}

// "92% (A)", as the Streamlit app shows grades.
function describe(grade: Grade): string {
  return `${Math.round(grade.percent)}% (${grade.letter})`;
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

function ReportCard({ report }: { report: GradeReport }) {
  if (!report.overall) {
    return (
      <Card>
        <Text style={styles.body}>No grades here yet.</Text>
      </Card>
    );
  }

  return (
    <Card>
      <Text style={styles.muted}>
        Overall Grade{report.period ? `, ${report.period.name}` : ''}
      </Text>
      <Text style={styles.overall}>{describe(report.overall)}</Text>

      {report.subjects.map((row) => (
        <View key={row.subject} style={styles.subjectRow}>
          <Text style={[styles.body, styles.flex]}>{row.subject}</Text>
          <Text style={styles.subjectGrade}>{describe(row.grade)}</Text>
        </View>
      ))}
    </Card>
  );
}

/** Each subject's grade per period, side by side, when any period has grades. */
function Comparison({ report, periods }: { report: GradeReport; periods: GradingPeriod[] }) {
  const graded = new Set(report.overall_by_period.map((p) => p.period_id));
  const shown = periods.filter((p) => graded.has(p.id));

  if (shown.length === 0) {
    return null;
  }

  function cell(grades: { period_id: number; grade: Grade }[], periodId: number) {
    const found = grades.find((g) => g.period_id === periodId);

    return found ? describe(found.grade) : '–';
  }

  return (
    <>
      <SectionTitle>Compare Periods</SectionTitle>
      <ScrollView horizontal>
        <View style={styles.table}>
          <View style={styles.tableRow}>
            <Text style={[styles.tableHead, styles.firstColumn]}>Subject</Text>
            {shown.map((p) => (
              <Text key={p.id} style={[styles.tableHead, styles.column]}>
                {p.name}
              </Text>
            ))}
          </View>
          {report.comparison.map((row) => (
            <View key={row.subject} style={styles.tableRow}>
              <Text style={[styles.tableCell, styles.firstColumn]}>{row.subject}</Text>
              {shown.map((p) => (
                <Text key={p.id} style={[styles.tableCell, styles.column]}>
                  {cell(row.periods, p.id)}
                </Text>
              ))}
            </View>
          ))}
          <View style={styles.tableRow}>
            <Text style={[styles.tableHead, styles.firstColumn]}>Overall</Text>
            {shown.map((p) => (
              <Text key={p.id} style={[styles.tableHead, styles.column]}>
                {cell(report.overall_by_period, p.id)}
              </Text>
            ))}
          </View>
        </View>
      </ScrollView>
    </>
  );
}

/** One piece of work with boxes to grade it, or change or clear its grade. */
function GradeRow({
  work,
  score,
  total,
  grade,
  onSave,
  onClear,
}: {
  work: WorkItem;
  score?: number;
  total: number;
  grade?: Grade;
  onSave: (work: WorkItem, score: number, total: number) => Promise<void>;
  onClear?: (work: WorkItem) => Promise<void>;
}) {
  const [scoreText, setScoreText] = useState(score === undefined ? '' : String(score));
  const [totalText, setTotalText] = useState(String(total));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<'save' | 'clear' | null>(null);

  async function save() {
    const earned = parseNumber(scoreText);
    const outOf = parseNumber(totalText);

    if (earned === null || outOf === null) {
      setError('Please enter the points earned and the total, as numbers.');
      return;
    }

    setBusy('save');
    setError(null);

    try {
      await onSave(work, earned, outOf);
    } catch (ex) {
      setError(errorMessage(ex));
    } finally {
      setBusy(null);
    }
  }

  async function clear() {
    if (!onClear) {
      return;
    }

    setBusy('clear');
    setError(null);

    try {
      await onClear(work);
    } catch (ex) {
      setError(errorMessage(ex));
      setBusy(null);
    }
  }

  return (
    <Card>
      <View style={styles.titleRow}>
        <Text style={[styles.workTitle, styles.flex]}>{work.title}</Text>
        {grade ? <Text style={styles.subjectGrade}>{describe(grade)}</Text> : null}
      </View>
      <Text style={styles.muted}>
        {work.subject?.name ?? 'No subject'} · {formatDate(work.date, true)} ·{' '}
        {work.completed ? '✅ Completed' : '⬜ Not completed'}
      </Text>

      <View style={styles.boxes}>
        <View style={styles.flex}>
          <TextField
            label="Points Earned"
            value={scoreText}
            onChangeText={setScoreText}
            keyboardType="decimal-pad"
            inputMode="decimal"
            maxLength={7}
          />
        </View>
        <View style={styles.flex}>
          <TextField
            label="Out Of"
            value={totalText}
            onChangeText={setTotalText}
            keyboardType="decimal-pad"
            inputMode="decimal"
            maxLength={7}
            returnKeyType="done"
            onSubmitEditing={save}
          />
        </View>
      </View>

      {error ? <ErrorMessage message={error} /> : null}

      <View style={styles.actions}>
        {onClear ? (
          <Button
            title="Clear Grade"
            variant="secondary"
            style={styles.action}
            busy={busy === 'clear'}
            disabled={busy !== null}
            onPress={clear}
          />
        ) : null}
        <Button
          title="Save Grade"
          style={styles.action}
          busy={busy === 'save'}
          disabled={busy !== null}
          onPress={save}
        />
      </View>
    </Card>
  );
}

// "92.5" as 92.5; anything that isn't a plain number as null.
function parseNumber(text: string): number | null {
  const trimmed = text.trim();

  return /^\d+(\.\d+)?$|^\.\d+$/.test(trimmed) ? Number(trimmed) : null;
}

/** The family's grading periods: add, edit and archive. */
function GradingPeriods({
  periods,
  today,
  onChanged,
}: {
  periods: GradingPeriod[];
  today: string;
  onChanged: (message: string) => Promise<void>;
}) {
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [archivingId, setArchivingId] = useState<number | null>(null);

  function closeAll() {
    setAdding(false);
    setEditingId(null);
    setArchivingId(null);
  }

  async function create(values: PeriodValues) {
    const period = await api<GradingPeriod>('/grading-periods', {
      method: 'POST',
      body: values,
    });
    closeAll();
    await onChanged(`${period.name} added.`);
  }

  async function update(id: number, values: PeriodValues) {
    const period = await api<GradingPeriod>(`/grading-periods/${id}`, {
      method: 'PUT',
      body: values,
    });
    closeAll();
    await onChanged(`${period.name} updated.`);
  }

  async function archive(period: GradingPeriod) {
    await api(`/grading-periods/${period.id}/archive`, { method: 'POST' });
    closeAll();
    await onChanged(`${period.name} archived.`);
  }

  return (
    <>
      <SectionTitle>🗓️ Grading Periods</SectionTitle>
      <Text style={styles.muted}>
        Periods are optional. Name them whatever fits your school year, like Fall 2026. Each grade
        belongs to the period covering its date, and changing a period&apos;s dates moves its
        grades.
      </Text>

      {periods.map((period) =>
        editingId === period.id ? (
          <Card key={period.id}>
            <Text style={styles.workTitle}>Edit {period.name}</Text>
            <PeriodForm
              initial={period}
              today={today}
              submitLabel="Save Changes"
              onSave={(values) => update(period.id, values)}
              onCancel={closeAll}
            />
          </Card>
        ) : archivingId === period.id ? (
          <ConfirmCard
            key={period.id}
            title={`Archive ${period.name}?`}
            confirmLabel="Archive"
            onConfirm={() => archive(period)}
            onCancel={closeAll}>
            It will no longer be offered or compared. Grades aren&apos;t changed.
          </ConfirmCard>
        ) : (
          <Card key={period.id}>
            <Text style={styles.workTitle}>{period.name}</Text>
            <Text style={styles.muted}>
              {formatDate(period.start_date, true)}, {period.start_date.slice(0, 4)} to{' '}
              {formatDate(period.end_date, true)}, {period.end_date.slice(0, 4)}
            </Text>
            <View style={styles.actions}>
              <Button
                title="Edit"
                variant="secondary"
                style={styles.action}
                onPress={() => {
                  closeAll();
                  setEditingId(period.id);
                }}
              />
              <Button
                title="Archive"
                variant="secondary"
                style={styles.action}
                onPress={() => {
                  closeAll();
                  setArchivingId(period.id);
                }}
              />
            </View>
          </Card>
        ),
      )}

      {adding ? (
        <Card>
          <Text style={styles.workTitle}>Add a Grading Period</Text>
          <PeriodForm today={today} submitLabel="Add Period" onSave={create} onCancel={closeAll} />
        </Card>
      ) : (
        <Button
          title="+ Add Grading Period"
          variant="secondary"
          onPress={() => {
            closeAll();
            setAdding(true);
          }}
        />
      )}
    </>
  );
}

interface PeriodValues {
  name: string;
  start_date: string;
  end_date: string;
}

function PeriodForm({
  initial,
  today,
  submitLabel,
  onSave,
  onCancel,
}: {
  initial?: GradingPeriod;
  today: string;
  submitLabel: string;
  onSave: (values: PeriodValues) => Promise<void>;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? '');
  const [start, setStart] = useState(initial?.start_date ?? today);
  const [end, setEnd] = useState(initial?.end_date ?? today);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!name.trim()) {
      setError("Please enter the period's name.");
      return;
    }

    if (end < start) {
      setError("The end date can't be before the start date.");
      return;
    }

    setBusy(true);
    setError(null);

    try {
      await onSave({ name: name.trim(), start_date: start, end_date: end });
    } catch (ex) {
      setError(errorMessage(ex));
      setBusy(false);
    }
  }

  return (
    <View style={styles.form}>
      <TextField
        label="Name"
        placeholder="For example, Fall 2026"
        value={name}
        onChangeText={setName}
        maxLength={100}
        autoFocus
      />
      <DateField label="Start Date" value={start} onChange={setStart} today={today} />
      <DateField label="End Date" value={end} onChange={setEnd} today={today} />

      {error ? <ErrorMessage message={error} /> : null}

      <View style={styles.actions}>
        <Button title="Cancel" variant="secondary" style={styles.action} onPress={onCancel} />
        <Button title={submitLabel} style={styles.action} busy={busy} onPress={submit} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: {
    flex: 1,
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
  overall: {
    color: Colors.navy,
    fontSize: 32,
    fontWeight: '700',
  },
  subjectRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    paddingVertical: Spacing.xs,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
  },
  subjectGrade: {
    color: Colors.navy,
    fontSize: 16,
    fontWeight: '700',
  },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Spacing.md,
  },
  workTitle: {
    color: Colors.navy,
    fontSize: 17,
    fontWeight: '700',
  },
  boxes: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  actions: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  action: {
    flex: 1,
  },
  form: {
    gap: Spacing.md,
  },
  table: {
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: 8,
  },
  tableRow: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  tableHead: {
    color: Colors.navy,
    fontSize: 14,
    fontWeight: '700',
    padding: Spacing.sm,
  },
  tableCell: {
    color: Colors.text,
    fontSize: 14,
    padding: Spacing.sm,
  },
  firstColumn: {
    width: 140,
  },
  column: {
    width: 110,
    textAlign: 'center',
  },
});
