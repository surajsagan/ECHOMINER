# `echo_extractor.py` — audit and hardening report

**Audited:** 8 August 2026 · **Subject:** uploaded `echo_extractor.py` (v1), `requirements.txt`
**Method:** static review plus execution against synthetic multi-report PDFs built to exercise each suspected path. Every finding below was **reproduced**, not inferred. Reproductions are in `test_engine.py`.
**Result:** v1's extraction logic is sound and its regex approach is appropriate. Two defects in *segmentation* affect record counts in both directions and are worth your attention independent of this web build, because the same code produced the corpus behind the manuscript.

---

## Severity summary

| ID | Defect | Severity | Effect on results |
|---|---|---|---|
| A1 | Trailing page furniture emits a phantom all-blank row | **High** | Inflates N |
| A2 | Missing `Echo Technologist` footer silently destroys a whole report | **High** | Deflates N, total loss of that record |
| A3 | No reconciliation between headers present and rows emitted | **High** | A1/A2 are invisible to the operator |
| A4 | Measurement patterns reject common formatting variants | Medium | Overstates clinical missingness |
| A5 | Every value is a string; missing is `""` not `NaN` | Medium | Downstream numeric analysis needs re-coercion |
| A6 | `Name` is lost when `Age / Gender` is absent; the fallback is dead code | Medium | Silent identity loss |
| A7 | Bullet-stripping class misses the markers actually used | Low–Medium | Enumeration prefixes contaminate impression text |
| A8 | Impressions beyond 10 are silently discarded | Medium | Unrecorded truncation |
| A9 | No provenance (page, record index) and no per-record warnings | Medium | Findings are not traceable to source |
| A10 | `fitz.Document` never closed | Low | Handle/memory leak in a long-running worker |
| A11 | A PDF with no text layer returns an empty frame, not an error | Medium | Scanned files fail silently |

---

## A1 — Phantom rows from page furniture

`re.split(r"Echo Technologist", full_text)` treats the footer as a *terminator*. Any text after the final footer — a hospital footer line, "Page 1 of 1", a print timestamp — becomes an extra chunk. It is non-empty, so the `if not entry: continue` guard does not catch it, and a row of 47 empty strings is appended.

```
Input : one report + "JSS Hospital, Mysuru | Page 1 of 1"
v1    : 2 rows  (row 2 is entirely blank)
v2    : 1 row
```

**Why it matters:** if the archive PDFs carry per-document footers, every file contributed one spurious record. A row that is blank in all 47 columns is easy to drop retrospectively — worth confirming your published N was computed after such a filter.

## A2 — Silent record loss on a missing separator

Segmentation is driven by *separator count*, so `n` footers yield `n+1` chunks regardless of how many reports are present. When a report lacks its footer, its text is absorbed into the neighbouring chunk, and because every pattern uses `.search()` (first match wins), only the earlier report's values are captured. The later report vanishes with no error.

```
Input : three reports, middle footer missing
v1    : 2 rows  → ['P1', 'P2']   (P3 lost entirely)
v2    : 3 rows  → ['P1', 'P2', 'P3']
```

**Why it matters:** this is the failure mode most likely to explain a corpus count that does not match the source archive. It is directionally opposite to A1, so the two can partially mask each other in aggregate.

**Fix:** v2 segments on the record **header** (`Name … Age / Gender`), which every report has by construction, and treats the footer as an end-of-record trim rather than a delimiter.

## A3 — No reconciliation

Neither failure above raises anything. v2 counts report headers in the file, compares against rows emitted, and attaches a warning when they disagree. The count is surfaced per file in the platform's Quality sheet.

**Recommended, cheap, and independent of this project:** re-run your archive through v2 and compare `record_count` against your recorded N per file. It is a single pass and it either confirms your published figure or tells you the exact files that differ.

## A4 — Formatting brittleness

`r"AO\s+(\d+(?:\.\d+)?)\s*mm"` requires whitespace after the label and treats the unit as mandatory-adjacent.

```
"AO: 32mm"  → v1: ''      v2: 32.0
"LA - 38 mm"→ v1: ''      v2: 38.0
"LA  35 mm" → v1: '35'    v2: 35.0
```

Missing values produced this way are indistinguishable from clinically absent measurements — which matters for any paper reporting completeness or missingness. v2 accepts `:`/`-`/`=`, optional whitespace, and an optional unit, while using a `(?<![A-Za-z])` guard so `LAA`/`RVSP`-style tokens do not false-positive (verified: they do not).

## A5 — Typing

All 47 columns are `str`; absent values are `""`. Excel therefore receives text cells and pandas an object dtype. v2 emits `float`/`int`/`None`, range-checks against the field dictionary, and **flags rather than drops** implausible values — a genuine outlier and a parse error look identical until a human decides.

## A6 — Name loss

The "Name fallback" block re-runs the identical regex that just failed, so it can never recover anything. With `Age / Gender` absent, `Name` is empty.

```
Report missing 'Age / Gender' → v1 Name: ''   v2 Name: recovered via loose anchor
```

## A7 — Bullet class

`^[\u2022\-\*\. ]+` covers `•`, `-`, `*`, `.` and space. It does not cover `·` (U+00B7), `▪`, `‣`, `–` (en dash), `○`, the `o` list marker, or numeric prefixes.

```
"1. Mild mitral regurgitation" → v1: '1. Mild mitral regurgitation'   v2: 'Mild mitral regurgitation'
```

This is the **only** behavioural divergence between v1 and v2 on clean input; the regression test asserts equivalence on all other columns. If impression text has been used for any string matching or coding, note that the previously extracted values carry enumeration prefixes.

## A8 / A9 / A10 / A11

- Impressions past the tenth are dropped; v2 records `_impression_overflow` and warns.
- v2 adds `_source_file`, `_source_pages`, `_record_index`, `_field_completeness`, `_warnings` per row, which is what makes the platform's Quality sheet possible and what a reviewer needs to audit an extraction.
- `doc.close()` is now guaranteed via `finally` — v1 leaks a handle per file, which is harmless in a script and not harmless in a worker processing thousands.
- An image-only PDF now raises `UnparseableDocument("no extractable text layer")` instead of returning zero rows that look like a valid empty result.

---

## Environment discrepancy

Your uploaded `requirements.txt` pins `streamlit==1.38.0, PyMuPDF==1.26.5, pandas==2.2.3, numpy==2.1.1`. My earlier notes from the manuscript work record a different pin set (`streamlit 1.28.0, pandas 2.0.0, openpyxl 3.1.0, PyMuPDF 1.23.0`). **These cannot both describe the environment that produced the published results.** Confirm which set was actually used, because the reproducibility statement and the Zenodo deposit should name that one. Separately, `import fitz` is deprecated upstream in favour of `import pymupdf`; v2 uses the current import so it does not break on a future release.

---

## What v2 does not change

Same rule-based method, same regex philosophy, same fields, same determinism. `to_dataframe(..., legacy_columns=True)` reproduces the exact 47-column v1 layout for regression comparison against previously published outputs, and `extract_echo_data(path)` remains available with the identical signature. The canonical dictionary splits `Age / Gender` into `age_years` + `sex`, which takes the canonical field count to **48** and aligns it with the 48-variable figure in the manuscript.

## Verification

```
$ python3 test_engine.py
PASS  A1 phantom row eliminated | v1=2 rows, v2=1 rows
PASS  A2 no silent record loss | v1 kept ['P1','P2'], v2 kept ['P1','P2','P3']
PASS  A3 reconciliation reported
PASS  A4 tolerant measurement parsing | v1 AO='', v2 AO=32.0, v2 LA=38.0
PASS  A5 numeric typing & age/sex split | ef=61.0 age=54 sex='M'
PASS  A7 marker stripped
PASS  A8 impression overflow counted
PASS  A9 provenance present
PASS  A11 empty text layer raises UnparseableDocument
PASS  EQ v2 legacy mode == v1 modulo marker stripping | differing columns: none
PASS  EQ marker stripping is the only divergence
PASS  STREAM binary stream input works
ALL CHECKS PASSED
```

One regression was introduced during hardening and caught by this suite before delivery: anchor-based segmentation initially pulled the `Echo Technologist` footer into `IMPRESSION3`. Fixed with explicit footer trimming plus a report-furniture filter, and the suite now covers it.

**Fixture caveat:** these reproductions use synthetic PDFs built to match the layout implied by v1's own regexes. Send 2–3 real (or de-identified) archive PDFs and I will convert them into the golden-file fixtures that gate every future build — at which point the field dictionary can be validated against real formatting rather than inferred formatting.
