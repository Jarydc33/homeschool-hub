/**
 * The menu: a sidebar on wide screens, a bottom tab bar on phones, and the
 * full list for the phone's More screen. Parents and students each get their
 * own (lib/nav.ts).
 */
import { Image } from 'expo-image';
import { Link, router, usePathname } from 'expo-router';
import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useEffect, useState } from 'react';

import { Colors, Radius, Spacing } from '@/constants/theme';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import {
  FEEDBACK_EMAIL,
  FEEDBACK_LINK,
  isActive,
  MORE_ITEM,
  navFor,
  type NavItem,
} from '@/lib/nav';
import type { Student } from '@/lib/types';

// Wider than this gets the sidebar.
export const SIDEBAR_BREAKPOINT = 768;

export function Sidebar() {
  const pathname = usePathname();
  const insets = useSafeAreaInsets();

  return (
    <View style={[styles.sidebar, { paddingTop: insets.top + Spacing.md }]}>
      <ScrollView contentContainerStyle={styles.sidebarScroll}>
        <Image
          source={require('../../assets/images/tally-logo.png')}
          style={styles.logo}
          contentFit="contain"
          accessibilityLabel="tally"
        />

        <WhoseView />

        <NavList pathname={pathname} />
      </ScrollView>

      <AccountLinks />
    </View>
  );
}

/** Every group's links, as the sidebar and the More screen show them. */
export function NavList({ pathname }: { pathname: string }) {
  const { me } = useAuth();

  return (
    <View style={styles.groups} accessibilityRole="menu">
      {navFor(me?.role).map((group) => (
        <View key={group.heading ?? 'top'} style={styles.group}>
          {group.heading ? <Text style={styles.heading}>{group.heading.toUpperCase()}</Text> : null}

          {group.items.map((item) => (
            <SideLink key={item.href} item={item} active={isActive(pathname, item.href)} />
          ))}
        </View>
      ))}
    </View>
  );
}

function SideLink({ item, active }: { item: NavItem; active: boolean }) {
  return (
    <Link href={item.href as never} asChild>
      <Pressable
        accessibilityRole="link"
        accessibilityState={{ selected: active }}
        style={({ pressed, hovered }) => [
          styles.sideLink,
          (pressed || hovered) && styles.sideLinkHover,
          active && styles.sideLinkActive,
        ]}>
        <Text style={styles.sideIcon}>{item.icon}</Text>
        <Text style={[styles.sideLabel, active && styles.sideLabelActive]}>{item.label}</Text>
      </Pressable>
    </Link>
  );
}

/** On a student's view: whose it is, and how it's signed in. */
export function WhoseView() {
  const { me } = useAuth();
  const [name, setName] = useState<string | null>(null);
  const studentId = me?.role === 'student' ? me.student_id : null;

  useEffect(() => {
    if (studentId === null) {
      return;
    }

    // A student only ever gets themselves here.
    api<Student[]>('/students')
      .then((rows) => setName(rows.find((s) => s.id === studentId)?.name ?? null))
      .catch(() => setName(null));
  }, [studentId]);

  if (!me || studentId === null || !name) {
    return null;
  }

  const how = me.student_mode ? 'Student Mode' : me.paired_device ? 'This device' : null;

  return (
    <View style={styles.whose}>
      <Text style={styles.whoseName}>🎓 {name}</Text>
      {how ? <Text style={styles.feedbackEmail}>{how}</Text> : null}
    </View>
  );
}

/**
 * Feedback and logging out, under the menu. Student Mode has no Log Out:
 * leaving it needs the family PIN.
 */
export function AccountLinks() {
  const { me, signOut } = useAuth();

  const studentMode = me?.student_mode ?? false;

  return (
    <View style={styles.account}>
      <Pressable accessibilityRole="link" onPress={() => Linking.openURL(FEEDBACK_LINK)}>
        <Text style={styles.feedback}>Send feedback</Text>
        <Text style={styles.feedbackEmail}>{FEEDBACK_EMAIL}</Text>
      </Pressable>

      {studentMode ? (
        <Pressable
          accessibilityRole="button"
          onPress={() => router.push('/exit-student-mode')}
          style={({ pressed }) => [styles.logout, pressed && styles.sideLinkHover]}>
          <Text style={styles.logoutText}>🔒 Exit Student Mode</Text>
        </Pressable>
      ) : me?.paired_device ? null : (
        <Pressable
          accessibilityRole="button"
          onPress={signOut}
          style={({ pressed }) => [styles.logout, pressed && styles.sideLinkHover]}>
          <Text style={styles.logoutText}>Log Out</Text>
        </Pressable>
      )}
    </View>
  );
}

/** The phone's bottom bar: the main areas, then More for the rest. */
export function BottomBar() {
  const pathname = usePathname();
  const insets = useSafeAreaInsets();
  const { me } = useAuth();

  const tabs = navFor(me?.role).flatMap((group) => group.items.filter((item) => item.tab));

  // Anything not in the bar counts as More.
  const onTab = tabs.some((item) => isActive(pathname, item.href));

  return (
    <View
      style={[styles.bottomBar, { paddingBottom: Math.max(insets.bottom, Spacing.sm) }]}
      accessibilityRole="tablist">
      {[...tabs, MORE_ITEM].map((item) => {
        const active = item === MORE_ITEM ? !onTab : isActive(pathname, item.href);

        return (
          <Link key={item.href} href={item.href as never} asChild>
            <Pressable
              accessibilityRole="tab"
              accessibilityState={{ selected: active }}
              accessibilityLabel={item.label}
              style={styles.tab}>
              <Text style={[styles.tabIcon, !active && styles.tabIconIdle]}>{item.icon}</Text>
              <Text style={[styles.tabLabel, active && styles.tabLabelActive]} numberOfLines={1}>
                {item.label}
              </Text>
            </Pressable>
          </Link>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  sidebar: {
    width: 240,
    backgroundColor: Colors.surface,
    borderRightWidth: 1,
    borderRightColor: Colors.border,
    paddingHorizontal: Spacing.sm,
    paddingBottom: Spacing.md,
  },
  sidebarScroll: {
    gap: Spacing.md,
  },
  logo: {
    width: 120,
    height: 48,
    marginLeft: Spacing.sm,
  },
  whose: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.sm,
    borderRadius: Radius,
    backgroundColor: Colors.background,
    gap: 2,
  },
  whoseName: {
    color: Colors.navy,
    fontSize: 15,
    fontWeight: '700',
  },
  groups: {
    gap: Spacing.md,
  },
  group: {
    gap: 2,
  },
  heading: {
    color: Colors.textMuted,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.8,
    paddingHorizontal: Spacing.sm,
    marginBottom: Spacing.xs,
  },
  sideLink: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    minHeight: 44,
    paddingHorizontal: Spacing.sm,
    borderRadius: Radius,
  },
  sideLinkHover: {
    backgroundColor: Colors.border,
  },
  sideLinkActive: {
    backgroundColor: Colors.background,
  },
  sideIcon: {
    fontSize: 18,
    width: 24,
    textAlign: 'center',
  },
  sideLabel: {
    color: Colors.navy,
    fontSize: 15,
    fontWeight: '500',
  },
  sideLabelActive: {
    color: Colors.orangeText,
    fontWeight: '700',
  },
  account: {
    gap: Spacing.md,
    paddingTop: Spacing.md,
    paddingHorizontal: Spacing.sm,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
  },
  feedback: {
    color: Colors.navy,
    fontSize: 14,
    fontWeight: '600',
  },
  feedbackEmail: {
    color: Colors.textMuted,
    fontSize: 12,
  },
  logout: {
    minHeight: 44,
    justifyContent: 'center',
    borderRadius: Radius,
  },
  logoutText: {
    color: Colors.navy,
    fontSize: 15,
    fontWeight: '600',
  },
  bottomBar: {
    flexDirection: 'row',
    backgroundColor: Colors.background,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
    paddingTop: Spacing.xs,
  },
  tab: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 52,
    gap: 2,
  },
  tabIcon: {
    fontSize: 20,
  },
  tabIconIdle: {
    opacity: 0.55,
  },
  tabLabel: {
    color: Colors.textMuted,
    fontSize: 11,
    fontWeight: '600',
  },
  tabLabelActive: {
    color: Colors.orangeText,
  },
});
