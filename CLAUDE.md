# CLAUDE.md - Kontext für Claude Code

## Projekt

**bbaw-dse-mcp**: MCP-Server für digitale Editionen (DHd2026 Poster)

## Aktueller Stand

Neues Projekt, Start bei Null. Deadline: Montag.

## Sofort-Kontext

### Was wir bauen

```
User: "Suche nach Briefen, die Humboldt erwähnen"
  ↓
Agent prüft Verbindung, ruft search_by_keyword() auf
  ↓
User: "Zeige mir den Brief vom März 1810"
  ↓
Agent ruft get_document() auf (behält Kontext!)
  ↓
Agent kann nahtlos zu correspSearch wechseln
```

### Die 3 Editionen

1. **schleiermacher digital** (SD) - Komplexe Briefedition, eXist-db/Ediarum
2. **Praktiken der Monarchie / Acta Borussica** (AB) - Dokumentensammlung, eXist-db/Ediarum
3. **correspSearch** (CS) - Korrespondenznetzwerk-Recherche, REST API

### Kern-Tools (Priorität)

```python
# MUST HAVE für Demo
browse(path) → Collection-Navigation
search(query) → Volltextsuche
get_register_entry(type, id) → "Wer ist X?"
search_letters(year, correspondent) → Brief-Filter
get_correspondent_stats(year) → "Wer war wichtig 1810?" ← HAUPT-DEMO

# NICE TO HAVE
deep_research(query) → ReAct Agent für komplexe Fragen
```

## Befehle

```bash
# Setup
cd /path/to/bbaw-dse-mcp
uv init
uv add fastmcp httpx anthropic pydantic-settings

# Server starten
uv run bbaw-dse-mcp

# In Claude Desktop config
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

## eXist-db Zugriff

```python
# REST API Pattern
POST /exist/rest/db
Content-Type: application/xquery

xquery version "3.1";
declare namespace tei="http://www.tei-c.org/ns/1.0";
collection("/db/projects/schleiermacher/data")//tei:TEI[@xml:id = "1810-05-21_v_Humboldt"]
```

## Wichtige IDs

- Personen: `S00xxx` (Schleiermacher selbst: S0003610)
- Orte: `O00xxx`
- Briefe: `YYYY-MM-DD_v_Name` oder `YYYY-MM-DD_a_Name`

## Lucene-Felder (SD)

```
sender-keys:S00456      # Absender
receiver-keys:S00456    # Empfänger
text-person-keys:S00456 # Erwähnung im Text
```

## Wenn ich frage...

**"Implementiere browse"** → Siehe `docs/TOOLS.md` für Spezifikation

**"Wie funktioniert X in eXist-db"** → Schau in die hochgeladenen XQuery-Files für Patterns

**"Teste den Server"** → `uv run python -c "from editions_mcp.main import create_app; print(create_app())"`

## Files die existieren

- `AGENT.md` - Projekt-Übersicht
- `docs/TOOLS.md` - Detaillierte Tool-Specs
- `docs/ARCHITECTURE.md` - Code-Struktur und Beispiele
- `.github/copilot-instructions.md` - Kurzreferenz

## Nächste Schritte

1. `pyproject.toml` erstellen
2. `src/editions_mcp/` Struktur anlegen
3. `existdb.py` Client implementieren
4. Erste Tools: browse, search
5. Testen gegen echte eXist-db
