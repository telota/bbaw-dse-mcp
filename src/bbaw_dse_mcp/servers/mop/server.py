"""FastMCP Server für Praktiken der Monarchie (MoP).

Edition zur Erforschung höfischer Praktiken und monarchischer Repräsentation.
Basiert auf ediarum/eXist-db mit TEI-XML Dokumenten.

Register-Typen:
- personen: Hof- und Kabinettsbeamte (mit GND-IDs)
- orte: Geografische Orte
- institutionen: Höfische und staatliche Einrichtungen
- hoefe: Hofstaaten
- werke: Schriftliche Werke
- aemter: Ämter und Behörden

Datensammlungen:
- Texte: Editierte Quellentexte
- Adjutantenjournale: Tageskalender der Monarchen (1840-1918)
- Biogramme: Prosopographische Daten
- Hofkalendarium: Ereignisse des Hoflebens
- Organigramme: Hierarchievisualisierungen
- Wohntopographie: Adressen der Hofbeamten (GeoJSON)

Tools:
- search_documents, browse_documents, get_document - Document search and retrieval
- search_register, get_register_entry - Register (people, places, institutions) search
- search_biogramme, get_biogramm_by_id, extract_family_network - Detailed biographical entries
- get_residential_topography, search_residential_addresses - Historical address data
- search_adjutanten_journals, get_adjutanten_journal_entry, list_adjutanten_by_monarch - Court journals
"""

import logging

from fastmcp import Context, FastMCP

from bbaw_dse_mcp.config.base import settings
from bbaw_dse_mcp.config.existdb import ExistDBConfig
from bbaw_dse_mcp.servers.mop.tools.adjutanten import register_adjutanten_tools
from bbaw_dse_mcp.servers.mop.tools.biogramm import register_biogramm_tools
from bbaw_dse_mcp.servers.mop.tools.register import register_register_tools
from bbaw_dse_mcp.servers.mop.tools.search import register_search_tools
from bbaw_dse_mcp.servers.mop.tools.wohntopo import register_wohntopo_tools
from bbaw_dse_mcp.utils.existdb import ExistDBClient

logger = logging.getLogger(__name__)

# FastMCP Server Instance
mcp = FastMCP("Praktiken der Monarchie")

# eXist-db Client (singleton)
_existdb_client: ExistDBClient | None = None


async def get_client() -> ExistDBClient:
    """Get or create eXist-db client for MoP."""
    global _existdb_client
    if _existdb_client is None:
        config = ExistDBConfig.remote(
            base_url=settings.ab_url,
            app_path=settings.ab_db_path,
            data_path=settings.ab_data_path,
            username=settings.ab_username,
            password=settings.ab_password,
        )
        _existdb_client = ExistDBClient(config)
    return _existdb_client


# Register tools from submodules
register_search_tools(mcp, get_client)
register_register_tools(mcp, get_client)
register_biogramm_tools(mcp, get_client)
register_wohntopo_tools(mcp)
register_adjutanten_tools(mcp, get_client)


@mcp.tool
async def check_database_connection(ctx: Context | None = None) -> dict:
    """Check if the database is reachable and responsive.

    PURPOSE: Verify database connectivity for troubleshooting.

    WHEN TO USE:
    - When other tools fail unexpectedly
    - To verify setup is working
    - Health monitoring

    Returns:
        DatabaseStatus object with connection status, version, and paths
    """
    if ctx:
        await ctx.info("Checking MoP database connection...")

    client = await get_client()

    try:
        # Simple XQuery to check connection
        result = await client.execute_xquery("xquery version '3.1'; '1+1'", how_many=1)
        connected = result.strip() == "2"
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
            "base_url": settings.ab_url,
            "db_path": settings.ab_db_path,
        }

    return {
        "connected": connected,
        "base_url": settings.ab_url,
        "db_path": settings.ab_db_path,
        "data_path": settings.ab_data_path,
    }


@mcp.tool
async def execute_xquery(
    query: str,
    max_results: int = 100,
    ctx: Context | None = None,
) -> str:
    """Execute a raw XQuery against the database.

    PURPOSE: Run custom queries for advanced users or debugging.

    WHEN TO USE:
    - Other tools don't provide the needed functionality
    - Debugging or exploring data structure
    - Complex custom queries

    WHEN NOT TO USE:
    - For common operations, use specific tools instead
    - Don't use for write operations (read-only!)

    Args:
        query: XQuery string to execute
        max_results: Maximum number of results to return

    Returns:
        Raw query result as string (usually XML)
    """
    if ctx:
        await ctx.info("Executing custom XQuery...")

    client = await get_client()

    try:
        result = await client.execute_xquery(query, how_many=max_results)
    except Exception as e:
        return f"ERROR: {e}"

    return result
