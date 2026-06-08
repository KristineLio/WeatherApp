from weather_app.domain.models import HourlySeries
from weather_app.domain.modes import HourlyMode


def test_from_api_pads_missing_arrays_with_none():
    series = HourlySeries.from_api(
        {
            "time": ["2026-06-07T10:00", "2026-06-07T11:00", "2026-06-07T12:00"],
            "temperature_2m": [20.0],
            "weathercode": [0, 1],
        }
    )

    assert series.temp == [20.0, None, None]
    assert series.code == [0, 1, None]
    assert series.feels_like == [None, None, None]


def test_from_api_truncates_long_arrays():
    series = HourlySeries.from_api(
        {
            "time": ["2026-06-07T10:00", "2026-06-07T11:00"],
            "temperature_2m": [20.0, 21.0, 22.0],
            "weathercode": [0, 1, 2],
        }
    )

    assert series.temp == [20.0, 21.0]
    assert series.code == [0, 1]


def test_derive_current_extras_matches_current_hour(sample_hourly_series):
    feels, humidity, precip, wind = sample_hourly_series.derive_current_extras(
        "2026-06-07T09:30"
    )

    assert feels == 21.0
    assert humidity == 58
    assert precip == 10
    assert wind == 8.0


def test_derive_current_extras_returns_none_tuple_when_hour_missing(sample_hourly_series):
    assert sample_hourly_series.derive_current_extras("2026-06-07T23:30") == (
        None,
        None,
        None,
        None,
    )


def test_snapshot_for_date_uses_peak_temp(sample_hourly_series):
    snap = sample_hourly_series.snapshot_for_date("2026-06-07", strategy="peak_temp")

    assert snap is not None
    assert snap["time"] == "2026-06-07T15:00"
    assert snap["temp"] == 25.0


def test_snapshot_for_date_falls_back_to_target_hour_when_temps_missing():
    series = HourlySeries.from_api(
        {
            "time": ["2026-06-07T10:00", "2026-06-07T15:00"],
            "temperature_2m": [None, None],
            "weathercode": [0, 1],
        }
    )

    snap = series.snapshot_for_date("2026-06-07", target_hour=15)

    assert snap is not None
    assert snap["time"] == "2026-06-07T15:00"
    assert snap["code"] == 1


def test_snapshot_for_date_returns_none_when_date_missing(sample_hourly_series):
    assert sample_hourly_series.snapshot_for_date("2026-06-09") is None


def test_build_day_returns_only_selected_date(sample_hourly_series):
    result = sample_hourly_series.build_day(
        "2026-06-08",
        mode=HourlyMode.TEMPERATURE,
        today_iso="2026-06-07",
        current_time_iso="2026-06-07T09:30",
    )

    assert result["time_isos"] == ["2026-06-08T10:00", "2026-06-08T15:00"]
    assert result["values"] == [23.0, 28.0]
    assert result["pivot_index"] is None


def test_build_day_sets_pivot_index_for_current_hour(sample_hourly_series):
    result = sample_hourly_series.build_day(
        "2026-06-07",
        mode=HourlyMode.TEMPERATURE,
        today_iso="2026-06-07",
        current_time_iso="2026-06-07T09:30",
    )

    assert result["pivot_index"] == 1
