import { usePathname } from 'expo-router';

import { AccountLinks, NavList } from '@/components/app-nav';
import { PageTitle, Screen } from '@/components/ui';

/** Phones: everything in the menu, since the bottom bar shows only the main areas. */
export default function MoreScreen() {
  const pathname = usePathname();

  return (
    <Screen>
      <PageTitle>More</PageTitle>
      <NavList pathname={pathname} />
      <AccountLinks />
    </Screen>
  );
}
