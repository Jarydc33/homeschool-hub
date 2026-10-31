import os

from dotenv import load_dotenv

load_dotenv()

DEV_MODE = (
    os.getenv(
        "DEV_MODE",
        "False"
    ).lower()
    == "true"
)
