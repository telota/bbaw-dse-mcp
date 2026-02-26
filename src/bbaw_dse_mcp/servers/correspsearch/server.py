"""FastMCP Server für correspSearch API.

This server provides tools for cross-edition correspondence search
via the correspSearch aggregation service (https://correspsearch.net).
"""

import logging

from fastmcp import FastMCP
import httpx

from bbaw_dse_mcp.servers.correspsearch.tools.search import register_search_tools
from bbaw_dse_mcp.tools.base import register_util_tools

logger = logging.getLogger(__name__)

# FastMCP Server Instance
mcp = FastMCP("correspSearch")


# HTTP Client (singleton)
def _create_client() -> httpx.AsyncClient:
    """Create HTTP client for API requests."""
    return httpx.AsyncClient(
        timeout=30.0,
        headers={"User-Agent": "bbaw-dse-mcp/1.0"},
    )


_client: httpx.AsyncClient = _create_client()


def get_client() -> httpx.AsyncClient:
    """Get HTTP client for API requests."""
    return _client


# Register tools
register_util_tools(mcp)
register_search_tools(mcp, get_client)
