import logging
import wx

from weather_app.ui.frame import WeatherApp


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,  # switch to DEBUG when needed
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def main() -> None:
    setup_logging()

    app = wx.App()
    WeatherApp(None, title="Weather App").Show()
    app.MainLoop()


if __name__ == "__main__":
    main()