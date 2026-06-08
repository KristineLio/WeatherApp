from weather_app.ui.request_state import RequestState


def test_begin_request_increments_and_marks_latest():
    state = RequestState()

    req1 = state.begin_request()
    req2 = state.begin_request()

    assert req1 == 1
    assert req2 == 2
    assert not state.is_latest(req1)
    assert state.is_latest(req2)


def test_reconnect_countdown_clamps_and_ticks_down():
    state = RequestState()

    state.start_reconnect(-5)
    assert state.reconnect_seconds == 0

    state.start_reconnect(3)
    assert state.tick_reconnect() == 2
    assert state.tick_reconnect() == 1
    assert state.tick_reconnect() == 0
    assert state.tick_reconnect() == 0


def test_clear_reconnect_resets_seconds():
    state = RequestState()
    state.start_reconnect(10)

    state.clear_reconnect()

    assert state.reconnect_seconds == 0


def test_should_retry_city_requires_latest_request_and_same_city():
    state = RequestState()
    req1 = state.begin_request()
    req2 = state.begin_request()

    assert not state.should_retry_city(
        failed_req_id=req1,
        requested_city="Sofia",
        current_city="Sofia",
    )
    assert state.should_retry_city(
        failed_req_id=req2,
        requested_city="Sofia",
        current_city="  sofia  ",
    )
    assert not state.should_retry_city(
        failed_req_id=req2,
        requested_city="Sofia",
        current_city="Plovdiv",
    )
