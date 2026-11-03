# Homeschool Hub

A homeschool management app: parents manage students, subjects and assignments; students see a daily dashboard and check off their work.

- **Stack:** Python, Streamlit (multipage), SQLAlchemy 2.x, Supabase (Postgres + Auth)
- **Live app:** https://homeschool-app.streamlit.app (Streamlit Community Cloud)
- **Roadmap:** https://claude.ai/artifact/GJHnbvYc9TdaodQxVeD1dM
- **Long-term plan:** move off Streamlit to our own site and domain (roadmap Phase 2). Prefer work that carries over: schema, services, tests. Keep Streamlit-specific plumbing minimal.

## Current status

- **Phase:** 0 (bug fixes and Streamlit stopgaps)
- **Done:** Edit Assignment dialog crash, `update_assignment` wiping completion status, family checks in the student, subject, assignment and user services, pytest suite, family and system-wide announcements
- **Next up (Phase 0):** remove `create_all()` and seeding from the Parent Dashboard
- Update this section when a phase or major item is finished.

## Running it

```bash
pip install -r requirements.txt
streamlit run app.py
```

Tests run on a temporary SQLite database, never Supabase:

```bash
pip install -r requirements-dev.txt
pytest
```

Config comes from `.env` locally, or from `st.secrets` on Streamlit Cloud (`.streamlit/secrets.toml`, never committed):

| Key | Used for |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy connection to Supabase Postgres (the `postgres` user) |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Anon key, used only for auth calls |
| `SERVICE_KEY` | Service-role key, used only for admin auth (student invites). Server-side only |
| `DEV_MODE` | `true` shows impersonation buttons on Login. Must be false in production |

Never print, log, or commit any of these values.

## Layout

```
app.py                  Router: sends users to the landing page or a dashboard
config.py               DEV_MODE flag
pages/                  One file per Streamlit page (emoji filenames, e.g. "✅_Assignments.py")
components/navigation.py  Sidebar nav + logout
services/               All business logic and DB access (static-method classes)
  auth_provider.py      Supabase Auth calls (login, register, invite, set password)
  auth_service.py       Current user, role, and family from session state
  session_service.py    Access token in browser localStorage (streamlit-local-storage)
  navigation_service.py Page guards: require_authentication / require_parent / require_student
  *_service.py          One service per entity
database/db.py          Engine, SessionLocal, Base
database/models.py      ORM models + enums (UserRole, AssignmentStatus, AssignmentType, RecurrencePattern)
scripts/                One-off scripts (init_db, seed_data, test_connection). Never run them from pages
tests/                  pytest suite for the services
```

## How data flows

- Pages call services. Services open a SQLAlchemy session, query, and return ORM objects. Pages never query the DB directly.
- Data goes through SQLAlchemy as the `postgres` user, so **Supabase RLS does not apply to app queries**. Keeping families apart is the service layer's job. RLS is enabled with no policies only to block Supabase's REST API.
- Supabase is used for **auth only**. The app's `users` table links to Supabase users by email for now. Moving to `users.auth_user_id` (UUID) is planned for Phase 1.
- Every page starts with `NavigationComponent.render()` and then a guard from `NavigationService`.
- Announcements (`banner_messages`) belong to a family, or are system-wide when `family_id` is NULL. Parents manage their family's; Admins (`users.role = 'Admin'`, no family, a separate login) manage system-wide ones and only see the Announcements page.

## Rules (follow these on every change)

1. **Scope everything to the family.** Every service function that reads or changes a row by ID must also filter by the current family's `family_id`, e.g. `filter(Student.id == student_id, Student.family_id == family_id)`. Creates must check that referenced subjects and students belong to the same family. Never call or add unscoped helpers (like the removed `get_all_*`) for pages to use.
2. **Never trust the page for identity.** Get the role, family, and student from `AuthService`, not from widget values or query params.
3. **Archive, don't delete.** Entities use `active` / `is_active` soft deletes. Every list a user sees filters out archived rows, including joined ones such as archived assignments on the student dashboard.
4. **Keep completion history.** Never delete and recreate `StudentAssignment` rows (or occurrence rows) to apply an edit; add and remove only what changed.
5. **One transaction per user action.** Multi-step writes (registration, creating an assignment with its student links) commit once.
6. **No side effects on page load.** No `create_all()`, seeding, or migrations from pages.
7. **Schema changes go through migrations** once Alembic is added (Phase 1). Don't rely on `create_all()` to change existing tables.
8. **Dates:** "today" means the family's local date, not the server's UTC date (Phase 1 adds `families.timezone`).
9. **User-facing errors are friendly.** Don't show `str(ex)` to users; log the detail instead.

## Streamlit gotchas we've hit

- Widgets inside `st.form` don't rerun until submit, so one widget can't enable or disable another inside the same form. Put the controlling widget outside the form.
- ORM objects returned after `db.close()` can raise `DetachedInstanceError` on lazy relationships. Eager-load with `joinedload`, or use a session with `expire_on_commit=False`.
- `streamlit-local-storage`: each `setItem` call in one run needs its own `key=` argument, or Streamlit raises a duplicate key error.
- Supabase email links (invite, password reset) put tokens in the URL fragment by default, and Streamlit's server can't read the fragment. Fix: use the `token_hash` email template, read `st.query_params`, call `verify_otp`.
- `st.session_state` is per browser tab session and is lost on a refresh. Persistent login comes from the stored tokens.

## Known open items (see the roadmap for the full list)

- `AuthService.logout()` is a stub, and the refresh token isn't stored yet.
- Archived students can't log in (`AuthService.get_current_user` blocks them) until a parent restores them on the Students page. Subjects and assignments can't be restored from the app yet.
- The student invite flow (`Complete_Account`) doesn't work yet (URL fragment issue above).
- Recurring assignments use a single status per student. The occurrence model (one row per assignment, per student, per date) is planned for Phase 1.
- Student Mode (a parent's device locked to one student, with a parent PIN to exit) and pairing codes for kids without email are designed but not built (roadmap Phase 2).

## Working style

- Make small, focused changes, one roadmap item at a time, and explain what changed and why.
- Before a schema change, a data migration, or anything destructive in Supabase, stop and confirm first.
- Add or update pytest tests for service changes, including a check that one family can't read another family's data.
