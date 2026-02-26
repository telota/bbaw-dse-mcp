"""Common eXist-db tools for all digital edition servers.

This module provides reusable MCP tools that work with any eXist-db
backed edition. Use `register_common_tools()` to add them to your server.

Example:
    ```python
    from fastmcp import FastMCP
    from bbaw_dse_mcp.tools.existdb import register_common_tools

    mcp = FastMCP("My Edition")

    # Register all common tools
    register_common_tools(mcp, get_client, db_path="/db/projects/myedition/data")
    ```
"""

from collections.abc import Awaitable
from typing import Protocol

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from lxml import etree

from bbaw_dse_mcp.schemas.base.data import Collection
from bbaw_dse_mcp.schemas.base.documents import RawDocument
from bbaw_dse_mcp.schemas.base.responses import (
    CollectionContents,
    CollectionStats,
    DatabaseStatus,
    FileInfo,
)
from bbaw_dse_mcp.utils.existdb import (
    DocumentNotFoundError,
    ExistDBClient,
    ExistDBError,
    QueryError,
)


class ClientGetter(Protocol):
    """Protocol for async client getter function."""

    def __call__(self) -> Awaitable[ExistDBClient]: ...


def register_existdb_tools(  # noqa: C901, PLR0915
    mcp: FastMCP,
    get_client: ClientGetter,
    data_path: str,
    app_path: str | None = None,
) -> None:
    """Register common eXist-db tools on the given MCP server.

    Args:
        mcp: The FastMCP server instance to register tools on
        get_client: Async function that returns an ExistDBClient
        data_path: Base path to the data collection (e.g., /db/projects/schleiermacher/data)
        app_path: Optional app collection path (e.g., /db/apps/schleiermacher). Defaults to data_path.
    """
    # Use data_path as fallback for app_path if not provided
    db_app_path = app_path or data_path
    db_data_path = data_path

    @mcp.tool
    async def list_collections(parent: str = "") -> Collection:
        """List available sub-collections in the database.

        PURPOSE: Explore the database structure and find available collections.

        WHEN TO USE:
        - User wants to know what data is available
        - Exploring the database structure
        - Finding the correct collection name for other queries

        Args:
            parent: Parent collection path (relative to data_path). Empty = root.

        Returns:
            Collection object with path, collections list, and document_count
        """
        client = await get_client()

        collection_path = f"{db_data_path}/{parent}".rstrip("/")

        query = f"""
        xquery version "3.1";

        let $path := '{collection_path}'
        let $collections := xmldb:get-child-collections($path)
        let $doc-count := count(collection($path)/*)
        return
            <result>
                <path>{{$path}}</path>
                <document-count>{{$doc-count}}</document-count>
                {{for $col in $collections return <collection>{{$col}}</collection>}}
            </result>
        """

        try:
            result = await client.execute_xquery(query.strip())
        except ExistDBError as e:
            raise ToolError(f"Failed to list collections: {e}") from e

        # Parse XML response
        try:
            root = etree.fromstring(result.encode("utf-8"))
            path = root.findtext("path") or collection_path
            count_text = root.findtext("document-count") or "0"
            collections = [col.text for col in root.findall("collection") if col.text]

            return Collection(
                path=path,
                document_count=int(count_text),
                collections=collections,
            )
        except etree.XMLSyntaxError as e:
            raise ToolError(f"Failed to parse XML response: {e}") from e

    @mcp.tool
    async def list_collection_contents(
        collection: str = "",
        limit: int = 100,
        ctx: Context | None = None,
    ) -> CollectionContents:
        """List files and subcollections in a collection.

        PURPOSE: List files and subcollections without parsing document contents.

        WHEN TO USE:
        - User wants to see what's available in a collection
        - Exploring collection structure
        - Fast overview of files and folders

        WHEN NOT TO USE:
        - For document metadata → use get_file_info() afterward
        - For specific keyword search → use edition-specific search tools
        - For full document details → use get_document tools

        Args:
            collection: Collection name/path (relative to data_path). Empty = root.
            limit: Maximum number of files to return
            ctx: FastMCP Context for progress reporting

        Returns:
            Dict with 'collection_path', 'file_count', 'files', and 'subcollections'
        """
        if ctx:
            await ctx.info(f"Listing collection contents: {collection or 'root'}")

        client = await get_client()
        collection_path = f"{db_data_path}/{collection}".rstrip("/")

        try:
            filenames, subcollections = await client.list_collection_contents(
                collection_path
            )
        except ExistDBError as e:
            raise ToolError(f"Failed to browse collection: {e}") from e

        # Return limited file list
        files = filenames[:limit]

        return CollectionContents(
            collection_path=collection_path,
            file_count=len(files),
            total_files=len(filenames),
            files=files,
            subcollections=subcollections,
        )

    @mcp.tool
    async def get_file_info(
        file_path: str,
        ctx: Context | None = None,
    ) -> FileInfo:
        """Get basic metadata for a single document file.

        PURPOSE: Extract basic TEI metadata from a document without full parsing.

        WHEN TO USE:
        - After browsing, to get details about specific files
        - When you need title, date, or ID information
        - For quick metadata extraction

        WHEN NOT TO USE:
        - For full document content → use get_document tools
        - For multiple files at once → use browse then call this for each

        Args:
            file_path: Full path to the file (relative to /db) or just filename
            ctx: FastMCP Context for progress reporting

        Returns:
            Dict with 'id', 'title', 'date', 'path', 'mime_type', 'size_bytes', 'modified'
        """
        if not file_path:
            raise ToolError("file_path is required")

        if ctx:
            await ctx.info(f"Getting info for: {file_path}")

        client = await get_client()

        # Handle relative path vs full path
        if not file_path.startswith("/db"):
            # Assume it's relative to data_path
            full_path = f"{db_data_path}/{file_path}".replace("//", "/")
        else:
            full_path = file_path

        query = f"""
        xquery version "3.1";
        declare namespace tei="http://www.tei-c.org/ns/1.0";

        let $doc := doc('{full_path}')//tei:TEI
        let $id := $doc/@xml:id/string()
        let $title := ($doc//tei:titleStmt/tei:title[1]/text())[1]
        let $date := (
            $doc//tei:correspAction[@type='sent']/tei:date/@when/string(),
            $doc//tei:creation/tei:date/@when/string(),
            $doc//tei:publicationStmt/tei:date/@when/string()
        )[1]
        let $resource := '{full_path}'
        return
            <info>
                <id>{{$id}}</id>
                <title>{{$title}}</title>
                <date>{{$date}}</date>
                <mime-type>{{xmldb:get-mime-type(xs:anyURI($resource))}}</mime-type>
                <size>{{xmldb:size(collection(util:collection-name($resource)), util:document-name($resource))}}</size>
                <modified>{{xmldb:last-modified(collection(util:collection-name($resource)), util:document-name($resource))}}</modified>
            </info>
        """

        try:
            result = await client.execute_xquery(query.strip())
        except ExistDBError as e:
            raise ToolError(f"Failed to get file info: {e}") from e

        # Parse XML response
        try:
            root = etree.fromstring(result.encode("utf-8"))
            doc_id = root.findtext("id") or file_path.split("/")[-1].replace(".xml", "")
            title = root.findtext("title") or "Untitled"
            date = root.findtext("date") or None
            mime_type = root.findtext("mime-type") or "application/xml"
            size_text = root.findtext("size")
            modified = root.findtext("modified") or ""

            return FileInfo(
                id=doc_id,
                title=title,
                date=date,
                path=full_path,
                mime_type=mime_type,
                size_bytes=int(size_text) if size_text else 0,
                modified=modified,
            )
        except etree.XMLSyntaxError as e:
            raise ToolError(f"Failed to parse XML response: {e}") from e

    @mcp.tool
    async def get_collection_stats(collection: str = "") -> CollectionStats:
        """Get statistics about documents in a collection.

        PURPOSE: Understand the size and content of a collection.

        WHEN TO USE:
        - User asks "how many documents are there?"
        - Getting an overview before browsing/searching
        - Verifying data availability

        Args:
            collection: Collection path (relative to data_path). Empty = root.

        Returns:
            CollectionStats object with document counts and metadata
        """
        client = await get_client()

        collection_path = f"{db_data_path}/{collection}".rstrip("/")

        query = f"""
        xquery version "3.1";
        declare namespace tei="http://www.tei-c.org/ns/1.0";

        let $docs := collection('{collection_path}')
        let $tei-docs := $docs//tei:TEI
        return
            <stats>
                <total-files>{{count($docs/*)}}</total-files>
                <tei-documents>{{count($tei-docs)}}</tei-documents>
                <path>{collection_path}</path>
            </stats>
        """

        try:
            result = await client.execute_xquery(query.strip())
        except ExistDBError as e:
            raise ToolError(f"Failed to get collection stats: {e}") from e

        # Parse XML response
        try:
            root = etree.fromstring(result.encode("utf-8"))
            total_files_text = root.findtext("total-files") or "0"
            tei_docs_text = root.findtext("tei-documents") or "0"

            return CollectionStats(
                path=collection_path,
                total_files=int(total_files_text),
                tei_documents=int(tei_docs_text),
            )
        except etree.XMLSyntaxError as e:
            raise ToolError(f"Failed to parse XML response: {e}") from e

    @mcp.tool
    async def execute_xquery(
        query: str,
        max_results: int = 100,
    ) -> str:
        """Execute a raw XQuery against the database.

        PURPOSE: Run custom queries for advanced users or debugging.

        WHEN TO USE:
        - Other tools don't provide the needed functionality
        - Debugging or exploring data structure
        - Complex custom queries

        WHEN NOT TO USE:
        - For common operations, use specific tools instead
        - Don't use for write operations (read-only!)

        Args:
            query: XQuery string to execute
            max_results: Maximum number of results to return

        Returns:
            Raw query result as string (usually XML)
        """
        if not query or not query.strip():
            raise ToolError("Query cannot be empty")

        client = await get_client()

        try:
            return await client.execute_xquery(query.strip(), how_many=max_results)
        except QueryError as e:
            raise ToolError(f"XQuery execution failed: {e}") from e
        except ExistDBError as e:
            raise ToolError(f"Database error: {e}") from e

    @mcp.tool
    async def check_database_connection() -> DatabaseStatus:
        """Check if the database is reachable and responsive.

        PURPOSE: Verify database connectivity for troubleshooting.

        WHEN TO USE:
        - When other tools fail unexpectedly
        - To verify setup is working
        - Health monitoring

        Returns:
            DatabaseStatus object with connection status, version, and paths
        """
        client = await get_client()

        try:
            version_query = "system:get-version()"
            version = await client.execute_xquery(version_query)

            return DatabaseStatus(
                status="connected",
                version=version.strip(),
                base_url=client.base_url,
                app_path=db_app_path,
                data_path=db_data_path,
            )
        except ExistDBError as e:
            return DatabaseStatus(
                status="error",
                error=str(e),
                base_url=client.base_url,
                app_path=db_app_path,
                data_path=db_data_path,
            )

    @mcp.tool
    async def get_raw_document_by_id(
        document_id: str,
        collection: str = "",
        ctx: Context | None = None,
    ) -> RawDocument:
        """Retrieve raw XML document by its xml:id.

        PURPOSE: Fetch raw XML for a document using its TEI xml:id attribute.

        WHEN TO USE:
        - After finding a document via search or browse
        - When you need the raw XML for custom processing
        - As a low-level building block for edition-specific tools

        WHEN NOT TO USE:
        - For exploring/discovering documents → use browse or search tools
        - When you only have a file path → use get_raw_document_by_path()

        Args:
            document_id: The xml:id attribute of the TEI document
            collection: Optional collection filter (relative to data_path)
            ctx: FastMCP Context for progress reporting

        Returns:
            RawDocument with id and xml content
        """
        if not document_id:
            raise ToolError("document_id is required")

        if ctx:
            await ctx.info(f"Fetching document: {document_id}")

        client = await get_client()

        try:
            xml_str = await client.get_xml_document_by_id(document_id, collection)
        except DocumentNotFoundError as e:
            raise ToolError(f"Document '{document_id}' not found") from e
        except ExistDBError as e:
            raise ToolError(f"Database error: {e}") from e

        return RawDocument(id=document_id, xml=xml_str)

    @mcp.tool
    async def get_raw_document_by_path(
        doc_path: str,
        ctx: Context | None = None,
    ) -> RawDocument:
        """Retrieve raw XML document by its file path.

        PURPOSE: Fetch raw XML for a document using its database path.

        WHEN TO USE:
        - When you have a file path from browse_collection
        - When accessing documents with known paths
        - Faster than ID-based lookup when path is known

        WHEN NOT TO USE:
        - When you have an xml:id → use get_raw_document_by_id()
        - For exploring documents → use browse or search tools

        Args:
            doc_path: Path to the document (relative to /db)
            ctx: FastMCP Context for progress reporting

        Returns:
            RawDocument with id, xml content, and path
        """
        if not doc_path:
            raise ToolError("doc_path is required")

        if ctx:
            await ctx.info(f"Fetching document: {doc_path}")

        client = await get_client()

        try:
            xml_str = await client.get_xml_document_by_path(doc_path)
        except DocumentNotFoundError as e:
            raise ToolError(f"Document not found: {doc_path}") from e
        except ExistDBError as e:
            raise ToolError(f"Database error: {e}") from e

        # Extract ID from path or XML
        doc_id = doc_path.split("/")[-1].replace(".xml", "")

        # Try to get xml:id from the document itself
        try:
            root = etree.fromstring(xml_str.encode("utf-8"))
            xml_id = root.get("{http://www.w3.org/XML/1998/namespace}id")
            if xml_id:
                doc_id = xml_id
        except etree.XMLSyntaxError:
            pass  # Use filename-based ID

        return RawDocument(id=doc_id, xml=xml_str, path=doc_path)
