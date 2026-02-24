from weather_app.domain.models import HourlySeries
from weather_app.domain.modes import HourlyMode


def _series_for_two_days() -> HourlySeries:
    # 2026-01-18: 12:00, 15:00, 16:00
    # 2026-01-19: 00:00
    return HourlySeries(
        time=[
            "2026-01-18T12:00",
            "2026-01-18T15:00",
            "2026-01-18T16:00",
            "2026-01-19T00:00",
        ],
        temp=[5.0, 7.0, 10.0, 1.0],
        code=[1, 2, 3, 45],
        feels_like=[4.0, 6.0, 9.0, 0.0],
        humidity=[50, 55, 60, 90],
        precip=[10, 20, 30, 40],
        wind=[5.0, 8.0, 12.0, 2.0],
    )


def test_derive_current_extras_matches_hour_bucket():
    s = _series_for_two_days()
    feels, hum, precip, wind = s.derive_current_extras("2026-01-18T12:50")
    assert feels == 4.0
    assert hum == 50
    assert precip == 10
    assert wind == 5.0


def test_snapshot_for_date_peak_temp_selects_max_temp_hour():
    s = _series_for_two_days()
    snap = s.snapshot_for_date("2026-01-18", strategy="peak_temp")
    assert snap is not None
    assert snap["time"] == "2026-01-18T16:00"
    assert snap["temp"] == 10.0
    assert snap["code"] == 3


def test_snapshot_for_date_fallbacks_to_target_hour_when_all_temps_missing():
    s = HourlySeries(
        time=["2026-01-18T12:00", "2026-01-18T15:00", "2026-01-18T16:00"],
        temp=[None, None, None],
        code=[1, 2, 3],
        feels_like=[None, None, None],
        humidity=[None, None, None],
        precip=[None, None, None],
        wind=[None, None, None],
    )
    snap = s.snapshot_for_date("2026-01-18", strategy="peak_temp", target_hour=15)
    assert snap is not None
    assert snap["time"] == "2026-01-18T15:00"


def test_snapshot_for_date_fallbacks_to_first_hour_when_target_hour_missing_and_all_temps_missing():
    s = HourlySeries(
        time=["2026-01-18T12:00", "2026-01-18T16:00"],  # no 15:00
        temp=[None, None],
        code=[1, 3],
        feels_like=[None, None],
        humidity=[None, None],
        precip=[None, None],
        wind=[None, None],
    )
    snap = s.snapshot_for_date("2026-01-18", strategy="peak_temp", target_hour=15)
    assert snap is not None
    assert snap["time"] == "2026-01-18T12:00"


def test_build_day_filters_only_selected_date_and_sets_pivot_index_for_today_current_hour():
    s = _series_for_two_days()

    day = s.build_day(
        "2026-01-18",
        mode=HourlyMode.TEMPERATURE,
        today_iso="2026-01-18",
        current_time_iso="2026-01-18T15:40",
    )

    assert day["time_isos"] == [
        "2026-01-18T12:00",
        "2026-01-18T15:00",
        "2026-01-18T16:00",
    ]
    assert day["hours_int"] == [12, 15, 16]
    assert day["values"] == [5.0, 7.0, 10.0]
    assert day["codes"] == [1, 2, 3]

    # pivot should point at the 15:00 entry (index 1 in the day lists)
    assert day["pivot_index"] == 1