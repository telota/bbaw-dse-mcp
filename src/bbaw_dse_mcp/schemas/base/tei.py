"""Shared TEI (Text Encoding Initiative) component schemas.

These schemas represent common TEI elements used across different digital editions.
"""

from pydantic import BaseModel, Field


class Editor(BaseModel):
    """Editor information from TEI header."""

    surname: str | None = Field(default=None, description="Last name")
    forename: str | None = Field(default=None, description="First name")
    gnd: str | None = Field(default=None, description="GND reference")


class CorrespondenceAction(BaseModel):
    """Correspondence action (sending or receiving) from TEI correspDesc."""

    person_name: str | None = Field(default=None, description="Person name")
    person_key: str | None = Field(default=None, description="Person ID (key)")
    place_name: str | None = Field(default=None, description="Place name")
    place_key: str | None = Field(default=None, description="Place ID (key)")
    date: str | None = Field(default=None, description="Date (ISO 8601)")
    date_cert: str | None = Field(
        default=None, description="Date certainty (high/medium/low)"
    )


class SourceDescription(BaseModel):
    """Source description from TEI msDesc (manuscript description)."""

    institution: str | None = Field(default=None, description="Holding institution")
    repository: str | None = Field(default=None, description="Archive/Repository")
    collection: str | None = Field(default=None, description="Collection")
    idno: str | None = Field(
        default=None, description="Signature/Identification number"
    )
