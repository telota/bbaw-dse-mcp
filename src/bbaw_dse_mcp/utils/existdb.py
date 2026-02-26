"""HTTP client for eXist-db REST API.

Supports both local and remote eXist-db instances.

Local development:
    - Default: http://localhost:8080
    - Default credentials: admin / (empty or "admin")

Remote (schleiermacher-digital.de):
    - HTTPS with optional authentication

Example:
    ```python
    # Local development
    config = ExistDBConfig.local(
        app_path="/db/apps/schleiermacher",
        data_path="/db/projects/schleiermacher/data"
    )
    async with ExistDBClient(config) as client:
        result = await client.execute_xquery("...")

    # Remote
    config = ExistDBConfig.remote(
        base_url="https://schleiermacher-digital.de",
        app_path="/db/apps/schleiermacher",
        data_path="/db/projects/schleiermacher/data"
    )
    async with ExistDBClient(config) as client:
        result = await client.execute_xquery("...")
    ```
"""

from __future__ import annotations

from http import HTTPStatus
import logging
from typing import TYPE_CHECKING, NoReturn, cast

import httpx
from lxml import etree

if TYPE_CHECKING:
    from types import TracebackType

    from bbaw_dse_mcp.config.existdb import ExistDBConfig

logger = logging.getLogger(__name__)


class ExistDBError(Exception):
    """Base exception for eXist-db errors."""

    pass


class ExistDBConnectionError(ExistDBError):
    """Connection error (server not reachable)."""

    pass


class QueryError(ExistDBError):
    """XQuery execution error."""

    pass


class DocumentNotFoundError(ExistDBError):
    """Document not found."""

    pass


class ExistDBClient:
    """Async HTTP Client for eXist-db REST API.

    Can be used as a context manager or directly:

        # As context manager (recommended):
        async with ExistDBClient(config) as client:
            result = await client.execute_xquery("...")

        # Direct usage (requires manual close()):
        client = ExistDBClient(config)
        try:
            result = await client.execute_xquery("...")
        finally:
            await client.close()
    """

    def __init__(self, config: ExistDBConfig) -> None:
        """Initialize eXist-db Client.

        Args:
            config: ExistDBConfig with connection parameters
        """
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self.app_path = config.app_path
        self.data_path = config.data_path
        # Default REST endpoint uses app_path for backwards compatibility
        self.rest_endpoint = f"{self.base_url}/exist/rest{config.app_path}"

        # Use httpx.BasicAuth for explicit authentication
        auth = None
        if config.username and config.password is not None:
            auth = httpx.BasicAuth(username=config.username, password=config.password)

        self._client: httpx.AsyncClient | None = None
        self._auth = auth
        self._timeout = config.timeout

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy-initialized HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                auth=self._auth,
                timeout=self._timeout,
                follow_redirects=True,
            )
        return self._client

    async def __aenter__(self) -> ExistDBClient:
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> bool:
        """Check if eXist-db is reachable.

        Returns:
            True if server is reachable, False otherwise.
        """
        try:
            response = await self.client.get(f"{self.base_url}/exist/")
            return response.status_code < HTTPStatus.INTERNAL_SERVER_ERROR
        except httpx.ConnectError:
            return False
        except httpx.TimeoutException:
            return False

    def _handle_http_error(
        self, error: httpx.HTTPStatusError, context: str
    ) -> NoReturn:
        """Convert HTTP errors to specific exceptions."""
        status = error.response.status_code
        if status == HTTPStatus.NOT_FOUND:
            raise DocumentNotFoundError(f"{context}: Not found") from error
        if status == HTTPStatus.UNAUTHORIZED:
            raise ExistDBError(f"{context}: Authentication failed") from error
        if status == HTTPStatus.FORBIDDEN:
            raise ExistDBError(f"{context}: Access denied") from error
        raise QueryError(f"{context}: HTTP {status}") from error

    def _handle_connection_error(self) -> NoReturn:
        """Convert connection errors to specific exception."""
        raise ExistDBConnectionError(
            f"Cannot connect to eXist-db at {self.base_url}. "
            f"Is the server running? (Local: java -jar start.jar)"
        )

    async def execute_xquery(
        self,
        query: str,
        how_many: int = 1000,
        *,
        wrap: bool = False,
    ) -> str:
        """Execute XQuery against eXist-db REST API.

        Args:
            query: XQuery as string
            how_many: Maximum number of results (_howmany parameter)
            wrap: Whether results should be wrapped in XML (keyword-only)

        Returns:
            Response text (XML or plain text, depending on query)

        Raises:
            QueryError: On XQuery errors
            ExistDBConnectionError: When server is not reachable
        """
        try:
            # eXist-db REST API: Use _query parameter for XQuery
            response = await self.client.get(
                f"{self.base_url}/exist/rest/db",
                params={
                    "_query": query,
                    "_howmany": str(how_many),
                    "_wrap": "yes" if wrap else "no",
                },
            )
            response.raise_for_status()
            return response.text

        except httpx.ConnectError as e:
            raise ExistDBConnectionError(
                f"Cannot connect to eXist-db at {self.base_url}. "
                f"Is the server running? (Local: java -jar start.jar)"
            ) from e

        except httpx.HTTPStatusError as e:
            raise QueryError(f"XQuery execution failed: {e.response.text}") from e

    async def get_xml_document_by_path(self, doc_path: str) -> str:
        """Retrieve document via REST using relative file path.

        Args:
            doc_path: Path relative to collection (e.g., "briefe/1810-03-15.xml")

        Returns:
            XML string of the document

        Raises:
            DocumentNotFoundError: When document does not exist
            ExistDBConnectionError: When server is not reachable
        """
        try:
            # Build full URL: /exist/rest/db/{doc_path}
            # Note: doc_path should already include collection prefix if needed
            url = f"{self.base_url}/exist/rest/db/{doc_path}"

            logger.debug("Fetching document: %s", url)
            response = await self.client.get(url)
            response.raise_for_status()

            logger.debug("Document returned %d chars", len(response.text))
            return response.text

        except httpx.HTTPStatusError as e:
            if e.response.status_code == HTTPStatus.NOT_FOUND:
                raise DocumentNotFoundError(f"Document not found: {doc_path}") from e
            self._handle_http_error(e, "Document retrieval")

        except httpx.ConnectError:
            self._handle_connection_error()

    async def get_document_raw(self, absolute_path: str) -> str:
        """Retrieve document via REST using absolute database path.

        Args:
            absolute_path: Absolute path in database (e.g., "/db/projects/schleiermacher/cache/data.json")

        Returns:
            Document content as string (XML, JSON, or text)

        Raises:
            DocumentNotFoundError: When document does not exist
            ExistDBConnectionError: When server is not reachable
        """
        try:
            # Strip leading /db/ if present, since REST endpoint already includes it
            path = absolute_path.lstrip("/")
            if path.startswith("db/"):
                path = path[3:]  # Remove 'db/' prefix

            url = f"{self.base_url}/exist/rest/db/{path}"

            logger.debug("Fetching raw document: %s", url)
            response = await self.client.get(url)
            response.raise_for_status()

            logger.debug("Document returned %d chars", len(response.text))
            return response.text

        except httpx.HTTPStatusError as e:
            if e.response.status_code == HTTPStatus.NOT_FOUND:
                raise DocumentNotFoundError(
                    f"Document not found: {absolute_path}"
                ) from e
            self._handle_http_error(e, "Document retrieval")

        except httpx.ConnectError:
            self._handle_connection_error()

    async def get_xml_document_by_id(self, doc_id: str, collection: str = "") -> str:
        """Retrieve document via XQuery using xml:id.

        Args:
            doc_id: The xml:id of the document
            collection: Optional collection filter (e.g., "Briefe")

        Returns:
            XML string of the document

        Raises:
            DocumentNotFoundError: When document is not found
            ExistDBConnectionError: When server is not reachable
        """
        logger.debug("Fetching document by ID: %s", doc_id)

        # If collection is absolute path, use it; otherwise append to data_path
        if collection and collection.startswith("/db"):
            collection_path = collection
        else:
            collection_path = (
                f"{self.data_path}/{collection}" if collection else self.data_path
            )

        query = f"""
        xquery version "3.1";
        declare namespace tei="http://www.tei-c.org/ns/1.0";

        let $doc := collection('{collection_path}')//tei:TEI[@xml:id='{doc_id}']
        return
            if (exists($doc)) then
                $doc
            else
                ()
        """

        result = await self.execute_xquery(query.strip(), how_many=1)

        if not result.strip():
            raise DocumentNotFoundError(
                f"Document with ID '{doc_id}' not found in {collection_path}"
            )

        return result

    async def list_collection_contents(
        self, collection_path: str
    ) -> tuple[list[str], list[str]]:
        """List resource filenames and subcollections using REST API.

        This is much faster than XQuery-based methods as it uses
        a simple HTTP GET to the collection path.

        Args:
            collection_path: Full absolute collection path (e.g., /db/projects/data/Briefe)

        Returns:
            Tuple of (resource filenames, subcollection names)

        Raises:
            ExistDBConnectionError: When server is not reachable
        """
        try:
            # Simple REST GET returns XML listing of collection contents
            response = await self.client.get(
                f"{self.base_url}/exist/rest{collection_path}"
            )
            response.raise_for_status()

            # Parse XML response to extract resource names and subcollections

            root = etree.fromstring(response.content)
            ns = {"exist": "http://exist.sourceforge.net/NS/exist"}

            # Find all <exist:resource> elements
            # xpath() returns various types, but attribute queries always return lists
            resources = cast(
                "list", root.xpath("//exist:resource/@name", namespaces=ns)
            )

            # Find subcollections - the first <exist:collection> is the parent,
            # nested ones are subcollections
            all_collections = cast(
                "list", root.xpath("//exist:collection/@name", namespaces=ns)
            )
            # Skip the first one (parent collection itself)
            subcollections = all_collections[1:] if len(all_collections) > 1 else []

            return [str(r) for r in resources], [str(c) for c in subcollections]

        except httpx.ConnectError:
            self._handle_connection_error()
        except httpx.HTTPStatusError as e:
            self._handle_http_error(e, "List resources")

    async def search_fulltext(
        self,
        search_term: str,
        collection: str = "",
        max_results: int = 100,
    ) -> list[dict[str, str]]:
        """Full-text search via Lucene (ft:query).

        Args:
            search_term: Search term (Lucene syntax)
            collection: Path relative to data_path
            max_results: Maximum results

        Returns:
            List of dicts with 'id', 'title', 'snippet'
        """
        collection_path = (
            f"{self.data_path}/{collection}" if collection else self.data_path
        )

        # Escape single quotes in search term
        safe_term = search_term.replace("'", "''")

        query = f"""
        xquery version "3.1";
        declare namespace tei="http://www.tei-c.org/ns/1.0";
        declare namespace ft="http://exist-db.org/xquery/lucene";

        for $doc in collection('{collection_path}')//tei:TEI[ft:query(., '{safe_term}')]
        let $id := $doc/@xml:id/string()
        let $title := $doc//tei:titleStmt/tei:title[1]/text()
        return concat($id, '|||', $title)
        """

        result = await self.execute_xquery(query.strip(), how_many=max_results)

        # Parse "id|||title" format
        results = []
        for line in result.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("|||")
            if len(parts) >= 2:  # noqa: PLR2004
                results.append({"id": parts[0], "title": parts[1], "snippet": ""})

        return results

    async def count_documents(self, collection: str = "") -> int:
        """Count documents in a collection.

        Args:
            collection: Path relative to data_path

        Returns:
            Number of TEI documents
        """
        collection_path = (
            f"{self.data_path}/{collection}" if collection else self.data_path
        )

        query = f"""
        xquery version "3.1";
        declare namespace tei="http://www.tei-c.org/ns/1.0";

        count(collection('{collection_path}')//tei:TEI)
        """

        result = await self.execute_xquery(query.strip())
        try:
            return int(result.strip())
        except ValueError:
            return 0
