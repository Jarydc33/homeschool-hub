import { Link, Redirect } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Button, Card, ErrorMessage, Loading, Screen, SectionTitle } from '@/components/ui';
import { Colors, Spacing } from '@/constants/theme';
import { api, ApiError } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import type { Student } from '@/lib/types';

/**
 * Home. A student goes straight to their own day; a parent picks a student.
 */
export default function HomeScreen() {
  const { me, error, reloadMe, signOut } = useAuth();

  if (error) {
    return (
      <Screen>
        <ErrorMessage message={error} onRetry={reloadMe} />
        <Button title="Log Out" variant="secondary" onPress={signOut} />
      </Screen>
    );
  }

  if (!me) {
    return <Loading />;
  }

  if (me.role === 'student' && me.student_id !== null) {
    return <Redirect href={{ pathname: '/student/[id]', params: { id: String(me.student_id) } }} />;
  }

  if (me.role === 'admin') {
    return (
      <Screen>
        <Text style={styles.body}>
          Announcements are still managed in the current Tally app for now.
        </Text>
        <Button title="Log Out" variant="secondary" onPress={signOut} />
      </Screen>
    );
  }

  return <ParentHome familyName={me.family_name} onSignOut={signOut} />;
}

function ParentHome({
  familyName,
  onSignOut,
}: {
  familyName: string | null;
  onSignOut: () => void;
}) {
  const [students, setStudents] = useState<Student[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const list = await api<Student[]>('/students');
      setStudents(list);
      setError(null);
    } catch (ex) {
      setError(ex instanceof ApiError ? ex.message : 'Something went wrong.');
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- loads data when this opens; state changes only after the API answers.
    load();
  }, [load]);

  return (
    <Screen>
      <Text style={styles.heading} accessibilityRole="header">
        {familyName ? `Welcome, ${familyName}` : 'Welcome'}
      </Text>

      <SectionTitle>Students</SectionTitle>

      {error ? <ErrorMessage message={error} onRetry={load} /> : null}

      {students === null && !error ? <Loading /> : null}

      {students?.length === 0 ? (
        <Text style={styles.body}>
          No students yet. Add them in the current Tally app for now.
        </Text>
      ) : null}

      {students?.map((student) => (
        <Link
          key={student.id}
          href={{ pathname: '/student/[id]', params: { id: String(student.id) } }}
          asChild>
          <Pressable accessibilityRole="link">
            {({ pressed }) => (
              <Card style={pressed && styles.pressed}>
                <View style={styles.row}>
                  <Text style={styles.name}>{student.name}</Text>
                  <Text style={styles.chevron}>{'›'}</Text>
                </View>
                {student.grade_level ? (
                  <Text style={styles.muted}>Grade {student.grade_level}</Text>
                ) : null}
              </Card>
            )}
          </Pressable>
        </Link>
      ))}

      <Button title="Log Out" variant="secondary" onPress={onSignOut} style={styles.logout} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  heading: {
    color: Colors.navy,
    fontSize: 24,
    fontWeight: '700',
  },
  body: {
    color: Colors.text,
    fontSize: 16,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  name: {
    color: Colors.navy,
    fontSize: 18,
    fontWeight: '600',
  },
  chevron: {
    color: Colors.textMuted,
    fontSize: 24,
  },
  muted: {
    color: Colors.textMuted,
    fontSize: 14,
  },
  pressed: {
    backgroundColor: Colors.surface,
  },
  logout: {
    marginTop: Spacing.lg,
  },
});
