# MiteMite

**TV & anime release tracking for Home Assistant.**

MiteMite follows the TV series and anime you choose, tells you when the next episode is out and where the series can be streamed in your region. Series are added directly from Home Assistant: no TMDB account lists or watchlists to maintain.

## Status

Early development — version 0.1.0. Setup, options, the TMDB client and all the entities below are implemented. It has been tested against recorded TMDB responses; feedback from real installations is welcome.

## Features

- **Add series from Home Assistant:** search TMDB by title, optionally limiting results to anime, and pick the series to follow. Add or remove them at any time from the integration options.
- **One device per series**, named with the title and first air year so remakes are easy to tell apart. Removing a series removes its device and entities.
- **Next and latest episode**, with the next release date.
- **Streaming availability** for your region, as series-level metadata.
- **Artwork and metadata as attributes** (poster, backdrop, TMDB link, genres, networks), so the data can feed other cards and integrations. Episode sensors use the poster as their picture.
- **Light on TMDB:** one request per series, every 6 hours and shortly after midnight. After a failure it retries after 15 minutes and keeps showing the last known data.
- **Read only:** MiteMite does not track what you have watched.

## Entities

Each followed series becomes a device with these entities.

| Entity | Type | State |
| --- | --- | --- |
| Next episode | sensor | Episode code such as `S01E52`, `unknown` when nothing is scheduled. |
| Next release | sensor (date) | Air date of the next episode, `unknown` when not known. |
| Latest episode | sensor | Code of the last episode that aired. |
| Episodes aired | sensor | Number of episodes that have aired. |
| Series status | sensor (enum) | Returning, ended, canceled, in production, planned or pilot. |
| New episode | binary sensor | On for a configurable number of days after an episode airs. |
| Streaming | sensor | Number of subscription (flatrate) providers in your region. |

The **MiteMite** device groups the diagnostics: **Last update**, **API status** (`ok`, `invalid_auth`, `rate_limited` or `error`, with the last error as an attribute) and an **Update data** button.

### Attributes

- **Next episode** and **Latest episode**: `season_number`, `episode_number`, `name`, `overview`, `air_date`, `episode_type` (`standard`, `mid_season`, `finale`...), `runtime`, `still_url`, plus the series attributes `series_id`, `series_name`, `first_air_date`, `poster_url`, `backdrop_url`, `tmdb_url`, `genres`, `networks`, `origin_country` and `vote_average`. Values TMDB does not have are left out.
- **Next release:** `episode`.
- **Episodes aired** and **Series status:** `episodes_total` (episodes TMDB lists, including scheduled ones), `number_of_seasons` and `in_production`.
- **New episode:** `episode` and `air_date` of the episode that makes it new.
- **Streaming:** `region`, `link` and the lists `flatrate`, `rent` and `buy` (each provider has `id`, `name` and `logo_url`), ordered by TMDB priority. Empty lists are left out.

### Example

Notify when a new episode comes out:

```yaml
alias: New episode
triggers:
  - trigger: state
    entity_id: sensor.detective_conan_1996_latest_episode
    not_from: [unknown, unavailable]
    not_to: [unknown, unavailable]
actions:
  - action: notify.notify
    data:
      title: "{{ trigger.to_state.attributes.series_name }}"
      message: >
        {{ trigger.to_state.state }} aired on
        {{ trigger.to_state.attributes.air_date }}.
```

## Data source and attribution

<img src="docs/images/tmdb-logo.svg" alt="TMDB logo" width="120">

This product uses the TMDB API but is not endorsed or certified by TMDB. Metadata and images come from [The Movie Database](https://www.themoviedb.org/).

Streaming availability data is provided by [JustWatch](https://www.justwatch.com/) through TMDB.

## Requirements

- Home Assistant 2026.8.0 or newer.
- A free [TMDB API key](https://www.themoviedb.org/settings/api). Both the v3 API key and the v4 read access token work.
- An internet connection.

## Installation

### HACS

1. Open HACS in Home Assistant.
2. Add this repository as a custom repository, selecting **Integration** as the category.
3. Install MiteMite and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and search for **MiteMite**.

### Manual installation

1. Copy the `custom_components/mitemite` directory into the `custom_components` directory of your Home Assistant configuration.
2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration** and search for **MiteMite**.

## Setup and configuration

1. Enter your TMDB API key, your region (used for streaming availability) and your language (used for titles and descriptions).
2. Search for a series by title. Turn on **Anime only** to keep only Japanese animation.
3. Select the series to follow.

Only one MiteMite instance can be configured. To change the list later, open the integration and choose **Configure**: you can add series, remove series, or change region, language and for how many days an episode counts as new. If TMDB ever rejects the stored key, Home Assistant asks you for a new one.

## How dates and episode numbers work

- **Air dates are broadcast dates in the series' country of origin**, not the date a streaming service in your region publishes the episode. An anime aired on a Saturday in Japan may reach your service later.
- **TMDB has no time of day**, only a date.
- **TMDB has no anime flag.** The **Anime only** filter keeps series in the Animation genre that originate in Japan.
- **Anime are usually a single TMDB season with absolute numbering**, so an episode code can look like `S01E1218`. MiteMite shows what TMDB reports.
- **Episodes aired is calculated** from the season list and the last aired episode, because TMDB's own episode count includes scheduled episodes.
- **New episode** means recent, not unwatched: MiteMite does not know what you have watched.
- **Titles and descriptions of recent episodes are often missing** on TMDB. Placeholder names such as "Episode 52" are normal.
- **Names fall back to the original language** when TMDB has no translation in yours. You can rename a device in Home Assistant and MiteMite will not overwrite it.

## Troubleshooting

- **Invalid API key:** check you copied the whole key. Both the v3 key and the v4 token are accepted.
- **Search finds nothing:** try a shorter title or turn off **Anime only**.
- **Next release is `unknown`:** TMDB has no scheduled episode for the series, for example between two seasons.
- **A series' entities are unavailable:** TMDB no longer has it. Remove it from the options.
- **API status shows an error:** the `last_error` attribute says why. Entities keep their last data and the integration retries after 15 minutes; press **Update data** to retry now.

## Development

```bash
pip install -r requirements_test.txt
ruff check .
pytest
```

## License

[MIT](LICENSE). Data from TMDB and JustWatch is subject to their own terms.
