import { useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';

import { StudentDayView, useStudentDay } from '@/components/student-day';
import { ErrorMessage, Loading, PageTitle, Screen } from '@/components/ui';
import { useAuth } from '@/lib/auth';

/**
 * A student's own day: their login, Student Mode, or a paired device.
 * Parents see a student's day from the Dashboard instead.
 */
export default function TodayScreen() {
  const { me } = useAuth();
  const { data, error, saving, celebrate, load, toggle } = useStudentDay(me?.student_id ?? null);
  const [refreshing, setRefreshing] = useState(false);

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

  return (
    <Screen refreshing={refreshing} onRefresh={refresh}>
      <PageTitle>{data ? `Hi, ${data.student.name}!` : 'Today'}</PageTitle>

      {error ? <ErrorMessage message={error} onRetry={load} /> : null}

      {!data && !error ? <Loading /> : null}

      {data ? (
        <StudentDayView data={data} saving={saving} celebrate={celebrate} onToggle={toggle} />
      ) : null}
    </Screen>
  );
}
