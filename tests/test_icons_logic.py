from weather_app.utils.icons import (
    pick_icon_by_threshold,
    PRECIP_ICONS,
    WIND_ICONS,
    HUMIDITY_ICONS,
    code_to_label_icon,
)


def test_pick_icon_by_threshold_none_returns_fallback():
    assert pick_icon_by_threshold(None, PRECIP_ICONS, "fallback.png") == "fallback.png"


def test_pick_icon_by_threshold_non_numeric_returns_fallback():
    assert pick_icon_by_threshold("abc", PRECIP_ICONS, "fallback.png") == "fallback.png"


def test_pick_icon_by_threshold_precip_buckets():
    assert pick_icon_by_threshold(0, PRECIP_ICONS) == "precip_low.png"
    assert pick_icon_by_threshold(20, PRECIP_ICONS) == "precip_med.png"   # 20 is not <20, next bucket
    assert pick_icon_by_threshold(79.9, PRECIP_ICONS) == "precip_high.png"
    assert pick_icon_by_threshold(80, PRECIP_ICONS) == "precip_storm.png"


def test_pick_icon_by_threshold_wind_buckets():
    assert pick_icon_by_threshold(0, WIND_ICONS) == "wind_calm.png"
    assert pick_icon_by_threshold(10, WIND_ICONS) == "wind_breeze.png"
    assert pick_icon_by_threshold(39.9, WIND_ICONS) == "wind_windy.png"


def test_pick_icon_by_threshold_humidity_buckets():
    assert pick_icon_by_threshold(0, HUMIDITY_ICONS) == "hum_dry.png"
    assert pick_icon_by_threshold(30, HUMIDITY_ICONS) == "hum_ok.png"
    assert pick_icon_by_threshold(79.9, HUMIDITY_ICONS) == "hum_humid.png"
    assert pick_icon_by_threshold(80, HUMIDITY_ICONS) == "hum_muggy.png"


def test_code_to_label_icon_day_night_variants():
    label, icon = code_to_label_icon(0, night=False)
    assert label
    assert icon == "clear.png"

    label2, icon2 = code_to_label_icon(0, night=True)
    assert label2 == label
    assert icon2 == "clear_night.png"