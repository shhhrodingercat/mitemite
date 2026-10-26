"""Constants for MiteMite."""

DOMAIN = "mitemite"
NAME = "MiteMite"
VERSION = "0.2.0"

# Config entry data is limited to the API key (homeassistant.const.CONF_API_KEY).
# Everything the user can change later lives in the entry options.
CONF_REGION = "region"
CONF_LANGUAGE = "language"
CONF_SERIES_IDS = "series_ids"
CONF_CALENDAR_IDS = "calendar_ids"
CONF_NEW_EPISODE_DAYS = "new_episode_days"

# Search form fields.
CONF_QUERY = "query"
CONF_ANIME_ONLY = "anime_only"

DEFAULT_REGION = "US"
DEFAULT_LANGUAGE = "en"
DEFAULT_NEW_EPISODE_DAYS = 2
MIN_NEW_EPISODE_DAYS = 1
MAX_NEW_EPISODE_DAYS = 14

TMDB_API_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_URL = "https://image.tmdb.org/t/p"
TMDB_TV_URL = "https://www.themoviedb.org/tv"

# Image sizes, all present in TMDB's /configuration response.
POSTER_SIZE = "w500"
BACKDROP_SIZE = "w780"
STILL_SIZE = "w300"
LOGO_SIZE = "w92"

# Device identifier of the "MiteMite" device that groups diagnostics.
SYSTEM_DEVICE_ID = "system"

# Key of the optional per-series calendar entity (unique ID: "<series id>_calendar").
CALENDAR_KEY = "calendar"

# Actions.
SERVICE_GET_RELEASES = "get_releases"
SERVICE_GET_UPCOMING = "get_upcoming"
ATTR_START_DATE = "start_date"
ATTR_DAYS = "days"
ATTR_LIMIT = "limit"
DEFAULT_RELEASE_DAYS = 1
MAX_RELEASE_DAYS = 366
DEFAULT_UPCOMING_LIMIT = 5
MAX_UPCOMING_LIMIT = 50

ATTRIBUTION = "Data provided by TMDB"
ATTRIBUTION_STREAMING = "Data provided by TMDB and JustWatch"
