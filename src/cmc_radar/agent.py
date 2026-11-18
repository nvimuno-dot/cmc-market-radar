"""The "agent" part: a bounded, auditable loop over the signal layer.

The agent does not trade. It performs a fixed sequence of read-only tool calls,
records what it did, and emits one JSON decision object per run:

    {"regime": ..., "watchlist": [...], "actions": [{"type": "review", ...}]}

Every action is a *suggestion with its evidence attached*, which is what an
execution layer (or a human) needs to accept or reject it. Keeping the loop
read-only is a deliberate safety property: the same code can run unattended.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Sequence

from .client import CmcClient
from .report import brief, markdown, table
from .signals import Asset, Scored, lead_lag, regime, score_universe

BENCHMARK = "BTC"


@dataclass
class RunResult:
    started_at: str
    finished_at: str
    regime: dict
    scored: list[Scored]
    watchlist: list[str]
    decisions: list[dict]
    api_stats: dict
    log: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(
            {
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "regime": self.regime,
                "watchlist": self.effective_watchlist(),
                "decisions": self.decisions,
                "api": self.api_stats,
                "top": [
                    {
                        "symbol": s.asset.symbol,
                        "score": s.score,
                        "momentum": s.momentum,
                        "volume_anomaly": s.volume_anomaly,
                        "liquidity": s.liquidity,
                        "flags": s.flags,
                    }
                    for s in self.scored[:10]
                ],
            },
            indent=2,
            ensure_ascii=False,
        )

    def effective_watchlist(self) -> list[str]:
        return list(dict.fromkeys([w for w in self.watchlist if w]))


class RadarAgent:
    """Runs `scan -> score -> decide` and keeps an audit trail of each step."""

    def __init__(
        self,
        client: CmcClient,
        universe_size: int = 100,
        watchlist: Sequence[str] = (),
        min_volume_usd: float = 25_000_000,
    ) -> None:
        self.client = client
        self.universe_size = universe_size
        self.watchlist = [w.upper() for w in watchlist]
        self.min_volume_usd = min_volume_usd

    def run(self, on_step: Callable[[str], None] | None = None) -> RunResult:
        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        log: list[str] = []

        def step(message: str) -> None:
            log.append(message)
            if on_step:
                on_step(message)

        step(f"fetch listings (top {self.universe_size})")
        listings = self.client.listings(limit=self.universe_size)
        everything = [Asset.from_listing(row) for row in listings]
        assets = [
            a for a in everything
            if a.market_cap > 0 and not a.is_stable_like and a.volume_24h >= self.min_volume_usd
        ]
        dropped = len(everything) - len(assets)
        step(f"scored universe: {len(assets)} assets ({dropped} excluded: stablecoin, no cap, or under ${self.min_volume_usd/1e6:.0f}M 24h volume)")

        step("fetch global metrics")
        glob = self.client.global_metrics()
        reg = regime(glob)

        scored = score_universe(assets)
        bench = next((a for a in assets if a.symbol == BENCHMARK), None)
        laggards = lead_lag(assets, bench) if bench else []
        step(f"lead/lag screen vs {BENCHMARK}: {len(laggards)} candidates")

        decisions: list[dict] = []
        for row in scored[:5]:
            decisions.append(
                {
                    "type": "watch",
                    "symbol": row.asset.symbol,
                    "score": row.score,
                    "evidence": [
                        f"momentum {row.momentum:+.2f}",
                        f"volume anomaly {row.volume_anomaly:+.2f}",
                        f"liquidity {row.liquidity:+.2f}",
                        *row.flags,
                    ],
                    "suggested_action": "add to desk watchlist" if row.score > 1 else "monitor only",
                }
            )
        for symbol, gap in laggards[:3]:
            if any(d["symbol"] == symbol for d in decisions):
                continue
            decisions.append(
                {
                    "type": "lag",
                    "symbol": symbol,
                    "gap_vs_benchmark_pct": gap,
                    "evidence": [f"{BENCHMARK} moved faster by {gap:+.2f} pp on the 1h window with rising volume"],
                    "suggested_action": "check for idiosyncratic news before treating as catch-up",
                }
            )

        result = RunResult(
            started_at=started,
            finished_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            regime=reg,
            scored=scored,
            watchlist=self.watchlist,
            decisions=decisions,
            api_stats=self.client.stats.as_dict(),
            log=log,
        )
        return result


def render_all(result: RunResult) -> dict[str, str]:
    """Convenience for the CLI and for tests: every representation at once."""
    return {
        "table": table(result.scored),
        "markdown": markdown(result.scored, result.regime, result.api_stats, len(result.scored)),
        "brief": brief(result.scored, result.regime, result.watchlist),
        "json": result.to_json(),
    }
