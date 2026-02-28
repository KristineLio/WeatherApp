from pathlib import Path
import pytest
from weather_app.services.storage import StorageRepo

pytestmark = pytest.mark.contract


#Guardrails / behavioral contracts 
#(limit=0 clamps to 1, whitespace normalization, delete only one row,clear_favorites full reset)
def test_history_limit_guardrails_limit_0_returns_1_when_data_exists(tmp_path: Path):
    db = tmp_path / "test.db"
    repo = StorageRepo(db_path=db)

    repo.add_history(city="City1", lat=None, lon=None)
    repo.add_history(city="City2", lat=None, lon=None)
    repo.add_history(city="City3", lat=None, lon=None)

    hist = repo.list_history(limit=0)
    assert len(hist) == 1
    assert hist[0].city == "City3"  # most recent (ORDER BY id DESC)


def test_remove_history_deletes_only_one_row(tmp_path: Path):
    db = tmp_path / "test.db"
    repo = StorageRepo(db_path=db)

    repo.add_history(city="City1", lat=None, lon=None)
    repo.add_history(city="City2", lat=None, lon=None)
    repo.add_history(city="City3", lat=None, lon=None)

    hist = repo.list_history(limit=20)
    ids = [h.id for h in hist]
    assert len(ids) == 3

    # delete one (pick the middle one to be safe)
    to_delete = ids[1]
    repo.remove_history(to_delete)

    remaining = repo.list_history(limit=20)
    remaining_ids = {h.id for h in remaining}

    assert to_delete not in remaining_ids
    assert ids[0] in remaining_ids
    assert ids[2] in remaining_ids


def test_clear_favorites_clears_and_is_favorite_is_false(tmp_path: Path):
    db = tmp_path / "test.db"
    repo = StorageRepo(db_path=db)

    repo.add_favorite(city="Sofia", lat=42.0, lon=23.0, country="BG")
    repo.add_favorite(city="Athens", lat=37.0, lon=23.0, country="GR")
    assert len(repo.list_favorites()) == 2

    repo.clear_favorites()

    assert repo.list_favorites() == []
    assert repo.is_favorite("Sofia") is False
    assert repo.is_favorite("Athens") is False


def test_city_whitespace_normalization_favorites(tmp_path: Path):
    db = tmp_path / "test.db"
    repo = StorageRepo(db_path=db)

    repo.add_favorite(city=" Sofia ", lat=42.6977, lon=23.3219, country="Bulgaria")

    # storage.strip() should normalize this
    assert repo.is_favorite("Sofia") is True
    assert repo.is_favorite(" Sofia ") is True