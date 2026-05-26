from datetime import date
import pytest


@pytest.fixture()
def cache(tmp_path, monkeypatch):
    """Redirect cache file to a temp dir so tests never touch ~/.nbodiesgravity."""
    import nbodiesgravity.data.cache as mod
    monkeypatch.setattr(mod, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(mod, "CACHE_FILE", tmp_path / "cache.json")
    return mod


def test_miss_returns_none(cache):
    assert cache.get("399", date(2000, 1, 1)) is None


def test_store_and_retrieve(cache):
    state = {"pos_au": [1.0, 0.0, 0.0], "vel_au_per_day": [0.0, 0.017202, 0.0]}
    cache.store("399", date(2000, 1, 1), state)
    assert cache.get("399", date(2000, 1, 1)) == state


def test_different_dates_are_independent(cache):
    a = {"pos_au": [1.0, 0.0, 0.0], "vel_au_per_day": [0.0, 0.017, 0.0]}
    b = {"pos_au": [0.0, 1.0, 0.0], "vel_au_per_day": [-0.017, 0.0, 0.0]}
    cache.store("399", date(2000, 1, 1), a)
    cache.store("399", date(2001, 1, 1), b)
    assert cache.get("399", date(2000, 1, 1)) == a
    assert cache.get("399", date(2001, 1, 1)) == b


def test_clear_cache_removes_file(cache, tmp_path):
    cache.store("399", date(2000, 1, 1), {"pos_au": [1, 0, 0], "vel_au_per_day": [0, 0, 0]})
    assert (tmp_path / "cache.json").exists()
    cache.clear_cache()
    assert not (tmp_path / "cache.json").exists()


def test_clear_nonexistent_cache_does_not_raise(cache):
    cache.clear_cache()  # file does not exist — must not raise
