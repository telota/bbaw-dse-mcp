"""Wohntopographie tools for MoP - residential topography data (GeoJSON).

Provides tools to fetch and search historical address data for court officials,
royal family members, and other persons/institutions in Berlin and Prussia.

Data is available for years: 1800, 1845, 1872, 1891, 1914
Source: https://actaborussica.bbaw.de/{year}.js (GeoJSON format)
"""

from collections.abc import Callable, Coroutine
import logging
from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
import httpx

from bbaw_dse_mcp.schemas.mop.mop import (
    GeoJSONFeature,
    ResidentialTopography,
)
from bbaw_dse_mcp.utils.existdb import ExistDBClient

logger = logging.getLogger(__name__)

# Type alias for client getter
ClientGetter = Callable[[], Coroutine[Any, Any, ExistDBClient]]

# Available years for Wohntopographie
AVAILABLE_YEARS = [1800, 1845, 1872, 1891, 1914]

# Base URL for Wohntopographie API
WOHNTOPO_BASE_URL = "https://actaborussica.bbaw.de"

# In-memory cache for fetched GeoJSON data
# Key: year (int), Value: ResidentialTopography
_wohntopo_cache: dict[int, ResidentialTopography] = {}


async def _fetch_wohntopo_data(
    year: int,
    ctx: Context | None = None,
) -> ResidentialTopography:
    """Fetch Wohntopographie data with caching.

    Args:
        year: Year to fetch (must be in AVAILABLE_YEARS)
        ctx: FastMCP Context for progress reporting

    Returns:
        ResidentialTopography object with all features

    Raises:
        ToolError: If year is invalid or API request fails
    """
    # Check cache first
    if year in _wohntopo_cache:
        if ctx:
            await ctx.info(f"Using cached data for year {year}")
        return _wohntopo_cache[year]

    # Fetch from API
    if ctx:
        await ctx.info(f"Fetching residential topography for year {year} from API...")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{WOHNTOPO_BASE_URL}/{year}.js"
            response = await client.get(url)
            response.raise_for_status()

            # Parse GeoJSON
            geojson_data = response.json()
            topo = ResidentialTopography(**geojson_data)

            # Store in cache
            _wohntopo_cache[year] = topo

            if ctx:
                await ctx.info(f"Cached {len(topo.features)} entries for year {year}")

            return topo

    except httpx.HTTPError as e:
        raise ToolError(f"Failed to fetch Wohntopographie data: {e}") from e


def register_wohntopo_tools(
    mcp: FastMCP,
) -> None:
    """Register Wohntopographie tools on the given MCP server.

    Args:
        mcp: The FastMCP server instance to register tools on
    """

    @mcp.tool
    async def get_residential_topography(
        year: int,
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """Fetch complete residential topography dataset for a specific year.

        PURPOSE: Retrieve GeoJSON data with addresses and locations of court officials,
                 royal family members, and other persons/institutions in Berlin and Prussia.

        WHEN TO USE:
        - User asks about where people lived in a specific year
        - User wants to analyze residential patterns
        - User needs geographic distribution of court members
        - For mapping and spatial analysis

        WHEN NOT TO USE:
        - For biographical register data → use search_register()
        - For document texts → use browse_documents() or search_documents()

        Args:
            year: Year for which to retrieve data (1800, 1845, 1872, 1891, or 1914)
            ctx: FastMCP Context for progress reporting

        Returns:
            Dict with:
            - year: The requested year
            - total_features: Total number of entries
            - features_with_coordinates: Number of entries with valid geographic coordinates
            - categories: Count of entries per category
            - cities: Count of entries per city
            - sample_features: First 10 features as examples
            - query_methods: Available search methods

        Raises:
            ToolError: If year is not available or API request fails
        """
        if year not in AVAILABLE_YEARS:
            raise ToolError(
                f"Year {year} not available. Available years: {', '.join(map(str, AVAILABLE_YEARS))}"
            )

        # Fetch data (with caching)
        topo = await _fetch_wohntopo_data(year, ctx)

        # Statistics
        with_coords = topo.get_with_coordinates()
        categories = topo.count_by_category()
        cities = topo.count_by_city()

        return {
            "year": year,
            "total_features": len(topo.features),
            "features_with_coordinates": len(with_coords),
            "categories": categories,
            "cities": cities,
            "sample_features": [_feature_to_dict(f) for f in topo.features[:10]],
            "query_methods": {
                "search_by_name": "Search by person name (partial match)",
                "search_by_category": "Filter by category (e.g., 'Königliche Familie')",
                "search_by_occupation": "Filter by occupation/activity",
                "search_by_location": "Filter by city or street",
                "search_by_ediarum_id": "Find exact person by Ediarum-ID",
            },
        }

    @mcp.tool
    async def search_residential_topography(
        year: int,
        name: str | None = None,
        vorname: str | None = None,
        kategorie: str | None = None,
        taetigkeit: str | None = None,
        stadt: str | None = None,
        strasse: str | None = None,
        ediarum_id: str | None = None,
        *,
        only_with_coordinates: bool = False,
        max_results: int = 50,
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """Search residential topography data with multiple filters.

        PURPOSE: Find persons/institutions by various criteria in historical address data.

        WHEN TO USE:
        - User searches for specific person by name
        - User wants to know who lived at a specific address
        - User wants to filter by profession, category, or location
        - User needs to find all court members in a certain category

        WHEN NOT TO USE:
        - For biographical details → use get_register_entry()
        - For full dataset overview → use get_residential_topography()

        Args:
            year: Year for data (1800, 1845, 1872, 1891, or 1914)
            name: Last name (partial match, case-insensitive)
            vorname: First name (partial match, case-insensitive)
            kategorie: Category filter (e.g., "Königliche Familie", "Diplomatie")
            taetigkeit: Occupation/activity filter
            stadt: City filter (partial match)
            strasse: Street name filter (partial match)
            ediarum_id: Exact Ediarum-ID match
            only_with_coordinates: Return only entries with valid geographic coordinates
            max_results: Maximum number of results to return
            ctx: FastMCP Context

        Returns:
            Dict with:
            - year: The queried year
            - filters_applied: List of active filters
            - total_matches: Number of matching entries
            - returned_results: Number of results in response (limited by max_results)
            - results: List of matching features

        Raises:
            ToolError: If year is not available or no filters provided
        """
        if year not in AVAILABLE_YEARS:
            raise ToolError(
                f"Year {year} not available. Available years: {', '.join(map(str, AVAILABLE_YEARS))}"
            )

        # Check if at least one filter is provided
        if not any([name, vorname, kategorie, taetigkeit, stadt, strasse, ediarum_id]):
            raise ToolError(
                "Please provide at least one search filter "
                "(name, vorname, kategorie, taetigkeit, stadt, strasse, or ediarum_id)"
            )

        # Fetch data (with caching)
        topo = await _fetch_wohntopo_data(year, ctx)

        # Apply filters
        results: list[GeoJSONFeature] = topo.features
        filters_applied: list[str] = []

        if ediarum_id:
            results = topo.get_by_ediarum_id(ediarum_id)
            filters_applied.append(f"ediarum_id='{ediarum_id}'")

        if name or vorname:
            results = topo.get_by_name(name=name, vorname=vorname)
            if name:
                filters_applied.append(f"name contains '{name}'")
            if vorname:
                filters_applied.append(f"vorname contains '{vorname}'")

        if kategorie:
            results = [f for f in results if f in topo.get_by_category(kategorie)]
            filters_applied.append(f"kategorie contains '{kategorie}'")

        if taetigkeit:
            results = [f for f in results if f in topo.get_by_occupation(taetigkeit)]
            filters_applied.append(f"taetigkeit contains '{taetigkeit}'")

        if stadt:
            results = [f for f in results if f in topo.get_by_city(stadt)]
            filters_applied.append(f"stadt contains '{stadt}'")

        if strasse:
            results = [f for f in results if f in topo.get_by_street(strasse)]
            filters_applied.append(f"strasse contains '{strasse}'")

        if only_with_coordinates:
            results = [f for f in results if f.has_coordinates()]
            filters_applied.append("only entries with coordinates")

        if ctx:
            await ctx.info(f"Found {len(results)} matching entries")

        # Limit results
        total_matches = len(results)
        results = results[:max_results]

        return {
            "year": year,
            "filters_applied": filters_applied,
            "total_matches": total_matches,
            "returned_results": len(results),
            "results": [_feature_to_dict(f) for f in results],
        }

    @mcp.tool
    async def list_available_wohntopo_years(
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """List all available years for residential topography data.

        PURPOSE: Show which years have Wohntopographie datasets available.

        WHEN TO USE:
        - User asks about available time periods
        - User wants to know which years can be queried
        - Before choosing a year for analysis

        Returns:
            Dict with available years and description
        """
        if ctx:
            await ctx.info("Listing available Wohntopographie years...")

        return {
            "available_years": AVAILABLE_YEARS,
            "description": "Residential topography datasets showing addresses and locations of court officials, royal family, and other persons/institutions in Berlin and Prussia.",
            "years_description": {
                1800: "Early Prussian court structure",
                1845: "Mid-19th century expansion",
                1872: "After German unification",
                1891: "Late 19th century",
                1914: "Pre-World War I",
            },
            "data_source": WOHNTOPO_BASE_URL,
        }


def _feature_to_dict(feature: GeoJSONFeature) -> dict[str, Any]:
    """Convert a GeoJSONFeature to a simplified dict for output.

    Args:
        feature: The feature to convert

    Returns:
        Dict with essential information
    """
    props = feature.properties
    result: dict[str, Any] = {
        "tabellen_id": props.tabellen_id,
        "ediarum_id": props.ediarum_id,
    }

    # Name information
    if props.adelspraedikat or props.adelstitel:
        full_name_parts = [
            props.adelstitel,
            props.vorname,
            props.adelspraedikat,
            props.name,
        ]
        result["full_name"] = " ".join(p for p in full_name_parts if p)
    else:
        name_parts = [props.vorname, props.name]
        result["full_name"] = " ".join(p for p in name_parts if p)

    # Categories and occupation
    if props.kategorie1:
        result["kategorie"] = props.kategorie1
    if props.taetigkeit:
        result["taetigkeit"] = props.taetigkeit
    if props.rang:
        result["rang"] = props.rang

    # Address
    address_parts = []
    if props.strasse:
        street = props.strasse
        if props.hausnummer:
            street = f"{street} {props.hausnummer}"
        address_parts.append(street)
    if props.adresszusatz:
        address_parts.append(props.adresszusatz)
    if props.stadt:
        address_parts.append(props.stadt)

    if address_parts:
        result["address"] = ", ".join(address_parts)

    # Coordinates
    if feature.has_coordinates():
        result["coordinates"] = {
            "longitude": feature.get_longitude(),
            "latitude": feature.get_latitude(),
        }

    # Additional info
    if props.verheiratet_mit_id:
        result["verheiratet_mit_id"] = props.verheiratet_mit_id
    if props.hof_hoefe:
        result["hof_hoefe"] = props.hof_hoefe
    if props.bemerkungen:
        result["bemerkungen"] = props.bemerkungen

    return result
