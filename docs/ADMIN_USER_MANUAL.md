# QUATA Digital — Admin user manual

A quick guide for non-technical admins. Everything below assumes you are
signed in at `https://quatadigital.com/admin` with an account that has the
right permissions.

---

## 1. Sign in

1. Open `https://quatadigital.com/admin/login`.
2. Enter your work email + password.
3. If 2FA is set up, enter the 6-digit code from your authenticator app.
4. **First-time only:** you'll be asked to set a new password and (if you're a super admin) enrol 2FA. Save the 8 recovery codes shown — they are the only way back in if you lose your phone.

Forgot password? `https://quatadigital.com/admin/forgot-password`. A reset
link is emailed to you. The link expires after 30 minutes.

After 5 failed login attempts your account locks for 15 minutes. Wait it out
or ask the engineering on-call to clear it.

---

## 2. Daily admin tasks

### 2.1 Review partner submissions

`/admin/partners`

- Filter by **type** (business / strategic / investor / service) and **status** (new / in_review / approved / rejected).
- Click a row to open the side panel and read the full submission.
- Add internal **notes** (only visible to staff).
- Set a status — the applicant receives an email automatically when you move them to **approved** or **rejected**.

Export everything to CSV from the toolbar at any time.

### 2.2 Reply to a contact-form message

`/admin/contact` is reachable from the Pipeline group in the sidebar (under
Partner requests on small layouts; it's surfaced through the dashboard tile if you can't find the link).

- Click an email address to open your mail client and reply directly.
- Mark the row as **handled** when done — keeps the queue clean.

### 2.3 Review job applications

`/admin/careers`

- Filter by status (new / shortlisted / interviewed / rejected / hired) and job.
- Click an applicant to view their resume + cover note.
- Set a status — the applicant gets an automatic email on shortlist / reject / hire.

### 2.4 Newsletter

`/admin/newsletter`

- See total + active subscriber counts at the top.
- Filter by `is_active` or search by email.
- Export the active list to CSV (use this as the import file when you're ready to mail-merge from your ESP).
- Delete spam signups.

---

## 3. Publishing content

### 3.1 Write a blog post

`/admin/cms` → **New post**.

1. **Title** — what shows in search results.
2. **Slug** — auto-generated from the title; edit only if you must.
3. **Excerpt** — 1–2 sentences shown on the blog index.
4. **Cover image** — upload a 1600×900 photo.
5. **Body** — Markdown. Use the **Preview** tab to see how it'll look.
6. **Category** — Company / Product / Insight / News / Press.
7. Toggle **Published** and click **Save**.

Drafts are visible only to staff. Published posts are live immediately on `/blog`.

### 3.2 Edit a CMS page

`/admin/cms` → **Pages** tab.

Same flow as a blog post. Used for `/about`, `/security`, `/privacy`, `/terms`. Be careful — these pages are legal-bearing.

### 3.3 Edit a product page

`/admin/products`. Edit the tagline, description, status badge (live / beta / coming_soon / planned), category, highlights and feature list per product. The seven products are seeded — you can edit them, but you generally shouldn't add or delete them.

### 3.4 Post a job

`/admin/careers` → **New job**.

1. **Title**, **department**, **location**, **employment type**.
2. **Summary** (shown on the careers index) and **description** (full body, Markdown).
3. **Responsibilities** and **requirements** as bullet lists.
4. Toggle **Published**.

The job appears immediately on `/careers`.

---

## 4. Managing people

### 4.1 Invite a new staff member

`/admin/staff` → **Invite**.

1. Enter their work email + name.
2. Pick a **role** (controls what they can do — see §5).
3. Optionally set a **department** and **biometric ID** (for the attendance device mapping).
4. Click **Send invite** — they receive an email with a one-time setup link to set their password.

Newly invited users are forced to reset their password on first login (`must_reset_password=true`).

### 4.2 Change someone's role

`/admin/staff` → click the row → **Edit** → change role → save.

The role determines their permissions globally. The change is logged in the activity feed.

### 4.3 Suspend or remove

- **Suspend** = soft delete. They can't log in but their history is preserved (`is_active=false`, `status=suspended`).
- Use suspend in 99% of cases. True deletion is destructive.
- You can't suspend yourself — the API blocks it.

### 4.4 Restore something deleted by mistake

Most resources soft-delete (products, blog posts, pages, jobs, applications, partner requests, departments, devices, staff). The trash list is exposed via the API at `/api/v1/admin/trash/{resource}` — engineering can surface a UI on request, but the safe route today is to ping engineering with the resource type + ID. Restoration is one POST.

---

## 5. Roles & permissions

| Role | What they can do |
|---|---|
| **super_admin** | Everything. Reserved for the founder + CTO. **Required** to enrol 2FA. |
| **admin** | All content, partners, careers, staff, RBAC, devices, activity, analytics, newsletter. Can also answer WhatsApp customers. |
| **support** | **Answer WhatsApp customers, and nothing else.** See §6.9. |
| **manager** | Partners, careers, staff, analytics. No RBAC, no devices. |
| **team_lead** | Partners, careers (read + edit). |
| **staff / intern / contractor** | Self-service only — log in, request leave, clock in/out, edit own profile. |

To change permissions per role: `/admin/roles`. Tick / untick the permission boxes per role.

The `super_admin` role is **immutable** — you can't change its permissions and you can't delete it. By design.

The 12 permission keys are: `content:manage`, `partners:manage`, `careers:manage`,
`staff:manage`, `rbac:manage`, `devices:manage`, `activity:view`,
`analytics:view`, `newsletter:manage`, `settings:manage`, `whatsapp:operate`,
`whatsapp:agent`. (`*` — "everything" — exists too, and only the founder holds it.)

Two of those reach beyond this website into the whole QUATA fleet, so they are
kept separate on purpose:

- **`whatsapp:operate`** switches the WhatsApp numbers on and off, issues a
  product's gateway key, and grants a product the right to send login codes.
  Only the founder holds it. If a number gets restricted by Meta, QUATAFOOD
  users cannot log in at all — that login code has no email backup.
- **`whatsapp:agent`** is the support desk and nothing more: pick up a waiting
  customer, read the conversation, reply, hand it back. It changes no setting,
  no number, no key. This is what the **support** role is.

**Staffing the support desk:** invite the person as normal (§4.1) and pick the
**support** role. An Admin can do this; you do not need the founder. They will
be asked to enrol 2FA on first login like everybody else.

**The founder can read the queue but cannot pick a conversation up.** That is
deliberate, not a bug — a master key is not the same as being on shift, and it
stops a customer conversation being parked on the boss's name where nobody
works it. If the founder genuinely needs to answer customers, give that person
a second account on the **support** role.

---

## 6. Other modules

### 6.1 Internal messaging

`/admin/messages` — send a note to all staff, a single department, or one
person. Recipients see it instantly via the WebSocket connection (notifications dropdown lights up) plus on next page load.

### 6.2 Leave management

- Staff request leave from `/admin/leave`.
- Managers approve / reject — staff get an email automatically.
- Drag a leave bar to reschedule (the API supports `PATCH /admin/leave/{id}/dates`).

### 6.3 Attendance

`/admin/attendance`. Shows daily check-in / check-out per staff. Data flows
in from biometric devices, GPS check-ins, or web self-service.

### 6.4 Devices

`/admin/devices`. Add a biometric device — copy the API token shown **once**, paste into the device. Rotate the token from the same page if it's ever compromised.

If the device firmware supports HMAC, set `DEVICE_REQUIRE_SIGNATURE=true` on the backend and configure the device to sign each request — it adds a second
layer of protection beyond the static token.

### 6.5 Activity log

`/admin/activity`. Every important action is recorded — who did what, when, on what resource, from what IP, with a JSON details blob. Filter by actor, action, resource type, and date range.

Old rows are pruned automatically: 90 days for activity, 180 days for page views (configurable via `ACTIVITY_LOG_RETENTION_DAYS` / `PAGE_VIEW_RETENTION_DAYS`).

### 6.6 Analytics

`/admin/analytics`. Anonymous page-view counts per page, per day, plus a
14-day time series for visits / partner requests / job applications. Only
visitors who accept the cookie banner are counted.

### 6.7 Alert centre (Telegram)

`/admin/alerts` — the control room for **@QuataAlertsBot**, which reports
everything important across QuataPay, QuataFood, Abaqwa, QuataTrade, QUATA AI
and this website into Telegram. Needs the `settings:manage` permission.

**First-time setup, in order:**

1. Paste the bot token under **Site settings → Integrations → Telegram bot
   token**. Use the token for the existing @QuataAlertsBot — never create a
   new bot.
2. Come back to **Alert centre → Delivery** and click **Test connection**.
   Green means Telegram recognises the token.
3. Add who receives alerts under **Recipients**. Message @QuataAlertsBot from
   your Telegram account first (or add it to your ops group and post once),
   then ask engineering to run `python -m app.scripts.telegram_chats` — it
   prints the chat ids to paste in.
4. Click **Send test notification**. If it lands in Telegram, you're live.

**The four tabs:**

- **Delivery** — the master on/off switch, the minimum priority to send, the
  large-transaction threshold, the daily-summary time, and the alert
  thresholds for CPU / memory / disk. Also the two test buttons and a
  preview of the daily report.
- **Platforms & events** — turn a whole product off (say QuataFood is in
  maintenance and you don't want its noise), or turn off a category of event
  across every product. Security and infrastructure are flagged — think twice
  before switching those off.
- **Recipients** — who is authorised. Each one can be limited to a minimum
  priority, specific platforms, or specific categories. Give the CEO's chat
  🔴 CRITICAL only and the ops group everything. **Pause** stops alerts
  without losing the configuration; **delete** removes access entirely.
- **Logs** — every notification ever sent, with search and filters. Click any
  row to see the exact message, who received it, and any error. Failed ones
  have a **Retry** button.

**Things worth knowing:**

- Turning notifications off does **not** stop events being recorded. They're
  all in Logs, marked `suppressed` with the reason. Nothing is lost.
- If an alert didn't arrive, open Logs and find it — the row says exactly
  why (platform off, category off, priority too low, no matching recipient,
  or a Telegram error).
- Alerts never contain passwords, OTPs, PINs, API keys or tokens. Account
  numbers are shown masked (`12••••••••••3456`). This is enforced in code,
  not by convention.
- A **missing daily summary** is itself a signal — it means the notification
  worker is down. Tell engineering.

### 6.8 My settings

`/admin/settings`. Update your profile (name, phone, avatar, job title), change your password, and enrol or disable 2FA. Notification preferences also live here.

### 6.9 WhatsApp support desk (QCP)

**Status today: switched off.** Both WhatsApp numbers are inactive, no product
is connected, and the AI is off. Nothing in this section is sending or
answering anything right now. It is written so that whoever switches it on
knows what has to be true first.

**What it is.** QUATA runs two WhatsApp numbers and they do different jobs:

- **Quata Verify** — login codes and security codes only. No support, no
  marketing, no AI, ever. Meta restricts a number that mixes the two, and if
  Verify gets restricted, QUATAFOOD users cannot log in.
- **QUATA** — everything else: support, order updates, promotions, and the AI.

**What the AI is allowed to do.** Answer simple, general questions (opening
hours, where to download an app, how something works). The moment a customer's
message touches **money, an identity check, a refund, a complaint, fraud or
anything legal**, it stops, does not answer, and puts the conversation in the
human queue. It also stops if the customer asks for a person, if it is unsure,
if the same question comes back a third time, or if the message is in a
language other than English or French. It never quotes a balance, an order
status or a verification decision, because it does not look those up — it
would be guessing, and a guess about somebody's money is worse than silence.

#### Before you switch it on — the three things that must be true

If any of these is missing, the feature will appear to be "broken" when it is
actually just unconfigured. In order:

1. **A support agent exists.** At least one person on the **support** role
   (§5), otherwise a conversation handed to a human lands in a queue nobody
   can open.
2. **A routing rule exists — in *both* languages.** An AI reply is a message,
   and every message needs a routing rule saying which number carries it.
   At `/admin/qcp/routing`, create a rule for the intent
   **`ai_support_reply`** on the QUATA (engagement) number, for the product
   concerned, and cover **English and
   French**. A rule created for English only will answer anglophone customers
   and silently ignore every francophone one. A single rule with the language
   left blank ("any language") covers both.
3. **The switches are on.** The AI has its own switch, separate from message
   delivery, so you can stop the bot without stopping login codes. Engineering
   sets `QCP_AI_REPLIES_ENABLED` in the environment; you then turn on the AI
   toggle in the QCP console. Both must agree — a toggle alone cannot start it.

**If you switch the AI on and it answers nobody**, it is almost always step 2,
and you no longer have to go looking. The agent console (`/admin/qcp/agent`)
shows a red banner reading **"AI replies are on, but the AI can answer nobody"**,
naming each product and each missing language, with a link straight to
`/admin/qcp/routing`. Read the language list rather than skimming it: a product
listed as missing `fr` only is answering your English-speaking customers and
ignoring every French-speaking one.

The same condition is also recorded in the QCP overview (`/admin/qcp`) under
**Routing denials** as an **`ai.misconfigured`** row, written automatically by
the background worker (below) once an hour while the problem lasts — not once a
minute, so it stays readable. The banner is the one to act on; the audit row is
the record that it was happening while nobody was looking at the console.

#### Working the queue

`/admin/qcp/agent` — the agent console.

- **Waiting on a human** lists conversations nobody has picked up, longest wait
  at the top. Rows past 15 minutes are flagged **overdue**.
- **Claim** takes a conversation. Two agents clicking at once is handled —
  exactly one of you gets it, the other is told who has it.
- **Reply** sends as QUATA. Conversations on the Quata Verify number are shown
  but cannot be replied to, on purpose.
- **Hand back to AI** returns the thread to automation once you are done. If
  the AI is switched off, the console tells you so at that moment, so you do
  not hand a customer back to nobody.
- **Suggest** asks the AI to draft a reply *for you to edit and send*. It is a
  separate switch from the AI answering customers by itself, and it withholds
  any draft containing a figure.

**Nobody answered? Something now notices.** A background worker
(`quata-whatsapp-worker`, run by engineering) checks every minute for
conversations handed to a human and left unclaimed past 15 minutes, and records
an alert for each one — once per customer, not once per check. This is what
stops a customer escalated at 21:00 sitting until morning. It runs whether or
not message delivery is switched on, and it sends nothing itself. **If that
worker is not running, nothing chases an ignored customer** — same rule as the
missing daily Telegram summary in §6.7: tell engineering.

That worker is a separate service from the API and has to be installed once
(`infra/systemd/quata-whatsapp-worker.service`, or the cron alternative
documented at the top of that file). Until it is, the 15-minute rule above is
not enforced by anything at all. Every deploy now prints its status, so the
quickest check is to ask engineering what the last deploy said about
`quata-whatsapp-worker` — "not installed" is the answer to watch for.

#### Things worth knowing

- Turning the AI off does not close the queue, stop agents replying, or stop
  login codes. They are separate switches on purpose.
- Every refusal is recorded with a reason. "The AI said nothing" always has an
  answer on the QCP overview screen; it is never a mystery.
- The support role cannot change any of the settings in this section. Only an
  Admin (console settings) or the founder (numbers, keys, login-code rights)
  can.

---

## 7. Security checklist

- [ ] Use a strong, unique password (≥10 chars; the API enforces this).
- [ ] Enrol 2FA at `/admin/setup-2fa` if you're a super_admin (mandatory). Strongly recommended for everyone else.
- [ ] Keep recovery codes in a password manager, never in plain text.
- [ ] Sign out from public/shared computers.
- [ ] Don't share admin links — each staff member gets their own account.
- [ ] Suspend departing staff the same day — and remove their Telegram chat
      from **Alert centre → Recipients** at the same time.
- [ ] Read the 🚨 SECURITY ALERT messages. Repeated failed logins or a login
      from a new country against an account that shouldn't be travelling is
      how a breach announces itself.
- [ ] If you suspect a breach, message the engineering on-call and change your password immediately.

---

## 8. Where to ask for help

- Engineering on-call: see internal Slack `#oncall`.
- General questions: `info@quatadigital.com`.
- Security concerns: `security@quatadigital.com`.

For step-by-step deploy / rollback / incident procedures (engineering audience), see [`RUNBOOK.md`](RUNBOOK.md).
