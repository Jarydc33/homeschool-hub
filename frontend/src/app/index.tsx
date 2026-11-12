import { Redirect } from 'expo-router';
import { StyleSheet, Text } from 'react-native';

import { Button, ErrorMessage, Loading, Screen } from '@/components/ui';
import { Colors } from '@/constants/theme';
import { useAuth } from '@/lib/auth';

/**
 * Home sends everyone to their start: a student to their own day, a parent
 * to the dashboard.
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

  return <Redirect href="/dashboard" />;
}

const styles = StyleSheet.create({
  body: {
    color: Colors.text,
    fontSize: 16,
  },
});
