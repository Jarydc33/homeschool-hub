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
