# BBAW-DSE-MCPP: AI Agent Interface für Digitale Editionen

## Projektübersicht

Dieses Projekt implementiert einen **MCP-Server (Model Context Protocol)** für den dialogischen, explorativen Zugang zu digitalen wissenschaftlichen Editionen. Es ist Teil eines DHd2026-Poster-Projekts mit dem Titel "Agenten im Dienst der Edition".

### Kernidee

Statt komplexer Suchmasken und Navigationsstrukturen ermöglicht der MCP-Server **natürlichsprachliche Konversation** mit den Editionen. Ein KI-Agent übersetzt Fragen wie "Wer war wichtig für Schleiermacher 1810?" automatisch in strukturierte Datenbankabfragen.

### Ziel-Editionen

1. **schleiermacher digital** (SD) - Komplexe Briefedition mit Tageskalender und Vorlesungen
2. **Praktiken der Monarchie / Acta Borussica** (AB) - Umfangreiche Dokumenten- und Quellensammlung
3. **correspSearch** (CS) - Recherche-Tool für übergreifende Korrespondenznetzwerke (CMIF)

## Architektur

```
┌────────────────────────────────────────────────────────────┐
│              bbaw-dse-mcp (FastMCP Composed)               │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │schleiermacher│  │      mop     │  │   correspsearch  │  │
│  │    Server    │  │    Server    │  │      Server      │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
└─────────┼─────────────────┼───────────────────┼────────────┘
          │                 │                   │
    ┌─────▼─────┐     ┌─────▼─────┐      ┌──────▼──────┐
    │ eXist-db  │     │ eXist-db  │      │  REST API   │
    │ (Ediarum) │     │ (Ediarum) │      │   (CMIF)    │
    └───────────┘     └───────────┘      └─────────────┘
```

### Technologie-Stack

- **FastMCP 2.0** - Python MCP Server Framework
- **httpx** - Async HTTP Client für eXist-db REST API
- **Anthropic API** - Für den internen ReAct-Agent (deep_research)

## Tool-Kategorien

### 1. Direkte Tools (schnelle Einzelabfragen)

Diese Tools werden vom Haupt-LLM direkt aufgerufen für einfache Fragen:

| Tool                      | Zweck                   | Beispiel-Frage                |
| ------------------------- | ----------------------- | ----------------------------- |
| `browse`                  | Collection-Navigation   | "Was gibt es in der Edition?" |
| `search`                  | Volltextsuche           | "Suche nach Universität"      |
| `get_document`            | Dokument abrufen        | "Zeig mir Brief 1234"         |
| `get_register_entry`      | Register-Lookup         | "Wer ist Henriette Herz?"     |
| `search_letters`          | Brief-Filterung         | "Briefe von 1810"             |
| `get_correspondent_stats` | Korrespondenz-Statistik | "Wer war wichtig 1810?"       |

### 2. Agent-Tool (komplexe Recherchen)

Für mehrstufige Forschungsfragen:

| Tool            | Zweck              | Beispiel-Frage                                           |
| --------------- | ------------------ | -------------------------------------------------------- |
| `deep_research` | Autonome Recherche | "Analysiere Schleiermachers Rolle in der Bildungsreform" |

## Demo-Szenario: Mehrstufiger Forschungsdialog

Das zentrale Demo-Szenario für das Poster (aus dem Abstract):

```
User: "Suche nach Briefen, die Humboldt erwähnen"

Agent: → Prüft Datenbankverbindung
       → search_by_keyword(keyword='Humboldt', collection='Briefe')
→ "Ich habe X Briefe gefunden, in denen Humboldt erwähnt wird..."

User: "Zeige mir den Brief vom März 1810"

Agent: get_document(id='S0001234')
→ Volltext des Briefes mit Metadaten

User: "Wer war wichtig für Schleiermacher 1810?"

Agent: get_correspondent_stats(year=1810)
→ "Basierend auf der Briefhäufigkeit waren folgende Personen wichtig:
   1. Charlotte Schleiermacher (15 Briefe) - Schwester
   2. Wilhelm von Humboldt (8 Briefe) - Universitätsgründung!
   ..."
```

Der Agent behält den Kontext der vorherigen Suche und kann auf dieser Grundlage weiterführende Fragen beantworten.

## Projektstruktur

```
bbaw-dse-mcp/
├── pyproject.toml
├── README.md
├── AGENT.md                    # Diese Datei
├── src/
│   └── bbaw_dse_mcp/
│       ├── __init__.py
│       ├── main.py             # Composed Server Entry Point
│       ├── config.py           # Konfiguration (URLs, Credentials)
│       ├── base.py             # Shared EdiarumEdition Base Class
│       ├── existdb.py          # eXist-db REST Client
│       ├── schleiermacher.py   # SD-spezifische Tools
│       ├── actaborussica.py    # AB-spezifische Tools
│       ├── correspsearch.py    # CS REST Client
│       └── research_agent.py   # ReAct Deep Research Agent
└── tests/
    ├── test_existdb.py
    ├── test_schleiermacher.py
    └── test_research.py
```

## Wichtige Implementierungsdetails

### eXist-db Zugriff

- REST API (nicht XML-RPC)
- Read-only Zugriff
- Lucene-Index für Volltextsuche
- Syntax: `sender-keys:`, `receiver-keys:`, `text-person-keys:`

### Register-Typen

**Schleiermacher:**

- personen, orte, werke

**Acta Borussica:**

- personen, orte, institutionen, höfe, werke, ämter

### Caching

SD nutzt JSON-Caches für Performance:

- `/db/projects/schleiermacher/cache/letters/register/letters-for-register.json`

## Deadline & Scope

**Deadline:** Montag (6 Tage ab jetzt)

**Must-Have für Demo:**

- [ ] `browse` - Collection-Navigation
- [ ] `search` - Volltextsuche
- [ ] `get_register_entry` - Register-Lookup
- [ ] `search_letters` - Brief-Suche (SD)
- [ ] `get_correspondent_stats` - Das 1810-Szenario
- [ ] Composed Server mit allen 3 Editionen

**Nice-to-Have:**

- [ ] `deep_research` - ReAct Agent
- [ ] `extract_entities` - NER auf Dokumenten
- [ ] `extract_timeline` - Chronologie

## Konventionen

### Code-Style

- Python 3.11+
- Async/await für alle I/O
- Type Hints
- Docstrings mit PURPOSE, WHEN TO USE, WHEN NOT TO USE

### Tool-Beschreibungen

```python
@mcp.tool
async def example_tool(param: str) -> dict:
    """Kurze Beschreibung.

    PURPOSE: Was macht das Tool?

    WHEN TO USE:
    - Situation A
    - Situation B

    WHEN NOT TO USE:
    - Situation C → nutze other_tool()

    Args:
        param: Beschreibung

    Returns:
        Beschreibung der Rückgabe
    """
```

### Error Handling

- `ToolError` für erwartete Fehler (leere Suche, ungültige ID)
- Logging für Debugging
- Graceful degradation

## Referenzen

- [FastMCP Dokumentation](https://gofastmcp.com/)
- [Anthropic MCP Spec](https://modelcontextprotocol.io/)
- [Schleiermacher-digital.de](https://schleiermacher-digital.de)
- [Acta Borussica](https://actaborussica.bbaw.de)
- [correspSearch](https://correspsearch.net)
