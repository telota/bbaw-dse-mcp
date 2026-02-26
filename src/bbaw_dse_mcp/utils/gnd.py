"""Utilities for interacting with the Lobid GND API."""

import httpx

from bbaw_dse_mcp.schemas.base.responses import LobidGNDResponse

BASE_URL = "https://lobid.org/gnd"
SEARCH_URL = f"{BASE_URL}/search"


async def search_gnd(
    query: str, limit: int = 10, type_filter: str | None = None
) -> list[dict[str, str]]:
    """
    Search GND for a given query string (autocomplete style).

    Args:
        query: The search term (e.g. "Goethe")
        limit: Number of results to return
        type_filter: Optional filter for type (e.g. 'Person', 'Place', 'CorporateBody')

    Returns:
        List of dictionaries containing 'id' (URI) and 'label'
    """
    params: dict[str, str | int] = {"q": query, "format": "json:suggest", "size": limit}

    if type_filter:
        params["filter"] = f"type:{type_filter}"

    async with httpx.AsyncClient() as client:
        response = await client.get(SEARCH_URL, params=params)
        response.raise_for_status()
        data: list[dict[str, str]] = response.json()
        return data


async def get_gnd_entity(gnd_id: str) -> LobidGNDResponse:
    """
    Get full entity data for a GND ID.

    Args:
        gnd_id: The GND ID (e.g. "118540238") or URI

    Returns:
        LobidGNDResponse object with entity data
    """
    # handle both raw ID and full URI
    if gnd_id.startswith("http"):
        # if it's a d-nb.info URI, extract the ID and use lobid.org
        if "d-nb.info/gnd/" in gnd_id:
            scan_id = gnd_id.rstrip("/").split("/")[-1]
            url = f"{BASE_URL}/{scan_id}.json"
        else:
            # for lobid.org or other URIs, ensure .json suffix
            url = gnd_id if gnd_id.endswith(".json") else f"{gnd_id}.json"
    else:
        url = f"{BASE_URL}/{gnd_id}.json"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        return LobidGNDResponse(**data)


async def resolve_gnd_id(name: str, type_filter: str = "Person") -> str | None:
    """
    Helper to resolve a name to the best matching GND ID (URI).

    Args:
        name: Name to search for
        type_filter: Type to filter by (default: Person)

    Returns:
        The URI of the first match or None
    """
    results = await search_gnd(name, limit=1, type_filter=type_filter)
    if results and len(results) > 0:
        return results[0].get("id")
    return None
