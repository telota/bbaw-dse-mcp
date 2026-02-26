"""Document schemas for digital editions."""

from pydantic import BaseModel, Field


class RawDocument(BaseModel):
    """Raw XML document from the database (unparsed)."""

    id: str = Field(description="Document identifier (xml:id or filename)")
    xml: str = Field(description="Raw XML content")
    path: str | None = Field(default=None, description="File path in database")


class Document(BaseModel):
    """Generic document (letter, diary, lecture, etc.)."""

    id: str = Field(description="Unique document ID")
    doc_type: str = Field(
        description="Document type (letter, diary, lecture, document)"
    )
    title: str = Field(description="Document title")
    doc_date: str | None = Field(default=None, description="Date (ISO 8601)")
    author: str | None = Field(default=None, description="Author")
    author_id: str | None = Field(default=None, description="Author ID")
    content: str | None = Field(default=None, description="Full text or excerpt")
    tei_xml: str | None = Field(default=None, description="Original TEI-XML")
    url: str | None = Field(default=None, description="URL to online edition")
    metadata: dict[str, str] | None = Field(
        default=None, description="Additional metadata"
    )


class Letter(BaseModel):
    """Letter metadata."""

    id: str = Field(description="Unique letter ID - use this EXACT value for citations")
    title: str = Field(description="Letter title/subject")
    date: str | None = Field(default=None, description="Date (ISO 8601)")
    sender: str | None = Field(default=None, description="Sender (name)")
    sender_id: str | None = Field(default=None, description="Sender (ID)")
    receiver: str | None = Field(default=None, description="Receiver (name)")
    receiver_id: str | None = Field(default=None, description="Receiver (ID)")
    send_place: str | None = Field(default=None, description="Sending location (name)")
    send_place_id: str | None = Field(default=None, description="Sending location (ID)")
    url: str | None = Field(default=None, description="URL to online edition")
    citation_url: str = Field(
        description="Canonical URL for citing this letter. Use this EXACT URL, do not construct your own."
    )


class Passage(BaseModel):
    """A text passage from a document."""

    position: int = Field(description="Position/index of this passage")
    text: str = Field(description="Text content of the passage")
    div_n: str | None = Field(
        default=None, description="Division number (@n attribute)"
    )
    page_n: str | None = Field(default=None, description="Page number (from pb/@n)")
    para_num: int | None = Field(
        default=None, description="Paragraph number in document for location reference"
    )
    highlight_offsets: list[tuple[int, int]] | None = Field(
        default=None, description="Character offsets for match highlights"
    )
