"""Render a single, self-contained static HTML executive dashboard.

Used for two things:
1. An on-demand snapshot the user can open in any browser (no server required).
2. The daily scheduled task regenerates this each morning and attaches it to the chat message,
   as an alternative to hosting a live server.

No JS charting library is used on purpose -- everything is plain HTML/CSS so the file is robust,
opens instantly, and never depends on a CDN being reachable. Every figure still carries the same
Live/Delayed/Manual/Sample/Not-available labeling used in the Streamlit app -- this is a rendering
of the same DuckDB data, not a separate source of truth.
"""
from __future__ import annotations

import html
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import FREIGHT_SEGMENTS, WATCHLIST
from src.data_model import DataStatus
from src.db import get_connection
from src.pages_logic.cfo_monitor import SignalLevel, get_all_signals
from src.pages_logic.executive_brief import (
    get_cfo_implications_summary,
    get_rate_movements_table,
    get_segment_heatmap,
    get_top_news,
)
from src.pages_logic.fleet_fundamentals import get_all_segment_fundamentals
from src.pages_logic.freight_markets import get_all_segment_views
from src.pages_logic.listed_companies import get_company_views, get_latest_fx_rate
from src.pages_logic.macro_context import get_chokepoint_views, get_macro_indicator_views
from src.pages_logic.news_events import get_news

CSS = """
:root {
  --ink: #1b1f24; --muted: #57606a; --line: #d0d7de; --bg: #ffffff; --card: #f6f8fa;
  --live: #1a7f37; --delayed: #9a6700; --manual: #0969da; --sample: #6e7781; --unavailable: #cf222e;
}
* { box-sizing: border-box; }
body { font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; color: var(--ink);
       background: var(--bg); margin: 0; padding: 0 0 60px 0; }
.wrap { max-width: 980px; margin: 0 auto; padding: 32px 24px; }
h1 { font-size: 1.7rem; margin-bottom: 2px; }
h2 { font-size: 1.2rem; margin: 36px 0 12px 0; padding-bottom: 6px; border-bottom: 2px solid var(--ink); }
h3 { font-size: 0.95rem; margin: 0 0 6px 0; }
.meta { color: var(--muted); font-size: 0.85rem; margin-bottom: 24px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; }
.grid-companies { grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px; }
.metric-value { font-size: 1.35rem; font-weight: 700; margin: 4px 0; }
.metric-label { font-size: 0.8rem; color: var(--muted); }
.badge { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 0.7rem; font-weight: 700;
         text-transform: uppercase; letter-spacing: 0.02em; }
.badge-live { background: color-mix(in srgb, var(--live) 15%, white); color: var(--live); }
.badge-delayed { background: color-mix(in srgb, var(--delayed) 15%, white); color: var(--delayed); }
.badge-manual { background: color-mix(in srgb, var(--manual) 15%, white); color: var(--manual); }
.badge-sample { background: color-mix(in srgb, var(--sample) 15%, white); color: var(--sample); }
.badge-unavailable { background: color-mix(in srgb, var(--unavailable) 15%, white); color: var(--unavailable); }
.badge-ok { background: #d9f2e3; color: var(--live); }
.badge-warning { background: #fff1c2; color: var(--delayed); }
.badge-alert { background: #ffd8d3; color: var(--unavailable); }
.src { color: var(--muted); font-size: 0.72rem; margin-top: 6px; }
table { border-collapse: collapse; width: 100%; font-size: 0.88rem; }
th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--line); }
th { color: var(--muted); font-weight: 600; font-size: 0.78rem; text-transform: uppercase; }
.news-item { padding: 8px 0; border-bottom: 1px solid var(--line); }
.news-cat { font-size: 0.72rem; color: var(--manual); font-weight: 700; text-transform: uppercase; }
.heat-row { display: flex; align-items: center; gap: 10px; margin: 6px 0; font-size: 0.85rem; }
.heat-label { width: 130px; flex-shrink: 0; }
.heat-bar-track { flex: 1; background: #eee; border-radius: 4px; height: 16px; position: relative; }
.heat-bar { height: 16px; border-radius: 4px; }
.section-note { color: var(--muted); font-size: 0.85rem; margin-bottom: 10px; }
.footer { color: var(--muted); font-size: 0.78rem; margin-top: 48px; border-top: 1px solid var(--line); padding-top: 12px; }
.nav { margin: 4px 0 24px 0; font-size: 0.85rem; }
.nav a { color: var(--manual); text-decoration: none; margin-right: 18px; }
.nav a.active { color: var(--ink); font-weight: 700; text-decoration: underline; }
.fin-row { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline;
           gap: 4px 10px; padding: 5px 0; border-bottom: 1px solid var(--line); font-size: 0.85rem; }
.fin-label { color: var(--muted); flex-shrink: 0; }
.fin-value { font-weight: 600; text-align: right; word-break: break-word; }
"""

NAV_LINKS = [
    ("index.html", "Oversikt"),
    ("fleet_fundamentals.html", "Fleet Fundamentals"),
]


def page_shell(body: str, active_href: str) -> str:
    """Shared head/nav/footer wrapper so index.html and fleet_fundamentals.html look consistent."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    nav_parts = []
    for href, label in NAV_LINKS:
        cls_attr = ' class="active"' if href == active_href else ""
        nav_parts.append(f'<a href="{href}"{cls_attr}>{esc(label)}</a>')
    nav_html = "".join(nav_parts)
    return f"""<!DOCTYPE html>
<html lang="no">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shipping CFO Intelligence — Executive Dashboard</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <h1>Shipping CFO Intelligence</h1>
  <div class="meta">Generert {esc(now)} &middot; Statisk øyeblikksbilde — ikke interaktiv.
    Alle tall er merket Live / Delayed / Manuelt / Sample / Not available med kilde og observasjonsdato.</div>
  <div class="nav">{nav_html}</div>
  {body}
  <div class="footer">
    Shipping CFO Intelligence &middot; statisk dashboard generert av scripts/generate_static_dashboard.py.
    Ingen data er fabrikkert eller interpolert — se docs/source_register.md for fullstendig kildeoversikt.
  </div>
</div>
</body>
</html>"""

_BADGE_CLASS = {
    DataStatus.LIVE: "badge-live", DataStatus.DELAYED: "badge-delayed",
    DataStatus.MANUAL: "badge-manual", DataStatus.ESTIMATED: "badge-manual",
    DataStatus.SAMPLE: "badge-sample", DataStatus.UNAVAILABLE: "badge-unavailable",
}


def esc(x) -> str:
    return html.escape(str(x)) if x is not None else ""


def badge(status: DataStatus) -> str:
    cls = _BADGE_CLASS.get(status, "badge-unavailable")
    return f'<span class="badge {cls}">{esc(status.label)}</span>'


def src_line(meta) -> str:
    date_str = meta.observation_date.isoformat() if meta.observation_date else "n/a"
    return (f'<div class="src">{badge(meta.status)} {esc(meta.source)} &middot; '
            f'observed {esc(date_str)} &middot; {esc(meta.frequency)}</div>')


def fmt_num(v, decimals=1) -> str:
    if v is None:
        return "—"
    try:
        return f"{v:,.{decimals}f}"
    except (TypeError, ValueError):
        return "—"


def fmt_pct(v, decimals=1) -> str:
    if v is None:
        return "—"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.{decimals}f}%"


def render_top_news(conn) -> str:
    df = get_top_news(conn, n=5)
    if df.empty:
        return '<p class="section-note">Ingen nyheter lastet inn ennå. Kjør "Refresh live data" eller vent på neste automatiske oppdatering.</p>'
    items = []
    for _, row in df.iterrows():
        items.append(
            f'<div class="news-item"><span class="news-cat">{esc(row["category"])}</span><br>'
            f'<a href="{esc(row["url"])}">{esc(row["headline"])}</a><br>'
            f'<span class="src">{esc(row["source"])} &middot; {esc(row["published_date"])}</span></div>'
        )
    return "".join(items)


def render_heatmap(conn) -> str:
    df = get_segment_heatmap(conn)
    rows = []
    for _, r in df.iterrows():
        wow = r["wow_change_pct"]
        if wow is None or (isinstance(wow, float) and wow != wow):
            rows.append(f'<div class="heat-row"><div class="heat-label">{esc(r["segment"])}</div>'
                        f'<div class="section-note" style="margin:0;">Not available</div></div>')
            continue
        pct = max(min(wow, 20), -20)
        width = abs(pct) / 20 * 50
        color = "#1a7f37" if wow >= 0 else "#cf222e"
        side = f'margin-left:50%;' if wow >= 0 else f'margin-left:{50-width}%;'
        rows.append(
            f'<div class="heat-row"><div class="heat-label">{esc(r["segment"])}</div>'
            f'<div class="heat-bar-track"><div class="heat-bar" style="width:{width}%;{side}background:{color};"></div></div>'
            f'<div style="width:60px;text-align:right;">{fmt_pct(wow)}</div></div>'
        )
    return "".join(rows) if rows else '<p class="section-note">Not available.</p>'


def render_rate_table(conn) -> str:
    df = get_rate_movements_table(conn)
    rows = []
    for _, r in df.iterrows():
        rows.append(
            f"<tr><td>{esc(r['segment'])}</td><td>{fmt_num(r['latest_value'])} {esc(r['unit'] or '')}</td>"
            f"<td>{esc(r['observation_date'])}</td><td>{fmt_pct(r['wow_change_pct'])}</td>"
            f"<td>{fmt_pct(r['mom_change_pct'])}</td><td>{esc(r['status'])}</td><td>{esc(r['source'])}</td></tr>"
        )
    return ("<table><tr><th>Segment</th><th>Latest</th><th>Observed</th><th>WoW</th><th>MoM</th>"
            "<th>Status</th><th>Source</th></tr>" + "".join(rows) + "</table>")


def render_cfo_summary(conn) -> str:
    df = get_cfo_implications_summary(conn)
    rows = []
    for _, r in df.iterrows():
        rows.append(f"<tr><td>{esc(r['company'])}</td><td>{esc(r['alerts'])}</td>"
                     f"<td>{esc(r['warnings'])}</td><td>{esc(r['signals_unavailable'])}</td></tr>")
    return ("<table><tr><th>Company</th><th>Alerts</th><th>Warnings</th><th>Signals awaiting data</th></tr>"
            + "".join(rows) + "</table>")


def render_freight_section(conn) -> str:
    views = get_all_segment_views(conn)
    cards = []
    for seg, v in views.items():
        if v.latest_value is None:
            body = '<p class="section-note" style="margin:4px 0;">Not available</p>'
        else:
            body = (f'<div class="metric-value">{fmt_num(v.latest_value)} {esc(v.latest_unit or "")}</div>'
                    f'<div class="metric-label">WoW {fmt_pct(v.wow_change_pct)} &middot; MoM {fmt_pct(v.mom_change_pct)}</div>')
        cards.append(f'<div class="card"><h3>{esc(seg)}</h3>{body}{src_line(v.source_meta)}</div>')
    return f'<div class="grid">{"".join(cards)}</div>'


def render_fleet_section(conn) -> str:
    views = get_all_segment_fundamentals(conn)
    blocks = []
    for seg, v in views.items():
        cards = []
        for metric_key, mv in v.metrics.items():
            val = f"{fmt_num(mv.value)} {esc(mv.unit or '')}" if mv.value is not None else "Not available"
            cards.append(f'<div class="card"><h3>{esc(mv.label)}</h3><div class="metric-value" style="font-size:1.05rem;">{val}</div>{src_line(mv.source_meta)}</div>')
        blocks.append(f'<h3 style="margin-top:20px;">{esc(seg)}</h3><div class="grid">{"".join(cards)}</div>')
    return "".join(blocks)


def render_companies_section(conn) -> str:
    views = get_company_views(conn)
    fx = get_latest_fx_rate(conn, "USDNOK")
    fx_note = ""
    if fx:
        rate, meta = fx
        fx_note = f'<p class="section-note">Referanse-FX: 1 USD = {rate:.4f} NOK ({esc(meta.source)}, {esc(meta.observation_date)})</p>'
    else:
        fx_note = '<p class="section-note">FX-referanse ikke lastet inn ennå.</p>'

    cards = []
    for v in views:
        if not v.listed:
            price_block = f'<div class="metric-value" style="color:var(--unavailable);font-size:1rem;">Ikke lenger børsnotert</div><p class="src">{esc(v.status_note)}</p>'
        elif v.latest_price is not None:
            price_block = (f'<div class="metric-value">{fmt_num(v.latest_price)} {esc(v.currency or "")}</div>'
                            f'{src_line(v.price_source_meta)}')
        else:
            price_block = f'<p class="section-note" style="margin:4px 0;">Kurs ikke tilgjengelig</p>{src_line(v.price_source_meta)}'

        fin_rows = []
        for metric_key, data in v.financials.items():
            val = f"{fmt_num(data['value'])} {esc(data['unit'] or '')}" if data["value"] is not None else "Not available"
            fin_rows.append(
                f'<div class="fin-row"><span class="fin-label">{esc(data["label"])}</span>'
                f'<span class="fin-value">{val}</span>{badge(data["source_meta"].status)}</div>'
            )
        fin_block = "".join(fin_rows)

        cards.append(
            f'<div class="card"><h3>{esc(v.name)} ({esc(v.ticker)}) — {esc(v.segment)}</h3>'
            f'{price_block}<div style="margin-top:10px;">{fin_block}</div>'
            f'<p class="src">NAV: {esc(v.nav_status)}</p></div>'
        )
    # Cards are wider here than the default grid track (financial rows need room to breathe) --
    # a dedicated class avoids affecting the freight/fleet/macro grids elsewhere on the page.
    return fx_note + f'<div class="grid grid-companies">{"".join(cards)}</div>'


def render_macro_section(conn) -> str:
    choke_views = get_chokepoint_views(conn)
    macro_views = get_macro_indicator_views(conn)

    if choke_views:
        cards = []
        for label, v in choke_views.items():
            short_label = esc(label.replace(" — daily vessel transits", ""))
            cards.append(
                f'<div class="card"><h3>{short_label}</h3>'
                f'<div class="metric-value">{fmt_num(v.latest_value, 0)} {esc(v.latest_unit or "")}</div>'
                f'<div class="metric-label">WoW {fmt_pct(v.wow_change_pct)}</div>{src_line(v.source_meta)}</div>'
            )
        choke_html = f'<div class="grid">{"".join(cards)}</div>'
    else:
        choke_html = ('<p class="section-note">Not available yet. No chokepoint data ingested -- '
                      'run scripts/update_data.py or wait for the next scheduled GitHub Actions run.</p>')

    macro_cards = []
    for label, v in macro_views.items():
        val = f"{fmt_num(v.latest_value)} {esc(v.latest_unit or '')}" if v.latest_value is not None else "Not available"
        macro_cards.append(
            f'<div class="card"><h3>{esc(label)}</h3><div class="metric-value" style="font-size:1.05rem;">{val}</div>'
            f'{src_line(v.source_meta)}</div>'
        )
    macro_html = f'<div class="grid">{"".join(macro_cards)}</div>'

    return (f'<h3>Chokepoint traffic (IMF PortWatch)</h3>{choke_html}'
            f'<h3 style="margin-top:20px;">Macro benchmark rates</h3>{macro_html}')


def render_news_section(conn) -> str:
    df = get_news(conn, limit=25)
    if df.empty:
        return '<p class="section-note">Ingen nyheter lastet inn ennå.</p>'
    items = []
    for _, row in df.iterrows():
        items.append(
            f'<div class="news-item"><span class="news-cat">{esc(row["category"])}</span><br>'
            f'<a href="{esc(row["url"])}">{esc(row["headline"])}</a><br>'
            f'<span class="src">{esc(row["source"])} &middot; {esc(row["published_date"])}</span></div>'
        )
    return "".join(items)


def render_cfo_monitor_section(conn) -> str:
    all_signals = get_all_signals(conn)
    level_order = {SignalLevel.ALERT: 0, SignalLevel.WARNING: 1, SignalLevel.OK: 2, SignalLevel.UNAVAILABLE: 3}
    level_class = {SignalLevel.ALERT: "badge-alert", SignalLevel.WARNING: "badge-warning",
                   SignalLevel.OK: "badge-ok", SignalLevel.UNAVAILABLE: "badge-unavailable"}
    blocks = []
    for company, signals in all_signals.items():
        signals_sorted = sorted(signals, key=lambda s: level_order[s.level])
        cards = []
        for s in signals_sorted:
            cards.append(
                f'<div class="card"><span class="badge {level_class[s.level]}">{esc(s.level.value.upper())}</span>'
                f'<h3 style="margin-top:6px;">{esc(s.label)}</h3>'
                f'<p class="metric-label" style="margin:0;">{esc(s.detail)}</p></div>'
            )
        blocks.append(f'<h3 style="margin-top:20px;">{esc(company)}</h3><div class="grid">{"".join(cards)}</div>')
    return "".join(blocks)


def generate_index_html(conn) -> str:
    body = f"""  <h2>Executive Brief</h2>
  <h3>Fem ting som betyr noe</h3>
  {render_top_news(conn)}
  <h3 style="margin-top:20px;">Segment-heatmap (WoW)</h3>
  {render_heatmap(conn)}
  <h3 style="margin-top:20px;">Rate- og indeksbevegelser</h3>
  {render_rate_table(conn)}
  <h3 style="margin-top:20px;">CFO-implikasjoner (signal-oppsummering)</h3>
  {render_cfo_summary(conn)}

  <h2>Freight Markets</h2>
  {render_freight_section(conn)}

  <h2>Fleet Fundamentals</h2>
  <p class="section-note">Trading fleet, orderbook, expected deliveries, scrapping and fleet age per
    segment — moved to its own page since every metric here is still manual-CSV-pending (no free
    automated source exists; see docs/source_register.md).
    <a href="fleet_fundamentals.html">Åpne Fleet Fundamentals →</a></p>

  <h2>Listed Companies</h2>
  {render_companies_section(conn)}

  <h2>News and Events</h2>
  {render_news_section(conn)}

  <h2>Macro & Chokepoints</h2>
  {render_macro_section(conn)}

  <h2>CFO Monitor</h2>
  {render_cfo_monitor_section(conn)}
"""
    return page_shell(body, active_href="index.html")


def generate_fleet_html(conn) -> str:
    body = f"""  <h2>Fleet Fundamentals</h2>
  <p class="section-note">Trading fleet, orderbook, orderbook as % of fleet, expected deliveries,
    scrapping and average fleet age per segment. Every metric below requires a manual CSV upload
    (Clarksons/VesselsValue-sourced) or a future licensed adapter — none has a free, legal,
    machine-readable source today. See docs/source_register.md for the full gap list.
    <a href="index.html">&larr; Tilbake til oversikten</a></p>
  {render_fleet_section(conn)}
"""
    return page_shell(body, active_href="fleet_fundamentals.html")


def main() -> int:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dashboard.html")
    fleet_path = out_path.parent / "fleet_fundamentals.html"
    conn = get_connection()

    index_html = generate_index_html(conn)
    out_path.write_text(index_html, encoding="utf-8")
    print(f"Wrote {out_path} ({len(index_html):,} bytes)")

    fleet_html = generate_fleet_html(conn)
    fleet_path.write_text(fleet_html, encoding="utf-8")
    print(f"Wrote {fleet_path} ({len(fleet_html):,} bytes)")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
