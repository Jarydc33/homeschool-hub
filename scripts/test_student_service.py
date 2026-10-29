import os
import sys

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

from services.student_service import StudentService

students = StudentService.get_all_students()

for student in students:
    print(
        student.id,
        student.name,
        student.grade_level
    )