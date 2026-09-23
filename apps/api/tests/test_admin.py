"""M9/M10 acceptance: admin auth with TOTP, oversight, analytics, CMS."""
import time
import pytest
from conftest import registration_payload
from echominer.config import get_settings
from echominer.db import SessionLocal
from echominer.security import new_totp_secret, totp_at
from echominer.services.admin import AdminService

PASSWORD = "a-long-admin-password"


@pytest.fixture(scope="module")
def admin_account():
    secret = new_totp_secret()
    with SessionLocal() as db:
        AdminService(db, get_settings()).create_admin(
            email="admin@echominer.in", password=PASSWORD, totp_secret=secret)
        db.commit()
    return {"email": "admin@echominer.in", "secret": secret}


def code_for(secret: str) -> str:
    return totp_at(secret, int(time.time()) // 30)


def sign_in_admin(client, account):
    return client.post("/api/v1/admin/auth/login", json={
        "email": account["email"], "password": PASSWORD, "totp_code": code_for(account["secret"])})


def test_password_alone_is_not_enough(client, admin_account):
    r = client.post("/api/v1/admin/auth/login",
                    json={"email": admin_account["email"], "password": PASSWORD})
    assert r.status_code == 401


def test_wrong_password_rejected(client, admin_account):
    r = client.post("/api/v1/admin/auth/login", json={
        "email": admin_account["email"], "password": "wrong-password-here",
        "totp_code": code_for(admin_account["secret"])})
    assert r.status_code == 401


def test_login_with_totp_and_whoami(client, admin_account):
    assert sign_in_admin(client, admin_account).status_code == 200
    assert client.get("/api/v1/admin/me").json()["email"] == admin_account["email"]


def test_admin_endpoints_require_admin_session(client):
    from fastapi.testclient import TestClient
    from echominer.main import app
    anon = TestClient(app)
    for path in ("/api/v1/admin/users", "/api/v1/admin/otp-logs",
                 "/api/v1/admin/analytics/usage", "/api/v1/admin/health"):
        assert anon.get(path).status_code == 401, path


def test_user_session_cannot_reach_admin(client, mailer):
    """A verified researcher session must not be an admin session."""
    import re
    from fastapi.testclient import TestClient
    from echominer.main import app
    user_client = TestClient(app)
    email = "notadmin@example.org"
    user_client.post("/api/v1/registrations", json=registration_payload(email=email))
    code = next(re.search(r"\b(\d{6})\b", m["text"]).group(1)
                for m in reversed(mailer.outbox) if m["template"] == "otp" and email in m["to"])
    user_client.post("/api/v1/auth/otp/verify", json={"email": email, "code": code})
    assert user_client.get("/api/v1/me").status_code == 200
    assert user_client.get("/api/v1/admin/users").status_code == 401


def test_user_search_and_csv_export(client, mailer, admin_account):
    client.post("/api/v1/registrations", json=registration_payload(
        email="searchable@example.org", full_name="Findable Researcher", institute="KMC Manipal"))
    sign_in_admin(client, admin_account)

    page = client.get("/api/v1/admin/users", params={"search": "findable"}).json()
    assert page["total"] >= 1
    assert any(u["full_name"] == "Findable Researcher" for u in page["items"])

    csv_text = client.get("/api/v1/admin/users.csv").text
    assert "searchable@example.org" in csv_text and csv_text.startswith("id,email")


def test_otp_log_never_exposes_the_code(client, mailer, admin_account):
    email = "logged@example.org"
    client.post("/api/v1/registrations", json=registration_payload(email=email))
    import re
    code = next(re.search(r"\b(\d{6})\b", m["text"]).group(1)
                for m in reversed(mailer.outbox) if m["template"] == "otp" and email in m["to"])
    sign_in_admin(client, admin_account)
    entries = client.get("/api/v1/admin/otp-logs").json()
    entry = next(e for e in entries if e["email"] == email)
    assert set(entry) == {"email", "purpose", "attempts", "verified", "locked",
                          "expires_at", "created_at"}
    assert code not in str(entries), "the OTP code must never appear in the log"


def test_analytics_and_health(client, admin_account):
    sign_in_admin(client, admin_account)
    usage = client.get("/api/v1/admin/analytics/usage").json()
    assert usage["summary"]["users_total"] >= 1
    assert isinstance(usage["timeseries"], list)

    geo = client.get("/api/v1/admin/analytics/geo").json()
    assert any(row["country"] == "IN" for row in geo["countries"])
    assert isinstance(client.get("/api/v1/admin/analytics/projects").json(), list)

    health = client.get("/api/v1/admin/health").json()
    assert set(health) >= {"queue_depth", "running", "purge_backlog", "failed_jobs", "status"}


def test_disabling_a_user_blocks_re_registration(client, mailer, admin_account):
    email = "blocked@example.org"
    client.post("/api/v1/registrations", json=registration_payload(email=email))
    sign_in_admin(client, admin_account)
    user = next(u for u in client.get("/api/v1/admin/users",
                                      params={"search": email}).json()["items"])
    assert client.post(f"/api/v1/admin/users/{user['id']}/status",
                       json={"status": "disabled"}).status_code == 200
    assert client.post("/api/v1/registrations",
                       json=registration_payload(email=email)).status_code == 400


def test_content_lifecycle_draft_then_publish(client, admin_account):
    sign_in_admin(client, admin_account)
    item = client.post("/api/v1/admin/content", json={
        "kind": "news", "slug": "launch", "title": "EchoMiner is live",
        "body_md": "The platform is open to researchers.", "published": False}).json()
    assert item["published_at"] is None

    # a draft is invisible publicly
    assert client.get("/api/v1/content/news").json() == []

    client.post("/api/v1/admin/content", json={
        "kind": "news", "slug": "launch", "title": "EchoMiner is live",
        "body_md": "The platform is open to researchers.", "published": True,
        "item_id": item["id"]})
    public = client.get("/api/v1/content/news").json()
    assert len(public) == 1 and public[0]["title"] == "EchoMiner is live"

    assert client.delete(f"/api/v1/admin/content/{item['id']}").status_code == 200
    assert client.get("/api/v1/content/news").json() == []


def test_public_content_rejects_unknown_kind(client):
    assert client.get("/api/v1/content/secrets").status_code == 404


def test_audit_trail_records_admin_actions(client, admin_account):
    sign_in_admin(client, admin_account)
    actions = {row["action"] for row in client.get("/api/v1/admin/audit").json()}
    assert "admin.login" in actions
