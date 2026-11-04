from services.auth_service import AuthService
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

            if not assignment.due_date:
                continue

            incomplete_students = [
                sa
                for sa
                in assignment.student_assignments
                if sa.status != "Complete"
            ]

            if not incomplete_students:
                continue

            if assignment.due_date < today:

                overdue_assignments.append(
                    assignment
                )

            elif assignment.due_date == today:

                today_assignments.append(
                    assignment
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

        today = AuthService.get_today()

        student_assignments = (
            StudentService.get_student_assignments(
                student.id
            )
        )

        total = len(student_assignments)

        completed = len(
            [
                assignment
                for assignment
                in student_assignments
                if assignment.status == "Complete"
            ]
        )

        percent = 0

        if total > 0:

            percent = round(
                (completed / total) * 100
            )

        overdue_count = len(
            [
                assignment
                for assignment
                in student_assignments
                if (
                    assignment.assignment.due_date
                    and assignment.assignment.due_date < today
                    and assignment.status != "Complete"
                )
            ]
        )

        return {
            "total": total,
            "completed": completed,
            "percent": percent,
            "student_assignments": student_assignments,
            "overdue_count": overdue_count
        }