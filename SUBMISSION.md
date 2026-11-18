# Submission - Build with CMC: API Hackathon (Round 2, "Plushie")

Copy-paste source for the DoraHacks submission. Every number, endpoint and command below matches what the repository actually contains.

**Status (2026-11-18 22:xx KST)**

| Step | State |
|---|---|
| Repository pushed | [완료] `main`, 5 commits, 21 files, demo video 471,947 bytes - https://github.com/nvimuno-dot/cmc-market-radar |
| Repository name | [완료] renamed from `cmc-market-rader` to `cmc-market-radar`; all links below use the fixed name |
| DoraHacks BUIDL created | ⬜ not yet - values in section 2 |
| X post published | ⬜ not yet - draft in section 4 |
| Submitted for review | ⬜ not yet - needs the X post URL |

Hackathon: submissions open 2026-11-18 09:00 KST, close **2026-12-10 09:00 KST** (2026-12-09 23:59 UTC). Judging 12/10-12/25, results 12/30. Required in every submission: public repo, working demo or screen recording, **X post with the DoraHacks BUIDL link, the demo video and `#BuildwithCMC` (post URL pasted into the form)**, endpoints named explicitly, visible evidence of a real API call, a short note on what the API made possible and where it got in the way, one track.

## 1. DoraHacks submission form - field by field

Open `https://dorahacks.io/hackathon/coinmarketcap-api-202611/build` → **Submit Build** → agree to the organizer disclaimer.

| Form field | Value |
|---|---|
| **Build** * | `Create new Build →` with the values in section 2 |
| **Track** * | `Markets and Trading Tools` |
| Organizer question: X/Twitter post URL * | the URL of the post in section 4 |
| Looking for teammates | `No` |
| Terms of Use / Participant Agreement | check |
| Button | `Submit for Review` |

Track reason: the tool's whole output is a market view a trader acts on (universe selection, liquidity screening, divergence flags), and it exists only because CMC covers assets and venues no single exchange API does. Track scoring: does it work 30, usefulness to a real trader 25, interesting use of the API 20, code quality and documentation 15, presentation 10.

## 2. Values for "Create a new Build"

| BUIDL field | Value |
|---|---|
| Name of your Build | `CMC Market Radar` |
| Brief description | The cross-section of the market, scored: which assets are really being bought, which moves are hollow, and what regime we are in - in one command, on 2 API credits. |
| Logo | `Letter` (the repo has no logo asset; a one-letter mark is honest) |
| Tags | `CMC API`, `Crypto`, `API`, `Trading`, `Market Data` |
| GitHub Repo | `https://github.com/nvimuno-dot/cmc-market-radar` |
| Video | `https://cdn.jsdelivr.net/gh/nvimuno-dot/cmc-market-radar@main/demo/cmc-market-radar-demo.mp4` (direct `.mp4`, 1280x720, 36 s - the form accepts YouTube, Vimeo, Loom or a direct file) |
| Website / X / LinkedIn | leave empty |
| Team Info | solo |
| Contact Info | organizer-only; leave empty unless asked |

### Description to paste into the BUIDL editor

```markdown
CMC Market Radar is a small market-intelligence layer for crypto desks and trading agents.

**The problem.** Most crypto "dashboards" show a price and a 24h change - exactly what a hundred free sites already show. A systematic trader needs the cross-section instead: which markets are liquid enough to trade today, which moves are volume-backed, and what regime the whole market is in. That is the job CoinMarketCap data is genuinely good at, because it covers assets and venues a single exchange's API does not.

**How it works.** One command scans the top-N liquid universe through the CMC Pro API, filters it to assets a desk can actually exit, and scores every asset on three explainable components: momentum (weighted 7d/24h/1h, missing windows skipped and renormalised), volume anomaly (24h volume change, squashed so one wash trade cannot own the ranking), and liquidity (turnover relative to the cohort median, so a micro cap and a megacap are compared on their own terms). Global metrics reduce to a regime label: risk-on / neutral / risk-off, crossed with btc-led / alt-led. It then flags the contradictions a desk cares about - price up on falling volume, a sell-off on rising volume, a thin float under a large cap.

**Key features.**
- One command, two API credits per scan, no database, no third-party dependencies.
- Markdown brief plus three sentences that can be pasted into a desk note.
- A read-only agent loop that emits a JSON decision object with per-asset evidence and never places an order, so it can run unattended and feed a separate execution layer.
- Retry/backoff with `Retry-After` handling and per-run credit accounting, so cost is visible per call.

**Tech stack.** Python 3.10+, standard library only. `client.py` (HTTP, retry, credits), `signals.py` (pure scoring functions), `agent.py` (scan → score → decide), `report.py` (table, Markdown, brief), `cli.py` (`scan`, `demo`). 12 unit tests on fixture data, no network needed.

**Endpoints used (CoinMarketCap Pro API).**
- `GET /v1/cryptocurrency/listings/latest` - the universe: price, market cap, volume, 1h/24h/7d change, 24h volume change (1 credit per 100 assets)
- `GET /v1/global-metrics/quotes/latest` - regime: total market cap change, BTC dominance (1 credit)
- `GET /v1/cryptocurrency/quotes/latest` - targeted watchlist refresh (1 credit per 100 assets)
- `GET /v1/cryptocurrency/trending/latest` - retail-attention cross-check (optional, 1 credit)
- `GET /v4/derivatives/market` - perp funding / open interest (paid tier; degrades to empty on Basic)
- `GET /v2/cryptocurrency/info` - tags for the narrative layer (optional, 1 credit per 100)

**Evidence of a real API call.** `data/sample_scan.md` and `data/sample_decision.json` in the repository are the unedited output of `PYTHONPATH=src python3 -m cmc_radar.cli scan --top 100 --watch BTC,ETH,SOL,HYPE` on 2026-11-18: 100 listings rows, 54 assets scored after filtering, BTC $63,992.67, total market cap $2.179T, BTC dominance 59.08%, 2 credits used, and the per-endpoint counter printed at the bottom of the brief.

**What the API made possible, and where it got in the way.**
- Possible: one call gives a comparable cross-section of the entire market - price, cap, volume and three change windows for 100 assets - which is what makes a cohort-relative liquidity score possible at all. No single-exchange API can rank a CEX token against a DEX-only asset.
- In the way: (1) `listings/latest` has no asset-type field, so 12 of the top 100 fiat-pegged rows have to be special-cased by tag or by guessing from the ticker, and they own every turnover-normalised ranking by construction; (2) `status.total_credits_left` came back null on Basic, so a client cannot budget itself from the response; (3) there is no `volume_change_7d` or `percent_change_30d` on the listing row, so multi-window momentum costs a second endpoint; (4) `listings/latest` does not allow `sort=volume_change_24h`, so "which of the top 500 just woke up" is five paginated calls instead of one; (5) the keyless tier is advertised but not documented endpoint by endpoint.

**Reproduce in 60 seconds.**
```
git clone https://github.com/nvimuno-dot/cmc-market-radar && cd cmc-market-radar
PYTHONPATH=src python3 -m cmc_radar.cli demo    # offline, no key, no network
python3 -m pytest -q                            # 12 passed
```

Scores are descriptive and read-only: no orders, no fills, no fees modelled. This is a market view, not trading advice.
```

## 3. Endpoints used (short version, for any field that asks)

| Endpoint | Purpose | Credits |
|---|---|---|
| `GET /v1/cryptocurrency/listings/latest` | universe: price, cap, volume, 1h/24h/7d change, volume change | 1 per 100 assets |
| `GET /v1/global-metrics/quotes/latest` | regime: total cap change, BTC dominance | 1 |
| `GET /v1/cryptocurrency/quotes/latest` | watchlist refresh | 1 per 100 assets |
| `GET /v1/cryptocurrency/trending/latest` | attention cross-check (optional) | 1 |
| `GET /v4/derivatives/market` | funding / open interest (paid tier, degrades to empty) | 1 |
| `GET /v2/cryptocurrency/info` | tags for the narrative layer (optional) | 1 per 100 |

## 4. X post (required by the hackathon)

The post must contain **the DoraHacks BUIDL link, the demo video and `#BuildwithCMC`**, and its URL goes into the organizer question. Post it after the BUIDL exists, so the BUIDL URL can be linked. Attach `demo/cmc-market-radar-demo.mp4` to the post itself (36 s, 1280x720) so the video plays in the timeline.

### English, 280-character version (weighted 258 - posts as is on a standard account)

```
Top 100 assets, one CoinMarketCap Pro API call: momentum, volume anomaly, cohort liquidity, and a regime label. 2 credits, stdlib only, read-only agent. #BuildwithCMC

Code: https://github.com/nvimuno-dot/cmc-market-radar
Demo: https://cdn.jsdelivr.net/gh/nvimuno-dot/cmc-market-radar@main/demo/cmc-market-radar-demo.mp4
BUIDL: <BUIDL URL>
```

### Korean, 280-character version (weighted 261)

```
CMC Pro API로 상위 100개 자산을 한 번에 훑어 모멘텀·거래량 이상·코호트 유동성과 국면 라벨을 뽑습니다. 스캔 2크레딧, 외부 라이브러리 0, 주문 없는 읽기 전용. #BuildwithCMC

코드: https://github.com/nvimuno-dot/cmc-market-radar
데모: https://cdn.jsdelivr.net/gh/nvimuno-dot/cmc-market-radar@main/demo/cmc-market-radar-demo.mp4
BUIDL: <BUIDL URL>
```

### Longer version (only if the account can post past 280 - weighted 414)

```
One command scans the top 100 assets on the CoinMarketCap Pro API and scores what is actually being bought: momentum, volume anomaly, and liquidity relative to the cohort, plus a risk-on / btc-led regime label. Two credits a scan, standard library only, read-only agent.

Built for the CMC API hackathon. #BuildwithCMC

Demo: https://cdn.jsdelivr.net/gh/nvimuno-dot/cmc-market-radar@main/demo/cmc-market-radar-demo.mp4
Code: https://github.com/nvimuno-dot/cmc-market-radar
DoraHacks: <BUIDL URL>
```

## 5. Order of operations

1. Rename the GitHub repository `cmc-market-rader` → `cmc-market-radar` (Settings → Repository name). GitHub redirects the old URL, and every link above assumes the fixed name.
2. Create the BUIDL with section 2, publish it, and copy its public URL.
3. Post on X with the BUIDL URL, the video attached, and `#BuildwithCMC`; copy the post URL.
4. Paste the post URL into the organizer question, select the `Markets and Trading Tools` track, check the agreements, `Submit for Review`.

## 6. What the judges can check in 60 seconds

```bash
git clone https://github.com/nvimuno-dot/cmc-market-radar && cd cmc-market-radar
PYTHONPATH=src python3 -m cmc_radar.cli demo     # no key, no network
python3 -m pytest -q                             # 12 passed
```
