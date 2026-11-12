/**
 * Form controls that React Native doesn't have: choice chips, a date field
 * with a month calendar, and a labelled switch. They work the same on the
 * web, iPhone and Android.
 */
import { useState } from 'react';
import { Pressable, StyleSheet, Switch, Text, View } from 'react-native';

import { Colors, Radius, Spacing } from '@/constants/theme';
import { formatDate, parseDate, toDateString } from '@/lib/dates';

export interface Choice<T> {
  value: T;
  label: string;
  // A small colour dot before the label, e.g. a subject's.
  color?: string | null;
}

function Label({ text, hint }: { text: string; hint?: string }) {
  return (
    <View style={styles.labelWrap}>
      <Text style={styles.label}>{text}</Text>
      {hint ? <Text style={styles.hint}>{hint}</Text> : null}
    </View>
  );
}

function Chip({
  label,
  color,
  selected,
  multiple,
  onPress,
}: {
  label: string;
  color?: string | null;
  selected: boolean;
  multiple: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole={multiple ? 'checkbox' : 'radio'}
      accessibilityState={{ checked: selected }}
      accessibilityLabel={label}
      onPress={onPress}
      style={({ pressed }) => [
        styles.chip,
        selected && styles.chipSelected,
        pressed && styles.dim,
      ]}>
      {color ? <View style={[styles.dot, { backgroundColor: color }]} /> : null}
      <Text style={[styles.chipText, selected && styles.chipTextSelected]}>
        {multiple && selected ? '✓ ' : ''}
        {label}
      </Text>
    </Pressable>
  );
}

/** Pick one. */
export function ChoiceField<T extends string | number>({
  label,
  hint,
  options,
  value,
  onChange,
}: {
  label: string;
  hint?: string;
  options: Choice<T>[];
  value: T | null;
  onChange: (value: T) => void;
}) {
  return (
    <View style={styles.field}>
      <Label text={label} hint={hint} />
      <View style={styles.chips} accessibilityRole="radiogroup" accessibilityLabel={label}>
        {options.map((option) => (
          <Chip
            key={String(option.value)}
            label={option.label}
            color={option.color}
            selected={option.value === value}
            multiple={false}
            onPress={() => onChange(option.value)}
          />
        ))}
      </View>
    </View>
  );
}

/** Pick any number. The result keeps the options' order. */
export function MultiChoiceField<T extends string | number>({
  label,
  hint,
  options,
  value,
  onChange,
}: {
  label: string;
  hint?: string;
  options: Choice<T>[];
  value: T[];
  onChange: (value: T[]) => void;
}) {
  function toggle(item: T) {
    const next = value.includes(item) ? value.filter((v) => v !== item) : [...value, item];

    onChange(options.map((o) => o.value).filter((v) => next.includes(v)));
  }

  return (
    <View style={styles.field}>
      <Label text={label} hint={hint} />
      <View style={styles.chips} accessibilityLabel={label}>
        {options.map((option) => (
          <Chip
            key={String(option.value)}
            label={option.label}
            color={option.color}
            selected={value.includes(option.value)}
            multiple
            onPress={() => toggle(option.value)}
          />
        ))}
      </View>
    </View>
  );
}

/** On or off, with a label and an optional explanation. */
export function SwitchField({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint?: string;
  value: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <View style={styles.switchRow}>
      <View style={styles.flex}>
        <Label text={label} hint={hint} />
      </View>
      <Switch
        accessibilityLabel={label}
        value={value}
        onValueChange={onChange}
        trackColor={{ true: Colors.orange, false: Colors.border }}
        thumbColor="#FFFFFF"
      />
    </View>
  );
}

/**
 * A date ("YYYY-MM-DD"), shown as text; tapping it opens a month calendar.
 * isEnabled limits which days can be picked.
 */
export function DateField({
  label,
  hint,
  value,
  onChange,
  today,
  isEnabled,
}: {
  label: string;
  hint?: string;
  value: string;
  onChange: (value: string) => void;
  today?: string;
  isEnabled?: (day: string) => boolean;
}) {
  const [open, setOpen] = useState(false);

  return (
    <View style={styles.field}>
      <Label text={label} hint={hint} />
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${label}: ${formatDate(value)}. Change date`}
        accessibilityState={{ expanded: open }}
        onPress={() => setOpen(!open)}
        style={({ pressed }) => [styles.dateButton, pressed && styles.dim]}>
        <Text style={styles.dateText}>{formatYear(value)}</Text>
        <Text style={styles.dateIcon}>📅</Text>
      </Pressable>

      {open ? (
        <MonthCalendar
          value={value}
          today={today}
          isEnabled={isEnabled}
          onPick={(day) => {
            onChange(day);
            setOpen(false);
          }}
        />
      ) : null}
    </View>
  );
}

// "Thursday, November 12, 2026".
export function formatYear(value: string): string {
  return parseDate(value).toLocaleDateString(undefined, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });
}

const WEEKDAYS = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

export function MonthCalendar({
  value,
  today,
  isEnabled,
  onPick,
}: {
  value: string;
  today?: string;
  isEnabled?: (day: string) => boolean;
  onPick: (day: string) => void;
}) {
  const start = parseDate(value);
  const [month, setMonth] = useState(new Date(start.getFullYear(), start.getMonth(), 1));

  const first = month.getDay();
  const daysInMonth = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();

  // Blank cells before the 1st, then the month's days, in rows of seven.
  const cells: (string | null)[] = [
    ...Array<null>(first).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) =>
      toDateString(new Date(month.getFullYear(), month.getMonth(), i + 1)),
    ),
  ];

  while (cells.length % 7 !== 0) {
    cells.push(null);
  }

  const weeks = Array.from({ length: cells.length / 7 }, (_, i) => cells.slice(i * 7, i * 7 + 7));

  function shift(months: number) {
    setMonth(new Date(month.getFullYear(), month.getMonth() + months, 1));
  }

  return (
    <View style={styles.calendar}>
      <View style={styles.calendarHeader}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Previous month"
          onPress={() => shift(-1)}
          style={styles.monthArrow}>
          <Text style={styles.monthArrowText}>‹</Text>
        </Pressable>
        <Text style={styles.monthTitle} accessibilityRole="header">
          {month.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}
        </Text>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Next month"
          onPress={() => shift(1)}
          style={styles.monthArrow}>
          <Text style={styles.monthArrowText}>›</Text>
        </Pressable>
      </View>

      <View style={styles.week}>
        {WEEKDAYS.map((day, index) => (
          <Text key={index} style={styles.weekday}>
            {day}
          </Text>
        ))}
      </View>

      {weeks.map((week, index) => (
        <View key={index} style={styles.week}>
          {week.map((day, dayIndex) => {
            if (!day) {
              return <View key={dayIndex} style={styles.day} />;
            }

            const enabled = isEnabled ? isEnabled(day) : true;
            const selected = day === value;

            return (
              <Pressable
                key={day}
                accessibilityRole="button"
                accessibilityLabel={formatDate(day)}
                accessibilityState={{ selected, disabled: !enabled }}
                disabled={!enabled}
                onPress={() => onPick(day)}
                style={[
                  styles.day,
                  day === today && styles.today,
                  selected && styles.daySelected,
                ]}>
                <Text
                  style={[
                    styles.dayText,
                    !enabled && styles.dayDisabled,
                    selected && styles.dayTextSelected,
                  ]}>
                  {parseDate(day).getDate()}
                </Text>
              </Pressable>
            );
          })}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  field: {
    gap: Spacing.sm,
  },
  labelWrap: {
    gap: 2,
  },
  label: {
    color: Colors.navy,
    fontSize: 15,
    fontWeight: '600',
  },
  hint: {
    color: Colors.textMuted,
    fontSize: 13,
  },
  flex: {
    flex: 1,
  },
  dim: {
    opacity: 0.7,
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
  },
  chip: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    paddingHorizontal: Spacing.md,
    borderRadius: 22,
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.background,
  },
  chipSelected: {
    backgroundColor: Colors.navy,
    borderColor: Colors.navy,
  },
  chipText: {
    color: Colors.navy,
    fontSize: 15,
  },
  chipTextSelected: {
    color: '#FFFFFF',
    fontWeight: '600',
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  switchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
  },
  dateButton: {
    minHeight: 48,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius,
    paddingHorizontal: Spacing.md,
  },
  dateText: {
    color: Colors.text,
    fontSize: 16,
  },
  dateIcon: {
    fontSize: 18,
  },
  calendar: {
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius,
    padding: Spacing.sm,
    gap: 2,
    maxWidth: 380,
  },
  calendarHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  monthArrow: {
    width: 44,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  monthArrowText: {
    color: Colors.navy,
    fontSize: 26,
  },
  monthTitle: {
    color: Colors.navy,
    fontSize: 16,
    fontWeight: '700',
  },
  week: {
    flexDirection: 'row',
  },
  weekday: {
    flex: 1,
    textAlign: 'center',
    color: Colors.textMuted,
    fontSize: 13,
    fontWeight: '600',
    paddingVertical: Spacing.xs,
  },
  day: {
    flex: 1,
    aspectRatio: 1,
    maxHeight: 48,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 24,
  },
  today: {
    borderWidth: 1,
    borderColor: Colors.orange,
  },
  daySelected: {
    backgroundColor: Colors.orange,
  },
  dayText: {
    color: Colors.text,
    fontSize: 15,
  },
  dayDisabled: {
    color: Colors.blueGrey,
  },
  dayTextSelected: {
    color: '#FFFFFF',
    fontWeight: '700',
  },
});
