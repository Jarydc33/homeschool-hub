import os
import sys

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)


from database.db import Base, engine
from database.models import *

def initialize_database():
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized successfully.")


if __name__ == "__main__":
    initialize_database()