import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import {
  EarnedBadges,
  earnedKeys,
  NewBadges,
  newlyEarned,
  Stat,
  Stats,
} from '@/components/achievements';
import { ChoiceField, DateField } from '@/components/form';
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
import { Colors, Spacing } from '@/constants/theme';
import { api, errorMessage } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { formatDate } from '@/lib/dates';
import type { Badge, Book, Bookshelf, Student } from '@/lib/types';

// The API's limits, in api/routers/reading.py.
const MAX_BOOK_PAGES = 10000;
const MAX_PAGES_PER_DAY = 2000;

/**
 * Reading: a student's books, pages logged per day, their reading streak and
 * badges. A parent picks the student.
 */
export default function ReadingScreen() {
  const [students, setStudents] = useState<Student[] | null>(null);
  const [chosen, setChosen] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Student[]>('/students')
      .then(setStudents)
      .catch((ex) => setError(errorMessage(ex)));
  }, []);

  // The first student until one is picked.
  const studentId = chosen ?? students?.[0]?.id ?? null;

  return (
    <Screen>
      <PageTitle>📖 Reading</PageTitle>

      {error ? <ErrorMessage message={error} /> : null}

      {!students && !error ? <Loading /> : null}

      {students && students.length === 0 ? (
        <Text style={styles.body}>Add a student on the Students screen first.</Text>
      ) : null}

      {students && students.length > 1 ? (
        <ChoiceField
          label="Student"
          options={students.map((s) => ({ value: s.id, label: s.name }))}
          value={studentId}
          onChange={setChosen}
        />
      ) : null}

      {studentId !== null ? <Shelf key={studentId} studentId={studentId} /> : null}
    </Screen>
  );
}

/** One student's reading. Kept apart so a student's own view can reuse it. */
function Shelf({ studentId }: { studentId: number }) {
  const { me } = useAuth();
  const today = me?.today ?? null;

  const [shelf, setShelf] = useState<Bookshelf | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [newBadges, setNewBadges] = useState<Badge[]>([]);
  const [chosenDay, setDay] = useState<string | null>(null);

  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [archivingId, setArchivingId] = useState<number | null>(null);
  const [showFinished, setShowFinished] = useState(false);
  const [reopeningId, setReopeningId] = useState<number | null>(null);

  // The badges earned before a change, to spot new ones after it.
  const earned = useRef<Set<string> | null>(null);

  const day = chosenDay ?? today;

  const load = useCallback(async () => {
    try {
      const data = await api<Bookshelf>(`/students/${studentId}/books`);
      const fresh = newlyEarned(earned.current, data.summary.badges);

      if (fresh.length > 0) {
        setNewBadges(fresh);
      }

      earned.current = earnedKeys(data.summary.badges);
      setShelf(data);
      setError(null);
    } catch (ex) {
      setError(errorMessage(ex));
    }
  }, [studentId]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  function closeAll() {
    setAdding(false);
    setEditingId(null);
    setArchivingId(null);
    setNotice(null);
    setNewBadges([]);
  }

  async function addBook(values: BookValues) {
    const book = await api<Book>(`/students/${studentId}/books`, { method: 'POST', body: values });
    closeAll();
    setNotice(`${book.title} added.`);
    await load();
  }

  async function updateBook(id: number, values: BookValues) {
    const book = await api<Book>(`/books/${id}`, { method: 'PUT', body: values });
    closeAll();
    setNotice(`${book.title} updated.`);
    await load();
  }

  async function archiveBook(book: Book) {
    await api(`/books/${book.id}/archive`, { method: 'POST' });
    closeAll();
    setNotice(`${book.title} archived.`);
    await load();
  }

  async function savePages(book: Book, pages: number) {
    await api(`/books/${book.id}/pages/${day}`, { method: 'PUT', body: { pages } });
    closeAll();
    setNotice(pages ? `Pages saved for ${book.title}.` : `Pages removed from ${book.title}.`);
    await load();
  }

  async function setFinished(book: Book, finished: boolean) {
    await api(`/books/${book.id}/finished`, { method: 'PUT', body: { finished } });
    closeAll();
    setNotice(finished ? `Finished ${book.title}! 🎉` : `${book.title} is back in progress.`);
    await load();
  }

  async function reopen(book: Book) {
    setReopeningId(book.id);
    try {
      await setFinished(book, false);
    } catch (ex) {
      setError(errorMessage(ex));
    } finally {
      setReopeningId(null);
    }
  }

  if (!shelf || !today || !day) {
    return error ? <ErrorMessage message={error} onRetry={load} /> : <Loading />;
  }

  const { summary } = shelf;
  const reading = shelf.books.filter((b) => !b.finished_on);
  const finished = shelf.books
    .filter((b) => b.finished_on)
    .sort((a, b) => (a.finished_on! < b.finished_on! ? 1 : -1));

  return (
    <>
      {error ? <ErrorMessage message={error} onRetry={load} /> : null}

      <NewBadges badges={newBadges} />

      {notice ? (
        <Text style={styles.notice} accessibilityLiveRegion="polite">
          ✓ {notice}
        </Text>
      ) : null}

      <Stats>
        <Stat label="🔥 Reading Streak" value={summary.streak === 1 ? '1 day' : `${summary.streak} days`} />
        <Stat label="🏅 Best Streak" value={String(summary.best_streak)} />
        <Stat label="📄 Pages This Week" value={String(summary.pages_this_week)} />
        <Stat label="📚 Books Finished" value={String(summary.books_finished)} />
      </Stats>

      <Text style={styles.muted}>
        Read something every day to keep the streak alive, weekends included. Forgot a day? Pick
        that date below and log it.
      </Text>

      <EarnedBadges badges={summary.badges} />

      <SectionTitle>Books in Progress</SectionTitle>

      <DateField
        label="Reading Day"
        hint="Pages below are for this day."
        value={day}
        onChange={setDay}
        today={today}
        isEnabled={(d) => d <= today}
      />

      {reading.length === 0 ? (
        <Text style={styles.body}>No books in progress. Add one below.</Text>
      ) : null}

      {reading.map((book) =>
        editingId === book.id ? (
          <Card key={book.id}>
            <Text style={styles.cardTitle}>Edit {book.title}</Text>
            <BookForm
              initial={book}
              submitLabel="Save Changes"
              onSave={(values) => updateBook(book.id, values)}
              onCancel={closeAll}
            />
          </Card>
        ) : archivingId === book.id ? (
          <ConfirmCard
            key={book.id}
            title={`Archive ${book.title}?`}
            confirmLabel="Archive"
            onConfirm={() => archiveBook(book)}
            onCancel={closeAll}>
            This is for a book added by mistake. Its pages come out of the totals and streak. If
            it&apos;s been read, use Finished instead.
          </ConfirmCard>
        ) : (
          <BookCard
            // A new key after a save resets the box to the saved pages.
            key={`${book.id}-${day}-${pagesOn(book, day)}`}
            book={book}
            day={day}
            today={today}
            onSavePages={(pages) => savePages(book, pages)}
            onFinish={() => setFinished(book, true)}
            onEdit={() => {
              closeAll();
              setEditingId(book.id);
            }}
            onArchive={() => {
              closeAll();
              setArchivingId(book.id);
            }}
          />
        ),
      )}

      {adding ? (
        <Card>
          <Text style={styles.cardTitle}>Add a Book</Text>
          <BookForm submitLabel="Add Book" onSave={addBook} onCancel={closeAll} />
        </Card>
      ) : (
        <Button
          title="+ Add a Book"
          onPress={() => {
            closeAll();
            setAdding(true);
          }}
        />
      )}

      {finished.length > 0 ? (
        <>
          <Pressable
            accessibilityRole="button"
            accessibilityState={{ expanded: showFinished }}
            onPress={() => setShowFinished(!showFinished)}>
            <SectionTitle>
              {showFinished ? '▾' : '▸'} 🎉 Finished Books ({finished.length})
            </SectionTitle>
          </Pressable>

          {showFinished
            ? finished.map((book) => (
                <Card key={book.id}>
                  <View style={styles.row}>
                    <View style={styles.flex}>
                      <Text style={styles.cardTitle}>{book.title}</Text>
                      <Text style={styles.muted}>
                        {book.author ? `by ${book.author} · ` : ''}Finished{' '}
                        {formatDate(book.finished_on!, true)} · {book.pages_read} pages logged
                      </Text>
                    </View>
                    <Button
                      title="Reopen"
                      variant="secondary"
                      busy={reopeningId === book.id}
                      onPress={() => reopen(book)}
                    />
                  </View>
                </Card>
              ))
            : null}
        </>
      ) : null}
    </>
  );
}

function pagesOn(book: Book, day: string): number {
  return book.logs.find((log) => log.date === day)?.pages ?? 0;
}

function BookCard({
  book,
  day,
  today,
  onSavePages,
  onFinish,
  onEdit,
  onArchive,
}: {
  book: Book;
  day: string;
  today: string;
  onSavePages: (pages: number) => Promise<void>;
  onFinish: () => Promise<void>;
  onEdit: () => void;
  onArchive: () => void;
}) {
  const saved = pagesOn(book, day);
  const [pagesText, setPagesText] = useState(saved ? String(saved) : '');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<'pages' | 'finish' | null>(null);

  const progress = book.total_pages ? Math.min(book.pages_read / book.total_pages, 1) : null;

  async function run(kind: 'pages' | 'finish', action: () => Promise<void>) {
    setBusy(kind);
    setError(null);

    try {
      await action();
    } catch (ex) {
      setError(errorMessage(ex));
      setBusy(null);
    }
  }

  function savePages() {
    const text = pagesText.trim();
    const pages = text === '' ? 0 : Number(text);

    if (!/^\d*$/.test(text) || pages > MAX_PAGES_PER_DAY) {
      setError(`Please enter a whole number of pages, up to ${MAX_PAGES_PER_DAY}.`);
      return;
    }

    run('pages', () => onSavePages(pages));
  }

  return (
    <Card>
      <Text style={styles.cardTitle}>📘 {book.title}</Text>
      {book.author ? <Text style={styles.muted}>by {book.author}</Text> : null}

      {progress !== null ? (
        <View
          accessible
          accessibilityRole="progressbar"
          accessibilityLabel={`${book.pages_read} of ${book.total_pages} pages`}
          accessibilityValue={{ min: 0, max: 100, now: Math.round(progress * 100) }}>
          <View style={styles.track}>
            <View style={[styles.fill, { width: `${progress * 100}%` }]} />
          </View>
          <Text style={styles.muted}>
            {book.pages_read} of {book.total_pages} pages
          </Text>
        </View>
      ) : (
        <Text style={styles.muted}>{book.pages_read} pages read</Text>
      )}

      <View style={styles.pagesRow}>
        <View style={styles.flex}>
          <TextField
            label={day === today ? 'Pages read today' : `Pages read on ${formatDate(day, true)}`}
            value={pagesText}
            onChangeText={setPagesText}
            placeholder="0"
            keyboardType="number-pad"
            inputMode="numeric"
            maxLength={4}
            returnKeyType="done"
            onSubmitEditing={savePages}
          />
        </View>
        <Button
          title="Save Pages"
          busy={busy === 'pages'}
          disabled={busy !== null}
          onPress={savePages}
        />
      </View>

      {error ? <ErrorMessage message={error} /> : null}

      <View style={styles.actions}>
        <Button
          title="✅ Finished"
          variant="secondary"
          style={styles.action}
          busy={busy === 'finish'}
          disabled={busy !== null}
          onPress={() => run('finish', onFinish)}
        />
        <Button title="Edit" variant="secondary" style={styles.action} onPress={onEdit} />
        <Button title="Archive" variant="secondary" style={styles.action} onPress={onArchive} />
      </View>
    </Card>
  );
}

interface BookValues {
  title: string;
  author: string | null;
  total_pages: number | null;
}

function BookForm({
  initial,
  submitLabel,
  onSave,
  onCancel,
}: {
  initial?: Book;
  submitLabel: string;
  onSave: (values: BookValues) => Promise<void>;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState(initial?.title ?? '');
  const [author, setAuthor] = useState(initial?.author ?? '');
  const [pages, setPages] = useState(initial?.total_pages ? String(initial.total_pages) : '');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    const total = pages.trim() === '' ? null : Number(pages.trim());

    if (!title.trim()) {
      setError('Please enter a title.');
      return;
    }

    if (total !== null && (!/^\d+$/.test(pages.trim()) || total < 1 || total > MAX_BOOK_PAGES)) {
      setError(`Please enter a number of pages from 1 to ${MAX_BOOK_PAGES}, or leave it empty.`);
      return;
    }

    setBusy(true);
    setError(null);

    try {
      await onSave({ title: title.trim(), author: author.trim() || null, total_pages: total });
    } catch (ex) {
      setError(errorMessage(ex));
      setBusy(false);
    }
  }

  return (
    <View style={styles.form}>
      <TextField label="Title" value={title} onChangeText={setTitle} maxLength={200} autoFocus />
      <TextField
        label="Author"
        hint="Optional."
        value={author}
        onChangeText={setAuthor}
        autoCapitalize="words"
        maxLength={100}
      />
      <TextField
        label="Number of Pages"
        hint="Optional. Shows how far along the book is."
        value={pages}
        onChangeText={setPages}
        keyboardType="number-pad"
        inputMode="numeric"
        maxLength={5}
        returnKeyType="done"
        onSubmitEditing={submit}
      />

      {error ? <ErrorMessage message={error} /> : null}

      <View style={styles.actions}>
        <Button title="Cancel" variant="secondary" style={styles.action} onPress={onCancel} />
        <Button title={submitLabel} style={styles.action} busy={busy} onPress={submit} />
      </View>
    </View>
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
  notice: {
    color: Colors.done,
    fontSize: 16,
    fontWeight: '600',
  },
  cardTitle: {
    color: Colors.navy,
    fontSize: 18,
    fontWeight: '700',
  },
  track: {
    height: 10,
    borderRadius: 5,
    backgroundColor: Colors.surface,
    overflow: 'hidden',
    marginVertical: Spacing.xs,
  },
  fill: {
    height: '100%',
    backgroundColor: Colors.orange,
  },
  pagesRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: Spacing.sm,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
  },
  actions: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  action: {
    flex: 1,
  },
  form: {
    gap: Spacing.md,
  },
});
