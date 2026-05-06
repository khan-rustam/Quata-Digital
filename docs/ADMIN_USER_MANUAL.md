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
| **admin** | All content, partners, careers, staff, RBAC, devices, activity, analytics, newsletter. |
| **manager** | Partners, careers, staff, analytics. No RBAC, no devices. |
| **team_lead** | Partners, careers (read + edit). |
| **staff / intern / contractor** | Self-service only — log in, request leave, clock in/out, edit own profile. |

To change permissions per role: `/admin/roles`. Tick / untick the permission boxes per role.

The `super_admin` role is **immutable** — you can't change its permissions and you can't delete it. By design.

The 9 permission keys are: `content:manage`, `partners:manage`, `careers:manage`, `staff:manage`, `rbac:manage`, `devices:manage`, `activity:view`, `analytics:view`, `newsletter:manage`.

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

### 6.7 My settings

`/admin/settings`. Update your profile (name, phone, avatar, job title), change your password, and enrol or disable 2FA. Notification preferences also live here.

---

## 7. Security checklist

- [ ] Use a strong, unique password (≥10 chars; the API enforces this).
- [ ] Enrol 2FA at `/admin/setup-2fa` if you're a super_admin (mandatory). Strongly recommended for everyone else.
- [ ] Keep recovery codes in a password manager, never in plain text.
- [ ] Sign out from public/shared computers.
- [ ] Don't share admin links — each staff member gets their own account.
- [ ] Suspend departing staff the same day.
- [ ] If you suspect a breach, message the engineering on-call and change your password immediately.

---

## 8. Where to ask for help

- Engineering on-call: see internal Slack `#oncall`.
- General questions: `info@quatadigital.com`.
- Security concerns: `security@quatadigital.com`.

For step-by-step deploy / rollback / incident procedures (engineering audience), see [`RUNBOOK.md`](RUNBOOK.md).
