"""Helper functions for generating citation URLs.

This module provides utilities for constructing canonical citation URLs
for documents in the Schleiermacher Digital edition.
"""


def get_schleiermacher_citation_url(
    document_id: str, doc_type: str | None = None  # noqa: ARG001
) -> str:
    """Generate canonical citation URL for Schleiermacher Digital documents.

    The URL format is simple: https://schleiermacher-digital.de/{document_id}
    Document IDs follow the pattern: S + 7 digits (e.g., S0006428)

    Args:
        document_id: Document xml:id (e.g., "S0006428")
        doc_type: Document type (not used, kept for compatibility)

    Returns:
        Canonical URL for citing this document

    Examples:
        >>> get_schleiermacher_citation_url("S0006428")
        "https://schleiermacher-digital.de/S0006428"
        >>> get_schleiermacher_citation_url("S0007791", "letter fs")
        "https://schleiermacher-digital.de/S0007791"
    """
    base_url = "https://schleiermacher-digital.de"
    return f"{base_url}/{document_id}"
