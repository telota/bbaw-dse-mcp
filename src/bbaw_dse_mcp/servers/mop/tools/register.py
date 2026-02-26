"""Register search tools for MoP person, place, institution, etc. indexes."""

from collections.abc import Callable, Coroutine
import json
import logging
from typing import Any
from xml.etree import ElementTree as ET

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from bbaw_dse_mcp.config.base import settings
from bbaw_dse_mcp.utils.existdb import ExistDBClient

logger = logging.getLogger(__name__)

# Type alias for client getter
ClientGetter = Callable[[], Coroutine[Any, Any, ExistDBClient]]


def register_register_tools(
    mcp: FastMCP,
    get_client: ClientGetter,
) -> None:
    """Register register-related tools on the given MCP server.

    Args:
        mcp: The FastMCP server instance to register tools on
        get_client: Async function that returns an ExistDBClient
    """

    @mcp.tool
    async def search_register(
        query: str,
        register_type: str = "personen",
        max_results: int = 20,
        ctx: Context | None = None,
    ) -> list[dict]:
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
            Liste von Register-Einträgen mit id, name, type, gnd (optional)
        """
        if not query:
            raise ToolError("query ist erforderlich")

        valid_types = ["personen", "orte", "institutionen", "hoefe", "werke", "aemter"]
        if register_type not in valid_types:
            raise ToolError(f"register_type muss einer von {valid_types} sein")

        if ctx:
            await ctx.info(f"Searching MoP {register_type} for: {query}")

        client = await get_client()

        # Build XQuery with Lucene fulltext search
        # This will be more efficient than contains() for large datasets
        xquery = f"""
        xquery version "3.1";
        declare namespace tei="http://www.tei-c.org/ns/1.0";
        declare namespace ft="http://exist-db.org/xquery/lucene";

        let $collection := collection('{settings.ab_db_path}/Register/{register_type}')
        let $hits := $collection//*[@xml:id][ft:query(., '{query}')]
        let $results := array {{
            for $hit in subsequence($hits, 1, {max_results})
            let $score := ft:score($hit)
            order by $score descending
            return map {{
                "id": $hit/@xml:id/string(),
                "name": normalize-space(string-join($hit//text()[not(parent::tei:note)], ' ')),
                "type": "{register_type}",
                "gnd": $hit/@corresp/string()
            }}
        }}
        return serialize($results, map {{"method": "json"}})
        """

        try:
            result_json = await client.execute_xquery(xquery.strip(), how_many=1)
        except Exception as e:
            raise ToolError(f"Register-Suche fehlgeschlagen: {e}") from e

        # Parse JSON result
        try:
            results = json.loads(result_json)
        except json.JSONDecodeError:
            # Fallback for older eXist versions or issues
            results = []

        return results

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
            raise ToolError(f"Eintrag nicht gefunden: {e}") from e

        if not xml_str.strip():
            raise ToolError(f"Eintrag '{entry_id}' nicht gefunden")

        # Parse XML
        try:
            root = ET.fromstring(
                f"<root xmlns:tei='http://www.tei-c.org/ns/1.0'>{xml_str}</root>"
            )
        except ET.ParseError as e:
            raise ToolError(f"XML-Parse-Fehler: {e}") from e

        # Extract content
        text_content = ET.tostring(root, encoding="unicode", method="text").strip()

        # Extract GND if available
        gnd = root.find(".//*[@corresp]")
        gnd_id = gnd.get("corresp") if gnd is not None else None

        MAX_CONTENT_LENGTH = 1000
        MAX_XML_LENGTH = 2000

        return {
            "id": entry_id,
            "type": register_type,
            "content": (
                text_content[:MAX_CONTENT_LENGTH]
                if len(text_content) > MAX_CONTENT_LENGTH
                else text_content
            ),
            "gnd": gnd_id,
            "xml": (
                xml_str[:MAX_XML_LENGTH] if len(xml_str) > MAX_XML_LENGTH else xml_str
            ),
        }
