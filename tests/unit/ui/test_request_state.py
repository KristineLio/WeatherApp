# tests/unit/ui/test_request_state.py
from weather_app.ui.request_state import RequestState


def test_begin_request_returns_incrementing_ids_and_marks_latest() -> None:
    rs = RequestState()

    first = rs.begin_request()
    second = rs.begin_request()

    assert first == 1
    assert second == 2
    assert rs.is_latest(2) is True
    assert rs.is_latest(1) is False


def test_is_latest_false_before_any_request() -> None:
    rs = RequestState()

    assert rs.is_latest(1) is False
    assert rs.is_latest(999) is False


def test_start_reconnect_sets_seconds() -> None:
    rs = RequestState()

    rs.start_reconnect(20)

    assert rs.reconnect_seconds == 20


def test_start_reconnect_clamps_negative_to_zero() -> None:
    rs = RequestState()

    rs.start_reconnect(-5)

    assert rs.reconnect_seconds == 0


def test_tick_reconnect_counts_down_to_zero() -> None:
    rs = RequestState()
    rs.start_reconnect(3)

    assert rs.tick_reconnect() == 2
    assert rs.tick_reconnect() == 1
    assert rs.tick_reconnect() == 0
    assert rs.tick_reconnect() == 0
    assert rs.reconnect_seconds == 0


def test_clear_reconnect_resets_seconds() -> None:
    rs = RequestState()
    rs.start_reconnect(10)

    rs.clear_reconnect()

    assert rs.reconnect_seconds == 0


def test_should_retry_city_true_for_latest_request_and_same_city_case_insensitive() -> None:
    rs = RequestState()
    req_id = rs.begin_request()

    ok = rs.should_retry_city(
        failed_req_id=req_id,
        requested_city="Sofia",
        current_city="  sofia  ",
    )

    assert ok is True


def test_should_retry_city_false_for_stale_request() -> None:
    rs = RequestState()
    old_req = rs.begin_request()
    rs.begin_request()  # newer request becomes active

    ok = rs.should_retry_city(
        failed_req_id=old_req,
        requested_city="Sofia",
        current_city="Sofia",
    )

    assert ok is False


def test_should_retry_city_false_for_different_city() -> None:
    rs = RequestState()
    req_id = rs.begin_request()

    ok = rs.should_retry_city(
        failed_req_id=req_id,
        requested_city="Sofia",
        current_city="Plovdiv",
    )

    assert ok is False


def test_should_retry_city_false_for_blank_current_city() -> None:
    rs = RequestState()
    req_id = rs.begin_request()

    ok = rs.should_retry_city(
        failed_req_id=req_id,
        requested_city="Sofia",
        current_city="",
    )

    assert ok is False