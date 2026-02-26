"""Schleiermacher Digital API response schemas."""

from pydantic import BaseModel, Field


class DocumentListItem(BaseModel):
    """Single document in a browse list."""

    id: str = Field(description="Document ID (xml:id)")
    title: str = Field(description="Document title")
    date: str | None = Field(default=None, description="Date (ISO 8601)")
    citation_url: str = Field(
        description="Canonical URL for citing this document. Use this EXACT URL, do not construct your own."
    )


class BrowseCollectionResult(BaseModel):
    """Result of a collection browse operation."""

    collection_path: str = Field(description="Absolute collection path")
    count: int = Field(description="Number of documents found")
    documents: list[DocumentListItem] = Field(description="List of documents")
    subcollections: list[str] = Field(
        default_factory=list, description="List of subcollections"
    )
