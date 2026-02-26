"""Response schemas for common tools."""

from pydantic import BaseModel, Field


class DatabaseStatus(BaseModel):
    """Database connection status."""

    status: str = Field(description="Connection status (connected/error)")
    version: str | None = Field(default=None, description="eXist-db version")
    base_url: str = Field(description="Base URL of the database")
    app_path: str = Field(description="Application collection path")
    data_path: str = Field(
        description="Data collection path (where documents are stored)"
    )
    error: str | None = Field(
        default=None, description="Error message if there are problems"
    )


class SearchResult(BaseModel):
    """Search result from an edition."""

    document_id: str = Field(
        description="Document ID - use this EXACT value for citations"
    )
    title: str = Field(description="Title")
    kwic_snippets: list[str] | None = Field(
        default=None, description="Keyword-in-context snippets from document"
    )
    score: float | None = Field(default=None, description="Relevance score")
    date: str | None = Field(default=None, description="Document date")
    type: str | None = Field(default=None, description="Document type")
    citation_url: str = Field(
        description="Canonical URL for citing this document. Use this EXACT URL, do not construct your own."
    )


class CorrespondentStats(BaseModel):
    """Statistics about correspondents."""

    person_id: str = Field(description="Person ID")
    person_name: str = Field(description="Name")
    letters_sent: int = Field(default=0, description="Number of letters sent")
    letters_received: int = Field(default=0, description="Number of letters received")
    total: int = Field(default=0, description="Total number of letters")
    years: list[int] = Field(
        default_factory=list, description="Years with correspondence"
    )


class CollectionStats(BaseModel):
    """Statistics about a collection."""

    path: str = Field(description="Full path to the collection")
    total_files: int = Field(description="Total number of files")
    tei_documents: int = Field(description="Number of TEI documents")


class CollectionContents(BaseModel):
    """Contents of a collection (files and subcollections)."""

    collection_path: str = Field(description="Full path to the collection")
    file_count: int = Field(description="Number of files returned (limited)")
    total_files: int = Field(description="Total number of files in collection")
    files: list[str] = Field(default_factory=list, description="List of file names")
    subcollections: list[str] = Field(
        default_factory=list, description="List of subcollection names"
    )


class FileInfo(BaseModel):
    """Metadata information about a file."""

    id: str = Field(description="Document xml:id")
    title: str = Field(description="Document title")
    date: str | None = Field(default=None, description="Document date (ISO 8601)")
    path: str = Field(description="Full path to the file in database")
    mime_type: str = Field(description="MIME type of the file")
    size_bytes: int = Field(description="File size in bytes")
    modified: str = Field(description="Last modification timestamp")


class GNDIdLabel(BaseModel):
    """GND ID and Label pair."""

    id: str | None = None
    label: str | None = None


class GNDCollection(BaseModel):
    """GND Collection info."""

    id: str | None = None
    abbr: str | None = None
    name: str | None = None
    publisher: str | None = None
    icon: str | None = None


class GNDSameAs(BaseModel):
    """GND SameAs entry."""

    id: str | None = None
    collection: GNDCollection | None = None


class GNDNameEntity(BaseModel):
    """GND Name components."""

    forename: list[str] | None = None
    surname: list[str] | None = None
    prefix: list[str] | None = None
    personal_name: list[str] | None = Field(default=None, alias="personalName")


class GNDLicense(BaseModel):
    """GND License info."""

    id: str | None = None
    name: str | None = None
    abbr: str | None = None


class GNDDepiction(BaseModel):
    """GND Depiction info."""

    id: str | None = None
    url: str | None = None
    thumbnail: str | None = None
    publisher: str | None = None
    creator_name: list[str] | None = Field(default=None, alias="creatorName")
    license: list[GNDLicense] | None = None


class LobidGNDResponse(BaseModel):
    """Response from Lobid GND API."""

    id: str = Field(description="The URI of the entity")
    gnd_identifier: str = Field(alias="gndIdentifier", description="The GND identifier")
    preferred_name: str = Field(
        alias="preferredName", description="The preferred name of the entity"
    )
    type: list[str] = Field(default_factory=list, description="Entity types")

    # Core Data
    date_of_birth: list[str] | None = Field(default=None, alias="dateOfBirth")
    date_of_death: list[str] | None = Field(default=None, alias="dateOfDeath")
    gender: list[GNDIdLabel] | None = None

    # Places
    place_of_birth: list[GNDIdLabel] | None = Field(default=None, alias="placeOfBirth")
    place_of_death: list[GNDIdLabel] | None = Field(default=None, alias="placeOfDeath")
    place_of_activity: list[GNDIdLabel] | None = Field(
        default=None, alias="placeOfActivity"
    )
    geographic_area_code: list[GNDIdLabel] | None = Field(
        default=None, alias="geographicAreaCode"
    )

    # Profession & Subject
    profession_or_occupation: list[GNDIdLabel] | None = Field(
        default=None, alias="professionOrOccupation"
    )
    gnd_subject_category: list[GNDIdLabel] | None = Field(
        default=None, alias="gndSubjectCategory"
    )

    # Biographical
    biographical_or_historical_information: list[str] | None = Field(
        default=None, alias="biographicalOrHistoricalInformation"
    )

    # Relationships
    familial_relationship: list[GNDIdLabel] | None = Field(
        default=None, alias="familialRelationship"
    )
    has_spouse: list[GNDIdLabel] | None = Field(default=None, alias="hasSpouse")
    has_child: list[GNDIdLabel] | None = Field(default=None, alias="hasChild")
    has_parent: list[GNDIdLabel] | None = Field(default=None, alias="hasParent")
    has_sibling: list[GNDIdLabel] | None = Field(default=None, alias="hasSibling")
    has_aunt_uncle: list[GNDIdLabel] | None = Field(default=None, alias="hasAuntUncle")
    has_friend: list[GNDIdLabel] | None = Field(default=None, alias="hasFriend")
    acquaintanceship_or_friendship: list[GNDIdLabel] | None = Field(
        default=None, alias="acquaintanceshipOrFriendship"
    )
    professional_relationship: list[GNDIdLabel] | None = Field(
        default=None, alias="professionalRelationship"
    )
    related_work: list[GNDIdLabel] | None = Field(default=None, alias="relatedWork")

    # Names
    variant_name: list[str] | None = Field(default=None, alias="variantName")
    preferred_name_entity_for_the_person: GNDNameEntity | None = Field(
        default=None, alias="preferredNameEntityForThePerson"
    )
    variant_name_entity_for_the_person: list[GNDNameEntity] | None = Field(
        default=None, alias="variantNameEntityForThePerson"
    )

    # Links & Metadata
    same_as: list[GNDSameAs] | None = Field(default=None, alias="sameAs")
    wikipedia: list[GNDIdLabel] | None = None
    depiction: list[GNDDepiction] | None = None
    old_authority_number: list[str] | None = Field(
        default=None, alias="oldAuthorityNumber"
    )
    deprecated_uri: list[str] | None = Field(default=None, alias="deprecatedUri")
