"""
Schleiermacher Digital specific MCP resources.

This module provides resources specific to the Schleiermacher edition,
including letters, diaries, and lectures.
"""

from collections.abc import Awaitable
from pathlib import Path
from typing import Protocol

from fastmcp import FastMCP
from lxml import etree

from bbaw_dse_mcp.config.base import settings
from bbaw_dse_mcp.servers.schleiermacher.utils.documents import (
    format_generic_document_as_markdown,
    parse_generic_document,
)
from bbaw_dse_mcp.servers.schleiermacher.utils.letters import (
    format_letter_as_markdown,
    parse_letter,
)
from bbaw_dse_mcp.utils.existdb import DocumentNotFoundError, ExistDBClient
from bbaw_dse_mcp.utils.tei import determine_doctype


class ClientGetter(Protocol):
    """Protocol for async client getter function."""

    def __call__(self) -> Awaitable[ExistDBClient]: ...


def register_schleiermacher_resources(
    mcp: FastMCP,
    get_client: ClientGetter,
) -> None:
    """Register Schleiermacher-specific resources on the given MCP server.
    Args:
        mcp: The FastMCP server instance to register tools on
        get_client: Async function that returns an ExistDBClient
    """

    @mcp.resource("schleiermacher://project-info")
    def get_project_info() -> str:
        """Information about Schleiermacher Digital edition.

        Provides context about the project, data structure, and available content.
        Loads information from project_info.md file.
        """
        project_info_path = Path(__file__).parent / "project_info.md"
        try:
            return project_info_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return "# Schleiermacher Digital\n\nProject information file not found."
        except (OSError, UnicodeDecodeError) as e:
            return f"# Schleiermacher Digital\n\nError loading project information: {e}"

    @mcp.resource("schleiermacher://citation-policy")
    def get_citation_policy() -> str:
        """Critical citation guidelines to prevent hallucinated references.

        READ THIS FIRST before citing any documents from the Schleiermacher edition.
        Explains how to properly cite documents and avoid inventing document IDs.
        """
        policy_path = Path(__file__).parent / "citation_policy.md"
        try:
            return policy_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return "# Citation Policy\n\nPolicy file not found."
        except (OSError, UnicodeDecodeError) as e:
            return f"# Citation Policy\n\nError loading policy: {e}"

    @mcp.resource("schleiermacher://document/{doc_id}")
    async def get_document_resource(doc_id: str) -> str:
        """Load a specific document (letter, diary) as context.

        Use this to attach a document's content to the conversation for analysis.
        Document IDs can be found via search_by_keyword(), browse_collection(),
        or search_letters().

        Args:
            doc_id: Document ID (xml:id attribute)
        """
        client = await get_client()

        try:
            # Use absolute path to data collection
            xml_str = await client.get_xml_document_by_id(
                doc_id, collection=settings.sd_data_path
            )
        except DocumentNotFoundError:
            return f"Document '{doc_id}' not found."

        # Determine document type for processing

        doctype = determine_doctype(xml_str)

        if doctype == "letter fs":
            # Parse using comprehensive letter parser
            try:
                letter = parse_letter(xml_str, doc_id)
                return format_letter_as_markdown(letter)
            except (etree.XMLSyntaxError, AttributeError, KeyError, ValueError) as e:
                return f"Error processing '{doc_id}': {e}"

        # Handle other document types (lecture, diary, etc.) with generic parser
        if doctype:
            try:
                doc = parse_generic_document(xml_str, doc_id)
                return format_generic_document_as_markdown(doc)
            except (etree.XMLSyntaxError, AttributeError, KeyError, ValueError) as e:
                return f"Error processing '{doc_id}': {e}"

        # Fallback if no doctype found
        return f"Document '{doc_id}' has no recognized type"
