# Homeschool Hub

A homeschool management app: parents manage students, subjects and assignments; students see a daily dashboard and check off their work.

- **Stack:** Python, Streamlit (multipage), SQLAlchemy 2.x, Supabase (Postgres + Auth)
- **Live app:** https://homeschool-app.streamlit.app (Streamlit Community Cloud)
- **Roadmap:** https://claude.ai/artifact/GJHnbvYc9TdaodQxVeD1dM
- **Long-term plan:** move off Streamlit to our own site and domain (roadmap Phase 2). Prefer work that carries over: schema, services, tests. Keep Streamlit-specific plumbing minimal.

## Current status

- **Phase:** 0 (bug fixes and Streamlit stopgaps) is complete. Phase 1 is next
- **Done:** Edit Assignment dialog crash, `update_assignment` wiping completion status, family checks in the student, subject, assignment and user services, pytest suite, family and system-wide announcements, archived students left out of lists and blocked from logging in, restoring students, Create Assignment form, no database setup on page load
- **Next up:** the first Phase 1 item on the roadmap
- Update this section when a phase or major item is finished.

## Running it

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app doesn't create tables or sample data on its own. A brand-new database needs `python scripts/init_db.py` first, and optionally `python scripts/seed_data.py` for sample data (it does nothing if a family already exists). Both use whatever `DATABASE_URL` points to, so check it first.

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

Never print, log, or commit any of these values.

## Layout

```
app.py                  Router: sends users to the landing page or a dashboard
pages/                  One file per Streamlit page (emoji filenames, e.g. "✅_Assignments.py")
components/navigation.py  Sidebar nav + logout
services/               All business logic and DB access (static-method classes)
  auth_provider.py      Supabase Auth calls (login, register, invite, set password)
  auth_service.py       Current user, role, and family from session state
  session_service.py    Access token in browser localStorage (via components/browser_session)
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
- When deployed files change, Streamlit reloads every project module while other scripts may still be running. Don't assume a module's objects stay valid across a deploy. `database/models.py` calls `configure_mappers()` for this reason. If a live error appears right after a push and a fresh start doesn't show it, try rebooting the app.
- ORM objects returned after `db.close()` can raise `DetachedInstanceError` on lazy relationships. Eager-load with `joinedload`, or use a session with `expire_on_commit=False`.
- Browser writes run after the script does, so `st.rerun()` or `st.switch_page()` right after one can cancel it. That's why `SessionService` queues writes and stops the script until `components/browser_session` confirms. Follow `save_session` or `clear_session` with a rerun or page change, and let `NavigationComponent.render()` finish the write.
- Supabase refresh tokens work once. Keep `auto_refresh_token=False` on clients, or a background timer uses up the token saved in the browser and ends the login. After a refresh, the new tokens must reach the browser before anything else happens.
- Supabase email links (invite, password reset) put tokens in the URL fragment by default, and Streamlit's server can't read the fragment. Fix: use the `token_hash` email template, read `st.query_params`, and call `verify_otp` on submit, not on page load, because tokens work once and email scanners open links. Act only on the link's token, never a saved login, and set the password on the client that verified it.
- `st.session_state` is per browser tab session and is lost on a refresh. Persistent login comes from the stored tokens.

## Known open items (see the roadmap for the full list)

- Logging out in one tab doesn't end the session in another open tab until that tab is refreshed.
- Archived students can't log in (`AuthService.get_current_user` blocks them) until a parent restores them on the Students page. Subjects and assignments can't be restored from the app yet.
- Invites and password resets depend on Supabase's email templates. "Invite user" must link to `{{ .SiteURL }}/Complete_Account?token_hash={{ .TokenHash }}&type=invite`, and "Reset Password" to the same address with `type=recovery`.
- A parent can't change a student's login email yet, so an invite sent to a mistyped address needs a manual fix. This is easier once `users.auth_user_id` exists (Phase 1).
- Recurring assignments use a single status per student. The occurrence model (one row per assignment, per student, per date) is planned for Phase 1.
- Student Mode (a parent's device locked to one student, with a parent PIN to exit) and pairing codes for kids without email are designed but not built (roadmap Phase 2).

## Working style

- Make small, focused changes, one roadmap item at a time, and explain what changed and why.
- Before a schema change, a data migration, or anything destructive in Supabase, stop and confirm first.
- Add or update pytest tests for service changes, including a check that one family can't read another family's data.
