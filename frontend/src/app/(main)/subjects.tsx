import { useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
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
import type { SubjectDetail } from '@/lib/types';

// Colours to pick from. The first is the one the API uses when none is set.
const SUBJECT_COLORS = [
  '#2196F3',
  '#3949AB',
  '#8E24AA',
  '#D81B60',
  '#E53935',
  '#E2672F',
  '#F9A825',
  '#43A047',
  '#00897B',
  '#6D4C41',
  '#546E7A',
];

/**
 * Subjects: add, edit, archive and restore. Archiving hides a subject from
 * new work; its assignments and grades stay as they are.
 */
export default function SubjectsScreen() {
  const [subjects, setSubjects] = useState<SubjectDetail[] | null>(null);
  const [archived, setArchived] = useState<SubjectDetail[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // Only one card is open at a time: adding, or editing / archiving one subject.
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [archivingId, setArchivingId] = useState<number | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [restoringId, setRestoringId] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const [active, old] = await Promise.all([
        api<SubjectDetail[]>('/subjects'),
        api<SubjectDetail[]>('/subjects/archived'),
      ]);
      setSubjects(active);
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
    setNotice(null);
  }

  async function create(values: SubjectValues) {
    const subject = await api<SubjectDetail>('/subjects', { method: 'POST', body: values });
    closeAll();
    setNotice(`${subject.name} added.`);
    await load();
  }

  async function update(id: number, values: SubjectValues) {
    const subject = await api<SubjectDetail>(`/subjects/${id}`, { method: 'PUT', body: values });
    closeAll();
    setNotice(`${subject.name} updated.`);
    await load();
  }

  async function archive(subject: SubjectDetail) {
    await api(`/subjects/${subject.id}/archive`, { method: 'POST' });
    closeAll();
    setNotice(`${subject.name} archived. You can restore it below.`);
    await load();
  }

  async function restore(subject: SubjectDetail) {
    setRestoringId(subject.id);
    try {
      await api(`/subjects/${subject.id}/restore`, { method: 'POST' });
      setNotice(`${subject.name} restored.`);
      await load();
    } catch (ex) {
      setError(errorMessage(ex));
    } finally {
      setRestoringId(null);
    }
  }

  return (
    <Screen refreshing={refreshing} onRefresh={refresh}>
      <PageTitle>📚 Subjects</PageTitle>

      {error ? <ErrorMessage message={error} onRetry={load} /> : null}

      {notice ? (
        <Text style={styles.notice} accessibilityLiveRegion="polite">
          ✓ {notice}
        </Text>
      ) : null}

      {!subjects && !error ? <Loading /> : null}

      {subjects ? (
        <>
          {adding ? (
            <Card>
              <Text style={styles.cardTitle}>Add a Subject</Text>
              <SubjectForm submitLabel="Add Subject" onSave={create} onCancel={closeAll} />
            </Card>
          ) : (
            <Button
              title="+ Add Subject"
              onPress={() => {
                closeAll();
                setAdding(true);
              }}
            />
          )}

          {subjects.length === 0 ? (
            <Text style={styles.body}>No subjects yet. Add your first one above.</Text>
          ) : null}

          {subjects.map((subject) =>
            editingId === subject.id ? (
              <Card key={subject.id}>
                <Text style={styles.cardTitle}>Edit {subject.name}</Text>
                <SubjectForm
                  initial={subject}
                  submitLabel="Save Changes"
                  onSave={(values) => update(subject.id, values)}
                  onCancel={closeAll}
                />
              </Card>
            ) : archivingId === subject.id ? (
              <ConfirmCard
                key={subject.id}
                title={`Archive ${subject.name}?`}
                confirmLabel="Archive"
                onConfirm={() => archive(subject)}
                onCancel={closeAll}>
                It won&apos;t be offered for new assignments. Its assignments and grades stay as
                they are, and you can restore it at any time.
              </ConfirmCard>
            ) : (
              <Card key={subject.id}>
                <View style={styles.row}>
                  <View
                    style={[styles.swatch, { backgroundColor: subject.color ?? SUBJECT_COLORS[0] }]}
                  />
                  <View style={styles.flex}>
                    <Text style={styles.name}>{subject.name}</Text>
                    <Text style={styles.muted}>
                      {subject.assignment_count === 1
                        ? '1 assignment'
                        : `${subject.assignment_count} assignments`}
                    </Text>
                  </View>
                </View>
                <View style={styles.actions}>
                  <Button
                    title="Edit"
                    variant="secondary"
                    style={styles.action}
                    onPress={() => {
                      closeAll();
                      setEditingId(subject.id);
                    }}
                  />
                  <Button
                    title="Archive"
                    variant="secondary"
                    style={styles.action}
                    onPress={() => {
                      closeAll();
                      setArchivingId(subject.id);
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
                  {showArchived ? '▾' : '▸'} Archived Subjects ({archived.length})
                </SectionTitle>
              </Pressable>

              {showArchived ? (
                <>
                  <Text style={styles.muted}>
                    Restoring a subject lets you choose it for new work again. Its assignments
                    and grades were never removed.
                  </Text>
                  {archived.map((subject) => (
                    <Card key={subject.id}>
                      <View style={styles.row}>
                        <Text style={[styles.body, styles.flex]}>{subject.name}</Text>
                        <Button
                          title="Restore"
                          variant="secondary"
                          busy={restoringId === subject.id}
                          onPress={() => restore(subject)}
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

interface SubjectValues {
  name: string;
  color: string;
}

function SubjectForm({
  initial,
  submitLabel,
  onSave,
  onCancel,
}: {
  initial?: SubjectDetail;
  submitLabel: string;
  onSave: (values: SubjectValues) => Promise<void>;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? '');
  const [color, setColor] = useState(initial?.color ?? SUBJECT_COLORS[0]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Keep a color picked in the old app selectable, even if it isn't one of ours.
  const choices = SUBJECT_COLORS.includes(color) ? SUBJECT_COLORS : [color, ...SUBJECT_COLORS];

  async function submit() {
    const trimmed = name.trim();

    if (!trimmed) {
      setError("Please enter the subject's name.");
      return;
    }

    setBusy(true);
    setError(null);

    try {
      await onSave({ name: trimmed, color });
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
        returnKeyType="done"
        onSubmitEditing={submit}
      />

      <View style={styles.field}>
        <Text style={styles.label}>Color</Text>
        <View style={styles.swatches} accessibilityRole="radiogroup">
          {choices.map((choice, index) => (
            <Pressable
              key={choice}
              accessibilityRole="radio"
              accessibilityLabel={`Color ${index + 1}`}
              accessibilityState={{ checked: choice === color }}
              onPress={() => setColor(choice)}
              style={[
                styles.choice,
                { backgroundColor: choice },
                choice === color && styles.choiceSelected,
              ]}>
              {choice === color ? <Text style={styles.check}>✓</Text> : null}
            </Pressable>
          ))}
        </View>
      </View>

      {error ? <ErrorMessage message={error} /> : null}

      <View style={styles.actions}>
        <Button title="Cancel" variant="secondary" style={styles.action} onPress={onCancel} />
        <Button title={submitLabel} style={styles.action} busy={busy} onPress={submit} />
      </View>
    </View>
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
    gap: Spacing.md,
  },
  flex: {
    flex: 1,
  },
  swatch: {
    width: 16,
    height: 40,
    borderRadius: 8,
  },
  form: {
    gap: Spacing.md,
  },
  field: {
    gap: Spacing.sm,
  },
  label: {
    color: Colors.navy,
    fontSize: 15,
    fontWeight: '600',
  },
  swatches: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
  },
  choice: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
  },
  choiceSelected: {
    borderWidth: 3,
    borderColor: Colors.navy,
  },
  check: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '700',
  },
  actions: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  action: {
    flex: 1,
  },
});
