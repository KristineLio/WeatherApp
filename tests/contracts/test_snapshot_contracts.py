"""second contract-style test file focused on HourlySeries.snapshot_for_date() 
(both peak_temp and target-hour fallback), 
plus a “no crash on empty/missing date” guard."""

import pytest

from weather_app.domain.models import HourlySeries

pytestmark = pytest.mark.contract

def _series_sample() -> HourlySeries:
    # Two days, with multiple hours on day 1 so peak temp selection is meaningful
    return HourlySeries(
        time=[
            "2026-01-18T09:00",
            "2026-01-18T12:00",
            "2026-01-18T15:00",
            "2026-01-19T12:00",
        ],
        temp=[5.0, 10.0, 8.0, 7.0],
        code=[1, 2, 3, 45],
        feels_like=[4.0, 9.0, 7.0, 6.0],
        humidity=[70, 55, 60, 80],
        precip=[10, 20, 30, 40],
        wind=[2.0, 5.0, 4.0, 1.0],
    )


def test_snapshot_for_date_contract_peak_temp_returns_max_temp_hour():
    s = _series_sample()
    snap = s.snapshot_for_date("2026-01-18", strategy="peak_temp")

    assert snap is not None
    assert set(snap.keys()) >= {"time", "temp", "code"}  # at least these
    assert snap["time"].startswith("2026-01-18T")
    assert snap["temp"] == 10.0
    assert snap["time"] == "2026-01-18T12:00"


def test_snapshot_for_date_contract_target_hour_finds_exact_match_when_present():
    s = _series_sample()
    snap = s.snapshot_for_date("2026-01-18", strategy="target_hour", target_hour=15)

    assert snap is not None
    assert snap["time"] == "2026-01-18T15:00"
    assert snap["code"] == 3


def test_snapshot_for_date_contract_target_hour_fallbacks_to_first_hour_when_target_missing():
    s = HourlySeries(
        time=["2026-01-18T09:00", "2026-01-18T12:00"],  # no 15:00
        temp=[5.0, 10.0],
        code=[1, 2],
        feels_like=[4.0, 9.0],
        humidity=[70, 55],
        precip=[10, 20],
        wind=[2.0, 5.0],
    )

    snap = s.snapshot_for_date("2026-01-18", strategy="target_hour", target_hour=15)

    assert snap is not None
    assert snap["time"] == "2026-01-18T09:00"  # first hour fallback
    assert snap["temp"] == 5.0


def test_snapshot_for_date_contract_returns_none_if_date_not_found():
    s = _series_sample()
    assert s.snapshot_for_date("2099-01-01", strategy="peak_temp") is None
    assert s.snapshot_for_date("2099-01-01", strategy="target_hour", target_hour=12) is None


def test_snapshot_for_date_contract_never_crashes_on_empty_series():
    s = HourlySeries(
        time=[],
        temp=[],
        code=[],
        feels_like=[],
        humidity=[],
        precip=[],
        wind=[],
    )

    assert s.snapshot_for_date("2026-01-18", strategy="peak_temp") is None
    assert s.snapshot_for_date("2026-01-18", strategy="target_hour", target_hour=12) is None