"""Search tools for correspSearch API.

This module provides tools for searching correspondence across multiple
editions via the correspSearch aggregation service.
"""

import logging
from typing import Protocol

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
import httpx

from bbaw_dse_mcp.schemas.correspsearch.correspsearch import (
    CorrespSearchResult,
    EditionInfo,
)
from bbaw_dse_mcp.servers.correspsearch.utils.api import (
    parse_edition_info,
)
from bbaw_dse_mcp.servers.correspsearch.utils.search import execute_correspsearch_query

logger = logging.getLogger(__name__)

# API v2.0 base URLs
API_V2_BASE = "https://correspsearch.net/api/v2.0"


class ClientGetter(Protocol):
    """Protocol for sync client getter function."""

    def __call__(self) -> httpx.AsyncClient: ...


def register_search_tools(
    mcp: FastMCP,
    get_client: ClientGetter,
) -> None:
    """Register correspSearch search tools on the given MCP server.

    Args:
        mcp: The FastMCP server instance to register tools on
        get_client: Function that returns an httpx.AsyncClient
    """

    @mcp.tool
    async def search_correspondences(
        person_gnd: str | list[str] | None = None,
        person_viaf: str | list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        place_geonames: str | None = None,
        occupation_wikidata: str | None = None,
        edition_id: str | None = None,
        cmif_url: str | None = None,
        availability: str | None = None,
        text_query: str | None = None,
        gender: str | None = None,
        role: str | None = None,
        place_role: str | None = None,
        page: int = 1,
        max_results: int = 100,
        ctx: Context | None = None,
    ) -> CorrespSearchResult:
        """Cross-Edition Briefsuche über correspSearch API.

        PURPOSE: Briefe über Edition-Grenzen hinweg finden

        WHEN TO USE:
        - User möchte Briefe in ALLEN Editionen finden
        - Cross-Referenzierung zwischen Editionen
        - Für umfassende Korrespondenz-Netzwerk-Analyse
        - Suche nach Korrespondenz einer historischen Person

        WHEN NOT TO USE:
        - Für schleiermacher-spezifische Suche → nutze sd_search_letters()

        Args:
            person_gnd: GND-ID(s) - einzelne ID oder Liste (z.B. "118540238" oder ["118540238", "118607626"])
            person_viaf: VIAF-ID(s) - einzelne ID oder Liste (alternativ zu GND)
            start_date: Start-Datum (ISO 8601, z.B. "1810-01-01")
            end_date: End-Datum (ISO 8601, z.B. "1815-12-31")
            place_geonames: GeoNames-ID eines Ortes (z.B. "2879139" für Leipzig)
            occupation_wikidata: Wikidata-ID eines Berufs (z.B. "Q36180" für Schriftsteller)
            edition_id: UUID einer Edition zur Filterung
            cmif_url: URL einer CMIF-Datei (z.B. "https://gams.uni-graz.at/context:hsa/CMIF")
            availability: "online", "print" oder "hybrid"
            text_query: Volltextsuche in Briefinhalten (experimentell, undokumentiert)
            gender: "male" (männlich), "female" (weiblich), oder "unknown" (unbekannt)
            role: "sent" (nur als Absender), "received" (nur als Empfänger), oder "mentioned" (nur erwähnt)
            place_role: "sent" (Schreibort) oder "received" (Empfangsort)
            page: Seite der Ergebnisse (1-indiziert, je 100 Treffer)
            max_results: Maximale Ergebnisse (zur Anzeige-Begrenzung)
            ctx: FastMCP Context

        Returns:
            CorrespSearchResult mit Briefen und Paginierungs-Info

        Note:
            Mehrere Personen (Liste) werden mit AND kombiniert - findet nur Briefe,
            die ALLE angegebenen Personen enthalten.
        """
        if not person_gnd and not person_viaf and not place_geonames:
            raise ToolError(
                "Mindestens person_gnd, person_viaf oder place_geonames erforderlich"
            )

        if ctx:
            search_info = person_gnd or person_viaf or place_geonames
            await ctx.info(f"Suche in correspSearch: {search_info}")

        result = await execute_correspsearch_query(
            client=get_client(),
            person_gnd=person_gnd,
            person_viaf=person_viaf,
            place_geonames=place_geonames,
            occupation_wikidata=occupation_wikidata,
            start_date=start_date,
            end_date=end_date,
            edition_id=edition_id,
            cmif_url=cmif_url,
            availability=availability,
            text_query=text_query,
            gender=gender,
            role=role,
            place_role=place_role,
            page=page,
            max_results=max_results,
        )

        if ctx:
            await ctx.info(
                f"Gefunden: {result.total_count} Briefe "
                f"(Seite {result.page}, zeige {len(result.letters)})"
            )

        return result

    @mcp.tool
    async def get_edition_info(
        edition_id: str,
        ctx: Context | None = None,
    ) -> EditionInfo:
        """Informationen über eine Edition in correspSearch abrufen.

        PURPOSE: Metadaten zu registrierten Editionen

        WHEN TO USE:
        - User fragt nach verfügbaren Editionen
        - Für Edition-Discovery
        - Um die Quelle von gefundenen Briefen zu identifizieren

        Args:
            edition_id: Edition-UUID in correspSearch
            ctx: FastMCP Context

        Returns:
            EditionInfo mit Metadaten zur Edition
        """
        if not edition_id:
            raise ToolError("edition_id ist erforderlich")

        if ctx:
            await ctx.info(f"Lade Edition-Info: {edition_id}")

        # Query the API with edition filter to get metadata
        params = {"e": edition_id, "x": "1"}

        try:
            client = get_client()
            response = await client.get(
                f"{API_V2_BASE}/tei-json.xql",
                params=params,
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise ToolError(f"Edition nicht gefunden: {e}") from e

        edition_info = parse_edition_info(response.json(), edition_id)

        if edition_info is None:
            raise ToolError(f"Konnte Edition-Metadaten nicht parsen: {edition_id}")

        return edition_info

    @mcp.tool
    async def search_correspondent_network(
        person_gnd: str,
        start_date: str | None = None,
        end_date: str | None = None,
        max_correspondents: int = 20,
        max_letters_to_analyze: int = 500,
        ctx: Context | None = None,
    ) -> dict:
        """Korrespondenz-Netzwerk einer Person analysieren.

        PURPOSE: Netzwerkanalyse von Korrespondenzen

        WHEN TO USE:
        - User fragt "Mit wem korrespondierte Person X?"
        - Netzwerk-Visualisierung vorbereiten
        - Wichtigste Korrespondenzpartner identifizieren

        Args:
            person_gnd: GND-ID der fokalen Person
            start_date: Optional: Start-Datum für Zeitfilter
            end_date: Optional: End-Datum für Zeitfilter
            max_correspondents: Maximale Anzahl Korrespondenten im Ergebnis
            max_letters_to_analyze: Maximale Anzahl Briefe zu analysieren (pro Richtung)
            ctx: FastMCP Context

        Returns:
            Dict mit Netzwerk-Statistiken und Top-Korrespondenten
        """
        if not person_gnd:
            raise ToolError("person_gnd ist erforderlich")

        if ctx:
            await ctx.info(f"Analysiere Korrespondenz-Netzwerk für: {person_gnd}")

        # Aggregate correspondent statistics
        correspondent_stats: dict[str, dict] = {}

        # Calculate pages needed (100 letters per page)
        pages_to_fetch = max(1, (max_letters_to_analyze + 99) // 100)

        # Fetch and process sent letters (person as sender)
        sent_total = 0
        sent_analyzed = 0
        for page in range(1, pages_to_fetch + 1):
            if ctx:
                await ctx.report_progress((page - 1) * 2, pages_to_fetch * 2)

            sent_result = await execute_correspsearch_query(
                client=get_client(),
                person_gnd=person_gnd,
                start_date=start_date,
                end_date=end_date,
                role="sent",
                page=page,
            )

            sent_total = sent_result.total_count

            # Process sent letters (count receivers)
            for letter in sent_result.letters:
                sent_analyzed += 1
                if letter.receiver and letter.receiver.authority_uri:
                    uri = letter.receiver.authority_uri
                    if uri not in correspondent_stats:
                        correspondent_stats[uri] = {
                            "name": letter.receiver.name,
                            "gnd": letter.receiver.gnd,
                            "authority_uri": uri,
                            "letters_received_from_person": 0,
                            "letters_sent_to_person": 0,
                        }
                    correspondent_stats[uri]["letters_sent_to_person"] += 1

            # Stop if we've seen all letters
            if (
                len(sent_result.letters) < 100
                or sent_analyzed >= max_letters_to_analyze
            ):
                break

        # Fetch and process received letters (person as receiver)
        received_total = 0
        received_analyzed = 0
        for page in range(1, pages_to_fetch + 1):
            if ctx:
                await ctx.report_progress(pages_to_fetch + page - 1, pages_to_fetch * 2)

            received_result = await execute_correspsearch_query(
                client=get_client(),
                person_gnd=person_gnd,
                start_date=start_date,
                end_date=end_date,
                role="received",
                page=page,
            )

            received_total = received_result.total_count

            # Process received letters (count senders)
            for letter in received_result.letters:
                received_analyzed += 1
                if letter.sender and letter.sender.authority_uri:
                    uri = letter.sender.authority_uri
                    if uri not in correspondent_stats:
                        correspondent_stats[uri] = {
                            "name": letter.sender.name,
                            "gnd": letter.sender.gnd,
                            "authority_uri": uri,
                            "letters_received_from_person": 0,
                            "letters_sent_to_person": 0,
                        }
                    correspondent_stats[uri]["letters_received_from_person"] += 1

            # Stop if we've seen all letters
            if (
                len(received_result.letters) < 100
                or received_analyzed >= max_letters_to_analyze
            ):
                break

        # Sort by total letters and take top N
        sorted_correspondents = sorted(
            correspondent_stats.values(),
            key=lambda x: x["letters_sent_to_person"]
            + x["letters_received_from_person"],
            reverse=True,
        )[:max_correspondents]

        # Add total to each correspondent
        for c in sorted_correspondents:
            c["total_letters"] = (
                c["letters_sent_to_person"] + c["letters_received_from_person"]
            )

        total_letters_analyzed = sent_analyzed + received_analyzed
        total_letters_in_corpus = sent_total + received_total

        if ctx:
            await ctx.info(
                f"Netzwerk: {len(correspondent_stats)} Korrespondenten, "
                f"{total_letters_analyzed} Briefe analysiert (von {total_letters_in_corpus} gesamt)"
            )

        return {
            "person_gnd": person_gnd,
            "total_letters_sent": sent_total,
            "total_letters_received": received_total,
            "total_letters_in_corpus": total_letters_in_corpus,
            "letters_sent_analyzed": sent_analyzed,
            "letters_received_analyzed": received_analyzed,
            "letters_analyzed": total_letters_analyzed,
            "unique_correspondents": len(correspondent_stats),
            "top_correspondents": sorted_correspondents,
            "date_range": (
                f"{start_date} - {end_date}" if start_date and end_date else "all time"
            ),
            "analysis_complete": total_letters_analyzed >= total_letters_in_corpus,
        }
