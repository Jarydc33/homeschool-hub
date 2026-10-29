import os
import sys

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

from database.db import SessionLocal
from database.models import Student

db = SessionLocal()

students = db.query(Student).all()

for student in students:
    print(student.id)
    print(student.name)
    print(student.grade_level)
    print("-------------")


db.close()