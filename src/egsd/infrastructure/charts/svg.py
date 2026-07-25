"""Minimal dependency-free SVG line-chart generator (theme-neutral).

Used to render ~6-month price history with a moving-average overlay. Self-contained SVG so
it can be embedded, exported, or shown as an artifact without any charting library.
"""

from __future__ import annotations


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def line_chart(
    title: str,
    x_labels: list[str],
    series: list[tuple[str, list[float], str]],
    unit: str = "",
    width: int = 820,
    height: int = 360,
) -> str:
    """Render one or more y-series sharing the same x axis.

    series: list of (name, values, hex_color).
    """
    pad_l, pad_r, pad_t, pad_b = 64, 130, 40, 46
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    all_values = [v for _, vals, _ in series for v in vals]
    y_min = min(all_values)
    y_max = max(all_values)
    if y_max == y_min:
        y_max = y_min + 1.0
    # round the axis a little
    span = y_max - y_min
    y_min -= span * 0.08
    y_max += span * 0.08

    n = len(x_labels)

    def px(i: int) -> float:
        return pad_l + (plot_w * i / (n - 1) if n > 1 else 0)

    def py(v: float) -> float:
        return pad_t + plot_h * (1 - (v - y_min) / (y_max - y_min))

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'font-family="system-ui,Segoe UI,Roboto,sans-serif" font-size="12">'
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="#0d1117"/>')
    parts.append(
        f'<text x="{pad_l}" y="24" fill="#e6edf3" font-size="15" '
        f'font-weight="600">{_esc(title)}</text>'
    )

    # y gridlines + labels
    for k in range(5):
        v = y_min + (y_max - y_min) * k / 4
        y = py(v)
        parts.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l + plot_w}" y2="{y:.1f}" '
            f'stroke="#30363d" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{pad_l - 8}" y="{y + 4:.1f}" fill="#8b949e" '
            f'text-anchor="end">{v:.1f}</text>'
        )
    if unit:
        parts.append(
            f'<text x="{pad_l - 8}" y="{pad_t - 12}" fill="#8b949e" '
            f'text-anchor="end">{_esc(unit)}</text>'
        )

    # x labels (thinned)
    step = max(1, n // 6)
    for i in range(0, n, step):
        x = px(i)
        parts.append(
            f'<text x="{x:.1f}" y="{height - pad_b + 20}" fill="#8b949e" '
            f'text-anchor="middle">{_esc(x_labels[i])}</text>'
        )

    # series polylines + legend
    for idx, (name, values, color) in enumerate(series):
        pts = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(values))
        parts.append(
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.2"/>'
        )
        ly = pad_t + 6 + idx * 20
        parts.append(
            f'<rect x="{pad_l + plot_w + 16}" y="{ly - 9}" width="12" height="12" '
            f'rx="2" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{pad_l + plot_w + 34}" y="{ly + 1}" fill="#e6edf3">{_esc(name)}</text>'
        )
        # last-value marker
        parts.append(
            f'<circle cx="{px(len(values) - 1):.1f}" cy="{py(values[-1]):.1f}" r="3.2" '
            f'fill="{color}"/>'
        )

    parts.append("</svg>")
    return "".join(parts)
