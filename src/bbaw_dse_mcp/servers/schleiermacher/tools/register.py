"""
Register tools for Schleiermacher Digital.

This module provides tools for searching and retrieving register entries
(persons, places, works) from the Schleiermacher edition.
"""

import json
import re
from collections.abc import Awaitable
from typing import Protocol

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from lxml import etree

from bbaw_dse_mcp.config.base import TEI_NS, settings
from bbaw_dse_mcp.schemas.schleiermacher.register import (
    CorrespondenceSummary,
    DocumentMention,
    MentionsSummary,
    PersonEntry,
    PersonName,
    PlaceEntry,
    WorkAuthor,
    WorkEntry,
)
from bbaw_dse_mcp.utils.existdb import ExistDBClient


class ClientGetter(Protocol):
    """Protocol for async client getter function."""

    def __call__(self) -> Awaitable[ExistDBClient]: ...


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
        register_type: str | None = None,
        max_results: int = 20,
        ctx: Context | None = None,
    ) -> list[dict]:
        """Search register using Lucene fulltext index.

        PURPOSE: Find persons, places, works, or organizations using indexed search

        WHEN TO USE:
        - User searches for person, place, work, or organization
        - For biographical/geographical/bibliographical information
        - To get IDs for further searches

        WHEN NOT TO USE:
        - For fulltext search in letters/diaries → use search_by_keyword()

        Args:
            query: Search term (name, title, etc.)
            register_type: Optional filter - 'person', 'place', 'work', 'org', or None for all
            max_results: Maximum results
            ctx: FastMCP Context

        Returns:
            List of register entry dicts with id, title, desc, type
        """
        if not query:
            raise ToolError("query is required")

        if ctx:
            type_info = f" in {register_type}" if register_type else " across all types"
            await ctx.info(f"Searching register{type_info} for: {query}")

        client = await get_client()

        # Build element path - index only exists for specific element types
        if register_type:
            type_map = {
                "person": "tei:person",
                "place": "tei:place",
                "org": "tei:org",
                "work": "tei:bibl",
            }
            element_path = f"//{type_map.get(register_type, f'tei:{register_type}')}"
        else:
            # Use union to query all indexed types
            element_path = "//(tei:person | tei:place | tei:org | tei:bibl)"

        # Use Lucene fulltext search with indexed fields
        # CRITICAL: fields must be requested in options map for ft:field() to work
        xquery = f"""
        xquery version "3.1";
        declare namespace tei="http://www.tei-c.org/ns/1.0";
        declare namespace ft="http://exist-db.org/xquery/lucene";

        let $options := map {{ "fields": ("id", "title", "desc", "doc-type", "fulltext") }}
        let $hits := collection('{settings.sd_data_path}/Register'){element_path}[ft:query(., '{query}', $options)]
        let $results := array {{
            for $hit in $hits
            let $score := ft:score($hit)
            order by $score descending
            return map {{
                "id": ft:field($hit, 'id')[1],
                "title": ft:field($hit, 'title')[1],
                "desc": ft:field($hit, 'desc')[1],
                "type": ft:field($hit, 'doc-type')[1],
                "fulltext": ft:field($hit, 'fulltext')[1],
                "score": $score
            }}
        }}
        return serialize($results, map {{ "method": "json" }})
        """

        try:
            result = await client.execute_xquery(xquery.strip(), how_many=max_results)
        except Exception as e:
            raise ToolError(f"Register search failed: {e}") from e

        # Parse JSON result
        def clean_text(text: str | None) -> str | None:
            """Remove linebreaks and collapse whitespace."""
            if not text:
                return None
            return re.sub(r"\s+", " ", text).strip()

        try:
            entries = json.loads(result)
            # Limit results and clean up
            return [
                {
                    "id": e.get("id"),
                    "title": clean_text(e.get("title")),
                    "desc": clean_text(e.get("desc")),
                    "type": e.get("type"),
                    "fulltext": clean_text(e.get("fulltext")),
                }
                for e in entries[:max_results]
            ]
        except json.JSONDecodeError:
            # Fallback if no results
            return []

    @mcp.tool
    async def get_register_entry(
        entry_id: str,
        include_mentions: bool = False,
        max_mentions: int = 20,
        ctx: Context | None = None,
    ) -> PersonEntry | PlaceEntry | WorkEntry | dict:
        """Get detailed information about a register entry.

        PURPOSE: Complete register entry details, optionally with mentions

        WHEN TO USE:
        - After register search for details about a person/place/work
        - For biographical information
        - To find mentions in letters/diaries (set include_mentions=True)

        WHEN NOT TO USE:
        - For document details → use get_document_by_id()

        Args:
            entry_id: xml:id of the register entry (e.g., "S0003676")
            include_mentions: If True, fetch mentions across letters, diaries, lectures
            max_mentions: Max mentions per category when include_mentions=True (default 20)
            ctx: FastMCP Context

        Returns:
            PersonEntry, PlaceEntry, WorkEntry, or dict based on entry type
        """
        if not entry_id:
            raise ToolError("entry_id is required")

        if ctx:
            mention_info = " with mentions" if include_mentions else ""
            await ctx.info(f"Fetching register entry: {entry_id}{mention_info}")

        client = await get_client()

        # First, find which type this entry is using Lucene index
        type_query = f"""
        xquery version "3.1";
        declare namespace tei="http://www.tei-c.org/ns/1.0";
        declare namespace ft="http://exist-db.org/xquery/lucene";

        let $hit := collection('{settings.sd_data_path}/Register')//*[@xml:id='{entry_id}']
        return if ($hit) then
            ft:field($hit, 'doc-type')
        else
            ''
        """

        try:
            doc_type_result = await client.execute_xquery(type_query.strip())
            doc_type = doc_type_result.strip()

            if not doc_type:
                raise ToolError(f"Register entry '{entry_id}' not found")

        except Exception as e:
            raise ToolError(f"Error retrieving type for '{entry_id}': {e}") from e

        # Now get the full entry XML
        xquery = f"""
        xquery version "3.1";
        declare namespace tei="http://www.tei-c.org/ns/1.0";

        collection('{settings.sd_data_path}/Register')//*[@xml:id='{entry_id}']
        """

        try:
            xml_result = await client.execute_xquery(xquery.strip())
        except Exception as e:
            raise ToolError(f"Error retrieving '{entry_id}': {e}") from e

        if not xml_result.strip():
            raise ToolError(f"Register entry '{entry_id}' not found")

        # Parse the XML
        try:
            root = etree.fromstring(xml_result.encode("utf-8"))
        except etree.XMLSyntaxError as e:
            raise ToolError(f"XML parsing failed: {e}") from e

        # Fetch mentions if requested
        mentions: MentionsSummary | None = None
        if include_mentions and doc_type in ("person", "place"):
            if ctx:
                await ctx.report_progress(50, 100)
                await ctx.info(f"Fetching mentions for {doc_type} {entry_id}...")
            mentions = await _fetch_mentions(client, entry_id, doc_type, max_mentions)

        # Parse based on type
        if doc_type == "person":
            person_entry = _parse_person_entry(root, entry_id)
            person_entry.mentions = mentions
            return person_entry
        if doc_type == "place":
            place_entry = _parse_place_entry(root, entry_id)
            place_entry.mentions = mentions
            return place_entry
        if doc_type == "work":
            return _parse_work_entry(root, entry_id)
        # Fallback to dict for unknown types
        return {
            "id": entry_id,
            "type": doc_type,
            "xml": xml_result,
        }


# Helper functions for parsing register entries


def _parse_person_entry(
    root: etree._Element,
    entry_id: str,
) -> PersonEntry:
    """Parse a person entry from XML."""
    # Extract main name
    reg_name = root.find(".//tei:persName[@type='reg']", TEI_NS)
    surname = None
    forename = None
    full_name = ""

    if reg_name is not None:
        surname_elem = reg_name.find("tei:surname", TEI_NS)
        forename_elem = reg_name.find("tei:forename", TEI_NS)
        surname = surname_elem.text if surname_elem is not None else None
        forename = forename_elem.text if forename_elem is not None else None
        full_name = f"{surname or ''}, {forename or ''}".strip(", ")

    name = PersonName(
        surname=surname,
        forename=forename,
        full_name=full_name or "Unknown",
    )

    # Life dates
    birth_elem = root.find(".//tei:birth", TEI_NS)
    death_elem = root.find(".//tei:death", TEI_NS)
    birth = birth_elem.text if birth_elem is not None else None
    death = death_elem.text if death_elem is not None else None

    # Note
    note_elem = root.find(".//tei:note", TEI_NS)
    note = note_elem.text if note_elem is not None else None

    # GND
    gnd = root.get("corresp")

    # TODO: Parse alternative names if needed

    return PersonEntry(
        id=entry_id,
        name=name,
        birth=birth,
        death=death,
        gnd=gnd,
        note=note,
    )


def _parse_place_entry(root: etree._Element, entry_id: str) -> PlaceEntry:
    """Parse a place entry from XML."""
    # Extract place name
    place_name_elem = root.find(".//tei:placeName[@type='reg']", TEI_NS)
    name = (
        (place_name_elem.text or "Unknown")
        if place_name_elem is not None
        else "Unknown"
    )

    # GND/Geonames
    geonames_elem = root.find(".//tei:idno[@type='uri']", TEI_NS)
    geonames_uri = geonames_elem.text if geonames_elem is not None else None

    # Note
    note_elem = root.find(".//tei:note", TEI_NS)
    note = note_elem.text if note_elem is not None else None

    # Place type
    place_type = root.get("type")

    # TODO: Parse alternative names and sub-places if needed

    return PlaceEntry(
        id=entry_id,
        name=name,
        place_type=place_type,
        geonames_uri=geonames_uri,
        note=note,
    )


def _parse_work_entry(root: etree._Element, entry_id: str) -> WorkEntry:
    """Parse a work entry from XML."""
    # Extract title
    title_elem = root.find(".//tei:title", TEI_NS)
    title = title_elem.text if title_elem is not None else ""

    # Extract author
    author_elem = root.find(".//tei:author/tei:persName", TEI_NS)
    author = None
    if author_elem is not None:
        surname_elem = author_elem.find("tei:surname", TEI_NS)
        forename_elem = author_elem.find("tei:forename", TEI_NS)
        author = WorkAuthor(
            key=author_elem.get("key"),
            surname=surname_elem.text if surname_elem is not None else None,
            forename=forename_elem.text if forename_elem is not None else None,
        )

    # Date
    date_elem = root.find(".//tei:date", TEI_NS)
    date = date_elem.text if date_elem is not None else None

    # Publication place
    pub_place_elem = root.find(".//tei:pubPlace", TEI_NS)
    pub_place = pub_place_elem.text if pub_place_elem is not None else None
    pub_place_key = pub_place_elem.get("key") if pub_place_elem is not None else None

    # Note
    note_elem = root.find(".//tei:note", TEI_NS)
    note = note_elem.text if note_elem is not None else None

    return WorkEntry(
        id=entry_id,
        author=author,
        title=title or "Unknown",
        date=date,
        pub_place=pub_place,
        pub_place_key=pub_place_key,
        note=note,
    )


# ==================== MENTION FETCHING ====================


async def _fetch_mentions(
    client: ExistDBClient,
    entry_id: str,
    entity_type: str,
    max_results: int = 20,
) -> MentionsSummary:
    """Fetch mentions of an entity across letters, diaries, lectures.

    For letters: Uses JSON cache at /db/projects/schleiermacher/cache/letters/register/
    For diaries/lectures: Uses Lucene indexed fields

    Args:
        client: ExistDB client
        entry_id: xml:id of the register entry
        entity_type: 'person' or 'place'
        max_results: Max items per category to return

    Returns:
        MentionsSummary with counts and sample documents
    """
    letters: list[DocumentMention] = []
    diaries: list[DocumentMention] = []
    lectures: list[DocumentMention] = []
    correspondence: CorrespondenceSummary | None = None
    total_letters = 0
    total_diaries = 0
    total_lectures = 0

    # ===== LETTERS: Use JSON cache for performance =====
    # The cache contains all letter metadata + mentions for each entity
    # Note: sender/receiver can be either a single object or an array
    letter_cache_xquery = f"""
    xquery version "3.1";

    let $cacheFile := '{settings.sd_cache_path}/letters/register/letters-for-register.json'
    let $jsonData := parse-json(util:binary-to-string(util:binary-doc($cacheFile)))
    let $letterArray := $jsonData("letter")
    let $entityType := '{entity_type}'
    let $entityId := '{entry_id}'

    (: Helper to check if sender/receiver matches - handles both object and array :)
    let $matchesSender := function($data, $id) {{
        let $sender := $data("sender")
        return
            if (empty($sender)) then false()
            else if ($sender instance of array(*)) then
                some $s in array:flatten($sender) satisfies $s("senderRef") = $id
            else if ($sender instance of map(*)) then
                $sender("senderRef") = $id
            else false()
    }}

    let $matchesReceiver := function($data, $id) {{
        let $receiver := $data("receiver")
        return
            if (empty($receiver)) then false()
            else if ($receiver instance of array(*)) then
                some $r in array:flatten($receiver) satisfies $r("receiverRef") = $id
            else if ($receiver instance of map(*)) then
                $receiver("receiverRef") = $id
            else false()
    }}

    (: Count correspondence (sender/receiver) for persons :)
    let $senderCount :=
        if ($entityType = 'person') then
            count(
                for $i in 1 to array:size($letterArray)
                let $entry := array:get($letterArray, $i)
                let $data := $entry("data")
                where $matchesSender($data, $entityId)
                return 1
            )
        else 0

    let $recipientCount :=
        if ($entityType = 'person') then
            count(
                for $i in 1 to array:size($letterArray)
                let $entry := array:get($letterArray, $i)
                let $data := $entry("data")
                where $matchesReceiver($data, $entityId)
                return 1
            )
        else 0

    (: Find letters with mentions of this entity :)
    let $mentionLetters :=
        for $i in 1 to array:size($letterArray)
        let $entry := array:get($letterArray, $i)
        let $data := $entry("data")
        let $mentions := $data("mentions")
        where exists($mentions) and $mentions instance of map(*)
        let $entityMentions :=
            if ($entityType = 'person') then
                let $persons := $mentions("persons")
                return if (exists($persons) and $persons instance of map(*)) then $persons("person") else ()
            else if ($entityType = 'place') then
                let $places := $mentions("places")
                return if (exists($places) and $places instance of map(*)) then $places("place") else ()
            else ()
        where exists($entityMentions) and $entityMentions instance of array(*)
        let $matchingMentions :=
            for $mention in array:flatten($entityMentions)
            where $mention instance of map(*) and $mention("id") = $entityId
            return $mention
        where exists($matchingMentions)
        let $mentionType :=
            if (some $m in $matchingMentions satisfies $m("type") = "regular") then "text"
            else "comment"
        order by $data("date_iso")
        return map {{
            "id": $data("id"),
            "title": concat("Brief ", $data("idno"), ": ", $data("dateDisplay")),
            "date": $data("date_iso"),
            "mentionType": $mentionType
        }}

    return serialize(map {{
        "senderCount": $senderCount,
        "recipientCount": $recipientCount,
        "correspondenceTotal": $senderCount + $recipientCount,
        "mentionTotal": count($mentionLetters),
        "mentions": array {{ subsequence($mentionLetters, 1, {max_results}) }}
    }}, map {{ "method": "json" }})
    """

    try:
        result = await client.execute_xquery(letter_cache_xquery.strip())
        data = json.loads(result) if result.strip() else {}

        # Correspondence stats (persons only)
        if entity_type == "person":
            correspondence = CorrespondenceSummary(
                person_id=entry_id,
                letters_as_sender=data.get("senderCount", 0),
                letters_as_recipient=data.get("recipientCount", 0),
                total_letters=data.get("correspondenceTotal", 0),
            )

        # Letter mentions
        total_letters = data.get("mentionTotal", 0)
        letters = [
            DocumentMention(
                id=item.get("id", ""),
                title=item.get("title", ""),
                date=item.get("date"),
                doc_type="letter",
                mention_type=item.get("mentionType", "text"),
            )
            for item in data.get("mentions", [])
        ]
    except Exception:
        pass  # Non-critical, continue with other sources

    # ===== DIARIES & LECTURES: Use Lucene index =====
    # Build field queries based on entity type
    if entity_type == "person":
        text_query = (
            f"text-person-keys:{entry_id} OR "
            f"text-rs-person-keys:{entry_id} OR "
            f"text-index-person-keys:{entry_id}"
        )
        comment_query = (
            f"comment-person-keys:{entry_id} OR " f"comment-rs-person-keys:{entry_id}"
        )
    else:
        text_query = f"text-place-keys:{entry_id}"
        comment_query = f"comment-place-keys:{entry_id}"

    # Query for diary mentions
    diary_xquery = f"""
    xquery version "3.1";
    declare namespace tei="http://www.tei-c.org/ns/1.0";
    declare namespace ft="http://exist-db.org/xquery/lucene";

    let $textHits := collection('{settings.sd_data_path}/Tageskalender')//tei:TEI[ft:query(., '{text_query}')]
    let $commentHits := collection('{settings.sd_data_path}/Tageskalender')//tei:TEI[ft:query(., '{comment_query}')]
    let $allHits := ($textHits | $commentHits)
    let $limited := subsequence($allHits, 1, {max_results})
    return serialize(map {{
        "total": count($allHits),
        "items": array {{
            for $doc in $limited
            let $id := string($doc/@xml:id)
            let $title := string(($doc//tei:titleStmt/tei:title)[1])
            let $date := string(($doc//tei:creation/tei:date/@when)[1])
            let $inText := $doc = $textHits
            order by $date
            return map {{
                "id": $id,
                "title": $title,
                "date": $date,
                "mentionType": if ($doc = $commentHits and not($inText)) then "comment" else "text"
            }}
        }}
    }}, map {{ "method": "json" }})
    """
    try:
        result = await client.execute_xquery(diary_xquery.strip())
        data = json.loads(result) if result.strip() else {}
        total_diaries = data.get("total", 0)
        diaries = [
            DocumentMention(
                id=item.get("id", ""),
                title=item.get("title", ""),
                date=item.get("date"),
                doc_type="diary",
                mention_type=item.get("mentionType", "text"),
            )
            for item in data.get("items", [])
        ]
    except Exception:
        pass

    # Query for lecture mentions
    lecture_xquery = f"""
    xquery version "3.1";
    declare namespace tei="http://www.tei-c.org/ns/1.0";
    declare namespace ft="http://exist-db.org/xquery/lucene";

    let $textHits := collection('{settings.sd_data_path}/Vorlesungen')//tei:TEI[ft:query(., '{text_query}')]
    let $commentHits := collection('{settings.sd_data_path}/Vorlesungen')//tei:TEI[ft:query(., '{comment_query}')]
    let $allHits := ($textHits | $commentHits)
    let $limited := subsequence($allHits, 1, {max_results})
    return serialize(map {{
        "total": count($allHits),
        "items": array {{
            for $doc in $limited
            let $id := string($doc/@xml:id)
            let $title := string(($doc//tei:titleStmt/tei:title)[1])
            let $inText := $doc = $textHits
            order by $title
            return map {{
                "id": $id,
                "title": $title,
                "date": (),
                "mentionType": if ($doc = $commentHits and not($inText)) then "comment" else "text"
            }}
        }}
    }}, map {{ "method": "json" }})
    """
    try:
        result = await client.execute_xquery(lecture_xquery.strip())
        data = json.loads(result) if result.strip() else {}
        total_lectures = data.get("total", 0)
        lectures = [
            DocumentMention(
                id=item.get("id", ""),
                title=item.get("title", ""),
                date=item.get("date"),
                doc_type="lecture",
                mention_type=item.get("mentionType", "text"),
            )
            for item in data.get("items", [])
        ]
    except Exception:
        pass

    return MentionsSummary(
        correspondence=correspondence,
        letters=letters,
        diaries=diaries,
        lectures=lectures,
        total_letter_mentions=total_letters,
        total_diary_mentions=total_diaries,
        total_lecture_mentions=total_lectures,
    )
