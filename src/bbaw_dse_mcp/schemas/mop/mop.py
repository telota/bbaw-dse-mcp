"""Schemas for MoP (Praktiken der Monarchie) specific data structures.

Provides Pydantic models for:
- Wohntopographie (Residential Topography) - GeoJSON-based person/address data
- ResidentialPerson - Person or institution properties
- GeoJSONFeature - Individual geographic feature with person data
"""

from pydantic import BaseModel, Field


class ResidentialPerson(BaseModel):
    """A person or institution entry from the Wohntopographie dataset."""

    tabellen_id: int | None = Field(None, alias="Tabellen-ID")
    ediarum_id: str | None = Field(None, alias="Ediarum-ID")
    name: str | None = Field(None, alias="Name")
    vorname: str | None = Field(None, alias="Vorname")
    geburtsname: str | None = Field(None, alias="Geburtsname")
    person_institution: str | None = Field(None, alias="Person/Institution")

    # Noble titles and ranks
    adelstitel: str | None = Field(None, alias="Adelstitel")
    adelspraedikat: str | None = Field(None, alias="Adelsprädikat")
    rang: str | None = Field(None, alias="Rang")
    akademischer_titel: str | None = Field(None, alias="AkademischerTitel")

    # Categories and occupation
    kategorie1: str | None = Field(None, alias="Kategorie1")
    kategorie2: str | None = Field(None, alias="Kategorie2")
    taetigkeit: str | None = Field(None, alias="Tätigkeit")

    # Address information
    stadt: str | None = Field(None, alias="Stadt")
    strasse: str | None = Field(None, alias="Straße")
    hausnummer: str | None = Field(None, alias="Hausnummer")
    adresszusatz: str | None = Field(None, alias="Adresszusatz")

    # Relationships and affiliations
    verheiratet_mit_id: str | None = Field(None, alias="Verheiratet mit (ID)")
    hof_hoefe: str | None = Field(None, alias="Hof/Höfe")
    hof_id: str | None = Field(None, alias="Hof-ID")

    # Notes and metadata
    bemerkungen: str | None = Field(None, alias="Bemerkungen")
    bem_2: str | None = Field(None, alias="Bem.2")
    wkt_geom_source: int | None = Field(None, alias="wkt_geom source")

    class Config:
        populate_by_name = True


class GeoJSONGeometry(BaseModel):
    """GeoJSON geometry (Point)."""

    type: str = Field(..., description="Geometry type (e.g., 'Point')")
    coordinates: list[float] | None = Field(None, description="[longitude, latitude]")


class GeoJSONFeature(BaseModel):
    """A single GeoJSON feature with person/institution data."""

    type: str = Field(default="Feature")
    geometry: GeoJSONGeometry | None = None
    properties: ResidentialPerson

    def has_coordinates(self) -> bool:
        """Check if this feature has valid coordinates."""
        return (
            self.geometry is not None
            and self.geometry.coordinates is not None
            and len(self.geometry.coordinates) == 2
        )

    def get_longitude(self) -> float | None:
        """Get longitude coordinate."""
        if self.has_coordinates():
            return self.geometry.coordinates[0]
        return None

    def get_latitude(self) -> float | None:
        """Get latitude coordinate."""
        if self.has_coordinates():
            return self.geometry.coordinates[1]
        return None


class ResidentialTopography(BaseModel):
    """Complete Wohntopographie dataset (GeoJSON FeatureCollection)."""

    type: str = Field(default="FeatureCollection")
    features: list[GeoJSONFeature] = Field(default_factory=list)

    def get_by_ediarum_id(self, ediarum_id: str) -> list[GeoJSONFeature]:
        """Find all entries with matching Ediarum-ID."""
        return [f for f in self.features if f.properties.ediarum_id == ediarum_id]

    def get_by_name(
        self,
        name: str | None = None,
        vorname: str | None = None,
        case_sensitive: bool = False,
    ) -> list[GeoJSONFeature]:
        """Find entries by name (partial match).

        Args:
            name: Last name (partial match)
            vorname: First name (partial match)
            case_sensitive: Whether to perform case-sensitive search

        Returns:
            List of matching features
        """
        results = []
        for f in self.features:
            match = True

            if name:
                person_name = f.properties.name or ""
                search_name = name if case_sensitive else name.lower()
                compare_name = person_name if case_sensitive else person_name.lower()
                match = match and (search_name in compare_name)

            if vorname:
                person_vorname = f.properties.vorname or ""
                search_vorname = vorname if case_sensitive else vorname.lower()
                compare_vorname = (
                    person_vorname if case_sensitive else person_vorname.lower()
                )
                match = match and (search_vorname in compare_vorname)

            if match:
                results.append(f)

        return results

    def get_by_category(self, kategorie: str) -> list[GeoJSONFeature]:
        """Find entries by category (Kategorie1 or Kategorie2)."""
        kategorie_lower = kategorie.lower()
        return [
            f
            for f in self.features
            if (
                f.properties.kategorie1
                and kategorie_lower in f.properties.kategorie1.lower()
            )
            or (
                f.properties.kategorie2
                and kategorie_lower in f.properties.kategorie2.lower()
            )
        ]

    def get_by_occupation(self, taetigkeit: str) -> list[GeoJSONFeature]:
        """Find entries by occupation/activity."""
        taetigkeit_lower = taetigkeit.lower()
        return [
            f
            for f in self.features
            if f.properties.taetigkeit
            and taetigkeit_lower in f.properties.taetigkeit.lower()
        ]

    def get_by_city(self, stadt: str) -> list[GeoJSONFeature]:
        """Find entries by city."""
        stadt_lower = stadt.lower()
        return [
            f
            for f in self.features
            if f.properties.stadt and stadt_lower in f.properties.stadt.lower()
        ]

    def get_by_street(self, strasse: str) -> list[GeoJSONFeature]:
        """Find entries by street name."""
        strasse_lower = strasse.lower()
        return [
            f
            for f in self.features
            if f.properties.strasse and strasse_lower in f.properties.strasse.lower()
        ]

    def get_with_coordinates(self) -> list[GeoJSONFeature]:
        """Get only entries that have valid geographic coordinates."""
        return [f for f in self.features if f.has_coordinates()]

    def count_by_category(self) -> dict[str, int]:
        """Count entries per category (Kategorie1)."""
        counts: dict[str, int] = {}
        for f in self.features:
            cat = f.properties.kategorie1 or "Unbekannt"
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def count_by_city(self) -> dict[str, int]:
        """Count entries per city."""
        counts: dict[str, int] = {}
        for f in self.features:
            city = f.properties.stadt or "Unbekannt"
            counts[city] = counts.get(city, 0) + 1
        return counts
