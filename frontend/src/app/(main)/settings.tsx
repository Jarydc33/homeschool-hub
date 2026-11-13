import { useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { ChoiceField } from '@/components/form';
import { TimeZoneField } from '@/components/time-zone-field';
import {
  Button,
  Card,
  ConfirmCard,
  ErrorMessage,
  Loading,
  PageTitle,
  Screen,
  SectionTitle,
  TextField,
} from '@/components/ui';
import { Colors, Radius, Spacing } from '@/constants/theme';
import { api, errorMessage } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { formatMoment } from '@/lib/dates';
import type { Device, FamilySettings, PairingCode, Student, TimeZoneChoice } from '@/lib/types';

/**
 * Family settings: name and time zone, the family PIN that ends Student Mode
 * and unpairs devices, and the devices showing a student's view.
 */
export default function SettingsScreen() {
  const { me, reloadMe } = useAuth();

  const [settings, setSettings] = useState<FamilySettings | null>(null);
  const [zones, setZones] = useState<TimeZoneChoice[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  // Goes up after each PIN save, to clear the PIN boxes.
  const [pinSaves, setPinSaves] = useState(0);

  const load = useCallback(async () => {
    try {
      const [family, zoneRows, deviceRows, studentRows] = await Promise.all([
        api<FamilySettings>('/family'),
        api<TimeZoneChoice[]>('/timezones'),
        api<Device[]>('/family/devices'),
        api<Student[]>('/students'),
      ]);
      setSettings(family);
      setZones(zoneRows);
      setDevices(deviceRows);
      setStudents(studentRows);
      setError(null);
    } catch (ex) {
      setError(errorMessage(ex));
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  async function refresh() {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }

  async function saveFamily(familyName: string, timezone: string) {
    const saved = await api<FamilySettings>('/family', {
      method: 'PUT',
      body: { family_name: familyName, timezone },
    });
    setSettings(saved);
    setNotice('Family settings saved.');
    // The name and what counts as today come from /me.
    await reloadMe();
  }

  async function savePin(pin: string, confirmPin: string) {
    const result = await api<{ message: string }>('/family/pin', {
      method: 'PUT',
      body: { pin, confirm_pin: confirmPin },
    });
    setPinSaves((n) => n + 1);
    setNotice(result.message);
    await load();
  }

  async function endDevice(device: Device) {
    await api(`/family/devices/${device.id}/end`, { method: 'POST' });
    setNotice(`${deviceKind(device)} ended for ${device.student.name}.`);
    await load();
  }

  const zone = me?.timezone ?? settings?.timezone ?? null;

  return (
    <Screen refreshing={refreshing} onRefresh={refresh}>
      <PageTitle>⚙️ Family Settings</PageTitle>

      {error ? <ErrorMessage message={error} onRetry={load} /> : null}

      {notice ? (
        <Text style={styles.notice} accessibilityLiveRegion="polite">
          ✓ {notice}
        </Text>
      ) : null}

      {!settings && !error ? <Loading /> : null}

      {settings ? (
        <>
          <FamilyForm
            key={`${settings.family_name}-${settings.timezone}`}
            settings={settings}
            zones={zones}
            onSave={saveFamily}
          />

          <SectionTitle>🔒 Family PIN</SectionTitle>
          <Text style={styles.muted}>
            The 4-digit PIN that ends Student Mode and unpairs devices. Any parent in your family
            can use it. Keep it secret from the kids.
          </Text>
          <PinForm key={pinSaves} hasPin={settings.has_pin} onSave={savePin} />

          <SectionTitle>📱 Devices</SectionTitle>
          <Text style={styles.muted}>
            Devices showing a student&apos;s view: paired devices, and parent devices in Student
            Mode. Ending one sends it back to the login.
          </Text>

          <PairDevice hasPin={settings.has_pin} students={students} zone={zone} onPaired={load} />

          {devices.length === 0 ? (
            <Text style={styles.muted}>
              No devices yet. Pair one above, or start Student Mode from the Dashboard.
            </Text>
          ) : null}

          {devices.map((device) => (
            <DeviceCard key={device.id} device={device} zone={zone} onEnd={endDevice} />
          ))}
        </>
      ) : null}
    </Screen>
  );
}

function deviceKind(device: Device): string {
  return device.mode === 'paired' ? 'Paired device' : 'Student Mode';
}

function FamilyForm({
  settings,
  zones,
  onSave,
}: {
  settings: FamilySettings;
  zones: TimeZoneChoice[];
  onSave: (familyName: string, timezone: string) => Promise<void>;
}) {
  const [name, setName] = useState(settings.family_name);
  const [timezone, setTimezone] = useState(settings.timezone);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const changed = name.trim() !== settings.family_name || timezone !== settings.timezone;

  async function submit() {
    if (!name.trim()) {
      setError('Please enter a family name.');
      return;
    }

    setBusy(true);
    setError(null);

    try {
      await onSave(name.trim(), timezone);
    } catch (ex) {
      setError(errorMessage(ex));
      setBusy(false);
    }
  }

  return (
    <Card>
      <View style={styles.form}>
        <TextField
          label="Family Name"
          value={name}
          onChangeText={setName}
          autoCapitalize="words"
          maxLength={100}
        />

        <TimeZoneField
          zones={zones}
          value={timezone}
          onChange={setTimezone}
          hint="Decides when your family's day starts and ends. Saved dates don't change."
        />

        {error ? <ErrorMessage message={error} /> : null}

        <Button title="Save Settings" busy={busy} disabled={!changed} onPress={submit} />
      </View>
    </Card>
  );
}

function PinForm({
  hasPin,
  onSave,
}: {
  hasPin: boolean;
  onSave: (pin: string, confirmPin: string) => Promise<void>;
}) {
  const [pin, setPin] = useState('');
  const [confirmPin, setConfirmPin] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!/^\d{4}$/.test(pin)) {
      setError('The PIN must be exactly 4 digits.');
      return;
    }

    if (pin !== confirmPin) {
      setError("The two PINs don't match.");
      return;
    }

    setBusy(true);
    setError(null);

    try {
      await onSave(pin, confirmPin);
    } catch (ex) {
      setError(errorMessage(ex));
      setBusy(false);
    }
  }

  return (
    <Card>
      {hasPin ? <Text style={styles.body}>✅ A PIN is set.</Text> : null}
      <View style={styles.form}>
        <View style={styles.pair}>
          <View style={styles.flex}>
            <TextField
              label={hasPin ? 'New PIN' : 'PIN'}
              value={pin}
              onChangeText={setPin}
              secureTextEntry
              keyboardType="number-pad"
              inputMode="numeric"
              maxLength={4}
              autoComplete="off"
            />
          </View>
          <View style={styles.flex}>
            <TextField
              label="Type it again"
              value={confirmPin}
              onChangeText={setConfirmPin}
              secureTextEntry
              keyboardType="number-pad"
              inputMode="numeric"
              maxLength={4}
              autoComplete="off"
              returnKeyType="done"
              onSubmitEditing={submit}
            />
          </View>
        </View>

        {error ? <ErrorMessage message={error} /> : null}

        <Button
          title={hasPin ? 'Change PIN' : 'Set PIN'}
          variant={hasPin ? 'secondary' : 'primary'}
          busy={busy}
          onPress={submit}
        />
      </View>
    </Card>
  );
}

/**
 * Makes a one-time code for a student's own device. The code stays on screen
 * until Done, since it's only shown once.
 */
function PairDevice({
  hasPin,
  students,
  zone,
  onPaired,
}: {
  hasPin: boolean;
  students: Student[];
  zone: string | null;
  onPaired: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [chosen, setChosen] = useState<number | null>(null);
  const [code, setCode] = useState<(PairingCode & { name: string }) | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const studentId = chosen ?? students[0]?.id ?? null;

  async function makeCode() {
    const student = students.find((s) => s.id === studentId);

    if (!student) {
      return;
    }

    setBusy(true);
    setError(null);

    try {
      const made = await api<PairingCode>(`/students/${student.id}/pairing-code`, {
        method: 'POST',
      });
      setCode({ ...made, name: student.name });
    } catch (ex) {
      setError(errorMessage(ex));
    } finally {
      setBusy(false);
    }
  }

  function done() {
    setOpen(false);
    setCode(null);
    setError(null);
    // The device shows up once it's used the code.
    onPaired();
  }

  if (!open) {
    return <Button title="+ Pair a Device" variant="secondary" onPress={() => setOpen(true)} />;
  }

  return (
    <Card>
      <Text style={styles.cardTitle}>📱 Pair a Device</Text>
      <Text style={styles.body}>
        Pair a student&apos;s own phone, tablet or computer. It will show only their view, with no
        email or password on it.
      </Text>

      {!hasPin ? (
        <Text style={styles.warning}>
          First, set a family PIN above. It&apos;s what unpairs a device.
        </Text>
      ) : students.length === 0 ? (
        <Text style={styles.warning}>Add a student on the Students screen first.</Text>
      ) : code ? (
        <View style={styles.form}>
          <Text style={styles.body}>Pairing code for {code.name}:</Text>
          <Text
            style={styles.code}
            accessibilityLabel={`Pairing code ${code.code.split('').join(' ')}`}
            selectable>
            {code.code.slice(0, 3)} {code.code.slice(3)}
          </Text>
          <Text style={styles.muted}>
            On their device, open tally and choose Have a Pairing Code on the login. The code works
            once and expires at {formatMoment(code.expires_at, zone)}.
          </Text>
        </View>
      ) : (
        <View style={styles.form}>
          {students.length > 1 ? (
            <ChoiceField
              label="Student"
              options={students.map((s) => ({ value: s.id, label: s.name }))}
              value={studentId}
              onChange={setChosen}
            />
          ) : null}
          {error ? <ErrorMessage message={error} /> : null}
          <Button
            title={students.length > 1 ? 'Make a Code' : `Make a Code for ${students[0].name}`}
            busy={busy}
            onPress={makeCode}
          />
        </View>
      )}

      <Button title={code ? 'Done' : 'Cancel'} variant="secondary" onPress={done} />
    </Card>
  );
}

function DeviceCard({
  device,
  zone,
  onEnd,
}: {
  device: Device;
  zone: string | null;
  onEnd: (device: Device) => Promise<void>;
}) {
  const [confirming, setConfirming] = useState(false);
  const kind = deviceKind(device);

  if (confirming) {
    return (
      <ConfirmCard
        title={`End ${kind} for ${device.student.name}?`}
        confirmLabel="End"
        onConfirm={() => onEnd(device)}
        onCancel={() => setConfirming(false)}>
        {device.mode === 'paired'
          ? 'That device goes back to the login, and needs a new code to pair again.'
          : 'That device goes back to the login, and a parent signs in again.'}
      </ConfirmCard>
    );
  }

  return (
    <Card>
      <View style={styles.row}>
        <View style={styles.flex}>
          <Text style={styles.cardTitle}>
            {device.student.name} · {kind}
          </Text>
          <Text style={styles.muted}>
            Started {formatMoment(device.created_at, zone)}
            {device.last_seen_at ? ` · Last used ${formatMoment(device.last_seen_at, zone)}` : ''}
          </Text>
        </View>
        <Button title="End" variant="secondary" onPress={() => setConfirming(true)} />
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  flex: {
    flex: 1,
  },
  body: {
    color: Colors.text,
    fontSize: 16,
  },
  muted: {
    color: Colors.textMuted,
    fontSize: 14,
  },
  warning: {
    color: Colors.orangeText,
    fontSize: 15,
    fontWeight: '600',
  },
  notice: {
    color: Colors.done,
    fontSize: 16,
    fontWeight: '600',
  },
  cardTitle: {
    color: Colors.navy,
    fontSize: 17,
    fontWeight: '700',
  },
  form: {
    gap: Spacing.md,
  },
  pair: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
  },
  code: {
    color: Colors.navy,
    fontSize: 40,
    fontWeight: '700',
    letterSpacing: 6,
    textAlign: 'center',
    paddingVertical: Spacing.sm,
    backgroundColor: Colors.surface,
    borderRadius: Radius,
  },
});
