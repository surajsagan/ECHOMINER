"""M4 acceptance: the validated pipeline is used unchanged and its output is untouched."""
import hashlib, pathlib, sys
import pymupdf, pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from echominer.adapters.extraction import ValidatedPipelineEngine, UnparseableDocument
from echominer.vendor import echo_extractor

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


def _pdf(tmp_path, text, name="r.pdf"):
    path = tmp_path / name
    doc = pymupdf.open(); page = doc.new_page(); page.insert_text((40, 50), text, fontsize=8)
    doc.save(path); doc.close()
    return path


def test_vendored_pipeline_is_byte_identical_to_the_validated_source():
    vendored = pathlib.Path(echo_extractor.__file__).read_bytes()
    original = pathlib.Path("/mnt/user-data/uploads/echo_extractor.py")
    if original.exists():
        assert hashlib.sha256(vendored).hexdigest() == hashlib.sha256(original.read_bytes()).hexdigest()


def test_adapter_output_matches_pipeline_output_exactly(tmp_path):
    path = _pdf(tmp_path, REPORT)
    direct = echo_extractor.extract_echo_data(str(path)).to_dict(orient="records")
    viaapi = ValidatedPipelineEngine().extract(path).rows
    assert viaapi == direct, "the adapter must not alter a single value the pipeline returns"


def test_adapter_reports_but_does_not_remove_blank_rows(tmp_path):
    path = _pdf(tmp_path, REPORT + "\nJSS Hospital, Mysuru | Page 1 of 1\n")
    result = ValidatedPipelineEngine().extract(path)
    assert result.record_count == len(echo_extractor.extract_echo_data(str(path)))
    assert result.blank_row_count == 1
    assert any("no populated field" in w for w in result.warnings)


def test_reconciliation_note_when_headers_and_rows_disagree(tmp_path):
    text = REPORT + REPORT.replace("TEST PATIENT", "SECOND").replace("Echo Technologist", "") + REPORT.replace("TEST PATIENT", "THIRD")
    result = ValidatedPipelineEngine().extract(_pdf(tmp_path, text))
    assert result.header_count == 3
    assert any("reconciliation" in w for w in result.warnings)


def test_empty_text_layer_raises(tmp_path):
    path = tmp_path / "blank.pdf"
    doc = pymupdf.open(); doc.new_page(); doc.save(path); doc.close()
    with pytest.raises(UnparseableDocument):
        ValidatedPipelineEngine().extract(path)


def test_page_cap_enforced(tmp_path):
    from echominer.adapters.extraction import DocumentTooLarge
    doc = pymupdf.open()
    for _ in range(3):
        doc.new_page().insert_text((40, 50), REPORT, fontsize=8)
    path = tmp_path / "many.pdf"; doc.save(path); doc.close()
    with pytest.raises(DocumentTooLarge):
        ValidatedPipelineEngine(max_pages=2).extract(path)


def test_export_module_imports_in_shallow_container_layout(tmp_path):
    """Regression: the API image puts the package at /app/echominer, only four
    directories deep. A hard-coded parents[4] lookup crashed the import."""
    import shutil
    import subprocess
    import sys
    from pathlib import Path
    src = Path(__file__).resolve().parents[1] / "echominer"
    root = tmp_path / "app"
    shutil.copytree(src, root / "echominer", ignore=shutil.ignore_patterns("__pycache__"))
    code = "import echominer.adapters.export as e; print(e.BRAND_DIR)"
    r = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
