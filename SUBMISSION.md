# Submission draft - Build with CMC: API Hackathon (Plushie)

Copy-paste source for the DoraHacks submission form. Everything here matches what the repository actually contains.

## Project name

CMC Market Radar

## Tagline (one line)

The cross-section of the market, scored: which assets are really being bought, which moves are hollow, and what regime we are in - in one command, on 2 API credits.

## Track

**Markets and Trading Tools**

Reason: the tool's whole output is a market view a trader acts on (universe selection, liquidity screening, divergence flags), and it exists only because CMC covers assets and venues no single exchange API does.

## Links

- Repository: `https://github.com/nvimuno-dot/cmc-market-radar`
- Demo video: `demo/cmc-market-radar-demo.mp4` in the repo (36s, recorded from real runs)
- Sample output: `data/sample_scan.md`, `data/sample_decision.json` (live run, 2026-11-18, 2 credits)

## What it is (150 words)

CMC Market Radar is a small market-intelligence layer for crypto desks and trading agents. One command scans the top-N liquid universe through the CoinMarketCap Pro API, then scores every asset on three explainable components - momentum (weighted 7d/24h/1h), volume anomaly (24h volume change), and liquidity (turnover relative to the cohort median) - and reduces the global metrics into a regime label (`risk-on/neutral/risk-off` x `btc-led/alt-led`). It flags the contradictions a desk cares about: price up on falling volume, a sell-off on rising volume, a thin float under a large cap. The agent loop is read-only: it emits a JSON decision object with evidence per suggestion and never places an order, so it can run unattended and feed a separate execution layer. Output is a Markdown brief plus three sentences you can paste into a desk note. Zero third-party dependencies, 12 unit tests, 2 API credits per scan.

## CoinMarketCap endpoints used

| Endpoint | Purpose | Credits |
|---|---|---|
| `GET /v1/cryptocurrency/listings/latest` | universe: price, cap, volume, 1h/24h/7d change, volume change | 1 per 100 assets |
| `GET /v1/global-metrics/quotes/latest` | regime: total cap change, BTC dominance | 1 |
| `GET /v1/cryptocurrency/quotes/latest` | watchlist refresh | 1 per 100 assets |
| `GET /v1/cryptocurrency/trending/latest` | attention cross-check (optional) | 1 |
| `GET /v4/derivatives/market` | funding / open interest (paid tier, degrades to empty) | 1 |
| `GET /v2/cryptocurrency/info` | tags for the narrative layer (optional) | 1 per 100 |

## Proof of real API usage

`data/sample_scan.md` and `data/sample_decision.json` are the unedited output of:

```bash
PYTHONPATH=src python3 -m cmc_radar.cli scan --top 100 --watch BTC,ETH,SOL,HYPE
```

Run on 2026-11-18 22:07 KST: 100 listings rows, 54 scored after filtering, BTC $63,992.67, total market cap $2.179T, BTC dominance 59.08%, credits used 2. The Brief tab in `sample_scan.md` prints the endpoint counters for the run.

## API feedback (required field)

1. **Add an asset-type field to `listings/latest`** (`coin | token | stablecoin | wrapped | lst`). 12 of the top 100 rows are fiat-pegged and they own every turnover-normalised ranking by construction; today every client special-cases them by tag or by guessing from the ticker.
2. **Return `total_credits_left` reliably.** `credit_count` is populated but `total_credits_left` came back `null` on Basic, so a client cannot budget itself from the response.
3. **Add `volume_change_7d` and `percent_change_30d` to the listing row.** Multi-window momentum is the most useful transform in this category and it currently costs an extra endpoint.
4. **Allow `sort=volume_change_24h` on `listings/latest`** so "which of the top 500 just woke up" is one call instead of five paginated ones.
5. **Document the keyless tier** next to the keyed endpoints - which endpoints it covers and what the limits are.

Full detail: `docs/API_NOTES.md`.

## What the judges can check in 60 seconds

```bash
git clone https://github.com/nvimuno-dot/cmc-market-radar && cd cmc-market-radar
PYTHONPATH=src python3 -m cmc_radar.cli demo     # no key, no network
python3 -m pytest -q                             # 12 passed
```

## Optional: X post for submission

> Built CMC Market Radar for #BuildwithCMC - one command scans the top-100 universe on the CoinMarketCap Pro API and ranks what's actually being bought: momentum + volume anomaly + cohort-relative liquidity, plus a regime label, on 2 credits. Read-only agent, zero dependencies.
> github.com/nvimuno-dot/cmc-market-radar

(Requires the user's decision - do not post without it.)
