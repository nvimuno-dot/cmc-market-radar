"""Rendering: one scan -> a Markdown brief and a terminal table."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Sequence

from .signals import Scored


def _money(value: float | None) -> str:
    if value is None:
        return "-"
    for unit, size in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(value) >= size:
            return f"${value / size:,.1f}{unit}"
    if abs(value) >= 1:
        return f"${value:,.2f}"
    if value == 0:
        return "$0"
    return f"${value:.6f}".rstrip("0").rstrip(".") if abs(value) < 0.01 else f"${value:.4f}"


def _pct(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:+.2f}%"


def table(rows: Sequence[Scored], limit: int = 15) -> str:
    header = f"{'#':>2}  {'SYM':<8}{'PRICE':>12}{'24H':>9}{'VOL CHG':>10}{'SCORE':>8}  FLAGS"
    lines = [header, "-" * 78]
    for i, row in enumerate(rows[:limit], 1):
        a = row.asset
        lines.append(
            f"{i:>2}  {a.symbol:<8}{_money(a.price):>12}{_pct(a.pct_24h):>9}"
            f"{_pct(a.volume_change_24h):>10}{row.score:>8.2f}  {'; '.join(row.flags)}"
        )
    return "\n".join(lines)


def markdown(rows: Sequence[Scored], regime: dict, stats: dict, universe_size: int, limit: int = 15) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out: list[str] = []
    out.append(f"# CMC Market Radar - {now}")
    out.append("")
    out.append(
        f"**Regime:** `{regime.get('label')}` / {regime.get('concentration')} "
        f"(BTC dominance {regime.get('btc_dominance') or 0:.1f}%, total cap {_money(regime.get('total_market_cap_usd'))})"
    )
    for note in regime.get("notes") or []:
        out.append(f"- {note}")
    out.append("")
    out.append(f"Scored {universe_size} assets. Top {min(limit, len(rows))} by composite score:")
    out.append("")
    out.append("| # | Symbol | Price | 24h | Vol chg | Momentum | Vol anomaly | Liquidity | Score | Flags |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    for i, row in enumerate(rows[:limit], 1):
        a = row.asset
        out.append(
            f"| {i} | **{a.symbol}** | {_money(a.price)} | {_pct(a.pct_24h)} | {_pct(a.volume_change_24h)} "
            f"| {row.momentum:+.2f} | {row.volume_anomaly:+.2f} | {row.liquidity:+.2f} | {row.score:+.2f} "
            f"| {'; '.join(row.flags) or '-'} |"
        )
    out.append("")
    if rows:
        worst = sorted(rows, key=lambda r: r.score)[:5]
        out.append("**Weakest 5** (avoid chasing / candidates for short-side watch):")
        out.append("")
        for row in worst:
            out.append(f"- {row.asset.symbol}: {row.score:+.2f} ({'; '.join(row.flags) or 'no flags'})")
        out.append("")
    out.append("## API usage this run")
    out.append("")
    out.append(f"- Calls: {stats.get('calls')} · credits used: {stats.get('credits_used')} · retries: {stats.get('retries')}")
    for endpoint, count in (stats.get("endpoints") or {}).items():
        out.append(f"- `{endpoint}` x{count}")
    out.append("")
    out.append("_Scores are descriptive, not trading advice. Each number is computed from the CMC quote fields shown above._")
    return "\n".join(out)


def brief(rows: Sequence[Scored], regime: dict, watchlist: Iterable[str] = ()) -> str:
    """Short prose an agent can post - three sentences, no fluff."""
    top = [r.asset.symbol for r in rows[:3]]
    watch = set(watchlist)
    focus = [r for r in rows if r.asset.symbol in watch][:3]
    sentences = [
        f"Regime is {regime.get('label')} with a {regime.get('concentration')} structure "
        f"(BTC dominance {regime.get('btc_dominance') or 0:.1f}%).",
    ]
    if top:
        sentences.append(f"Volume-weighted momentum is concentrated in {', '.join(top)}.")
    if focus:
        parts = [f"{r.asset.symbol} {r.score:+.2f}" for r in focus]
        sentences.append(f"On the desk watchlist: {'; '.join(parts)}.")
    flagged = [r.asset.symbol for r in rows if r.flags][:3]
    if flagged:
        sentences.append(f"Divergences worth a look: {', '.join(flagged)}.")
    return " ".join(sentences)
