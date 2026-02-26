"""Search tools for MoP documents and fulltext search."""

import logging
from collections.abc import Callable, Coroutine
from typing import Any
from xml.etree import ElementTree as ET

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from bbaw_dse_mcp.config.base import settings
from bbaw_dse_mcp.schemas.base.documents import Document
from bbaw_dse_mcp.schemas.base.responses import SearchResult
from bbaw_dse_mcp.utils.existdb import ExistDBClient

# Namespace constants
NS = {"tei": "http://www.tei-c.org/ns/1.0"}

logger = logging.getLogger(__name__)

# Type alias for client getter
ClientGetter = Callable[[], Coroutine[Any, Any, ExistDBClient]]


def register_search_tools(
    mcp: FastMCP,
    get_client: ClientGetter,
) -> None:
    """Register search and document browsing tools on the given MCP server.

    Args:
        mcp: The FastMCP server instance to register tools on
        get_client: Async function that returns an ExistDBClient
    """

    @mcp.tool
    async def browse_documents(
        collection: str = "Texte",
        limit: int = 100,
        ctx: Context | None = None,
    ) -> dict:
        """Browse files and subcollections in MoP.

        PURPOSE: Überblick über verfügbare Dateien in der MoP-Edition

        WHEN TO USE:
        - User möchte sehen, was in der Edition verfügbar ist
        - Exploration ohne konkreten Suchbegriff

        WHEN NOT TO USE:
        - Bei konkreter Suche → nutze search_documents()
        - Für Metadaten → nutze get_document() danach

        Args:
            collection: Collection-Name (Texte, Register)
            limit: Maximale Anzahl Dateien
            ctx: FastMCP Context für Progress

        Returns:
            Dict mit 'files' und 'subcollections' Liste
        """
        if ctx:
            await ctx.info(f"Browsing MoP collection: {collection}")

        client = await get_client()
        collection_path = f"{settings.ab_db_path}/{collection}"

        try:
            filenames, subcollections = await client.list_collection_contents(
                collection_path
            )
        except Exception as e:
            raise ToolError(f"Fehler beim Abrufen der Collection: {e}") from e

        # Return limited file list
        files = filenames[:limit]

        return {
            "collection_path": collection_path,
            "file_count": len(files),
            "total_files": len(filenames),
            "files": files,
            "subcollections": subcollections,
        }

    @mcp.tool
    async def search_documents(
        keyword: str,
        collection: str = "Texte",
        max_results: int = 50,
        ctx: Context | None = None,
    ) -> list[SearchResult]:
        """Volltextsuche in MoP-Dokumenten.

        PURPOSE: Dokumente finden, die einen bestimmten Begriff enthalten

        WHEN TO USE:
        - User sucht nach Person, Institution, Thema
        - Explorative Suche zu höfischen Praktiken

        WHEN NOT TO USE:
        - Für strukturierte Registersuche → nutze search_register()

        Args:
            keyword: Suchbegriff
            collection: Collection (Texte)
            max_results: Maximale Ergebnisse
            ctx: FastMCP Context

        Returns:
            Liste von SearchResult-Objekten
        """
        if not keyword:
            raise ToolError("keyword ist erforderlich")

        if ctx:
            await ctx.info(f"Searching MoP for: {keyword}")

        client = await get_client()

        try:
            results = await client.search_fulltext(keyword, collection, max_results)
        except Exception as e:
            raise ToolError(f"Suchfehler: {e}") from e

        return [
            SearchResult(
                document_id=r["id"],
                title=r["title"],
                kwic_snippets=r.get("kwic_snippets"),
                citation_url=f"{settings.ab_url}/dokument/{r['id']}",
                type="document",
            )
            for r in results
        ]

    @mcp.tool
    async def get_document(
        document_id: str,
        *,
        include_xml: bool = False,
        ctx: Context | None = None,
    ) -> Document:
        """Vollständiges Dokument abrufen.

        PURPOSE: Detaillierte Ansicht eines spezifischen Dokuments

        WHEN TO USE:
        - User möchte ein Aktenstück lesen
        - Nach erfolgreicher Suche → Details anzeigen

        WHEN NOT TO USE:
        - Für Übersicht → nutze browse_documents() oder search_documents()

        Args:
            document_id: Die xml:id des Dokuments
            include_xml: Ob TEI-XML inkludiert werden soll
            ctx: FastMCP Context

        Returns:
            Document-Objekt mit Metadaten und Content
        """
        if not document_id:
            raise ToolError("document_id ist erforderlich")

        if ctx:
            await ctx.info(f"Fetching MoP document: {document_id}")

        client = await get_client()

        query = f"""
        xquery version "3.1";
        declare namespace tei="http://www.tei-c.org/ns/1.0";

        let $doc := collection('{settings.ab_db_path}')//tei:TEI[@xml:id='{document_id}']
        return $doc
        """

        try:
            xml_str = await client.execute_xquery(query.strip())
        except Exception as e:
            raise ToolError(f"Dokument nicht gefunden: {e}") from e

        if not xml_str.strip():
            raise ToolError(f"Dokument '{document_id}' nicht gefunden")

        # Parse TEI-XML
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError as e:
            raise ToolError(f"XML-Parse-Fehler: {e}") from e

        # Extract Metadaten
        title_elem = root.find(".//tei:titleStmt/tei:title", NS)
        title = (
            title_elem.text
            if title_elem is not None and title_elem.text
            else "Unbekannt"
        )

        # Text extrahieren
        body = root.find(".//tei:body", NS)
        content = (
            ET.tostring(body, encoding="unicode", method="text")
            if body is not None
            else ""
        )

        MAX_CONTENT_LENGTH = 2000
        truncated_content = (
            content[:MAX_CONTENT_LENGTH]
            if len(content) > MAX_CONTENT_LENGTH
            else content
        )

        return Document(
            id=document_id,
            doc_type="document",
            title=title,
            content=truncated_content,
            tei_xml=xml_str if include_xml else None,
            url=f"{settings.ab_url}/dokument/{document_id}",
        )
