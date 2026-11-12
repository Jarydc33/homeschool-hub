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
