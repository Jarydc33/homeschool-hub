/**
 * Picking a family's time zone: the US ones as chips, and a search for the
 * rest. Used by sign-up and Settings.
 */
import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { ChoiceField } from '@/components/form';
import { TextField } from '@/components/ui';
import { Colors, Spacing } from '@/constants/theme';
import type { TimeZoneChoice } from '@/lib/types';

// How many time zones a search shows.
const ZONE_MATCHES = 8;

export function TimeZoneField({
  zones,
  value,
  onChange,
  hint,
}: {
  zones: TimeZoneChoice[];
  value: string;
  onChange: (zone: string) => void;
  hint?: string;
}) {
  const [search, setSearch] = useState('');

  // The US zones come first from the API and have a friendly label.
  const common = zones.filter((z) => z.label !== z.name);
  const current = zones.find((z) => z.name === value);
  const choices = current && !common.includes(current) ? [...common, current] : common;

  const query = search.trim().toLowerCase().replace(/\s+/g, '_');
  const matches = query
    ? zones
        .filter((z) => !choices.includes(z) && z.label.toLowerCase().includes(query))
        .slice(0, ZONE_MATCHES)
    : [];

  return (
    <View style={styles.field}>
      <ChoiceField
        label="Time Zone"
        hint={hint}
        options={choices.map((z) => ({ value: z.name, label: z.label.replace(/ \(.*\)$/, '') }))}
        value={value}
        onChange={onChange}
      />

      <TextField
        label="Somewhere else?"
        placeholder="Search, for example London or Toronto"
        value={search}
        onChangeText={setSearch}
        autoCorrect={false}
      />

      {matches.length > 0 ? (
        <ChoiceField
          label="Matching time zones"
          options={matches.map((z) => ({ value: z.name, label: z.name.replace(/_/g, ' ') }))}
          value={value}
          onChange={(picked) => {
            onChange(picked);
            setSearch('');
          }}
        />
      ) : query ? (
        <Text style={styles.muted}>No time zones match that.</Text>
      ) : null}
    </View>
  );
}

/** The device's own time zone if Tally offers it, else the first choice. */
export function deviceTimeZone(zones: TimeZoneChoice[]): string {
  let zone = '';

  try {
    zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch {
    // No time zone support: use the default below.
  }

  return zones.some((z) => z.name === zone) ? zone : (zones[0]?.name ?? 'America/Chicago');
}

const styles = StyleSheet.create({
  field: {
    gap: Spacing.md,
  },
  muted: {
    color: Colors.textMuted,
    fontSize: 14,
  },
});
