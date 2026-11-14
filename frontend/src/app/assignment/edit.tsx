import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import {
  ChoiceField,
  DateField,
  formatYear,
  MultiChoiceField,
  SwitchField,
  type Choice,
} from '@/components/form';
import { Button, Card, ErrorMessage, Loading, Screen, TextField } from '@/components/ui';
import { Colors, Spacing } from '@/constants/theme';
import { api, errorMessage } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { addDays, parseDate } from '@/lib/dates';
import type { Assignment, AssignmentType, Student, SubjectDetail } from '@/lib/types';

const FREQUENCIES = [
  'Every Day',
  'Weekdays',
  'Weekly',
  'Monthly',
  'Every Monday',
  'Every Tuesday',
  'Every Wednesday',
  'Every Thursday',
  'Every Friday',
];

// As the API saves them, in this order.
const SCHOOL_DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

// The API refuses schedules longer than this.
const MAX_SCHEDULE_DAYS = 731;

const TYPE_HINTS: Record<AssignmentType, string> = {
  'One Time': 'Due on one day.',
  Recurring: 'Repeats on a schedule, such as every weekday.',
  Curriculum: 'A set number of lessons, one per school day.',
};

/**
 * Creating an assignment, or editing one when opened with ?id=. Saving
 * creates or updates every date it happens on; students who stay keep their
 * check-offs, notes and grades. The Calendar opens a new one with ?date= (and
 * ?student= when it shows one student's schedule) to start on that day.
 */
export default function AssignmentEditScreen() {
  const { id, date, student } = useLocalSearchParams<{
    id?: string;
    date?: string;
    student?: string;
  }>();
  const { me } = useAuth();
  const today = me?.today ?? null;
  const startDate = date && /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : null;
  const startStudent = student ? Number(student) : null;

  const [subjects, setSubjects] = useState<Choice<number>[] | null>(null);
  const [students, setStudents] = useState<Student[] | null>(null);
  const [existing, setExisting] = useState<Assignment | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [subjectRows, studentRows, assignment] = await Promise.all([
          api<SubjectDetail[]>('/subjects'),
          api<Student[]>('/students'),
          id ? api<Assignment>(`/assignments/${id}`) : Promise.resolve(null),
        ]);

        const choices: Choice<number>[] = subjectRows.map((s) => ({
          value: s.id,
          label: s.name,
          color: s.color,
        }));

        // An assignment can stay in a subject that's since been archived.
        const current = assignment?.subject;

        if (current && !choices.some((c) => c.value === current.id)) {
          choices.unshift({
            value: current.id,
            label: `${current.name} (archived)`,
            color: current.color,
          });
        }

        setSubjects(choices);
        setStudents(studentRows);
        setExisting(assignment);
      } catch (ex) {
        setLoadError(errorMessage(ex));
      }
    }

    load();
  }, [id]);

  const ready = subjects && students && today && (!id || existing);

  return (
    <Screen>
      {loadError ? <ErrorMessage message={loadError} /> : null}

      {!ready && !loadError ? <Loading /> : null}

      {ready ? (
        <AssignmentForm
          today={today}
          subjects={subjects}
          students={students}
          existing={existing}
          startDate={startDate}
          startStudent={startStudent}
        />
      ) : null}
    </Screen>
  );
}

function AssignmentForm({
  today,
  subjects,
  students,
  existing,
  startDate,
  startStudent,
}: {
  today: string;
  subjects: Choice<number>[];
  students: Student[];
  existing: Assignment | null;
  // Where a new assignment starts: the day and student it was opened for.
  startDate: string | null;
  startStudent: number | null;
}) {
  const editing = existing !== null;
  const wasCurriculum = existing?.assignment_type === 'Curriculum';
  const firstDate = startDate ?? today;
  const defaultEnd = `${firstDate.slice(0, 4)}-12-31`;

  const [type, setType] = useState<AssignmentType>(existing?.assignment_type ?? 'One Time');
  const [title, setTitle] = useState(existing?.title ?? '');
  const [subjectId, setSubjectId] = useState<number | null>(
    existing?.subject?.id ?? (subjects.length === 1 ? subjects[0].value : null),
  );
  const [studentIds, setStudentIds] = useState<number[]>(
    existing
      ? existing.students.map((s) => s.id)
      : students.length === 1
        ? [students[0].id]
        : startStudent !== null && students.some((s) => s.id === startStudent)
          ? [startStudent]
          : [],
  );
  const [description, setDescription] = useState(existing?.description ?? '');
  const [dueDate, setDueDate] = useState(existing?.due_date ?? firstDate);
  const [endDate, setEndDate] = useState(existing?.end_date ?? defaultEnd);
  const [frequency, setFrequency] = useState(
    existing?.assignment_type === 'Recurring' && existing.recurrence_pattern
      ? existing.recurrence_pattern
      : 'Every Day',
  );
  const [schoolDays, setSchoolDays] = useState<string[]>(
    wasCurriculum && existing?.recurrence_pattern
      ? existing.recurrence_pattern.split(',')
      : SCHOOL_DAYS.slice(0, 5),
  );
  const [lessons, setLessons] = useState(existing?.lesson_count ? String(existing.lesson_count) : '');
  const [graded, setGraded] = useState(existing?.graded ?? false);

  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // A curriculum can't become other work, or the reverse.
  const typeChoices: AssignmentType[] = editing
    ? wasCurriculum
      ? ['Curriculum']
      : ['One Time', 'Recurring']
    : ['One Time', 'Recurring', 'Curriculum'];

  const lessonCount = /^\d+$/.test(lessons.trim()) ? Number(lessons.trim()) : null;
  const finish =
    type === 'Curriculum' && lessonCount && schoolDays.length > 0
      ? lastLessonDate(schoolDays, dueDate, lessonCount)
      : null;

  function check(): string | null {
    if (!title.trim()) {
      return 'Please enter a title.';
    }

    if (subjectId === null) {
      return subjects.length === 0
        ? 'Add a subject on the Subjects screen first.'
        : 'Please choose a subject.';
    }

    if (studentIds.length === 0) {
      return students.length === 0
        ? 'Add a student on the Students screen first.'
        : 'Please choose at least one student.';
    }

    if (type === 'Recurring' && endDate < dueDate) {
      return "The end date can't be before the start date.";
    }

    if (type === 'Curriculum') {
      if (!lessonCount || lessonCount < 1) {
        return 'Please enter how many lessons there are.';
      }

      if (schoolDays.length === 0) {
        return 'Please choose at least one school day.';
      }

      if (!finish) {
        return 'At this pace the lessons would run more than two years. Try more school days or fewer lessons.';
      }
    }

    return null;
  }

  async function save() {
    const problem = check();

    if (problem) {
      setError(problem);
      return;
    }

    const body = {
      title: title.trim(),
      subject_id: subjectId,
      student_ids: studentIds,
      description: description.trim() || null,
      assignment_type: type,
      recurrence_pattern:
        type === 'Recurring' ? frequency : type === 'Curriculum' ? schoolDays.join(',') : null,
      due_date: dueDate,
      end_date: type === 'Recurring' ? endDate : null,
      lesson_count: type === 'Curriculum' ? lessonCount : null,
      graded,
    };

    setBusy(true);
    setError(null);

    try {
      await api(editing ? `/assignments/${existing.id}` : '/assignments', {
        method: editing ? 'PUT' : 'POST',
        body,
      });

      close();
    } catch (ex) {
      setError(errorMessage(ex));
      setBusy(false);
    }
  }

  return (
    <View style={styles.form}>
      <Text style={styles.heading} accessibilityRole="header">
        {editing ? `Edit ${existing.title}` : 'New Assignment'}
      </Text>

      {typeChoices.length > 1 ? (
        <ChoiceField
          label="Type"
          hint={TYPE_HINTS[type]}
          options={typeChoices.map((t) => ({ value: t, label: t }))}
          value={type}
          onChange={setType}
        />
      ) : null}

      <TextField label="Title" value={title} onChangeText={setTitle} maxLength={200} />

      {subjects.length > 0 ? (
        <ChoiceField label="Subject" options={subjects} value={subjectId} onChange={setSubjectId} />
      ) : (
        <Text style={styles.warning}>Add a subject on the Subjects screen first.</Text>
      )}

      {students.length > 0 ? (
        <MultiChoiceField
          label="Assign To"
          options={students.map((s) => ({ value: s.id, label: s.name }))}
          value={studentIds}
          onChange={setStudentIds}
        />
      ) : (
        <Text style={styles.warning}>Add a student on the Students screen first.</Text>
      )}

      <TextField
        label="Description"
        hint="Optional. Students see this with the work."
        value={description}
        onChangeText={setDescription}
        multiline
        maxLength={5000}
        style={styles.multiline}
      />

      <Card style={styles.schedule}>
        <Text style={styles.subheading}>Schedule</Text>

        {type === 'Recurring' ? (
          <ChoiceField
            label="Frequency"
            options={FREQUENCIES.map((f) => ({ value: f, label: f }))}
            value={frequency}
            onChange={setFrequency}
          />
        ) : null}

        {type === 'Curriculum' ? (
          <>
            <TextField
              label="Number of Lessons"
              placeholder="For example, 120"
              value={lessons}
              onChangeText={setLessons}
              keyboardType="number-pad"
              inputMode="numeric"
              maxLength={4}
            />
            <MultiChoiceField
              label="School Days"
              options={SCHOOL_DAYS.map((d) => ({ value: d, label: d }))}
              value={schoolDays}
              onChange={setSchoolDays}
            />
          </>
        ) : null}

        <DateField
          label={type === 'One Time' ? 'Due Date' : 'Starts On'}
          value={dueDate}
          onChange={setDueDate}
          today={today}
        />

        {type === 'Recurring' ? (
          <DateField label="Ends On" value={endDate} onChange={setEndDate} today={today} />
        ) : null}

        {type === 'Curriculum' && finish && lessonCount ? (
          <Text style={styles.info}>
            Lesson {lessonCount} lands on {formatYear(finish)}.
          </Text>
        ) : null}

        {type === 'Curriculum' && editing ? (
          <Text style={styles.hint}>
            Changing the start date or school days gives every lesson that hasn&apos;t been
            started a new date, from today on.
          </Text>
        ) : null}
      </Card>

      <SwitchField
        label="Graded"
        hint="Its scores count towards grades on the Grades page."
        value={graded}
        onChange={setGraded}
      />

      {error ? <ErrorMessage message={error} /> : null}

      <View style={styles.actions}>
        <Button title="Cancel" variant="secondary" style={styles.action} onPress={close} />
        <Button
          title={editing ? 'Save Changes' : 'Create Assignment'}
          style={styles.action}
          busy={busy}
          onPress={save}
        />
      </View>
    </View>
  );
}

function close() {
  if (router.canGoBack()) {
    router.back();
  } else {
    router.replace('/assignments');
  }
}

/**
 * The date of the last lesson, one per school day from start on, or null if
 * that's more than the API allows. Mirrors OccurrenceService.lesson_dates.
 */
function lastLessonDate(schoolDays: string[], start: string, count: number): string | null {
  // JavaScript counts Sunday as 0; SCHOOL_DAYS starts on Monday.
  const weekdays = new Set(schoolDays.map((d) => (SCHOOL_DAYS.indexOf(d) + 1) % 7));

  if (weekdays.size === 0 || count > MAX_SCHEDULE_DAYS) {
    return null;
  }

  let day = start;
  let found = 0;

  for (let offset = 0; offset <= MAX_SCHEDULE_DAYS; offset++) {
    if (weekdays.has(parseDate(day).getDay())) {
      found++;

      if (found === count) {
        return day;
      }
    }

    day = addDays(day, 1);
  }

  return null;
}

const styles = StyleSheet.create({
  form: {
    gap: Spacing.lg,
  },
  heading: {
    color: Colors.navy,
    fontSize: 24,
    fontWeight: '700',
  },
  subheading: {
    color: Colors.navy,
    fontSize: 17,
    fontWeight: '700',
  },
  schedule: {
    gap: Spacing.md,
    backgroundColor: Colors.surface,
  },
  multiline: {
    minHeight: 96,
    paddingTop: Spacing.sm,
    textAlignVertical: 'top',
  },
  info: {
    color: Colors.navy,
    fontSize: 15,
    fontWeight: '600',
  },
  hint: {
    color: Colors.textMuted,
    fontSize: 13,
  },
  warning: {
    color: Colors.danger,
    fontSize: 15,
  },
  actions: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  action: {
    flex: 1,
  },
});
