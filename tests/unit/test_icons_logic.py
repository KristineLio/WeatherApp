from weather_app.utils.icon_logic import (
    pick_icon_by_threshold,
    PRECIP_ICONS,
    WIND_ICONS,
    HUMIDITY_ICONS,
    code_to_label_icon,
    code_to_gif,
)


def test_pick_icon_by_threshold_none_fallback():
    assert pick_icon_by_threshold(None, PRECIP_ICONS, "fallback.png") == "fallback.png"


def test_pick_icon_by_threshold_non_numeric_fallback():
    assert pick_icon_by_threshold("abc", PRECIP_ICONS, "fallback.png") == "fallback.png"


def test_precip_buckets():
    assert pick_icon_by_threshold(0, PRECIP_ICONS) == "precip_low.png"
    assert pick_icon_by_threshold(20, PRECIP_ICONS) == "precip_med.png"
    assert pick_icon_by_threshold(79.9, PRECIP_ICONS) == "precip_high.png"
    assert pick_icon_by_threshold(80, PRECIP_ICONS) == "precip_storm.png"


def test_wind_buckets():
    assert pick_icon_by_threshold(0, WIND_ICONS) == "wind_calm.png"
    assert pick_icon_by_threshold(10, WIND_ICONS) == "wind_breeze.png"
    assert pick_icon_by_threshold(39.9, WIND_ICONS) == "wind_windy.png"


def test_humidity_buckets():
    assert pick_icon_by_threshold(0, HUMIDITY_ICONS) == "hum_dry.png"
    assert pick_icon_by_threshold(30, HUMIDITY_ICONS) == "hum_ok.png"
    assert pick_icon_by_threshold(79.9, HUMIDITY_ICONS) == "hum_humid.png"
    assert pick_icon_by_threshold(80, HUMIDITY_ICONS) == "hum_muggy.png"


def test_code_to_label_icon_day_night():
    label, icon = code_to_label_icon(0, night=False)
    assert label == "Clear sky"
    assert icon == "clear.png"

    label2, icon2 = code_to_label_icon(0, night=True)
    assert label2 == label
    assert icon2 == "clear_night.png"


def test_code_to_gif_day_night_and_none():
    assert code_to_gif(0, night=False) == "clear.gif"
    assert code_to_gif(0, night=True) == "clear_night.gif"
    assert code_to_gif(None) == "unknown.gif"



def test_unknown_weather_code_returns_weather_unknown_png():
    """Edge: unknown WMO code falls back to unknown icon (day)."""
    label, icon = code_to_label_icon(999, night=False)
    assert label == "Weather"
    assert icon == "unknown.png"


def test_unknown_weather_code_at_night_gets_night_suffix():
    """Edge: unknown WMO code at night falls back to unknown_night.png."""
    label, icon = code_to_label_icon(999, night=True)
    assert label == "Weather"
    assert icon == "unknown_night.png"