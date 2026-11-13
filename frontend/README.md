# Tally app

The new Tally app for web, iPhone and Android, built with Expo (React Native)
and Expo Router. It talks to the Tally API (`../api`) and uses Supabase only
for logging in.

## Running it

```bash
cp .env.example .env    # then fill in the Supabase URL and anon key
npm install
npm run web             # http://localhost:8081
npx expo start          # phones, with the Expo Go app
```

Before committing: `npm run typecheck` and `npm run lint`.

`EXPO_PUBLIC_API_URL` picks the API (the live one by default). The live API
allows calls from `http://localhost:8081` for local work.

## Layout

- `src/app/` screens (each file is a route): `login`, `index` (sends people
  to their start), `student/[id]` (a parent's look at one student's day),
  `missed-day`, `assignment/edit` (create, or edit with `?id=`),
  `assignment/notes`, `event/edit`, `exit-student-mode` (asks for the family
  PIN), and `(main)/` for the screens with the menu, whose `_layout` draws it
  (a sidebar on wide screens, a bottom tab bar on phones) and sends anyone to
  their start from a screen not on their menu. Students (their own login,
  Student Mode or a paired device) get `today` and the shared screens, which
  hide what only parents can do.
- `src/lib/nav.ts` the parent and student menus' groups and links
- `src/lib/` the API client, Supabase login, and the shapes the API returns
- `src/components/ui.tsx` shared building blocks; `form.tsx` choice chips, a
  date field with a month calendar, and a switch; `app-nav.tsx` the menu;
  `student-day.tsx` a student's day; `achievements.tsx` stat tiles and badges
- `src/constants/theme.ts` Tally's colours

`AGENTS.md` has Expo's notes for coding agents: use `npx expo install` to add
packages, and check the docs for this SDK version rather than memory.
