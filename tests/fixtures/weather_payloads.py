"""Reusable fake Open-Meteo payloads for pytest tests.

These are intentionally small but shaped like the real API responses used by
WeatherService.
"""

GEOCODE_SOFIA = {
    "results": [
        {
            "name": "Sofia",
            "latitude": 42.6977,
            "longitude": 23.3219,
            "country": "Bulgaria",
        }
    ]
}

GEOCODE_EMPTY = {"results": []}

FORECAST_SOFIA = {
    "current_weather": {
        "time": "2026-06-07T09:30",
        "temperature": 22.4,
        "weathercode": 1,
        "windspeed": 8.0,
    },
    "daily": {
        "time": ["2026-06-07", "2026-06-08", "2026-06-09"],
        "temperature_2m_max": [25.2, 28.0, 27.0],
        "temperature_2m_min": [16.1, 17.0, 18.0],
        "weathercode": [1, 61, 0],
        "sunrise": [
            "2026-06-07T05:50",
            "2026-06-08T05:50",
            "2026-06-09T05:50",
        ],
        "sunset": [
            "2026-06-07T20:55",
            "2026-06-08T20:56",
            "2026-06-09T20:56",
        ],
    },
    "hourly": {
        "time": [
            "2026-06-07T08:00",
            "2026-06-07T09:00",
            "2026-06-07T10:00",
            "2026-06-08T09:00",
            "2026-06-08T10:00",
            "2026-06-08T15:00",
        ],
        "temperature_2m": [20.0, 22.0, 24.0, 21.0, 23.0, 28.0],
        "weathercode": [0, 1, 2, 61, 61, 3],
        "apparent_temperature": [19.0, 21.0, 23.0, 20.0, 22.0, 27.0],
        "relativehumidity_2m": [55, 58, 60, 70, 72, 65],
        "precipitation_probability": [0, 10, 20, 55, 60, 30],
        "windspeed": [5.0, 8.0, 10.0, 15.0, 18.0, 12.0],
    },
}

FORECAST_MISSING_CURRENT_TIME = {
    "current_weather": {
        "temperature": 22.4,
        "weathercode": 1,
        "windspeed": 8.0,
    },
    "daily": FORECAST_SOFIA["daily"],
    "hourly": FORECAST_SOFIA["hourly"],
}

FORECAST_MISSING_DAILY_HOURLY_TIME = {
    "current_weather": FORECAST_SOFIA["current_weather"],
    "daily": {},
    "hourly": {},
}
