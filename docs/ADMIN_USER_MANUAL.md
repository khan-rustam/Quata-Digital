# QUATA Digital — Admin user manual

A quick guide for non-technical admins. Everything below assumes you are
signed in at `https://quatadigital.com/admin` with an account that has
the right permissions.

---

## 1. Sign in

1. Open `https://quatadigital.com/admin/login`.
2. Enter your work email + password.
3. If 2FA is set up, enter the 6-digit code from your authenticator app.
4. **First-time only:** you'll be asked to set a new password and enrol
   2FA. Save the recovery codes shown — they are the only way back in
   if you lose your phone.

Forgot password? `https://quatadigital.com/admin/forgot-password`. A
reset link is emailed to you.

---

## 2. Daily admin tasks

### 2.1 Review partner submissions

`/admin/partners`

- Filter by **type** (business / strategic / investor / service) and
  **status** (new / in review / approved / rejected).
- Click a row to open the side panel and read the full submission.
- Add internal notes (only visible to staff).
- Set a status — the applicant receives an email automatically when you
  move them to **approved** or **rejected**.

Tip: use the bulk action bar (appears when you tick rows) to move many
applicants at once.

### 2.2 Reply to a contact-form message

`/admin/contact`

- Each message lists who, when, what they wrote.
- Click their email to open your mail client and reply directly.
- Mark the row as **handled** when done — keeps the queue clean.

### 2.3 Review job applications

`/admin/applications`

- Filter by **role** and **status** (new / shortlisted / rejected /
  hired).
- Click an applicant to view their resume + cover note.
- Set a status — the applicant gets an automatic email on shortlist /
  reject / hire.

---

## 3. Publishing content

### 3.1 Write a blog post

`/admin/cms` → **New post**.

1. **Title** — what shows in search results.
2. **Slug** — auto-generated from the title; edit only if you must.
3. **Excerpt** — 1–2 sentences shown on the blog index.
4. **Cover image** — upload a 1600×900 photo (kept on disk).
5. **Body** — Markdown. Use the **Preview** tab to see how it'll look.
6. **Category** — News / Insights / Product / Press.
7. Toggle **Published** and click **Save**.

Drafts (unpublished) are visible only to staff. Published posts are
live immediately on `/blog`.

### 3.2 Edit a CMS page

`/admin/cms` → **Pages** tab.

Same flow as a blog post. Used for `/about`, `/security` snippets,
`/privacy`, `/terms`. Be careful — these pages are legal-bearing.

### 3.3 Post a job

`/admin/careers`.

1. **Title**, **department**, **location**, **employment type**.
2. **Summary** (shown on the careers index) and **description** (full
   body, Markdown).
3. Toggle **Published**.

The job appears immediately on `/careers`. Applicants apply via the
public form.

---

## 4. Managing people

### 4.1 Invite a new staff member

`/admin/staff` → **Invite**.

1. Enter their work email + name.
2. Pick a **role** (controls what they can do — see §5).
3. Optionally set a **department**.
4. Click **Send invite** — they receive an email with a one-time setup
   link to set their password.

### 4.2 Change someone's role

`/admin/staff` → click the row → **Edit** → change role → save.

The role determines their permissions globally. The change is logged
in the activity feed.

### 4.3 Suspend or remove

- **Suspend** = soft delete. They can't log in but their history is
  preserved.
- Use suspend in 99% of cases. True deletion is destructive.

---

## 5. Roles & permissions

| Role | What they can do |
|---|---|
| **super_admin** | Everything. Reserved for the founder + CTO. |
| **admin** | All content, partners, careers, staff, RBAC, devices, activity, analytics. |
| **manager** | Partners, careers, staff, analytics. No RBAC, no devices. |
| **team_lead** | Partners, careers (read + edit). |
| **staff / intern / contractor** | Self-service only — log in, request leave, clock in/out. |

To change permissions per role: `/admin/roles`. Tick / untick the
permission boxes per role.

---

## 6. Other modules

### 6.1 Internal messaging

`/admin/messages` — send a note to all staff, a single department, or
one person. Recipients see it in their notifications dropdown.

### 6.2 Leave management

- Staff request leave from `/admin/leave`.
- Managers approve / reject — staff get an email automatically.

### 6.3 Attendance

`/admin/attendance`. Shows daily check-in / check-out per staff. Data
flows in from the biometric devices (or staff self-service on
`/admin/attendance`).

### 6.4 Devices

`/admin/devices`. Add a biometric device — copy the API token shown
once, paste into the device. Rotate the token if it's ever
compromised.

### 6.5 Activity log

`/admin/activity`. Every important action is recorded — who did what,
when, on what resource. Use it for audits.

### 6.6 Analytics

`/admin/analytics`. Anonymous page-view counts per page, per day. Only
visitors who accept the cookie banner are counted.

---

## 7. Security checklist

- [ ] Use a strong, unique password.
- [ ] Enrol 2FA (`/admin/setup-2fa`) — no exceptions.
- [ ] Keep recovery codes in a password manager, never in plain text.
- [ ] Sign out from public/shared computers.
- [ ] Don't share admin links — each staff member gets their own
      account.
- [ ] Suspend departing staff the same day.
- [ ] If you suspect a breach, message the engineering on-call and
      change your password immediately.

---

## 8. Where to ask for help

- Engineering on-call: see internal Slack `#oncall`.
- General questions: `info@quatadigital.com`.
- Security concerns: `security@quatadigital.com`.

For step-by-step deploy / rollback / incident procedures (engineering
audience), see [`RUNBOOK.md`](RUNBOOK.md).
