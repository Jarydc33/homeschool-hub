import { Stack, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { StudentDayView, useStudentDay } from '@/components/student-day';
import { ErrorMessage, Loading } from '@/components/ui';
import { Colors, MaxContentWidth, Spacing } from '@/constants/theme';

/**
 * A parent's look at one student's day, opened from the Dashboard. Checking
 * work off here counts the same as the student doing it.
 */
export default function StudentDayScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { data, error, saving, celebrate, load, toggle } = useStudentDay(id);
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
    <SafeAreaView style={styles.screen} edges={['left', 'right']}>
      <Stack.Screen options={{ title: data ? data.student.name : 'Today' }} />

      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}>
        <View style={styles.content}>
          {error ? <ErrorMessage message={error} onRetry={load} /> : null}

          {!data && !error ? <Loading /> : null}

          {data ? (
            <StudentDayView data={data} saving={saving} celebrate={celebrate} onToggle={toggle} />
          ) : null}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  scroll: {
    flexGrow: 1,
  },
  content: {
    width: '100%',
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
    padding: Spacing.md,
    gap: Spacing.sm,
  },
});
