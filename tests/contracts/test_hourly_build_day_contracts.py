"""It checks that every HourlyMode works end-to-end with HourlySeries.build_day(),
 and that the returned lists are consistent + pivot_index is sane.
 One test that quickly detects: mode meta mismatch, missing keys, 
 wrong lengths, pivot bugs — across future refactors.
 shape invariants + no-crash across all modes + pivot “sane”"""


import pytest

from weather_app.domain.models import HourlySeries
from weather_app.domain.modes import HourlyMode

pytestmark = pytest.mark.contract

def _series_sample() -> HourlySeries:
    # A small but representative dataset (same date, consecutive-ish hours)
    return HourlySeries(
        time=[
            "2026-01-18T11:00",
            "2026-01-18T12:00",
            "2026-01-18T13:00",
            "2026-01-18T14:00",
        ],
        temp=[8.0, 10.0, 11.0, 9.0],
        code=[1, 2, 3, 45],
        feels_like=[7.0, 9.0, 10.0, 8.0],
        humidity=[60, 55, 50, 70],
        precip=[10, 20, 30, 40],
        wind=[3.0, 5.0, 6.0, 2.0],
    )


def test_build_day_contract_for_all_modes_outputs_consistent_lengths_and_no_crash():
    s = _series_sample()

    for mode in HourlyMode:
        day = s.build_day(
            "2026-01-18",
            mode=mode,
            today_iso="2026-01-18",
            current_time_iso="2026-01-18T12:50",  # pivot should be sane (in-bounds) if present
        )

        # Required keys exist
        for key in ("labels", "hours_int", "values", "codes", "time_isos", "pivot_index"):
            assert key in day, f"Missing key '{key}' for mode={mode}"

        labels = day["labels"]
        hours = day["hours_int"]
        values = day["values"]
        codes = day["codes"]
        time_isos = day["time_isos"]
        pivot = day["pivot_index"]

        # All lists should have the same length and match the selected date
        n = len(time_isos)
        assert n == len(labels) == len(hours) == len(values) == len(codes)
        assert n > 0

        assert all(t.startswith("2026-01-18T") for t in time_isos)
        assert all(isinstance(x, str) and x for x in labels)
        assert all(isinstance(h, int) for h in hours)

        # Values can be None (for precip/wind/humidity etc. depending on mode),
        # but must be list-shaped and stable.
        assert isinstance(values, list)

        # Codes should be ints (or None if padded/missing)
        assert all((c is None) or isinstance(c, int) for c in codes)

        # pivot_index should be within bounds when present
        assert pivot is None or (0 <= pivot < n)


