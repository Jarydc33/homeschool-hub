from services.auth_service import AuthService
from services.occurrence_service import OccurrenceService
from services.student_service import (
    StudentService
)
from services.subject_service import (
    SubjectService
)
from services.assignment_service import (
    AssignmentService
)


class DashboardService:

    @staticmethod
    def get_dashboard_data():
        """
        overdue_assignments and today_assignments are lists of
        {"assignment", "student_names"}. Overdue names who still owes the
        work. Missed recurring dates aren't overdue.
        """

        students = (
            StudentService.get_current_family_students()
        )

        subjects = (
            SubjectService.get_current_family_subjects()
        )

        assignments = (
            AssignmentService.get_current_family_assignments()
        )

        today = AuthService.get_today()

        overdue_assignments = []
        today_assignments = []

        for assignment in assignments:

            names = {
                link.student_id: link.student.name
                for link in assignment.student_assignments
            }

            rows = [
                row
                for row in assignment.occurrences
                if row.student_id in names
            ]

            is_one_time = (
                assignment.assignment_type != "Recurring"
            )

            late = [
                row
                for row in rows
                if is_one_time
                and row.occurrence_date < today
                and not OccurrenceService.is_complete(row)
            ]

            if late:

                overdue_assignments.append(
                    {
                        "assignment": assignment,
                        "student_names": sorted(
                            names[row.student_id]
                            for row in late
                        ),
                    }
                )

            due_today = [
                row
                for row in rows
                if row.occurrence_date == today
            ]

            if any(
                not OccurrenceService.is_complete(row)
                for row in due_today
            ):

                today_assignments.append(
                    {
                        "assignment": assignment,
                        "student_names": sorted(
                            names[row.student_id]
                            for row in due_today
                        ),
                    }
                )

        return {
            "students": students,
            "subjects": subjects,
            "assignments": assignments,
            "today": today,
            "overdue_assignments": overdue_assignments,
            "today_assignments": today_assignments,
        }

    @staticmethod
    def get_student_metrics(student):

        groups = OccurrenceService.group_for_student(
            StudentService.get_student_occurrences(
                student.id
            ),
            AuthService.get_today()
        )

        progress = OccurrenceService.progress(groups)

        return {
            "total": progress["total"],
            "completed": progress["completed"],
            "percent": progress["percent"],
            "overdue_count": len(groups["overdue"]),
        }
