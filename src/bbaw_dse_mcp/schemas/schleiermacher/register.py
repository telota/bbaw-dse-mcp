"""
Schemas for Schleiermacher Digital register entries.

This module provides Pydantic schemas for the person register in the Schleiermacher edition.
"""

from pydantic import BaseModel, Field


# ==================== DOCUMENT MENTIONS ====================


class DocumentMention(BaseModel):
    """Reference to a document that mentions an entity."""

    id: str = Field(description="Document ID (xml:id)")
    title: str = Field(description="Document title or heading")
    date: str | None = Field(default=None, description="Document date (ISO or display)")
    doc_type: str = Field(
        description="Document type: 'letter', 'diary', 'lecture', 'document'"
    )
    mention_type: str = Field(
        default="text",
        description="Where mentioned: 'text' (in main content) or 'comment' (in annotations)",
    )


class CorrespondenceSummary(BaseModel):
    """Summary of correspondence with a person."""

    person_id: str = Field(description="Person ID in the register")
    letters_as_sender: int = Field(
        default=0, description="Count of letters sent by this person"
    )
    letters_as_recipient: int = Field(
        default=0, description="Count of letters received by this person"
    )
    total_letters: int = Field(default=0, description="Total correspondence count")


class MentionsSummary(BaseModel):
    """Summary of all mentions of an entity across editions."""

    correspondence: CorrespondenceSummary | None = Field(
        default=None,
        description="Correspondence statistics (for persons only)",
    )
    letters: list[DocumentMention] = Field(
        default_factory=list,
        description="Letters mentioning this entity (max 20)",
    )
    diaries: list[DocumentMention] = Field(
        default_factory=list,
        description="Diary entries mentioning this entity (max 20)",
    )
    lectures: list[DocumentMention] = Field(
        default_factory=list,
        description="Lectures mentioning this entity (max 20)",
    )
    total_letter_mentions: int = Field(
        default=0, description="Total count of letter mentions (may exceed list)"
    )
    total_diary_mentions: int = Field(
        default=0, description="Total count of diary mentions (may exceed list)"
    )
    total_lecture_mentions: int = Field(
        default=0, description="Total count of lecture mentions (may exceed list)"
    )


# ==================== PERSON REGISTER ====================
class PersonName(BaseModel):
    """Person name components from persName[@type='reg']."""

    surname: str | None = Field(default=None, description="Last name (surname)")
    forename: str | None = Field(
        default=None,
        description="First name(s) - full text including nested <name type='used'> markup",
    )
    forename_used: str | None = Field(
        default=None,
        description="The 'used' part of forename if specified (name[@type='used'] within forename)",
    )
    full_name: str = Field(description="Full display name as string")


class AlternativeName(BaseModel):
    """Alternative name from persName[@type='alt']."""

    surname: str | None = Field(default=None, description="Alternative surname")
    forename: str | None = Field(default=None, description="Alternative forename")
    name: str | None = Field(default=None, description="Alternative name (generic)")
    is_birthname: bool = Field(
        default=False, description="Whether this is a maiden/birth name"
    )
    full_name: str = Field(description="Full alternative name as string")


class PersonEntry(BaseModel):
    """Person entry from the register."""

    id: str = Field(description="xml:id of the person entry")
    name: PersonName = Field(description="Main name (persName[@type='reg'])")
    birth: str | None = Field(default=None, description="Birth date and place")
    death: str | None = Field(default=None, description="Death date and place")
    gnd: str | None = Field(
        default=None, description="GND authority file URI (idno[@type='uri'])"
    )
    alternative_names: list[AlternativeName] = Field(
        default_factory=list,
        description="Alternative names (persName[@type='alt'])",
    )
    note: str | None = Field(default=None, description="Biographical note")
    wedding_date: str | None = Field(
        default=None, description="Wedding date from event[@type='wedding']"
    )
    mentions: MentionsSummary | None = Field(
        default=None,
        description="Summary of mentions across letters, diaries, lectures (optional, fetched when include_mentions=True)",
    )


class PersonGroup(BaseModel):
    """Family or group container from listPerson[@type='group']."""

    head: str = Field(description="Family/group name from <head> element")
    persons: list[PersonEntry] = Field(
        description="List of person entries in this family group"
    )


# ==================== BIBLICAL REFERENCES ====================


class BiblicalReference(BaseModel):
    """Reference to a biblical passage in a document."""

    doc_id: str = Field(description="Document ID (ref/@doc)")
    doc_type: str = Field(
        description="Document type (ref/@type, e.g., 'letter fs', 'lecture fs', 'diary fs')"
    )
    place: str = Field(
        description="Biblical reference location (ref/@place, e.g., 'Gen 2,9')"
    )
    note_id: str | None = Field(
        default=None, description="Note ID if applicable (ref/@note-id)"
    )
    original_text: str | None = Field(
        default=None, description="Original text from document (ref/@orig)"
    )
    doc_title: str = Field(description="Document title (ref text content)")


class BiblicalBook(BaseModel):
    """Biblical book entry with metadata and references."""

    id: str = Field(description="xml:id of the item")
    number: int = Field(description="Sequential book number (item/@n)")
    idno: str = Field(
        description="Standard book abbreviation (idno, e.g., 'Gen', 'Mt')"
    )
    name: str | None = Field(
        default=None, description="Full book name (label[@unit='name'])"
    )
    abbreviation: str | None = Field(
        default=None, description="Abbreviation (label[@unit='abk'])"
    )
    alternative_name: str | None = Field(
        default=None, description="Alternative name (label[@unit='name2'])"
    )
    alternative_abbreviation: str | None = Field(
        default=None, description="Alternative abbreviation (label[@unit='abk2'])"
    )
    group_a: str | None = Field(
        default=None,
        description="Primary group (label[@unit='gruppea'], e.g., 'Pentateuch', 'Propheten')",
    )
    group_b: str | None = Field(
        default=None,
        description="Secondary group (label[@unit='gruppeb'], e.g., 'große Propheten')",
    )
    group_c: str | None = Field(
        default=None, description="Tertiary group (label[@unit='gruppec'])"
    )
    testament: str = Field(
        description="Testament type: 'AT' (Altes Testament), 'NT' (Neues Testament), or 'AP' (Apokryphen)"
    )
    references: list[BiblicalReference] = Field(
        default_factory=list,
        description="List of document references to this biblical book",
    )


# ==================== GLOSSARY ====================


class GlossaryEntry(BaseModel):
    """Glossary entry for terms and concepts."""

    id: str = Field(description="xml:id of the glossary item")
    label: str = Field(description="Main term (label[@type='reg'])")
    alternative_labels: list[str] = Field(
        default_factory=list,
        description="Alternative terms or spellings (label[@type='alt'])",
    )
    language: str | None = Field(
        default=None, description="Language code (xml:lang, e.g., 'deu')"
    )
    description: str | None = Field(
        default=None, description="Short description (desc)"
    )
    description_responsible: str | None = Field(
        default=None, description="Responsible editor for description (desc/@resp)"
    )
    interpretation: str | None = Field(
        default=None,
        description="Category/interpretation ID (interp/@id, e.g., '#christliche_sitte', '#instrument')",
    )
    note: str | None = Field(
        default=None, description="Detailed explanatory note (note text content)"
    )
    note_responsible: str | None = Field(
        default=None, description="Responsible editor for note (note/@resp)"
    )
    source_paragraphs: list[str] = Field(
        default_factory=list,
        description="Source information paragraphs (p[@type='source'])",
    )


# ==================== PLACE REGISTER ====================


class PlaceEntry(BaseModel):
    """Place entry from the register."""

    id: str = Field(description="xml:id of the place entry")
    name: str = Field(description="Place name (placeName[@type='reg'])")
    place_type: str | None = Field(
        default=None,
        description="Type: street, building, park, district, others (place/@type)",
    )
    geonames_uri: str | None = Field(
        default=None, description="Geonames URI (idno[@type='uri'])"
    )
    alternative_names: list[str] = Field(
        default_factory=list,
        description="Alternative place names (placeName[@type='alt'])",
    )
    note: str | None = Field(
        default=None, description="Additional information about the place"
    )
    sub_places: list["PlaceEntry"] = Field(
        default_factory=list,
        description="Nested sub-places from listPlace (e.g., buildings, streets, districts within a city)",
    )
    mentions: MentionsSummary | None = Field(
        default=None,
        description="Summary of mentions across letters, diaries, lectures (optional)",
    )


# ==================== WORKS REGISTER ====================


class WorkAuthor(BaseModel):
    """Author information from bibl/author/persName."""

    key: str | None = Field(
        default=None, description="Person ID reference (persName/@key)"
    )
    surname: str | None = Field(default=None, description="Author surname")
    forename: str | None = Field(default=None, description="Author forename")
    full_name: str | None = Field(
        default=None, description="Full name if not structured"
    )


class WorkEntry(BaseModel):
    """Bibliographic work entry from the register."""

    id: str = Field(description="xml:id of the bibl entry")
    author: WorkAuthor | None = Field(
        default=None, description="Author information (author/persName)"
    )
    title: str = Field(description="Work title")
    date: str | None = Field(default=None, description="Publication date")
    pub_place: str | None = Field(
        default=None, description="Publication place (pubPlace)"
    )
    pub_place_key: str | None = Field(
        default=None, description="Publication place ID (pubPlace/@key)"
    )
    note: str | None = Field(
        default=None, description="Additional notes about the work"
    )


class WorkGroup(BaseModel):
    """Group of works by same author from listBibl[@type='group']."""

    head: str = Field(description="Author name from <head> element")
    works: list[WorkEntry] = Field(
        description="List of bibliographic entries for this author"
    )
