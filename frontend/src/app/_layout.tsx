import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';

import { Colors } from '@/constants/theme';
import { AuthProvider, useAuth } from '@/lib/auth';

SplashScreen.preventAutoHideAsync();

function Routes() {
  const { ready, session } = useAuth();

  useEffect(() => {
    if (ready) {
      SplashScreen.hideAsync();
    }
  }, [ready]);

  if (!ready) {
    return null;
  }

  const signedIn = session !== null;

  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: Colors.navy },
        headerTintColor: '#FFFFFF',
        headerTitleStyle: { fontWeight: '700' },
        contentStyle: { backgroundColor: Colors.background },
      }}>
      {/* Screens for someone signed in. Anyone else is sent to the login. */}
      <Stack.Protected guard={signedIn}>
        <Stack.Screen name="index" options={{ title: 'tally' }} />
        <Stack.Screen name="(parent)" options={{ headerShown: false, title: 'tally' }} />
        <Stack.Screen name="student/[id]" options={{ title: 'Today' }} />
        <Stack.Screen
          name="missed-day"
          options={{ title: 'Missed a Day?', presentation: 'modal' }}
        />
        <Stack.Screen
          name="assignment/edit"
          options={{ title: 'Assignment', presentation: 'modal' }}
        />
        <Stack.Screen
          name="assignment/notes"
          options={{ title: 'Notes for a Date', presentation: 'modal' }}
        />
        <Stack.Screen name="event/edit" options={{ title: 'Event', presentation: 'modal' }} />
      </Stack.Protected>

      <Stack.Protected guard={!signedIn}>
        <Stack.Screen name="login" options={{ headerShown: false }} />
      </Stack.Protected>
    </Stack>
  );
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <StatusBar style="light" />
      <Routes />
    </AuthProvider>
  );
}
