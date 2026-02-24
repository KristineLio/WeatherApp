from pathlib import Path


# weather_app/ directory
PACKAGE_DIR = Path(__file__).resolve().parent.parent

# weather_app/assets/
ASSETS_DIR = PACKAGE_DIR / "assets"

# weather_app/assets/png/
PNG_DIR = ASSETS_DIR / "png"

# weather_app/assets/gif/
GIF_DIR = ASSETS_DIR / "gif"
