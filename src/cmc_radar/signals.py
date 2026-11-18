"""Signal layer: turn raw CMC quotes into a small, explicit scoring model.

Everything here is pure arithmetic on numbers the API already returns, so the
whole layer is unit-testable from fixtures without a key or network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Iterable, Sequence


def _num(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


@dataclass
class Asset:
    """The subset of a CMC listing row the model actually reads."""

    symbol: str
    name: str
    price: float
    market_cap: float
    volume_24h: float
    pct_1h: float | None
    pct_24h: float | None
    pct_7d: float | None
    volume_change_24h: float | None
    rank: int | None = None
    tags: tuple[str, ...] = ()
    extra: dict = field(default_factory=dict)

    @property
    def is_stable_like(self) -> bool:
        """Fiat-pegged or wrapped-cash assets: huge turnover, no momentum signal.

        CMC tags most of them, but not all historic rows carry tags, so the
        symbol pattern is the second net. Excluding them keeps the ranking about
        price discovery instead of redemption flow.
        """
        lowered = {t.lower() for t in self.tags}
        if "stablecoin" in lowered or "fiat-stablecoin" in lowered:
            return True
        if self.symbol.endswith("USD") or self.symbol.startswith("USD"):
            return True
        return self.symbol in {"DAI", "TUSD", "USDE", "FDUSD", "PYUSD", "USDD", "GUSD", "LUSD", "BUSD", "USDS"}

    @property
    def turnover(self) -> float:
        """24h volume / market cap - how much of the float actually traded."""
        if self.market_cap <= 0:
            return 0.0
        return self.volume_24h / self.market_cap

    @classmethod
    def from_listing(cls, row: dict) -> "Asset":
        quote = ((row.get("quote") or {}).get("USD")) or {}
        return cls(
            symbol=str(row.get("symbol", "")).upper(),
            name=str(row.get("name", "")),
            price=_num(quote.get("price")) or 0.0,
            market_cap=_num(quote.get("market_cap")) or 0.0,
            volume_24h=_num(quote.get("volume_24h")) or 0.0,
            pct_1h=_num(quote.get("percent_change_1h")),
            pct_24h=_num(quote.get("percent_change_24h")),
            pct_7d=_num(quote.get("percent_change_7d")),
            volume_change_24h=_num(quote.get("volume_change_24h")),
            rank=row.get("cmc_rank"),
            tags=tuple(row.get("tags") or ()),
            extra=row,
        )


@dataclass
class Scored:
    asset: Asset
    momentum: float
    volume_anomaly: float
    liquidity: float
    score: float
    flags: list[str] = field(default_factory=list)


def momentum(asset: Asset) -> float:
    """Blend of 1h/24h/7d moves, re-weighted so momentum decays with the window.

    Returns a value in ~[-10, 10]: positive means the asset is being bought.
    Missing windows are skipped rather than treated as zero, so a freshly
    listed token with no 7d history is not silently penalised.
    """
    parts: list[tuple[float, float]] = []
    for value, weight in ((asset.pct_7d, 0.2), (asset.pct_24h, 0.5), (asset.pct_1h, 0.3)):
        if value is not None:
            parts.append((value, weight))
    if not parts:
        return 0.0
    total_weight = sum(w for _, w in parts)
    blended = sum(value * weight for value, weight in parts) / total_weight
    return max(-10.0, min(10.0, blended))


def volume_anomaly(asset: Asset) -> float:
    """Volume change vs. price change, squashed into [-5, 5].

    `volume_change_24h` is a percentage change of 24h volume, so a quiet token
    that suddenly trades 300% more shows up here even before price reacts.
    """
    change = asset.volume_change_24h
    if change is None:
        return 0.0
    return max(-5.0, min(5.0, change / 40.0))


def liquidity(asset: Asset, cohort_median_turnover: float | None = None) -> float:
    """Turnover relative to the cohort median, in [-3, 3].

    1.0 turnover on a top-100 asset is normal; the same ratio on a micro cap is
    a red flag. Comparing to the cohort median keeps it scale-free instead of
    hard-coding magic thresholds per market-cap bucket.
    """
    baseline = cohort_median_turnover if cohort_median_turnover and cohort_median_turnover > 0 else 0.05
    ratio = asset.turnover / baseline
    if ratio <= 0:
        return -3.0
    if ratio >= 3:
        return 3.0
    # ratio 1.0 -> 0.0, ratio 3.0 -> +3.0, ratio 1/3 -> -3.0
    if ratio >= 1:
        return min(3.0, (ratio - 1.0) * 1.5)
    return max(-3.0, -(1.0 / ratio - 1.0) * 1.5)


def flags_for(asset: Asset) -> list[str]:
    """Human-readable notes a desk would want next to the number."""
    flags: list[str] = []
    if (asset.pct_24h or 0) > 5 and (asset.volume_change_24h or 0) < -20:
        flags.append("price-up / volume-down divergence")
    if (asset.pct_24h or 0) < -5 and (asset.volume_change_24h or 0) > 50:
        flags.append("sell-off on rising volume")
    if asset.turnover > 0.5:
        flags.append("unusually high turnover")
    if asset.turnover < 0.005 and (asset.market_cap or 0) > 1e9:
        flags.append("thin float for its cap")
    if (asset.pct_7d or 0) > 25 and (asset.pct_1h or 0) < -2:
        flags.append("extended, rolling over")
    return flags


def score_universe(assets: Sequence[Asset]) -> list[Scored]:
    """Score every asset, then rank. Deterministic and side-effect free."""
    if not assets:
        return []
    turnovers = [a.turnover for a in assets if a.market_cap > 0]
    cohort = median(turnovers) if turnovers else None
    scored: list[Scored] = []
    for asset in assets:
        m = momentum(asset)
        v = volume_anomaly(asset)
        l = liquidity(asset, cohort)
        total = round(0.55 * m + 0.30 * v + 0.15 * l, 3)
        scored.append(Scored(asset=asset, momentum=round(m, 3), volume_anomaly=round(v, 3), liquidity=round(l, 3), score=total, flags=flags_for(asset)))
    return sorted(scored, key=lambda s: s.score, reverse=True)


def regime(global_data: dict) -> dict[str, object]:
    """Classify the market regime from global metrics.

    Deliberately coarse: three states a perp desk can act on, not a taxonomy.
    """
    usd = (global_data.get("quote") or {}).get("USD") or {}
    total_cap = _num(usd.get("total_market_cap"))
    cap_change = _num(usd.get("total_market_cap_yesterday_percentage_change"))
    btc_dominance = _num(global_data.get("btc_dominance"))
    stable_cap = _num(usd.get("total_market_cap"))  # placeholder if stablecoin data absent

    label = "neutral"
    if cap_change is not None:
        if cap_change > 2:
            label = "risk-on"
        elif cap_change < -2:
            label = "risk-off"
    concentration = "btc-led" if (btc_dominance or 0) >= 55 else "alt-led"
    return {
        "label": label,
        "total_market_cap_usd": total_cap,
        "market_cap_change_24h_pct": cap_change,
        "btc_dominance": btc_dominance,
        "concentration": concentration,
        "notes": _regime_notes(label, concentration, btc_dominance, stable_cap),
    }


def _regime_notes(label: str, concentration: str, btc_dominance: float | None, _stable: float | None) -> list[str]:
    notes: list[str] = []
    if label == "risk-off" and concentration == "btc-led":
        notes.append("Defensive tape: size down, prefer the deepest books, avoid chasing alt breakouts.")
    elif label == "risk-on" and concentration == "alt-led":
        notes.append("Broad risk appetite with rotation out of BTC: momentum names can run, but keep stops tight.")
    elif label == "risk-on":
        notes.append("Risk-on but BTC-heavy: alt moves need their own volume confirmation.")
    else:
        notes.append("Mixed tape: treat single-asset signals as noise until volume confirms.")
    if btc_dominance is not None:
        notes.append(f"BTC dominance {btc_dominance:.1f}%: {concentration} structure.")
    return notes


def lead_lag(candidates: Iterable[Asset], bench: Asset) -> list[tuple[str, float]]:
    """Cheap cross-sectional lead/lag proxy: 1h beta to the benchmark move.

    Not a time-series lead/lag estimate - that needs intraday bars. This is the
    ranking a screen can compute from one snapshot: who is already moving with
    the benchmark, and who is lagging behind it but trading more.
    """
    out: list[tuple[str, float]] = []
    bench_move = bench.pct_1h or 0.0
    if abs(bench_move) < 0.2:
        return out
    for asset in candidates:
        move = asset.pct_1h
        if move is None:
            continue
        gap = bench_move - move
        if gap * (1 if bench_move > 0 else -1) > 0.3 and (asset.volume_change_24h or 0) > 0:
            out.append((asset.symbol, round(gap, 3)))
    return sorted(out, key=lambda row: row[1], reverse=True)
