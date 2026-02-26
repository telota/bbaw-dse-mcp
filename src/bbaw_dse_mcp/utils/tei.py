"""Universal TEI XML parsing utilities.

This module provides reusable functions for parsing TEI-encoded documents
that can be used across different digital scholarly editions.
"""

import re

from lxml import etree

from bbaw_dse_mcp.config.base import TEI_NS as NS
from bbaw_dse_mcp.schemas.base.tei import (
    CorrespondenceAction,
    Editor,
    SourceDescription,
)


def determine_doctype(xml_str: str) -> str | None:
    """Determine the document type from TEI XML string.

    Extracts the telota:doctype attribute from the root TEI element.

    Args:
        xml_str: TEI XML string

    Returns:
        Document type as string (e.g., "letter", "letter fs") or None if not found

    Example:
        >>> xml = '<TEI xmlns="http://www.tei-c.org/ns/1.0" xmlns:telota="http://www.telota.de" telota:doctype="letter fs" xml:id="S0007791">...</TEI>'
        >>> determine_doctype(xml)
        'letter fs'
    """
    try:
        root = etree.fromstring(xml_str.encode("utf-8"))
        # Extract telota:doctype attribute
        return root.get("{http://www.telota.de}doctype")

    except (etree.XMLSyntaxError, AttributeError):
        return None


def strip_processing_instructions(xml_str: str) -> str:
    """Remove all processing instructions from XML string before parsing.

    Args:
        xml_str: Raw XML string with processing instructions

    Returns:
        Cleaned XML string without processing instructions
    """
    # Parse to tree
    root = etree.fromstring(xml_str.encode("utf-8"))

    # Remove all processing instructions recursively
    for element in root.iter():
        # Remove processing instruction children
        for child in element:
            if isinstance(child, etree._ProcessingInstruction):
                element.remove(child)

    # Return cleaned XML
    return etree.tostring(root, encoding="unicode")


def extract_text(element: etree._Element | None) -> str | None:
    """Extract clean readable text from TEI element.

    - Skips: editorial notes, index entries, sic elements, processing instructions
    - Includes: corrected text (corr), expansions (ex), supplied text

    Args:
        element: TEI element to extract text from

    Returns:
        Extracted text or None if element is None or empty
    """
    if element is None:
        return None

    # Elements to skip entirely
    skip_tags = {
        f"{{{NS['tei']}}}note",
        f"{{{NS['tei']}}}index",
        f"{{{NS['tei']}}}sic",  # Skip uncorrected text
        etree.ProcessingInstruction,  # Skip <?pagina ...?> etc.
    }

    def extract_recursive(elem: etree._Element) -> list[str]:
        """Recursively extract text, respecting skip rules."""
        parts = []

        # Add element's direct text
        if elem.text:
            parts.append(elem.text)

        # Process children
        for child in elem:
            # Skip processing instructions
            if isinstance(child, etree._ProcessingInstruction):
                if child.tail:
                    parts.append(child.tail)
                continue

            # Skip certain elements
            if child.tag in skip_tags:
                # But still get tail text after skipped element
                if child.tail:
                    parts.append(child.tail)
                continue

            # For <choice>, only take <corr>, skip <sic>
            if child.tag == f"{{{NS['tei']}}}choice":
                corr = child.find("tei:corr", NS)
                if corr is not None:
                    parts.extend(extract_recursive(corr))
                # Get tail after choice
                if child.tail:
                    parts.append(child.tail)
                continue

            # For <seg type="comment">, skip the whole thing
            if child.tag == f"{{{NS['tei']}}}seg" and child.get("type") == "comment":
                # But keep tail
                if child.tail:
                    parts.append(child.tail)
                continue

            # Recursively process other elements
            parts.extend(extract_recursive(child))

            # Add tail text
            if child.tail:
                parts.append(child.tail)

        return parts

    text = "".join(extract_recursive(element)).strip()
    return text if text else None


def clean_text(text: str | None) -> str | None:
    """Clean up extracted text by normalizing whitespace.

    Args:
        text: Text to clean

    Returns:
        Cleaned text with normalized whitespace
    """
    if text is None:
        return None
    # Replace multiple whitespace/newlines with single space
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_corresp_action(
    action_elem: etree._Element | None,
) -> CorrespondenceAction | None:
    """Parse correspAction element into CorrespondenceAction model.

    Args:
        action_elem: TEI correspAction element

    Returns:
        CorrespondenceAction object or None if element is None
    """
    if action_elem is None:
        return None

    # Person
    person_elem = action_elem.find("tei:persName", NS)
    person_name = extract_text(person_elem)
    person_key = person_elem.get("key") if person_elem is not None else None

    # Place
    place_elem = action_elem.find("tei:placeName", NS)
    place_name = extract_text(place_elem)
    place_key = place_elem.get("key") if place_elem is not None else None

    # Date
    date_elem = action_elem.find("tei:date", NS)
    date = date_elem.get("when") if date_elem is not None else None
    date_cert = date_elem.get("cert") if date_elem is not None else None

    return CorrespondenceAction(
        person_name=person_name,
        person_key=person_key,
        place_name=place_name,
        place_key=place_key,
        date=date,
        date_cert=date_cert,
    )


def parse_editor(editor_elem: etree._Element) -> Editor:
    """Parse editor element into Editor model.

    Args:
        editor_elem: TEI editor element

    Returns:
        Editor object with parsed information
    """
    # Try direct children first
    surname_elem = editor_elem.find("tei:surname", NS)
    forename_elem = editor_elem.find("tei:forename", NS)

    # If not found, try within persName
    person_elem = editor_elem.find("tei:persName", NS)
    if person_elem is not None:
        if surname_elem is None:
            surname_elem = person_elem.find("tei:surname", NS)
        if forename_elem is None:
            forename_elem = person_elem.find("tei:forename", NS)

    surname = extract_text(surname_elem)
    forename = extract_text(forename_elem)

    # GND from persName/@ref
    gnd = person_elem.get("ref") if person_elem is not None else None

    return Editor(surname=surname, forename=forename, gnd=gnd)


def parse_source(source_elem: etree._Element | None) -> SourceDescription | None:
    """Parse sourceDesc element into SourceDescription model.

    Args:
        source_elem: TEI sourceDesc element

    Returns:
        SourceDescription object or None if element is None or has no msIdentifier
    """
    if source_elem is None:
        return None

    ms_ident = source_elem.find(".//tei:msIdentifier", NS)
    if ms_ident is None:
        return None

    institution = extract_text(ms_ident.find("tei:institution", NS))
    repository = extract_text(ms_ident.find("tei:repository", NS))
    collection = extract_text(ms_ident.find("tei:collection", NS))
    idno = extract_text(ms_ident.find("tei:idno", NS))

    return SourceDescription(
        institution=institution,
        repository=repository,
        collection=collection,
        idno=idno,
    )
