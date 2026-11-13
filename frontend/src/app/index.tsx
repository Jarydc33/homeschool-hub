import { Redirect } from 'expo-router';

import { Button, ErrorMessage, Loading, Screen } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { homeFor } from '@/lib/nav';

/**
 * Home sends everyone to their start: a student to their Today, a parent
 * to the dashboard, an Admin to the announcements.
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

  return <Redirect href={homeFor(me.role) as never} />;
}
