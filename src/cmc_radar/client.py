"""Minimal, dependency-free CoinMarketCap Pro API client.

Design notes
------------
* Standard library only: a reviewer can run this with `python -m cmc_radar.cli`
  on a clean machine without installing anything.
* Every call goes through `_get`, which centralises retry/backoff, per-call
  credit accounting (CMC reports it in `status.credit_count`) and the one thing
  that actually bites you in production: HTTP 429 with `Retry-After`.
* A key is optional for the endpoints that CMC serves keylessly; when a key is
  present it is sent in `X-CMC_PRO_API_KEY`.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Iterable

BASE_URL = "https://pro-api.coinmarketcap.com"


class CmcError(RuntimeError):
    """Raised when the API answers with an error payload or an unrecoverable status."""

    def __init__(self, message: str, status: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.status = status or {}


@dataclass
class CallStats:
    calls: int = 0
    credits_used: int = 0
    credits_left: int | None = None
    retries: int = 0
    endpoints: dict[str, int] = field(default_factory=dict)

    def record(self, endpoint: str, status: dict[str, Any]) -> None:
        self.calls += 1
        self.endpoints[endpoint] = self.endpoints.get(endpoint, 0) + 1
        credit_count = status.get("credit_count")
        if isinstance(credit_count, int):
            self.credits_used += credit_count
        left = status.get("total_credits_left") or status.get("credits_left")
        if isinstance(left, int):
            self.credits_left = left

    def as_dict(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "credits_used": self.credits_used,
            "credits_left": self.credits_left,
            "retries": self.retries,
            "endpoints": dict(sorted(self.endpoints.items())),
        }


class CmcClient:
    """Thin wrapper over the few CMC endpoints this project needs."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = BASE_URL,
        timeout: float = 20.0,
        max_retries: int = 3,
        user_agent: str = "cmc-market-radar/0.1",
    ) -> None:
        self.api_key = api_key or os.environ.get("CMC_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent
        self.stats = CallStats()

    # -- transport ---------------------------------------------------------
    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})
        url = f"{self.base_url}{path}" + (f"?{query}" if query else "")
        headers = {"Accept": "application/json", "User-Agent": self.user_agent}
        if self.api_key:
            headers["X-CMC_PRO_API_KEY"] = self.api_key

        delay = 1.0
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            request = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                status = payload.get("status") or {}
                if status.get("error_code"):
                    raise CmcError(status.get("error_message", "unknown API error"), status)
                self.stats.record(path, status)
                return payload
            except urllib.error.HTTPError as exc:  # 4xx/5xx
                body = exc.read().decode("utf-8", "replace")
                status: dict[str, Any] = {}
                try:
                    status = json.loads(body).get("status") or {}
                except json.JSONDecodeError:
                    pass
                # 429 / 5xx are worth another try; other 4xx are caller errors.
                if exc.code == 429 or 500 <= exc.code < 600:
                    last_error = CmcError(f"HTTP {exc.code}: {body[:200]}", status)
                    retry_after = exc.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after and retry_after.isdigit() else delay
                    time.sleep(min(wait, 30.0))
                    delay *= 2
                    self.stats.retries += 1
                    continue
                raise CmcError(f"HTTP {exc.code}: {body[:300]}", status) from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
                time.sleep(delay)
                delay *= 2
                self.stats.retries += 1
        raise CmcError(f"request failed after {self.max_retries + 1} attempts: {last_error}")

    # -- endpoints ---------------------------------------------------------
    def quotes(self, symbols: Iterable[str] | None = None, ids: Iterable[int] | None = None) -> dict[str, dict]:
        """`/v1/cryptocurrency/quotes/latest` - price + market stats for known assets."""
        params = {
            "symbol": ",".join(symbols).upper() if symbols else None,
            "id": ",".join(str(i) for i in ids) if ids else None,
            "convert": "USD",
            "skip_invalid": "true",
        }
        return self._get("/v1/cryptocurrency/quotes/latest", params).get("data") or {}

    def listings(self, limit: int = 100, sort: str = "market_cap") -> list[dict]:
        """`/v1/cryptocurrency/listings/latest` - the universe scan (1 credit / 100 assets)."""
        data = self._get(
            "/v1/cryptocurrency/listings/latest",
            {"start": 1, "limit": limit, "convert": "USD", "sort": sort, "sort_dir": "desc"},
        ).get("data")
        return data or []

    def global_metrics(self) -> dict:
        """`/v1/global-metrics/quotes/latest` - regime inputs (dominance, total mcap)."""
        return (self._get("/v1/global-metrics/quotes/latest", {"convert": "USD"}).get("data")) or {}

    def trending(self, limit: int = 10) -> list[dict]:
        """`/v1/cryptocurrency/trending/latest` - retail attention proxy."""
        data = self._get("/v1/cryptocurrency/trending/latest", {"limit": limit, "convert": "USD"}).get("data")
        return data or []

    def metadata(self, symbols: Iterable[str]) -> dict[str, dict]:
        """`/v2/cryptocurrency/info` - tags/category data for the narrative layer."""
        params = {"symbol": ",".join(s.upper() for s in symbols), "skip_invalid": "true"}
        return self._get("/v2/cryptocurrency/info", params).get("data") or {}

    def derivatives(self, symbols: Iterable[str]) -> dict[str, list[dict]]:
        """`/v4/derivatives/market` - perp funding / open interest.

        This endpoint needs a paid tier; callers must tolerate an empty result.
        """
        try:
            data = self._get(
                "/v4/derivatives/market",
                {"symbol": ",".join(s.upper() for s in symbols), "sort": "open_interest", "sort_dir": "desc"},
            ).get("data")
            return data or {}
        except CmcError:
            return {}
