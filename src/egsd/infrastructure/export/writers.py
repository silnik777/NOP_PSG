"""Engineering-result export to CSV and XLSX.

Every export carries an explicit result-class banner ([SCREENING] / [ENGINEERING]) to
address risk R-04 (screening results must not be mistaken for final engineering design).
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from openpyxl import Workbook


@dataclass(frozen=True)
class ExportRow:
    parameter: str
    value: object
    unit: str = ""


@dataclass(frozen=True)
class ExportDocument:
    title: str
    result_class: str  # "Engineering" | "Screening"
    rows: list[ExportRow]
    warnings: list[str] | None = None

    @property
    def banner(self) -> str:
        return f"[{self.result_class.upper()}]"


_HEADER = ("Parameter", "Value", "Unit")


def to_csv_bytes(doc: ExportDocument) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([f"{doc.banner} {doc.title}"])
    writer.writerow([])
    writer.writerow(_HEADER)
    for r in doc.rows:
        writer.writerow([r.parameter, r.value, r.unit])
    for w in doc.warnings or []:
        writer.writerow([])
        writer.writerow(["WARNING", w])
    return buffer.getvalue().encode("utf-8")


def to_xlsx_bytes(doc: ExportDocument) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Results"
    ws.append([f"{doc.banner} {doc.title}"])
    ws.append([])
    ws.append(list(_HEADER))
    for r in doc.rows:
        ws.append([r.parameter, r.value, r.unit])
    for w in doc.warnings or []:
        ws.append([])
        ws.append(["WARNING", w])
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
