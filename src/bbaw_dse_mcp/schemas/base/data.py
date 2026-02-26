"""Base schemas for digital editions."""

from pydantic import BaseModel, Field


class Person(BaseModel):
    """Person from an edition register."""

    id: str = Field(description="Unique ID (local ID)")
    name: str = Field(description="Full name")
    forename: str | None = Field(default=None, description="First name")
    surname: str | None = Field(default=None, description="Last name")
    birth_date: str | None = Field(default=None, description="Birth date (ISO 8601)")
    death_date: str | None = Field(default=None, description="Death date (ISO 8601)")
    gnd: str | None = Field(default=None, description="GND number")
    note: str | None = Field(default=None, description="Biographical note")


class Place(BaseModel):
    """Place from an edition register."""

    id: str = Field(description="Unique ID (e.g., Geonames, local ID)")
    name: str = Field(description="Place name")
    country: str | None = Field(default=None, description="Country")
    region: str | None = Field(default=None, description="Region/State")
    geonames: str | None = Field(default=None, description="Geonames ID")
    coordinates: tuple[float, float] | None = Field(
        default=None, description="Coordinates (lat, lon)"
    )


class Work(BaseModel):
    """Work from an edition register."""

    id: str = Field(description="Unique ID")
    title: str = Field(description="Work title")
    author: str | None = Field(default=None, description="Author")
    year: int | None = Field(default=None, description="Publication year")
    description: str | None = Field(default=None, description="Description")


class Collection(BaseModel):
    """Information about an eXist-db Collection."""

    path: str = Field(description="Full path to the collection")
    document_count: int = Field(description="Number of documents in the collection")
    collections: list[str] = Field(
        default_factory=list, description="List of subcollections"
    )
