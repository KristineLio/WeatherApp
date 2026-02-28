from weather_app.domain.modes import HourlyMode, MODE_META
from weather_app.domain.models import HourlySeries
from weather_app.domain.settings import Units


def _dummy_series() -> HourlySeries:
    # lengths are consistent to avoid zip truncation surprises
    return HourlySeries(
        time=["2026-01-18T12:00", "2026-01-18T13:00"],
        temp=[10.0, 11.0],
        code=[1, 2],
        feels_like=[9.0, 10.0],
        humidity=[50, 55],
        precip=[10, 20],
        wind=[5.0, 6.0],
    )


def test_mode_meta_covers_all_modes():
    # No missing modes in the dict
    assert set(MODE_META.keys()) == set(HourlyMode)


def test_mode_meta_fields_are_callable_and_reasonable():
    s = _dummy_series()

    for mode in HourlyMode:
        meta = MODE_META[mode]

        assert isinstance(meta.tab_label, str) and meta.tab_label.strip()
        assert callable(meta.fmt)
        assert callable(meta.icon)
        assert callable(meta.values)
        assert callable(meta.current_value)

        # fmt should always return a string, even for None
        out_none = meta.fmt(None, Units.METRIC)
        assert isinstance(out_none, str) and out_none

        # values() should return a list (same length as time in our dummy series)
        vals = meta.values(s)
        assert isinstance(vals, list)
        assert len(vals) == len(s.time)

        # icon() should return a filename-ish string
        icon = meta.icon(vals[0], s.code[0], False)
        assert isinstance(icon, str) and icon.endswith(".png")