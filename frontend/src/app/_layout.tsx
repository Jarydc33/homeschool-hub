// Each weight from its own path, so the build carries only these five.
import { Inter_400Regular } from '@expo-google-fonts/inter/400Regular';
import { Inter_500Medium } from '@expo-google-fonts/inter/500Medium';
import { Inter_600SemiBold } from '@expo-google-fonts/inter/600SemiBold';
import { Inter_700Bold } from '@expo-google-fonts/inter/700Bold';
import { Inter_800ExtraBold } from '@expo-google-fonts/inter/800ExtraBold';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';

import { Colors, Fonts } from '@/constants/theme';
import { AuthProvider, useAuth } from '@/lib/auth';

SplashScreen.preventAutoHideAsync();

function Routes() {
  const { ready, signedIn } = useAuth();
  // If the fonts fail to load, carry on with the system font.
  const [fontsLoaded, fontError] = useFonts({
    Inter_400Regular,
    Inter_500Medium,
    Inter_600SemiBold,
    Inter_700Bold,
    Inter_800ExtraBold,
  });
  const fontsReady = fontsLoaded || fontError !== null;

  useEffect(() => {
    if (ready && fontsReady) {
      SplashScreen.hideAsync();
    }
  }, [ready, fontsReady]);

  if (!ready || !fontsReady) {
    return null;
  }

  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: Colors.navy },
        headerTintColor: '#FFFFFF',
        headerTitleStyle: { fontFamily: Fonts.bold },
        contentStyle: { backgroundColor: Colors.background },
      }}>
      {/* Screens for someone signed in. Anyone else is sent to the login. */}
      <Stack.Protected guard={signedIn}>
        <Stack.Screen name="index" options={{ title: 'tally' }} />
        <Stack.Screen name="(main)" options={{ headerShown: false, title: 'tally' }} />
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
        <Stack.Screen
          name="feedback"
          options={{ title: 'Send Feedback', presentation: 'modal' }}
        />
        <Stack.Screen
          name="exit-student-mode"
          options={{ title: 'Exit Student Mode', presentation: 'modal' }}
        />
        <Stack.Screen
          name="unpair-device"
          options={{ title: 'Unpair This Device', presentation: 'modal' }}
        />
      </Stack.Protected>

      <Stack.Protected guard={!signedIn}>
        <Stack.Screen name="login" options={{ headerShown: false }} />
        <Stack.Screen name="register" options={{ headerShown: false }} />
        <Stack.Screen name="forgot-password" options={{ headerShown: false }} />
      </Stack.Protected>

      {/* Email links work whoever is signed in on this device, if anyone. */}
      <Stack.Screen name="complete-account" options={{ headerShown: false }} />
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
