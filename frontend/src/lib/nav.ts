/**
 * The parent menu, in the same groups as the Streamlit sidebar. Computers
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

export const MORE_ITEM: NavItem = { href: '/more', label: 'More', icon: '☰' };

export const FEEDBACK_EMAIL = 'tallyhomeschoolapp@gmail.com';

export const FEEDBACK_LINK = `mailto:${FEEDBACK_EMAIL}?subject=tally%20feedback`;

// The current app, for screens not rebuilt here yet.
export const CURRENT_APP_URL = 'https://tally-homeschool.streamlit.app';

export function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
