"""Utility tools for authority ID lookups (GND, GeoNames, Wikidata, etc.)."""

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from bbaw_dse_mcp.utils.geonames import GeoNamesClient, get_geoname_id
from bbaw_dse_mcp.utils.gnd import search_gnd
from bbaw_dse_mcp.utils.wikidata import search_occupations, search_wikidata


def register_util_tools(mcp: FastMCP) -> None:
    """Register utility tools for authority ID lookups on the FastMCP server.

    Provides tools for:
    - GND (Gemeinsame Normdatei) person/place/organization lookups
    - GeoNames geographic identifier lookups
    - Wikidata occupation and entity lookups

    Args:
        mcp: The FastMCP server instance to register tools on
    """

    @mcp.tool
    async def search_for_gnd_id(
        name_query: str,
        limit: int = 5,
    ) -> list[dict[str, str]]:
        """Search for GND IDs by name using Lobid GND API.

        PURPOSE: Find GND identifiers for persons, places, or corporate bodies.

        WHEN TO USE:
        - When you need a GND ID for correspSearch filtering
        - To resolve person names to standard identifiers
        - For enriching metadata with authority data

        WHEN NOT TO USE:
        - For full entity data → use get_gnd_entity() tools
        - For non-GND authority data → use other services

        Args:
            name_query: Name or term to search for (e.g., "Goethe", "Humboldt")
            limit: Maximum number of results to return

        Returns:
            List of dicts with 'id' (GND URI) and 'label' for matching entities

        Example:
            >>> results = await search_for_gnd_id("Wilhelm von Humboldt")
            >>> gnd_id = results[0]['id'].split('/')[-1]  # Extract ID from URI
            >>> letters = await search_correspondences(person_gnd=gnd_id)
        """
        try:
            return await search_gnd(name_query, limit=limit)
        except Exception as e:
            raise ToolError(f"GND search failed: {e}") from e

    @mcp.tool
    async def search_for_geonames_id(
        place_query: str,
        country: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, str | int]]:
        """Search for GeoNames IDs by place name.

        PURPOSE: Find GeoNames identifiers for places to use as filters.

        WHEN TO USE:
        - When you need a GeoNames ID for correspSearch place filtering
        - To resolve place names to standard identifiers
        - For geographic analysis of correspondence networks

        WHEN NOT TO USE:
        - For person or organization names → use search_for_gnd_id()
        - When you already have a GeoNames ID

        Args:
            place_query: Place name to search for (e.g., "Berlin", "Paris")
            country: Optional ISO-2 country code to restrict search (e.g., "DE", "FR")
            limit: Maximum number of results to return

        Returns:
            List of dicts with place information:
            - geonameId: The GeoNames ID (use this for correspSearch)
            - name: Place name
            - countryCode: ISO-2 country code
            - lat, lng: Coordinates
            - adminName1: First-level admin division (e.g., state)
            - population: Population count (if available)

        Example:
            >>> results = await search_for_geonames_id("Berlin", country="DE")
            >>> geonames_id = str(results[0]['geonameId'])
            >>> letters = await search_correspondences(place_geonames=geonames_id)
        """
        try:
            client = GeoNamesClient()
            places = await client.search_place(
                place_query, max_rows=limit, country=country
            )

            # Return simplified format for easy use
            return [
                {
                    "geonameId": place.get("geonameId"),
                    "name": place.get("name", ""),
                    "countryCode": place.get("countryCode", ""),
                    "lat": place.get("lat"),
                    "lng": place.get("lng"),
                    "adminName1": place.get("adminName1", ""),
                    "population": place.get("population"),
                }
                for place in places
            ]
        except ValueError as e:
            # GeoNames username not configured
            raise ToolError(
                f"GeoNames configuration error: {e}. "
                "Set EDITIONS_GEONAMES_USERNAME in .env"
            ) from e
        except Exception as e:
            raise ToolError(f"GeoNames search failed: {e}") from e

    @mcp.tool
    async def get_place_geonames_id(
        place_name: str,
        country: str | None = None,
    ) -> int | None:
        """Get the GeoNames ID for a place (convenience function).

        PURPOSE: Quick lookup of a single GeoNames ID for a place.

        WHEN TO USE:
        - When you just need the ID without details
        - For quick place-to-ID conversion
        - When you're confident about the place name

        WHEN NOT TO USE:
        - When the place name might be ambiguous → use search_for_geonames_id()
        - When you need full place details

        Args:
            place_name: Name of the place (e.g., "Berlin", "Paris")
            country: Optional ISO-2 country code to restrict search (e.g., "DE")

        Returns:
            GeoNames ID as integer, or None if not found

        Example:
            >>> berlin_id = await get_place_geonames_id("Berlin", country="DE")
            >>> # Returns: 2950159
            >>> letters = await search_correspondences(place_geonames=str(berlin_id))
        """
        try:
            return await get_geoname_id(place_name, country=country)
        except ValueError as e:
            raise ToolError(
                f"GeoNames configuration error: {e}. "
                "Set EDITIONS_GEONAMES_USERNAME in .env"
            ) from e
        except Exception as e:
            raise ToolError(f"GeoNames lookup failed: {e}") from e

    @mcp.tool
    async def search_for_wikidata_occupation(
        occupation_query: str,
        limit: int = 10,
    ) -> list[dict[str, str]]:
        """Search for occupation entities in Wikidata.

        PURPOSE: Find Wikidata IDs for occupations to filter correspondence by profession.

        WHEN TO USE:
        - When you need a Wikidata ID for correspSearch occupation filtering
        - To find letters by correspondent profession (writers, philosophers, etc.)
        - For professional network analysis

        WHEN NOT TO USE:
        - For person names → use search_for_gnd_id()
        - For places → use search_for_geonames_id()
        - For non-occupation entities → use search_wikidata_entity()

        Args:
            occupation_query: Occupation name to search for (e.g., "Dichter", "Philosoph", "Maler")
            limit: Maximum number of results to return

        Returns:
            List of dicts with occupation entities:
            - id: Wikidata ID (e.g., "Q36180")
            - label: Occupation name in German
            - description: Brief description
            - uri: Full Wikidata URI

        Example:
            >>> results = await search_for_wikidata_occupation("Schriftsteller")
            >>> occupation_id = results[0]['id']  # e.g., "Q36180"
            >>> letters = await search_correspondences(occupation_wikidata=occupation_id)
        """
        try:
            return await search_occupations(occupation_query, limit=limit)
        except Exception as e:
            raise ToolError(f"Wikidata occupation search failed: {e}") from e

    @mcp.tool
    async def search_wikidata_entity(
        query: str,
        limit: int = 10,
        language: str = "de",
    ) -> list[dict[str, str]]:
        """Search for any entity in Wikidata.

        PURPOSE: General-purpose Wikidata entity search for various use cases.

        WHEN TO USE:
        - When searching for entities that aren't occupations
        - For broader Wikidata lookups
        - When you need flexibility in entity type

        WHEN NOT TO USE:
        - Specifically for occupations → use search_for_wikidata_occupation()
        - For GND/GeoNames data → use respective tools

        Args:
            query: Search term for any Wikidata entity
            limit: Maximum number of results to return
            language: Language code for labels (default: "de")

        Returns:
            List of dicts with entity information:
            - id: Wikidata ID (e.g., "Q36180")
            - label: Entity name
            - description: Brief description
            - uri: Full Wikidata URI

        Example:
            >>> results = await search_wikidata_entity("Aufklärung")
            >>> entity_id = results[0]['id']
        """
        try:
            return await search_wikidata(query, limit=limit, language=language)
        except Exception as e:
            raise ToolError(f"Wikidata search failed: {e}") from e
