import json
from pathlib import Path

import pytest

from cmc_radar.signals import Asset, lead_lag, liquidity, momentum, regime, score_universe, volume_anomaly


def make(symbol="AAA", price=10.0, cap=1e9, vol=5e7, h1=0.0, h24=0.0, d7=0.0, vol_chg=0.0, rank=10):
    return Asset(
        symbol=symbol,
        name=symbol,
        price= price,
        market_cap=cap,
        volume_24h=vol,
        pct_1h=h1,
        pct_24h=h24,
        pct_7d=d7,
        volume_change_24h=vol_chg,
        rank=rank,
    )


def test_from_listing_reads_quote_fields():
    row = {
        "symbol": "btc",
        "name": "Bitcoin",
        "cmc_rank": 1,
        "quote": {"USD": {"price": 64000.5, "market_cap": 1.2e12, "volume_24h": 3.1e10, "percent_change_1h": 0.4, "percent_change_24h": -1.2, "percent_change_7d": 3.0, "volume_change_24h": 12.5}},
    }
    asset = Asset.from_listing(row)
    assert asset.symbol == "BTC"
    assert asset.price == pytest.approx(64000.5)
    assert asset.pct_24h == pytest.approx(-1.2)
    assert asset.turnover == pytest.approx(3.1e10 / 1.2e12)


def test_from_listing_tolerates_missing_quote():
    asset = Asset.from_listing({"symbol": "x"})
    assert asset.price == 0.0
    assert asset.pct_24h is None
    assert asset.turnover == 0.0


def test_momentum_skips_missing_windows():
    # only 24h is known: the blend must use that alone, not dilute with zeros
    assert momentum(make(h24=4.0, h1=None, d7=None)) == pytest.approx(4.0)
    assert momentum(make(h24=-12.0, h1=None, d7=None)) == pytest.approx(-10.0)  # clamped


def test_momentum_weights_recent_window_less_than_daily():
    # same +2% on 7d only should count less than +2% on 24h
    assert momentum(make(d7=2.0)) < momentum(make(h24=2.0))


def test_volume_anomaly_clamped():
    assert volume_anomaly(make(vol_chg=400)) == pytest.approx(5.0)
    assert volume_anomaly(make(vol_chg=-400)) == pytest.approx(-5.0)
    assert volume_anomaly(make(vol_chg=None)) == 0.0


def test_liquidity_is_relative_to_cohort_median():
    hot = make(vol=2e8, cap=1e9)  # turnover 0.2
    assert liquidity(hot, cohort_median_turnover=0.1) > 0
    assert liquidity(hot, cohort_median_turnover=0.4) < 0


def test_high_turnover_is_flagged():
    scored = score_universe([make(symbol="HOT", vol=8e8, cap=1e9, h24=3.0)])
    assert "unusually high turnover" in scored[0].flags


def test_score_order_puts_momentum_with_volume_first():
    rows = [
        make("QUIET", h24=2.0, vol_chg=0.0),
        make("RUNNER", h24=9.0, vol_chg=180.0, vol=1.5e8),
        make("FADER", h24=-6.0, vol_chg=-40.0),
    ]
    ranked = score_universe(rows)
    assert ranked[0].asset.symbol == "RUNNER"
    assert ranked[-1].asset.symbol == "FADER"


def test_regime_labels():
    hot = regime({"btc_dominance": 61.0, "quote": {"USD": {"total_market_cap": 2e12, "total_market_cap_yesterday_percentage_change": 3.4}}})
    cold = regime({"btc_dominance": 48.0, "quote": {"USD": {"total_market_cap": 2e12, "total_market_cap_yesterday_percentage_change": -3.1}}})
    assert hot["label"] == "risk-on" and hot["concentration"] == "btc-led"
    assert cold["label"] == "risk-off" and cold["concentration"] == "alt-led"
    assert hot["notes"]


def test_lead_lag_only_flags_positive_gaps_with_volume():
    bench = make("BTC", h1=1.0)
    lagging = make("LAG", h1=0.1, vol_chg=40.0)
    ahead = make("AHEAD", h1=3.0, vol_chg=10.0)
    quiet = make("QUIET", h1=0.1, vol_chg=-5.0)
    out = dict(lead_lag([lagging, ahead, quiet], bench))
    assert "LAG" in out
    assert "AHEAD" not in out
    assert "QUIET" not in out


def test_lead_lag_empty_when_benchmark_flat():
    assert lead_lag([make("LAG", h1=-1.0)], make("BTC", h1=0.05)) == []


def test_demo_fixture_scores_cleanly():
    fixture = Path(__file__).parent / "fixtures" / "listings_demo.json"
    rows = json.loads(fixture.read_text(encoding="utf-8"))
    scored = score_universe([Asset.from_listing(r) for r in rows])
    assert len(scored) == len(rows)
    assert all(-20 <= s.score <= 20 for s in scored)
