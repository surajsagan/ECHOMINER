import os, sys, pathlib, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
os.environ.update({
    "ENV": "test",
    "DATABASE_URL": os.environ.get("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:"),
    "MAIL_PROVIDER": "console",
    "CAPTCHA_PROVIDER": "null",
    "SECRET_KEY": "test-secret-key",
    "OTP_PEPPER": "test-pepper",
    # Uploads are staged in a throwaway folder, not /var (not writable on CI runners).
    "SPOOL_DIR": tempfile.mkdtemp(prefix="echominer-spool-"),
})

import pytest
from fastapi.testclient import TestClient
from echominer.config import get_settings
from echominer.db import create_all, engine
from echominer.main import app
from echominer.api import deps


@pytest.fixture(scope="session", autouse=True)
def _schema():
    create_all()
    yield
    engine.dispose()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mailer():
    box = deps.get_mailer(get_settings())
    box.outbox.clear()
    return box


def registration_payload(**over):
    base = dict(
        full_name="Test Researcher", designation="Senior Research Fellow",
        affiliation="JSS Medical College", institute="JSS AHER",
        taluk="Mysuru", district="Mysuru", state="Karnataka", country_iso2="IN",
        email="researcher@example.org", phone_e164="+919000000000",
        project_title="Echo registry analysis",
        project_description="Descriptive epidemiology of echocardiography reports.",
        purpose="Structured extraction for a doctoral study.",
        agreement_accepted=True, agreement_text="EchoMiner agreement v1.0 text",
        captcha_token="test-token")
    base.update(over)
    return base
