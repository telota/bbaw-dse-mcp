"""Schemas for correspSearch API responses."""

from pydantic import BaseModel, Field


class Correspondent(BaseModel):
    """A correspondent (sender or receiver) in a letter."""

    name: str | None = Field(default=None, description="Name of the correspondent")
    gnd: str | None = Field(
        default=None, description="GND identifier (without URL prefix)"
    )
    authority_uri: str | None = Field(
        default=None, description="Full authority URI (typically GND)"
    )


class Place(BaseModel):
    """A place (sending or receiving location)."""

    name: str | None = Field(default=None, description="Name of the place")
    geonames_id: str | None = Field(
        default=None, description="GeoNames ID (without URL prefix)"
    )
    geonames_uri: str | None = Field(default=None, description="Full GeoNames URI")


class CorrespSearchLetter(BaseModel):
    """Letter metadata from correspSearch API (CMIF format)."""

    id: str = Field(description="Unique letter ID from correspSearch")
    title: str = Field(description="Letter title (constructed from sender/receiver)")
    date: str | None = Field(default=None, description="Date of the letter (ISO 8601)")
    date_text: str | None = Field(
        default=None, description="Human-readable date text if available"
    )
    date_when: str | None = Field(
        default=None, description="Exact date (@when attribute)"
    )
    date_from: str | None = Field(
        default=None, description="Range start date (@from attribute)"
    )
    date_to: str | None = Field(
        default=None, description="Range end date (@to attribute)"
    )
    date_not_before: str | None = Field(
        default=None, description="Earliest possible date (@notBefore attribute)"
    )
    date_not_after: str | None = Field(
        default=None, description="Latest possible date (@notAfter attribute)"
    )
    sender: Correspondent | None = Field(default=None, description="Sender information")
    receiver: Correspondent | None = Field(
        default=None, description="Receiver information"
    )
    send_place: Place | None = Field(
        default=None, description="Place where letter was sent from"
    )
    receive_place: Place | None = Field(
        default=None, description="Place where letter was received"
    )
    edition_id: str | None = Field(
        default=None, description="Edition/publication identifier"
    )
    edition_title: str | None = Field(
        default=None, description="Title of the edition/publication"
    )
    source_url: str | None = Field(
        default=None, description="URL to the letter in the source edition"
    )
    cmif_url: str | None = Field(
        default=None, description="URL of the CMIF file containing this letter"
    )


class EditionInfo(BaseModel):
    """Information about an edition registered in correspSearch."""

    id: str = Field(description="Edition UUID in correspSearch")
    title: str = Field(description="Title of the edition")
    editor: str | None = Field(default=None, description="Editor(s) of the edition")
    publisher: str | None = Field(default=None, description="Publisher")
    url: str | None = Field(default=None, description="URL to the edition")
    cmif_url: str | None = Field(default=None, description="URL to the CMIF file")
    license: str | None = Field(default=None, description="License information")
    letter_count: int | None = Field(
        default=None, description="Number of letters in this edition"
    )


class CorrespSearchResult(BaseModel):
    """Result set from correspSearch API with pagination info."""

    letters: list[CorrespSearchLetter] = Field(
        default_factory=list, description="List of letters matching the query"
    )
    total_count: int = Field(
        default=0, description="Total number of matches (may exceed returned letters)"
    )
    page: int = Field(default=1, description="Current page number (1-indexed)")
    has_next: bool = Field(default=False, description="Whether more pages exist")
    next_page_url: str | None = Field(
        default=None, description="URL for the next page of results"
    )


class CorrespondentNetwork(BaseModel):
    """Correspondence network statistics for a person."""

    person_gnd: str = Field(description="GND identifier of the focal person")
    person_name: str | None = Field(default=None, description="Name of the person")
    correspondents: list[dict] = Field(
        default_factory=list,
        description="List of correspondents with letter counts",
    )
    total_letters: int = Field(
        default=0, description="Total number of letters involving this person"
    )
    date_range: str | None = Field(
        default=None, description="Date range of correspondence (e.g., 1800-1834)"
    )
