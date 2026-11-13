/**
 * Stat tiles and badges, shared by the Reading and P.E. screens.
 */
import { StyleSheet, Text, View } from 'react-native';

import { Card } from '@/components/ui';
import { Colors, Radius, Spacing } from '@/constants/theme';
import type { Badge } from '@/lib/types';

/** Tiles in a row on wide screens, wrapping two by two on phones. */
export function Stats({ children }: { children: React.ReactNode }) {
  return <View style={styles.stats}>{children}</View>;
}

export function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.stat} accessible accessibilityLabel={`${label}: ${value}`}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={styles.statValue}>{value}</Text>
    </View>
  );
}

/** The badges earned so far, as small pills. Nothing when there are none. */
export function EarnedBadges({ badges }: { badges: Badge[] }) {
  const earned = badges.filter((b) => b.earned);

  if (earned.length === 0) {
    return null;
  }

  return (
    <View
      style={styles.badges}
      accessible
      accessibilityLabel={`Badges: ${earned.map((b) => b.name).join(', ')}`}>
      {earned.map((badge) => (
        <View key={badge.key} style={styles.badge}>
          <Text style={styles.badgeText}>
            {badge.icon} {badge.name}
          </Text>
        </View>
      ))}
    </View>
  );
}

/** A card for each badge just earned. */
export function NewBadges({ badges }: { badges: Badge[] }) {
  return (
    <>
      {badges.map((badge) => (
        <Card key={badge.key} style={styles.badgeCard}>
          <Text style={styles.badgeNew} accessibilityLiveRegion="polite">
            {badge.icon} New badge: {badge.name}!
          </Text>
          <Text style={styles.muted}>{badge.description}</Text>
        </Card>
      ))}
    </>
  );
}

/**
 * The badges in after that weren't earned in before (a set of keys), like
 * AchievementService.newly_earned.
 */
export function newlyEarned(before: Set<string> | null, after: Badge[]): Badge[] {
  if (!before) {
    return [];
  }

  return after.filter((b) => b.earned && !before.has(b.key));
}

export function earnedKeys(badges: Badge[]): Set<string> {
  return new Set(badges.filter((b) => b.earned).map((b) => b.key));
}

const styles = StyleSheet.create({
  muted: {
    color: Colors.textMuted,
    fontSize: 14,
  },
  stats: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
  },
  stat: {
    flexGrow: 1,
    flexBasis: 140,
    padding: Spacing.md,
    borderRadius: Radius,
    backgroundColor: Colors.surface,
    gap: Spacing.xs,
  },
  statLabel: {
    color: Colors.textMuted,
    fontSize: 13,
  },
  statValue: {
    color: Colors.navy,
    fontSize: 24,
    fontWeight: '700',
  },
  badges: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
  },
  badge: {
    paddingHorizontal: Spacing.sm,
    paddingVertical: Spacing.xs,
    borderRadius: 14,
    backgroundColor: '#FFF6EE',
    borderWidth: 1,
    borderColor: '#F3C6A8',
  },
  badgeText: {
    color: Colors.navy,
    fontSize: 13,
    fontWeight: '600',
  },
  badgeCard: {
    backgroundColor: '#FFF6EE',
    borderColor: '#F3C6A8',
  },
  badgeNew: {
    color: Colors.navy,
    fontSize: 18,
    fontWeight: '700',
  },
});
