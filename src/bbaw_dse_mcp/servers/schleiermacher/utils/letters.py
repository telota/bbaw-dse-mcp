"""Letter-specific parsing and formatting for Schleiermacher Digital."""

from lxml import etree

from bbaw_dse_mcp.config.base import TEI_NS as NS
from bbaw_dse_mcp.schemas.schleiermacher.documents import Letter
from bbaw_dse_mcp.servers.schleiermacher.utils.citations import (
    get_schleiermacher_citation_url,
)
from bbaw_dse_mcp.utils.tei import (
    clean_text,
    extract_text,
    parse_corresp_action,
    parse_editor,
    parse_source,
    strip_processing_instructions,
)


def _extract_body_content(
    body_elem: etree._Element | None,
) -> tuple[str | None, str | None, str | None]:
    """Extract body content sections: opener, body text, closer.

    Handles multiple writing sessions by concatenating their content.

    Args:
        body_elem: TEI body element

    Returns:
        Tuple of (opener, body_text, closer)
    """
    if body_elem is None:
        return None, None, None

    # Find all writingSession divs
    writing_sessions = body_elem.findall(".//tei:div[@type='writingSession']", NS)
    if not writing_sessions:
        # Fallback to extracting all text from body
        body_text = extract_text(body_elem)
        return None, body_text, None

    # Process all writing sessions
    all_openers = []
    all_paragraphs = []
    all_closers = []

    for session in writing_sessions:
        # Extract opener (address, dateline, salute)
        opener_elem = session.find("tei:opener", NS)
        if opener_elem is not None:
            opener_text = extract_text(opener_elem)
            if opener_text:
                all_openers.append(clean_text(opener_text))

        # Extract all paragraphs
        for p_elem in session.findall("tei:p", NS):
            p_text = extract_text(p_elem)
            if p_text:
                all_paragraphs.append(clean_text(p_text))

        # Extract closer (signed, salute)
        closer_elem = session.find("tei:closer", NS)
        if closer_elem is not None:
            closer_text = extract_text(closer_elem)
            if closer_text:
                all_closers.append(clean_text(closer_text))

    # Combine results
    opener = "\n\n".join(o for o in all_openers if o) if all_openers else None
    body_text = "\n\n".join(p for p in all_paragraphs if p) if all_paragraphs else None
    closer = "\n\n".join(c for c in all_closers if c) if all_closers else None

    return opener, body_text, closer


def _extract_register_references(
    body_elem: etree._Element | None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Extract referenced persons and places from body.

    Args:
        body_elem: TEI body element

    Returns:
        Tuple of (persons, places) with id and name
    """
    persons: list[dict[str, str]] = []
    places: list[dict[str, str]] = []

    if body_elem is None:
        return persons, places

    # Extract all persName elements with @key
    seen_persons = set()
    for pers_elem in body_elem.findall(".//tei:persName[@key]", NS):
        key = pers_elem.get("key")
        name_raw = extract_text(pers_elem)
        name = clean_text(name_raw)  # Clean whitespace and linebreaks
        if key and name and key not in seen_persons:
            persons.append({"id": key, "name": name})
            seen_persons.add(key)

    # Extract all placeName elements with @key
    seen_places = set()
    for place_elem in body_elem.findall(".//tei:placeName[@key]", NS):
        key = place_elem.get("key")
        name_raw = extract_text(place_elem)
        name = clean_text(name_raw)  # Clean whitespace and linebreaks
        if key and name and key not in seen_places:
            places.append({"id": key, "name": name})
            seen_places.add(key)

    return persons, places


def _extract_editorial_notes(body_elem: etree._Element | None) -> list[str]:
    """Extract all editorial notes from body.

    Args:
        body_elem: TEI body element

    Returns:
        List of note texts
    """
    notes: list[str] = []

    if body_elem is None:
        return notes

    # Extract all <note> elements
    for note_elem in body_elem.findall(".//tei:note", NS):
        note_text = extract_text(note_elem)
        if note_text:
            # Clean up whitespace and linebreaks
            cleaned = clean_text(note_text)
            if cleaned:
                notes.append(cleaned)

    return notes


def parse_letter(xml_str: str, doc_id: str) -> Letter:
    """Parse comprehensive letter metadata from TEI XML string.

    Args:
        xml_str: TEI XML string
        doc_id: Document ID (xml:id)

    Returns:
        Letter object with all extracted metadata

    Example:
        >>> xml = '''<TEI xmlns="http://www.tei-c.org/ns/1.0" xml:id="S0007791">...</TEI>'''
        >>> letter = parse_letter(xml, "S0007791")
        >>> print(letter.title)
        >>> print(letter.sender.person_name)
    """
    # Strip processing instructions first
    xml_str = strip_processing_instructions(xml_str)

    root = etree.fromstring(xml_str.encode("utf-8"))
    header = root.find(".//tei:teiHeader", NS)

    if header is None:
        # Fallback to minimal parsing
        return Letter(id=doc_id, title="Unknown")

    # Title and idno
    title_elem = header.find(".//tei:titleStmt/tei:title", NS)

    # Extract idno from title (e.g., "3413a")
    idno_elem = title_elem.find("tei:idno", NS) if title_elem is not None else None
    idno = extract_text(idno_elem)

    # Extract title text, excluding idno element
    if title_elem is not None:
        # Get direct text and tail text, excluding child elements
        title_parts = []
        if title_elem.text:
            title_parts.append(title_elem.text.strip())
        title_parts.extend(child.tail.strip() for child in title_elem if child.tail)
        title = " ".join(part for part in title_parts if part) or "Unknown"
    else:
        title = "Unknown"

    # Editors
    editors = [
        parse_editor(editor_elem)
        for editor_elem in header.findall(".//tei:titleStmt/tei:editor", NS)
    ]

    # Correspondence description
    corresp_desc = header.find(".//tei:correspDesc", NS)
    sender = None
    receiver = None

    if corresp_desc is not None:
        sent_action = corresp_desc.find(".//tei:correspAction[@type='sent']", NS)
        received_action = corresp_desc.find(
            ".//tei:correspAction[@type='received']", NS
        )

        sender = parse_corresp_action(sent_action)
        receiver = parse_corresp_action(received_action)

    # Note from correspDesc
    note_elem = corresp_desc.find("tei:note", NS) if corresp_desc is not None else None
    note_text = extract_text(note_elem)
    note = clean_text(note_text) if note_text else None

    # Abstract (for inferred letters)
    abstract_elem = header.find(".//tei:abstract/tei:p", NS)
    abstract_text = extract_text(abstract_elem)
    abstract = clean_text(abstract_text) if abstract_text else None

    # Manuscript status
    ms_desc = header.find(".//tei:msDesc", NS)
    manuscript_status = ms_desc.get("rend") if ms_desc is not None else None

    # Source description
    source_elem = header.find(".//tei:sourceDesc", NS)
    source = parse_source(source_elem)

    # Parse body content
    body_elem = root.find(".//tei:text/tei:body", NS)
    opener, body_text, closer = _extract_body_content(body_elem)

    # Extract register references and editorial notes
    referenced_persons, referenced_places = _extract_register_references(body_elem)
    editorial_notes = _extract_editorial_notes(body_elem)

    # Extract facsimile URLs
    facsimiles = []
    if body_elem is not None:
        for fig in body_elem.findall(".//tei:figure[@type='letter'][@facs]", NS):
            facs_url = fig.get("facs")
            if facs_url:
                facsimiles.append(facs_url)

    # Generate URL
    url = f"https://schleiermacher-digital.de/{doc_id}" if doc_id else None
    citation_url = get_schleiermacher_citation_url(doc_id, "letter fs")

    return Letter(
        id=doc_id,
        idno=idno,
        title=title,
        sender=sender,
        receiver=receiver,
        editors=editors,
        source=source,
        note=note,
        abstract=abstract,
        manuscript_status=manuscript_status,
        opener=opener,
        body_text=body_text,
        closer=closer,
        referenced_persons=referenced_persons,
        referenced_places=referenced_places,
        editorial_notes=editorial_notes,
        facsimiles=facsimiles,
        url=url,
        citation_url=citation_url,
    )


def format_letter_as_markdown(
    letter: Letter,
    *,
    max_text_length: int = 300000,
    max_persons: int = 100,
    max_notes: int = 50,
) -> str:
    """Format letter as comprehensive markdown resource.

    Args:
        letter: Letter object to format
        max_text_length: Maximum length for body text before truncation
        max_persons: Maximum number of referenced persons to show
        max_notes: Maximum number of editorial notes to show

    Returns:
        Formatted markdown string
    """

    parts = [f"# {letter.title}\n"]

    # Metadata section
    metadata_lines = [f"**ID:** {letter.id}"]
    if letter.idno:
        metadata_lines.append(f"**Letter No:** {letter.idno}")

    if letter.sender:
        sender_info = letter.sender.person_name or "Unknown"
        if letter.sender.place_name:
            sender_info += f" ({letter.sender.place_name})"
        if letter.sender.date:
            metadata_lines.append(f"**Date:** {letter.sender.date}")
        metadata_lines.append(f"**From:** {sender_info}")

    if letter.receiver:
        metadata_lines.append(f"**To:** {letter.receiver.person_name or 'Unknown'}")

    if letter.source:
        if letter.source.institution:
            metadata_lines.append(f"**Source:** {letter.source.institution}")
        if letter.source.idno:
            metadata_lines.append(f"**Signature:** {letter.source.idno}")

    if letter.url:
        metadata_lines.append(f"**URL:** {letter.url}")

    parts.append("\n".join(metadata_lines) + "\n")

    # Manuscript status warning
    if letter.manuscript_status == "notExtant":
        parts.append(
            "\n> ⚠️ **Inferred Letter**: Manuscript not preserved. "
            "Only metadata available.\n"
        )

    # Correspondence note
    if letter.note:
        parts.append(f"\n**Note:** {letter.note}\n")

    # Abstract (for letters without full text)
    if letter.abstract:
        parts.append(f"\n## Abstract\n\n{letter.abstract}\n")

    # Facsimiles
    if letter.facsimiles:
        parts.append("\n## Facsimiles\n")
        for i, facs_url in enumerate(letter.facsimiles, 1):
            parts.append(f"- [Page {i}]({facs_url})")

    # Referenced persons and places
    if letter.referenced_persons:
        parts.append("\n## Mentioned Persons\n")
        persons_to_show = letter.referenced_persons[:max_persons]
        parts.extend(
            f"- {person['name']} ({person['id']})" for person in persons_to_show
        )
        if len(letter.referenced_persons) > max_persons:
            parts.append(
                f"- ... and {len(letter.referenced_persons) - max_persons} more"
            )

    if letter.referenced_places:
        parts.append("\n## Mentioned Places\n")
        parts.extend(
            f"- {place['name']} ({place['id']})" for place in letter.referenced_places
        )

    # Editorial notes
    if letter.editorial_notes:
        parts.append("\n## Editorial Notes\n")
        notes_to_show = letter.editorial_notes[:max_notes]
        parts.extend(f"- {note}" for note in notes_to_show)
        if len(letter.editorial_notes) > max_notes:
            parts.append(f"- ... and {len(letter.editorial_notes) - max_notes} more")

    # Body text
    if letter.opener:
        parts.append(f"\n## Letter Opening\n\n{letter.opener}\n")

    if letter.body_text:
        text = letter.body_text
        if len(text) > max_text_length:
            text = text[:max_text_length] + "\n\n[... Text truncated ...]"
        parts.append(f"\n## Letter Body\n\n{text}\n")

    if letter.closer:
        parts.append(f"\n## Letter Closing\n\n{letter.closer}")

    return "\n".join(parts)
