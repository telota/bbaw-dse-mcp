"""Adjutantenjournale tools for MoP - court adjutant journals.

Provides tools to search and retrieve daily court journal entries from Prussian kings
(Friedrich Wilhelm IV, Wilhelm I, Wilhelm II, Friedrich III). These journals document
daily activities, audiences, meetings, and events at court.

Available monarchs:
- Friedrich_Wilhelm_IV (1840-1861)
- Wilhelm_I (1861-1888)
- Wilhelm_II (1888-1918)
- Friedrich_III (1888)
"""

from collections.abc import Callable, Coroutine
from typing import Any
from xml.etree import ElementTree as ET

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from bbaw_dse_mcp.utils.existdb import ExistDBClient

# Type alias for client getter
ClientGetter = Callable[[], Coroutine[Any, Any, ExistDBClient]]

# Available monarchs
AVAILABLE_MONARCHS = [
    "Friedrich_Wilhelm_IV",
    "Wilhelm_I",
    "Wilhelm_II",
    "Friedrich_III",
]

# TEI namespace
NS = {"tei": "http://www.tei-c.org/ns/1.0"}


def register_adjutanten_tools(
    mcp: FastMCP,
    get_client: ClientGetter,
) -> None:
    """Register Adjutantenjournale tools on the given MCP server.

    Args:
        mcp: The FastMCP server instance to register tools on
        get_client: Async function that returns an eXist-db client
    """

    @mcp.tool
    async def search_adjutanten_journals(
        query: str | None = None,
        monarch: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        person_key: str | None = None,
        place_key: str | None = None,
        limit: int = 50,
        ctx: Context | None = None,
    ) -> list[dict[str, Any]]:
        """Search in Adjutantenjournale (court adjutant journals).

        PURPOSE: Find daily court journal entries documenting royal activities, audiences,
                 meetings, and events. Each entry shows who was on duty and what happened.

        WHEN TO USE:
        - User asks "What did the king do on [date]?"
        - User wants to know about daily court life
        - User searches for specific events, persons, or places mentioned in journals
        - User wants to track activities of a specific monarch
        - User researches who served as adjutant when

        WHEN NOT TO USE:
        - For biographical data → use search_register()
        - For correspondence → use letters search in Schleiermacher Digital
        - For institutional documents → use browse_documents()

        Args:
            query: Full-text search term (searches in journal text)
            monarch: Filter by monarch (Friedrich_Wilhelm_IV, Wilhelm_I, Wilhelm_II, Friedrich_III)
            date_from: Start date in ISO format (YYYY-MM-DD), e.g., "1861-01-01"
            date_to: End date in ISO format (YYYY-MM-DD), e.g., "1861-12-31"
            person_key: Filter by person mentioned (register key, e.g., "P0002157")
            place_key: Filter by place mentioned (register key, e.g., "P0003556")
            limit: Maximum number of results (default: 50)
            ctx: FastMCP Context for progress reporting

        Returns:
            List of journal entries with:
            - id: Document ID
            - monarch: Which monarch's reign
            - date_from/date_to: Time range covered
            - place: Where the court was located
            - authors: Adjutants who wrote the entry
            - snippet: Text excerpt showing matched content
            - url: Link to full entry on website

        Raises:
            ToolError: If monarch is invalid or query fails
        """
        if monarch and monarch not in AVAILABLE_MONARCHS:
            raise ToolError(
                f"Invalid monarch '{monarch}'. Available: {', '.join(AVAILABLE_MONARCHS)}"
            )

        if ctx:
            await ctx.info("Searching Adjutantenjournale...")

        client = await get_client()

        # Build XQuery
        conditions = []

        # Path filter by monarch
        if monarch:
            path = f"'/db/projects/mop/data/Adjutantenjournale/{monarch}'"
        else:
            path = "'/db/projects/mop/data/Adjutantenjournale'"

        # Full-text query
        if query:
            conditions.append(f".[ft:query(., '{query}')]")

        # Date range filter
        date_conditions = []
        if date_from:
            date_conditions.append(f"@to >= '{date_from}'")
        if date_to:
            date_conditions.append(f"@from <= '{date_to}'")
        if date_conditions:
            conditions.append(
                f".//tei:creation/tei:date[{' and '.join(date_conditions)}]"
            )

        # Person filter
        if person_key:
            conditions.append(f".//tei:persName[@key='{person_key}']")

        # Place filter
        if place_key:
            conditions.append(f".//tei:placeName[@key='{place_key}']")

        # Combine conditions
        filter_expr = "".join(f"[{cond}]" for cond in conditions) if conditions else ""

        xquery = f"""
        declare namespace tei="http://www.tei-c.org/ns/1.0";

        for $doc in collection({path})//tei:TEI{filter_expr}
        let $date_from := $doc//tei:creation/tei:date/@from
        let $date_to := $doc//tei:creation/tei:date/@to
        let $id := $doc/@xml:id
        order by $date_from
        return $doc
        """

        try:
            result_xml = await client.execute_xquery(xquery)
            root = ET.fromstring(f"<results>{result_xml}</results>")

            results = []
            for doc in root.findall(".//tei:TEI", NS)[:limit]:
                doc_id = doc.get("{http://www.w3.org/XML/1998/namespace}id", "unknown")

                # Extract metadata
                date_elem = doc.find(".//tei:creation/tei:date", NS)
                date_from_val = date_elem.get("from") if date_elem is not None else None
                date_to_val = date_elem.get("to") if date_elem is not None else None

                # Determine monarch from path/ID
                monarch_val = None
                if monarch:
                    monarch_val = monarch
                else:
                    # Try to determine from document structure
                    for m in AVAILABLE_MONARCHS:
                        if doc_id and m.lower() in doc_id.lower():
                            monarch_val = m
                            break

                # Extract place (first dateline place)
                place_elem = doc.find(".//tei:dateline/tei:placeName", NS)
                place = place_elem.text if place_elem is not None else None
                place_key_val = (
                    place_elem.get("key") if place_elem is not None else None
                )

                # Extract authors (adjutants on duty)
                authors = []
                for author_elem in doc.findall(
                    ".//tei:ab[@type='author']/tei:persName", NS
                ):
                    author_name = author_elem.text or ""
                    authors.append(author_name.strip())

                # Extract snippet
                snippet_parts = []
                for p in doc.findall(".//tei:div[@type='journalText']//tei:p", NS)[:2]:
                    text = "".join(p.itertext()).strip()
                    if text:
                        snippet_parts.append(
                            text[:200] + "..." if len(text) > 200 else text
                        )
                snippet = " | ".join(snippet_parts)

                results.append(
                    {
                        "id": doc_id,
                        "monarch": monarch_val,
                        "date_from": date_from_val,
                        "date_to": date_to_val,
                        "place": place,
                        "place_key": place_key_val,
                        "authors": authors,
                        "snippet": snippet,
                        "url": f"https://actaborussica.bbaw.de/v.01/editiondetail/{doc_id}",
                    }
                )

            if ctx:
                await ctx.info(f"Found {len(results)} journal entries")

            return results

        except ET.ParseError as e:
            raise ToolError(f"Failed to parse XML results: {e}") from e
        except Exception as e:
            raise ToolError(f"Search failed: {e}") from e

    @mcp.tool
    async def get_adjutanten_journal_entry(
        document_id: str,
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """Retrieve full text and metadata of a specific journal entry.

        PURPOSE: Get complete details of a daily court journal entry.

        WHEN TO USE:
        - After finding entries with search_adjutanten_journals()
        - User wants to read the full journal entry for a specific day
        - User needs detailed information about activities on a specific date

        WHEN NOT TO USE:
        - For searching multiple entries → use search_adjutanten_journals()
        - For biographical data → use get_register_entry()

        Args:
            document_id: Document ID from search results (e.g., "P0005285")
            ctx: FastMCP Context for progress reporting

        Returns:
            Dict with:
            - id: Document ID
            - monarch: Which monarch's reign
            - date_from/date_to: Time range covered
            - shelfmark: Archive reference
            - days: List of daily entries, each with:
                - date: ISO date
                - place: Location
                - authors: Adjutants on duty
                - text: Full journal text for that day
            - url: Link to online edition

        Raises:
            ToolError: If document not found or retrieval fails
        """
        if ctx:
            await ctx.info(f"Retrieving journal entry {document_id}...")

        client = await get_client()

        xquery = f"""
        declare namespace tei="http://www.tei-c.org/ns/1.0";

        collection('/db/projects/mop/data/Adjutantenjournale')//tei:TEI[@xml:id='{document_id}']
        """

        try:
            result_xml = await client.execute_xquery(xquery)
            root = ET.fromstring(f"<results>{result_xml}</results>")

            doc = root.find(".//tei:TEI", NS)
            if doc is None:
                raise ToolError(f"Journal entry '{document_id}' not found")

            # Extract metadata
            date_elem = doc.find(".//tei:creation/tei:date", NS)
            date_from = date_elem.get("from") if date_elem is not None else None
            date_to = date_elem.get("to") if date_elem is not None else None

            shelfmark_elem = doc.find(
                ".//tei:msIdentifier/tei:idno/tei:idno[@type='shelfmark']", NS
            )
            shelfmark = shelfmark_elem.text if shelfmark_elem is not None else None

            # Determine monarch
            monarch_val = None
            for m in AVAILABLE_MONARCHS:
                if document_id and m.lower() in document_id.lower():
                    monarch_val = m
                    break

            # Extract daily entries
            days = []
            for day_div in doc.findall(".//tei:div[@type='tag']", NS):
                dateline = day_div.find(".//tei:dateline", NS)
                if dateline is None:
                    continue

                date_elem = dateline.find(".//tei:date", NS)
                day_date = date_elem.get("when") if date_elem is not None else None

                place_elem = dateline.find(".//tei:placeName", NS)
                day_place = place_elem.text if place_elem is not None else None

                # Extract authors and text by writing session
                sessions = []
                for session in day_div.findall(
                    ".//tei:div[@type='writingSession']", NS
                ):
                    author_elem = session.find(
                        ".//tei:ab[@type='author']/tei:persName", NS
                    )
                    author = author_elem.text if author_elem is not None else "Unknown"

                    # Get all paragraph text
                    paragraphs = []
                    for p in session.findall(".//tei:p", NS):
                        text = "".join(p.itertext()).strip()
                        if text:
                            paragraphs.append(text)

                    sessions.append(
                        {"author": author.strip(), "text": "\n\n".join(paragraphs)}
                    )

                days.append(
                    {"date": day_date, "place": day_place, "sessions": sessions}
                )

            result = {
                "id": document_id,
                "monarch": monarch_val,
                "date_from": date_from,
                "date_to": date_to,
                "shelfmark": shelfmark,
                "days": days,
                "url": f"https://actaborussica.bbaw.de/v.01/editiondetail/{document_id}",
            }

            if ctx:
                await ctx.info(f"Retrieved journal with {len(days)} daily entries")

            return result

        except ET.ParseError as e:
            raise ToolError(f"Failed to parse document: {e}") from e
        except Exception as e:
            raise ToolError(f"Retrieval failed: {e}") from e

    @mcp.tool
    async def list_adjutanten_by_monarch(
        monarch: str,
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """List all adjutants who served under a specific monarch.

        PURPOSE: Identify who served as adjutant and when.

        WHEN TO USE:
        - User asks "Who served as adjutant under Wilhelm I?"
        - User wants to know the rotation of adjutants
        - User researches prosopography of court officials

        WHEN NOT TO USE:
        - For full biographical data → use search_register()
        - For journal content → use search_adjutanten_journals()

        Args:
            monarch: Monarch name (Friedrich_Wilhelm_IV, Wilhelm_I, Wilhelm_II, Friedrich_III)
            ctx: FastMCP Context for progress reporting

        Returns:
            Dict with:
            - monarch: Monarch name
            - total_entries: Number of journal entries analyzed
            - adjutants: List of adjutants with:
                - name: Full name
                - person_key: Register ID
                - entries_count: How many times they wrote entries
                - date_range: First and last appearance

        Raises:
            ToolError: If monarch is invalid or query fails
        """
        if monarch not in AVAILABLE_MONARCHS:
            raise ToolError(
                f"Invalid monarch '{monarch}'. Available: {', '.join(AVAILABLE_MONARCHS)}"
            )

        if ctx:
            await ctx.info(f"Analyzing adjutants for {monarch}...")

        client = await get_client()

        xquery = f"""
        declare namespace tei="http://www.tei-c.org/ns/1.0";

        for $author in distinct-values(
            collection('/db/projects/mop/data/Adjutantenjournale/{monarch}')
            //tei:ab[@type='author']/tei:persName/@key
        )
        let $name := collection('/db/projects/mop/data/Adjutantenjournale/{monarch}')
            //tei:ab[@type='author']/tei:persName[@key=$author][1]/text()
        let $entries := collection('/db/projects/mop/data/Adjutantenjournale/{monarch}')
            //tei:ab[@type='author']/tei:persName[@key=$author]
        let $dates := for $entry in $entries
            return $entry/ancestor::tei:div[@type='tag']//tei:dateline/tei:date/@when
        let $min_date := min($dates)
        let $max_date := max($dates)
        order by $name
        return <adjutant key="{{$author}}" name="{{$name}}" count="{{count($entries)}}"
                         min_date="{{$min_date}}" max_date="{{$max_date}}"/>
        """

        try:
            result_xml = await client.execute_xquery(xquery)
            root = ET.fromstring(f"<results>{result_xml}</results>")

            adjutants = []
            for adj in root.findall(".//adjutant"):
                adjutants.append(
                    {
                        "name": adj.get("name"),
                        "person_key": adj.get("key"),
                        "entries_count": int(adj.get("count", 0)),
                        "date_range": {
                            "first": adj.get("min_date"),
                            "last": adj.get("max_date"),
                        },
                    }
                )

            # Get total entries count
            count_query = f"""
            declare namespace tei="http://www.tei-c.org/ns/1.0";
            count(collection('/db/projects/mop/data/Adjutantenjournale/{monarch}')//tei:TEI)
            """
            total = await client.execute_xquery(count_query)

            result = {
                "monarch": monarch,
                "total_entries": int(total.strip()) if total.strip().isdigit() else 0,
                "adjutants": adjutants,
                "count": len(adjutants),
            }

            if ctx:
                await ctx.info(f"Found {len(adjutants)} adjutants")

            return result

        except ET.ParseError as e:
            raise ToolError(f"Failed to parse results: {e}") from e
        except Exception as e:
            raise ToolError(f"Query failed: {e}") from e
