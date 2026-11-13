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

The links must stay in this form (see CLAUDE.md): the Streamlit app's
Complete Account page reads `token_hash` and `type` from the address, and
verifies it only when the password is submitted, since email scanners open
links. Until the switch-over, `{{ .SiteURL }}` is the Streamlit app. When the
new app takes over, change the links to its own invite and reset screens.

They're sent through Resend from `tally <hello@tallyhomeschool.com>`, an alias
of Jaryd's mailbox, so replies reach a person.
