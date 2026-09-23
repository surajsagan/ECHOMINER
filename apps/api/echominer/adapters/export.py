"""Branded XLSX export.

Six sheets: Cover, Data, Quality, Dictionary, Acknowledgement, Citation.
The Data sheet reproduces the pipeline's columns in the pipeline's order --
no reordering, no renaming, no derived columns.

Determinism: same rows + same engine version + same dictionary version produce a
byte-identical Data sheet, so an export can be reproduced years later.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Sequence

from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from ..citation import CANONICAL, all_formats

IST = timezone(timedelta(hours=5, minutes=30))

DEEP = "0E4C6B"
TEAL = "0F9E8E"
MIST = "EEF4F7"
LINE = "D3E1E8"

BRAND_DIR = Path(__file__).resolve().parents[4] / "apps" / "web" / "public" / "brand"

AGREEMENT_TEXT = [
    "EchoMiner was developed at JSS Academy of Higher Education and Research (JSS AHER), Mysore.",
    "Copyright in the software belongs to JSS AHER.",
    "The software is intended for academic and research use.",
    "Users must acknowledge EchoMiner in all publications, theses, conference papers, reports",
    "and scientific communications that use data generated through this tool.",
    "",
    "Developed under the Department of Biotechnology (DBT) BUILDER Project,",
    "Group 3 - Spatial Health Informatics and Management,",
    "Department of Community Medicine, JSS Medical College, JSS AHER, Mysore.",
]


def _header(ws, text: str, row: int = 1) -> None:
    cell = ws.cell(row=row, column=1, value=text)
    cell.font = Font(name="Calibri", size=14, bold=True, color=DEEP)


def _label_value(ws, row: int, label: str, value: Any) -> int:
    ws.cell(row=row, column=1, value=label).font = Font(bold=True, color=DEEP)
    ws.cell(row=row, column=2, value=value)
    return row + 1


def _autosize(ws, max_width: int = 60) -> None:
    for column_cells in ws.columns:
        letter = get_column_letter(column_cells[0].column)
        longest = max((len(str(c.value)) for c in column_cells if c.value is not None), default=0)
        ws.column_dimensions[letter].width = min(max(10, longest + 2), max_width)


def _place_logos(ws, anchor_row: int = 1) -> None:
    """Institutional marks. Absent files are skipped rather than failing the export."""
    for filename, anchor in (("jss-aher-240w.png", "D1"), ("dbt-240w.png", "G1")):
        path = BRAND_DIR / filename
        if not path.exists():
            continue
        img = XLImage(str(path))
        scale = 90 / img.height
        img.height, img.width = 90, int(img.width * scale)
        ws.add_image(img, anchor)


def build_workbook(
    *,
    rows: Sequence[dict[str, Any]],
    columns: Sequence[str],
    job_id: str,
    engine_version: str,
    dictionary_version: str,
    file_summaries: Sequence[dict[str, Any]],
    generated_at: datetime | None = None,
) -> bytes:
    generated_at = generated_at or datetime.now(timezone.utc)
    wb = Workbook()

    # ---------------- Cover ----------------
    cover = wb.active
    cover.title = "Cover"
    _place_logos(cover)
    _header(cover, "EchoMiner - Structured Echocardiography Extraction")
    cover["A2"] = "JSS Academy of Higher Education and Research, Mysore | DBT-BUILDER, Group 3"
    cover["A2"].font = Font(size=11, color=TEAL)
    r = 4
    r = _label_value(cover, r, "Job identifier", job_id)
    r = _label_value(cover, r, "Generated (IST)", generated_at.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"))
    r = _label_value(cover, r, "Generated (UTC)", generated_at.strftime("%Y-%m-%d %H:%M:%S"))
    r = _label_value(cover, r, "Extraction engine", engine_version)
    r = _label_value(cover, r, "Field dictionary", dictionary_version)
    r = _label_value(cover, r, "Files processed", len(file_summaries))
    r = _label_value(cover, r, "Records extracted", len(rows))
    _autosize(cover)

    # ---------------- Data ----------------
    data = wb.create_sheet("Data")
    head_fill = PatternFill("solid", fgColor=DEEP)
    thin = Side(style="thin", color=LINE)
    for idx, name in enumerate(columns, start=1):
        cell = data.cell(row=1, column=idx, value=name)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = head_fill
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        cell.border = Border(bottom=thin)
    for r_idx, row in enumerate(rows, start=2):
        for c_idx, name in enumerate(columns, start=1):
            value = row.get(name, "")
            # Numeric-looking strings become real numbers so the sheet is
            # analysable; the underlying text is never altered.
            if isinstance(value, str):
                stripped = value.strip()
                if stripped and _looks_numeric(stripped):
                    value = float(stripped) if "." in stripped else int(stripped)
                else:
                    value = stripped
            data.cell(row=r_idx, column=c_idx, value=value)
    data.freeze_panes = "A2"
    if rows:
        data.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{len(rows) + 1}"
    _autosize(data, max_width=45)

    # ---------------- Quality ----------------
    quality = wb.create_sheet("Quality")
    _header(quality, "Extraction quality and provenance")
    quality["A2"] = ("Reported exactly as the validated pipeline returned it. No row has been "
                     "removed, corrected or reordered.")
    quality["A2"].font = Font(italic=True, size=9)
    headers = ["Source file", "Pages", "Report headers in source", "Rows returned",
               "Rows with no populated field", "Status", "Notes"]
    for idx, name in enumerate(headers, start=1):
        cell = quality.cell(row=4, column=idx, value=name)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = head_fill
    for r_idx, summary in enumerate(file_summaries, start=5):
        for c_idx, key in enumerate(
                ["filename", "pages", "header_count", "record_count",
                 "blank_row_count", "status", "warnings"], start=1):
            quality.cell(row=r_idx, column=c_idx, value=summary.get(key))
    _autosize(quality, max_width=70)

    # ---------------- Dictionary ----------------
    dictionary = wb.create_sheet("Dictionary")
    _header(dictionary, f"Field dictionary ({dictionary_version})")
    dictionary.cell(row=3, column=1, value="Column").font = Font(bold=True)
    dictionary.cell(row=3, column=2, value="Position").font = Font(bold=True)
    for idx, name in enumerate(columns, start=1):
        dictionary.cell(row=3 + idx, column=1, value=name)
        dictionary.cell(row=3 + idx, column=2, value=idx)
    _autosize(dictionary)

    # ---------------- Acknowledgement ----------------
    ack = wb.create_sheet("Acknowledgement")
    _place_logos(ack)
    _header(ack, "Acknowledgement and terms of use")
    for idx, line in enumerate(AGREEMENT_TEXT, start=3):
        ack.cell(row=idx, column=1, value=line)
    ack.column_dimensions["A"].width = 100

    # ---------------- Citation ----------------
    cite = wb.create_sheet("Citation")
    _header(cite, "How to cite EchoMiner")
    cite["A2"] = "Cite the software in any publication, thesis or report using data generated by this tool."
    cite["A2"].font = Font(italic=True, size=9)
    row = 4
    for style, text in all_formats().items():
        cite.cell(row=row, column=1, value=style.upper()).font = Font(bold=True, color=DEEP)
        target = cite.cell(row=row, column=2, value=text)
        target.alignment = Alignment(wrap_text=True, vertical="top")
        cite.row_dimensions[row].height = 15 * (1 + text.count("\n"))
        row += 2
    cite.column_dimensions["A"].width = 12
    cite.column_dimensions["B"].width = 110
    cite.cell(row=row + 1, column=1, value="DOI").font = Font(bold=True, color=DEEP)
    cite.cell(row=row + 1, column=2, value=CANONICAL.url)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _looks_numeric(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True
