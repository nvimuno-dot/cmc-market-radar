# CMC Market Radar

A small, auditable market-intelligence layer for crypto desks and trading agents, built on the **CoinMarketCap Pro API**. It answers one question every time it runs:

> *Given the whole liquid market right now, which assets are actually being bought, which moves are hollow, and what regime are we in?*

Zero third-party dependencies, no database, one command.

```bash
python -m cmc_radar.cli scan --top 100 --watch BTC,ETH,SOL,HYPE
```

```
 #  SYM            PRICE      24H   VOL CHG   SCORE  FLAGS
------------------------------------------------------------------------------
 1  PIEVERSE       $2.91  +49.74%   +97.81%    6.49
 2  WLFI         $0.0459   +0.03% +1130.95%    1.46
 3  JST          $0.1445   +1.44%   -43.98%   -0.10
 ...
13  SOL           $74.21   +0.73%    -6.48%   -1.10
```

---

## Why this exists

Most "crypto dashboards" show price and a 24h change, which is exactly what a hundred free sites already show. What a desk needs is the *cross-section*: a stable, explainable ranking of where volume-backed momentum is, what the market regime is, and which individual moves are inconsistent with their own volume.

A perp trader running a systematic strategy needs this for **universe selection**, not for entry timing: which markets are liquid enough to trade today, which ones are moving for real, and which are quietly dying. That is the gap this fills — and it is the job CMC data is genuinely good at, because it covers assets and venues that a single exchange's API does not.

## What it does

1. **Universe scan** - one `listings/latest` call returns the top N assets with price, market cap, volume, 1h/24h/7d changes and 24h volume change. Filtered to assets a desk can actually exit: market cap > 0, not fiat-pegged, at least $25M of 24h volume.
2. **Score** - each asset gets three explainable components and one composite score:
   - `momentum` - weighted blend of 7d/24h/1h change (recent window weighted highest, missing windows skipped rather than zeroed).
   - `volume anomaly` - 24h volume change, squashed; a quiet asset that suddenly trades 3x more shows up before price reacts.
   - `liquidity` - turnover (24h volume / market cap) relative to the cohort median, so a micro cap and a megacap are compared on their own terms.
   - composite = `0.55*momentum + 0.30*volume + 0.15*liquidity`, plus human-readable flags (`price-up / volume-down divergence`, `sell-off on rising volume`, `thin float for its cap`, ...).
3. **Regime** - global metrics (total market cap change, BTC dominance) are reduced to `risk-on / neutral / risk-off` x `btc-led / alt-led`, with one sentence of what it implies for position sizing.
4. **Agent output** - a bounded, read-only loop emits a JSON decision object: watchlist, per-asset evidence, and `suggested_action` strings. It never places orders. That is a deliberate safety property: this runs unattended, and the execution layer (or the human) stays the only thing that can move money.
5. **Brief** - three sentences and a Markdown table, ready to paste into a desk note or a chat.

## Architecture

```
 CMC Pro API                         cmc_radar
┌──────────────────────┐    ┌───────────────────────────────────────────┐
│ listings/latest      │───►│ client.py   retry/backoff, 429 Retry-After │
│ global-metrics/...   │    │             per-run credit accounting     │
│ quotes/latest        │    └───────────────┬───────────────────────────┘
│ (optional) trending  │                    ▼
└──────────────────────┘    ┌───────────────────────────────────────────┐
                            │ signals.py  Asset → momentum / volume /    │
                            │             liquidity / flags / regime     │
                            │             (pure functions, unit-tested)  │
                            └───────────────┬───────────────────────────┘
                                            ▼
                            ┌───────────────────────────────────────────┐
                            │ agent.py    scan → score → decide (read-only)│
                            │ report.py   table / Markdown / 3-sentence  │
                            │             brief                          │
                            │ cli.py      scan | demo                    │
                            └───────────────────────────────────────────┘
```

The signal layer is pure arithmetic on API fields with no I/O, so every rule in `signals.py` is covered by fixture-based unit tests (`pytest`, 12 tests, no network).

## Quickstart

```bash
git clone https://github.com/nvimuno-dot/cmc-market-radar.git
cd cmc-market-radar

# 1. offline demo - no key, no network
PYTHONPATH=src python3 -m cmc_radar.cli demo

# 2. live run
cp .env.example .env          # paste your CMC Pro API key
export CMC_API_KEY=...
PYTHONPATH=src python3 -m cmc_radar.cli scan --top 100 --watch BTC,ETH,SOL

# 3. tests
python3 -m pytest -q          # 12 passed

# 4. or install it
pip install -e . && cmc-radar scan --top 50
```

Python 3.10+. Nothing else.

### CLI

| Flag | Default | Meaning |
|---|---|---|
| `--top N` | 50 | universe size (CMC bills 1 credit per 100 rows) |
| `--watch BTC,ETH` | - | symbols always named in the prose brief |
| `--min-volume` | `25000000` | drop assets below this 24h USD volume |
| `--out FILE` | - | write the Markdown brief |
| `--json FILE` | - | write the agent decision object |
| `--quiet` | off | print only the Markdown |

## Cost

A scan is **2 credits** on the free Basic tier (15,000/month): one `listings/latest` for 100 rows, one `global-metrics`. Hourly scanning costs about 1,440 credits a month, which fits comfortably inside the free tier.

## CoinMarketCap endpoints used

| Endpoint | Used for | Credits |
|---|---|---|
| `GET /v1/cryptocurrency/listings/latest` | the universe: price, cap, volume, 1h/24h/7d change, volume change | 1 / 100 assets |
| `GET /v1/global-metrics/quotes/latest` | regime: total cap change, BTC dominance | 1 |
| `GET /v1/cryptocurrency/quotes/latest` | targeted refresh of a watchlist | 1 / 100 assets |
| `GET /v1/cryptocurrency/trending/latest` | retail-attention cross-check (optional) | 1 |
| `GET /v4/derivatives/market` | perp funding / open interest (paid tier; degrades to empty) | 1 |
| `GET /v2/cryptocurrency/info` | tags for the narrative layer (optional) | 1 / 100 |

See [`docs/API_NOTES.md`](docs/API_NOTES.md) for what we learned using them, including the API feedback submitted with this project.

## Demo

A 36-second screen recording rendered from real runs lives at [`demo/cmc-market-radar-demo.mp4`](demo/cmc-market-radar-demo.mp4) (offline demo, live scan, and the Markdown brief). `demo/render_demo.py` regenerates it from the captured stdout in `demo/`.

## Sample run (real API, committed)

[`data/sample_scan.md`](data/sample_scan.md) and [`data/sample_decision.json`](data/sample_decision.json) are the unedited output of a live scan on 2026-11-18 (100 assets, 2 credits). They are in the repo rather than screenshots so a reviewer can diff them against their own run.

## Limits, honestly

- Lead/lag from a single snapshot is a **cross-sectional proxy** (who is lagging the benchmark on the 1h window while volume rises), not a time-series estimate. Real lead/lag needs intraday bars; the interface is ready for it (`signals.lead_lag`), the data source is not in this build.
- The score is descriptive. No backtest, no fills, no fees modelled; do not read it as a trade list.
- 24h volume change is a percentage over a moving window, so a single large print can distort it. That is why it is squashed and weighted below momentum.
- Derivatives data needs a paid tier; on Basic the endpoint returns empty and the agent continues by design.

## Roadmap

1. Intraday bars (`/v1/cryptocurrency/ohlcv/historical`) for a real lead/lag estimator and a rolling z-score instead of a static squash.
2. Derivatives factors (funding, OI change) merged into the score once the tier allows it.
3. SQLite snapshot store + a diff view ("what changed since the last scan"), which is the actual desk workflow.
4. A tiny read-only HTTP endpoint so an agent can pull the decision object instead of shelling out.

## License

MIT - see [LICENSE](LICENSE).
