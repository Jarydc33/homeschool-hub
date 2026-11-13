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

export interface EventEntry {
  event: { id: number; title: string; audience: string };
  date: string;
  when: string;
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
