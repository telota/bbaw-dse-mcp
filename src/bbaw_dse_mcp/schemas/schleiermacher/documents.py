"""Schleiermacher Digital specific schemas."""

from pydantic import BaseModel, Field

from bbaw_dse_mcp.schemas.base.tei import (
    CorrespondenceAction,
    Editor,
    SourceDescription,
)


class Letter(BaseModel):
    """Complete letter metadata from TEI XML."""

    id: str = Field(description="Document ID (xml:id)")
    idno: str | None = Field(default=None, description="Letter number (e.g., 3413a)")
    title: str = Field(description="Letter title")

    # Correspondence metadata
    sender: CorrespondenceAction | None = Field(
        default=None, description="Sender information"
    )
    receiver: CorrespondenceAction | None = Field(
        default=None, description="Receiver information"
    )

    # Editors
    editors: list[Editor] = Field(default_factory=list, description="List of editors")

    # Source
    source: SourceDescription | None = Field(
        default=None, description="Source description"
    )

    # Notes
    note: str | None = Field(
        default=None, description="Editorial note on dating/context"
    )

    # Abstract and manuscript status
    abstract: str | None = Field(
        default=None, description="Summary (for inferred letters)"
    )
    manuscript_status: str | None = Field(
        default=None,
        description="Manuscript status: 'notExtant', 'manuscript', 'copy', etc.",
    )

    # Letter text
    opener: str | None = Field(
        default=None, description="Letter opening (address, date, salutation)"
    )
    body_text: str | None = Field(
        default=None, description="Main text of the letter (all paragraphs)"
    )
    closer: str | None = Field(
        default=None, description="Letter closing (valediction, signature)"
    )

    # Structured annotations
    referenced_persons: list[dict[str, str]] = Field(
        default_factory=list, description="Persons mentioned in text with ID and name"
    )
    referenced_places: list[dict[str, str]] = Field(
        default_factory=list, description="Places mentioned in text with ID and name"
    )
    editorial_notes: list[str] = Field(
        default_factory=list,
        description="Editorial comments and annotations on the text",
    )

    # Facsimiles
    facsimiles: list[str] = Field(
        default_factory=list, description="URLs to facsimile images"
    )

    # URL
    url: str | None = Field(
        default=None,
        description="URL to the letter on schleiermacher-digital.de (deprecated, use citation_url)",
    )

    citation_url: str = Field(
        description="Canonical URL for citing this letter. Use this EXACT URL, do not construct your own."
    )
