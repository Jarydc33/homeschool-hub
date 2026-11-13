# Tally

Full name Tally Homeschool, shown as lowercase "tally" in the app, as in the brand design (logo and colours in `assets/` and `.streamlit/config.toml`). Tagline: Less logging, more learning. Formerly Homeschool Hub, which remains in the browser storage keys on purpose, since changing them would log everyone out, and in the repo address.

A homeschool management app: parents manage students, subjects and assignments; students see a daily dashboard and check off their work.

- **Stack:** Python, Streamlit (multipage), SQLAlchemy 2.x, Supabase (Postgres + Auth)
- **Live app:** https://tally-homeschool.streamlit.app (Streamlit Community Cloud)
- **Roadmap:** https://claude.ai/artifact/GJHnbvYc9TdaodQxVeD1dM
- **Domain:** tallyhomeschool.com (Namecheap, with Private Email at jaryd@tallyhomeschool.com). The API is live at https://api.tallyhomeschool.com (Render).
- **Migration (in progress, roadmap Phase 5):** moving off Streamlit to a FastAPI backend (keeps the SQLAlchemy models, services, Alembic and tests) and an Expo (React Native) frontend that builds the website, iOS and Android apps from one codebase. Supabase stays for the database and auth, so no data moves. Planned addresses: landing page at tallyhomeschool.com, app at app.tallyhomeschool.com, API at api.tallyhomeschool.com. The Streamlit app keeps running until the switch-over, so keep it working. Don't spend effort polishing the Streamlit look; the redesign happens in the new frontend.

## Current status

### Start here next session (left off 2026-11-13)

1. **From about 2026-11-20, start migration step 6 (removing the Streamlit code).** The switch-over was finished on 2026-11-13: Supabase's Site URL and email links, the landing page's buttons and student invites all go to https://app.tallyhomeschool.com, `https://app.tallyhomeschool.com/**` is in Supabase's Redirect URLs, `APP_MOVED_TO` is set so the Streamlit app shows "tally has moved" (except `Complete_Account`), the live site passed Jaryd's tests (sign-up, invite, reset, Student Mode, pairing), and the sister's family was told. First, once the week is up and old email links have expired, remove the Streamlit addresses from Supabase's Redirect URLs. Optional design polish any time: the Inter font in the app, bolder page headers, the Dashboard and Today screens.
2. **Point the landing page's buttons at the new app** once it's hosted at app.tallyhomeschool.com: the two lines in `landing/index.html`'s `LINKS` script (Log In and Get Started open the Streamlit app until then).

### Next step: the migration (decided 2026-11-12)

Parents hesitate to click a link containing "streamlit", and mobile apps were asked for, so the move comes before new features. Steps:

1. ~~Separate the services from Streamlit.~~ Done 2026-11-12. Identity is in `services/current_user.py` (an API request sets it with `CurrentUser.acting_as(user, auth_session_id)`), settings in `config.py`, and the rate limits keep their counts in plain memory (the pairing limit takes the caller's per-client list). `auth_provider.py` imports Streamlit only inside its three Streamlit-only methods. `tests/test_no_streamlit_in_services.py` fails if a service imports Streamlit.
2. ~~FastAPI backend (`api/`).~~ Endpoints done 2026-11-12: every Streamlit page's actions have one (72 endpoints; list them at `/docs`), with tests in `tests/test_api.py` and `tests/test_api_areas.py`. Login: Bearer Supabase token, or `X-Device-Token` for paired devices. The app itself logs in, resets passwords and completes invite links with Supabase's client; the API only signs up (`POST /register`). Before a parent signs out, the app calls `POST /logout` to end Student Mode. Hosted on Render at https://api.tallyhomeschool.com (service `tally-api`, also https://homeschool-hub-o9lx.onrender.com, an address kept from the service's first name; Starter plan; region Virginia, next to Supabase's North Virginia database; Namecheap CNAME `api` → the onrender address). Moved there from Oregon on 2026-11-13, since every query crossing the country made each request slow; keep the API in Supabase's region. Render builds with `pip install -r requirements-api.txt`, starts with `uvicorn api.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips="*"`, checks `/health`, and redeploys on every push to `main`. Its environment variables are the same four keys as Streamlit Cloud plus `PYTHON_VERSION` (3.13.5; align it with Streamlit Cloud and local 3.15 later). `DATABASE_URL` there must be Supabase's Session pooler string, since Render can't reach the IPv6-only direct address. Each request checks its login with one Supabase call, on a shared client (`SupabaseService.get_token_client`, only for `get_user(token)`). Later: `ALLOWED_ORIGINS` for the web app, and checking tokens locally with Supabase's signing keys to drop that call (a token then stays valid until it expires, up to an hour, even after logging out elsewhere).
3. Expo frontend (`frontend/`), in progress. Done 2026-11-12: login (Supabase email and password), the Student Dashboard with checking work on and off and new badges, the parent menu (sidebar on wide screens, bottom tab bar on phones; areas not rebuilt yet link to the Streamlit app) and the Parent Dashboard with "Missed a Day?". Also done 2026-11-12: Students and Subjects (add, edit, archive, restore; student logins and pairing come with Settings, as in the Streamlit app), and Assignments (list, create and edit on `assignment/edit`, notes for a date on `assignment/notes`, archive, restore). It runs on the web at http://localhost:8081 against the live API, which only accepts that port locally. Done 2026-11-13: Calendar, Events, Grades, Reading, P.E., Settings (family, PIN, devices, pairing codes), student logins on the Students screen, Student Mode (started from the Dashboard, left with the PIN), the student's side (their own menu in `(main)`, with Events and Grades read-only and parent screens redirected), the fuller student day (missed work, streaks, badges, the last 30 days' completed work; check-offs show at once and save in the background), and pairing a student's own device from the login screen (the key in `lib/device.ts`, unpaired with the PIN). Also done 2026-11-13: Announcements (an Admin gets only that screen), sign-up, Forgot Password and `complete-account`, which finishes invite and reset links on its own non-saving Supabase client, using the token only on submit. Hosted 2026-11-13 at https://app.tallyhomeschool.com: Render static site `tally-app` (also https://tally-app-3j1d.onrender.com), root directory `frontend`, build `npm ci && npm run build:web`, publish `dist`, a rewrite of `/*` to `/index.html`, and the `EXPO_PUBLIC_` settings plus `NODE_VERSION` 22 on Render; Namecheap CNAME `app` → the onrender address. The API allows it in `DEFAULT_ORIGINS` (`api/main.py`). Nobody is sent there yet: until the switch-over, the landing page's buttons, Supabase's Site URL and the email links all stay on the Streamlit app. Design pass done 2026-11-13: the sidebar is navy like the landing page, with each group under a divider and its heading on its links (`components/app-nav.tsx`; `Link asChild` drops a function style and crashes on a style list, so pass one flattened style). Next: the switch-over. Before going live, a proper UI/UX design pass (Jaryd, 2026-11-12): the screens so far are functional, not final.
4. ~~Sign-in emails from the domain.~~ Done 2026-11-13: Supabase sends through Resend's SMTP (`smtp.resend.com`, port 465, user `resend`, an API key named Supabase) as `tally <hello@tallyhomeschool.com>`, an alias of Jaryd's mailbox so replies reach him. The invite, reset and confirm signup templates are in `email-templates/`, pasted into Supabase by hand. All three tested: SPF, DKIM and DMARC pass. Supabase's Site URL and the templates' links still go to the Streamlit app; change them at the switch-over.
5. ~~Switch over.~~ Done 2026-11-13 (see "Start here"): set Supabase's Site URL to the new app; change the email templates' links from `/Complete_Account` to `/complete-account` (same `token_hash` and `type`; the Site URL and the links must change together, or invites and resets break); add the app's address to Supabase's Redirect URLs; change the Streamlit address in `AuthProvider.create_student_account`'s `redirect_to`; point the landing page's buttons at the app; redirect the Streamlit address; remove its Supabase redirect URLs.
6. Remove the Streamlit code, as its own step once the beta family is on the new app. Tag the last commit that has it (`streamlit-final`) first. Delete `app.py`, `pages/`, `components/navigation.py`, `components/browser_session/`, `.streamlit/`, `services/auth_service.py`, `session_service.py`, `navigation_service.py`, the Streamlit packages in `requirements.txt` (then maybe merge it with `requirements-api.txt`) and the "Streamlit gotchas" section here. Trim `auth_provider.py`'s Streamlit-only methods and `config.py`'s `st.secrets` fallback. Most tests that import Streamlit test services and stay: switch them to `CurrentUser.acting_as(...)` as the API tests do; drop only those testing Streamlit itself (such as `test_auth_pages.py`, `test_session_service.py`).
7. Later: app store releases (need in-app account deletion and a privacy policy).

Domain and DNS (Namecheap, settled 2026-11-13). The landing page is a Render static site (`landing/`, publish directory `landing`, no build) at https://tallyhomeschool.com: `@` is an A record → `216.24.57.1` and `www` a CNAME → `tally-l6wq.onrender.com`, which redirects to the bare domain. Mail Settings is Custom MX: `@` → `mx1.privateemail.com` and `mx2.privateemail.com` (priority 10). TXT: `@` SPF `v=spf1 include:spf.privateemail.com ~all`, `_dmarc` (`p=none`, reports to jaryd@), `privateemail._domainkey` (the mailbox's DKIM), `resend._domainkey` (Resend's DKIM). CNAMEs: `api` → the Render API, `app` → `tally-app-3j1d.onrender.com` (the web app), `send` → `send.forge.rmta.net` and `rsend` → `rsend.forge.rmta.net` (Resend's sending routes, from its dashboard). Pitfalls hit: switching Mail Settings to Custom MX drops Private Email's MX and SPF records, so re-add them; never put a CNAME or ALIAS on `@`, since it hides the MX, SPF and DMARC records there; a CNAME can't share a host with other records; and Host fields take only the part before the domain. Gmail "Show original" passes SPF, DKIM and DMARC for both the mailbox and Resend; a new domain lands in spam at first until it builds a reputation (mark it Not spam, reply). Later, once mail has passed for a while, consider DMARC `p=quarantine`.

### Deferred: hours tracking

Left off for now on 2026-11-12 (no feedback asked for it). Only P.E. logs time today (`activity_logs.minutes`), while the landing banner promises "homeschool hours and records that keep themselves". The approach agreed earlier, for when it comes back (schema still needs Jaryd's OK before the migration):

1. **Record on the assignment, report by subject.** A subject gets an optional usual time per day; an assignment can override it.
2. **Checking off saves the minutes** on that occurrence (`assignment_occurrences`), using the assignment's time or the subject's. They're stored at check-off, not worked out on read, so changing a subject's usual time later doesn't rewrite past hours (the same idea as grades). Parents can adjust a day's minutes; unchecking clears them.
3. **Totals** per student, subject, week, grading period and year, with a "core subject" flag on subjects, since some states count core hours separately (Missouri: 1,000 hours, 600 core). These feed the state report export later.
4. **Later, if needed:** a manual "Log time" entry (student, subject, date, minutes, note) for co-op classes or field trips. P.E. minutes count toward the P.E. subject so nothing is entered twice.

Build 1 to 3 first. Before starting, ask Jaryd what the sister said: her state's hours rules (including core subjects), and whether parents should trust the defaults or confirm minutes.

### Where things stand

- **Phase:** 0, 1 and 2 are complete. Phase 3 (launch-ready auth and private beta) is in progress, with the sister's family as the first beta family. Phase 5 (the migration) started early, on 2026-11-12; families moved to the new app on 2026-11-13.
- **Done:** Edit Assignment dialog crash, `update_assignment` wiping completion status, family checks in the student, subject, assignment and user services, pytest suite, family and system-wide announcements, archived students left out of lists and blocked from logging in, restoring students, Create Assignment form, no database setup on page load, Alembic with a baseline migration, `users.auth_user_id`, constraints and `family_id` indexes, session context manager, registration transaction, fetching the current user once per page run, `families.timezone`, occurrences table and date generator, writing occurrences when assignments are saved, dashboards and check-offs per date, per-date notes, dropping the old `student_assignments` progress columns, curriculum schedules, missed-day recovery, streaks and badges, events, calendar view, reading tracker, recent activity, daily message, scores and grades (not the subject health score), P.E. tracker, family settings (name and time zone), grouped sidebar, restoring subjects and assignments, Student Dashboard redesign (work first, today-only progress bar), Student Mode, pairing codes, security review and fixes (login limit, parent checks in services), version 1.0.0, branding (logo, colours, Inter, lowercase "tally"), parent feedback link
- **After the migration:** to be re-planned once it's done. Candidates: the second parent invite (Jaryd's wife joins his family), then whatever the sister's feedback asks for. Also closing an announcement once read (Jaryd, 2026-11-13): stored per person in a new table, against the student for any student view (own login, Student Mode or paired device) and the parent's login for parents, so it's closed on every device; closing only hides it for that person, and editing it doesn't bring it back. It's on the roadmap doc under Phase 5. Waiting on feedback: subject health score and bulk assignment creator. Moved later: opt-in leaderboard (Phase 3), accessibility options (Phase 5 redesign), spreadsheet importer (after Phase 5), state report export (pre-launch).
- **To discuss with Jaryd: pricing** (asked 2026-11-13). Nothing is decided and the landing page says nothing about price. Settle it before the public launch and the app store releases: free or paid, and whether by family or per student; whether beta families stay free; and how payment works on the web versus in the iPhone and Android apps, whose stores have their own rules for in-app subscriptions. Then add it to the landing page.
- **Questions for the sister's feedback:** was the Grades page clear, is the sidebar easy to use on a phone, did she use Student Mode or only pairing, and does her state require an hours log.
- Update this section when a phase or major item is finished.

## Running it

The project lives at `C:\Users\jaryd\code\homeschool_hub`, outside OneDrive since 2026-11-12 (OneDrive fought with Git and would sync the app's `node_modules`). The old OneDrive copy is retired. Use Python 3.14: the pinned packages don't all build on 3.15 yet. The virtual environment is `.venv`.

```bash
py -V:3.14 -m venv .venv          # once
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

The new app (`frontend/`, Node 22) has its own README: `npm install`, then `npm run web`. Its settings are in `frontend/.env` (see `.env.example`): only public values, never the service key.

The app doesn't create tables or sample data on its own. A brand-new database needs `python scripts/init_db.py` first (it runs the migrations, so it needs `requirements-dev.txt`), and optionally `python scripts/seed_data.py` for sample data (it does nothing if a family already exists). Both use whatever `DATABASE_URL` points to, so check it first.

The API runs locally with `pip install -r requirements-api.txt` and `uvicorn api.main:app --reload`; its endpoint docs are at http://127.0.0.1:8000/docs. It uses whatever `DATABASE_URL` points to, so check it before calling endpoints that read or write data. `ALLOWED_ORIGINS` (comma-separated) lists the web app addresses allowed to call it.

Tests run on a temporary SQLite database, never Supabase:

```bash
pip install -r requirements-dev.txt
pytest
```

Schema changes use Alembic, run by hand from the project root against whatever `DATABASE_URL` points to. Deploys don't run them, so migrate before pushing code that needs the change. Dropping something is the reverse: deploy the code that stops using it first, then migrate:

```bash
alembic revision --autogenerate -m "Describe the change"   # then read and fix the generated file
alembic upgrade head --sql                                 # review the SQL without running it
alembic upgrade head
```

`migrations/env.py` enables RLS on any `public` table that lacks it after every run, so migrations don't need to. Keep migrations working on both Postgres and SQLite, since the tests run them on SQLite.

Config is read by `config.get_setting()`: environment variables or `.env` first, then `st.secrets` on Streamlit Cloud (`.streamlit/secrets.toml`, never committed):

| Key | Used for |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy connection to Supabase Postgres (the `postgres` user) |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Anon key, used only for auth calls |
| `SERVICE_KEY` | Service-role key, used only for admin auth (student invites and login email changes). Server-side only |

Never print, log, or commit any of these values.

## Layout

```
app.py                  Router: sends users to the landing page or a dashboard
landing/                The landing page for tallyhomeschool.com: plain HTML (index.html), no build. Log In and Get Started go wherever its LINKS script says
email-templates/        Supabase's sign-in emails (invite, reset, confirm signup), pasted into Supabase by hand
frontend/               Expo app (web, iOS, Android): src/app (screens), src/lib (API client, login), see frontend/README.md
api/                    FastAPI backend for the new app: main.py (app), auth.py (who's calling: signed_in, require_parent), errors.py, schemas.py (shared response shapes), routers/ (one file per area)
config.py               Settings from environment variables, falling back to st.secrets
pages/                  One file per Streamlit page (emoji filenames, e.g. "✅_Assignments.py")
components/navigation.py  Sidebar nav (grouped links per role) + logout
services/               All business logic and DB access (static-method classes)
  auth_provider.py      Supabase Auth calls (login, register, invite, set password)
  current_user.py       Who's making the request (role, family, student, today), with no Streamlit. Services use this
  auth_service.py       Streamlit login and session: finds the user for CurrentUser outside an API request
  account_service.py    Sign-up, student invites and login email changes (Supabase and users together)
  session_service.py    Access token in browser localStorage (via components/browser_session)
  navigation_service.py Page guards: require_authentication / require_parent / require_student
  *_service.py          One service per entity or feature
database/db.py          Engine, SessionLocal, Base
database/models.py      ORM models + enums (UserRole, AssignmentStatus, AssignmentType, RecurrencePattern)
migrations/             Alembic environment and migration files
scripts/                One-off scripts (init_db, seed_data, test_connection). Never run them from pages
tests/                  pytest suite for the services
```

## How data flows

- Pages call services. Services open a SQLAlchemy session, query, and return ORM objects. Pages never query the DB directly.
- API endpoints call the same services, inside `Depends(signed_in)`, which runs the request as that user through `CurrentUser`. They turn ORM objects into the Pydantic shapes in `api/schemas.py` and never return ORM objects or query the DB directly. Services list whole-family data even for students (the Streamlit pages only show a student their own), so an endpoint a student can call must narrow it, as `GET /students` does.
- Data goes through SQLAlchemy as the `postgres` user, so **Supabase RLS does not apply to app queries**. Keeping families apart is the service layer's job. RLS is enabled with no policies only to block Supabase's REST API.
- Supabase is used for **auth only**. The app's `users` table links to Supabase accounts by `users.auth_user_id` (UUID), which is required and unique. Identify people by it, never by email; email is only how they sign in. Anything that creates a `users` row needs the account's UUID first, including an Admin added by hand.
- Every page starts with `NavigationComponent.render()` and then a guard from `NavigationService`.
- `student_assignments` only says who is assigned. `assignment_occurrences` holds one row per assignment, per student, per date, with its status, completion time, notes and score. Rows are created when an assignment is saved, never on page load. "Missed" is worked out when read, never stored.
- A curriculum is an assignment of type "Curriculum" with one row per lesson, per student. `lesson_number` stays with the lesson when its date moves, `recurrence_pattern` holds the school days ("Mon,Tue"), and the lesson count and finish date come from the rows. Unfinished lessons stay overdue. Each student's dates can differ. "Missed a Day?" on the parent dashboard moves only unfinished lessons, for the chosen students; other assignment types don't shift.
- Streaks and badges are worked out from occurrences when read, never stored (`services/achievement_service.py`). A day counts once all its work is done, whenever that happens. Days with no work don't count or break a streak.
- Events belong to a family. With no `event_students` rows, one is for the whole family, including students added later. Repeating events' dates are worked out when read, and an edit applies to the whole series.
- Books belong to one student, and `reading_logs` holds one row per book, per date. The reading streak is separate from the assignment streak and counts every calendar day. Reading totals and badges are worked out when read.
- Grades: an occurrence's `score` is points earned, out of its `points_possible`, on assignments marked `graded`. Percentages and letters are worked out when read. A blank score never counts, not even as zero. A grade belongs to the `grading_periods` row its date falls in, and periods can't overlap. Archived assignments and subjects still count, as a deliberate exception to rule 3, so tidying up doesn't change a past semester.
- P.E.: `activity_logs` holds one row per activity, per student, per date, and several can share a date. A mistaken entry is deleted, not archived, as a deliberate exception to rule 3, since it's a correction, not a record. There's no P.E. streak; totals, active days and hour badges are worked out when read.
- Student Mode: a parent's login switched to one student's view. `device_sessions` ties it to the Supabase `session_id` claim in the login token, so the server decides the mode and clearing the browser can't end it. While a row is active (`revoked_at` empty), `CurrentUser.is_student()` is true, `is_parent()` is false, and `get_student_id()` returns that student, so pages and services need no special cases. Leaving needs the family PIN (`families.parent_pin_hash`, bcrypt, exactly 4 digits); 5 wrong tries lock it for 5 minutes. Logging out ends it without the PIN, since getting back in needs the parent's password. Students in Student Mode have no `users` row.
- Paired devices: a student's own device, with no login. A parent makes a one-time 6-digit code (`pairing_codes`, hashed, 10 minutes); redeeming it saves a random device key in the browser (`homeschoolhub_device`) and its SHA-256 in `device_sessions.token_hash` (mode "paired", no `auth_session_id`). With no Supabase login, `AuthService` turns a valid key into a `PairedUser`, which stands in for a `users` row so the role helpers work as usual. Unpairing needs the family PIN; parents end devices from Settings, and archiving the student ends them too. Wrong codes are limited per browser session and app-wide, in memory, because every request reaches the app from the same server.
- Announcements (`banner_messages`) belong to a family, or are system-wide when `family_id` is NULL. Parents manage their family's; Admins (`users.role = 'Admin'`, no family, a separate login) manage system-wide ones and only see the Announcements page.

## Rules (follow these on every change)

1. **Scope everything to the family.** Every service function that reads or changes a row by ID must also filter by the current family's `family_id`, e.g. `filter(Student.id == student_id, Student.family_id == family_id)`. Creates must check that referenced subjects and students belong to the same family. Never call or add unscoped helpers (like the removed `get_all_*`) for pages to use.
2. **Never trust the page for identity.** Services get the role, family, and student from `CurrentUser` (pages may use `AuthService`, which forwards to it), never from widget values, query params or request bodies. Services never import `AuthService` or Streamlit, so the API can reuse them. Parent-only changes also check `CurrentUser.is_parent()` in the service, so a missing page guard can't let a student (or Student Mode) make them.
3. **Archive, don't delete.** Entities use `active` / `is_active` soft deletes. Every list a user sees filters out archived rows, including joined ones such as archived assignments on the student dashboard.
4. **Keep completion history.** Never delete and recreate `StudentAssignment` rows (or occurrence rows) to apply an edit; add and remove only what changed.
5. **One transaction per user action.** Multi-step writes (registration, creating an assignment with its student links) commit once.
6. **No side effects on page load.** No `create_all()`, seeding, or migrations from pages.
7. **Schema changes go through Alembic migrations.** Never use `create_all()` outside tests.
8. **Dates:** "today" means the family's local date, not the server's UTC date. Use `CurrentUser.get_today()` (or `AuthService.get_today()` on pages), never `date.today()`, including for date picker defaults.
9. **User-facing errors are friendly.** Don't show `str(ex)` to users; log the detail instead.

## Streamlit gotchas we've hit

- Widgets inside `st.form` don't rerun until submit, so one widget can't enable or disable another inside the same form. Put the controlling widget outside the form.
- Always put `type="password"` inputs in an `st.form`. Outside one, pressing Tab moves focus to the box's "Show password" icon, Streamlit doesn't send the value, and the server sees an empty password while the box shows it filled in.
- When deployed files change, Streamlit reloads every project module while other scripts may still be running. Don't assume a module's objects stay valid across a deploy. `database/models.py` calls `configure_mappers()` for this reason. If a live error appears right after a push and a fresh start doesn't show it, try rebooting the app.
- ORM objects returned after `db.close()` can raise `DetachedInstanceError` on lazy relationships. Eager-load with `joinedload`, or use a session with `expire_on_commit=False`.
- Browser writes run after the script does, so `st.rerun()` or `st.switch_page()` right after one can cancel it. That's why `SessionService` queues writes and stops the script until `components/browser_session` confirms. Follow `save_session` or `clear_session` with a rerun or page change, and let `NavigationComponent.render()` finish the write.
- Supabase refresh tokens work once. Keep `auto_refresh_token=False` on clients, or a background timer uses up the token saved in the browser and ends the login. After a refresh, the new tokens must reach the browser before anything else happens.
- Supabase email links (invite, password reset) put tokens in the URL fragment by default, and Streamlit's server can't read the fragment. Fix: use the `token_hash` email template, read `st.query_params`, and call `verify_otp` on submit, not on page load, because tokens work once and email scanners open links. Act only on the link's token, never a saved login, and set the password on the client that verified it.
- `st.session_state` is per browser tab session and is lost on a refresh. Persistent login comes from the stored tokens.

## Known open items (see the roadmap for the full list)

- Logging out in one tab doesn't end the session in another open tab until that tab is refreshed.
- The web app keeps its size when an open window is resized (seen 2026-11-13: narrowing a wide window left the page and bottom bar in a small box). A refresh fixes it, and a fresh load at any size is right. Check rotating a phone or tablet before the app store releases, since that's a resize too.
- Archived students can't log in (`AuthService.get_current_user` blocks them) until a parent restores them on the Students page. Subjects and assignments are restored on their own pages. Books and events can't be restored yet.
- Invites and password resets depend on Supabase's email templates. "Invite user" must link to `{{ .SiteURL }}/Complete_Account?token_hash={{ .TokenHash }}&type=invite`, and "Reset Password" to the same address with `type=recovery`.
- Changing a student's login email has to update Supabase and `users` together, because people sign in with Supabase's copy and the app shows its own. `AuthService.update_student_email` handles this. Supabase refuses an email another account already has. Parents can't change their own email yet.

## Working style

- Make small, focused changes, one roadmap item at a time, and explain what changed and why.
- Before a schema change, a data migration, or anything destructive in Supabase, stop and confirm first.
- Add or update pytest tests for service changes, including a check that one family can't read another family's data.
