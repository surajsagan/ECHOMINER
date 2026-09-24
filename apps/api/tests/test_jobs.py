"""M5/M6 acceptance: upload validation, processing, ownership, export, purge."""
import io, re
import pymupdf, pytest
from openpyxl import load_workbook
from conftest import registration_payload

REPORT = """Name  TEST PATIENT  Age / Gender : 54 / M
Address  Mysuru
AO 32 mm
LA 38 mm
EF : 61 %
FINDINGS
Left Ventricle : Normal in size
IMPRESSION
1. Mild mitral regurgitation
Echo Technologist
"""


def pdf_bytes(text=REPORT):
    doc = pymupdf.open(); doc.new_page().insert_text((40, 50), text, fontsize=8)
    buf = io.BytesIO(); doc.save(buf); doc.close()
    return buf.getvalue()


def sign_in(client, mailer, email):
    client.post("/api/v1/registrations", json=registration_payload(email=email))
    code = next(re.search(r"\b(\d{6})\b", m["text"]).group(1)
                for m in reversed(mailer.outbox) if m["template"] == "otp" and email in m["to"])
    client.post("/api/v1/auth/otp/verify", json={"email": email, "code": code})


def drain():
    """Run the worker inline until the queue is empty, as the worker loop does.
    Draining only one job would make tests depend on execution order."""
    from echominer.config import get_settings
    from echominer.db import SessionLocal
    from echominer.services.jobs import JobService
    processed = 0
    while True:
        with SessionLocal() as db:
            job = JobService(db, get_settings()).run_next()
            db.commit()
        if job is None:
            return processed
        processed += 1


def test_upload_requires_authentication(client):
    r = client.post("/api/v1/jobs", files=[("files", ("a.pdf", pdf_bytes(), "application/pdf"))])
    assert r.status_code == 401


def test_rejects_more_than_twenty_files(client, mailer):
    sign_in(client, mailer, "many@example.org")
    files = [("files", (f"r{i}.pdf", pdf_bytes(), "application/pdf")) for i in range(21)]
    r = client.post("/api/v1/jobs", files=files)
    assert r.status_code == 413 and "20 files" in r.json()["detail"]


def test_rejects_non_pdf_and_active_content(client, mailer):
    sign_in(client, mailer, "bad@example.org")
    r = client.post("/api/v1/jobs", files=[("files", ("x.pdf", b"not a pdf at all", "application/pdf"))])
    assert r.status_code == 400 and "not a valid PDF" in r.json()["detail"]

    laced = b"%PDF-1.7\n/OpenAction << /S /Launch >>\n"
    r = client.post("/api/v1/jobs", files=[("files", ("y.pdf", laced, "application/pdf"))])
    assert r.status_code == 400 and "active content" in r.json()["detail"]


def test_job_runs_and_preview_matches_pipeline_columns(client, mailer):
    sign_in(client, mailer, "run@example.org")
    r = client.post("/api/v1/jobs", files=[("files", ("r.pdf", pdf_bytes(), "application/pdf"))])
    job_id = r.json()["id"]
    assert client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "queued"

    drain()
    state = client.get(f"/api/v1/jobs/{job_id}").json()
    assert state["status"] == "completed" and state["record_count"] == 1

    preview = client.get(f"/api/v1/jobs/{job_id}/preview").json()
    assert preview["columns"][:3] == ["Name", "Age / Gender", "Address"]
    assert len(preview["columns"]) == 47, "pipeline column set must pass through untouched"
    assert preview["rows"][0]["Name"] == "TEST PATIENT"
    assert preview["rows"][0]["EF"] == "61"


def test_another_user_cannot_see_the_job(client, mailer):
    from fastapi.testclient import TestClient
    from echominer.main import app
    sign_in(client, mailer, "owner@example.org")
    job_id = client.post("/api/v1/jobs",
                         files=[("files", ("r.pdf", pdf_bytes(), "application/pdf"))]).json()["id"]
    other = TestClient(app)
    sign_in(other, mailer, "intruder@example.org")
    # 404, not 403: existence must not be confirmed to a non-owner.
    assert other.get(f"/api/v1/jobs/{job_id}").status_code == 404
    assert other.get(f"/api/v1/jobs/{job_id}/export.xlsx").status_code == 404


def test_export_workbook_has_all_sheets_and_purges_artefacts(client, mailer):
    sign_in(client, mailer, "export@example.org")
    job_id = client.post("/api/v1/jobs",
                         files=[("files", ("r.pdf", pdf_bytes(), "application/pdf"))]).json()["id"]
    drain()
    r = client.get(f"/api/v1/jobs/{job_id}/export.xlsx")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats")

    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Cover", "Data", "Quality", "Dictionary", "Acknowledgement", "Citation"]
    data = wb["Data"]
    assert [c.value for c in data[1]][:2] == ["Name", "Age / Gender"]
    assert data.cell(row=2, column=1).value == "TEST PATIENT"
    assert data.cell(row=2, column=4).value == 32, "numeric strings become numeric cells"
    cite_text = "\n".join(str(c.value) for row in wb["Citation"].iter_rows() for c in row if c.value)
    assert "10.5281/zenodo.21281483" in cite_text

    # download purges artefacts; a second download is Gone, not a stale file
    assert client.get(f"/api/v1/jobs/{job_id}").json()["purged"] is True
    assert client.get(f"/api/v1/jobs/{job_id}/export.xlsx").status_code == 410
    assert client.get(f"/api/v1/jobs/{job_id}/preview").json()["total"] == 0


def test_quality_sheet_reports_blank_rows_without_removing_them(client, mailer):
    sign_in(client, mailer, "quality@example.org")
    content = pdf_bytes(REPORT + "\nJSS Hospital, Mysuru | Page 1 of 1\n")
    job_id = client.post("/api/v1/jobs",
                         files=[("files", ("q.pdf", content, "application/pdf"))]).json()["id"]
    drain()
    preview = client.get(f"/api/v1/jobs/{job_id}/preview").json()
    assert preview["total"] == 2, "pipeline output passes through unfiltered"

    wb = load_workbook(io.BytesIO(client.get(f"/api/v1/jobs/{job_id}/export.xlsx").content))
    quality = wb["Quality"]
    header = [c.value for c in quality[4]]
    values = dict(zip(header, [c.value for c in quality[5]]))
    assert values["Rows returned"] == 2
    assert values["Rows with no populated field"] == 1
    assert "no populated field" in (values["Notes"] or "")


def test_abandoned_job_is_swept(client, mailer):
    from echominer.config import get_settings
    from echominer.db import SessionLocal
    from echominer.security import expires_in
    from echominer.services.jobs import JobService
    sign_in(client, mailer, "sweep@example.org")
    job_id = client.post("/api/v1/jobs",
                         files=[("files", ("r.pdf", pdf_bytes(), "application/pdf"))]).json()["id"]
    drain()
    with SessionLocal() as db:
        service = JobService(db, get_settings())
        from echominer.models import ExtractionJob
        db.get(ExtractionJob, __import__("uuid").UUID(job_id)).purge_after = expires_in(-10)
        db.commit()
        assert service.purge_expired() >= 1
        db.commit()
    assert client.get(f"/api/v1/jobs/{job_id}").json()["purged"] is True


def test_row_order_is_stable_across_files(client, mailer):
    """Two files uploaded together must always yield the same row order."""
    sign_in(client, mailer, "order@example.org")
    files = [("files", (f"z{i}.pdf", pdf_bytes(REPORT.replace("TEST PATIENT", f"P{i}")),
                        "application/pdf")) for i in range(3)]
    job_id = client.post("/api/v1/jobs", files=files).json()["id"]
    drain()
    names = [r["Name"] for r in client.get(f"/api/v1/jobs/{job_id}/preview").json()["rows"]]
    assert names == ["P0", "P1", "P2"], f"row order follows filename, got {names}"


def test_citation_endpoint_formats():
    from echominer.citation import all_formats
    formats = all_formats()
    assert set(formats) == {"apa", "vancouver", "ieee", "bibtex", "ris"}
    assert all("10.5281/zenodo.21281483" in text for text in formats.values())
    assert formats["apa"].startswith("B Manjunath, S. (2026).")
    assert formats["bibtex"].startswith("@software{echominer2026,")
    assert formats["ris"].startswith("TY  - COMP")


def test_export_is_deterministic():
    from datetime import datetime, timezone
    from echominer.adapters.export import build_workbook
    args = dict(rows=[{"Name": "A", "EF": "60"}], columns=["Name", "EF"], job_id="j1",
                engine_version="e1", dictionary_version="d1", file_summaries=[],
                generated_at=datetime(2026, 8, 8, tzinfo=timezone.utc))
    first, second = build_workbook(**args), build_workbook(**args)
    wb1, wb2 = load_workbook(io.BytesIO(first)), load_workbook(io.BytesIO(second))
    assert [[c.value for c in r] for r in wb1["Data"]] == [[c.value for c in r] for r in wb2["Data"]]


def _multi_page_pdf(pages):
    doc = pymupdf.open()
    for i in range(pages):
        doc.new_page().insert_text((40, 50), REPORT if i == 0 else f"page {i}", fontsize=8)
    buf = io.BytesIO(); doc.save(buf); doc.close()
    return buf.getvalue()


def test_page_limits_reject_oversized_submissions_before_processing(client, mailer, monkeypatch):
    from echominer.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "max_pages_per_file", 5)
    monkeypatch.setattr(settings, "max_pages_per_job", 8)
    sign_in(client, mailer, "pages@example.org")

    r = client.post("/api/v1/jobs", files=[("files", ("big.pdf", _multi_page_pdf(6), "application/pdf"))])
    assert r.status_code == 400 and "6 pages; the limit is 5 pages per file" in r.json()["detail"]

    two = [("files", (f"q{i}.pdf", _multi_page_pdf(5), "application/pdf")) for i in range(2)]
    r = client.post("/api/v1/jobs", files=two)
    assert r.status_code == 400 and "10 pages in total" in r.json()["detail"]
    assert "8 pages per submission" in r.json()["detail"]

    ok = [("files", (f"q{i}.pdf", _multi_page_pdf(4), "application/pdf")) for i in range(2)]
    assert client.post("/api/v1/jobs", files=ok).status_code == 202
    drain()
