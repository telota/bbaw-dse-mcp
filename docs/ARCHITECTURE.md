# Technische Architektur

## Projektsetup

### pyproject.toml

```toml
[project]
name = "bbaw-dse-mcp"
version = "0.1.0"
description = "MCP Server für digitale wissenschaftliche Editionen"
requires-python = ">=3.11"
dependencies = [
    "fastmcp>=2.0.0",
    "httpx>=0.27.0",
    "anthropic>=0.40.0",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
]

[project.scripts]
bbaw-dse-mcp = "bbaw_dse_mcp.main:main"
```

### Verzeichnisstruktur

```
bbaw-dse-mcp/
├── pyproject.toml
├── README.md
├── AGENT.md
├── CLAUDE.md
├── docs/
│   ├── TOOLS.md              # Alle Tool-Spezifikationen
│   └── ARCHITECTURE.md       # Code-Struktur und Beispiele
├── src/
│   └── bbaw_dse_mcp/
│       ├── main.py            # Entry Point, Composed Server
│       ├── config/
│       │   ├── base.py        # Settings, Konstanten
│       │   └── existdb.py     # eXist-db Konfiguration
│       ├── schemas/
│       │   ├── base/          # Shared Pydantic models
│       │   │   ├── data.py
│       │   │   ├── documents.py
│       │   │   ├── responses.py
│       │   │   └── tei.py
│       │   ├── correspsearch/
│       │   │   └── correspsearch.py
│       │   ├── mop/
│       │   │   └── mop.py
│       │   └── schleiermacher/
│       │       ├── documents.py
│       │       ├── register.py
│       │       └── responses.py
│       ├── servers/
│       │   ├── schleiermacher/
│       │   │   ├── server.py
│       │   │   ├── resources/     # MCP Resources (prompts, guides)
│       │   │   ├── tools/
│       │   │   │   ├── chronology.py
│       │   │   │   ├── diaries.py
│       │   │   │   ├── docs.py
│       │   │   │   ├── register.py
│       │   │   │   └── search.py
│       │   │   └── utils/
│       │   │       ├── citations.py
│       │   │       ├── documents.py
│       │   │       ├── existdb.py
│       │   │       └── letters.py
│       │   ├── mop/
│       │   │   ├── server.py
│       │   │   ├── resources/     # MCP Resources
│       │   │   ├── tools/
│       │   │   │   ├── adjutanten.py
│       │   │   │   ├── biogramm.py
│       │   │   │   ├── register.py
│       │   │   │   ├── search.py
│       │   │   │   └── wohntopo.py
│       │   │   └── utils/
│       │   └── correspsearch/
│       │       ├── server.py
│       │       ├── tools/
│       │       │   └── search.py
│       │       └── utils/
│       │           ├── api.py
│       │           └── search.py
│       ├── tools/
│       │   ├── base.py            # Shared tool utilities
│       │   ├── existdb.py         # eXist-db tool helpers
│       │   └── research_agent.py  # ReAct Deep Research Agent
│       └── utils/
│           ├── existdb.py         # eXist-db Client
│           ├── geonames.py        # GeoNames API
│           ├── gnd.py             # GND authority data
│           ├── tei.py             # TEI XML utilities
│           └── wikidata.py        # Wikidata queries
```

---

## Konfiguration

### config.py

```python
from pydantic_settings import BaseSettings
from pydantic import Field

class EditionConfig(BaseSettings):
    """Konfiguration für eine einzelne Edition."""
    name: str
    base_url: str
    rest_path: str = "/exist/rest"
    username: str | None = None
    password: str | None = None

class Settings(BaseSettings):
    """Globale Einstellungen."""

    # Schleiermacher
    sd_url: str = Field(default="https://schleiermacher-digital.de")
    sd_db_path: str = Field(default="/db/projects/schleiermacher/data")
    sd_username: str | None = Field(default=None)
    sd_password: str | None = Field(default=None)

    # Acta Borussica
    ab_url: str = Field(default="https://actaborussica.bbaw.de")
    ab_db_path: str = Field(default="/db/projects/actaborussica/data")
    ab_username: str | None = Field(default=None)
    ab_password: str | None = Field(default=None)

    # correspSearch
    cs_api_url: str = Field(default="https://correspsearch.net/api/v1.1")

    # Anthropic (für deep_research Agent)
    anthropic_api_key: str | None = Field(default=None)
    research_model: str = Field(default="claude-sonnet-4-20250514")

    class Config:
        env_file = ".env"
        env_prefix = "EDITIONS_"

settings = Settings()
```

---

## eXist-db Client

### existdb.py

```python
import httpx
from typing import Any
from xml.etree import ElementTree as ET

class ExistDBClient:
    """Async HTTP Client für eXist-db REST API."""

    def __init__(
        self,
        base_url: str,
        db_path: str,
        username: str | None = None,
        password: str | None = None
    ):
        self.base_url = base_url.rstrip("/")
        self.db_path = db_path
        self.auth = (username, password) if username else None
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                auth=self.auth,
                timeout=30.0
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def execute_xquery(
        self,
        query: str,
        variables: dict[str, Any] | None = None
    ) -> str:
        """Führe eine XQuery aus und gib das Ergebnis zurück."""
        client = await self._get_client()

        # XQuery mit Variablen-Deklarationen
        if variables:
            var_decls = "\n".join(
                f'declare variable ${k} external := "{v}";'
                for k, v in variables.items()
            )
            query = f"{var_decls}\n{query}"

        response = await client.post(
            "/exist/rest/db",
            content=query,
            headers={
                "Content-Type": "application/xquery",
            },
            params={
                "_howmany": "1000",
                "_wrap": "no"
            }
        )
        response.raise_for_status()
        return response.text

    async def get_document(self, doc_path: str) -> str:
        """Hole ein XML-Dokument."""
        client = await self._get_client()
        response = await client.get(f"/exist/rest{self.db_path}/{doc_path}")
        response.raise_for_status()
        return response.text

    async def list_collection(self, collection_path: str = "") -> dict:
        """Liste Inhalt einer Collection."""
        query = f'''
        xquery version "3.1";
        let $path := "{self.db_path}/{collection_path}"
        return
        <result>
            <path>{{$path}}</path>
            <collections>{{
                for $col in xmldb:get-child-collections($path)
                order by $col
                return <c>{{$col}}</c>
            }}</collections>
            <resources>{{
                for $res in xmldb:get-child-resources($path)
                order by $res
                return <r>{{$res}}</r>
            }}</resources>
        </result>
        '''
        result = await self.execute_xquery(query)
        return self._parse_collection_result(result)

    async def fulltext_search(
        self,
        query: str,
        collection: str | None = None,
        limit: int = 20
    ) -> list[dict]:
        """Lucene Volltextsuche."""
        search_path = f"{self.db_path}/{collection}" if collection else self.db_path

        xquery = f'''
        xquery version "3.1";
        import module namespace ft="http://exist-db.org/xquery/lucene";
        declare namespace tei="http://www.tei-c.org/ns/1.0";

        let $query := "{query}"
        let $hits := collection("{search_path}")//tei:TEI[ft:query(., $query)]
        return
        <results total="{{count($hits)}}">{{
            for $hit in subsequence($hits, 1, {limit})
            let $score := ft:score($hit)
            order by $score descending
            return
            <hit score="{{$score}}">
                <id>{{$hit/@xml:id/string()}}</id>
                <title>{{$hit//tei:titleStmt/tei:title/string()}}</title>
            </hit>
        }}</results>
        '''
        result = await self.execute_xquery(xquery)
        return self._parse_search_result(result)

    async def search_register(
        self,
        register_type: str,
        query: str,
        limit: int = 10
    ) -> list[dict]:
        """Durchsuche ein Register."""
        # Register-Pfade je nach Typ
        register_paths = {
            "personen": "Register/Personen",
            "orte": "Register/Orte",
            "werke": "Register/Werke",
        }
        reg_path = register_paths.get(register_type, f"Register/{register_type}")

        xquery = f'''
        xquery version "3.1";
        declare namespace tei="http://www.tei-c.org/ns/1.0";

        let $query := lower-case("{query}")
        let $entries := collection("{self.db_path}/{reg_path}")//tei:*[
            @xml:id and
            contains(lower-case(string-join(.//text(), ' ')), $query)
        ]
        return
        <results>{{
            for $e in subsequence($entries, 1, {limit})
            return
            <entry>
                <id>{{$e/@xml:id/string()}}</id>
                <name>{{normalize-space($e/(tei:persName[@type='reg']|tei:placeName[@type='reg']|tei:title)/string())}}</name>
            </entry>
        }}</results>
        '''
        result = await self.execute_xquery(xquery)
        return self._parse_register_result(result)

    def _parse_collection_result(self, xml_str: str) -> dict:
        """Parse Collection-Listing XML."""
        root = ET.fromstring(xml_str)
        return {
            "path": root.findtext("path", ""),
            "collections": [c.text for c in root.findall(".//c") if c.text],
            "resources": [r.text for r in root.findall(".//r") if r.text],
        }

    def _parse_search_result(self, xml_str: str) -> list[dict]:
        """Parse Suchergebnis XML."""
        root = ET.fromstring(xml_str)
        return [
            {
                "id": hit.findtext("id", ""),
                "title": hit.findtext("title", ""),
                "score": float(hit.get("score", 0)),
            }
            for hit in root.findall(".//hit")
        ]

    def _parse_register_result(self, xml_str: str) -> list[dict]:
        """Parse Register-Ergebnis XML."""
        root = ET.fromstring(xml_str)
        return [
            {
                "id": entry.findtext("id", ""),
                "name": entry.findtext("name", ""),
            }
            for entry in root.findall(".//entry")
        ]
```

---

## Base Server Class

### base.py

```python
from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError
from .existdb import ExistDBClient

class EdiarumEditionServer:
    """Basis-Klasse für Ediarum-basierte Editionen."""

    def __init__(
        self,
        name: str,
        db_client: ExistDBClient,
        register_types: list[str]
    ):
        self.name = name
        self.db = db_client
        self.register_types = register_types
        self.mcp = FastMCP(name)
        self._register_tools()

    def _register_tools(self):
        """Registriere die Standard-Tools."""

        @self.mcp.tool
        async def browse(path: str = "/") -> dict:
            """Navigiere durch die Collection-Hierarchie.

            PURPOSE: Orientierung - "Was gibt es hier?"

            WHEN TO USE:
            - Exploration der Editionsstruktur
            - Überblick ohne konkretes Suchziel

            WHEN NOT TO USE:
            - Konkrete Suche → search()
            """
            try:
                return await self.db.list_collection(path.lstrip("/"))
            except Exception as e:
                raise ToolError(f"Fehler beim Navigieren: {e}")

        @self.mcp.tool
        async def search(
            query: str,
            collection: str | None = None,
            limit: int = 20
        ) -> dict:
            """Volltextsuche in der Edition.

            PURPOSE: Finde Dokumente nach Suchbegriffen.

            WHEN TO USE:
            - Suche nach Themen oder Begriffen
            - Offene Exploration

            WHEN NOT TO USE:
            - Personensuche → search_register("personen", ...)
            - Strukturierte Briefsuche → search_letters()
            """
            if len(query) < 2:
                raise ToolError("Suchbegriff muss mindestens 2 Zeichen haben")

            results = await self.db.fulltext_search(query, collection, limit)
            return {
                "query": query,
                "collection": collection,
                "total": len(results),
                "results": results
            }

        @self.mcp.tool
        async def list_registers() -> dict:
            """Liste alle verfügbaren Register-Typen.

            PURPOSE: Zeige welche Register (Personen, Orte, etc.) es gibt.
            """
            return {
                "edition": self.name,
                "registers": self.register_types
            }

        @self.mcp.tool
        async def search_register(
            register: str,
            query: str,
            limit: int = 10
        ) -> dict:
            """Durchsuche ein Register.

            PURPOSE: Finde Einträge in Personen-, Orts-, Werkregister etc.

            WHEN TO USE:
            - "Wer ist X?" → search_register("personen", "X")
            - Vor get_register_entry() um ID zu finden
            """
            if register not in self.register_types:
                raise ToolError(
                    f"Unbekannter Register-Typ: {register}. "
                    f"Verfügbar: {', '.join(self.register_types)}"
                )

            results = await self.db.search_register(register, query, limit)
            return {
                "register": register,
                "query": query,
                "results": results
            }

        @self.mcp.tool
        async def get_register_entry(
            register: str,
            entry_id: str
        ) -> dict:
            """Hole Details zu einem Register-Eintrag.

            PURPOSE: Vollständige Infos zu Person, Ort, Werk.

            WHEN TO USE:
            - "Wer ist X?" (wenn ID bekannt)
            - Details nach search_register()

            WHEN NOT TO USE:
            - ID unbekannt → erst search_register()
            - Komplexe Recherche → deep_research()
            """
            # Implementierung abhängig von Edition
            return await self._get_register_entry_impl(register, entry_id)

        @self.mcp.tool
        async def get_document(
            doc_id: str,
            include_text: bool = True
        ) -> dict:
            """Hole ein Dokument mit Metadaten und optional Volltext.

            PURPOSE: Detailansicht eines bekannten Dokuments.

            WHEN TO USE:
            - User will spezifisches Dokument lesen
            - Follow-up nach Suchergebnis
            """
            return await self._get_document_impl(doc_id, include_text)

    async def _get_register_entry_impl(self, register: str, entry_id: str) -> dict:
        """Überschreiben für editions-spezifische Implementierung."""
        raise NotImplementedError

    async def _get_document_impl(self, doc_id: str, include_text: bool) -> dict:
        """Überschreiben für editions-spezifische Implementierung."""
        raise NotImplementedError
```

---

## Schleiermacher Server

### servers/schleiermacher.py

```python
from fastmcp import Context
from fastmcp.exceptions import ToolError
from ..base import EdiarumEditionServer
from ..existdb import ExistDBClient
from ..config import settings

class SchleiermaherServer(EdiarumEditionServer):
    """MCP Server für Schleiermacher-digital.de"""

    def __init__(self):
        db_client = ExistDBClient(
            base_url=settings.sd_url,
            db_path=settings.sd_db_path,
            username=settings.sd_username,
            password=settings.sd_password
        )
        super().__init__(
            name="schleiermacher",
            db_client=db_client,
            register_types=["personen", "orte", "werke"]
        )
        self._register_sd_specific_tools()

    def _register_sd_specific_tools(self):
        """Registriere SD-spezifische Tools."""

        @self.mcp.tool
        async def search_letters(
            sender: str | None = None,
            recipient: str | None = None,
            year: int | None = None,
            query: str | None = None,
            limit: int = 50
        ) -> dict:
            """Durchsuche den Briefwechsel mit strukturierten Filtern.

            PURPOSE: Gezielte Suche in der Korrespondenz.

            WHEN TO USE:
            - Briefe nach Korrespondent filtern
            - Briefe eines bestimmten Jahres
            - "Zeig mir alle Briefe von/an X"

            WHEN NOT TO USE:
            - Statistiken → get_correspondent_stats()
            - Komplexe Analyse → deep_research()

            Args:
                sender: Person-ID des Absenders (z.B. "S00456")
                recipient: Person-ID des Empfängers
                year: Jahr (z.B. 1810)
                query: Zusätzlicher Volltext-Filter
                limit: Max. Ergebnisse
            """
            # Baue Lucene-Query
            query_parts = []
            if sender:
                query_parts.append(f"sender-keys:{sender}")
            if recipient:
                query_parts.append(f"receiver-keys:{recipient}")
            if query:
                query_parts.append(query)

            lucene_query = " AND ".join(query_parts) if query_parts else "*"

            # Collection-Filter für Jahr
            collection = f"Briefe/{year}" if year else "Briefe"

            results = await self.db.fulltext_search(
                lucene_query,
                collection,
                limit
            )

            return {
                "filters": {
                    "sender": sender,
                    "recipient": recipient,
                    "year": year,
                    "query": query
                },
                "total": len(results),
                "letters": results
            }

        @self.mcp.tool
        async def get_correspondent_stats(
            year: int | None = None
        ) -> dict:
            """Statistik über Korrespondenzpartner.

            PURPOSE: Analysiere wer die wichtigsten Briefpartner waren.
            Dies ist das zentrale Tool für "Wer war wichtig 1810?"

            WHEN TO USE:
            - "Wer war wichtig für Schleiermacher in Jahr X?"
            - "Mit wem korrespondierte er am meisten?"
            - Überblick über Korrespondenz-Netzwerk

            WHEN NOT TO USE:
            - Details zu einzelnen Briefen → search_letters()
            - Biografische Infos → get_register_entry()

            Args:
                year: Optional, filtert auf ein bestimmtes Jahr
            """
            collection = f"Briefe/{year}" if year else "Briefe"

            xquery = f'''
            xquery version "3.1";
            declare namespace tei="http://www.tei-c.org/ns/1.0";

            let $letters := collection("{self.db.db_path}/{collection}")//tei:TEI[.//tei:correspDesc]
            let $correspondents :=
                for $action in $letters//tei:correspAction
                let $person := $action/tei:persName[@key != 'S0003610']  (: Nicht Schleiermacher selbst :)
                where $person
                group by $key := $person/@key
                let $name := ($person)[1]/string()
                let $sent := count($action[@type='sent'])
                let $received := count($action[@type='received'])
                order by ($sent + $received) descending
                return
                <c key="{{$key}}" name="{{$name}}" sent="{{$sent}}" received="{{$received}}" total="{{$sent + $received}}"/>

            return
            <result year="{year or 'all'}" total="{{count($letters)}}">
                {{subsequence($correspondents, 1, 20)}}
            </result>
            '''

            result = await self.db.execute_xquery(xquery)
            return self._parse_correspondent_stats(result, year)

        @self.mcp.tool
        async def get_calendar_entries(
            date_from: str,
            date_to: str
        ) -> dict:
            """Hole Tageskalender-Einträge für einen Zeitraum.

            PURPOSE: Was hat Schleiermacher an bestimmten Tagen gemacht?

            WHEN TO USE:
            - Zeitliche Einordnung von Ereignissen
            - "Was passierte im März 1810?"
            - Kontext zu Briefen

            Args:
                date_from: Startdatum (ISO: "1810-03-01")
                date_to: Enddatum (ISO: "1810-03-31")
            """
            xquery = f'''
            xquery version "3.1";
            declare namespace tei="http://www.tei-c.org/ns/1.0";

            for $entry in collection("{self.db.db_path}/Tageskalender")//tei:item
            let $date := $entry/tei:date/@when/string()
            where $date >= "{date_from}" and $date <= "{date_to}"
            order by $date
            return
            <entry date="{{$date}}">
                <content>{{normalize-space($entry)}}</content>
            </entry>
            '''

            result = await self.db.execute_xquery(xquery)
            return self._parse_calendar_entries(result)

    def _parse_correspondent_stats(self, xml_str: str, year: int | None) -> dict:
        """Parse Korrespondenten-Statistik."""
        from xml.etree import ElementTree as ET
        root = ET.fromstring(xml_str)

        correspondents = []
        for c in root.findall(".//c"):
            correspondents.append({
                "person_id": c.get("key"),
                "name": c.get("name"),
                "letters_sent": int(c.get("sent", 0)),
                "letters_received": int(c.get("received", 0)),
                "total": int(c.get("total", 0))
            })

        context = ""
        if year == 1810:
            context = ("1810 war das Jahr der Berliner Universitätsgründung, "
                      "an der Schleiermacher als Gründungsdekan maßgeblich beteiligt war.")

        return {
            "year": year,
            "total_letters": int(root.get("total", 0)),
            "correspondents": correspondents,
            "context": context
        }

    def _parse_calendar_entries(self, xml_str: str) -> dict:
        """Parse Kalender-Einträge."""
        from xml.etree import ElementTree as ET
        # Wrap in root element if needed
        if not xml_str.strip().startswith("<"):
            return {"entries": []}

        try:
            root = ET.fromstring(f"<r>{xml_str}</r>")
            entries = [
                {
                    "date": e.get("date"),
                    "content": e.findtext("content", "")
                }
                for e in root.findall(".//entry")
            ]
            return {"entries": entries}
        except ET.ParseError:
            return {"entries": [], "error": "Parse error"}

    async def _get_register_entry_impl(self, register: str, entry_id: str) -> dict:
        """SD-spezifische Register-Abfrage."""
        # Nutze die vorhandene XQuery-Logik aus dem hochgeladenen Code
        xquery = f'''
        xquery version "3.1";
        declare namespace tei="http://www.tei-c.org/ns/1.0";

        let $entry := collection("{self.db.db_path}/Register")//tei:*[@xml:id = "{entry_id}"]
        return
        if ($entry) then
            <result>
                <id>{entry_id}</id>
                <type>{{local-name($entry)}}</type>
                <name>{{normalize-space(($entry/tei:persName[@type='reg']|$entry/tei:placeName[@type='reg']|$entry/tei:title)[1])}}</name>
                <gnd>{{$entry/tei:idno/text()}}</gnd>
                {{if ($entry/tei:birth) then <birth>{{$entry/tei:birth/text()}}</birth> else ()}}
                {{if ($entry/tei:death) then <death>{{$entry/tei:death/text()}}</death> else ()}}
                {{if ($entry/tei:note) then <note>{{$entry/tei:note/string()}}</note> else ()}}
            </result>
        else
            <error>Entry not found: {entry_id}</error>
        '''

        result = await self.db.execute_xquery(xquery)
        return self._parse_register_entry(result)

    def _parse_register_entry(self, xml_str: str) -> dict:
        """Parse Register-Eintrag."""
        from xml.etree import ElementTree as ET
        root = ET.fromstring(xml_str)

        if root.tag == "error":
            raise ToolError(root.text)

        return {
            "id": root.findtext("id"),
            "type": root.findtext("type"),
            "name": root.findtext("name"),
            "gnd_id": root.findtext("gnd"),
            "dates": {
                "birth": root.findtext("birth"),
                "death": root.findtext("death")
            },
            "description": root.findtext("note")
        }

    async def _get_document_impl(self, doc_id: str, include_text: bool) -> dict:
        """SD-spezifische Dokument-Abfrage."""
        # Vereinfachte Implementierung
        xquery = f'''
        xquery version "3.1";
        declare namespace tei="http://www.tei-c.org/ns/1.0";

        let $doc := collection("{self.db.db_path}")//tei:TEI[@xml:id = "{doc_id}"]
        return
        if ($doc) then
            <result>
                <id>{doc_id}</id>
                <title>{{$doc//tei:titleStmt/tei:title/string()}}</title>
                {{if ({str(include_text).lower()}) then
                    <text>{{normalize-space($doc//tei:text)}}</text>
                else ()}}
            </result>
        else
            <error>Document not found: {doc_id}</error>
        '''

        result = await self.db.execute_xquery(xquery)
        return self._parse_document(result)

    def _parse_document(self, xml_str: str) -> dict:
        from xml.etree import ElementTree as ET
        root = ET.fromstring(xml_str)

        if root.tag == "error":
            raise ToolError(root.text)

        return {
            "id": root.findtext("id"),
            "title": root.findtext("title"),
            "text": root.findtext("text")
        }


# Singleton-Instanz
schleiermacher_server = SchleiermaherServer()
```

---

## Main Entry Point

### main.py

```python
from fastmcp import FastMCP
from .servers.schleiermacher import schleiermacher_server
from .servers.actaborussica import actaborussica_server
from .servers.correspsearch import correspsearch_server
from .agents.research import register_research_tool

def create_app() -> FastMCP:
    """Erstelle den kombinierten MCP Server."""

    # Hauptserver
    app = FastMCP("Digital Editions")

    # Compose alle Edition-Server
    app.mount("sd", schleiermacher_server.mcp)
    app.mount("ab", actaborussica_server.mcp)
    app.mount("cs", correspsearch_server.mcp)

    # Registriere den Deep Research Agent als globales Tool
    register_research_tool(app)

    return app

def main():
    """CLI Entry Point."""
    app = create_app()
    app.run()

if __name__ == "__main__":
    main()
```

---

## Deep Research Agent

### agents/research.py

```python
import json
from anthropic import Anthropic
from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError
from ..config import settings

# Interne Tool-Funktionen (werden vom Agent genutzt)
async def _search_edition(edition: str, query: str, limit: int = 10) -> dict:
    """Interne Suche - wird vom Agent aufgerufen."""
    from ..servers.schleiermacher import schleiermacher_server
    from ..servers.actaborussica import actaborussica_server

    if edition == "schleiermacher":
        return await schleiermacher_server.db.fulltext_search(query, None, limit)
    elif edition == "actaborussica":
        return await actaborussica_server.db.fulltext_search(query, None, limit)
    else:
        raise ValueError(f"Unknown edition: {edition}")

async def _get_person(edition: str, person_id: str) -> dict:
    """Interne Person-Abfrage."""
    from ..servers.schleiermacher import schleiermacher_server
    from ..servers.actaborussica import actaborussica_server

    if edition == "schleiermacher":
        return await schleiermacher_server._get_register_entry_impl("personen", person_id)
    elif edition == "actaborussica":
        return await actaborussica_server._get_register_entry_impl("personen", person_id)

async def _search_letters(year: int = None, correspondent: str = None) -> dict:
    """Interne Brief-Suche (nur SD)."""
    from ..servers.schleiermacher import schleiermacher_server
    # Direkter Aufruf der internen Logik
    ...

# Tool-Definitionen für den Agent
AGENT_TOOLS = [
    {
        "name": "search_edition",
        "description": "Durchsuche eine Edition nach Stichworten",
        "input_schema": {
            "type": "object",
            "properties": {
                "edition": {
                    "type": "string",
                    "enum": ["schleiermacher", "actaborussica"],
                    "description": "Welche Edition durchsuchen"
                },
                "query": {
                    "type": "string",
                    "description": "Suchbegriff"
                }
            },
            "required": ["edition", "query"]
        }
    },
    {
        "name": "get_person",
        "description": "Hole Details zu einer Person aus dem Register",
        "input_schema": {
            "type": "object",
            "properties": {
                "edition": {"type": "string", "enum": ["schleiermacher", "actaborussica"]},
                "person_id": {"type": "string", "description": "Die XML-ID der Person"}
            },
            "required": ["edition", "person_id"]
        }
    },
    {
        "name": "get_correspondent_stats",
        "description": "Statistik der Korrespondenzpartner für ein Jahr (nur Schleiermacher)",
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "description": "Das Jahr"}
            },
            "required": ["year"]
        }
    },
    {
        "name": "finish_research",
        "description": "Beende die Recherche und gib den finalen Report zurück",
        "input_schema": {
            "type": "object",
            "properties": {
                "report": {"type": "string", "description": "Der finale Recherche-Bericht"},
                "sources": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Liste der verwendeten Quellen"
                }
            },
            "required": ["report", "sources"]
        }
    }
]

async def execute_agent_tool(name: str, input: dict) -> dict:
    """Führe ein Agent-Tool aus."""
    if name == "search_edition":
        return await _search_edition(input["edition"], input["query"])
    elif name == "get_person":
        return await _get_person(input["edition"], input["person_id"])
    elif name == "get_correspondent_stats":
        from ..servers.schleiermacher import schleiermacher_server
        # Direkter Aufruf
        ...
    elif name == "finish_research":
        return {"finished": True, **input}
    else:
        raise ValueError(f"Unknown tool: {name}")


def register_research_tool(app: FastMCP):
    """Registriere das deep_research Tool."""

    @app.tool
    async def deep_research(
        query: str,
        editions: list[str] = ["schleiermacher", "actaborussica"],
        max_steps: int = 10,
        ctx: Context = None
    ) -> dict:
        """Führe eine autonome, mehrstufige Recherche durch.

        PURPOSE: Komplexe Forschungsfragen die mehrere Suchen und Synthese erfordern.

        WHEN TO USE:
        - Komplexe, offene Forschungsfragen
        - Fragen die mehrere Editionen betreffen
        - Analysen die Zusammenhänge erfordern

        WHEN NOT TO USE:
        - Einfache Fakten-Fragen → get_register_entry()
        - Einzelne Suchen → search()
        - Wenn schnelle Antwort nötig (dauert 30-60 Sekunden)

        Args:
            query: Die Forschungsfrage in natürlicher Sprache
            editions: Welche Editionen durchsucht werden sollen
            max_steps: Maximale Schritte (Sicherheitslimit)
        """
        if not settings.anthropic_api_key:
            raise ToolError("Anthropic API Key nicht konfiguriert für deep_research")

        client = Anthropic(api_key=settings.anthropic_api_key)

        if ctx:
            await ctx.info(f"Starte Deep Research: {query}")

        system_prompt = f"""Du bist ein Recherche-Agent für digitale wissenschaftliche Editionen.

Verfügbare Editionen: {', '.join(editions)}

- schleiermacher: Briefwechsel, Tageskalender, Vorlesungen von Friedrich Schleiermacher
- actaborussica: Preußische Staatsquellen, Protokolle, Journale

Deine Aufgabe: Beantworte die Forschungsfrage systematisch.

Vorgehen:
1. Plane deine Recherche-Strategie
2. Nutze die Tools um Informationen zu sammeln
3. Verknüpfe Ergebnisse aus verschiedenen Quellen
4. Rufe finish_research auf wenn du genug Informationen hast

Wichtig: Zitiere immer deine Quellen (Dokument-IDs, Personen-IDs)."""

        messages = [{"role": "user", "content": query}]
        sources = []
        steps = 0

        while steps < max_steps:
            if ctx:
                await ctx.report_progress(steps, max_steps)

            response = client.messages.create(
                model=settings.research_model,
                max_tokens=4096,
                system=system_prompt,
                tools=AGENT_TOOLS,
                messages=messages
            )

            # Sammle Tool-Aufrufe
            tool_uses = [b for b in response.content if b.type == "tool_use"]

            if not tool_uses:
                # Agent ist fertig ohne finish_research
                final_text = next(
                    (b.text for b in response.content if b.type == "text"),
                    "Keine Ergebnisse"
                )
                return {
                    "query": query,
                    "report": final_text,
                    "sources": sources,
                    "steps_taken": steps
                }

            # Führe Tools aus
            tool_results = []
            for tool_use in tool_uses:
                if tool_use.name == "finish_research":
                    # Agent ist fertig
                    return {
                        "query": query,
                        "report": tool_use.input.get("report", ""),
                        "sources": tool_use.input.get("sources", []) + sources,
                        "steps_taken": steps
                    }

                try:
                    result = await execute_agent_tool(tool_use.name, tool_use.input)
                    sources.append({
                        "tool": tool_use.name,
                        "input": tool_use.input,
                        "step": steps
                    })
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(result, ensure_ascii=False)
                    })
                except Exception as e:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": f"Error: {str(e)}",
                        "is_error": True
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
            steps += 1

        # Max steps erreicht
        return {
            "query": query,
            "report": "Maximale Schritte erreicht. Partielle Ergebnisse.",
            "sources": sources,
            "steps_taken": steps,
            "incomplete": True
        }
```