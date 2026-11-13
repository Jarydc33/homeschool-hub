import { useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { DateField } from '@/components/form';
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
import { addDays, parseDate } from '@/lib/dates';
import type { Banner } from '@/lib/types';

// How long a new announcement shows unless changed.
const DEFAULT_DAYS = 7;

/**
 * Announcements on the dashboards between two dates: a parent's for their
 * family, an Admin's for every family. Archiving takes one down for good.
 */
export default function AnnouncementsScreen() {
  const { me } = useAuth();
  const today = me?.today ?? null;
  const isAdmin = me?.role === 'admin';

  const [banners, setBanners] = useState<Banner[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // Only one card is open at a time: adding, or editing / archiving one.
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [archivingId, setArchivingId] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      setBanners(await api<Banner[]>('/announcements'));
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

  async function create(values: BannerValues) {
    const row = await api<Banner>('/announcements', { method: 'POST', body: values });
    closeAll();
    setNotice(`${row.title} added.`);
    await load();
  }

  async function update(id: number, values: BannerValues) {
    const row = await api<Banner>(`/announcements/${id}`, { method: 'PUT', body: values });
    closeAll();
    setNotice(`${row.title} updated.`);
    await load();
  }

  async function archive(row: Banner) {
    await api(`/announcements/${row.id}/archive`, { method: 'POST' });
    closeAll();
    setNotice(`${row.title} archived.`);
    await load();
  }

  return (
    <Screen refreshing={refreshing} onRefresh={refresh}>
      <PageTitle>📢 Announcements</PageTitle>

      <Text style={styles.body}>
        {isAdmin
          ? 'Messages for every family and student, on their dashboards between the dates you choose.'
          : "Messages on your family's dashboards, between the dates you choose."}
      </Text>

      {error ? <ErrorMessage message={error} onRetry={load} /> : null}

      {notice ? (
        <Text style={styles.notice} accessibilityLiveRegion="polite">
          ✓ {notice}
        </Text>
      ) : null}

      {!banners && !error ? <Loading /> : null}

      {banners && today ? (
        <>
          {adding ? (
            <Card>
              <Text style={styles.cardTitle}>New Announcement</Text>
              <BannerForm
                today={today}
                submitLabel="Add Announcement"
                onSave={create}
                onCancel={closeAll}
              />
            </Card>
          ) : (
            <Button
              title="+ Add Announcement"
              onPress={() => {
                closeAll();
                setAdding(true);
              }}
            />
          )}

          <SectionTitle>Current Announcements</SectionTitle>

          {banners.length === 0 ? (
            <Text style={styles.muted}>No announcements yet.</Text>
          ) : null}

          {banners.map((row) =>
            editingId === row.id ? (
              <Card key={row.id}>
                <Text style={styles.cardTitle}>Edit {row.title}</Text>
                <BannerForm
                  initial={row}
                  today={today}
                  submitLabel="Save Changes"
                  onSave={(values) => update(row.id, values)}
                  onCancel={closeAll}
                />
              </Card>
            ) : archivingId === row.id ? (
              <ConfirmCard
                key={row.id}
                title={`Archive ${row.title}?`}
                confirmLabel="Archive"
                onConfirm={() => archive(row)}
                onCancel={closeAll}>
                It will no longer show on {isAdmin ? 'anyone' : 'your family'}&apos;s dashboards.
              </ConfirmCard>
            ) : (
              <Card key={row.id}>
                <View style={styles.row}>
                  <Text style={[styles.cardTitle, styles.flex]}>📢 {row.title}</Text>
                  <Status row={row} today={today} />
                </View>
                <Text style={styles.muted}>{when(row)}</Text>
                <Text style={styles.body}>{row.message}</Text>
                <View style={styles.actions}>
                  <Button
                    title="Edit"
                    variant="secondary"
                    style={styles.action}
                    onPress={() => {
                      closeAll();
                      setEditingId(row.id);
                    }}
                  />
                  <Button
                    title="Archive"
                    variant="secondary"
                    style={styles.action}
                    onPress={() => {
                      closeAll();
                      setArchivingId(row.id);
                    }}
                  />
                </View>
              </Card>
            ),
          )}
        </>
      ) : null}
    </Screen>
  );
}

// "Nov 13, 2026 to Nov 20, 2026".
function when(row: Banner): string {
  const day = (value: string) =>
    parseDate(value).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });

  if (!row.start_date || !row.end_date) {
    return 'No dates set';
  }

  return row.start_date === row.end_date
    ? day(row.start_date)
    : `${day(row.start_date)} to ${day(row.end_date)}`;
}

/** Whether it's on the dashboards today, still to come, or over. */
function Status({ row, today }: { row: Banner; today: string }) {
  const [label, color] =
    row.start_date && row.start_date > today
      ? ['Scheduled', Colors.textMuted]
      : row.end_date && row.end_date < today
        ? ['Ended', Colors.textMuted]
        : ['Showing now', Colors.done];

  return <Text style={[styles.status, { color, borderColor: color }]}>{label}</Text>;
}

interface BannerValues {
  title: string;
  message: string;
  start_date: string;
  end_date: string;
}

function BannerForm({
  initial,
  today,
  submitLabel,
  onSave,
  onCancel,
}: {
  initial?: Banner;
  today: string;
  submitLabel: string;
  onSave: (values: BannerValues) => Promise<void>;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState(initial?.title ?? '');
  const [message, setMessage] = useState(initial?.message ?? '');
  const [start, setStart] = useState(initial?.start_date ?? today);
  const [end, setEnd] = useState(initial?.end_date ?? addDays(today, DEFAULT_DAYS - 1));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!title.trim()) {
      setError('Please enter a title.');
      return;
    }

    if (!message.trim()) {
      setError('Please enter a message.');
      return;
    }

    if (end < start) {
      setError('The end date must be on or after the start date.');
      return;
    }

    setBusy(true);
    setError(null);

    try {
      await onSave({
        title: title.trim(),
        message: message.trim(),
        start_date: start,
        end_date: end,
      });
    } catch (ex) {
      setError(errorMessage(ex));
      setBusy(false);
    }
  }

  return (
    <View style={styles.form}>
      <TextField label="Title" value={title} onChangeText={setTitle} maxLength={200} autoFocus />
      <TextField
        label="Message"
        value={message}
        onChangeText={setMessage}
        multiline
        maxLength={5000}
        style={styles.multiline}
      />
      <DateField label="Show From" value={start} onChange={setStart} today={today} />
      <DateField
        label="Show Until"
        hint="It shows through the end of this day."
        value={end}
        onChange={setEnd}
        today={today}
      />

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
  cardTitle: {
    color: Colors.navy,
    fontSize: 18,
    fontWeight: '700',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  status: {
    fontSize: 12,
    fontWeight: '700',
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
  },
  form: {
    gap: Spacing.md,
  },
  multiline: {
    minHeight: 96,
    paddingVertical: Spacing.sm,
    textAlignVertical: 'top',
  },
  actions: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  action: {
    flex: 1,
  },
});
