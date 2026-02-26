"""
Diary (Tageskalender) retrieval tools for Schleiermacher Digital.

This module provides tools for accessing Schleiermacher's diaries
by specific date or date range.
"""

from collections.abc import Awaitable
from datetime import datetime
from typing import Protocol, cast

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from lxml import etree

from bbaw_dse_mcp.config.base import TEI_NS, settings
from bbaw_dse_mcp.utils.existdb import ExistDBClient


class ClientGetter(Protocol):
    """Protocol for async client getter function."""

    def __call__(self) -> Awaitable[ExistDBClient]: ...


def _extract_text(elem: etree._Element) -> str:
    """Extract all text content from an XML element.

    Args:
        elem: XML element

    Returns:
        Concatenated text content
    """
    return "".join(cast("str", t) for t in elem.itertext()).strip()


def register_diary_tools(
    mcp: FastMCP,
    get_client: ClientGetter,
) -> None:
    """Register diary retrieval tools on the given MCP server.

    Args:
        mcp: The FastMCP server instance to register tools on
        get_client: Async function that returns an ExistDBClient
    """

    @mcp.tool
    async def get_diary_entry(
        date: str,
        ctx: Context | None = None,
    ) -> dict:
        """Retrieve a specific diary entry by date.

        PURPOSE: Access a specific day's entry from Schleiermacher's diary

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
            ctx: FastMCP Context

        Returns:
            Dictionary with date, content from left side, content from right side,
            and raw XML of the entry
        """
        if not date:
            raise ToolError("date is required")

        # Validate date format
        try:
            parsed_date = datetime.fromisoformat(date)
        except ValueError:
            raise ToolError(
                f"Invalid date format: {date}. Use ISO 8601 format (YYYY-MM-DD)"
            ) from None

        if ctx:
            await ctx.info(f"Fetching diary entry for: {date}")

        client = await get_client()

        # XQuery to find the specific diary entry
        xquery = f"""
        declare namespace tei = "http://www.tei-c.org/ns/1.0";

        let $entry := collection('{settings.sd_data_path}/Tageskalender')//tei:div[@type='tag'][.//tei:date[@type='tageseintrag'][@when='{date}']]
        return
            if ($entry) then
                $entry
            else
                ()
        """

        try:
            result = await client.execute_xquery(xquery)
        except Exception as e:
            raise ToolError(f"Error retrieving diary entry for {date}: {e}") from e

        if not result or result.strip() == "":
            raise ToolError(
                f"No diary entry found for {date}. "
                f"Diaries are available from 1808 to 1834."
            )

        # Parse the XML result
        try:
            entry_elem = etree.fromstring(result.encode("utf-8"))
        except etree.XMLSyntaxError as e:
            raise ToolError(f"Error parsing diary entry XML: {e}") from e

        # Extract left and right side content
        left_side = entry_elem.find(".//tei:div[@type='linke_seite']", TEI_NS)
        right_side = entry_elem.find(".//tei:div[@type='rechte_seite']", TEI_NS)

        # Get text content (simplified - just extract text for now)
        left_text = ""
        if left_side is not None:
            # Remove the date element to get only the content
            date_elem = left_side.find(".//tei:date[@type='tageseintrag']", TEI_NS)
            date_text = _extract_text(date_elem) if date_elem is not None else date

            # Get all text content
            left_text = _extract_text(left_side)
            # Remove date prefix if it's there
            if date_text and left_text.startswith(date_text):
                left_text = left_text[len(date_text) :].strip()

        right_text = ""
        if right_side is not None:
            right_text = _extract_text(right_side)

        return {
            "date": date,
            "year": parsed_date.year,
            "left_side": left_text,
            "right_side": right_text,
            "raw_xml": etree.tostring(
                entry_elem, encoding="unicode", pretty_print=True
            ),
        }

    @mcp.tool
    async def get_diary_entries(
        date_from: str,
        date_to: str,
        ctx: Context | None = None,
    ) -> list[dict]:
        """Retrieve diary entries for a date range.

        PURPOSE: Access multiple diary entries across a time period

        Available years: 1808-1811, 1817, 1820-1834. Note: 1812-1816 and 1818-1819 are not extant.

        WHEN TO USE:
        - User asks for diary entries in a date range
        - User wants to see activities over a period
        - For temporal analysis of diary content

        WHEN NOT TO USE:
        - For single date → use get_diary_entry()
        - For keyword search → use search_in_documents()

        Args:
            date_from: Start date in ISO 8601 format (YYYY-MM-DD)
            date_to: End date in ISO 8601 format (YYYY-MM-DD)
            ctx: FastMCP Context

        Returns:
            List of dictionaries, each with date, left_side, right_side content
        """
        if not date_from or not date_to:
            raise ToolError("Both date_from and date_to are required")

        # Validate date formats
        try:
            start_date = datetime.fromisoformat(date_from)
            end_date = datetime.fromisoformat(date_to)
        except ValueError as e:
            raise ToolError(
                f"Invalid date format: {e}. Use ISO 8601 format (YYYY-MM-DD)"
            ) from None

        if start_date > end_date:
            raise ToolError("date_from must be before or equal to date_to")

        if ctx:
            await ctx.info(f"Fetching diary entries from {date_from} to {date_to}")

        client = await get_client()

        # XQuery to find diary entries in the date range
        xquery = f"""
        declare namespace tei = "http://www.tei-c.org/ns/1.0";

        for $entry in collection('{settings.sd_data_path}/Tageskalender')//tei:div[@type='tag']
        let $date := $entry//tei:date[@type='tageseintrag']/@when
        where $date >= '{date_from}' and $date <= '{date_to}'
        order by $date
        return
            <entry>
                <date>{{string($date)}}</date>
                <content>{{$entry}}</content>
            </entry>
        """

        try:
            result = await client.execute_xquery(xquery)
        except Exception as e:
            raise ToolError(
                f"Error retrieving diary entries from {date_from} to {date_to}: {e}"
            ) from e

        if not result or result.strip() == "":
            return []

        # Wrap results in root element for parsing
        wrapped_result = f"<results>{result}</results>"

        try:
            root = etree.fromstring(wrapped_result.encode("utf-8"))
        except etree.XMLSyntaxError as e:
            raise ToolError(f"Error parsing diary entries XML: {e}") from e

        entries = []
        for entry_wrapper in root.findall(".//entry"):
            date_text = entry_wrapper.find("date")
            if date_text is None or not date_text.text:
                continue

            entry_date = date_text.text.strip()

            # Get the content element
            content = entry_wrapper.find("content")
            if content is None:
                continue

            # Find the actual div[@type='tag'] inside
            entry_elem = content.find(".//tei:div[@type='tag']", TEI_NS)
            if entry_elem is None:
                continue

            # Extract left and right side content
            left_side = entry_elem.find(".//tei:div[@type='linke_seite']", TEI_NS)
            right_side = entry_elem.find(".//tei:div[@type='rechte_seite']", TEI_NS)

            # Get text content
            left_text = ""
            if left_side is not None:
                # Remove the date element to get only the content
                date_elem = left_side.find(".//tei:date[@type='tageseintrag']", TEI_NS)
                date_display_text = (
                    _extract_text(date_elem) if date_elem is not None else entry_date
                )

                # Get all text content
                left_text = _extract_text(left_side)
                # Remove date prefix if it's there
                if date_display_text and left_text.startswith(date_display_text):
                    left_text = left_text[len(date_display_text) :].strip()

            right_text = ""
            if right_side is not None:
                right_text = _extract_text(right_side)

            parsed_date = datetime.fromisoformat(entry_date)

            entries.append(
                {
                    "date": entry_date,
                    "year": parsed_date.year,
                    "left_side": left_text,
                    "right_side": right_text,
                }
            )

        if ctx:
            await ctx.info(f"Found {len(entries)} diary entries")

        return entries
