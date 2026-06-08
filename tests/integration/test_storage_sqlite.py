import pytest

from weather_app.services.storage import StorageRepo

pytestmark = pytest.mark.integration


def test_storage_repo_creates_database_and_tables(tmp_path):
    db_path = tmp_path / "weather.db"

    repo = StorageRepo(db_path)

    assert db_path.exists()
    assert repo.list_favorites() == []
    assert repo.list_history() == []


def test_favorites_add_list_replace_remove_and_clear(tmp_path):
    repo = StorageRepo(tmp_path / "weather.db")

    repo.add_favorite(city="Sofia, Bulgaria", lat=42.6977, lon=23.3219, country="Bulgaria")
    repo.add_favorite(city="Kavala, Greece", lat=40.9376, lon=24.4129, country="Greece")

    assert repo.is_favorite("Sofia, Bulgaria") is True
    assert repo.is_favorite("Unknown") is False

    rows = repo.list_favorites()
    assert {row.city for row in rows} == {"Sofia, Bulgaria", "Kavala, Greece"}

    # Same city replaces the row instead of duplicating it.
    repo.add_favorite(city="Sofia, Bulgaria", lat=1.0, lon=2.0, country="Bulgaria")
    rows = [row for row in repo.list_favorites() if row.city == "Sofia, Bulgaria"]
    assert len(rows) == 1
    assert rows[0].lat == 1.0
    assert rows[0].lon == 2.0

    repo.remove_favorite("Sofia, Bulgaria")
    assert repo.is_favorite("Sofia, Bulgaria") is False

    repo.clear_favorites()
    assert repo.list_favorites() == []


def test_blank_favorite_is_ignored(tmp_path):
    repo = StorageRepo(tmp_path / "weather.db")

    repo.add_favorite(city="   ", lat=None, lon=None, country=None)

    assert repo.list_favorites() == []


def test_history_add_list_limit_remove_and_clear(tmp_path):
    repo = StorageRepo(tmp_path / "weather.db")

    repo.add_history(city="Sofia, Bulgaria", lat=42.6977, lon=23.3219)
    repo.add_history(city="Kavala, Greece", lat=40.9376, lon=24.4129)
    repo.add_history(city="Plovdiv, Bulgaria", lat=42.1354, lon=24.7453)

    latest_two = repo.list_history(limit=2)
    assert [row.city for row in latest_two] == ["Plovdiv, Bulgaria", "Kavala, Greece"]

    repo.remove_history(latest_two[0].id)
    cities = [row.city for row in repo.list_history(limit=10)]
    assert "Plovdiv, Bulgaria" not in cities

    repo.clear_history()
    assert repo.list_history() == []


def test_blank_history_is_ignored(tmp_path):
    repo = StorageRepo(tmp_path / "weather.db")

    repo.add_history(city="", lat=None, lon=None)

    assert repo.list_history() == []


def test_history_limit_is_clamped_to_at_least_one(tmp_path):
    repo = StorageRepo(tmp_path / "weather.db")
    repo.add_history(city="Sofia", lat=None, lon=None)
    repo.add_history(city="Kavala", lat=None, lon=None)

    rows = repo.list_history(limit=0)

    assert len(rows) == 1
