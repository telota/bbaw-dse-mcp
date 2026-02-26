# bbaw-dse-mcp

An [MCP server](https://modelcontextprotocol.io/) for dialogical, exploratory access to digital scholarly editions.

> **DHd2026 Poster**: *Agenten im Dienst der Edition*

## Overview

Instead of complex search forms and navigation structures, this MCP server enables **natural-language conversation** with digital scholarly editions. An AI agent translates questions like *"Who was important for Schleiermacher in 1810?"* into structured database queries — and maintains conversational context across follow-up questions.

The server aggregates three editions from [BBAW](https://www.bbaw.de/)/[TELOTA](https://www.bbaw.de/bbaw-digital/telota) into a single MCP endpoint using [FastMCP](https://gofastmcp.com/) composition:

| Edition | Prefix | Backend | Content |
|---|---|---|---|
| [schleiermacher digital](https://schleiermacher-digital.de) | `sd_` | eXist-db | Letters, diaries, lectures, chronology |
| [Praktiken der Monarchie](https://actaborussica.bbaw.de) | `mop_` | eXist-db | Documents on Prussian monarchy and governance |
| [correspSearch](https://correspsearch.net) | `cs_` | REST API | Cross-edition correspondence network search |

## Available Tools

### Schleiermacher Digital (`sd_*`) — 19 tools

| Tool | Description |
|---|---|
| `sd_search_documents` | Fulltext search with facets (document type, year, date range) |
| `sd_filter_letters` | Filter letters by sender, receiver, place, period |
| `sd_get_correspondent_stats` | Correspondent statistics for network analysis |
| `sd_get_document_by_id` | Retrieve a complete document as Markdown |
| `sd_get_document_passages` | Retrieve text passages from a document |
| `sd_search_register` | Lucene fulltext search in person/place/work registers |
| `sd_get_register_entry` | Detailed register entry with optional mention summary |
| `sd_get_diary_entry` / `sd_get_diary_entries` | Diary entries by date or date range |
| `sd_get_chronology_entry` / `sd_get_chronology_entries` / `sd_get_chronology_year` | Chronology lookup |
| `sd_list_collections` / `sd_list_collection_contents` | Browse collection structure |
| `sd_get_collection_stats` / `sd_get_file_info` | Collection and file metadata |
| `sd_execute_xquery` | Execute raw XQuery |
| `sd_check_database_connection` | Health check |
| `sd_get_raw_document_by_id` / `sd_get_raw_document_by_path` | Raw XML retrieval |

### Praktiken der Monarchie (`mop_*`) — 17 tools

| Tool | Description |
|---|---|
| `mop_browse_documents` | Browse files and subcollections |
| `mop_search_documents` | Fulltext search in MoP documents |
| `mop_get_document` | Retrieve a complete document |
| `mop_search_register` / `mop_get_register_entry` | Search registers (persons, places, institutions, courts, works, offices) |
| `mop_search_biogramme` / `mop_get_biogramm_by_id` | Search and retrieve detailed biographies |
| `mop_extract_family_network` | Extract family network from a biography |
| `mop_get_residential_topography` / `mop_search_residential_topography` / `mop_list_available_wohntopo_years` | Residential topography data |
| `mop_search_adjutanten_journals` / `mop_get_adjutanten_journal_entry` / `mop_list_adjutanten_by_monarch` | Court adjutant journals |
| `mop_execute_xquery` | Execute raw XQuery |
| `mop_check_database_connection` | Health check |

### correspSearch (`cs_*`) — 8 tools

| Tool | Description |
|---|---|
| `cs_search_correspondences` | Cross-edition correspondence search |
| `cs_get_edition_info` | Information about a correspSearch edition |
| `cs_search_correspondent_network` | Analyze correspondence network of a person |
| `cs_search_for_gnd_id` | Look up GND authority IDs by name |
| `cs_search_for_geonames_id` / `cs_get_place_geonames_id` | Look up GeoNames IDs |
| `cs_search_wikidata_entity` / `cs_search_for_wikidata_occupation` | Wikidata lookups |

## Installation

```bash
# Clone the repository
git clone https://github.com/telota/bbaw-dse-mcp.git
cd bbaw-dse-mcp

# Install with uv (recommended)
uv sync
```

Requires Python 3.11+.

## Configuration

Configuration uses environment variables (prefix `EDITIONS_`). Create a `.env` file:

```env
# Schleiermacher Digital eXist-db
EDITIONS_SD_URL=http://localhost:8080
EDITIONS_SD_USERNAME=admin
EDITIONS_SD_PASSWORD=

# Praktiken der Monarchie eXist-db
EDITIONS_AB_URL=https://actaborussica.bbaw.de
EDITIONS_AB_USERNAME=
EDITIONS_AB_PASSWORD=

# correspSearch API (no auth required)
EDITIONS_CS_API_URL=https://correspsearch.net/api/v2.0

# Optional: GeoNames API
EDITIONS_GEONAMES_USERNAME=

# Optional: Anthropic API (for research agent)
EDITIONS_ANTHROPIC_API_KEY=
```

## Usage

### Running the server

```bash
uv run bbaw-dse-mcp
```

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "editions": {
      "command": "uv",
      "args": ["run", "bbaw-dse-mcp"],
      "cwd": "/path/to/bbaw-dse-mcp"
    }
  }
}
```

### Example Conversation

```
User: Search for letters mentioning Humboldt.

Agent: → sd_search_documents(query="Humboldt", doc_type="letters")
       Found 23 letters mentioning Humboldt, mostly from 1810 —
       the year of the Berlin university founding...

User: Who was important for Schleiermacher in 1810?

Agent: → sd_get_correspondent_stats(year=1810)
       Based on letter frequency, the most important correspondents in 1810:
       1. Charlotte Schleiermacher (15 letters) — his sister
       2. Wilhelm von Humboldt (8 letters) — central figure in university reform
       ...

User: Can we trace Humboldt's correspondence network beyond this edition?

Agent: → cs_search_correspondent_network(name="Humboldt, Wilhelm von")
       Cross-edition network across 12 editions: ...
```

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│               bbaw-dse-mcp (FastMCP Composed)                │
├──────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌─────────────┐  ┌────────────────┐  │
│  │  schleiermacher   │  │     mop     │  │  correspsearch │  │
│  │   19 tools        │  │  17 tools   │  │    8 tools     │  │
│  └────────┬─────────┘  └──────┬──────┘  └───────┬────────┘  │
└───────────┼────────────────────┼─────────────────┼───────────┘
            │                    │                 │
      ┌─────▼─────┐       ┌─────▼─────┐     ┌─────▼──────┐
      │  eXist-db  │       │  eXist-db  │     │  REST API  │
      │  (Ediarum) │       │  (Ediarum) │     │   (CMIF)   │
      └───────────┘        └───────────┘     └────────────┘
```

## Tech Stack

- **[FastMCP](https://gofastmcp.com/) 2.x** — Python MCP server framework
- **[httpx](https://www.python-httpx.org/)** — Async HTTP client for eXist-db REST API
- **[lxml](https://lxml.de/)** — TEI-XML parsing
- **[Pydantic](https://docs.pydantic.dev/) v2** — Data models and settings

## Documentation

- [AGENT.md](./AGENT.md) — Project overview and design decisions
- [docs/TOOLS.md](./docs/TOOLS.md) — Detailed tool specifications
- [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) — Technical architecture

## License

MIT

## Author

Tim Westphal, [BBAW TELOTA](https://www.bbaw.de/bbaw-digital/telota)
