"""Extraction adapter.

Ruling (8 Aug 2026): the validated pipeline is used AS IS. `echo_extractor.py`
is vendored byte-for-byte and its `extract_echo_data()` is called unchanged, so
the workbook the portal produces is identical to the one the validated script
produces for the same input.

This adapter therefore adds NOTHING to the extraction itself. It only:
  * hands the pipeline a file path (its native input) from tmpfs staging,
  * observes the result -- rows returned, blank rows present, report headers in
    the source -- and records those counts as job metadata,
  * closes the handle and enforces the page cap.

The observations change no column and drop no row. They exist so the Quality
sheet can state what happened, rather than the operator having to infer it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pymupdf

from ..vendor import echo_extractor  # vendored unchanged; do not edit

ENGINE_VERSION = "aiechominer-validated/1.0.0"
DICTIONARY_VERSION = "legacy-47"

# Used only to count report headers for the reconciliation note. Never used to
# parse, split, or modify anything the pipeline produces.
_HEADER_PROBE = re.compile(r"Name\s.+?Age\s*/\s*Gender", re.IGNORECASE | re.DOTALL)


@dataclass
class RawExtraction:
    rows: list[dict[str, Any]] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    page_count: int = 0
    blank_row_count: int = 0
    header_count: int = 0
    warnings: list[str] = field(default_factory=list)
    version: str = ENGINE_VERSION
    dictionary_version: str = DICTIONARY_VERSION

    @property
    def record_count(self) -> int:
        return len(self.rows)


class UnparseableDocument(Exception):
    pass


class DocumentTooLarge(Exception):
    pass


class ValidatedPipelineEngine:
    """Wraps the validated extractor without altering its behaviour."""

    version = ENGINE_VERSION
    dictionary_version = DICTIONARY_VERSION

    def __init__(self, max_pages: int = 2000):
        self.max_pages = max_pages

    def _probe(self, path: Path) -> tuple[int, int]:
        """Read-only inspection for the Quality sheet: page count and how many
        report headers the source contains."""
        doc = pymupdf.open(path)
        try:
            pages = doc.page_count
            text = "".join(page.get_text() for page in doc)
        finally:
            doc.close()
        return pages, len(_HEADER_PROBE.findall(text))

    def extract(self, path: str | Path, *, filename: str | None = None) -> RawExtraction:
        path = Path(path)
        filename = filename or path.name

        pages, headers = self._probe(path)
        if pages > self.max_pages:
            raise DocumentTooLarge(f"{pages} pages exceeds the {self.max_pages}-page limit")

        # --- the validated pipeline, called exactly as published -------------
        df = echo_extractor.extract_echo_data(str(path))
        # --------------------------------------------------------------------

        columns = list(df.columns)
        rows = df.to_dict(orient="records")

        blank = sum(1 for r in rows if all(str(v).strip() == "" for v in r.values()))

        warnings: list[str] = []
        if not rows:
            raise UnparseableDocument("pipeline returned no records (no text layer, or unrecognised layout)")
        if blank:
            warnings.append(f"{blank} row(s) returned with no populated field")
        if headers and headers != len(rows):
            warnings.append(f"reconciliation: {headers} report header(s) in source, {len(rows)} row(s) returned")

        return RawExtraction(rows=rows, columns=columns, page_count=pages,
                             blank_row_count=blank, header_count=headers, warnings=warnings)
