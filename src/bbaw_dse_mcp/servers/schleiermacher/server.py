"""FastMCP Server for Schleiermacher Digital."""

from fastmcp import FastMCP

from bbaw_dse_mcp.config.base import settings
from bbaw_dse_mcp.servers.schleiermacher.resources.documents import (
    register_schleiermacher_resources,
)
from bbaw_dse_mcp.servers.schleiermacher.tools.chronology import (
    register_chronology_tools,
)
from bbaw_dse_mcp.servers.schleiermacher.tools.diaries import register_diary_tools
from bbaw_dse_mcp.servers.schleiermacher.tools.docs import register_docs_tools
from bbaw_dse_mcp.servers.schleiermacher.tools.register import register_register_tools
from bbaw_dse_mcp.servers.schleiermacher.tools.search import register_search_tools
from bbaw_dse_mcp.servers.schleiermacher.utils.existdb import (
    get_client,
    get_letter_cache,
)
from bbaw_dse_mcp.tools.existdb import register_existdb_tools

# FastMCP Server Instance
mcp = FastMCP("Schleiermacher Digital MCP Server")


# Register common eXist-db tools (list_collections, get_collection_stats, etc.)
register_existdb_tools(
    mcp, get_client, data_path=settings.sd_data_path, app_path=settings.sd_db_path
)

# Register Schleiermacher-specific resources
register_schleiermacher_resources(mcp, get_client)

# Register Schleiermacher-specific tools from submodules
register_docs_tools(mcp, get_client)
register_register_tools(mcp, get_client)
register_search_tools(mcp, get_client, get_letter_cache)
register_diary_tools(mcp, get_client)
register_chronology_tools(mcp, get_client)
