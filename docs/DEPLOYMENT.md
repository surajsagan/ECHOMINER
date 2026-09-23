# EchoMiner — Deployment Runbook

Takes the code in this repository to a live, HTTPS site at **https://echominer.in**.

> **No credit card?** Oracle Cloud needs one. Use the card-free set-up instead:
> [`DEPLOY_RENDER.md`](DEPLOY_RENDER.md) (Render + Neon + Cloudflare). This guide remains the
> reference for any Ubuntu VM, including an institutional server.
Total cost: ₹0 per month (domain renewal at GoDaddy aside).

```
Visitor ──HTTPS──> Cloudflare (DNS, TLS, CDN, DDoS)  ──HTTPS (origin cert)──>  Oracle ARM VM
                                                                             └─ nginx ─┬─ web    (Next.js)
                                                                                       ├─ api    (FastAPI)
                                                                                       ├─ worker (validated extractor)
                                                                                       └─ postgres
OTP / registration mail: api ──SMTP──> Brevo ──> inbox   (sender noreply@echominer.in)
```

Follow the phases in order. Phases 2–4 involve waiting (DNS, Oracle capacity),
so start them early and do the others while you wait.

| Phase | What | Time |
|---|---|---|
| 1 | Put the code on GitHub | 10 min |
| 2 | Move echominer.in DNS from GoDaddy to Cloudflare | 15 min + up to 24 h wait |
| 3 | Create the Oracle Cloud VM | 30 min (capacity can take days) |
| 4 | Prepare the server | 15 min |
| 5 | HTTPS: Cloudflare origin certificate + DNS records | 10 min |
| 6 | Email: Brevo | 20 min + verification wait |
| 7 | reCAPTCHA keys | 5 min |
| 8 | Configure secrets on the server | 10 min |
| 9 | First deploy + admin account | 20 min |
| 10 | Automatic deploys and backups | 15 min |
| 11 | Launch checklist | 15 min |

Windows note: every `ssh` command below works in **PowerShell** (OpenSSH is built into Windows 10/11).

---

## Phase 1 — Code on GitHub

Repository: `https://github.com/surajsagan/ECHOMINER` (public — no secrets are ever committed;
`.env` files, certificates and keys are in `.gitignore`).

Push with **GitHub Desktop** (https://desktop.github.com): *File → Add local repository* → choose the
`ECHOMINER` folder → *Push origin*. After the push, the **Actions** tab runs CI (tests on SQLite and
PostgreSQL, migration check, web build, Docker image builds, nginx config check). All jobs must be green.
The **Deploy** workflow will say "DEPLOY_HOST not set — skipping" until Phase 10; that is expected.

---

## Phase 2 — DNS: GoDaddy → Cloudflare

1. Create a free account at https://dash.cloudflare.com → **Add a domain** → `echominer.in` → **Free** plan.
2. Cloudflare scans existing records and then shows **two nameservers** (e.g. `xxx.ns.cloudflare.com`). Keep that tab open.
3. GoDaddy → **My Products** → `echominer.in` → **DNS** → **Nameservers** → **Change nameservers** →
   **I'll use my own nameservers** → enter the two Cloudflare nameservers → Save.
   If GoDaddy says DNSSEC is on, turn DNSSEC off first.
4. Back in Cloudflare click **Check nameservers**. Status becomes **Active** within minutes to 24 h;
   Cloudflare emails you.
5. Delete any leftover GoDaddy parking records Cloudflare imported (A records pointing at GoDaddy parking IPs,
   `_domainconnect` CNAME). You will add the real records in Phase 5.

---

## Phase 3 — Oracle Cloud VM

### 3.1 Account
Sign up at https://signup.cloud.oracle.com.
- **Home region: choose `India South (Hyderabad)` or `India West (Mumbai)`. This cannot be changed later**,
  and Always Free resources exist only in the home region.
- A card is required for identity verification. An Always Free account is not charged.

### 3.2 Create the instance
Console → **Compute → Instances → Create instance**.

| Setting | Value |
|---|---|
| Name | `echominer-prod` |
| Image | **Canonical Ubuntu 24.04** (the aarch64 build is picked automatically for Ampere) |
| Shape | **Ampere → VM.Standard.A1.Flex**, **2 OCPUs, 12 GB memory** (the Always Free allowance — larger shapes are billed) |
| Networking | Create new VCN + **public subnet**, **Assign a public IPv4 address: Yes** |
| SSH keys | **Generate a key pair for me** → **Save private key** (e.g. `echominer.key`) |
| Boot volume | 100 GB (Always Free covers 200 GB total) |

If you get **"Out of host capacity"**: this is Oracle temporarily having no free ARM hosts in your region.
Retry the same form later (early morning IST often works), or try a different *availability domain* in the
placement section. It can take several attempts over a few days.

Note the instance's **Public IP address**.

### 3.3 Open ports 80/443 in Oracle's network
Instance page → **Subnet** link → **Security Lists** → *Default Security List* → **Add Ingress Rules**:

| Source CIDR | Protocol | Destination port |
|---|---|---|
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |

(Port 22 for SSH is already open.) The VM's own firewall also blocks these ports; the bootstrap script in
Phase 4 opens it. Both are needed — this is the most common reason a new Oracle site "does not load".

### 3.4 Idle reclamation — read this
Oracle states that Always Free instances may be reclaimed if, over 7 days, 95th-percentile CPU,
network, **and** memory utilisation are all below 20%
([Always Free Resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)).
A low-traffic research site can meet that. Consequences and mitigation:
- Keep **off-VM copies of the database backups** (Phase 10.3). Code is on GitHub; with a backup the whole
  site can be rebuilt on a new VM in about an hour using this runbook.
- Watch the email address on the Oracle account for notices.

---

## Phase 4 — Prepare the server

From PowerShell, in the folder containing the key:

```powershell
ssh -i .\echominer.key ubuntu@<PUBLIC_IP>
```
(If Windows complains the key permissions are too open: right-click the key → Properties → Security →
Advanced → Disable inheritance → remove every user except yourself.)

On the server:

```bash
sudo mkdir -p /opt/echominer && sudo chown ubuntu:ubuntu /opt/echominer
git clone https://github.com/surajsagan/ECHOMINER /opt/echominer
cd /opt/echominer
bash infra/scripts/bootstrap-server.sh     # Docker, firewall ports 80/443, swap, auto security updates
exit
```

Log back in (`ssh -i ...` again) so the `docker` group applies. Check: `docker run --rm hello-world`.

---

## Phase 5 — HTTPS and DNS records (Cloudflare)

### 5.1 Origin certificate (what the server presents to Cloudflare)
Cloudflare → `echominer.in` → **SSL/TLS → Origin Server → Create Certificate**
→ *Generate private key and CSR with Cloudflare*, RSA 2048, hostnames `echominer.in`, `*.echominer.in`,
validity 15 years → **Create**.

On the server, paste each block into its file:

```bash
sudo nano /etc/echominer/certs/origin.pem   # paste "Origin Certificate", save (Ctrl+O, Enter, Ctrl+X)
sudo nano /etc/echominer/certs/origin.key   # paste "Private Key", save
sudo chmod 600 /etc/echominer/certs/origin.key
```

The private key is shown **once**. If you lose it, revoke and create a new certificate.

### 5.2 SSL settings
- **SSL/TLS → Overview → Configure → Full (strict)**
- **SSL/TLS → Edge Certificates → Always Use HTTPS: On**, **Minimum TLS: 1.2**

### 5.3 DNS records
Cloudflare → **DNS → Records → Add record**:

| Type | Name | Content | Proxy |
|---|---|---|---|
| A | `echominer.in` (`@`) | `<PUBLIC_IP>` | **Proxied** (orange cloud) |
| CNAME | `www` | `echominer.in` | **Proxied** |

The nginx configuration serves the site **only to connections from Cloudflare's IP ranges**; opening
`https://<PUBLIC_IP>` directly is dropped by design.

---

## Phase 6 — Email (Brevo)

Sends the OTP codes and the registration notices, from `noreply@echominer.in`, with replies going to
`aiechominer@gmail.com`. No mailbox is created. Free plan: 300 emails/day.

1. Sign up at https://www.brevo.com (use `aiechominer@gmail.com`).
2. **Settings → Senders, Domains & Dedicated IPs → Domains → Add a domain** → `echominer.in`.
   Brevo lists DNS records (a `brevo-code` TXT, DKIM record(s), and a DMARC TXT). If Brevo offers to set them
   up in Cloudflare automatically, accept; otherwise add **exactly** the records it shows in Cloudflare → DNS,
   with **Proxy status: DNS only** (grey cloud) for any CNAME. Click **Authenticate** in Brevo until each shows
   verified.
3. **Senders → Add a sender**: name `EchoMiner`, email `noreply@echominer.in`.
4. **SMTP & API → SMTP** tab: note the **Login** and click **Generate a new SMTP key**. Copy the key now.
5. New Brevo accounts are sometimes held for a manual activation review before they can send. If test mails
   do not arrive, check the Brevo dashboard for an activation notice.

---

## Phase 7 — reCAPTCHA v3

https://www.google.com/recaptcha/admin/create →
Label `EchoMiner`, type **Score based (v3)**, domain `echominer.in` → Submit.
Copy the **site key** (public) and the **secret key**.

---

## Phase 8 — Secrets on the server

```bash
cd /opt/echominer
cp .env.deploy.example .env.deploy
cp apps/api/.env.example apps/api/.env
openssl rand -hex 24     # -> database password
openssl rand -hex 32     # -> SECRET_KEY
openssl rand -hex 32     # -> OTP_PEPPER
nano .env.deploy         # POSTGRES_PASSWORD, NEXT_PUBLIC_RECAPTCHA_SITE_KEY
nano apps/api/.env       # SECRET_KEY, OTP_PEPPER, DATABASE_URL (same password), SMTP_USER, SMTP_PASSWORD, RECAPTCHA_SECRET
chmod 600 .env.deploy apps/api/.env
```

In `apps/api/.env`, `DATABASE_URL` must read
`postgresql+psycopg://echominer:<THE_SAME_PASSWORD>@postgres:5432/echominer`.
If the password contains `@ : / %`, generate a hex one as above (hex is always safe).

Keep a copy of both files in a password manager. They are not in Git and are needed to rebuild the server.

---

## Phase 9 — First deploy

```bash
cd /opt/echominer
C="docker compose -f infra/compose/docker-compose.yml --env-file .env.deploy"
$C up -d --build           # first build on ARM takes ~10–20 minutes
$C ps                      # postgres/api/worker/web/nginx "running", migrate "exited (0)"
$C logs --tail 50 api worker
curl -sk --resolve echominer.in:443:127.0.0.1 https://echominer.in/readyz    # {"status":"ready",...}
```

Create the administrator (use a strong password; you will be asked for it at `/admin`):

```bash
$C run --rm api python -m echominer.cli create-admin --email aiechominer@gmail.com --password '<STRONG_PASSWORD>'
```

It prints a **TOTP secret** and an `otpauth://` link once. Add it to Google Authenticator / Microsoft
Authenticator (*Add → Enter a setup key*). Admin sign-in needs email + password + the 6-digit code.

Open **https://echominer.in** and **https://echominer.in/admin**.

---

## Phase 10 — Automation

### 10.1 Automatic deploys on every push to `main`
On the server:
```bash
ssh-keygen -t ed25519 -f ~/.ssh/github_deploy -N "" -C github-actions
cat ~/.ssh/github_deploy.pub >> ~/.ssh/authorized_keys
cat ~/.ssh/github_deploy          # copy the whole private key, including BEGIN/END lines
```
GitHub → repository → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
|---|---|
| `DEPLOY_HOST` | the VM public IP |
| `DEPLOY_USER` | `ubuntu` |
| `DEPLOY_SSH_KEY` | the private key printed above |

From then on: push to `main` → CI → (if green) Deploy runs `infra/scripts/deploy.sh` on the server:
safety database backup → pull → build → migrate → restart → smoke test → **automatic code rollback** if the
smoke test fails. **Actions → Deploy → Run workflow** redeploys by hand.

### 10.2 Nightly backups and Cloudflare range refresh
```bash
crontab -e
```
Add:
```
30 20 * * * /opt/echominer/infra/scripts/backup.sh nightly >> /var/backups/echominer/backup.log 2>&1
15 21 * * 0 /opt/echominer/infra/scripts/refresh-cloudflare-ips.sh >> /var/backups/echominer/cf.log 2>&1
```
(20:30 UTC = 02:00 IST.) Backups go to `/var/backups/echominer/`, newest 14 kept.

### 10.3 Off-VM backup copy (do not skip — see 3.4)
The database holds researcher registrations (personal data). Keep copies somewhere private — never in the
public GitHub repo. Simplest manual routine, weekly, from PowerShell on your PC:
```powershell
scp -i .\echominer.key "ubuntu@<PUBLIC_IP>:/var/backups/echominer/echominer-*nightly.sql.gz" .\EchoMiner-backups\
```
Store that folder on institutional storage.

---

## Phase 11 — Launch checklist

- [ ] `https://echominer.in` loads with a padlock; `http://` and `www.` redirect to `https://echominer.in`
- [ ] `https://<PUBLIC_IP>` does **not** load (origin lock); `http://<PUBLIC_IP>` only redirects to the domain
- [ ] Register with a real address → OTP email arrives (check spam once; mark "not spam") within a minute
- [ ] The three team addresses receive the registration notice
- [ ] OTP unlocks the tool on the same page; reload → tool still unlocked without OTP (trusted device)
- [ ] Other browser → **Already registered? Sign in** → code → unlocked
- [ ] Upload 1–3 real (authorised) PDFs → progress → preview → **Download Excel** → 6 sheets present
- [ ] After download: `/admin` → Platform health shows purge backlog 0
- [ ] `/admin` sign-in with TOTP works; add at least one FAQ / news item and publish it
- [ ] Google Search Console: add `echominer.in` (DNS verification in Cloudflare), submit `https://echominer.in/sitemap.xml`
- [ ] GitHub Actions: CI and Deploy both green on the latest commit

---

## Everyday operations

```bash
cd /opt/echominer
C="docker compose -f infra/compose/docker-compose.yml --env-file .env.deploy"
$C ps                                   # status
$C logs -f --tail 100 api worker        # live logs (Ctrl+C to stop)
$C restart api worker                   # restart after editing apps/api/.env
$C up -d --build web                    # rebuild web after changing NEXT_PUBLIC_* in .env.deploy
infra/scripts/backup.sh manual          # on-demand backup
infra/scripts/restore.sh /var/backups/echominer/<file>.sql.gz   # DESTRUCTIVE restore (asks to confirm)
df -h / && free -h                      # disk and memory
```

**Changing the code:** edit on your PC → commit → push to `main`. Never edit files on the server
(`deploy.sh` resets the server copy to `origin/main`).

**Database schema changes:** edit `apps/api/echominer/models.py`, then locally
`cd apps/api && alembic revision --autogenerate -m "describe change"`, review the generated file in
`alembic/versions/`, commit. The `migrate` service applies it on deploy. CI fails if models and migrations drift.

**Rollback:** `deploy.sh` rolls back code automatically when the smoke test fails. If a migration had
already run and the old code cannot work with the new schema, restore the automatic pre-deploy backup:
`ls -t /var/backups/echominer/ | head` → `infra/scripts/restore.sh <the pre-xxxxxxx file>`.

**The validated extractor** (`apps/api/echominer/vendor/echo_extractor.py`) is never edited. CI checks its
SHA-256 on every push (`d49edd7d…0be322`) and fails if it changes.

## Local development (your PC)

```bash
# API (Python 3.11+; local PostgreSQL, or DATABASE_URL=sqlite+pysqlite:///./dev.db)
cd apps/api && pip install -e ".[dev]" && cp .env.example .env
#   in .env set: ENV=dev, MAIL_PROVIDER=console, CAPTCHA_PROVIDER=null, PUBLIC_BASE_URL=http://localhost:3000
alembic upgrade head
uvicorn echominer.main:app --reload --port 8000      # terminal 1 (OTP codes are printed here in dev)
python -m echominer.worker                           # terminal 2
# Web
cd apps/web && npm ci && API_PROXY=http://localhost:8000 npm run dev   # terminal 3 → http://localhost:3000
```

## Known limitations

| Item | Status |
|---|---|
| Idle reclamation of Always Free VMs | Possible; mitigated by off-VM backups + this runbook (3.4, 10.3) |
| Backups live on the VM | Manual weekly copy off-VM (10.3); automate later if needed |
| Parser defects (docs/PARSER_AUDIT.md) | Extractor runs unchanged by decision; 2 defects change record counts |
| Brevo free tier | 300 emails/day. Each registration sends an OTP plus a team notice to 3 addresses, so roughly 75 registrations/day |
| Single VM | No high availability; a VM outage takes the site down until restart |
