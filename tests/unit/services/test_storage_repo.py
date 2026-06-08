from weather_app.services.storage import StorageRepo


def make_repo(tmp_path):
    return StorageRepo(tmp_path / "weather.db")


def test_favorite_lifecycle(tmp_path):
    repo = make_repo(tmp_path)

    assert repo.is_favorite("Sofia") is False

    repo.add_favorite(city="Sofia, Bulgaria", lat=42.6977, lon=23.3219, country="Bulgaria")

    assert repo.is_favorite("Sofia, Bulgaria") is True

    rows = repo.list_favorites()
    assert len(rows) == 1
    assert rows[0].city == "Sofia, Bulgaria"
    assert rows[0].lat == 42.6977
    assert rows[0].lon == 23.3219
    assert rows[0].country == "Bulgaria"
    assert rows[0].added_at

    repo.remove_favorite("Sofia, Bulgaria")

    assert repo.is_favorite("Sofia, Bulgaria") is False
    assert repo.list_favorites() == []


def test_add_favorite_ignores_empty_city(tmp_path):
    repo = make_repo(tmp_path)

    repo.add_favorite(city="   ", lat=None, lon=None, country=None)

    assert repo.list_favorites() == []


def test_add_favorite_replaces_existing_city(tmp_path):
    repo = make_repo(tmp_path)

    repo.add_favorite(city="Sofia", lat=1.0, lon=2.0, country="Old")
    repo.add_favorite(city="Sofia", lat=42.0, lon=23.0, country="Bulgaria")

    rows = repo.list_favorites()

    assert len(rows) == 1
    assert rows[0].city == "Sofia"
    assert rows[0].lat == 42.0
    assert rows[0].lon == 23.0
    assert rows[0].country == "Bulgaria"


def test_clear_favorites(tmp_path):
    repo = make_repo(tmp_path)

    repo.add_favorite(city="Sofia", lat=None, lon=None, country=None)
    repo.add_favorite(city="Kavala", lat=None, lon=None, country=None)

    repo.clear_favorites()

    assert repo.list_favorites() == []


def test_history_lifecycle_and_newest_first_order(tmp_path):
    repo = make_repo(tmp_path)

    repo.add_history(city="Sofia", lat=42.6977, lon=23.3219)
    repo.add_history(city="Kavala", lat=40.9376, lon=24.4129)
    repo.add_history(city="Drama", lat=41.149, lon=24.147)

    rows = repo.list_history(limit=10)

    assert [row.city for row in rows] == ["Drama", "Kavala", "Sofia"]
    assert rows[0].id > rows[1].id > rows[2].id
    assert rows[0].searched_at

    repo.remove_history(rows[1].id)

    remaining = repo.list_history(limit=10)
    assert [row.city for row in remaining] == ["Drama", "Sofia"]


def test_list_history_respects_limit_and_minimum_limit(tmp_path):
    repo = make_repo(tmp_path)

    repo.add_history(city="Sofia", lat=None, lon=None)
    repo.add_history(city="Kavala", lat=None, lon=None)
    repo.add_history(city="Drama", lat=None, lon=None)

    assert len(repo.list_history(limit=2)) == 2
    assert len(repo.list_history(limit=0)) == 1


def test_add_history_ignores_empty_city(tmp_path):
    repo = make_repo(tmp_path)

    repo.add_history(city="   ", lat=None, lon=None)

    assert repo.list_history() == []


def test_clear_history(tmp_path):
    repo = make_repo(tmp_path)

    repo.add_history(city="Sofia", lat=None, lon=None)
    repo.add_history(city="Kavala", lat=None, lon=None)

    repo.clear_history()

    assert repo.list_history() == []
