"""Single-service hosting (Render free tier): DB URL handling, Brevo HTTPS mailer,
in-process rate limiting, static site serving, embedded worker, admin bootstrap."""
import json

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from echominer.adapters.mail import BrevoApiMailer, build_mailer
from echominer.config import Settings
from echominer.models import Admin, Base
from echominer.ratelimit import RateLimiter


# -- database URL -------------------------------------------------------------
@pytest.mark.parametrize("given", [
    "postgres://u:p@ep-x.ap-southeast-1.aws.neon.tech/neondb?sslmode=require",
    "postgresql://u:p@ep-x.ap-southeast-1.aws.neon.tech/neondb?sslmode=require",
])
def test_hosted_postgres_urls_get_the_psycopg_driver(given):
    s = Settings(database_url=given)
    assert s.database_url.startswith("postgresql+psycopg://u:p@ep-x.")
    assert s.database_url.endswith("?sslmode=require")


def test_explicit_driver_and_sqlite_urls_untouched():
    for url in ("postgresql+psycopg://a@h/db", "sqlite+pysqlite:///:memory:"):
        assert Settings(database_url=url).database_url == url


# -- Brevo HTTPS mailer ------------------------------------------------------------
def _brevo(handler):
    settings = Settings(mail_provider="brevo_api", brevo_api_key="xkeysib-test")
    return BrevoApiMailer(settings, client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_brevo_mailer_sends_expected_payload():
    seen = {}

    def handler(request: httpx.Request):
        seen["url"] = str(request.url)
        seen["key"] = request.headers["api-key"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(201, json={"messageId": "<abc@relay>"})

    mid = _brevo(handler).send(to=["a@example.org"], subject="Code", text="Your code is 123456 <b>")
    assert mid == "<abc@relay>"
    assert seen["url"] == "https://api.brevo.com/v3/smtp/email"
    assert seen["key"] == "xkeysib-test"
    body = seen["body"]
    assert body["sender"] == {"name": "EchoMiner", "email": "noreply@echominer.in"}
    assert body["to"] == [{"email": "a@example.org"}]
    assert body["replyTo"] == {"email": "aiechominer@gmail.com"}
    assert body["textContent"] == "Your code is 123456 <b>"
    assert "&lt;b&gt;" in body["htmlContent"]           # text is escaped into the HTML part


def test_brevo_mailer_raises_on_rejection():
    mailer = _brevo(lambda r: httpx.Response(401, json={"message": "Key not found"}))
    with pytest.raises(RuntimeError, match="401"):
        mailer.send(to=["a@example.org"], subject="s", text="t")


def test_brevo_mailer_requires_key():
    with pytest.raises(ValueError):
        build_mailer(Settings(mail_provider="brevo_api", brevo_api_key=""))


# -- rate limiter ------------------------------------------------------------------
def test_rate_limiter_blocks_after_limit_and_recovers():
    now = [1000.0]
    rl = RateLimiter(clock=lambda: now[0])
    for _ in range(10):
        assert rl.check("1.2.3.4", "/api/v1/auth/otp/verify", "POST") is None
    wait = rl.check("1.2.3.4", "/api/v1/auth/otp/verify", "POST")
    assert wait is not None and wait >= 1
    assert rl.check("5.6.7.8", "/api/v1/auth/otp/verify", "POST") is None   # per IP
    assert rl.check("1.2.3.4", "/", "GET") is None                          # site pages unlimited
    now[0] += 61
    assert rl.check("1.2.3.4", "/api/v1/auth/otp/verify", "POST") is None


# -- static site ----------------------------------------------------------------------
def test_site_files_serve_pages_and_cache_hashed_assets(tmp_path):
    from echominer.main import _SiteFiles
    (tmp_path / "index.html").write_text("<h1>home</h1>")
    (tmp_path / "admin").mkdir()
    (tmp_path / "admin" / "index.html").write_text("<h1>admin</h1>")
    (tmp_path / "404.html").write_text("<h1>missing</h1>")
    (tmp_path / "_next" / "static").mkdir(parents=True)
    (tmp_path / "_next" / "static" / "app.js").write_text("x")
    app = FastAPI()

    @app.get("/api/v1/ping")
    def ping():
        return {"ok": True}

    app.mount("/", _SiteFiles(directory=tmp_path, html=True))
    c = TestClient(app)
    assert c.get("/api/v1/ping").json() == {"ok": True}                  # API wins
    assert "home" in c.get("/").text
    assert "admin" in c.get("/admin/").text
    assert c.get("/admin", follow_redirects=True).status_code == 200
    r = c.get("/_next/static/app.js")
    assert "immutable" in r.headers["cache-control"]
    missing = c.get("/no-such-page")
    assert missing.status_code == 404 and "missing" in missing.text


# -- embedded worker ------------------------------------------------------------------
def test_embedded_worker_picks_up_a_job_as_soon_as_it_is_notified(client, mailer):
    """The worker runs in a thread; with a 60 s idle poll, only notify() can
    make it start the job within the test's time limit."""
    import time
    from test_jobs import pdf_bytes, sign_in
    from echominer import worker
    from echominer.config import get_settings
    if get_settings().database_url.startswith("sqlite"):
        pytest.skip("threads need a real connection pool (runs on PostgreSQL in CI)")
    sign_in(client, mailer, "embedded@example.org")
    settings = get_settings().model_copy(update={"worker_poll_seconds": 60})
    thread, stop = worker.start_embedded(settings)
    try:
        time.sleep(0.5)                                   # worker is now idle, waiting
        r = client.post("/api/v1/jobs", files=[("files", ("a.pdf", pdf_bytes(), "application/pdf"))])
        assert r.status_code == 202
        job_id = r.json()["id"]
        deadline = time.time() + 20
        status = None
        while time.time() < deadline:
            status = client.get(f"/api/v1/jobs/{job_id}").json()["status"]
            if status in ("completed", "partial", "failed"):
                break
            time.sleep(0.2)
        assert status == "completed"
    finally:
        stop.set()
        worker.notify()
        thread.join(timeout=10)
    assert not thread.is_alive()


# -- admin bootstrap ------------------------------------------------------------------
def test_bootstrap_admin_creates_first_admin_once(monkeypatch, capsys):
    from echominer import cli
    engine = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    monkeypatch.setattr(cli, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False))
    from echominer.config import get_settings
    boot = get_settings().model_copy(update={"admin_bootstrap_email": "ops@echominer.in",
                                             "admin_bootstrap_password": "a-long-admin-password"})
    monkeypatch.setattr(cli, "get_settings", lambda: boot)

    cli.bootstrap_admin()
    out = capsys.readouterr().out
    assert "created administrator ops@echominer.in" in out and "otpauth://totp/" in out

    cli.bootstrap_admin()                                 # second start: no-op
    assert "already exists" in capsys.readouterr().out
    with sessionmaker(bind=engine)() as db:
        assert db.scalar(select(func.count()).select_from(Admin)) == 1


def test_bootstrap_admin_does_nothing_without_env(monkeypatch, capsys):
    from echominer import cli
    from echominer.config import get_settings
    monkeypatch.setattr(cli, "get_settings", lambda: get_settings().model_copy(
        update={"admin_bootstrap_email": "", "admin_bootstrap_password": ""}))
    cli.bootstrap_admin()
    assert capsys.readouterr().out == ""
