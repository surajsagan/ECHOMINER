# EchoMiner

Research platform for structured extraction from echocardiography PDF reports.
JSS Academy of Higher Education and Research (JSS AHER), Mysore — DBT-BUILDER, Group 3.

## Status

| Module | State |
|---|---|
| M0 foundation — config, structured logging, health/readiness, Docker, CI | **Done** |
| M1 persistence — 14-table schema, TZ-safe timestamps, append-only audit | **Done** |
| M2 identity — registration, agreement capture, OTP, sessions, trusted devices | **Done** |
| M3 mail — SMTP relay + console adapters, OTP and team-notification templates | **Done** |
| M4 extraction — validated pipeline vendored unchanged behind an observing adapter | **Done** |
| M5 jobs — upload validation, DB-backed queue, worker, SSE progress, purge sweeper | **Done** |
| M6 export — six-sheet branded XLSX, Quality + Citation sheets, deterministic | **Done** |
| M7 site — 14 sections, design system, SEO, JSON-LD, dark/light, a11y floor | **Done** |
| M8 tool UI — registration gate, agreement modal, OTP, upload, live progress, preview, export | **Done** |
| M9 admin — TOTP sign-in, user oversight, verification log, analytics, health | **Done** |
| M10 CMS — news / publications / FAQ CRUD, published entries drive the public page | **Done** |
| M11 ops — Alembic migrations, deploy/backup/restore scripts, CI + CD with auto-rollback, Cloudflare origin lock | **Done** |
| M12 launch — deployment runbook (`docs/DEPLOYMENT.md`), end-to-end verified | **Done** |

## The extraction pipeline is used as-is

`echominer/vendor/echo_extractor.py` is the validated extractor, vendored **byte-for-byte**
(`sha256 d49edd7d…0be322`). `ValidatedPipelineEngine` calls `extract_echo_data()` and returns
its output unmodified — a test asserts row-for-row equality with a direct call, and CI fails
if the vendored file's hash changes.

The adapter adds only *observations* alongside the untouched output: page count, how many
report headers the source contains, and how many returned rows have no populated field.
These become Quality-sheet notes. Nothing is filtered, corrected, or dropped.

## Run locally

```bash
cd apps/api
pip install -e ".[dev]"
cp .env.example .env          # fill SECRET_KEY and OTP_PEPPER: openssl rand -hex 32
pytest -q                     # 53 tests
uvicorn echominer.main:app --reload
```

Defaults are dev-safe: console mailer (prints instead of sending), null captcha,
SQLite if `DATABASE_URL` points at one. Nothing leaves the machine.

## Deploy

Two supported targets:

- **Card-free:** Render free web service + Neon Postgres + Cloudflare — one process serves the
  website, API and extraction worker. Step-by-step: **[`docs/DEPLOY_RENDER.md`](docs/DEPLOY_RENDER.md)**
  (`render.yaml` Blueprint, `infra/docker/render.Dockerfile`).
- **Any Ubuntu VM** (Oracle Cloud Always Free, or an institutional server) behind Cloudflare, Brevo for mail. Step-by-step:
**[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)** (GoDaddy → Cloudflare DNS, Oracle VM, certificates, secrets,
first deploy, automatic deploys, backups, launch checklist, local development).

## Frontend

```bash
cd apps/web
npm ci
API_PROXY=http://localhost:8000 npm run dev   # http://localhost:3000, /api proxied to the local API
npm run typecheck && npm run build
```

Registration and the tool live on the same page: after OTP verification the
workspace is revealed in place, no redirect. A returning visitor on a known
device is restored silently on load and never sees the OTP step again.

Palette and tone are pinned by the brief (blue, teal, white, minimal). Where the
brief left room, the choices come from the subject — echocardiography is a
waveform-and-number discipline, so every measurement, unit, version string and
timestamp is set in mono, and the single signature motif is a Doppler spectral
envelope that draws once in the hero and returns quietened as the section rule.
Motion is limited to three orchestrated moments and fully bypassed under
`prefers-reduced-motion`.

## Administration

```bash
python -m echominer.cli create-admin --email you@jssuni.edu.in --password '…'
```

Prints an `otpauth://` URL once — enrol it in an authenticator before closing the
terminal. Sign in at `/admin`. The admin realm is fully separate from the
researcher realm: its own credential table, its own session table, its own cookie
name, `SameSite=Strict`, and a 15-minute idle timeout. `/admin` is `noindex` and
disallowed in `robots.txt`.

Password hashing uses scrypt from the standard library rather than Argon2id as
originally specified — it is memory-hard, needs no C build stage in the ARM
runtime image, and removes a dependency. TOTP is RFC 6238 implemented directly.

## Documentation

- `docs/ARCHITECTURE.md` — system design, schema, API, security review, roadmap
- `docs/PARSER_AUDIT.md` — extractor behaviour audit with reproductions
- `packages/field-dictionary/` — canonical field definitions

## Job pipeline

Upload → validate (PDF magic bytes, no active content, ≤20 files / ≤200 MB) →
stage in tmpfs → DB-claimed queue → worker runs the validated pipeline →
rows stored → preview → branded XLSX → artefacts purged on download.

The queue is PostgreSQL row-claiming (`FOR UPDATE SKIP LOCKED`) rather than a
broker: on a single VM that removes a moving part, jobs survive a restart because
they live in the database that is already backed up, and there is no second
system to monitor. Rate limiting is done by nginx, so there is no Redis.

Abandoned jobs (tab closed, no download) are swept by TTL. Job metadata and the
audit trail survive a purge; nothing that could reconstruct a report does.
