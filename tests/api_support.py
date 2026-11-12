"""
Helpers for the API tests. The api fixture in conftest.py signs people in
with tokens made by _token; Supabase is never called.
"""
import base64
import json


def _token(name, session_id="session-a"):
    """A token shaped like Supabase's, carrying a session_id claim."""
    claims = json.dumps({"sub": name, "session_id": session_id}).encode()
    payload = base64.urlsafe_b64encode(claims).decode().rstrip("=")
    return f"header.{payload}.signature"


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def as_(name, session_id="session-a"):
    """Headers for one of the api fixture's people: smith_parent, bob, jones_parent."""
    return _auth(_token(name, session_id))
