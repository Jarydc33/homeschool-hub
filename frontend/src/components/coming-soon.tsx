import { Linking, StyleSheet, Text } from 'react-native';

import { Button, Card, PageTitle, Screen } from '@/components/ui';
import { Colors } from '@/constants/theme';
import { CURRENT_APP_URL } from '@/lib/nav';

/** A menu area not rebuilt in the new app yet. */
export function ComingSoon({ title, icon }: { title: string; icon: string }) {
  return (
    <Screen>
      <PageTitle>
        {icon} {title}
      </PageTitle>

      <Card>
        <Text style={styles.body}>
          {title} is coming to the new app soon. Until then, it&apos;s in the current Tally app.
        </Text>
        <Button
          title="Open the current app"
          variant="secondary"
          onPress={() => Linking.openURL(CURRENT_APP_URL)}
        />
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  body: {
    color: Colors.text,
    fontSize: 16,
  },
});
