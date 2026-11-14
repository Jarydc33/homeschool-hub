/**
 * The menu: a navy sidebar on wide screens, a bottom tab bar on phones, and
 * the full list for the phone's More screen. Parents and students each get
 * their own (lib/nav.ts).
 */
import { Image } from 'expo-image';
import { Link, router, usePathname } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Colors, Radius, Spacing } from '@/constants/theme';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import {
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
      <ScrollView
        contentContainerStyle={styles.sidebarScroll}
        showsVerticalScrollIndicator={false}>
        <View style={styles.brand}>
          <Image
            source={require('../../assets/images/tally-logo.png')}
            style={styles.brandMark}
            contentFit="contain"
            accessibilityLabel="tally"
          />
          <Text style={styles.brandName}>tally</Text>
        </View>

        <WhoseView dark />

        <NavList pathname={pathname} dark />
      </ScrollView>

      <AccountLinks dark />
    </View>
  );
}

/**
 * Every group's links, as the sidebar (on navy) and the phone's More screen
 * (on white) show them. Each group sits under a divider, with its heading
 * right on top of its links.
 */
export function NavList({ pathname, dark = false }: { pathname: string; dark?: boolean }) {
  const { me } = useAuth();
  const tone = dark ? darkStyles : lightStyles;

  return (
    <View style={styles.groups} accessibilityRole="menu">
      {navFor(me?.role).map((group) => (
        <View
          key={group.heading ?? 'top'}
          style={[styles.group, group.heading ? [styles.groupHeaded, tone.groupHeaded] : null]}>
          {group.heading ? (
            <Text style={[styles.heading, tone.heading]} accessibilityRole="header">
              {group.heading.toUpperCase()}
            </Text>
          ) : null}

          {group.items.map((item) => (
            <SideLink
              key={item.href}
              item={item}
              active={isActive(pathname, item.href)}
              dark={dark}
            />
          ))}
        </View>
      ))}
    </View>
  );
}

function SideLink({ item, active, dark }: { item: NavItem; active: boolean; dark: boolean }) {
  const tone = dark ? darkStyles : lightStyles;
  // Link (asChild) drops a style given as a function and can't take a list,
  // so hover is tracked here and the styles are merged into one.
  const [hovered, setHovered] = useState(false);

  return (
    <Link href={item.href as never} asChild>
      <Pressable
        accessibilityRole="link"
        accessibilityState={{ selected: active }}
        onHoverIn={() => setHovered(true)}
        onHoverOut={() => setHovered(false)}
        style={StyleSheet.flatten([
          styles.sideLink,
          hovered && tone.linkHover,
          active && tone.linkActive,
        ])}>
        <View style={[styles.activeBar, active && styles.activeBarOn]} />
        <Text style={styles.sideIcon}>{item.icon}</Text>
        <Text style={[styles.sideLabel, tone.label, active && tone.labelActive]}>
          {item.label}
        </Text>
      </Pressable>
    </Link>
  );
}

/** On a student's view: whose it is, and how it's signed in. */
export function WhoseView({ dark = false }: { dark?: boolean }) {
  const { me } = useAuth();
  const [name, setName] = useState<string | null>(null);
  const studentId = me?.role === 'student' ? me.student_id : null;
  const tone = dark ? darkStyles : lightStyles;

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
    <View style={[styles.whose, tone.whose]}>
      <Text style={[styles.whoseName, tone.strong]}>🎓 {name}</Text>
      {how ? <Text style={[styles.small, tone.muted]}>{how}</Text> : null}
    </View>
  );
}

/**
 * Feedback and logging out, under the menu. Student Mode and paired devices
 * have no Log Out: leaving either needs the family PIN.
 */
export function AccountLinks({ dark = false }: { dark?: boolean }) {
  const { me, signOut } = useAuth();
  const tone = dark ? darkStyles : lightStyles;

  const action = me?.student_mode
    ? { label: '🔒 Exit Student Mode', onPress: () => router.push('/exit-student-mode') }
    : me?.paired_device
      ? { label: '🔓 Unpair This Device', onPress: () => router.push('/unpair-device') }
      : { label: 'Log Out', onPress: signOut };

  // Only parents send feedback; the API refuses students.
  const canSendFeedback = me?.role === 'parent' && !me.student_mode && !me.paired_device;

  return (
    <View style={[styles.account, tone.account]}>
      {canSendFeedback ? (
        <Pressable
          accessibilityRole="button"
          onPress={() => router.push('/feedback')}
          style={({ pressed, hovered }) => [styles.accountLink, (pressed || hovered) && tone.linkHover]}>
          <Text style={[styles.accountText, tone.strong]}>💬 Send feedback</Text>
        </Pressable>
      ) : null}

      <Pressable
        accessibilityRole="button"
        onPress={action.onPress}
        style={({ pressed, hovered }) => [styles.accountLink, (pressed || hovered) && tone.linkHover]}>
        <Text style={[styles.accountText, tone.strong]}>{action.label}</Text>
      </Pressable>
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
    width: 248,
    backgroundColor: Colors.navy,
    paddingHorizontal: Spacing.sm,
    paddingBottom: Spacing.md,
  },
  sidebarScroll: {
    gap: Spacing.md,
    paddingBottom: Spacing.md,
  },
  brand: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingHorizontal: Spacing.xs,
    paddingBottom: Spacing.xs,
  },
  brandMark: {
    width: 40,
    height: 40,
    borderRadius: 8,
  },
  brandName: {
    color: '#FFFFFF',
    fontSize: 26,
    fontWeight: '800',
    letterSpacing: -0.5,
  },
  groups: {
    gap: Spacing.md,
  },
  group: {
    gap: 2,
  },
  // A divider above each headed group, so its links read as belonging to it.
  groupHeaded: {
    borderTopWidth: 1,
    paddingTop: Spacing.md,
  },
  heading: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1.2,
    paddingHorizontal: Spacing.md,
    marginBottom: Spacing.xs,
  },
  sideLink: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    minHeight: 40,
    paddingRight: Spacing.sm,
    borderRadius: Radius,
    overflow: 'hidden',
  },
  // The current page's orange edge, as on the landing page.
  activeBar: {
    width: 4,
    alignSelf: 'stretch',
    marginRight: Spacing.xs,
  },
  activeBarOn: {
    backgroundColor: Colors.orange,
  },
  sideIcon: {
    fontSize: 17,
    width: 22,
    textAlign: 'center',
  },
  sideLabel: {
    fontSize: 15,
    fontWeight: '500',
  },
  whose: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: Radius,
    gap: 2,
  },
  whoseName: {
    fontSize: 15,
    fontWeight: '700',
  },
  small: {
    fontSize: 12,
  },
  account: {
    gap: 2,
    paddingTop: Spacing.sm,
    borderTopWidth: 1,
  },
  accountLink: {
    minHeight: 40,
    justifyContent: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs,
    borderRadius: Radius,
  },
  accountText: {
    fontSize: 14,
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

// The sidebar, on navy.
const darkStyles = StyleSheet.create({
  groupHeaded: { borderTopColor: Colors.navyLine },
  heading: { color: '#8C97B3' },
  label: { color: Colors.onNavy },
  labelActive: { color: '#FFFFFF', fontWeight: '700' },
  linkHover: { backgroundColor: Colors.navyRaised },
  linkActive: { backgroundColor: Colors.navyRaised },
  whose: { backgroundColor: Colors.navyRaised },
  strong: { color: '#FFFFFF' },
  muted: { color: Colors.onNavyMuted },
  account: { borderTopColor: Colors.navyLine },
});

// The phone's More screen, on white.
const lightStyles = StyleSheet.create({
  groupHeaded: { borderTopColor: Colors.border },
  heading: { color: Colors.textMuted },
  label: { color: Colors.navy },
  labelActive: { color: Colors.orangeText, fontWeight: '700' },
  linkHover: { backgroundColor: Colors.surface },
  linkActive: { backgroundColor: Colors.surface },
  whose: { backgroundColor: Colors.surface },
  strong: { color: Colors.navy },
  muted: { color: Colors.textMuted },
  account: { borderTopColor: Colors.border },
});
