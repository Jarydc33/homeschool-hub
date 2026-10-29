# scripts/verify_seed.py

import os
import sys

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

from database.db import SessionLocal
from database.models import (
    Family,
    Student,
    Subject,
    Assignment,
    StudentAssignment
)

db = SessionLocal()

print(f"Families: {db.query(Family).count()}")
print(f"Students: {db.query(Student).count()}")
print(f"Subjects: {db.query(Subject).count()}")
print(f"Assignments: {db.query(Assignment).count()}")
print(f"Student Assignments: {db.query(StudentAssignment).count()}")

db.close()