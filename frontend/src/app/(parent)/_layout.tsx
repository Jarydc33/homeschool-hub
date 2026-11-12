import { Redirect, Slot } from 'expo-router';
import { StyleSheet, useWindowDimensions, View } from 'react-native';

import { Loading } from '@/components/ui';
import { BottomBar, Sidebar, SIDEBAR_BREAKPOINT } from '@/components/parent-nav';
import { Colors } from '@/constants/theme';
import { useAuth } from '@/lib/auth';

/**
 * Parents' screens, with the menu: a sidebar on wide screens, a tab bar
 * along the bottom on phones. Anyone else goes back home, which sends them
 * to the right place. The API checks every call too.
 */
export default function ParentLayout() {
  const { me, error } = useAuth();
  const { width } = useWindowDimensions();

  if (error) {
    return <Redirect href="/" />;
  }

  if (!me) {
    return <Loading />;
  }

  if (me.role !== 'parent') {
    return <Redirect href="/" />;
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
