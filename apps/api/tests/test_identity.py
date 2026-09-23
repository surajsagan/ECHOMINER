"""M2 acceptance tests: registration, OTP, trusted-device restore, theft detection."""
import re
from conftest import registration_payload


def _otp_from(mailer, email):
    for msg in reversed(mailer.outbox):
        if msg["template"] == "otp" and email in msg["to"]:
            return re.search(r"\b(\d{6})\b", msg["text"]).group(1)
    raise AssertionError("no OTP mail captured")


def test_registration_sends_otp_and_team_notice(client, mailer):
    r = client.post("/api/v1/registrations", json=registration_payload(email="a@example.org"))
    assert r.status_code == 202
    templates = [m["template"] for m in mailer.outbox]
    assert "otp" in templates and "registration_notice" in templates
    notice = next(m for m in mailer.outbox if m["template"] == "registration_notice")
    assert set(notice["to"]) == {"surajbm@jssuni.edu.in", "madhub@jssuni.edu.in", "aiechominer@gmail.com"}


def test_agreement_must_be_accepted(client):
    r = client.post("/api/v1/registrations", json=registration_payload(agreement_accepted=False))
    assert r.status_code == 422


def test_open_registration_accepts_any_domain(client, mailer):
    for email in ("someone@gmail.com", "prof@harvard.edu", "x@jssuni.edu.in"):
        assert client.post("/api/v1/registrations", json=registration_payload(email=email)).status_code == 202


def test_otp_verification_unlocks_tool_and_sets_cookies(client, mailer):
    email = "verify@example.org"
    client.post("/api/v1/registrations", json=registration_payload(email=email))
    code = _otp_from(mailer, email)
    r = client.post("/api/v1/auth/otp/verify", json={"email": email, "code": code})
    assert r.status_code == 200 and r.json()["tool_unlocked"] is True
    assert "__Host-em_session" in r.cookies and "__Host-em_device" in r.cookies
    assert client.get("/api/v1/me").json()["email"] == email


def test_wrong_code_rejected_and_locks_after_max_attempts(client, mailer):
    email = "brute@example.org"
    client.post("/api/v1/registrations", json=registration_payload(email=email))
    for _ in range(5):
        assert client.post("/api/v1/auth/otp/verify", json={"email": email, "code": "000000"}).status_code == 400
    correct = _otp_from(mailer, email)
    assert client.post("/api/v1/auth/otp/verify", json={"email": email, "code": correct}).status_code == 400


def test_returning_device_restores_without_otp(client, mailer):
    email = "return@example.org"
    client.post("/api/v1/registrations", json=registration_payload(email=email))
    client.post("/api/v1/auth/otp/verify", json={"email": email, "code": _otp_from(mailer, email)})
    device_before = client.cookies.get("__Host-em_device")
    client.cookies.delete("__Host-em_session")            # session gone, device remembered
    r = client.post("/api/v1/auth/session/restore")
    assert r.status_code == 200 and r.json()["tool_unlocked"] is True
    assert client.cookies.get("__Host-em_device") != device_before, "validator must rotate on use"
    assert client.get("/api/v1/me").status_code == 200


def test_unknown_device_requires_step_up(client):
    from fastapi.testclient import TestClient
    from echominer.main import app
    fresh = TestClient(app)
    assert fresh.post("/api/v1/auth/session/restore").status_code == 401


def test_stale_validator_is_treated_as_theft(client, mailer):
    from fastapi.testclient import TestClient
    from echominer.main import app
    email = "theft@example.org"
    client.post("/api/v1/registrations", json=registration_payload(email=email))
    client.post("/api/v1/auth/otp/verify", json={"email": email, "code": _otp_from(mailer, email)})
    stolen = client.cookies.get("__Host-em_device")

    client.cookies.delete("__Host-em_session")
    client.post("/api/v1/auth/session/restore")           # legitimate use rotates the validator

    attacker = TestClient(app)
    attacker.cookies.set("__Host-em_device", stolen)
    assert attacker.post("/api/v1/auth/session/restore").status_code == 401

    client.cookies.delete("__Host-em_session")
    assert client.post("/api/v1/auth/session/restore").status_code == 401, \
        "reuse must revoke every device for that user, including the legitimate one"


def test_sign_out_revokes_session(client, mailer):
    email = "out@example.org"
    client.post("/api/v1/registrations", json=registration_payload(email=email))
    client.post("/api/v1/auth/otp/verify", json={"email": email, "code": _otp_from(mailer, email)})
    assert client.delete("/api/v1/auth/session").status_code == 200
    assert client.get("/api/v1/me").status_code == 401


def test_health_endpoints(client):
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").json()["database"] == "ok"


def test_registered_user_can_sign_in_on_new_device_via_resend(client, mailer):
    email = "newdevice@example.org"
    client.post("/api/v1/registrations", json=registration_payload(email=email))
    client.post("/api/v1/auth/otp/verify", json={"email": email, "code": _otp_from(mailer, email)})
    client.cookies.clear()                       # a different browser / device
    mailer.outbox.clear()
    r = client.post("/api/v1/auth/otp/resend", json={"email": email, "captcha_token": "t"})
    assert r.status_code == 202
    r = client.post("/api/v1/auth/otp/verify", json={"email": email, "code": _otp_from(mailer, email)})
    assert r.status_code == 200
    assert client.get("/api/v1/me").json()["email"] == email


def test_resend_never_mails_unregistered_addresses(client, mailer):
    mailer.outbox.clear()
    r = client.post("/api/v1/auth/otp/resend", json={"email": "stranger@example.org", "captcha_token": "t"})
    assert r.status_code == 202                  # same response: no account enumeration
    assert mailer.outbox == []
