"""Biogramm tools for detailed biographical entries in MoP."""

import json
import logging
from collections.abc import Callable, Coroutine
from typing import Any
from xml.etree import ElementTree as ET

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from bbaw_dse_mcp.config.base import settings
from bbaw_dse_mcp.utils.existdb import ExistDBClient

# Namespace constants
NS = {"tei": "http://www.tei-c.org/ns/1.0"}

logger = logging.getLogger(__name__)

# Type alias for client getter
ClientGetter = Callable[[], Coroutine[Any, Any, ExistDBClient]]


def register_biogramm_tools(
    mcp: FastMCP,
    get_client: ClientGetter,
) -> None:
    """Register biogramm-related tools on the given MCP server.

    Args:
        mcp: The FastMCP server instance to register tools on
        get_client: Async function that returns an ExistDBClient
    """

    @mcp.tool
    async def search_biogramme(
        query: str,
        birth_year: int | None = None,
        death_year: int | None = None,
        max_results: int = 20,
        ctx: Context | None = None,
    ) -> list[dict]:
        """Suche in MoP-Biogrammen (detaillierte Biografien).

        PURPOSE: Detaillierte biografische Einträge finden

        WHEN TO USE:
        - User sucht nach Person für biografische Details
        - Um Familienverhältnisse, Karriere, Besitztümer zu recherchieren
        - Prosopographische Forschung zu Hofbeamten

        WHEN NOT TO USE:
        - Für einfache Registersuche → nutze search_register("personen")
        - Für Volltextsuche in Dokumenten → nutze search_documents()

        Args:
            query: Suchbegriff (Name)
            birth_year: Filter nach Geburtsjahr
            death_year: Filter nach Sterbejahr
            max_results: Maximale Ergebnisse
            ctx: FastMCP Context

        Returns:
            Liste von Biogramm-Treffern mit id, name, birth, death, gnd
        """
        if not query:
            raise ToolError("query ist erforderlich")

        if ctx:
            await ctx.info(f"Searching MoP biogramme for: {query}")

        client = await get_client()

        # Build XQuery for biogramm search
        birth_filter = (
            f"and contains(.//tei:div[@type='birth']//text(), '{birth_year}')"
            if birth_year
            else ""
        )
        death_filter = (
            f"and contains(.//tei:div[@type='death']//text(), '{death_year}')"
            if death_year
            else ""
        )

        xquery = f"""
        xquery version "3.1";
        declare namespace tei="http://www.tei-c.org/ns/1.0";
        declare namespace ft="http://exist-db.org/xquery/lucene";

        let $collection := collection('{settings.ab_db_path}/Biogramme')
        let $hits := $collection//tei:TEI[
            ft:query(.//tei:div[@type='name'], '{query}')
            {birth_filter}
            {death_filter}
        ]
        let $results := array {{
            for $hit in subsequence($hits, 1, {max_results})
            let $name := $hit//tei:div[@type='name']//tei:persName/normalize-space(.)
            let $birth := $hit//tei:div[@type='birth']/normalize-space(.)
            let $death := $hit//tei:div[@type='death']/normalize-space(.)
            let $gnd := $hit//tei:div[@type='gnd']/normalize-space(.)
            let $person-id := $hit//tei:div[@type='name']//tei:persName/@key/string()
            return map {{
                "id": $hit/@xml:id/string(),
                "person_id": $person-id,
                "name": $name,
                "birth": $birth,
                "death": $death,
                "gnd": $gnd
            }}
        }}
        return serialize($results, map {{ "method": "json" }})
        """

        try:
            result_json = await client.execute_xquery(xquery)
            results = json.loads(result_json)
            if ctx:
                await ctx.info(f"Found {len(results)} biogramme")
            return results
        except Exception as e:
            logger.error(f"Error searching biogramme: {e}")
            raise ToolError(f"Fehler bei Biogramm-Suche: {e}") from e

    @mcp.tool
    async def get_biogramm_by_id(
        biogramm_id: str,
        ctx: Context | None = None,
    ) -> dict:
        """Vollständiges Biogramm mit allen Details abrufen.

        PURPOSE: Detaillierte biografische Daten einer Person abrufen

        WHEN TO USE:
        - Nach search_biogramme() um Details zu bekommen
        - Um Familiennetzwerk, Karriere, Besitz zu analysieren
        - Für vollständige prosopographische Information

        Args:
            biogramm_id: XML-ID des Biogramms (z.B. "P0005251")
            ctx: FastMCP Context

        Returns:
            Dict mit allen biografischen Daten strukturiert
        """
        if not biogramm_id:
            raise ToolError("biogramm_id ist erforderlich")

        if ctx:
            await ctx.info(f"Retrieving biogramm: {biogramm_id}")

        client = await get_client()

        xquery = f"""
        xquery version "3.1";
        declare namespace tei="http://www.tei-c.org/ns/1.0";

        let $biogramm := collection('{settings.ab_db_path}/Biogramme')//tei:TEI[@xml:id='{biogramm_id}']
        return
            if (exists($biogramm))
            then serialize($biogramm, map {{ "method": "xml", "indent": true() }})
            else ""
        """

        try:
            xml_result = await client.execute_xquery(xquery)
            if not xml_result or xml_result.strip() == "":
                raise ToolError(f"Biogramm {biogramm_id} nicht gefunden")

            # Parse XML and extract structured data
            root = ET.fromstring(xml_result)

            # Helper function to extract div content
            def get_div_text(div_type: str) -> str:
                """Extract text content from a div by type."""
                div = root.find(f".//tei:div[@type='{div_type}']", NS)
                if div is not None:
                    return ET.tostring(div, encoding="unicode", method="text").strip()
                return ""

            def get_div_list(div_type: str) -> list[str]:
                """Extract list items from a div by type."""
                div = root.find(f".//tei:div[@type='{div_type}']", NS)
                if div is not None:
                    items = div.findall(".//tei:item", NS)
                    return [
                        ET.tostring(item, encoding="unicode", method="text").strip()
                        for item in items
                        if item.text and item.text.strip()
                    ]
                return []

            # Extract family relations
            relatives_div = root.find(".//tei:div[@type='relatives']", NS)
            family_relations = []
            if relatives_div is not None:
                for relation in relatives_div.findall(".//tei:relation", NS):
                    rel_type = relation.get("name", "unknown")
                    desc_elem = relation.find(".//tei:desc", NS)
                    desc = (
                        ET.tostring(
                            desc_elem, encoding="unicode", method="text"
                        ).strip()
                        if desc_elem is not None
                        else ""
                    )
                    if desc:
                        family_relations.append(
                            {"relation": rel_type, "description": desc}
                        )

            # Extract properties
            property_list = get_div_list("property")

            biogramm_data = {
                "id": biogramm_id,
                "title": (
                    root.find(".//tei:titleStmt/tei:title", NS).text
                    if root.find(".//tei:titleStmt/tei:title", NS) is not None
                    and root.find(".//tei:titleStmt/tei:title", NS).text is not None
                    else ""
                ),
                "name": get_div_text("name"),
                "gender": get_div_text("gender"),
                "birth": get_div_text("birth"),
                "death": get_div_text("death"),
                "confession": get_div_text("confession"),
                "property": property_list,
                "family_relations": family_relations,
                "court_offices": get_div_list("court-office"),
                "education": get_div_list("education"),
                "military": get_div_list("military"),
                "awards": get_div_list("awards"),
                "notes": get_div_list("notes"),
                "gnd": get_div_text("gnd"),
            }

            if ctx:
                await ctx.info(
                    f"Retrieved biogramm for {biogramm_data.get('name', 'unknown')}"
                )

            return biogramm_data

        except ET.ParseError as e:
            logger.error(f"Error parsing biogramm XML: {e}")
            raise ToolError(f"Fehler beim Parsen des Biogramms: {e}") from e
        except Exception as e:
            logger.error(f"Error retrieving biogramm: {e}")
            raise ToolError(f"Fehler beim Abrufen des Biogramms: {e}") from e

    async def _get_biogramm_internal(biogramm_id: str) -> dict:
        """Internal helper to get biogramm data without tool wrapper."""
        client = await get_client()

        xquery = f"""
        xquery version "3.1";
        declare namespace tei="http://www.tei-c.org/ns/1.0";

        let $biogramm := collection('{settings.ab_db_path}/Biogramme')//tei:TEI[@xml:id='{biogramm_id}']
        return
            if (exists($biogramm))
            then serialize($biogramm, map {{ "method": "xml", "indent": true() }})
            else ""
        """

        xml_result = await client.execute_xquery(xquery)
        if not xml_result or xml_result.strip() == "":
            raise ToolError(f"Biogramm {biogramm_id} nicht gefunden")

        # Parse XML and extract structured data
        root = ET.fromstring(xml_result)  # noqa: S314

        # Helper function to extract div content
        def get_div_text(div_type: str) -> str:
            """Extract text content from a div by type."""
            div = root.find(f".//tei:div[@type='{div_type}']", NS)
            if div is not None:
                return ET.tostring(div, encoding="unicode", method="text").strip()
            return ""

        # Extract family relations
        relatives_div = root.find(".//tei:div[@type='relatives']", NS)
        family_relations = []
        if relatives_div is not None:
            for relation in relatives_div.findall(".//tei:relation", NS):
                rel_type = relation.get("name", "unknown")
                desc_elem = relation.find(".//tei:desc", NS)
                desc = (
                    ET.tostring(desc_elem, encoding="unicode", method="text").strip()
                    if desc_elem is not None
                    else ""
                )
                if desc:
                    family_relations.append({"relation": rel_type, "description": desc})

        return {
            "name": get_div_text("name"),
            "family_relations": family_relations,
        }

    @mcp.tool
    async def extract_family_network(
        biogramm_id: str,
        ctx: Context | None = None,
    ) -> dict:
        """Familiennetzwerk aus einem Biogramm extrahieren.

        PURPOSE: Verwandtschaftsbeziehungen analysieren

        WHEN TO USE:
        - Für genealogische Forschung
        - Um höfische Netzwerke zu rekonstruieren
        - Analyse von Familiendynastien am Hof

        Args:
            biogramm_id: XML-ID des Biogramms
            ctx: FastMCP Context

        Returns:
            Dict mit Familienrelationen strukturiert nach Typ
        """
        if not biogramm_id:
            raise ToolError("biogramm_id ist erforderlich")

        if ctx:
            await ctx.info(f"Extracting family network for: {biogramm_id}")

        # Get biogramm data
        biogramm_data = await _get_biogramm_internal(biogramm_id)

        # Organize relations by type
        family_network = {
            "person": biogramm_data.get("name", ""),
            "parents": [],
            "siblings": [],
            "spouse": [],
            "children": [],
            "other_relations": [],
        }

        for relation in biogramm_data.get("family_relations", []):
            rel_type = relation["relation"]
            desc = relation["description"]

            if rel_type in ["father", "mother"]:
                family_network["parents"].append(desc)
            elif rel_type in ["brother", "sister"]:
                family_network["siblings"].append(desc)
            elif rel_type in ["wife", "husband", "spouse"]:
                family_network["spouse"].append(desc)
            elif rel_type in ["son", "daughter", "child"]:
                family_network["children"].append(desc)
            else:
                family_network["other_relations"].append(
                    {"type": rel_type, "description": desc}
                )

        if ctx:
            total_relations = sum(
                len(v) if isinstance(v, list) else 0 for v in family_network.values()
            )
            await ctx.info(f"Found {total_relations} family relations")

        return family_network
