"""State attributes of MiteMite entities, built from the data models."""

from typing import Any

from .models import Episode, Provider, Series, WatchProviders


def _compact(attributes: dict[str, Any]) -> dict[str, Any]:
    """Drop None and empty values: TMDB leaves many fields unknown."""
    return {
        key: value
        for key, value in attributes.items()
        if value is not None and value != "" and value != []
    }


def series_attributes(series: Series) -> dict[str, Any]:
    """Return the attributes that describe the series itself."""
    return _compact(
        {
            "series_id": series.id,
            "series_name": series.name,
            "first_air_date": (
                series.first_air_date.isoformat() if series.first_air_date else None
            ),
            "poster_url": series.poster_url,
            "backdrop_url": series.backdrop_url,
            "tmdb_url": series.tmdb_url,
            "genres": list(series.genres),
            "networks": list(series.networks),
            "origin_country": list(series.origin_country),
            "vote_average": series.vote_average,
        }
    )


def episode_attributes(series: Series, episode: Episode | None) -> dict[str, Any]:
    """Return episode attributes followed by the series attributes.

    The series attributes are always present, so a card can still show the
    poster of a series with nothing scheduled.
    """
    attributes: dict[str, Any] = {}
    if episode is not None:
        attributes = _compact(
            {
                "season_number": episode.season_number,
                "episode_number": episode.number,
                "name": episode.name,
                "overview": episode.overview,
                "air_date": episode.air_date.isoformat() if episode.air_date else None,
                "episode_type": episode.episode_type,
                "runtime": episode.runtime,
                "still_url": episode.still_url,
            }
        )
    return {**attributes, **series_attributes(series)}


def count_attributes(series: Series) -> dict[str, Any]:
    """Return the episode and season counts and the production flag."""
    return _compact(
        {
            "episodes_total": series.episodes_total,
            "number_of_seasons": series.number_of_seasons,
            "in_production": series.in_production,
        }
    )


def _provider_attributes(providers: tuple[Provider, ...]) -> list[dict[str, Any]]:
    return [
        _compact({"id": p.id, "name": p.name, "logo_url": p.logo_url})
        for p in providers
    ]


def provider_attributes(providers: WatchProviders | None) -> dict[str, Any]:
    """Return streaming availability: the region, the link and non-empty lists."""
    if providers is None:
        return {}
    return _compact(
        {
            "region": providers.region,
            "link": providers.link,
            "flatrate": _provider_attributes(providers.flatrate),
            "rent": _provider_attributes(providers.rent),
            "buy": _provider_attributes(providers.buy),
        }
    )


# Attributes that rarely change or are bulky: keep them out of the recorder.
UNRECORDED_ATTRIBUTES = frozenset(
    {
        "overview",
        "still_url",
        "poster_url",
        "backdrop_url",
        "tmdb_url",
        "genres",
        "networks",
        "origin_country",
        "flatrate",
        "rent",
        "buy",
        "link",
        "entity_picture",
    }
)
