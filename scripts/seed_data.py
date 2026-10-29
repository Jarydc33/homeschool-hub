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
    StudentAssignment,
)


def seed_database():

    db = SessionLocal()

    # Prevent duplicate seed runs
    existing_family = db.query(Family).first()

    if existing_family:
        print("Database already contains data.")
        db.close()
        return

    # -------------------------------------------------
    # Family
    # -------------------------------------------------

    family = Family(
        family_name="Johnson Family"
    )

    db.add(family)
    db.commit()
    db.refresh(family)

    # -------------------------------------------------
    # Students
    # -------------------------------------------------

    emma = Student(
        family_id=family.id,
        name="Emma",
        grade_level="5th Grade"
    )

    noah = Student(
        family_id=family.id,
        name="Noah",
        grade_level="3rd Grade"
    )

    olivia = Student(
        family_id=family.id,
        name="Olivia",
        grade_level="1st Grade"
    )

    db.add_all([
        emma,
        noah,
        olivia
    ])

    db.commit()

    # -------------------------------------------------
    # Subjects
    # -------------------------------------------------

    math = Subject(
        family_id=family.id,
        name="Math",
        color="#4CAF50"
    )

    reading = Subject(
        family_id=family.id,
        name="Reading",
        color="#2196F3"
    )

    science = Subject(
        family_id=family.id,
        name="Science",
        color="#FF9800"
    )

    history = Subject(
        family_id=family.id,
        name="History",
        color="#9C27B0"
    )

    db.add_all([
        math,
        reading,
        science,
        history
    ])

    db.commit()

    # Refresh subject ids

    db.refresh(math)
    db.refresh(reading)
    db.refresh(science)
    db.refresh(history)

    # Refresh student ids

    db.refresh(emma)
    db.refresh(noah)
    db.refresh(olivia)

    # -------------------------------------------------
    # Assignments
    # -------------------------------------------------

    assignment1 = Assignment(
        family_id=family.id,
        subject_id=math.id,
        title="Math Lesson 32"
    )

    assignment2 = Assignment(
        family_id=family.id,
        subject_id=reading.id,
        title="Read Chapter 6"
    )

    assignment3 = Assignment(
        family_id=family.id,
        subject_id=science.id,
        title="Science Worksheet"
    )

    db.add_all([
        assignment1,
        assignment2,
        assignment3
    ])

    db.commit()

    db.refresh(assignment1)
    db.refresh(assignment2)
    db.refresh(assignment3)

    # -------------------------------------------------
    # Student Assignments
    # -------------------------------------------------

    db.add_all([

        StudentAssignment(
            assignment_id=assignment1.id,
            student_id=emma.id
        ),

        StudentAssignment(
            assignment_id=assignment1.id,
            student_id=noah.id
        ),

        StudentAssignment(
            assignment_id=assignment2.id,
            student_id=emma.id
        ),

        StudentAssignment(
            assignment_id=assignment3.id,
            student_id=olivia.id
        ),

    ])

    db.commit()

    db.close()

    print("✅ Seed data loaded successfully.")


if __name__ == "__main__":
    seed_database()