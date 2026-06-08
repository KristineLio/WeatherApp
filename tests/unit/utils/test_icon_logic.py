from weather_app.utils import icon_logic
from weather_app.utils.icon_logic import (
    HUMIDITY_ICONS,
    PRECIP_ICONS,
    WIND_ICONS,
    code_to_gif,
    code_to_label_icon,
    night_variant,
    pick_icon_by_threshold,
)


def test_code_to_label_icon_known_and_unknown_codes():
    assert code_to_label_icon(0) == ("Clear sky", "clear.png")
    assert code_to_label_icon(999) == ("Weather", "unknown.png")


def test_pick_icon_by_threshold_boundaries():
    assert pick_icon_by_threshold(29, HUMIDITY_ICONS) == "hum_dry.png"
    assert pick_icon_by_threshold(30, HUMIDITY_ICONS) == "hum_ok.png"
    assert pick_icon_by_threshold(60, HUMIDITY_ICONS) == "hum_humid.png"
    assert pick_icon_by_threshold(80, HUMIDITY_ICONS) == "hum_muggy.png"

    assert pick_icon_by_threshold(19, PRECIP_ICONS) == "precip_low.png"
    assert pick_icon_by_threshold(20, PRECIP_ICONS) == "precip_med.png"

    assert pick_icon_by_threshold(9, WIND_ICONS) == "wind_calm.png"
    assert pick_icon_by_threshold(10, WIND_ICONS) == "wind_breeze.png"


def test_pick_icon_by_threshold_bad_values_use_fallback():
    assert pick_icon_by_threshold(None, HUMIDITY_ICONS, "fallback.png") == "fallback.png"
    assert pick_icon_by_threshold("bad", HUMIDITY_ICONS, "fallback.png") == "fallback.png"
    assert pick_icon_by_threshold(9999, HUMIDITY_ICONS, "fallback.png") == "fallback.png"


def test_night_variant_returns_original_when_not_night():
    assert night_variant("clear.png", night=False) == "clear.png"


def test_night_variant_uses_existing_png_candidate(tmp_path, monkeypatch):
    (tmp_path / "clear_night.png").write_text("fake")
    monkeypatch.setattr(icon_logic, "PNG_DIR", tmp_path)

    assert night_variant("clear.png", night=True, kind="png") == "clear_night.png"


def test_night_variant_falls_back_when_candidate_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(icon_logic, "PNG_DIR", tmp_path)

    assert night_variant("clear.png", night=True, kind="png") == "clear.png"


def test_code_to_gif_known_unknown_and_none():
    assert code_to_gif(0) == "clear.gif"
    assert code_to_gif(61) == "rain.gif"
    assert code_to_gif(999) == "unknown.gif"
    assert code_to_gif(None) == "unknown.gif"
