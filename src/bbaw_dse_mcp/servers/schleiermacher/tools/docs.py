"""
Document retrieval tools for Schleiermacher Digital.

This module provides tools for retrieving and displaying full documents
(letters, diary entries, lectures) from the Schleiermacher edition.
"""

from collections.abc import Awaitable
from typing import Protocol

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from lxml import etree

from bbaw_dse_mcp.config.base import settings
from bbaw_dse_mcp.servers.schleiermacher.resources.documents import determine_doctype
from bbaw_dse_mcp.servers.schleiermacher.utils.documents import (
    format_generic_document_as_markdown,
    parse_generic_document,
)
from bbaw_dse_mcp.servers.schleiermacher.utils.letters import (
    format_letter_as_markdown,
    parse_letter,
)
from bbaw_dse_mcp.utils.existdb import DocumentNotFoundError, ExistDBClient


class ClientGetter(Protocol):
    """Protocol for async client getter function."""

    def __call__(self) -> Awaitable[ExistDBClient]: ...


def register_docs_tools(
    mcp: FastMCP,
    get_client: ClientGetter,
) -> None:
    """Register document retrieval tools on the given MCP server.

    Args:
        mcp: The FastMCP server instance to register tools on
        get_client: Async function that returns an ExistDBClient
    """

    @mcp.tool
    async def get_document_by_id(
        document_id: str,
        ctx: Context | None = None,
    ) -> str:
        """Retrieve complete document.

        PURPOSE: Detailed view of a specific document as Markdown

        WHEN TO USE:
        - User wants to read a letter/diary entry
        - After successful search → display details
        - For citations and text analysis

        WHEN NOT TO USE:
        - For browsing/exploring → use list_collections() or list_collection_contents()
        - For keyword search → use search_by_keyword()

        Args:
            document_id: The xml:id of the document
            ctx: FastMCP Context

        Returns:
            Formatted markdown string with document content
        """
        if not document_id:
            raise ToolError("document_id is required")

        if ctx:
            await ctx.info(f"Fetching document: {document_id}")

        client = await get_client()

        try:
            # Use absolute path to data collection
            xml_str = await client.get_xml_document_by_id(
                document_id, collection=settings.sd_data_path
            )
        except DocumentNotFoundError:
            raise ToolError(f"Document '{document_id}' not found") from None
        except Exception as e:
            raise ToolError(f"Error retrieving '{document_id}': {e}") from e

        # Determine document type for processing
        doctype = determine_doctype(xml_str)

        if doctype == "letter fs":
            # Parse using comprehensive letter parser
            try:
                letter = parse_letter(xml_str, document_id)
                return format_letter_as_markdown(letter)
            except (etree.XMLSyntaxError, AttributeError, KeyError, ValueError) as e:
                raise ToolError(f"Error processing '{document_id}': {e}") from e

        # Handle other document types (lecture, diary, etc.) with generic parser
        if doctype:
            try:
                doc = parse_generic_document(xml_str, document_id)
                return format_generic_document_as_markdown(doc)
            except (etree.XMLSyntaxError, AttributeError, KeyError, ValueError) as e:
                raise ToolError(f"Error processing '{document_id}': {e}") from e

        # Fallback if no doctype found
        raise ToolError(f"Document '{document_id}' has no recognized type")
