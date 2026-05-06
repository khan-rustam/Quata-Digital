# Hostinger domain check — step by step

For: confirming `quatadigital.com` DNS is pointed correctly and deciding which
host (`apex` vs `www`) is canonical, ahead of public launch.

You'll be in the **Hostinger panel** the whole way through. No SSH, no code.

---

## 0. What you'll need before you start

- Login to Hostinger (the account that owns `quatadigital.com`).
- The **public IPv4 address** of the VPS (the one Caddy/Nginx is running on). If you don't have it handy, run `curl ifconfig.me` from the VPS or check the VPS card in Hostinger → VPS.
- 5 minutes.

---

## 1. Open the DNS zone

1. Sign in at https://hpanel.hostinger.com.
2. Top nav → **Domains**.
3. Click **quatadigital.com** in the list.
4. Left sidebar → **DNS / Name Servers**.

You should now see a table of DNS records (Type / Name / Points to / TTL).

---

## 2. What records to look for

Send back **screenshots or copy-paste** of the following rows. Mask nothing —
DNS is public, none of this is secret.

### A record for the apex (`@`)

- **Type:** A
- **Name:** `@`
- **Points to:** should be the VPS public IPv4

If it points anywhere else (parking page, Hostinger placeholder, old IP), that's the first thing to fix.

### CNAME or A record for `www`

- **Type:** CNAME or A
- **Name:** `www`
- **Points to:** ideally `quatadigital.com.` (with trailing dot) as a CNAME — that way `www` follows the apex automatically. An A record pointing to the same VPS IP also works.

### A record for `api`

- **Type:** A
- **Name:** `api`
- **Points to:** the VPS public IPv4 (same as apex)

This is what `https://api.quatadigital.com` resolves to.

### A record for `2025quata` (if present)

- **Type:** A
- **Name:** `2025quata`
- **Points to:** VPS public IPv4

This is the staging subdomain referenced in `BACKEND_CORS_ORIGINS`. Confirm it still exists and points to the right host.

### TXT records for email (only if SMTP is set up)

- **SPF:** TXT on `@` containing `v=spf1 include:smtp2go.com ~all` (or the equivalent for your provider).
- **DKIM:** TXT on `selector1._domainkey` (or whatever selector your SMTP provider gave you) with the long base64 public key.
- **DMARC:** TXT on `_dmarc` with at least `v=DMARC1; p=none; rua=mailto:postmaster@quatadigital.com`.

If these aren't there yet, that's expected — they get added when you finish the SMTP setup.

---

## 3. What to send back

Either:
- Screenshots of the DNS table showing rows for `@`, `www`, `api`, `2025quata`, and any TXT records starting with `v=spf1` / `v=DMARC1` / containing `_domainkey`.

Or paste this filled in:

```
@                A      <ip>      TTL: <value>
www              CNAME  <target>  TTL: <value>
api              A      <ip>      TTL: <value>
2025quata        A      <ip>      TTL: <value>     (if present)

# Email TXT records (paste verbatim if they exist)
@                TXT    "v=spf1 ..."
selector1._domainkey  TXT  "..."
_dmarc           TXT    "v=DMARC1; ..."
```

---

## 4. Decide which host is canonical

Pick **one** answer:

- **(A) Apex is canonical** — `quatadigital.com` is the public URL. `www.quatadigital.com` 301-redirects to it.
- **(B) `www` is canonical** — `www.quatadigital.com` is the public URL. `quatadigital.com` (apex) 301-redirects to it.

Most modern brands pick (A). Either works. Once you've decided, engineering wires the redirect at the reverse proxy (Caddy/Nginx) — about a 5-line change.

---

## 5. After you send the info back

Engineering will:

1. Confirm every record points to the VPS.
2. Add the 301 redirect for the non-canonical host.
3. Run a smoke test: `curl -sI https://www.quatadigital.com` should return `301` with `Location: https://quatadigital.com/...` (or the reverse, depending on your choice).
4. Mark **C-02** done in [PRODUCTION_AUDIT.md](PRODUCTION_AUDIT.md).

Total turnaround once you reply: ~30 minutes.

---

## 6. While you're in Hostinger — quick wins

If you want to take advantage of being in the panel:

- **DNSSEC:** if Hostinger offers it for the domain, enable it. Adds tamper protection. Free.
- **Auto-renew:** confirm `quatadigital.com` has auto-renew on. A lapsed domain at launch would be catastrophic.
- **WHOIS privacy:** confirm enabled (default for most TLDs at Hostinger).
