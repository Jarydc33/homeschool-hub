import { Redirect, Slot, usePathname } from 'expo-router';
import { StyleSheet, useWindowDimensions, View } from 'react-native';

import { Loading } from '@/components/ui';
import { BottomBar, Sidebar, SIDEBAR_BREAKPOINT } from '@/components/app-nav';
import { allowed, homeFor, navFor } from '@/lib/nav';
import { Colors } from '@/constants/theme';
import { useAuth } from '@/lib/auth';

/**
 * The screens with the menu: a sidebar on wide screens, a tab bar along the
 * bottom on phones. Parents and students each get their own menu, and a
 * screen that isn't on someone's menu sends them to their start. The API
 * checks every call too.
 */
export default function MainLayout() {
  const { me, error } = useAuth();
  const { width } = useWindowDimensions();
  const pathname = usePathname();

  if (error) {
    return <Redirect href="/" />;
  }

  if (!me) {
    return <Loading />;
  }

  if (me.role !== 'parent' && me.role !== 'student' && me.role !== 'admin') {
    return <Redirect href="/" />;
  }

  if (!allowed(navFor(me.role), pathname)) {
    return <Redirect href={homeFor(me.role) as never} />;
  }

  const wide = width >= SIDEBAR_BREAKPOINT;

  return (
    <View style={[styles.shell, wide && styles.row]}>
      {wide ? <Sidebar /> : null}

      <View style={styles.main}>
        <Slot />
      </View>

      {wide ? null : <BottomBar />}
    </View>
  );
}

const styles = StyleSheet.create({
  shell: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  row: {
    flexDirection: 'row',
  },
  main: {
    flex: 1,
  },
});
