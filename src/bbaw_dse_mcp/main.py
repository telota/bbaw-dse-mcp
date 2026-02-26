"""Entry point for bbaw-dse-mcp Server.

Composite MCP Server for BBAW Digital Scholarly Editions.
Aggregates multiple digital scholarly editions via FastMCP mount().
"""

import logging

from fastmcp import FastMCP

from bbaw_dse_mcp.config.base import settings
from bbaw_dse_mcp.servers.correspsearch import server as correspsearch
from bbaw_dse_mcp.servers.mop import server as mop
from bbaw_dse_mcp.servers.schleiermacher import server as schleiermacher

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# Main aggregator server
app = FastMCP(
    name=settings.server_name,
    instructions="""
    MCP Server for dialogical access to digital scholarly editions from BBAW/TELOTA.

    Available editions:
    - sd_* (Schleiermacher Digital): Letters, diaries, lectures by Friedrich Schleiermacher
    - mop_* (Practices of Monarchy): Files on prussian monarchy and governance
    - cs_* (correspSearch): Cross-edition correspondence search

    Typical workflow:
    1. sd_search_in_documents, sd_filter_letters or sd_list_collections → Get overview
    2. sd_get_document_by_id → Retrieve details
    3. sd_search_register → Look up persons/places
    4. cs_search_correspondences → Cross-edition research
    """,
)

# Mount edition servers with prefixes
app.mount(server=schleiermacher.mcp, prefix="sd")
app.mount(server=mop.mcp, prefix="mop")
app.mount(server=correspsearch.mcp, prefix="cs")


# For direct execution
def main() -> None:
    """Run the MCP server."""
    logger.info("Starting BBAW DSE MCP Server...")
    logger.info(f"Server name: {settings.server_name}")
    logger.info(
        "Mounted editions: sd (Schleiermacher), mop (Monarchy), cs (correspSearch)"
    )
    app.run()


if __name__ == "__main__":
    main()
