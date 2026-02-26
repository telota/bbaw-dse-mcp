"""
Search and filter tools for Schleiermacher Digital.

This module provides tools for searching documents, filtering letters,
and analyzing correspondence patterns in the Schleiermacher edition.
"""

from collections.abc import Awaitable
import re
from typing import Protocol
from xml.etree import ElementTree as ET

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from bbaw_dse_mcp.config.base import settings
from bbaw_dse_mcp.schemas.base.documents import Letter, Passage
from bbaw_dse_mcp.schemas.base.responses import SearchResult
from bbaw_dse_mcp.servers.schleiermacher.utils.citations import (
    get_schleiermacher_citation_url,
)
from bbaw_dse_mcp.utils.existdb import ExistDBClient

# Constant for minimum parts in split operation
MIN_PARTS_FOR_STATS = 2

# Valid document types in the Schleiermacher Digital index
# Based on actual facet values from eXist-db
# Note: Most types have " fs" suffix in the index
VALID_DOC_TYPES = {
    "letter",  # Base type
    "letter fs",  # 8071 documents (main letter type)
    "lecture",  # Base type
    "lecture fs",  # 143 documents (main lecture type)
    "chronology",  # 61 documents
    "intro",  # 42 documents
    "chronology-intro",  # 29 documents
    "diary",  # Base type
    "diary fs",  # 21 documents (main diary type)
}


def parse_kwic_xml(kwic_xml: str) -> list[str]:
    """Extract plain text snippets from KWIC XML.

    Args:
        kwic_xml: XML string with KWIC results

    Returns:
        List of formatted snippet strings
    """
    if not kwic_xml or not kwic_xml.strip():
        return []

    snippets = []
    try:
        # If not wrapped, wrap in root
        if not kwic_xml.strip().startswith("<root"):
            kwic_xml = f"<root>{kwic_xml}</root>"

        root = ET.fromstring(kwic_xml)

        # Find all <p> elements (namespace-aware via universal namespace pattern)
        for p_elem in root.iter():
            # Check if it's a p element (regardless of namespace)
            if p_elem.tag.endswith("}p") or p_elem.tag == "p":
                # Build text with highlighting
                text_parts = []

                # Process all spans
                for span in p_elem.iter():
                    if span.tag.endswith("}span") or span.tag == "span":
                        # Check if it's a highlight span
                        span_class = span.get("class", "")
                        span_text = "".join(span.itertext())

                        if span_class == "hi":
                            text_parts.append(f"**{span_text}**")
                        else:
                            text_parts.append(span_text)

                snippet = "".join(text_parts)
                # Normalize whitespace
                snippet = " ".join(snippet.split())
                if snippet:
                    snippets.append(snippet)

    except Exception as e:
        # Fallback: just strip all tags with regex
        # Log the error but continue with fallback
        clean = re.sub(r"<[^>]+>", " ", kwic_xml)
        clean = " ".join(clean.split())
        if clean:
            snippets.append(f"[XML parse warning: {e}] {clean}")

    return snippets


def parse_passage_xml(xml_result: str) -> list[Passage]:
    """Parse passage XML results into Passage objects.

    Args:
        xml_result: XML string with passage results

    Returns:
        List of Passage objects
    """
    passages = []
    try:
        # Wrap in root element if not already wrapped
        if not xml_result.strip().startswith("<root>"):
            xml_result = f"<root>{xml_result}</root>"

        root = ET.fromstring(xml_result)
        for passage_elem in root.findall(".//passage"):
            position_elem = passage_elem.find("position")
            text_elem = passage_elem.find("text")
            div_elem = passage_elem.find("div_n")
            page_elem = passage_elem.find("page_n")
            para_num_elem = passage_elem.find("para_num")

            if position_elem is not None and text_elem is not None:
                # Parse KWIC if present - get XML content of text element
                text_content = ""

                # Check if text has child elements (KWIC XML)
                if len(text_elem) > 0:
                    # Has child elements - extract as XML string and parse KWIC
                    text_xml = ET.tostring(text_elem, encoding="unicode", method="xml")
                    kwic_snippets = parse_kwic_xml(text_xml)
                    text_content = " ... ".join(kwic_snippets) if kwic_snippets else ""

                # If no content yet, try direct text
                if not text_content and text_elem.text:
                    text_content = text_elem.text

                # Still no content? Try itertext as fallback
                if not text_content:
                    all_text = "".join(text_elem.itertext()).strip()
                    if all_text:
                        text_content = all_text

                passages.append(
                    Passage(
                        position=int(position_elem.text or 0),
                        text=text_content,
                        div_n=(
                            div_elem.text
                            if div_elem is not None and div_elem.text
                            else None
                        ),
                        page_n=(
                            page_elem.text
                            if page_elem is not None and page_elem.text
                            else None
                        ),
                        para_num=(
                            int(para_num_elem.text)
                            if para_num_elem is not None and para_num_elem.text
                            else None
                        ),
                    )
                )
    except Exception as e:
        # Raise error with XML preview for debugging
        xml_preview = xml_result[:500] if len(xml_result) > 500 else xml_result
        raise ToolError(
            f"Failed to parse passage XML: {e}. XML preview: {xml_preview}"
        ) from e

    return passages


def _parse_search_results(xml_result: str) -> list[SearchResult]:
    """Parse search result XML into SearchResult objects.

    Args:
        xml_result: Raw XML string from eXist-db query

    Returns:
        List of SearchResult objects
    """
    results = []
    try:
        xml_wrapped = f"<root>{xml_result}</root>"
        root = ET.fromstring(xml_wrapped)

        for result_elem in root.findall(".//result"):
            doc_id = result_elem.findtext("id", "")
            title = result_elem.findtext("title", "")
            doc_type = result_elem.findtext("type")
            year = result_elem.findtext("year")
            date = result_elem.findtext("date")
            score_text = result_elem.findtext("score")
            snippets_elem = result_elem.find("snippets")

            # Parse KWIC snippets
            kwic_snippets = None
            if snippets_elem is not None:
                snippets_xml = ET.tostring(snippets_elem, encoding="unicode")
                kwic_snippets = parse_kwic_xml(snippets_xml)

            # Use date if available, otherwise use year
            result_date = date if date else year

            results.append(
                SearchResult(
                    document_id=doc_id,
                    title=title,
                    type=doc_type if doc_type else None,
                    date=result_date if result_date else None,
                    kwic_snippets=kwic_snippets if kwic_snippets else None,
                    score=float(score_text) if score_text else None,
                    citation_url=get_schleiermacher_citation_url(doc_id, doc_type),
                )
            )
    except ET.ParseError as e:
        # Log parse error with XML snippet for debugging
        xml_preview = xml_result[:500] if len(xml_result) > 500 else xml_result
        raise ToolError(
            f"Failed to parse search results XML: {e}. XML preview: {xml_preview}"
        ) from e

    return results


class ClientGetter(Protocol):
    """Protocol for async client getter function."""

    def __call__(self) -> Awaitable[ExistDBClient]: ...


class CacheGetter(Protocol):
    """Protocol for async cache getter function."""

    def __call__(self) -> Awaitable[list[dict]]: ...


def register_search_tools(  # noqa: C901, PLR0915
    mcp: FastMCP,
    get_client: ClientGetter,
    get_letter_cache: CacheGetter,
) -> None:
    """Register search and filter tools on the given MCP server.

    Args:
        mcp: The FastMCP server instance to register tools on
        get_client: Async function that returns an ExistDBClient
        get_letter_cache: Async function that returns letter cache
    """

    @mcp.tool
    async def search_documents(
        query: str,
        doc_types: list[str] | None = None,
        years: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        *,
        include_commentary: bool = True,
        use_or_logic: bool = True,
        limit: int = 50,
        ctx: Context | None = None,
    ) -> list[SearchResult]:
        """Search documents in Schleiermacher Digital via eXist-db with facets.

        PURPOSE: Primary search tool for finding documents by text, type, year, etc.

        WHEN TO USE:
        - Full-text search in documents
        - Filter by document type (letter, diary, lecture, etc.)
        - Filter by year or date range
        - Any search query for document discovery

        WHEN NOT TO USE:
        - For structured letter filtering by sender/receiver → use filter_letters()
        - For register search (persons, places) → use search_register()
        - For detailed text passages → use get_document_passages()

        ⚠️ CITATION WARNING:
        Only cite documents returned by this tool. Each result includes:
        - document_id: Use this EXACT value for citations
        - citation_url: Use this EXACT URL, do not construct your own
        NEVER invent document IDs or URLs that were not returned in the results.

        Valid doc_types (from index):
        - "letter" or "letter fs" (8071 documents)
        - "lecture" or "lecture fs" (143 documents)
        - "chronology" (61 documents)
        - "intro" (42 documents)
        - "chronology-intro" (29 documents)
        - "diary" or "diary fs" (21 documents)

        Args:
            query: Search terms (space-separated for multiple terms)
            doc_types: Filter by document types (letter, letter fs, diary, diary fs, lecture, lecture fs, chronology, intro)
            years: Filter by years (e.g., ["1810", "1811"])
            date_from: Earliest date (ISO 8601, e.g., "1810-01-01")
            date_to: Latest date (ISO 8601, e.g., "1815-12-31")
            include_commentary: If True, search in commentary too (default: True)
            use_or_logic: If True, use OR between terms (default); if False, use AND
            limit: Maximum results (default: 50)
            ctx: FastMCP Context

        Returns:
            List of SearchResult objects with document_id, title, type, date, kwic_snippets, and citation_url
        """
        if not query or not query.strip():
            raise ToolError("query is required")

        if ctx:
            await ctx.info(f"Searching for: {query}")

        # Validate doc_types if provided
        if doc_types:
            invalid_types = [dt for dt in doc_types if dt not in VALID_DOC_TYPES]
            if invalid_types:
                valid_list = ", ".join(sorted(VALID_DOC_TYPES))
                raise ToolError(
                    f"Invalid doc_types: {invalid_types}. Valid types: {valid_list}"
                )

        client = await get_client()

        # Build Lucene query with proper OR/AND logic
        terms = query.strip().split()
        if len(terms) > 1:
            operator = " OR " if use_or_logic else " AND "
            lucene_query = "(" + operator.join(terms) + ")"
        else:
            lucene_query = terms[0]

        # Choose fulltext field based on include_commentary
        if include_commentary:
            full_query = (
                f"(fulltext-main:{lucene_query} OR fulltext-commentary:{lucene_query})"
            )
        else:
            full_query = f"fulltext-main:{lucene_query}"

        if ctx:
            await ctx.info(f"Lucene query: {full_query}")

        # Build facet filters for doc-type and year (faster than query filters)
        facet_conditions = []
        if doc_types:
            doc_type_facets = ", ".join([f'"{dt}"' for dt in doc_types])
            facet_conditions.append(f'"doc-type": ({doc_type_facets})')
        if years:
            year_facets = ", ".join([f'"{y}"' for y in years])
            facet_conditions.append(f'"year": ({year_facets})')

        facet_map = ""
        if facet_conditions:
            facet_map = f', "facets": map {{ {", ".join(facet_conditions)} }}'

        # Build date range filter in XQuery if specified
        date_filter = ""
        if date_from or date_to:
            date_conditions = []
            if date_from:
                date_conditions.append(f"$date >= '{date_from}'")
            if date_to:
                date_conditions.append(f"$date <= '{date_to}'")
            date_filter = " and ".join(date_conditions)

        # Execute search via eXist-db with KWIC and facets
        # Optimization: Limit before sorting to avoid sorting all results
        if date_filter:
            xquery = f"""
            xquery version "3.1";
            declare namespace tei="http://www.tei-c.org/ns/1.0";
            declare namespace ft="http://exist-db.org/xquery/lucene";
            import module namespace kwic="http://exist-db.org/xquery/kwic";

            let $options := map {{
                "fields": ("id", "title", "doc-type", "year", "date"){facet_map}
            }}
            let $hits := collection('{settings.sd_data_path}')//tei:TEI[ft:query(., '{full_query}', $options)]

            (: Filter by date, sort by score, limit results :)
            let $filtered := for $h in $hits
                let $date := ft:field($h, 'date')
                where {date_filter}
                order by ft:score($h) descending
                return $h

            (: Only process KWIC for limited results :)
            for $hit in subsequence($filtered, 1, {limit})
            let $score := ft:score($hit)
            let $kwic := kwic:summarize($hit, <config width="120" table="no"/>)
            return
                <result>
                    <id>{{ft:field($hit, 'id')}}</id>
                    <title>{{ft:field($hit, 'title')}}</title>
                    <type>{{ft:field($hit, 'doc-type')}}</type>
                    <year>{{ft:field($hit, 'year')}}</year>
                    <date>{{ft:field($hit, 'date')}}</date>
                    <score>{{$score}}</score>
                    <snippets>{{$kwic}}</snippets>
                </result>
            """
        else:
            xquery = f"""
            xquery version "3.1";
            declare namespace tei="http://www.tei-c.org/ns/1.0";
            declare namespace ft="http://exist-db.org/xquery/lucene";
            import module namespace kwic="http://exist-db.org/xquery/kwic";

            let $options := map {{
                "fields": ("id", "title", "doc-type", "year", "date"){facet_map}
            }}
            let $hits := collection('{settings.sd_data_path}')//tei:TEI[ft:query(., '{full_query}', $options)]

            (: Sort by score and limit :)
            let $sorted := for $h in $hits
                order by ft:score($h) descending
                return $h

            (: Only process KWIC for limited results :)
            for $hit in subsequence($sorted, 1, {limit})
            let $score := ft:score($hit)
            let $kwic := kwic:summarize($hit, <config width="120" table="no"/>)
            return
                <result>
                    <id>{{ft:field($hit, 'id')}}</id>
                    <title>{{ft:field($hit, 'title')}}</title>
                    <type>{{ft:field($hit, 'doc-type')}}</type>
                    <year>{{ft:field($hit, 'year')}}</year>
                    <date>{{ft:field($hit, 'date')}}</date>
                    <score>{{$score}}</score>
                    <snippets>{{$kwic}}</snippets>
                </result>
            """

        try:
            result = await client.execute_xquery(xquery.strip(), how_many=limit)
        except Exception as e:
            raise ToolError(f"Search failed: {e}") from e

        # Parse XML results
        results = _parse_search_results(result)

        if ctx:
            await ctx.info(f"Found {len(results)} results")

        return results

    @mcp.tool
    async def filter_letters(
        sender: str | None = None,
        receiver: str | None = None,
        send_place: str | None = None,
        not_before: str | None = None,
        not_after: str | None = None,
        max_results: int = 100,
        ctx: Context | None = None,
    ) -> list[Letter]:
        """Filter letters by sender, receiver, place, and time period.

        PURPOSE: Filter letters by specific criteria (FAST - uses cache)

        WHEN TO USE:
        - User asks "letters from/to person X"
        - User asks "letters from Berlin"
        - User asks "letters between 1810 and 1815"
        - For correspondence network analyses

        WHEN NOT TO USE:
        - For keyword search → use search_by_keyword()
        - For register search → use search_register()

        Args:
            sender: Person ID of sender (from register, e.g., "S0003676")
            receiver: Person ID of receiver (from register, e.g., "S0003677")
            send_place: Place ID or name of sending location (e.g., "S0000065" or "Berlin")
            not_before: Earliest date (ISO 8601, e.g., "1810-01-01")
            not_after: Latest date (ISO 8601, e.g., "1815-12-31")
            max_results: Maximum results
            ctx: FastMCP Context

        Returns:
            List of Letter objects
        """
        if not any([sender, receiver, send_place, not_before, not_after]):
            raise ToolError(
                "At least one filter required: sender, receiver, send_place, not_before, or not_after"
            )

        if ctx:
            filters = []
            if sender:
                filters.append(f"sender={sender}")
            if receiver:
                filters.append(f"receiver={receiver}")
            if send_place:
                filters.append(f"place={send_place}")
            if not_before or not_after:
                filters.append(f"date={not_before or ''}..{not_after or ''}")
            await ctx.info(f"Filtering letters: {', '.join(filters)}")

        # Load cache
        cache = await get_letter_cache()

        # Filter in memory (FAST!)
        results = []
        for letter_data in cache:
            # Check sender filter
            if sender:
                sender_ref = (
                    letter_data.get("sender", {}).get("senderRef")
                    if not isinstance(letter_data.get("sender"), list)
                    else None
                )
                if isinstance(letter_data.get("sender"), list):
                    sender_refs = [
                        s.get("senderRef") for s in letter_data.get("sender", [])
                    ]
                    if sender not in sender_refs:
                        continue
                elif sender_ref != sender:
                    continue

            # Check receiver filter
            if receiver:
                receiver_ref = (
                    letter_data.get("receiver", {}).get("receiverRef")
                    if not isinstance(letter_data.get("receiver"), list)
                    else None
                )
                if isinstance(letter_data.get("receiver"), list):
                    receiver_refs = [
                        r.get("receiverRef") for r in letter_data.get("receiver", [])
                    ]
                    if receiver not in receiver_refs:
                        continue
                elif receiver_ref != receiver:
                    continue

            # Check place filter
            if send_place:
                place_ref = letter_data.get("place", {}).get("placeRef") or ""
                place_name = letter_data.get("place", {}).get("placeName") or ""
                if (
                    send_place not in place_ref
                    and send_place.lower() not in place_name.lower()
                ):
                    continue

            # Check date filters
            date_iso = letter_data.get("date_iso")
            if date_iso:
                if not_before and date_iso < not_before:
                    continue
                if not_after and date_iso > not_after:
                    continue

            # All filters passed - add to results
            letter_id = letter_data.get("id")
            if not letter_id:
                continue

            # Extract sender/receiver names and IDs
            sender_obj = letter_data.get("sender", {})
            receiver_obj = letter_data.get("receiver", {})
            place_obj = letter_data.get("place", {})

            sender_name = (
                sender_obj.get("senderName")
                if not isinstance(sender_obj, list)
                else ", ".join([s.get("senderName", "") for s in sender_obj])
            )
            sender_id = (
                sender_obj.get("senderRef")
                if not isinstance(sender_obj, list)
                else sender_obj[0].get("senderRef") if sender_obj else None
            )

            receiver_name = (
                receiver_obj.get("receiverName")
                if not isinstance(receiver_obj, list)
                else ", ".join([r.get("receiverName", "") for r in receiver_obj])
            )
            receiver_id = (
                receiver_obj.get("receiverRef")
                if not isinstance(receiver_obj, list)
                else receiver_obj[0].get("receiverRef") if receiver_obj else None
            )

            send_place_name = place_obj.get("placeName") if place_obj else None
            send_place_id = place_obj.get("placeRef") if place_obj else None

            results.append(
                Letter(
                    id=letter_id,
                    title=f"Brief: {sender_name} an {receiver_name}",
                    date=letter_data.get("dateDisplay", ""),
                    sender=sender_name,
                    sender_id=sender_id,
                    receiver=receiver_name,
                    receiver_id=receiver_id,
                    send_place=send_place_name,
                    send_place_id=send_place_id,
                    url=f"{settings.sd_url}/{letter_id}",
                    citation_url=get_schleiermacher_citation_url(
                        letter_id, "letter fs"
                    ),
                )
            )

            if len(results) >= max_results:
                break

        return results

    @mcp.tool
    async def get_correspondent_stats(
        year: int | None = None,
        min_letters: int = 1,
        ctx: Context | None = None,
    ) -> list[dict]:
        """Statistics about correspondents (for network analysis).

        PURPOSE: Overview of most important correspondents

        WHEN TO USE:
        - User asks "Who was important for X?"
        - User asks "Most frequent correspondents"
        - For quantitative analyses

        Args:
            year: Optional year filter
            min_letters: Minimum number of letters
            ctx: FastMCP Context

        Returns:
            List of dicts with person_name, total, letters_sent, letters_received
        """
        if ctx:
            await ctx.info(f"Computing correspondent stats for year={year}")

        client = await get_client()

        year_filter = f"where starts-with($date, '{year}')" if year else ""

        xquery = f"""
        xquery version "3.1";
        declare namespace tei="http://www.tei-c.org/ns/1.0";

        let $letters := collection('{settings.sd_data_path}/Briefe')//tei:TEI
        for $letter in $letters
        let $date := $letter//tei:correspAction[@type='sent']/tei:date/@when/string()
        {year_filter}
        let $sender := $letter//tei:correspAction[@type='sent']/tei:persName/@ref/string()
        let $receiver := $letter//tei:correspAction[@type='received']/tei:persName/@ref/string()
        return concat($sender, '|||', $receiver, '|||', $date)
        """

        try:
            result = await client.execute_xquery(xquery.strip(), how_many=5000)
        except Exception as e:
            raise ToolError(f"Stats calculation failed: {e}") from e

        # Aggregate statistics (simplified)
        stats: dict[str, dict] = {}

        for line in result.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("|||")
            if len(parts) < MIN_PARTS_FOR_STATS:
                continue

            sender = parts[0] if parts[0] else "unknown"
            receiver = parts[1] if parts[1] else "unknown"

            # Count sender
            if sender != "unknown":
                if sender not in stats:
                    stats[sender] = {"name": sender, "sent": 0, "received": 0}
                stats[sender]["sent"] += 1

            # Count receiver
            if receiver != "unknown":
                if receiver not in stats:
                    stats[receiver] = {"name": receiver, "sent": 0, "received": 0}
                stats[receiver]["received"] += 1

        # Format output
        result_list = []
        for person_id, data in stats.items():
            total = data["sent"] + data["received"]
            if total >= min_letters:
                result_list.append(
                    {
                        "person_id": person_id,
                        "person_name": data["name"],  # TODO: resolve from register
                        "letters_sent": data["sent"],
                        "letters_received": data["received"],
                        "total": total,
                    }
                )

        # Sort by total descending
        result_list.sort(key=lambda x: x["total"], reverse=True)

        return result_list

    @mcp.tool
    async def get_document_passages(
        document_id: str,
        query: str | None = None,
        division: str | None = None,
        page: str | None = None,
        context_size: int = 500,
        max_passages: int = 10,
        ctx: Context | None = None,
    ) -> list[Passage]:
        """Retrieve text passages from a specific document.

        PURPOSE: Get actual text content from a document found via search

        WHEN TO USE:
        - After search returns relevant document IDs
        - User wants to read specific sections
        - Need actual quotes for citations

        WHEN NOT TO USE:
        - For discovery → use search_documents_direct()
        - For full document → use get_document_by_id()

        Args:
            document_id: The xml:id of the document
            query: Optional search term to highlight/filter passages
            division: Filter to specific div by @n value
            page: Filter to specific page by pb/@n
            context_size: Characters of context around matches
            max_passages: Maximum passages to return
            ctx: FastMCP Context

        Returns:
            List of Passage objects with text and location info
        """
        if not document_id or not document_id.strip():
            raise ToolError("document_id is required")

        if ctx:
            await ctx.info(f"Getting passages from {document_id}")

        client = await get_client()

        # Build location filter
        location_filter = ""
        if division:
            location_filter = f"[ancestor-or-self::tei:div[@n='{division}']]"
        elif page:
            location_filter = f"[preceding::tei:pb[@n='{page}']]"

        if query:
            # Query-based: return matching passages with KWIC
            xquery = f"""
            xquery version "3.1";
            declare namespace tei="http://www.tei-c.org/ns/1.0";
            declare namespace ft="http://exist-db.org/xquery/lucene";
            import module namespace kwic="http://exist-db.org/xquery/kwic";

            let $doc := collection('{settings.sd_data_path}')//tei:TEI[@xml:id='{document_id}']
            let $hits := $doc//tei:body//tei:p{location_filter}[ft:query(., '{query}')]

            for $hit at $pos in subsequence($hits, 1, {max_passages})
            let $kwic := kwic:summarize($hit, <config width="{context_size}" table="no"/>)
            let $div := $hit/ancestor::tei:div[@n][1]
            let $pb := $hit/preceding::tei:pb[@n][1]
            (: Use paragraph position instead of path() for eXist-db compatibility :)
            let $para_pos := count($hit/preceding::tei:p) + 1
            return
                <passage>
                    <position>{{$pos}}</position>
                    <div_n>{{$div/@n/string()}}</div_n>
                    <page_n>{{$pb/@n/string()}}</page_n>
                    <text>{{$kwic}}</text>
                    <para_num>{{$para_pos}}</para_num>
                </passage>
            """
        else:
            # No query: return structural passages (paragraphs/divs)
            xquery = f"""
            xquery version "3.1";
            declare namespace tei="http://www.tei-c.org/ns/1.0";

            let $doc := collection('{settings.sd_data_path}')//tei:TEI[@xml:id='{document_id}']
            let $passages := $doc//tei:body//tei:p{location_filter}

            for $p at $pos in subsequence($passages, 1, {max_passages})
            let $div := $p/ancestor::tei:div[@n][1]
            let $pb := $p/preceding::tei:pb[@n][1]
            let $text := normalize-space(string-join($p//text(), ' '))
            (: Use paragraph position instead of path() for eXist-db compatibility :)
            let $para_pos := count($p/preceding::tei:p) + 1
            return
                <passage>
                    <position>{{$pos}}</position>
                    <div_n>{{$div/@n/string()}}</div_n>
                    <page_n>{{$pb/@n/string()}}</page_n>
                    <text>{{substring($text, 1, {context_size})}}</text>
                    <para_num>{{$para_pos}}</para_num>
                </passage>
            """

        try:
            result = await client.execute_xquery(xquery.strip())
        except Exception as e:
            raise ToolError(f"Passage retrieval failed: {e}") from e

        # Parse XML result
        passages = parse_passage_xml(result)

        if ctx:
            await ctx.info(f"Retrieved {len(passages)} passages")

        return passages
