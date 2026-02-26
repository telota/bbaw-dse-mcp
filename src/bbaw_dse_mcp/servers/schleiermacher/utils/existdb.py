"""eXist-db client state management for Schleiermacher server."""

import json
import logging

from bbaw_dse_mcp.config.base import settings
from bbaw_dse_mcp.config.existdb import ExistDBConfig
from bbaw_dse_mcp.utils.existdb import (
    ExistDBClient,
    ExistDBConnectionError,
)

logger = logging.getLogger(__name__)


# Server state container (avoids global keyword)
class _ServerState:
    """Container for server state to avoid global mutable variables."""

    client: ExistDBClient | None = None
    letter_cache: list[dict] | None = None  # Cached letter metadata


_state = _ServerState()


def _get_config() -> ExistDBConfig:
    """Build ExistDBConfig from settings.

    Uses sd_db_path for app collection and sd_data_path for data collection.
    """
    if settings.sd_local:
        return ExistDBConfig.local(
            app_path=settings.sd_db_path,
            data_path=settings.sd_data_path,
            username=settings.sd_username or "admin",
            password=settings.sd_password or "",
        )
    return ExistDBConfig.remote(
        base_url=settings.sd_url,
        app_path=settings.sd_db_path,
        data_path=settings.sd_data_path,
        username=settings.sd_username,
        password=settings.sd_password,
    )


async def get_client() -> ExistDBClient:
    """Get or create eXist-db client.

    Raises:
        ExistDBConnectionError: If database is not reachable
    """
    if _state.client is None:
        config = _get_config()
        _state.client = ExistDBClient(config)
        # Health check on first connection - fail fast if db is down
        if not await _state.client.health_check():
            raise ExistDBConnectionError(
                f"eXist-db not reachable at {config.base_url}. "
                f"Is the server running?"
            )
    return _state.client


async def close_client() -> None:
    """Close the eXist-db client (for cleanup)."""
    if _state.client is not None:
        await _state.client.close()
        _state.client = None
        _state.letter_cache = None  # Clear cache on close


async def get_letter_cache() -> list[dict]:
    """Get or load letter cache from eXist-db.

    The cache is loaded once from the JSON file in eXist-db and kept in memory
    for fast filtering. Contains all letter metadata including correspondence,
    dates, places, and mentions.

    Returns:
        List of letter metadata dicts
    """
    if _state.letter_cache is None:
        client = await get_client()
        cache_path = (
            f"{settings.sd_cache_path}/letters/register/letters-for-register.json"
        )

        try:
            # Fetch JSON from eXist-db
            json_content = await client.get_document_raw(cache_path)
            cache_data = json.loads(json_content)

            # Extract letter array from wrapper
            if isinstance(cache_data, dict) and "letter" in cache_data:
                letters = cache_data["letter"]
            else:
                letters = []

            # Extract data from each letter entry
            _state.letter_cache = [
                entry["data"] for entry in letters if "data" in entry
            ]

            logger.info(f"Loaded {len(_state.letter_cache)} letters into cache")
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load letter cache: {e}. Using empty cache.")
            _state.letter_cache = []

    return _state.letter_cache
