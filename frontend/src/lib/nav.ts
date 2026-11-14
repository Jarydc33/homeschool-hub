import type { Role } from './types';

/**
 * The menus, in the same groups as the Streamlit sidebar. Computers
 * show it all as a sidebar; phones show the `tab` items along the bottom and
 * the rest under More.
 */

export interface NavItem {
  href: string;
  label: string;
  icon: string;
  // Shown in the phone's bottom bar.
  tab?: boolean;
}

export interface NavGroup {
  // No heading: the links sit above the groups.
  heading: string | null;
  items: NavItem[];
}

export const PARENT_NAV: NavGroup[] = [
  {
    heading: null,
    items: [{ href: '/dashboard', label: 'Dashboard', icon: '🏡', tab: true }],
  },
  {
    heading: 'Plan',
    items: [
      { href: '/calendar', label: 'Calendar', icon: '📆', tab: true },
      { href: '/assignments', label: 'Assignments', icon: '✅', tab: true },
      { href: '/events', label: 'Events', icon: '📅' },
      { href: '/subjects', label: 'Subjects', icon: '📚' },
    ],
  },
  {
    heading: 'Track',
    items: [
      { href: '/grades', label: 'Grades', icon: '📊' },
      { href: '/reading', label: 'Reading', icon: '📖' },
      { href: '/pe', label: 'P.E.', icon: '🏃' },
    ],
  },
  {
    heading: 'Family',
    items: [
      { href: '/students', label: 'Students', icon: '👨‍🎓', tab: true },
      { href: '/announcements', label: 'Announcements', icon: '📢' },
      { href: '/settings', label: 'Settings', icon: '⚙️' },
    ],
  },
];

// A student's menu: their own login, Student Mode or a paired device. The
// screens they share with parents show them only their own, read-only where
// that's a parent's job.
export const STUDENT_NAV: NavGroup[] = [
  {
    heading: null,
    items: [{ href: '/today', label: 'Today', icon: '🎓', tab: true }],
  },
  {
    heading: 'Plan',
    items: [
      { href: '/calendar', label: 'Calendar', icon: '📆', tab: true },
      { href: '/events', label: 'Events', icon: '📅' },
    ],
  },
  {
    heading: 'Track',
    items: [
      { href: '/grades', label: 'Grades', icon: '📊' },
      { href: '/reading', label: 'Reading', icon: '📖', tab: true },
      { href: '/pe', label: 'P.E.', icon: '🏃', tab: true },
    ],
  },
];

// An Admin (a separate login, no family) only manages system-wide
// announcements, as in the Streamlit app.
export const ADMIN_NAV: NavGroup[] = [
  {
    heading: null,
    items: [{ href: '/announcements', label: 'Announcements', icon: '📢', tab: true }],
  },
];

export function navFor(role: Role | undefined): NavGroup[] {
  if (role === 'admin') {
    return ADMIN_NAV;
  }

  return role === 'student' ? STUDENT_NAV : PARENT_NAV;
}

/** The screen someone starts on. */
export function homeFor(role: Role | undefined): string {
  if (role === 'admin') {
    return '/announcements';
  }

  return role === 'student' ? '/today' : '/dashboard';
}

/** Whether this menu has the screen, or More, which every menu has. */
export function allowed(nav: NavGroup[], pathname: string): boolean {
  return (
    isActive(pathname, MORE_ITEM.href) ||
    nav.some((group) => group.items.some((item) => isActive(pathname, item.href)))
  );
}

export const MORE_ITEM: NavItem = { href: '/more', label: 'More', icon: '☰' };

export const FEEDBACK_EMAIL = 'hello@tallyhomeschool.com';

export function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
