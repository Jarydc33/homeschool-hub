"""
The services load without Streamlit, so the API can reuse them.

Only the Streamlit plumbing below may import it. Those modules go when the
Streamlit app is retired.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STREAMLIT_ONLY = {
    "auth_service",
    "navigation_service",
    "session_service",
}


def _api_modules():
    names = [
        f"services.{path.stem}"
        for path in sorted((ROOT / "services").glob("*.py"))
        if path.stem != "__init__" and path.stem not in STREAMLIT_ONLY
    ]
    return ["config", "database.db", "database.models", *names]


def test_services_import_without_streamlit():
    modules = _api_modules()

    # A fresh interpreter, with Streamlit made impossible to import.
    script = (
        "import sys\n"
        "sys.modules['streamlit'] = None\n"
        f"for name in {modules!r}:\n"
        "    __import__(name)\n"
        "print('ok')\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip() == "ok"


def test_the_list_covers_every_service():
    # A new service is checked automatically; this just guards the glob.
    assert "services.current_user" in _api_modules()
    assert "services.assignment_service" in _api_modules()
