"""
The Tally API, which the new web and mobile app calls.

Run it locally from the project root:

    uvicorn api.main:app --reload

Then open http://127.0.0.1:8000/docs to try the endpoints.
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import me, occurrences, students

# The web app's addresses, comma-separated. The local defaults are Expo's
# web dev servers. Phone apps don't need to be listed: CORS only applies
# to browsers.
DEFAULT_ORIGINS = "http://localhost:8081,http://localhost:19006"

app = FastAPI(
    title="Tally API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("ALLOWED_ORIGINS", DEFAULT_ORIGINS).split(",")
        if origin.strip()
    ],
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "X-Device-Token"],
)


@app.get("/health", tags=["health"])
def health():
    """For the host's uptime checks. Needs no login and touches nothing."""

    return {"status": "ok"}


app.include_router(me.router)
app.include_router(students.router)
app.include_router(occurrences.router)
