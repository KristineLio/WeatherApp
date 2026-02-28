import datetime as dt

# ============================================================================
# Date/Time Formatting
# ============================================================================

def _format_date(date_iso: str, pattern: str) -> str:
    d = dt.date.fromisoformat(date_iso)
    return d.strftime(pattern)

def weekday_from_iso(date_str: str) -> str:
    # "2025-09-23" -> "Tue"
    return _format_date(date_str, "%a")

def format_full_date(date_iso: str) -> str:
    # "2025-12-30" -> "Tuesday 30 Dec"
    return _format_date(date_iso, "%A, %d %b")  #b Dec, B December

def format_hour_label(hour_int: int) -> str:
    t = dt.time(hour=hour_int)
    try:
        return t.strftime("%-I %p")   # Unix
    except ValueError:
        return t.strftime("%I %p").lstrip("0")  # Windows


def is_night(time_iso: str | None, sunrise: str | None, sunset: str | None) -> bool:
    if not (time_iso and sunrise and sunset):
        return False

    t = dt.datetime.fromisoformat(time_iso)
    sr = dt.datetime.fromisoformat(sunrise)
    ss = dt.datetime.fromisoformat(sunset)

    return t < sr or t >= ss

def time_hhmm_from_iso(dt_iso: str | None) -> str:
    if not dt_iso:
        return ""
    try:
        return dt.datetime.fromisoformat(dt_iso).strftime("%H:%M")
    except Exception:
        return ""

def format_d_m_hhmm(iso: str) -> str:
    try:
        t = dt.datetime.fromisoformat((iso or "").strip())
        return t.strftime("%d %b %H:%M")
    except Exception:
        return (iso or "").strip() or "—"