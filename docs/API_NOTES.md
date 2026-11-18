# API notes - what we actually observed

Everything below was observed while building this project against the live Pro API on **2026-11-18** (Basic tier, one key). Numbers are from real calls, not from docs.

## Credits and limits

- One `GET /v1/cryptocurrency/listings/latest?limit=100` reports `status.credit_count = 1`. A full `scan` (listings + global metrics) costs **2 credits**.
- `status.credit_count` is populated on success, but `status.total_credits_left` came back **`null`** on the Basic tier for this key. The monthly quota is therefore visible in the dashboard, not in the response - a client cannot self-throttle from the payload alone. `client.CallStats` records the field when present and otherwise keeps its own per-run tally.
- Error responses keep the same envelope and put the machine-readable reason in `status.error_code` / `status.error_message`; `client.CmcError` surfaces both, so a caller can branch on the code rather than parse a string.
- HTTP 429 carries `Retry-After`; `client._get` honours it when it is an integer number of seconds and otherwise falls back to exponential backoff (1s, 2s, 4s). No 429 was hit during development, so this path is covered by code review rather than by a live trace.

## Fields we had to work around

- **Stablecoins pollute any turnover-based ranking.** In the top 100 there were 12 fiat-pegged rows (USDT, USDC, USDG, DAI, TUSD, RLUSD, USD1, ...). They are the highest-turnover assets in the dataset by construction - a $1 token that changes hands all day has turnover near 1.0 - so a naive "volume / market cap" screen ranks them above every real asset. CMC tags most of them (`stablecoin`), but not uniformly across all rows, which is why `Asset.is_stable_like` uses tags first and a symbol-pattern net second.
- **24h volume change is a moving-window percentage**, so a single large print moves it by hundreds of percent (`WLFI +1130.95%` in our sample). It is useful as an early signal but must be squashed (`volume_anomaly` clamps at ±5) and weighted below momentum, otherwise one wash trade owns the ranking.
- **Missing windows are common for new listings** (`percent_change_7d: null`). Treating null as 0 silently penalises fresh assets, so `momentum()` drops unknown windows and renormalises the weights instead.
- **`/v4/derivatives/market` needs a paid tier.** On Basic it fails; `CmcClient.derivatives()` catches `CmcError` and returns `{}` so the agent degrades instead of crashing. This is why funding/OI is a roadmap item and not a factor today.

## Feedback for the CMC API team

Concrete asks, in order of how much they would have changed this build:

1. **Add an asset-type field to `listings/latest`** (e.g. `asset_type: coin | token | stablecoin | wrapped | lst`). Twelve of the top 100 rows are fiat-pegged and every turnover- or volume-normalised screen has to special-case them by tag or by guessing from the symbol. A single boolean would remove a whole class of silent ranking bugs.
2. **Return `total_credits_left` (and the reset timestamp) reliably on every tier.** Right now a client cannot budget its own calls; it has to keep a local tally and hope the dashboard agrees.
3. **Add `volume_change_7d` and `percent_change_30d` to the listing row.** Multi-window momentum is the single most requested transform in this class of tool, and adding them costs no extra call - today it costs a second endpoint and 100 more credits to approximate.
4. **Allow `sort=volume_change_24h` on `listings/latest`.** "Which of the top 500 assets just woke up" is one query on the data but impossible to ask; with sorting it is one cheap call instead of five paginated ones.
5. **Document the keyless endpoints next to the keyed ones** on the API site. `coinmarketcap.com/api` now advertises a keyless tier; a short note on which endpoints it covers (and which limits apply) would save developers an afternoon of probing.

## Reproduction

```bash
export CMC_API_KEY=...
PYTHONPATH=src python3 -m cmc_radar.cli scan --top 100 --watch BTC,ETH,SOL,HYPE \
  --out data/sample_scan.md --json data/sample_decision.json
```

`data/sample_scan.md` and `data/sample_decision.json` in this repo are exactly that command's output on 2026-11-18, unedited. Total cost of the committed sample: 2 credits.
