"""Technical report generation (OPZ §33, MVP #23).

Renders a self-contained HTML technical report for a set of result blocks. Every report
carries provenance (generation timestamp, engine/model versions, config checksum) and shows
each block's quality classification and warnings explicitly, so a screening result can never
be read as a reference-grade one. No external assets — the HTML is portable and exportable.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from datetime import UTC, datetime

from ..domain.project.hashing import result_hash

REPORT_ENGINE_VERSION = "1.0.0"

_QUALITY_COLORS = {
    "reference": "#2ea043",
    "referencyjny": "#2ea043",
    "engineering": "#1f6feb",
    "inżynierski": "#1f6feb",
    "screening": "#bb8009",
    "screeningowy": "#bb8009",
}


@dataclass(frozen=True)
class ReportBlock:
    title: str
    result_class: str  # reference | engineering | screening (§B.5)
    inputs: dict
    outputs: dict
    warnings: list[str] = field(default_factory=list)
    model_versions: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TechnicalReport:
    title: str
    project: str
    variant: str
    scenario: str
    author: str
    blocks: list[ReportBlock]


def _esc(v) -> str:
    return html.escape(str(v))


def _kv_table(data: dict) -> str:
    if not data:
        return '<p class="muted">—</p>'
    rows = "".join(
        f"<tr><th>{_esc(k)}</th><td>{_esc(_fmt(v))}</td></tr>" for k, v in data.items()
    )
    return f"<table class='kv'>{rows}</table>"


def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:.6g}"
    if isinstance(v, dict):
        return ", ".join(f"{k}={_fmt(val)}" for k, val in v.items())
    if isinstance(v, list):
        return ", ".join(_fmt(x) for x in v)
    return str(v)


def build_report(report: TechnicalReport) -> tuple[str, str]:
    """Return (html, config_checksum). The checksum fingerprints all block inputs+versions."""
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    checksum = result_hash(
        {
            "title": report.title, "project": report.project, "variant": report.variant,
            "scenario": report.scenario,
            "blocks": [
                {"title": b.title, "inputs": b.inputs, "class": b.result_class}
                for b in report.blocks
            ],
        },
        {"report": REPORT_ENGINE_VERSION,
         **{k: v for b in report.blocks for k, v in b.model_versions.items()}},
    )

    block_html: list[str] = []
    for b in report.blocks:
        color = _QUALITY_COLORS.get(b.result_class.lower(), "#8b949e")
        warn = ""
        if b.warnings:
            items = "".join(f"<li>{_esc(w)}</li>" for w in b.warnings)
            warn = f"<div class='warn'><strong>Ostrzeżenia:</strong><ul>{items}</ul></div>"
        versions = (
            f"<p class='muted'>Wersje modeli: {_esc(_fmt(b.model_versions))}</p>"
            if b.model_versions else ""
        )
        block_html.append(
            f"""
            <section class="block">
              <h2>{_esc(b.title)}
                <span class="badge" style="background:{color}">{_esc(b.result_class)}</span>
              </h2>
              <h3>Dane wejściowe</h3>{_kv_table(b.inputs)}
              <h3>Wyniki</h3>{_kv_table(b.outputs)}
              {warn}{versions}
            </section>"""
        )

    meta = _kv_table({
        "Projekt": report.project, "Wariant": report.variant, "Scenariusz": report.scenario,
        "Autor": report.author, "Wygenerowano (UTC)": generated_at,
        "Suma kontrolna": checksum, "Wersja generatora raportu": REPORT_ENGINE_VERSION,
    })

    doc = f"""<!doctype html>
<html lang="pl"><head><meta charset="utf-8">
<title>{_esc(report.title)}</title>
<style>
 body{{font-family:system-ui,Segoe UI,Roboto,sans-serif;margin:2rem auto;max-width:900px;
      color:#0d1117;line-height:1.5;padding:0 1rem}}
 h1{{border-bottom:3px solid #1f6feb;padding-bottom:.3rem}}
 h2{{margin-top:2rem;border-bottom:1px solid #d0d7de;padding-bottom:.2rem}}
 .badge{{color:#fff;font-size:.7rem;padding:.15rem .5rem;border-radius:1rem;
         vertical-align:middle;margin-left:.5rem}}
 table.kv{{border-collapse:collapse;width:100%;margin:.4rem 0}}
 table.kv th{{text-align:left;width:38%;background:#f6f8fa;padding:.3rem .5rem;
              border:1px solid #d0d7de;font-weight:600;vertical-align:top}}
 table.kv td{{padding:.3rem .5rem;border:1px solid #d0d7de;vertical-align:top}}
 .warn{{background:#fff8c5;border:1px solid #d4a72c;border-radius:6px;padding:.5rem .8rem;
        margin:.6rem 0}}
 .muted{{color:#57606a;font-size:.85rem}}
 footer{{margin-top:3rem;color:#57606a;font-size:.8rem;border-top:1px solid #d0d7de;
         padding-top:.6rem}}
</style></head><body>
<h1>{_esc(report.title)}</h1>
<section class="block"><h2>Metryka raportu</h2>{meta}</section>
{''.join(block_html)}
<footer>Raport techniczny wygenerowany przez e-GSD. Klasa wyniku (referencyjny/inżynierski/
screeningowy) oznaczona przy każdym bloku. Wynik screeningowy nie może być prezentowany jako
projektowy (OPZ §7).</footer>
</body></html>"""
    return doc, checksum
