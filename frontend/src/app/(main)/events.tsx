import { router, useFocusEffect } from 'expo-router';
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
} from '@/components/ui';
import { Colors, Spacing } from '@/constants/theme';
import { api, errorMessage } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { formatDate } from '@/lib/dates';
import type { Event, EventList } from '@/lib/types';

/**
 * Events: field trips, co-op days, appointments. Upcoming ones show their
 * next date; a repeating event's edit or archive applies to every date.
 * Students see their own and the family's, without changing them.
 */
export default function EventsScreen() {
  const { me } = useAuth();
  const isParent = me?.role === 'parent';
  const [events, setEvents] = useState<EventList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [archivingId, setArchivingId] = useState<number | null>(null);
  const [showPast, setShowPast] = useState(false);

  const load = useCallback(async () => {
    try {
      setEvents(await api<EventList>('/events'));
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

  async function archive(event: Event) {
    await api(`/events/${event.id}/archive`, { method: 'POST' });
    setArchivingId(null);
    setNotice(`${event.title} archived.`);
    await load();
  }

  function open(id?: number) {
    setNotice(null);
    setArchivingId(null);
    router.push(id ? { pathname: '/event/edit', params: { id: String(id) } } : '/event/edit');
  }

  function renderEvent(event: Event, when: string | null, key: string) {
    if (archivingId === event.id) {
      return (
        <ConfirmCard
          key={key}
          title={`Archive ${event.title}?`}
          confirmLabel="Archive"
          onConfirm={() => archive(event)}
          onCancel={() => setArchivingId(null)}>
          It will no longer show for anyone.
          {event.recurrence_pattern ? " Since it repeats, that's every date." : ''}
        </ConfirmCard>
      );
    }

    return (
      <Card key={key}>
        <Text style={styles.name}>🎉 {event.title}</Text>
        <Text style={styles.detail}>📅 {when ?? pastWhen(event)}</Text>
        {event.recurrence_pattern && event.repeat_until ? (
          <Text style={styles.detail}>
            🔁 {event.recurrence_pattern}, until {formatDate(event.repeat_until, true)}
          </Text>
        ) : null}
        <Text style={styles.detail}>👨‍🎓 {event.audience}</Text>
        {event.description ? <Text style={styles.body}>{event.description}</Text> : null}

        {isParent ? (
          <View style={styles.actions}>
            <Button
              title="Edit"
              variant="secondary"
              style={styles.action}
              onPress={() => open(event.id)}
            />
            <Button
              title="Archive"
              variant="secondary"
              style={styles.action}
              onPress={() => {
                setNotice(null);
                setArchivingId(event.id);
              }}
            />
          </View>
        ) : null}
      </Card>
    );
  }

  return (
    <Screen refreshing={refreshing} onRefresh={refresh}>
      <PageTitle>📅 Events</PageTitle>

      {error ? <ErrorMessage message={error} onRetry={load} /> : null}

      {notice ? (
        <Text style={styles.notice} accessibilityLiveRegion="polite">
          ✓ {notice}
        </Text>
      ) : null}

      {!events && !error ? <Loading /> : null}

      {events ? (
        <>
          {isParent ? <Button title="+ Add Event" onPress={() => open()} /> : null}

          <SectionTitle>Upcoming</SectionTitle>

          {events.upcoming.length === 0 ? (
            <Text style={styles.body}>No upcoming events.</Text>
          ) : null}

          {events.upcoming.map((entry) =>
            renderEvent(entry.event, entry.when, `${entry.event.id}-${entry.date}`),
          )}

          {events.past.length > 0 ? (
            <>
              <Pressable
                accessibilityRole="button"
                accessibilityState={{ expanded: showPast }}
                onPress={() => setShowPast(!showPast)}>
                <SectionTitle>
                  {showPast ? '▾' : '▸'} Past Events ({events.past.length})
                </SectionTitle>
              </Pressable>

              {showPast
                ? events.past.map((event) => renderEvent(event, null, `past-${event.id}`))
                : null}
            </>
          ) : null}
        </>
      ) : null}
    </Screen>
  );
}

// A past event's dates: "Tue, Nov 10", or "Mon, Nov 9 to Fri, Nov 13".
function pastWhen(event: Event): string {
  const start = formatDate(event.start_date, true);
  const end = event.repeat_until ?? event.end_date;

  return end && end !== event.start_date ? `${start} to ${formatDate(end, true)}` : start;
}

const styles = StyleSheet.create({
  body: {
    color: Colors.text,
    fontSize: 16,
  },
  detail: {
    color: Colors.textMuted,
    fontSize: 14,
  },
  notice: {
    color: Colors.done,
    fontSize: 16,
    fontWeight: '600',
  },
  name: {
    color: Colors.navy,
    fontSize: 18,
    fontWeight: '700',
  },
  actions: {
    flexDirection: 'row',
    gap: Spacing.sm,
    marginTop: Spacing.xs,
  },
  action: {
    flex: 1,
  },
});
