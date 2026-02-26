"""GeoNames API utilities for place name geocoding and ID lookup."""

from __future__ import annotations

import httpx

from bbaw_dse_mcp.config.base import settings


class GeoNamesClient:
    """Client for GeoNames API to lookup place information and IDs.

    Requires a GeoNames username. Get one free at: http://www.geonames.org/login
    Set via EDITIONS_GEONAMES_USERNAME in .env or pass directly.
    """

    def __init__(self, username: str | None = None) -> None:
        """Initialize GeoNames client.

        Args:
            username: GeoNames API username. If None, reads from settings.
        """
        self.username = username or settings.geonames_username
        if not self.username:
            raise ValueError(
                "GeoNames username required. Set EDITIONS_GEONAMES_USERNAME in .env "
                "or pass username parameter. Register at http://www.geonames.org/login"
            )
        self.base_url = "http://api.geonames.org"

    async def search_place(
        self,
        name: str,
        max_rows: int = 5,
        country: str | None = None,
        feature_class: str | None = None,
    ) -> list[dict]:
        """Search for places by name using GeoNames API.

        Args:
            name: Place name to search for
            max_rows: Maximum number of results (default: 5)
            country: ISO-2 country code to restrict search (e.g., 'DE', 'FR')
            feature_class: GeoNames feature class (e.g., 'P' for populated place)

        Returns:
            List of place dictionaries with fields:
            - geonameId: Unique GeoNames ID
            - name: Place name
            - lat, lng: Coordinates
            - countryCode: ISO-2 country code
            - countryName: Full country name
            - adminName1: First-level admin division (e.g., state)
            - population: Population count
            - feature*: Feature class and code

        Raises:
            httpx.HTTPError: If API request fails
        """
        params: dict[str, str | int] = {
            "q": name,
            "maxRows": max_rows,
            "username": str(self.username),
            "type": "json",
        }

        if country:
            params["country"] = country
        if feature_class:
            params["featureClass"] = feature_class

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/searchJSON",
                params=params,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            # Check for API errors
            if "status" in data:
                raise RuntimeError(
                    f"GeoNames API error: {data['status'].get('message', 'Unknown error')}"
                )

            geonames: list[dict] = data.get("geonames", [])
            return geonames

    async def get_geoname_id(
        self,
        name: str,
        country: str | None = None,
    ) -> int | None:
        """Get the GeoNames ID for a place by searching for its name.

        Returns the ID of the first (most relevant) result.

        Args:
            name: Place name to search for
            country: ISO-2 country code to restrict search (e.g., 'DE', 'FR')

        Returns:
            GeoNames ID as integer, or None if no results found
        """
        results = await self.search_place(name, max_rows=1, country=country)
        if results:
            return results[0].get("geonameId")
        return None


async def get_geoname_id(
    name: str,
    country: str | None = None,
    username: str | None = None,
) -> int | None:
    """Convenience function to get GeoNames ID for a place name.

    Args:
        name: Place name to search for
        country: ISO-2 country code to restrict search (e.g., 'DE', 'FR')
        username: GeoNames API username (optional, reads from env if not provided)

    Returns:
        GeoNames ID as integer, or None if no results found

    Example:
        >>> geoname_id = await get_geoname_id("Berlin", country="DE")
        >>> print(geoname_id)
        2950159
    """
    client = GeoNamesClient(username=username)
    return await client.get_geoname_id(name, country=country)
