"""Canonical citation record and format generators.

Every citation the platform emits -- workbook sheet, site section, /citation
endpoint -- derives from this single record. A correction here propagates
everywhere; there are no hand-maintained citation strings in the codebase.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class CitationRecord:
    family: str = "B Manjunath"
    given: str = "Suraj"
    year: int = 2026
    title: str = ("EchoMiner: source code for rule-based NLP extraction from "
                  "echocardiography PDF reports")
    publisher: str = "Zenodo"
    doi: str = "10.5281/zenodo.21281483"

    @property
    def url(self) -> str:
        return f"https://doi.org/{self.doi}"

    @property
    def initials(self) -> str:
        return "".join(part[0] for part in self.given.split() if part)


CANONICAL = CitationRecord()


def apa(rec: CitationRecord = CANONICAL) -> str:
    return (f"{rec.family}, {rec.initials}. ({rec.year}). {rec.title} "
            f"[Computer software]. {rec.publisher}. {rec.url}")


def vancouver(rec: CitationRecord = CANONICAL) -> str:
    return (f"{rec.family} {rec.initials}. {rec.title} [Computer software]. "
            f"{rec.publisher}; {rec.year}. Available from: {rec.url}")


def ieee(rec: CitationRecord = CANONICAL) -> str:
    return (f'{rec.initials}. {rec.family}, "{rec.title}," {rec.publisher}, {rec.year}. '
            f"[Online]. Available: {rec.url}")


def bibtex(rec: CitationRecord = CANONICAL) -> str:
    return "\n".join([
        f"@software{{echominer{rec.year},",
        f"  author    = {{{rec.family}, {rec.given}}},",
        f"  title     = {{{rec.title}}},",
        f"  year      = {{{rec.year}}},",
        f"  publisher = {{{rec.publisher}}},",
        f"  doi       = {{{rec.doi}}},",
        f"  url       = {{{rec.url}}}",
        "}",
    ])


def ris(rec: CitationRecord = CANONICAL) -> str:
    return "\n".join([
        "TY  - COMP",
        f"AU  - {rec.family}, {rec.given}",
        f"TI  - {rec.title}",
        f"PY  - {rec.year}",
        f"PB  - {rec.publisher}",
        f"DO  - {rec.doi}",
        f"UR  - {rec.url}",
        "ER  - ",
    ])


FORMATS = {"apa": apa, "vancouver": vancouver, "ieee": ieee, "bibtex": bibtex, "ris": ris}


def render(fmt: str, rec: CitationRecord = CANONICAL) -> str:
    if fmt not in FORMATS:
        raise KeyError(fmt)
    return FORMATS[fmt](rec)


def all_formats(rec: CitationRecord = CANONICAL) -> dict[str, str]:
    return {name: fn(rec) for name, fn in FORMATS.items()}
