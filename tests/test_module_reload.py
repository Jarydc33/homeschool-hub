"""The models keep working when Streamlit reloads modules during a deploy.

These run in a new process, because they need a fresh import and they remove
modules, which would disturb the other tests.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RELOAD_DURING_RUNNING_SCRIPT = """
import gc, sys
from sqlalchemy.exc import InvalidRequestError, OperationalError
from services import user_service

old_get_user = user_service.UserService.get_user_by_id

for name in list(sys.modules):
    if name == "database" or name.startswith(("database.", "services")):
        del sys.modules[name]
del user_service
gc.collect()

try:
    old_get_user(1)
except OperationalError:
    pass  # This test's database has no tables, which is fine here.
except InvalidRequestError as ex:
    sys.exit("mapper error: " + str(ex)[:200])
"""


def run(code):
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=dict(os.environ, DATABASE_URL="sqlite://", PYTHONUTF8="1"),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_relationships_are_linked_on_import():
    result = run(
        "from database.models import User\n"
        "import sys\n"
        "sys.exit(0 if User.__mapper__.configured else 'not linked on import')"
    )

    assert result.returncode == 0, result.stderr


def test_running_script_survives_a_reload():
    result = run(RELOAD_DURING_RUNNING_SCRIPT)

    assert result.returncode == 0, result.stderr
