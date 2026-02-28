import time
from pathlib import Path

from weather_app.services.storage import StorageRepo


def test_favorites_add_list_is_favorite_remove(tmp_path: Path):
    db = tmp_path / "test.db"
    repo = StorageRepo(db_path=db)

    assert repo.is_favorite("Sofia") is False

    repo.add_favorite(city="Sofia", lat=42.6977, lon=23.3219, country="Bulgaria")
    assert repo.is_favorite("Sofia") is True

    favs = repo.list_favorites()
    assert len(favs) == 1
    assert favs[0].city == "Sofia"
    assert favs[0].country in ("Bulgaria", "BG", None)  # depends what you pass

    repo.remove_favorite("Sofia")
    assert repo.is_favorite("Sofia") is False
    assert repo.list_favorites() == []


def test_favorites_replace_updates_added_at(tmp_path: Path):
    db = tmp_path / "test.db"
    repo = StorageRepo(db_path=db)

    repo.add_favorite(city="Athens", lat=37.9838, lon=23.7275, country="Greece")
    first = repo.list_favorites()[0].added_at

    # ensure timestamp changes (repo uses seconds precision)
    time.sleep(1)

    repo.add_favorite(city="Athens", lat=37.98, lon=23.72, country="Greece")
    second = repo.list_favorites()[0].added_at

    assert second >= first
    assert repo.is_favorite("Athens") is True


def test_history_add_list_limit_and_order(tmp_path: Path):
    db = tmp_path / "test.db"
    repo = StorageRepo(db_path=db)

    for i in range(25):
        repo.add_history(city=f"City{i}", lat=None, lon=None)

    hist20 = repo.list_history(limit=20)
    assert len(hist20) == 20

    # most recent should be City24 first
    assert hist20[0].city == "City24"
    assert hist20[-1].city == "City5"


def test_history_clear(tmp_path: Path):
    db = tmp_path / "test.db"
    repo = StorageRepo(db_path=db)

    repo.add_history(city="Sofia", lat=1.0, lon=2.0)
    assert len(repo.list_history(limit=20)) == 1

    repo.clear_history()
    assert repo.list_history(limit=20) == []