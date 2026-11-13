/**
 * What the API sends back. These mirror api/schemas.py; see the full list at
 * https://api.tallyhomeschool.com/docs. Dates are "YYYY-MM-DD" strings.
 */

export type Role = 'parent' | 'student' | 'admin';

export interface Me {
  role: Role;
  family_id: number | null;
  family_name: string | null;
  timezone: string | null;
  student_id: number | null;
  student_mode: boolean;
  paired_device: boolean;
  today: string;
}

export interface Student {
  id: number;
  name: string;
  grade_level: string | null;
  birth_year?: number | null;
}

export interface Subject {
  id: number;
  name: string;
  color: string | null;
}

export interface WorkItem {
  occurrence_id: number;
  assignment_id: number;
  title: string;
  subject: Subject | null;
  date: string;
  completed: boolean;
  completed_at: string | null;
  notes: string | null;
  lesson_number: number | null;
}

export interface Badge {
  key: string;
  icon: string;
  name: string;
  description: string;
  earned: boolean;
}

export interface Event {
  id: number;
  title: string;
  description: string | null;
  start_date: string;
  // The last day of a multi-day event.
  end_date: string | null;
  // "14:30:00", or null for all day.
  start_time: string | null;
  // "Weekly", "Every Day", ... or null for a one-off.
  recurrence_pattern: string | null;
  repeat_until: string | null;
  // Empty means the whole family, including students added later.
  student_ids: number[];
  // Who it's for, for reading: "Whole family" or names.
  audience: string;
}

// One date of an event, as a list shows it.
export interface EventEntry {
  event: Event;
  date: string;
  // "Tue, Nov 10 at 2:00 PM".
  when: string;
}

export interface EventList {
  // The next date of each upcoming event, soonest first.
  upcoming: EventEntry[];
  // Events that are over, newest first.
  past: Event[];
}

export interface Banner {
  id: number;
  title: string;
  message: string;
}

export interface StudentDashboard {
  student: Student;
  today: string;
  message: string;
  progress: { done: number; total: number };
  overdue: WorkItem[];
  today_work: WorkItem[];
  completed_today: WorkItem[];
  upcoming: WorkItem[];
  missed: WorkItem[];
  achievements: { streak: number; best_streak: number; badges: Badge[] };
  upcoming_events: EventEntry[];
  banners: Banner[];
}

export interface CheckOffResult {
  work: WorkItem;
  new_badges: Badge[];
}

export interface StudentMetrics {
  student: Student;
  total: number;
  completed: number;
  // 0 to 100.
  percent: number;
  overdue_count: number;
}

export interface DueWork {
  assignment_id: number;
  title: string;
  subject: Subject | null;
  // Overdue: who still owes it. Today: who it's due for.
  student_names: string[];
}

export interface ActivityDay {
  date: string;
  label: string;
  items: string[];
}

export interface ParentDashboard {
  today: string;
  message: string;
  students: StudentMetrics[];
  overdue: DueWork[];
  due_today: DueWork[];
  recent_activity: ActivityDay[];
  students_behind: number[];
  has_curriculum: boolean;
  upcoming_events: EventEntry[];
  banners: Banner[];
}

export interface RecoveryStep {
  student_name: string;
  title: string;
  next_lesson: number | null;
  next_date: string | null;
  old_finish: string | null;
  new_finish: string | null;
}

export interface SubjectDetail extends Subject {
  // Active assignments in this subject.
  assignment_count: number;
}

export type AssignmentType = 'One Time' | 'Recurring' | 'Curriculum';

export interface Assignment {
  id: number;
  title: string;
  description: string | null;
  subject: Subject | null;
  assignment_type: AssignmentType;
  // Recurring: how often ("Every Day", "Weekly", ...). Curriculum: its
  // school days ("Mon,Wed,Fri").
  recurrence_pattern: string | null;
  // One-time: due. Recurring: the first date. Curriculum: the first lesson.
  due_date: string;
  end_date: string | null;
  graded: boolean;
  active: boolean;
  // Active students only. Archived assignments list none.
  students: Student[];
  progress: { done: number; total: number } | null;
  lesson_count: number | null;
  finish_date: string | null;
}

export interface NoteRow {
  occurrence_id: number;
  student: Student;
  date: string;
  notes: string | null;
}

export type CalendarStatus = 'event' | 'to_do' | 'done' | 'overdue' | 'missed';

export interface CalendarItem {
  status: CalendarStatus;
  title: string;
  detail: string | null;
  // Whose work it is; null for an event.
  student: string | null;
}

// Only dates with something on them are sent.
export interface CalendarDay {
  date: string;
  items: CalendarItem[];
}

// A percent with its letter, such as 92.0 and "A".
export interface Grade {
  percent: number;
  letter: string;
}

export interface GradedWork {
  work: WorkItem;
  score: number;
  points_possible: number;
  grade: Grade;
}

export interface GradingPeriod {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
}

export interface PeriodGrade {
  period_id: number;
  grade: Grade;
}

export interface GradeReport {
  // The period asked for, or null for all time.
  period: GradingPeriod | null;
  overall: Grade | null;
  subjects: { subject: string; grade: Grade }[];
  work: GradedWork[];
  // Each subject across every period, and the overall, to compare terms.
  comparison: { subject: string; periods: PeriodGrade[] }[];
  overall_by_period: PeriodGrade[];
}

export interface GradingQueue {
  // Checked off but not graded yet, oldest first.
  finished: WorkItem[];
  // Not checked off, from the last 30 days through the next 7.
  unfinished: WorkItem[];
  // Points to suggest per assignment id, from its latest grade.
  suggested_totals: Record<string, number>;
}

export interface ReadingSummary {
  // Days in a row with some reading, weekends included.
  streak: number;
  best_streak: number;
  pages_this_week: number;
  total_pages: number;
  books_finished: number;
  badges: Badge[];
}

export interface Book {
  id: number;
  student_id: number;
  title: string;
  author: string | null;
  total_pages: number | null;
  finished_on: string | null;
  pages_read: number;
  pages_today: number;
  // Pages per date, newest first.
  logs: { date: string; pages: number }[];
}

export interface Bookshelf {
  books: Book[];
  summary: ReadingSummary;
}

export interface PESummary {
  minutes_this_week: number;
  active_days_this_week: number;
  total_minutes: number;
  badges: Badge[];
}

export interface Activity {
  id: number;
  student_id: number;
  date: string;
  activity: string;
  minutes: number;
}

export interface PELog {
  // Newest first.
  logs: Activity[];
  summary: PESummary;
  // Activity names already used, most used first, to suggest.
  known_activities: string[];
}
