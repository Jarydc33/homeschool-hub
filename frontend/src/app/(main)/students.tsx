import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
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
  TextField,
} from '@/components/ui';
import { Colors, Spacing } from '@/constants/theme';
import { api, errorMessage } from '@/lib/api';
import type { Student } from '@/lib/types';

/**
 * Students: add, edit, archive and restore. Archiving hides a student and
 * blocks their login and devices; their work and grades are kept.
 */
export default function StudentsScreen() {
  const [students, setStudents] = useState<Student[] | null>(null);
  const [archived, setArchived] = useState<Student[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // Only one card is open at a time: adding, or editing / archiving / the
  // login of one student.
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [loginId, setLoginId] = useState<number | null>(null);
  const [archivingId, setArchivingId] = useState<number | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [restoringId, setRestoringId] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const [active, old] = await Promise.all([
        api<Student[]>('/students'),
        api<Student[]>('/students/archived'),
      ]);
      setStudents(active);
      setArchived(old);
      setError(null);
    } catch (ex) {
      setError(errorMessage(ex));
    }
  }, []);

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

  function closeAll() {
    setAdding(false);
    setEditingId(null);
    setArchivingId(null);
    setLoginId(null);
  }

  async function create(values: StudentValues) {
    const student = await api<Student>('/students', { method: 'POST', body: values });
    closeAll();
    setNotice(`${student.name} added.`);
    await load();
  }

  async function update(id: number, values: StudentValues) {
    const student = await api<Student>(`/students/${id}`, { method: 'PUT', body: values });
    closeAll();
    setNotice(`${student.name} updated.`);
    await load();
  }

  async function archive(student: Student) {
    await api(`/students/${student.id}/archive`, { method: 'POST' });
    closeAll();
    setNotice(`${student.name} archived. You can restore them below.`);
    await load();
  }

  async function restore(student: Student) {
    setRestoringId(student.id);
    try {
      await api(`/students/${student.id}/restore`, { method: 'POST' });
      setNotice(`${student.name} restored.`);
      await load();
    } catch (ex) {
      setError(errorMessage(ex));
    } finally {
      setRestoringId(null);
    }
  }

  return (
    <Screen refreshing={refreshing} onRefresh={refresh}>
      <PageTitle>👨‍🎓 Students</PageTitle>

      {error ? <ErrorMessage message={error} onRetry={load} /> : null}

      {notice ? (
        <Text style={styles.notice} accessibilityLiveRegion="polite">
          ✓ {notice}
        </Text>
      ) : null}

      {!students && !error ? <Loading /> : null}

      {students ? (
        <>
          {adding ? (
            <Card>
              <Text style={styles.cardTitle}>Add a Student</Text>
              <StudentForm submitLabel="Add Student" onSave={create} onCancel={closeAll} />
            </Card>
          ) : (
            <Button
              title="+ Add Student"
              onPress={() => {
                closeAll();
                setNotice(null);
                setAdding(true);
              }}
            />
          )}

          {students.length === 0 ? (
            <Text style={styles.body}>No students yet. Add your first one above.</Text>
          ) : null}

          {students.map((student) =>
            editingId === student.id ? (
              <Card key={student.id}>
                <Text style={styles.cardTitle}>Edit {student.name}</Text>
                <StudentForm
                  initial={student}
                  submitLabel="Save Changes"
                  onSave={(values) => update(student.id, values)}
                  onCancel={closeAll}
                />
              </Card>
            ) : loginId === student.id ? (
              <LoginCard
                key={student.id}
                student={student}
                onDone={(message) => {
                  closeAll();
                  setNotice(message);
                }}
                onCancel={closeAll}
              />
            ) : archivingId === student.id ? (
              <ConfirmCard
                key={student.id}
                title={`Archive ${student.name}?`}
                confirmLabel="Archive"
                onConfirm={() => archive(student)}
                onCancel={closeAll}>
                They&apos;ll be hidden from lists and won&apos;t be able to log in, and any paired
                devices stop working. Their work and grades are kept, and you can restore them at
                any time.
              </ConfirmCard>
            ) : (
              <Card key={student.id}>
                <View style={styles.row}>
                  <View style={styles.flex}>
                    <Text style={styles.name}>{student.name}</Text>
                    <Text style={styles.muted}>{describe(student)}</Text>
                  </View>
                </View>
                <View style={styles.actions}>
                  <Button
                    title="Edit"
                    variant="secondary"
                    style={styles.action}
                    onPress={() => {
                      closeAll();
                      setNotice(null);
                      setEditingId(student.id);
                    }}
                  />
                  <Button
                    title="Login"
                    variant="secondary"
                    style={styles.action}
                    onPress={() => {
                      closeAll();
                      setNotice(null);
                      setLoginId(student.id);
                    }}
                  />
                  <Button
                    title="Archive"
                    variant="secondary"
                    style={styles.action}
                    onPress={() => {
                      closeAll();
                      setNotice(null);
                      setArchivingId(student.id);
                    }}
                  />
                </View>
              </Card>
            ),
          )}

          {archived.length > 0 ? (
            <>
              <Pressable
                accessibilityRole="button"
                accessibilityState={{ expanded: showArchived }}
                onPress={() => setShowArchived(!showArchived)}>
                <SectionTitle>
                  {showArchived ? '▾' : '▸'} Archived Students ({archived.length})
                </SectionTitle>
              </Pressable>

              {showArchived ? (
                <>
                  <Text style={styles.muted}>
                    Restoring a student brings back their assignments, progress and login.
                  </Text>
                  {archived.map((student) => (
                    <Card key={student.id}>
                      <View style={styles.row}>
                        <Text style={[styles.body, styles.flex]}>{student.name}</Text>
                        <Button
                          title="Restore"
                          variant="secondary"
                          busy={restoringId === student.id}
                          onPress={() => restore(student)}
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

interface StudentValues {
  name: string;
  grade_level: string;
  birth_year?: number;
}

function StudentForm({
  initial,
  submitLabel,
  onSave,
  onCancel,
}: {
  initial?: Student;
  submitLabel: string;
  onSave: (values: StudentValues) => Promise<void>;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? '');
  const [grade, setGrade] = useState(initial?.grade_level ?? '');
  const [birthYear, setBirthYear] = useState(
    initial?.birth_year ? String(initial.birth_year) : '',
  );
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    const trimmed = name.trim();

    if (!trimmed) {
      setError("Please enter the student's name.");
      return;
    }

    const values: StudentValues = { name: trimmed, grade_level: grade.trim() };
    const year = birthYear.trim();

    if (year) {
      const number = Number(year);

      if (!/^\d{4}$/.test(year) || number < 1990 || number > 2100) {
        setError('Please enter the birth year as four digits, like 2015.');
        return;
      }

      values.birth_year = number;
    }

    setBusy(true);
    setError(null);

    try {
      await onSave(values);
    } catch (ex) {
      setError(errorMessage(ex));
      setBusy(false);
    }
  }

  return (
    <View style={styles.form}>
      <TextField
        label="Name"
        value={name}
        onChangeText={setName}
        autoCapitalize="words"
        maxLength={100}
        autoFocus
      />
      <TextField
        label="Grade Level"
        hint="Optional, e.g. 3rd or Kindergarten"
        value={grade}
        onChangeText={setGrade}
        maxLength={50}
      />
      <TextField
        label="Birth Year"
        hint="Optional"
        value={birthYear}
        onChangeText={setBirthYear}
        keyboardType="number-pad"
        inputMode="numeric"
        maxLength={4}
        returnKeyType="done"
        onSubmitEditing={submit}
      />

      {error ? <ErrorMessage message={error} /> : null}

      <View style={styles.actions}>
        <Button title="Cancel" variant="secondary" style={styles.action} onPress={onCancel} />
        <Button title={submitLabel} style={styles.action} busy={busy} onPress={submit} />
      </View>
    </View>
  );
}

function describe(student: Student): string {
  const parts = [
    student.grade_level ? `Grade: ${student.grade_level}` : 'No grade level',
    student.birth_year ? `Born ${student.birth_year}` : null,
  ];

  return parts.filter(Boolean).join('  ·  ');
}

/**
 * A student's own login: invite them by email, or change the email they sign
 * in with. Students can also use a paired device or Student Mode instead.
 */
function LoginCard({
  student,
  onDone,
  onCancel,
}: {
  student: Student;
  onDone: (message: string) => void;
  onCancel: () => void;
}) {
  // undefined while loading; null when they have no login yet.
  const [current, setCurrent] = useState<string | null | undefined>(undefined);
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<{ email: string | null }>(`/students/${student.id}/login`)
      .then((login) => {
        setCurrent(login.email);
        setEmail(login.email ?? '');
      })
      .catch((ex) => setError(errorMessage(ex)));
  }, [student.id]);

  const inviting = current === null;

  async function submit() {
    if (!email.trim()) {
      setError('Please enter an email address.');
      return;
    }

    setBusy(true);
    setError(null);

    try {
      const result = await api<{ message: string }>(`/students/${student.id}/login`, {
        method: inviting ? 'POST' : 'PUT',
        body: { email: email.trim() },
      });
      onDone(result.message);
    } catch (ex) {
      setError(errorMessage(ex));
      setBusy(false);
    }
  }

  return (
    <Card>
      <Text style={styles.cardTitle}>🔐 {student.name}&apos;s Login</Text>

      {current === undefined && !error ? <Loading /> : null}

      {current !== undefined ? (
        <View style={styles.form}>
          {inviting ? (
            <Text style={styles.body}>
              {student.name} doesn&apos;t have a login yet. We&apos;ll email them an invitation to
              set a password. A paired device or Student Mode works without one.
            </Text>
          ) : (
            <>
              <Text style={styles.body}>Signs in as {current}.</Text>
              <Text style={styles.muted}>
                To change it: if they&apos;ve already set a password, it stays the same. If they
                haven&apos;t, we&apos;ll send a new invitation to the new email, and the old one
                stops working.
              </Text>
            </>
          )}

          <TextField
            label={inviting ? 'Student Email' : 'New Email'}
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            inputMode="email"
            autoCapitalize="none"
            autoCorrect={false}
            autoComplete="off"
            maxLength={254}
            returnKeyType="done"
            onSubmitEditing={submit}
          />
        </View>
      ) : null}

      {error ? <ErrorMessage message={error} /> : null}

      <View style={styles.actions}>
        <Button title="Cancel" variant="secondary" style={styles.action} onPress={onCancel} />
        {current !== undefined ? (
          <Button
            title={inviting ? 'Send Invitation' : 'Save Email'}
            style={styles.action}
            busy={busy}
            disabled={!inviting && email.trim().toLowerCase() === current?.toLowerCase()}
            onPress={submit}
          />
        ) : null}
      </View>
    </Card>
  );
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
  notice: {
    color: Colors.done,
    fontSize: 16,
    fontWeight: '600',
  },
  cardTitle: {
    color: Colors.navy,
    fontSize: 18,
    fontWeight: '700',
  },
  name: {
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
  form: {
    gap: Spacing.md,
  },
  actions: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  action: {
    flex: 1,
  },
});
