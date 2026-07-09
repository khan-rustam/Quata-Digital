# QUATA Digital — Enterprise HRMS/HCM Upgrade Roadmap

Living checklist for turning the current admin (Careers, Applicants, Employees,
Departments, Roles, Attendance, Leave, Biometric devices) into a full Human
Capital Management platform. Built **incrementally** — each item is a shippable,
tested slice that **extends** existing modules (no rebuilds, no removed features,
backward-compatible, same UI language).

**Standing decisions (from the boss, 2026-07-09):**
- **AI provider = OpenAI** (boss decision 2026-07-09). Gated behind
  `OPENAI_API_KEY` + a feature flag (`settings.ai_enabled`); the openai client is
  imported lazily so the app boots without a key. Default model `gpt-4o-mini`.
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

### 1E. AI talent intelligence ✅ shipped (OpenAI)
- [x] CV parse (pypdf) → skills/soft-skills/languages/certs/education/experience
- [x] Overall hiring score + per-role-family match % (7 QUATA families)
- [x] Strengths/weaknesses, recommended role+dept, 5 interview Qs, training recs,
      hiring recommendation, summary. On-demand "Analyse CV" on the applicant
      panel (careers:manage). POST /admin/applications/{id}/analyze; app/services/
      ai_cv.py; migration o5t6u7v8w9x0; test_ai_cv.py (mocked). Needs OPENAI_API_KEY.
- [~] "Move applicant" — recommendation surfaced (recommended role/dept +
      hiring rec); one-click re-assign to another vacancy still to wire.

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

### 2A. Complete employee personnel file ✅ (core sections)
- [x] Personal (gender, DOB, nationality, ID, marital, blood group, personal email,
      address, emergency contacts), Employment (type, grade, work location, reporting
      manager, hire/confirmation/contract dates, probation), Professional (skills,
      languages, certifications, education, previous employment, portfolio). Editable
      dialog on the staff detail page. migration n4s5t6u7v8w9; PATCH
      /admin/staff/{id}/profile; test_employee_profile.py
- [ ] Company-records history (promotions/transfers/disciplinary/rewards/assets) —
      separate modules (Phase 2G / Phase 3)

### 2B. Employee ID system ✅ shipped
- [x] Auto employee number (QDE-YYYY-NNNNNN) — unique, immutable, assigned on hire
      + seed backfill + on-demand generate endpoint. migration m3r4s5t6u7v8;
      shown in staff list + detail. test_employee_identity.py
- [x] QR verification code (random token) generated alongside the number
- [ ] Card number, encrypted NFC token, digital certificate (with 2C card)

### 2C. Smart ID card generator ✅ (front side)
- [x] Print-ready CR80 card (PNG + PDF) via Pillow + qrcode: logo, photo/initials,
      name, employee number, position, department, business unit, QR → verify URL,
      issue date. GET /admin/staff/{id}/id-card?format=png|pdf; View/Download on
      the staff detail page. test_employee_identity.py
- [ ] Back side, reissue/suspend history, card numbers

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
- [x] Employee directory — /admin/staff with search (name/email/employee no/location),
      department + status filters, and CSV export (GET /admin/staff/export.csv)
- [x] Performance reviews · Training records · Asset assignment — per-employee
      cards on the staff detail page (list/add/delete). migrations p6/q7/r8;
      test_employee_records.py

---

## PHASE 3 — HR Ops & Intelligence  (Prompt 3)

- [x] Payroll preparation — SalaryRecord (basic/allowances/bonus/overtime, tax/
      pension/insurance/loan/advance, computed gross/deductions/net, payment
      method incl. QuataPay). Admin-only (rbac:manage). 'Compensation' card on
      the staff detail. migration u1z2a3b4c5d6. Disbursement engine still future.
- [~] Contract management — expiry alerts done (GET /admin/hr-alerts + dashboard
      "Contracts expiring" panel, from 2A contract_expiry). Versions/renewals pending.
- [~] Probation management — on-probation + overdue alerts done (dashboard panel,
      from 2A probation_status/confirmation_date). Evaluations/auto-confirm pending.
- [x] Disciplinary — confidential per-employee records (warning→investigation→
      resolution), audit-logged. migration s9x0y1z2a3b4
- [x] Exit management — offboarding record (type/date/reason/rehire eligibility/
      knowledge transfer + checklist: assets/access/exit interview/settlement);
      marks the employee 'exited'/inactive; reversible. migration t0y1z2a3b4c5
- [x] Alumni database — /admin/alumni: searchable former staff with rehire
      eligibility (GET /admin/alumni). History never deleted.
- [x] HR analytics dashboard — /admin/hr-dashboard + GET /admin/hr-analytics:
      KPI tiles + headcount-by-department/business-unit + recruitment-funnel +
      workforce distributions (gender, age, tenure, employment type) — all
      single-hue magnitude bars, dependency-free, real data. Plus HR-alerts panel
      (contracts/probation). Trends over time still pending (needs history).
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
