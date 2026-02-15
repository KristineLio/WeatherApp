import wx

from weather_app.ui.frame import WeatherApp
from weather_app.utils.logging_config import setup_logging



def main() -> None:
    setup_logging()

    app = wx.App()
    WeatherApp(None, title="Weather App").Show()
    app.MainLoop()


if __name__ == "__main__":
    main()