# Sign-in email templates

The copies of the emails Supabase sends, kept here so changes are tracked.
Paste each file's HTML into Supabase: Authentication > Emails > Templates.
Supabase fills in `{{ .SiteURL }}`, `{{ .TokenHash }}`, `{{ .ConfirmationURL }}`
and `{{ .Email }}`. Confirm signup matters only while Supabase's "Confirm email"
setting is on; it keeps Supabase's own `{{ .ConfirmationURL }}` link, as before.
Changing a student's login email sends nothing: the app changes it directly.

| File | Supabase template | Subject |
| --- | --- | --- |
| `invite.html` | Invite user | You're invited to tally |
| `reset-password.html` | Reset Password | Reset your tally password |
| `confirm-signup.html` | Confirm signup | Confirm your email for tally |

The links must stay in this form: the new app's `complete-account` screen
reads `token_hash` and `type` from the address, and uses the token only when
the password is submitted, since email scanners open links. `{{ .SiteURL }}`
is https://app.tallyhomeschool.com (since the switch-over on 2026-11-13). The
Site URL and these links change together, or invites and resets break.

They're sent through Resend from `tally <hello@tallyhomeschool.com>`, an alias
of Jaryd's mailbox, so replies reach a person.
