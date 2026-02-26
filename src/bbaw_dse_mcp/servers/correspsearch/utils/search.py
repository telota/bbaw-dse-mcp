"""Utilities for searching correspSearch."""

import logging

from fastmcp.exceptions import ToolError
import httpx

from bbaw_dse_mcp.schemas.correspsearch.correspsearch import CorrespSearchResult
from bbaw_dse_mcp.servers.correspsearch.utils.api import (
    build_api_params,
    parse_tei_json_response,
)

logger = logging.getLogger(__name__)

API_V2_BASE = "https://correspsearch.net/api/v2.0"


async def execute_correspsearch_query(
    client: httpx.AsyncClient,
    person_gnd: str | list[str] | None = None,
    person_viaf: str | list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    place_geonames: str | None = None,
    occupation_wikidata: str | None = None,
    edition_id: str | None = None,
    cmif_url: str | None = None,
    availability: str | None = None,
    text_query: str | None = None,
    gender: str | None = None,
    role: str | None = None,
    place_role: str | None = None,
    page: int = 1,
    max_results: int | None = None,
) -> CorrespSearchResult:
    """
    Execute a search query against the correspSearch API.

    Args:
        client: httpx.AsyncClient instance
        person_gnd: GND-ID(s) of the person(s) - single or list (combined with AND)
        person_viaf: VIAF-ID(s) of the person(s) - single or list (combined with AND)
        start_date: Start date (ISO 8601)
        end_date: End date (ISO 8601)
        place_geonames: GeoNames-ID of the place
        occupation_wikidata: Wikidata-ID of an occupation (e.g., "Q36180")
        edition_id: UUID of the edition
        cmif_url: URL of a CMIF file
        availability: "online", "print" or "hybrid"
        text_query: Full-text search query (searches in letter content)
        gender: "male", "female", or "unknown" to filter by correspondent gender
        role: "sent", "received", or "mentioned" for person filter
        place_role: "sent" or "received" for place filter
        page: Page number (1-indexed)
        max_results: Maximum number of results to return (slice the list)

    Returns:
        CorrespSearchResult object
    """
    params = build_api_params(
        person_gnd=person_gnd,
        person_viaf=person_viaf,
        place_geonames=place_geonames,
        occupation_wikidata=occupation_wikidata,
        start_date=start_date,
        end_date=end_date,
        edition_id=edition_id,
        cmif_url=cmif_url,
        availability=availability,
        text_query=text_query,
        gender=gender,
        page=page,
        role=role,
        place_role=place_role,
    )

    try:
        response = await client.get(
            f"{API_V2_BASE}/tei-json.xql",
            params=params,
        )
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.error(f"correspSearch API Error: {e}")
        raise ToolError(f"correspSearch API Fehler: {e}") from e

    result = parse_tei_json_response(response.json())

    # Limit results if requested
    if max_results is not None and max_results < len(result.letters):
        result.letters = result.letters[:max_results]

    return result
