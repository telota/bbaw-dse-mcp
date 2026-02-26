# Tool-Spezifikationen

Dieses Dokument beschreibt alle MCP-Tools im Detail für die Implementierung.

## Shared Base Tools (für SD und AB)

Diese Tools werden von beiden Ediarum-basierten Editionen geteilt.

### browse

```python
@mcp.tool
async def browse(
    path: str = "/",
    edition: str = "schleiermacher"
) -> dict:
    """Navigiere durch die Collection-Hierarchie einer Edition.

    PURPOSE: Orientierung in der Editionsstruktur - "Was gibt es hier?"

    WHEN TO USE:
    - User fragt "Was gibt es in der Edition?"
    - User will verstehen wie Daten organisiert sind
    - Exploration ohne konkretes Suchziel

    WHEN NOT TO USE:
    - Konkrete Suche nach Inhalten → search()
    - Bekannte Dokument-ID → get_document()

    Args:
        path: Collection-Pfad, z.B. "/" oder "/Briefe/1810"
        edition: "schleiermacher" oder "actaborussica"

    Returns:
        {
            "path": "/Briefe",
            "collections": ["1800", "1801", ..., "1834"],
            "documents": [],
            "total_documents": 5420
        }
    """
```

**eXist-db Query:**

```xquery
xquery version "3.1";
let $path := "/db/projects/schleiermacher/data" || $requestedPath
return
<result>
    <collections>{
        for $col in xmldb:get-child-collections($path)
        return <collection>{$col}</collection>
    }</collections>
    <documents>{
        for $doc in xmldb:get-child-resources($path)
        return <document>{$doc}</document>
    }</documents>
</result>
```

---

### search

```python
@mcp.tool
async def search(
    query: str,
    edition: str = "schleiermacher",
    collection: str = None,
    limit: int = 20
) -> dict:
    """Volltextsuche in einer Edition.

    PURPOSE: Finde Dokumente die einen Suchbegriff enthalten.

    WHEN TO USE:
    - User sucht nach einem Thema oder Begriff
    - Offene Exploration eines Themenfelds

    WHEN NOT TO USE:
    - Suche nach Personen → search_register("personen", query)
    - Strukturierte Brief-Suche → search_letters()
    - Komplexe Forschungsfragen → deep_research()

    Args:
        query: Suchbegriff(e)
        edition: "schleiermacher" oder "actaborussica"
        collection: Optional, z.B. "Briefe" oder "Vorlesungen"
        limit: Max. Anzahl Ergebnisse (default: 20)

    Returns:
        {
            "query": "Universität",
            "total": 234,
            "results": [
                {
                    "id": "1810-05-21_v_Humboldt",
                    "title": "Von Wilhelm von Humboldt, 21.5.1810",
                    "snippet": "...die neue Universität in Berlin...",
                    "collection": "Briefe/1810",
                    "score": 0.95
                },
                ...
            ]
        }
    """
```

**eXist-db Lucene Query:**

```xquery
xquery version "3.1";
import module namespace ft="http://exist-db.org/xquery/lucene";

let $hits := collection($dataPath)//tei:TEI[ft:query(., $query)]
for $hit in subsequence($hits, 1, $limit)
let $score := ft:score($hit)
order by $score descending
return
<result>
    <id>{$hit/@xml:id/string()}</id>
    <title>{$hit//tei:titleStmt/tei:title/string()}</title>
    <snippet>{ft:highlight($hit, $query)}</snippet>
    <score>{$score}</score>
</result>
```

---

### get_document

```python
@mcp.tool
async def get_document(
    doc_id: str,
    edition: str = "schleiermacher",
    include_metadata: bool = True,
    include_text: bool = True
) -> dict:
    """Hole ein einzelnes Dokument mit Volltext und Metadaten.

    PURPOSE: Detailansicht eines bekannten Dokuments.

    WHEN TO USE:
    - User will ein spezifisches Dokument lesen
    - Follow-up nach Suchergebnis
    - Dokument-ID ist bekannt

    WHEN NOT TO USE:
    - Dokument-ID unbekannt → erst search() oder browse()

    Args:
        doc_id: XML-ID des Dokuments, z.B. "1810-05-21_v_Humboldt"
        edition: "schleiermacher" oder "actaborussica"
        include_metadata: Header-Infos einschließen
        include_text: Volltext einschließen (kann groß sein!)

    Returns:
        {
            "id": "1810-05-21_v_Humboldt",
            "title": "Von Wilhelm von Humboldt",
            "date": "1810-05-21",
            "metadata": {
                "sender": {"name": "Wilhelm von Humboldt", "id": "S00456"},
                "recipient": {"name": "Friedrich Schleiermacher", "id": "S00001"},
                "place": {"name": "Berlin", "id": "O00123"}
            },
            "text": "Hochgeschätzter Freund, ..."
        }
    """
```

---

### list_registers

```python
@mcp.tool
async def list_registers(
    edition: str = "schleiermacher"
) -> dict:
    """Liste alle verfügbaren Register-Typen einer Edition.

    PURPOSE: Zeige welche Register (Personen, Orte, etc.) verfügbar sind.

    Args:
        edition: "schleiermacher" oder "actaborussica"

    Returns:
        {
            "edition": "schleiermacher",
            "registers": [
                {"type": "personen", "count": 4523, "label": "Personenregister"},
                {"type": "orte", "count": 1234, "label": "Ortsregister"},
                {"type": "werke", "count": 892, "label": "Werkregister"}
            ]
        }
    """
```

---

### search_register

```python
@mcp.tool
async def search_register(
    register: str,
    query: str,
    edition: str = "schleiermacher",
    limit: int = 10
) -> dict:
    """Durchsuche ein Register (Personen, Orte, Werke, etc.).

    PURPOSE: Finde Einträge in einem Register.

    WHEN TO USE:
    - User sucht nach einer Person, einem Ort, einem Werk
    - Vor get_register_entry() um die ID zu finden

    Args:
        register: "personen", "orte", "werke", etc.
        query: Suchbegriff
        edition: "schleiermacher" oder "actaborussica"
        limit: Max. Anzahl Ergebnisse

    Returns:
        {
            "register": "personen",
            "query": "Humboldt",
            "results": [
                {"id": "S00456", "name": "Humboldt, Wilhelm von", "dates": "1767-1835"},
                {"id": "S00457", "name": "Humboldt, Alexander von", "dates": "1769-1859"}
            ]
        }
    """
```

---

### get_register_entry

```python
@mcp.tool
async def get_register_entry(
    register: str,
    entry_id: str,
    edition: str = "schleiermacher"
) -> dict:
    """Hole detaillierte Informationen zu einem Register-Eintrag.

    PURPOSE: Vollständige Details zu einer Person, einem Ort, etc.

    WHEN TO USE:
    - User fragt "Wer ist X?" oder "Was ist Y?"
    - Nach search_register() für Details
    - Kontext zu einer in Dokumenten erwähnten Entität

    WHEN NOT TO USE:
    - ID unbekannt → erst search_register()
    - Komplexe biografische Recherche → deep_research()

    Args:
        register: "personen", "orte", "werke", etc.
        entry_id: XML-ID des Eintrags, z.B. "S00456"
        edition: "schleiermacher" oder "actaborussica"

    Returns:
        {
            "id": "S00456",
            "type": "person",
            "name": "Humboldt, Wilhelm von",
            "name_variants": ["Wilhelm Freiherr von Humboldt"],
            "dates": {
                "birth": "1767-06-22",
                "death": "1835-04-08"
            },
            "description": "Preußischer Gelehrter, Staatsmann und Bildungsreformer...",
            "gnd_id": "118554727",
            "references": {
                "letters_as_correspondent": 12,
                "mentions_in_letters": 45,
                "mentions_in_diaries": 8
            },
            "external_links": [
                {"label": "GND", "url": "https://d-nb.info/gnd/118554727"},
                {"label": "Wikipedia", "url": "https://de.wikipedia.org/wiki/Wilhelm_von_Humboldt"}
            ]
        }
    """
```

**eXist-db Query (basierend auf dem vorhandenen Code):**

```xquery
xquery version "3.1";
import module namespace edwebRegister="http://www.bbaw.de/telota/ediarum/web/register";

let $person := collection($edweb:dataRegister)//tei:person[@xml:id = $entryId]
return
<result>
    <id>{$person/@xml:id/string()}</id>
    <name>{edweb:persName($person/tei:persName[@type='reg'], 'forename')}</name>
    <birth>{$person/tei:birth/text()}</birth>
    <death>{$person/tei:death/text()}</death>
    <gnd>{$person/tei:idno/text()}</gnd>
    <!-- ... weitere Felder ... -->
</result>
```

---

## Schleiermacher-spezifische Tools

### search_letters

```python
@mcp.tool
async def search_letters(
    sender: str = None,
    recipient: str = None,
    year: int = None,
    date_from: str = None,
    date_to: str = None,
    query: str = None,
    limit: int = 50
) -> dict:
    """Durchsuche den Briefwechsel mit strukturierten Filtern.

    PURPOSE: Gezielte Suche in der Korrespondenz.

    WHEN TO USE:
    - User sucht Briefe nach Korrespondent, Datum, oder beidem
    - "Zeig mir alle Briefe von/an X"
    - "Briefe aus dem Jahr Y"

    WHEN NOT TO USE:
    - Volltextsuche ohne Brief-Kontext → search()
    - Statistiken über Korrespondenz → get_correspondent_stats()

    Args:
        sender: Person-ID des Absenders
        recipient: Person-ID des Empfängers
        year: Jahr (z.B. 1810)
        date_from: Startdatum (ISO: "1810-01-01")
        date_to: Enddatum (ISO: "1810-12-31")
        query: Zusätzlicher Volltext-Filter
        limit: Max. Anzahl Ergebnisse

    Returns:
        {
            "filters": {"year": 1810, "sender": "S00456"},
            "total": 8,
            "letters": [
                {
                    "id": "1810-05-21_v_Humboldt",
                    "date": "1810-05-21",
                    "sender": {"id": "S00456", "name": "Wilhelm von Humboldt"},
                    "recipient": {"id": "S00001", "name": "Friedrich Schleiermacher"},
                    "place": "Berlin",
                    "summary": "Über die Universitätsgründung..."
                },
                ...
            ]
        }
    """
```

**Lucene Query:**

```
sender-keys:{senderId} AND receiver-keys:{recipientId}
```

---

### get_correspondent_stats

```python
@mcp.tool
async def get_correspondent_stats(
    year: int = None,
    person_id: str = None
) -> dict:
    """Statistik über Korrespondenzpartner.

    PURPOSE: Analysiere wer die wichtigsten Briefpartner waren.
    Dies ist das zentrale Tool für das Demo-Szenario "Wer war wichtig 1810?"

    WHEN TO USE:
    - "Wer war wichtig für Schleiermacher in Jahr X?"
    - "Mit wem korrespondierte Schleiermacher am meisten?"
    - Netzwerk-Überblick

    WHEN NOT TO USE:
    - Details zu einzelnen Briefen → search_letters()
    - Biografische Infos → get_register_entry()

    Args:
        year: Optional, filtert auf ein Jahr
        person_id: Optional, Statistik für diese Person als Korrespondent

    Returns:
        {
            "year": 1810,
            "total_letters": 185,
            "correspondents": [
                {
                    "person_id": "S00789",
                    "name": "Charlotte Schleiermacher",
                    "role": "Schwester",
                    "letters_sent": 8,
                    "letters_received": 7,
                    "total": 15
                },
                {
                    "person_id": "S00456",
                    "name": "Wilhelm von Humboldt",
                    "role": "Bildungsreformer",
                    "letters_sent": 3,
                    "letters_received": 5,
                    "total": 8,
                    "note": "Schlüsselfigur der Universitätsgründung 1810"
                },
                ...
            ],
            "context": "1810 war das Jahr der Berliner Universitätsgründung, an der Schleiermacher maßgeblich beteiligt war."
        }
    """
```

---

### get_calendar_entries

```python
@mcp.tool
async def get_calendar_entries(
    date_from: str,
    date_to: str,
    person_id: str = None
) -> dict:
    """Hole Tageskalender-Einträge für einen Zeitraum.

    PURPOSE: Was hat Schleiermacher an bestimmten Tagen gemacht?

    WHEN TO USE:
    - Zeitliche Einordnung von Ereignissen
    - "Was passierte im März 1810?"
    - Kontext zu Briefen

    Args:
        date_from: Startdatum (ISO)
        date_to: Enddatum (ISO)
        person_id: Optional, nur Einträge die diese Person erwähnen

    Returns:
        {
            "period": {"from": "1810-03-01", "to": "1810-03-31"},
            "entries": [
                {
                    "date": "1810-03-15",
                    "content": "Predigt in der Dreifaltigkeitskirche. Abends bei Reimer.",
                    "persons_mentioned": ["S00123", "S00456"],
                    "places_mentioned": ["O00789"]
                },
                ...
            ]
        }
    """
```

---

### get_diary_entry

```python
@mcp.tool
async def get_diary_entry(
    date: str
) -> dict:
    """Retrieve a specific diary entry by date.

    PURPOSE: Access a specific day's entry from Schleiermacher's diary.

    Available years: 1808-1811, 1817, 1820-1834. Note: 1812-1816 and 1818-1819 are not extant.

    WHEN TO USE:
    - User asks for diary entry on specific date
    - User wants to know what happened on a particular day
    - After search → get full diary entry

    WHEN NOT TO USE:
    - For date range → use get_diary_entries()
    - For keyword search → use search_in_documents()

    Args:
        date: Date in ISO 8601 format (YYYY-MM-DD), e.g., "1808-01-01"

    Returns:
        {
            "date": "1808-01-01",
            "year": 1808,
            "left_side": "...",
            "right_side": "...",
            "raw_xml": "<div>...</div>"
        }
    """
```

---

### get_diary_entries

```python
@mcp.tool
async def get_diary_entries(
    date_from: str,
    date_to: str
) -> list[dict]:
    """Retrieve diary entries for a date range.

    PURPOSE: Access multiple diary entries across a time period.

    Available years: 1808-1811, 1817, 1820-1834. Note: 1812-1816 and 1818-1819 are not extant.

    WHEN TO USE:
    - User asks for diary entries in a date range
    - User wants to see activities over a period

    WHEN NOT TO USE:
    - For single date → use get_diary_entry()
    - For keyword search → use search_in_documents()

    Args:
        date_from: Start date in ISO 8601 format (YYYY-MM-DD)
        date_to: End date in ISO 8601 format (YYYY-MM-DD)

    Returns:
        List of dicts, each with date, left_side, right_side content
    """
```

---

### get_chronology_entry

```python
@mcp.tool
async def get_chronology_entry(
    date: str
) -> list[dict]:
    """Retrieve chronology entries for a specific date.

    PURPOSE: Access events from Schleiermacher's life on a specific date.
    The chronology provides structured historical/biographical events (1768-1834),
    complementing the diaries which contain personal daily notes (1808-1834).

    WHEN TO USE:
    - "What happened on August 29, 1785?"
    - Getting biographical information for a particular day
    - Following up after document search

    WHEN NOT TO USE:
    - For date range → use get_chronology_entries()
    - For entire year → use get_chronology_year()
    - For keyword search → use search_documents()

    Args:
        date: Date in ISO 8601 format (YYYY-MM-DD), e.g., "1785-08-29"

    Returns:
        [
            {
                "date_display": "August 29",
                "when": "1785-08-29",
                "notBefore": null,
                "notAfter": null,
                "cert": "high",
                "event": "Aufnahme Schleiermachers in den Brüderchor..."
            }
        ]
    """
```

---

### get_chronology_entries

```python
@mcp.tool
async def get_chronology_entries(
    date_from: str,
    date_to: str
) -> list[dict]:
    """Retrieve chronology entries for a date range.

    PURPOSE: Access events from Schleiermacher's life across a time period.
    Intelligently handles both exact dates (@when) and date ranges (@notBefore/@notAfter).

    WHEN TO USE:
    - "What happened between 1785 and 1790?"
    - Biographical timeline for a specific period
    - Temporal analysis of life events

    WHEN NOT TO USE:
    - For single date → use get_chronology_entry()
    - For entire year → use get_chronology_year()

    Args:
        date_from: Start date in ISO 8601 format
        date_to: End date in ISO 8601 format

    Returns:
        List of chronology entries sorted chronologically
    """
```

---

### get_chronology_year

```python
@mcp.tool
async def get_chronology_year(
    year: int
) -> dict:
    """Retrieve all chronology entries for a specific year.

    PURPOSE: Complete biographical timeline for a year in Schleiermacher's life.

    WHEN TO USE:
    - "What happened in 1785?"
    - Annual biographical overview
    - Year-level summaries

    WHEN NOT TO USE:
    - For specific date → use get_chronology_entry()
    - For date range spanning years → use get_chronology_entries()

    Args:
        year: Year (1768-1834)

    Returns:
        {
            "year": 1785,
            "heading": "Chronologie 1785",
            "entries": [ ... ]
        }
    """
```

**Chronology vs. Diary comparison:**

| Feature   | Diaries                   | Chronology                     |
| --------- | ------------------------- | ------------------------------ |
| Content   | Daily personal notes      | Historical/biographical events |
| Coverage  | 1808-1834 (with gaps)     | 1768-1834 (complete)           |
| Structure | Left/right page format    | Timeline items                 |
| Dates     | Always specific days      | Specific or range              |
| Use case  | "What did S. write on X?" | "What happened in X?"          |

---

## MoP (Praktiken der Monarchie) - spezifische Tools

### browse_documents

```python
@mcp.tool
async def browse_documents(
    collection: str = "Texte",
    limit: int = 100
) -> dict:
    """Browse files and subcollections in MoP.

    PURPOSE: Überblick über verfügbare Dateien in der MoP-Edition.

    WHEN TO USE:
    - User möchte sehen, was in der Edition verfügbar ist
    - Exploration ohne konkreten Suchbegriff

    WHEN NOT TO USE:
    - Bei konkreter Suche → nutze search_documents()

    Args:
        collection: Collection-Name (Texte, Register)
        limit: Maximale Anzahl Dateien

    Returns:
        Dict mit 'files' und 'subcollections' Liste
    """
```

---

### search_documents

```python
@mcp.tool
async def search_documents(
    keyword: str,
    collection: str = "Texte",
    max_results: int = 50
) -> list[SearchResult]:
    """Volltextsuche in MoP-Dokumenten.

    PURPOSE: Dokumente finden, die einen bestimmten Begriff enthalten.

    WHEN TO USE:
    - User sucht nach Person, Institution, Thema
    - Explorative Suche zu höfischen Praktiken

    WHEN NOT TO USE:
    - Für strukturierte Registersuche → nutze search_register()

    Args:
        keyword: Suchbegriff
        collection: Collection (Texte)
        max_results: Maximale Ergebnisse

    Returns:
        Liste von SearchResult-Objekten
    """
```

---

### search_register (MoP)

```python
@mcp.tool
async def search_register(
    query: str,
    register_type: str = "personen",
    max_results: int = 20
) -> list[dict]:
    """Suche in MoP-Registern.

    PURPOSE: Strukturierte Registereinträge finden.

    WHEN TO USE:
    - User sucht nach Person, Ort, Institution, Hof
    - Um IDs für weitere Suchen zu bekommen

    Args:
        query: Suchbegriff
        register_type: Register (personen, orte, institutionen, hoefe, werke, aemter)
        max_results: Maximale Ergebnisse

    Returns:
        Liste von Register-Einträgen mit id, name, type, gnd
    """
```

---

### get_register_entry (MoP)

```python
@mcp.tool
async def get_register_entry(
    entry_id: str,
    register_type: str = "personen"
) -> dict:
    """Detailansicht eines MoP-Registereintrags.

    PURPOSE: Vollständige Informationen zu Person, Ort, etc.

    WHEN TO USE:
    - Nach Registersuche für Details
    - Für biographische/geographische Informationen

    Args:
        entry_id: XML-ID des Eintrags (z.B. "P0002157")
        register_type: Register (personen, orte, institutionen, hoefe, werke, aemter)

    Returns:
        Dict mit vollständigen Registerdaten
    """
```

---

### search_adjutanten_journals

```python
@mcp.tool
async def search_adjutanten_journals(
    query: str | None = None,
    monarch: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    person_key: str | None = None,
    place_key: str | None = None,
    limit: int = 50
) -> list[dict]:
    """Search in Adjutantenjournale (court adjutant journals).

    PURPOSE: Find daily court journal entries documenting royal activities,
    audiences, meetings, and events. The journals were written by rotating
    adjutants on duty (1840-1918).

    Available monarchs:
    - Friedrich_Wilhelm_IV (1840-1861)
    - Wilhelm_I (1861-1888)
    - Wilhelm_II (1888-1918)
    - Friedrich_III (1888)

    WHEN TO USE:
    - "What did the king do on [date]?"
    - User wants to know about daily court life
    - User searches for specific events, persons, or places in journals
    - User wants to track activities of a specific monarch

    WHEN NOT TO USE:
    - For biographical data → use search_register() or search_biogramme()
    - For institutional documents → use browse_documents()

    Args:
        query: Full-text search term (searches in journal text)
        monarch: Filter by monarch (Friedrich_Wilhelm_IV, Wilhelm_I, Wilhelm_II, Friedrich_III)
        date_from: Start date in ISO format (YYYY-MM-DD)
        date_to: End date in ISO format (YYYY-MM-DD)
        person_key: Filter by person mentioned (register key, e.g., "P0002157")
        place_key: Filter by place mentioned (register key, e.g., "P0003556")
        limit: Maximum number of results (default: 50)

    Returns:
        List of journal entries with:
        - id: Document ID
        - monarch: Which monarch's reign
        - date_from/date_to: Time range covered
        - place: Where the court was located
        - authors: Adjutants who wrote the entry
        - snippet: Text excerpt
        - url: Link to online edition
    """
```

**Example Queries:**

```python
# What did Wilhelm I do in January 1861?
search_adjutanten_journals(monarch="Wilhelm_I", date_from="1861-01-01", date_to="1861-01-31")

# Find mentions of Bismarck
search_adjutanten_journals(query="Bismarck")

# Activities at Sanssouci palace
search_adjutanten_journals(place_key="P0003556")
```

---

### get_adjutanten_journal_entry

```python
@mcp.tool
async def get_adjutanten_journal_entry(
    document_id: str
) -> dict:
    """Retrieve the full text and details of a specific journal entry.

    PURPOSE: Full view of a court journal entry with all daily records.

    WHEN TO USE:
    - After search_adjutanten_journals() to get full detail
    - When document_id is known

    Args:
        document_id: Document ID from search results (e.g., "P0005285")

    Returns:
        Full metadata (monarch, dates, archive reference) plus daily entries
        with date, location, writing sessions (by different adjutants),
        and complete journal text.
    """
```

---

### list_adjutanten_by_monarch

```python
@mcp.tool
async def list_adjutanten_by_monarch(
    monarch: str
) -> dict:
    """Get a prosopographic overview of all adjutants who served under a specific monarch.

    PURPOSE: Prosopographic analysis of court adjutants.

    WHEN TO USE:
    - "Who served as adjutant under Friedrich Wilhelm IV?"
    - Research on court personnel

    Args:
        monarch: Monarch name (Friedrich_Wilhelm_IV, Wilhelm_I, Wilhelm_II, Friedrich_III)

    Returns:
        Total journal entries for that monarch, list of all adjutants with
        name, register ID, number of entries written, and service date range.
    """
```

---

### search_biogramme

```python
@mcp.tool
async def search_biogramme(
    query: str,
    birth_year: int | None = None,
    death_year: int | None = None,
    max_results: int = 20
) -> list[dict]:
    """Search in MoP Biogramme (detailed biographical entries).

    PURPOSE: Find detailed biographical entries for court officials and nobility (1786-1918).

    WHEN TO USE:
    - User searches for person with biographical details
    - Research on family relationships, careers, properties
    - Prosopographic studies of court officials

    WHEN NOT TO USE:
    - For simple register lookup → use search_register("personen")
    - For full-text search in documents → use search_documents()

    Args:
        query: Name to search for
        birth_year: Optional filter by birth year
        death_year: Optional filter by death year
        max_results: Maximum number of results (default: 20)

    Returns:
        List of matches with id, person_id, name, birth, death, gnd
    """
```

---

### get_biogramm_by_id

```python
@mcp.tool
async def get_biogramm_by_id(
    biogramm_id: str
) -> dict:
    """Retrieve complete biographical data for a specific person.

    PURPOSE: Detailed biographical entry with family, career, property data.

    WHEN TO USE:
    - After search_biogramme() to get full details
    - Analyze family networks, career, properties
    - Comprehensive prosopographic information

    Args:
        biogramm_id: XML-ID of the biogramm (e.g., "P0005251")

    Returns:
        Dict with structured biographical data:
        - name, gender, birth, death, confession
        - property: List of property holdings
        - family_relations: List of family relationships with type
        - court_offices: List of court positions
        - education, military, awards, notes
        - gnd: GND identifier
    """
```

---

### extract_family_network

```python
@mcp.tool
async def extract_family_network(
    biogramm_id: str
) -> dict:
    """Extract and organize family relationships from a biogramm.

    PURPOSE: Genealogical research and court network reconstruction.

    WHEN TO USE:
    - Genealogical research
    - Reconstruct court networks
    - Analyze family dynasties

    Args:
        biogramm_id: XML-ID of the biogramm

    Returns:
        {
            "person": "Name of focal person",
            "parents": [...],
            "siblings": [...],
            "spouse": [...],
            "children": [...],
            "other_relations": [...]
        }
    """
```

---

### search_residential_addresses

```python
@mcp.tool
async def search_residential_addresses(
    year: int,
    name: str | None = None,
    street: str | None = None,
    category: str | None = None,
    max_results: int = 50
) -> list[dict]:
    """Search residential topography data (Wohntopographie).

    PURPOSE: Find historical addresses of court officials, royal family,
    and other persons/institutions in Berlin and Prussia.

    Available years: 1800, 1845, 1872, 1891, 1914
    Source: GeoJSON data from actaborussica.bbaw.de

    WHEN TO USE:
    - "Where did Bismarck live in 1872?"
    - Geographic analysis of court officials
    - Combine with Adjutantenjournale for spatial context

    Args:
        year: Year (1800, 1845, 1872, 1891, or 1914)
        name: Filter by person/institution name
        street: Filter by street name
        category: Filter by category
        max_results: Maximum results

    Returns:
        List of address entries with name, street, coordinates, category
    """
```

**Cross-tool workflows:**

```python
# 1. Find journal entries mentioning a person
results = search_adjutanten_journals(person_key="P0002157")

# 2. Get full biographical data
bio = get_biogramm_by_id("P0002157")

# 3. Analyze family network
family = extract_family_network("P0002157")

# 4. Find where they lived
addresses = search_residential_addresses(year=1861, name="Bismarck")
```

---

## correspSearch Tools

### search_correspondence

```python
@mcp.tool
async def search_correspondence(
    sender: str = None,
    recipient: str = None,
    place: str = None,
    date_from: str = None,
    date_to: str = None,
    gnd_id: str = None
) -> dict:
    """Durchsuche den correspSearch Meta-Index.

    PURPOSE: Finde Korrespondenzen über viele Editionen hinweg.

    WHEN TO USE:
    - "Gibt es mehr Briefe von/an X in anderen Editionen?"
    - Cross-Edition Recherche
    - Netzwerk-Analyse über Editionsgrenzen hinweg

    WHEN NOT TO USE:
    - Suche nur in Schleiermacher → search_letters()
    - Volltext-Suche → nicht möglich in correspSearch

    Args:
        sender: Name oder GND-ID des Absenders
        recipient: Name oder GND-ID des Empfängers
        place: Ort
        date_from: Startdatum
        date_to: Enddatum
        gnd_id: GND-ID einer Person (präziser als Name)

    Returns:
        {
            "query": {"sender_gnd": "118554727"},
            "total": 234,
            "results": [
                {
                    "sender": "Humboldt, Wilhelm von",
                    "recipient": "Goethe, Johann Wolfgang von",
                    "date": "1810-04-15",
                    "place": "Berlin",
                    "edition": "Goethe-Briefwechsel",
                    "url": "https://goethe-edition.de/briefe/1234"
                },
                ...
            ],
            "editions_found": ["Goethe-Briefwechsel", "Schiller-Edition", ...]
        }
    """
```

**REST API Call:**

```
GET https://correspsearch.net/api/v1.1/tei-xml.xql?
    correspondent=http://d-nb.info/gnd/118554727
    &startdate=1810-01-01
    &enddate=1810-12-31
```

---

## Agent Tool

### deep_research

```python
@mcp.tool
async def deep_research(
    query: str,
    editions: list[str] = ["schleiermacher", "actaborussica"],
    max_steps: int = 10,
    ctx: Context = None
) -> dict:
    """Führe eine autonome, mehrstufige Recherche durch.

    PURPOSE: Komplexe Forschungsfragen die mehrere Suchen und
    Synthese erfordern.

    WHEN TO USE:
    - Komplexe, offene Forschungsfragen
    - Fragen die mehrere Editionen betreffen
    - Analysen die Zusammenhänge erfordern
    - "Analysiere...", "Untersuche...", "Vergleiche..."

    WHEN NOT TO USE:
    - Einfache Fakten-Fragen → get_register_entry()
    - Einzelne Suchen → search(), search_letters()
    - Wenn schnelle Antwort nötig (dauert 30-60 Sekunden)

    ACHTUNG: Dieses Tool startet einen autonomen ReAct-Agenten der
    mehrere Suchen durchführt. Es dauert länger und verbraucht mehr
    Ressourcen als direkte Tools.

    Args:
        query: Die Forschungsfrage in natürlicher Sprache
        editions: Welche Editionen durchsucht werden sollen
        max_steps: Maximale Anzahl von Agent-Schritten (Sicherheitslimit)

    Returns:
        {
            "query": "Schleiermachers Rolle in der Bildungsreform 1810",
            "report": "## Zusammenfassung\n\nSchleiermacher war...",
            "sources": [
                {"type": "letter", "id": "1810-05-21_v_Humboldt", "relevance": "hoch"},
                {"type": "register", "id": "S00456", "name": "Wilhelm von Humboldt"},
                ...
            ],
            "steps_taken": 7,
            "editions_searched": ["schleiermacher", "actaborussica"],
            "entities_found": [
                {"id": "S00456", "name": "Humboldt", "mentions": 12},
                ...
            ]
        }
    """
```

---

## Tool-Übersicht nach Server

### Schleiermacher Digital (SD) - 10 Tools

1. `browse` - Collection-Navigation
2. `search` / `search_in_documents` - Lucene-Volltextsuche
3. `get_document` - Dokument-Abruf
4. `search_register` / `get_register_entry` - Register
5. `filter_letters` - Strukturierte Brief-Suche
6. `get_correspondent_stats` - Korrespondenz-Netzwerk
7. `get_diary_entry` / `get_diary_entries` - Tageskalender
8. `get_chronology_entry` / `get_chronology_entries` / `get_chronology_year` - Chronologie

### MoP / Acta Borussica (AB) - 10 Tools

1. `browse_documents` - Collection-Navigation
2. `search_documents` - Volltextsuche
3. `search_register` / `get_register_entry` - Register (personen, orte, institutionen, hoefe, werke, aemter)
4. `search_adjutanten_journals` / `get_adjutanten_journal_entry` / `list_adjutanten_by_monarch` - Adjutantenjournale
5. `search_biogramme` / `get_biogramm_by_id` / `extract_family_network` - Biogramme
6. `search_residential_addresses` - Wohntopographie

### correspSearch (CS) - 4 Tools

1. `search_correspondences` - Korrespondenz-Metaindex
2. `search_correspondent_network` - Netzwerk-Analyse

### Übergreifend

1. `deep_research` - ReAct Agent für komplexe Fragen
