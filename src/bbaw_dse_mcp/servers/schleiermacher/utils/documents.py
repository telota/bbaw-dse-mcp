"""Generic document parsing and formatting for Schleiermacher Digital.

This module provides parsers and formatters for non-letter documents
such as lectures, diary entries, and other TEI documents.
"""

from dataclasses import dataclass

from lxml import etree

from bbaw_dse_mcp.config.base import TEI_NS as NS
from bbaw_dse_mcp.servers.schleiermacher.utils.citations import (
    get_schleiermacher_citation_url,
)
from bbaw_dse_mcp.utils.tei import (
    clean_text,
    extract_text,
    strip_processing_instructions,
)


@dataclass
class GenericDocument:
    """Represents a generic TEI document (lecture, diary, etc.)."""

    id: str
    title: str | None = None
    doctype: str | None = None
    date: str | None = None
    author: str | None = None
    editor: str | None = None
    body_text: str | None = None
    abstract: str | None = None
    source_info: str | None = None


def parse_generic_document(xml_str: str, document_id: str) -> GenericDocument:
    """Parse a generic TEI document (lecture, diary, etc.).

    Args:
        xml_str: Raw XML string of the document
        document_id: The xml:id of the document

    Returns:
        GenericDocument with extracted content
    """
    # Clean XML
    try:
        xml_str = strip_processing_instructions(xml_str)
    except etree.XMLSyntaxError:
        pass  # Try to parse anyway

    root = etree.fromstring(xml_str.encode("utf-8"))

    # Extract basic metadata
    doctype = root.get("{http://www.telota.de}doctype")

    # Title from titleStmt
    title_elem = root.find(
        ".//tei:teiHeader//tei:titleStmt/tei:title[@type='main']", NS
    )
    if title_elem is None:
        title_elem = root.find(".//tei:teiHeader//tei:titleStmt/tei:title", NS)
    title = extract_text(title_elem)

    # Author
    author_elem = root.find(
        ".//tei:teiHeader//tei:titleStmt/tei:author/tei:persName", NS
    )
    if author_elem is None:
        author_elem = root.find(".//tei:teiHeader//tei:titleStmt/tei:author", NS)
    author = extract_text(author_elem)

    # Editor
    editor_elem = root.find(
        ".//tei:teiHeader//tei:titleStmt/tei:editor/tei:persName", NS
    )
    if editor_elem is None:
        editor_elem = root.find(".//tei:teiHeader//tei:titleStmt/tei:editor", NS)
    editor = extract_text(editor_elem)

    # Date - try various locations
    date = None
    for date_path in [
        ".//tei:teiHeader//tei:creation/tei:date",
        ".//tei:teiHeader//tei:publicationStmt/tei:date",
        ".//tei:teiHeader//tei:sourceDesc//tei:date",
    ]:
        date_elem = root.find(date_path, NS)
        if date_elem is not None:
            date = (
                date_elem.get("when")
                or date_elem.get("notBefore")
                or extract_text(date_elem)
            )
            if date:
                break

    # Abstract/summary
    abstract_elem = root.find(".//tei:teiHeader//tei:abstract", NS)
    abstract = extract_text(abstract_elem)

    # Body text
    body_elem = root.find(".//tei:text/tei:body", NS)
    body_text = _extract_body_content(body_elem)

    # Source info
    source_elem = root.find(".//tei:teiHeader//tei:sourceDesc", NS)
    source_info = extract_text(source_elem) if source_elem is not None else None

    return GenericDocument(
        id=document_id,
        title=title,
        doctype=doctype,
        date=date,
        author=author,
        editor=editor,
        body_text=body_text,
        abstract=abstract,
        source_info=source_info,
    )


def _extract_body_content(body_elem: etree._Element | None) -> str | None:
    """Extract body content from TEI body element.

    Handles various TEI structures including divs, paragraphs, etc.

    Args:
        body_elem: TEI body element

    Returns:
        Extracted body text
    """
    if body_elem is None:
        return None

    parts = []

    # Try to extract structured content first (divs with heads)
    divs = body_elem.findall(".//tei:div", NS)

    if divs:
        for div in divs:
            # Get division heading if any
            head = div.find("tei:head", NS)
            if head is not None:
                head_text = extract_text(head)
                if head_text:
                    # Check for @n attribute for section number
                    n_attr = div.get("n")
                    if n_attr:
                        parts.append(f"### {n_attr}. {head_text}")
                    else:
                        parts.append(f"### {head_text}")

            # Get paragraphs in this div
            for p in div.findall("tei:p", NS):
                p_text = extract_text(p)
                if p_text:
                    parts.append(clean_text(p_text) or p_text)
    else:
        # Fallback: extract all paragraphs
        for p in body_elem.findall(".//tei:p", NS):
            p_text = extract_text(p)
            if p_text:
                parts.append(clean_text(p_text) or p_text)

    if not parts:
        # Last resort: get all text
        return extract_text(body_elem)

    return "\n\n".join(parts)


def format_generic_document_as_markdown(doc: GenericDocument) -> str:
    """Format a generic document as markdown.

    Args:
        doc: GenericDocument to format

    Returns:
        Markdown-formatted document
    """
    lines = []

    # Header with title
    if doc.title:
        lines.append(f"# {doc.title}")
    else:
        lines.append(f"# Document {doc.id}")

    lines.append("")

    # Metadata section
    lines.append("## Metadata")
    lines.append("")
    lines.append(f"- **ID:** {doc.id}")
    if doc.doctype:
        # Make doctype more readable
        doctype_display = doc.doctype.replace(" fs", "").replace("_", " ").title()
        lines.append(f"- **Type:** {doctype_display}")
    if doc.date:
        lines.append(f"- **Date:** {doc.date}")
    if doc.author:
        lines.append(f"- **Author:** {doc.author}")
    if doc.editor:
        lines.append(f"- **Editor:** {doc.editor}")

    # Citation URL
    citation_url = get_schleiermacher_citation_url(doc.id, doc.doctype or "document")
    if citation_url:
        lines.append(f"- **Online:** [{citation_url}]({citation_url})")

    lines.append("")

    # Abstract if present
    if doc.abstract:
        lines.append("## Abstract")
        lines.append("")
        lines.append(doc.abstract)
        lines.append("")

    # Main content
    lines.append("## Content")
    lines.append("")

    if doc.body_text:
        lines.append(doc.body_text)
    else:
        lines.append("*No text content available.*")

    lines.append("")

    # Source info if present
    if doc.source_info:
        lines.append("## Source")
        lines.append("")
        lines.append(doc.source_info)
        lines.append("")

    return "\n".join(lines)
