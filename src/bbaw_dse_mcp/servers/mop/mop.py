"""FastMCP Server für Praktiken der Monarchie (MoP).

Edition zur Erforschung höfischer Praktiken und monarchischer Repräsentation.
Basiert auf ediarum/eXist-db, ähnlich wie Schleiermacher Digital.
"""

import logging
from xml.etree import ElementTree as ET

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from bbaw_dse_mcp.config.base import TEI_NS as NS, settings
from bbaw_dse_mcp.config.existdb import ExistDBConfig
from bbaw_dse_mcp.schemas.base.data import Person, Place
from bbaw_dse_mcp.schemas.base.documents import Document
from bbaw_dse_mcp.schemas.base.responses import SearchResult
from bbaw_dse_mcp.utils.existdb import ExistDBClient

logger = logging.getLogger(__name__)

# FastMCP Server Instance
mcp = FastMCP("Praktiken der Monarchie")

# eXist-db Client
existdb: ExistDBClient | None = None


async def get_client() -> ExistDBClient:
    """Get or create eXist-db client for MoP."""
    global existdb
    if existdb is None:
        config = ExistDBConfig.remote(
            base_url=settings.ab_url,
            app_path=settings.ab_db_path,
            data_path=settings.ab_data_path,
            username=settings.ab_username,
            password=settings.ab_password,
        )
        existdb = ExistDBClient(config)
    return existdb


@mcp.tool
async def browse_documents(
    collection: str = "Texte",
    limit: int = 100,
    ctx: Context | None = None,
) -> dict:
    """Browse files and subcollections (MoP-specific wrapper).

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
        raise ToolError(f"Suchfehler: {e}")

    return [
        SearchResult(
            document_id=r["id"],
            title=r["title"],
            snippet=r.get("snippet", ""),
            type="document",
        )
        for r in results
    ]


@mcp.tool
async def get_document(
    document_id: str,
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
        raise ToolError(f"Dokument nicht gefunden: {e}")

    if not xml_str.strip():
        raise ToolError(f"Dokument '{document_id}' nicht gefunden")

    # Parse TEI-XML
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError as e:
        raise ToolError(f"XML-Parse-Fehler: {e}")

    # Extract Metadaten
    title_elem = root.find(".//tei:titleStmt/tei:title", NS)
    title = (
        title_elem.text if title_elem is not None and title_elem.text else "Unbekannt"
    )

    # Text extrahieren
    body = root.find(".//tei:body", NS)
    content = (
        ET.tostring(body, encoding="unicode", method="text") if body is not None else ""
    )

    doc = Document(
        id=document_id,
        doc_type="document",
        title=title,
        content=content[:2000] if len(content) > 2000 else content,
        tei_xml=xml_str if include_xml else None,
        url=f"{settings.ab_url}/dokument/{document_id}",
    )

    return doc


@mcp.tool
async def search_register(
    query: str,
    register_type: str = "personen",
    max_results: int = 20,
    ctx: Context | None = None,
) -> list[Person] | list[Place]:
    """Suche in MoP-Registern.

    PURPOSE: Strukturierte Registereinträge finden

    WHEN TO USE:
    - User sucht nach Person, Ort, Institution, Hof
    - Um IDs für weitere Suchen zu bekommen

    WHEN NOT TO USE:
    - Für Volltextsuche → nutze search_documents()

    Args:
        query: Suchbegriff
        register_type: Register (personen, orte, institutionen, hoefe, werke, aemter)
        max_results: Maximale Ergebnisse
        ctx: FastMCP Context

    Returns:
        Liste von Person/Place-Objekten
    """
    if not query:
        raise ToolError("query ist erforderlich")

    valid_types = ["personen", "orte", "institutionen", "hoefe", "werke", "aemter"]
    if register_type not in valid_types:
        raise ToolError(f"register_type muss einer von {valid_types} sein")

    if ctx:
        await ctx.info(f"Searching MoP {register_type} for: {query}")

    client = await get_client()

    # Angepasste XQuery je nach Register-Typ
    if register_type == "personen":
        xquery = f"""
        xquery version "3.1";
        declare namespace tei="http://www.tei-c.org/ns/1.0";

        for $person in collection('{settings.ab_db_path}/Register/personen')//tei:person
        let $name := string-join($person/tei:persName//text(), ' ')
        where contains(lower-case($name), lower-case('{query}'))
        let $id := $person/@xml:id/string()
        let $gnd := $person/@corresp/string()
        return concat($id, '|||', $name, '|||', $gnd)
        """
    elif register_type == "orte":
        xquery = f"""
        xquery version "3.1";
        declare namespace tei="http://www.tei-c.org/ns/1.0";

        for $place in collection('{settings.ab_db_path}/Register/orte')//tei:place
        let $name := $place/tei:placeName[1]/text()
        where contains(lower-case($name), lower-case('{query}'))
        let $id := $place/@xml:id/string()
        return concat($id, '|||', $name, '|||', '')
        """
    else:
        # Generische Suche für andere Register-Typen
        xquery = f"""
        xquery version "3.1";
        declare namespace tei="http://www.tei-c.org/ns/1.0";

        for $entry in collection('{settings.ab_db_path}/Register/{register_type}')//*[@xml:id]
        let $name := string-join($entry//text(), ' ')
        where contains(lower-case($name), lower-case('{query}'))
        let $id := $entry/@xml:id/string()
        return concat($id, '|||', normalize-space(substring($name, 1, 100)), '|||', '')
        """

    try:
        result = await client.execute_xquery(xquery.strip(), how_many=max_results)
    except Exception as e:
        raise ToolError(f"Register-Suche fehlgeschlagen: {e}")

    entries = []
    for line in result.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("|||")
        if len(parts) >= 2:
            if register_type == "orte":
                entries.append(
                    Place(
                        id=parts[0],
                        name=parts[1],
                    )
                )
            else:
                entries.append(
                    Person(
                        id=parts[0],
                        name=parts[1],
                        gnd=parts[2] if len(parts) > 2 and parts[2] else None,
                    )
                )

    return entries


@mcp.tool
async def get_register_entry(
    entry_id: str,
    register_type: str = "personen",
    ctx: Context | None = None,
) -> dict:
    """Detailansicht eines Registereintrags.

    PURPOSE: Vollständige Informationen zu Person, Ort, etc.

    WHEN TO USE:
    - Nach Registersuche für Details
    - Für biographische/geographische Informationen

    Args:
        entry_id: ID des Registereintrags
        register_type: Register-Typ
        ctx: FastMCP Context

    Returns:
        Dict mit allen verfügbaren Informationen
    """
    if not entry_id:
        raise ToolError("entry_id ist erforderlich")

    if ctx:
        await ctx.info(f"Fetching MoP {register_type} entry: {entry_id}")

    client = await get_client()

    query = f"""
    xquery version "3.1";
    declare namespace tei="http://www.tei-c.org/ns/1.0";

    collection('{settings.ab_db_path}/Register/{register_type}')//*[@xml:id='{entry_id}']
    """

    try:
        xml_str = await client.execute_xquery(query.strip())
    except Exception as e:
        raise ToolError(f"Eintrag nicht gefunden: {e}")

    if not xml_str.strip():
        raise ToolError(f"Eintrag '{entry_id}' nicht gefunden")

    # Parse XML
    try:
        root = ET.fromstring(
            f"<root xmlns:tei='http://www.tei-c.org/ns/1.0'>{xml_str}</root>"
        )
    except ET.ParseError as e:
        raise ToolError(f"XML-Parse-Fehler: {e}")

    # Extract content
    text_content = ET.tostring(root, encoding="unicode", method="text").strip()

    return {
        "id": entry_id,
        "type": register_type,
        "content": text_content[:1000] if len(text_content) > 1000 else text_content,
        "xml": xml_str,
    }
