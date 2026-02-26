"""Utilities for correspSearch API interactions."""

import logging
import re
from typing import Any

from bbaw_dse_mcp.schemas.correspsearch.correspsearch import (
    Correspondent,
    CorrespSearchLetter,
    CorrespSearchResult,
    Place,
)

logger = logging.getLogger(__name__)


def extract_gnd_from_uri(uri: str | None) -> str | None:
    """Extract GND ID from a full GND URI.

    Args:
        uri: Full URI like "http://d-nb.info/gnd/118540238"

    Returns:
        GND ID like "118540238" or None
    """
    if not uri:
        return None
    match = re.search(r"gnd/(\d+X?)", uri, re.IGNORECASE)
    return match.group(1) if match else None


def extract_geonames_from_uri(uri: str | None) -> str | None:
    """Extract GeoNames ID from a full GeoNames URI.

    Args:
        uri: Full URI like "http://www.geonames.org/2879139"

    Returns:
        GeoNames ID like "2879139" or None
    """
    if not uri:
        return None
    match = re.search(r"geonames\.org/(\d+)", uri, re.IGNORECASE)
    return match.group(1) if match else None


def parse_correspondent(
    action_data: dict[str, Any] | None,
) -> tuple[Correspondent | None, Place | None, dict[str, str | None]]:
    """Parse a correspAction dict to extract correspondent and place.

    Args:
        action_data: The correspAction dictionary from JSON

    Returns:
        Tuple of (Correspondent, Place, date_dict with when/from/to/notBefore/notAfter)
    """
    if action_data is None:
        return None, None, {}

    correspondent = None
    place = None
    date_info: dict[str, str | None] = {
        "when": None,
        "from": None,
        "to": None,
        "notBefore": None,
        "notAfter": None,
    }

    # Parse person/organization
    pers_data = action_data.get("persName")
    if pers_data:
        # persName can be a list or single dict
        if isinstance(pers_data, list):
            pers_data = pers_data[0] if pers_data else None

        if pers_data:
            name = pers_data.get("#text", "").strip() or None
            ref = pers_data.get("ref", "")

            # Handle multiple refs (space-separated)
            refs = ref.split() if ref else []
            gnd = None
            authority_uri = refs[0] if refs else None

            for r in refs:
                if "gnd" in r.lower():
                    gnd = extract_gnd_from_uri(r)
                    if not authority_uri:
                        authority_uri = r

            correspondent = Correspondent(
                name=name,
                gnd=gnd,
                authority_uri=authority_uri,
            )

    # Handle orgName if no persName
    if not correspondent:
        org_data = action_data.get("orgName")
        if org_data:
            if isinstance(org_data, list):
                org_data = org_data[0] if org_data else None

            if org_data:
                name = org_data.get("#text", "").strip() or None
                ref = org_data.get("ref", "")

                correspondent = Correspondent(
                    name=name,
                    authority_uri=ref if ref else None,
                )

    # Parse place
    place_data = action_data.get("placeName")
    if place_data:
        if isinstance(place_data, list):
            place_data = place_data[0] if place_data else None

        if place_data:
            place_name = place_data.get("#text", "").strip() or None
            place_ref = place_data.get("ref", "")
            geonames_id = extract_geonames_from_uri(place_ref)

            place = Place(
                name=place_name,
                geonames_id=geonames_id,
                geonames_uri=place_ref if place_ref else None,
            )

    # Parse date
    date_data = action_data.get("date")
    if date_data:
        if isinstance(date_data, list):
            date_data = date_data[0] if date_data else None

        if date_data:
            # Store all date attributes
            date_info["when"] = date_data.get("when")
            date_info["from"] = date_data.get("from")
            date_info["to"] = date_data.get("to")
            date_info["notBefore"] = date_data.get("notBefore")
            date_info["notAfter"] = date_data.get("notAfter")

    return correspondent, place, date_info


def parse_correspdesc_to_letter(
    corresp_data: dict[str, Any],
) -> CorrespSearchLetter | None:
    """Parse a correspDesc dictionary into a CorrespSearchLetter.

    Args:
        corresp_data: A correspDesc dictionary from JSON

    Returns:
        CorrespSearchLetter or None if parsing fails
    """
    try:
        # Extract source URL from @ref attribute (this is the letter's URL in the edition)
        source_url = corresp_data.get("ref")

        # Use source URL as ID if available
        letter_id = source_url or "unknown"

        # Get correspAction array
        actions = corresp_data.get("correspAction", [])
        if not isinstance(actions, list):
            actions = [actions]

        # Find sent and received actions
        sender_action = next((a for a in actions if a.get("type") == "sent"), None)
        receiver_action = next(
            (a for a in actions if a.get("type") == "received"), None
        )

        # Parse sender
        sender, send_place, send_date_info = parse_correspondent(sender_action)

        # Parse receiver
        receiver, receive_place, _ = parse_correspondent(receiver_action)

        # Extract date fields
        date_when = send_date_info.get("when")
        date_from = send_date_info.get("from")
        date_to = send_date_info.get("to")
        date_not_before = send_date_info.get("notBefore")
        date_not_after = send_date_info.get("notAfter")

        # Determine primary date for backward compatibility
        # Prefer @when, then @from, then @notBefore, then @notAfter
        primary_date = date_when or date_from or date_not_before or date_not_after

        # Build title with appropriate date representation
        sender_name = sender.name if sender else "N.N."
        receiver_name = receiver.name if receiver else "N.N."
        title = f"Brief von {sender_name} an {receiver_name}"

        if date_when:
            title += f" ({date_when})"
        elif date_from and date_to:
            title += f" ({date_from} bis {date_to})"
        elif date_from:
            title += f" ({date_from})"
        elif date_not_before and date_not_after:
            title += f" (zwischen {date_not_before} und {date_not_after})"
        elif date_not_before:
            title += f" (nach {date_not_before})"
        elif date_not_after:
            title += f" (vor {date_not_after})"

        # Get edition reference from @source attribute (points to bibl/@xml:id)
        edition_id = corresp_data.get("source", "")
        # Remove leading # if present
        if edition_id.startswith("#"):
            edition_id = edition_id[1:]

        return CorrespSearchLetter(
            id=letter_id,
            title=title,
            date=primary_date,
            date_when=date_when,
            date_from=date_from,
            date_to=date_to,
            date_not_before=date_not_before,
            date_not_after=date_not_after,
            sender=sender,
            receiver=receiver,
            send_place=send_place,
            receive_place=receive_place,
            edition_id=edition_id if edition_id else None,
            source_url=source_url,
        )
    except (AttributeError, TypeError, ValueError, KeyError) as e:
        logger.warning(f"Failed to parse correspDesc: {e}")
        return None


def parse_tei_json_response(json_data: dict[str, Any]) -> CorrespSearchResult:
    """Parse TEI-JSON response from correspSearch API.

    Args:
        json_data: Parsed JSON response

    Returns:
        CorrespSearchResult with letters and pagination info
    """
    letters: list[CorrespSearchLetter] = []
    total_count = 0
    page = 1
    has_next = False
    next_page_url = None

    try:
        tei_header = json_data.get("teiHeader", {})
        file_desc = tei_header.get("fileDesc", {})

        # Extract edition metadata from sourceDesc/bibl elements
        edition_cmif_urls: dict[str, str | None] = {}
        edition_titles: dict[str, str | None] = {}

        source_desc = file_desc.get("sourceDesc")
        if source_desc:  # sourceDesc might be None if no results
            bibl_list = source_desc.get("bibl", [])
            if not isinstance(bibl_list, list):
                bibl_list = [bibl_list]

            for bibl in bibl_list:
                bibl_id = bibl.get("xml:id")
                if bibl_id:
                    # Extract edition title
                    edition_title = bibl.get("#text", "").strip() or None
                    edition_titles[bibl_id] = edition_title

                    # Extract CMIF URL from ref
                    ref = bibl.get("ref")
                    if ref:
                        if isinstance(ref, dict):
                            edition_cmif_urls[bibl_id] = ref.get("target")
                        elif isinstance(ref, str):
                            edition_cmif_urls[bibl_id] = ref

        # Extract pagination info from notesStmt
        notes_stmt = file_desc.get("notesStmt", {})
        note = notes_stmt.get("note", "")
        if note:
            # Try to extract numbers like "1-10 of 681 hits"
            match = re.search(r"(\d+)-(\d+).*?(\d+)", note)
            if match:
                page = (int(match.group(1)) - 1) // 100 + 1
                total_count = int(match.group(3))

        # Get next page URL
        related_item = notes_stmt.get("relatedItem", {})
        if isinstance(related_item, dict) and related_item.get("type") == "next":
            next_page_url = related_item.get("target")
            has_next = next_page_url is not None

        # Parse all correspDesc elements
        profile_desc = tei_header.get("profileDesc")
        if profile_desc:
            corresp_descs = profile_desc.get("correspDesc", [])
            if not isinstance(corresp_descs, list):
                corresp_descs = [corresp_descs]

            for corresp_data in corresp_descs:
                letter = parse_correspdesc_to_letter(corresp_data)
                if letter:
                    # Enrich with edition metadata
                    if letter.edition_id:
                        if letter.edition_id in edition_titles:
                            letter.edition_title = edition_titles[letter.edition_id]
                        if letter.edition_id in edition_cmif_urls:
                            letter.cmif_url = edition_cmif_urls[letter.edition_id]
                    letters.append(letter)

    except (KeyError, TypeError, ValueError) as e:
        logger.error(f"JSON parse error: {e}")

    return CorrespSearchResult(
        letters=letters,
        total_count=total_count if total_count else len(letters),
        page=page,
        has_next=has_next,
        next_page_url=next_page_url,
    )


def parse_edition_info(
    json_data: dict[str, Any], edition_id: str
) -> "EditionInfo | None":
    """Parse edition metadata from TEI-JSON response.

    Args:
        json_data: Parsed JSON response from correspSearch API
        edition_id: Edition UUID to extract metadata for

    Returns:
        EditionInfo or None if parsing fails
    """
    from bbaw_dse_mcp.schemas.correspsearch.correspsearch import EditionInfo

    try:
        tei_header = json_data.get("teiHeader", {})
        file_desc = tei_header.get("fileDesc", {})
        source_desc = file_desc.get("sourceDesc", {})
        bibl_list = source_desc.get("bibl", [])
        if not isinstance(bibl_list, list):
            bibl_list = [bibl_list]

        # Find the bibl with matching xml:id
        for bibl in bibl_list:
            bibl_id = bibl.get("xml:id")
            if bibl_id == edition_id:
                # Extract title
                title = bibl.get("#text", "").strip() or "Unknown Edition"

                # Extract CMIF URL from ref
                cmif_url = None
                ref = bibl.get("ref")
                if ref:
                    if isinstance(ref, dict):
                        cmif_url = ref.get("target")
                    elif isinstance(ref, str):
                        cmif_url = ref

                # Extract editor from titleStmt/editor if available
                title_stmt = file_desc.get("titleStmt", {})
                editor_data = title_stmt.get("editor")
                editor = None
                if editor_data:
                    if isinstance(editor_data, dict):
                        editor = editor_data.get("#text", "").strip() or None
                    elif isinstance(editor_data, list) and editor_data:
                        editor = editor_data[0].get("#text", "").strip() or None

                # Extract publisher from publicationStmt
                pub_stmt = file_desc.get("publicationStmt", {})
                publisher_data = pub_stmt.get("publisher")
                publisher = None
                if publisher_data:
                    if isinstance(publisher_data, dict):
                        publisher = publisher_data.get("#text", "").strip() or None
                    elif isinstance(publisher_data, str):
                        publisher = publisher_data.strip() or None

                # Extract license from availability
                license_info = None
                availability = pub_stmt.get("availability", {})
                if availability:
                    license_elem = availability.get("licence")
                    if isinstance(license_elem, dict):
                        license_info = license_elem.get("target") or license_elem.get(
                            "#text"
                        )

                return EditionInfo(
                    id=edition_id,
                    title=title,
                    editor=editor,
                    publisher=publisher,
                    url=None,  # Not available in this response
                    cmif_url=cmif_url,
                    license=license_info,
                    letter_count=None,  # Would need separate query
                )

        logger.warning(f"Edition {edition_id} not found in bibl list")
        return None

    except (KeyError, TypeError, ValueError) as e:
        logger.error(f"Failed to parse edition info: {e}")
        return None


def build_api_params(
    person_gnd: str | list[str] | None = None,
    person_viaf: str | list[str] | None = None,
    place_geonames: str | None = None,
    occupation_wikidata: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    edition_id: str | None = None,
    cmif_url: str | None = None,
    availability: str | None = None,
    text_query: str | None = None,
    gender: str | None = None,
    page: int = 1,
    role: str | None = None,
    place_role: str | None = None,
) -> dict[str, str]:
    """Build API query parameters for correspSearch.

    Args:
        person_gnd: GND ID(s) of person(s) - single string or list (combined with AND)
        person_viaf: VIAF ID(s) of person(s) - single string or list (combined with AND)
        place_geonames: GeoNames ID of a place
        occupation_wikidata: Wikidata ID of an occupation (e.g., "Q36180" or full URI)
        start_date: Start date (ISO 8601)
        end_date: End date (ISO 8601)
        edition_id: Edition UUID to filter by
        cmif_url: URL of a CMIF file (e.g., "https://gams.uni-graz.at/context:hsa/CMIF")
        availability: 'online', 'print', or 'hybrid'
        text_query: Full-text search query (searches in letter content, undocumented)
        gender: 'male', 'female', or 'unknown' to filter by correspondent gender
        page: Page number (1-indexed)
        role: 'sent', 'received', or 'mentioned' to filter person by role
        place_role: 'sent' or 'received' to filter place by role

    Returns:
        Dictionary of query parameters
    """
    params: dict[str, str] = {}

    # Person parameter (s)
    # Multiple persons are comma-separated and combined with AND
    if person_gnd:
        # Normalize to list
        gnd_list = [person_gnd] if isinstance(person_gnd, str) else person_gnd

        # Build URIs for each GND
        gnd_uris = []
        for gnd in gnd_list:
            gnd_uri = gnd if gnd.startswith("http") else f"http://d-nb.info/gnd/{gnd}"
            if role:
                gnd_uri += f"::{role}"
            gnd_uris.append(gnd_uri)

        params["s"] = ",".join(gnd_uris)
    elif person_viaf:
        # Normalize to list
        viaf_list = [person_viaf] if isinstance(person_viaf, str) else person_viaf

        # Build URIs for each VIAF
        viaf_uris = []
        for viaf in viaf_list:
            viaf_uri = (
                viaf if viaf.startswith("http") else f"http://viaf.org/viaf/{viaf}"
            )
            if role:
                viaf_uri += f"::{role}"
            viaf_uris.append(viaf_uri)

        params["s"] = ",".join(viaf_uris)

    # Place parameter (p) - MUST use sws.geonames.org prefix!
    if place_geonames:
        geo_uri = (
            place_geonames
            if place_geonames.startswith("http")
            else f"http://sws.geonames.org/{place_geonames}"
        )
        if place_role:
            geo_uri += f"::{place_role}"
        params["p"] = geo_uri

    # Occupation parameter (o)
    if occupation_wikidata:
        occupation_uri = (
            occupation_wikidata
            if occupation_wikidata.startswith("http")
            else f"http://www.wikidata.org/entity/{occupation_wikidata}"
        )
        params["o"] = occupation_uri

    # Date parameter (d)
    # If start and end are the same, use single value (e.g., "1808" instead of "1808-1808")
    if start_date and end_date:
        if start_date == end_date:
            params["d"] = start_date
        else:
            params["d"] = f"{start_date}-{end_date}"
    elif start_date:
        params["d"] = start_date
    elif end_date:
        params["d"] = end_date

    # Edition parameter (e)
    if edition_id:
        params["e"] = edition_id

    # CMIF URL parameter (c)
    if cmif_url:
        params["c"] = cmif_url

    # Availability parameter (a)
    if availability and availability in ("online", "print", "hybrid"):
        params["a"] = availability

    # Text search (q) - undocumented API feature
    if text_query:
        params["q"] = text_query

    # Gender parameter (g)
    if gender and gender in ("male", "female", "unknown"):
        params["g"] = gender

    # Pagination (x)
    if page > 1:
        params["x"] = str(page)

    return params
