"""Command line entry point.

    python -m cmc_radar.cli scan --top 50
    python -m cmc_radar.cli scan --top 100 --watch BTC,ETH,SOL --out radar.md --json out.json
    python -m cmc_radar.cli demo            # runs fully offline against fixtures

Exit codes: 0 ok, 2 usage error, 3 API error (message on stderr).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .agent import RadarAgent, render_all
from .client import CmcClient, CmcError
from .signals import Asset, regime, score_universe
from .report import markdown, table


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cmc-radar", description="Cross-sectional market radar built on the CoinMarketCap Pro API.")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="score the top-N universe once")
    scan.add_argument("--top", type=int, default=50, help="universe size (CMC returns 100 rows per credit)")
    scan.add_argument("--watch", default="", help="comma separated symbols always shown in the brief")
    scan.add_argument("--out", help="write the Markdown brief to this path")
    scan.add_argument("--json", dest="json_path", help="write the agent decision object to this path")
    scan.add_argument("--min-volume", type=float, default=25_000_000, help="drop assets below this 24h USD volume (default 25M): a desk needs a book it can exit")
    scan.add_argument("--quiet", action="store_true", help="print only the Markdown brief")

    demo = sub.add_parser("demo", help="offline demo on bundled fixtures (no API key, no network)")
    demo.add_argument("--json", dest="json_path", help="write the demo decision object to this path")
    return parser


def _demo() -> int:
    fixtures = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "listings_demo.json"
    rows = json.loads(fixtures.read_text(encoding="utf-8"))
    assets = [Asset.from_listing(row) for row in rows]
    scored = score_universe(assets)
    reg = regime(
        {
            "btc_dominance": 58.4,
            "quote": {"USD": {"total_market_cap": 2.31e12, "total_market_cap_yesterday_percentage_change": 1.7}},
        }
    )
    print(markdown(scored, reg, {"calls": 0, "credits_used": 0, "retries": 0, "endpoints": {}}, len(scored)))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "demo":
        return _demo()

    api_key = os.environ.get("CMC_API_KEY")
    if not api_key:
        print("CMC_API_KEY is not set. Copy .env.example to .env and paste your key, or run `demo`.", file=sys.stderr)
        return 2

    client = CmcClient(api_key=api_key)
    agent = RadarAgent(
        client,
        universe_size=args.top,
        watchlist=[w for w in args.watch.split(",") if w],
        min_volume_usd=args.min_volume,
    )
    try:
        result = agent.run(on_step=lambda m: print(f"[agent] {m}", file=sys.stderr) if not args.quiet else None)
    except CmcError as exc:
        print(f"CMC API error: {exc}", file=sys.stderr)
        return 3

    rendered = render_all(result)
    if args.quiet:
        print(rendered["markdown"])
    else:
        print(rendered["table"])
        print()
        print(result.regime)
        print()
        print(rendered["brief"])
        print()
        print("api:", json.dumps(result.api_stats, ensure_ascii=False))

    if args.out:
        Path(args.out).write_text(rendered["markdown"], encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    if args.json_path:
        Path(args.json_path).write_text(rendered["json"], encoding="utf-8")
        print(f"wrote {args.json_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
