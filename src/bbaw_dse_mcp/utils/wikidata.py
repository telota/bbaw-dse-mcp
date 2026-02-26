"""Utilities for interacting with the Wikidata API."""

from __future__ import annotations

import httpx


async def search_wikidata(
    query: str,
    limit: int = 10,
    language: str = "de",
    entity_type: str | None = None,
) -> list[dict[str, str]]:
    """
    Search Wikidata entities using the wbsearchentities API.

    Args:
        query: Search term (e.g., "Dichter", "Philosoph")
        limit: Number of results to return (default: 10)
        language: Language code for labels (default: "de")
        entity_type: Filter by type - "item" for Q-items, "property" for P-properties

    Returns:
        List of dictionaries containing:
        - id: Wikidata ID (e.g., "Q36180")
        - label: Entity label in specified language
        - description: Entity description
        - uri: Full Wikidata URI (e.g., "http://www.wikidata.org/entity/Q36180")
    """
    api_url = "https://www.wikidata.org/w/api.php"

    params: dict[str, str | int] = {
        "action": "wbsearchentities",
        "format": "json",
        "search": query,
        "language": language,
        "limit": limit,
    }

    if entity_type:
        params["type"] = entity_type

    headers = {
        "User-Agent": "BBAW-DSE-MCP/1.0 (https://github.com/bbaw; research tool)"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(api_url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        return [
            {
                "id": item.get("id", ""),
                "label": item.get("label", ""),
                "description": item.get("description", ""),
                "uri": item.get("concepturi", ""),
            }
            for item in data.get("search", [])
        ]


async def get_wikidata_entity(entity_id: str, language: str = "de") -> dict:
    """
    Get detailed information about a Wikidata entity.

    Args:
        entity_id: Wikidata ID (e.g., "Q36180") or full URI
        language: Language code for labels and descriptions

    Returns:
        Dictionary with entity data including:
        - id: Wikidata ID
        - label: Entity label
        - description: Entity description
        - uri: Full URI
        - aliases: Alternative names
        - claims: Entity properties and values
    """
    # Extract ID from URI if needed
    if entity_id.startswith("http"):
        entity_id = entity_id.split("/")[-1]

    api_url = "https://www.wikidata.org/w/api.php"

    params = {
        "action": "wbgetentities",
        "format": "json",
        "ids": entity_id,
        "languages": language,
    }

    headers = {
        "User-Agent": "BBAW-DSE-MCP/1.0 (https://github.com/telota; research tool)"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(api_url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        entities = data.get("entities", {})
        if entity_id not in entities:
            return {}

        entity = entities[entity_id]

        # Extract basic info
        labels = entity.get("labels", {})
        descriptions = entity.get("descriptions", {})
        aliases = entity.get("aliases", {})

        return {
            "id": entity_id,
            "label": labels.get(language, {}).get("value", ""),
            "description": descriptions.get(language, {}).get("value", ""),
            "uri": f"http://www.wikidata.org/entity/{entity_id}",
            "aliases": [alias.get("value", "") for alias in aliases.get(language, [])],
            "claims": entity.get("claims", {}),
        }


async def search_occupations(query: str, limit: int = 10) -> list[dict[str, str]]:
    """
    Search for occupation entities in Wikidata.

    This is a convenience wrapper around search_wikidata that searches
    specifically for occupations (subclass of Q12737077).

    Args:
        query: Search term (e.g., "Dichter", "Philosoph", "Maler")
        limit: Number of results to return

    Returns:
        List of occupation entities with id, label, description, and uri
    """
    # Simple search - Wikidata API doesn't directly support filtering by instance/subclass
    # We search and return all results, caller can filter if needed
    results = await search_wikidata(query, limit=limit, entity_type="item")

    # Filter to only include items that look like occupations
    # (have "Beruf" or "occupation" in description)
    occupation_keywords = ["beruf", "occupation", "profession"]
    filtered = []

    for item in results:
        desc = item.get("description", "").lower()
        if any(keyword in desc for keyword in occupation_keywords):
            filtered.append(item)

    # If no filtered results, return all (user query was specific enough)
    return filtered if filtered else results
