"""Tests for MiteMite data models."""

from custom_components.mitemite.models import (
    Episode,
    Provider,
    Season,
    Series,
)


def test_provider():
    """Test a provider."""
    provider = Provider(
        id=283,
        name="Crunchyroll",
        logo_path="/logo.png",
        url="https://www.crunchyroll.com",
    )

    assert provider.id == 283
    assert provider.name == "Crunchyroll"
    assert provider.logo_path == "/logo.png"
    assert provider.url == "https://www.crunchyroll.com"


def test_episode():
    """Test an episode."""
    episode = Episode(
        id=12345,
        number=1,
        name="Episode One",
        overview="An episode.",
        air_date="2026-10-05",
    )

    assert episode.id == 12345
    assert episode.number == 1
    assert episode.name == "Episode One"
    assert episode.air_date == "2026-10-05"


def test_season():
    """Test a season."""
    episode = Episode(
        id=12345,
        number=1,
        name="Episode One",
    )
    season = Season(
        series_id=54321,
        number=1,
        name="Season 1",
        episodes=(episode,),
    )

    assert season.series_id == 54321
    assert season.number == 1
    assert len(season.episodes) == 1
    assert season.episodes[0].id == 12345


def test_series():
    """Test a series."""
    provider = Provider(
        id=283,
        name="Crunchyroll",
    )
    series = Series(
        id=54321,
        name="Frieren",
        overview="An elf goes on an adventure.",
        poster_path="/poster.jpg",
        providers=(provider,),
    )

    assert series.id == 54321
    assert series.name == "Frieren"
    assert series.poster_path == "/poster.jpg"
    assert series.providers[0].name == "Crunchyroll"


def test_optional_values_default_to_none():
    """Test optional values."""
    episode = Episode(
        id=12345,
        number=1,
        name="Episode One",
    )

    assert episode.overview is None
    assert episode.air_date is None


def test_collections_default_to_empty():
    """Test empty collections."""
    series = Series(id=54321, name="Frieren")
    season = Season(series_id=54321, number=1, name="Season 1")

    assert series.providers == ()
    assert season.episodes == ()
