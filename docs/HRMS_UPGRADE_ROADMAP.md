# QUATA Digital — Enterprise HRMS/HCM Upgrade Roadmap

Living checklist for turning the current admin (Careers, Applicants, Employees,
Departments, Roles, Attendance, Leave, Biometric devices) into a full Human
Capital Management platform. Built **incrementally** — each item is a shippable,
tested slice that **extends** existing modules (no rebuilds, no removed features,
backward-compatible, same UI language).

**Standing decisions (from the boss, 2026-07-09):**
- **AI is structure-first, off until a key is provided.** Build the fields, UI
  and "Move applicant instead of reject" flow; gate all real LLM calls behind an
  Anthropic API key + a feature flag. Provider = Claude when enabled.
- **Identity/access is software-only for now.** Generate ID cards (PDF/PNG), QR
  verification, and encrypted tokens in software; physical NFC readers / door
  controllers integrate later via a clean API.
- No applicant or employee is ever hard-deleted (soft-delete + history everywhere).

Legend: `[ ]` todo · `[~]` in progress · `[x]` done · `(AI)` needs key · `(HW)` needs hardware · `(SS)` needs employee self-service auth

---

## PHASE 1 — Recruitment & Talent  (Prompt 1)

### 1A. Applicant collaboration (FIRST — easiest, purely additive) ✅ shipped
- [x] Assigned HR officer per applicant (dropdown on the applicant panel)
- [x] Internal notes / comments thread (author + timestamp)
- [x] Activity timeline on the applicant profile (from existing activity log)
- migration `j0o1p2q3r4s5`; endpoints `/applications/{id}/{assignment,notes,timeline}`; tests `test_applicant_collaboration.py`

### 1B. Full recruitment pipeline stages ✅ shipped
- [x] Applicant pipeline: New → HR Review → Shortlisted → Interview Scheduled →
      Interview Completed → Assessment → Reference Check → Offer → Offer Accepted →
      Hired / Rejected / Archived ("Move to stage" selector; shortlist/hire/reject
      keep their email dialogs). Backward-compatible; no migration (string status).
- [x] Per-stage status + timestamp + assigned HR + notes + comments + logs (1A timeline)
- [x] Attachments on applicants (offer letters, assessments, reference checks) —
      private (authed download, blocked from public mount); migration l2q3r4s5t6u7
- [x] Keep rejected applicants searchable (never hard-delete) — talent pool base

### 1C. Applicant profile (complete digital profile)
- [ ] Structured profile: personal, contact, education, employment history,
      skills, languages, references, portfolio, social links, certificates
- [ ] Offer history · interview notes · assessment results · reference check
- [ ] Download Profile PDF

### 1D. Talent pool / database
- [~] Search/filter all applicants (incl. rejected/archived) — name/email + stage
      done (Applicants tab, /admin/applications/v2). Richer filters (skills,
      education, certs, AI score, dept match) land with 1C profile + 1E AI.
- [ ] When a vacancy opens, surface matching past applicants first

### 1E. AI talent intelligence (AI)
- [ ] CV parse → education/experience/skills/languages/certs (extract)
- [ ] Overall hiring score + per-role/department match %
- [ ] Strengths/weaknesses, recommended role+dept, interview Qs, training recs
- [ ] "Move Applicant" (internal fit) vs Reject

### 1F. Organization architecture ✅ (org chart pending)
- [x] Business Units (distinct from products): admin page + CRUD + seed
      (Corporate Services, QuataPay, QuataTrade, QuataFood, Abaqwa)
- [x] Enterprise departments: business unit, head, assistant head, objectives,
      KPIs, budget, max headcount (capacity), office location. migration
      k1p2q3r4s5t6; test_business_units.py
- [~] Hierarchy Company → Business Unit → Department done; Team → Position pending
- [ ] Dynamic org chart (drag & drop, reporting lines, auto-updates)

---

## PHASE 2 — Employee & Identity  (Prompt 2)

### 2A. Complete employee personnel file
- [ ] Personal / employment / professional / company-records / documents sections
- [ ] Promotions, transfers, disciplinary, rewards, assets, access rights history

### 2B. Employee ID system ✅ shipped
- [x] Auto employee number (QDE-YYYY-NNNNNN) — unique, immutable, assigned on hire
      + seed backfill + on-demand generate endpoint. migration m3r4s5t6u7v8;
      shown in staff list + detail. test_employee_identity.py
- [x] QR verification code (random token) generated alongside the number
- [ ] Card number, encrypted NFC token, digital certificate (with 2C card)

### 2C. Smart ID card generator
- [ ] Front/back printable card (PDF/PNG/high-res), preview, reissue/suspend history

### 2D. QR employee verification page  (public, minimal PII) ✅ shipped
- [x] Public /verify/{code} page + GET /api/v1/verify/{code} — photo, name, dept,
      position, business unit, employment status, verified badge. No PII, lookup
      by random code (not enumerable). noindex.

### 2E. NFC & access control  (HW for physical readers)
- [ ] Access levels + role/dept/time-based/temporary/visitor/contractor
- [ ] Log every access attempt

### 2F. Employee self-service portal  (SS)
- [ ] Profile, attendance, leave, training, reviews, announcements, docs, card

### 2G. Attendance / Leave / Performance / Training / Assets / Directory upgrades
- [ ] Attendance: NFC/QR/biometric/manual/GPS/WiFi, breaks, overtime, reports
- [ ] Leave: types + Employee→Manager→HR workflow, auto balance
- [ ] Performance reviews · Training records · Asset assignment · Employee directory

---

## PHASE 3 — HR Ops & Intelligence  (Prompt 3)

- [ ] Payroll preparation (structure, allowances, deductions; link to QuataPay later)
- [ ] Contract management (types, expiry alerts, versions)
- [ ] Probation management (evaluations, confirmation, reminders)
- [ ] Disciplinary workflow (confidential, audit trail)
- [ ] Exit management (asset return, access/NFC revocation, clearance, interview)
- [ ] Alumni database (searchable former staff, rehire eligibility)
- [ ] HR analytics dashboards (headcount, turnover, funnel, trends, charts)
- [ ] AI HR assistant (AI): summaries, recommendations, forecasts, reports
- [ ] Performance & succession planning · Workforce planning
- [ ] Reports & exports (PDF/Excel/CSV) everywhere
- [ ] Notification centre (contract/probation/birthday/anniversary/expiry/…)
- [ ] Integration API layer (QuataPay, biometric, NFC, payroll, SMS/push) — auth+versioned

---

## Cross-cutting (apply to every module as built)
- [ ] Search · advanced filters · sorting · bulk actions
- [ ] Audit logs (user, timestamp, IP, device, old→new, reason)
- [ ] Activity timeline · notifications · attachments · comments
- [ ] Field-level / role-based permissions (RBAC + ABAC-ready)
- [ ] PDF / Excel / CSV export · mobile responsive
