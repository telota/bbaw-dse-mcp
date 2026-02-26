"""
Chronology retrieval tools for Schleiermacher Digital.

This module provides tools for accessing chronological entries
from Schleiermacher's life by specific date, date range, or year.
"""

from collections.abc import Awaitable
from datetime import datetime
import re
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
        Concatenated text content with normalized whitespace
    """
    raw_text = "".join(cast("str", t) for t in elem.itertext())
    # Normalize all whitespace (newlines, tabs, multiple spaces) to single space
    return re.sub(r"\s+", " ", raw_text).strip()


def _parse_chronology_item(item: etree._Element) -> dict:
    """Parse a single chronology item element.

    Args:
        item: XML item element

    Returns:
        Dictionary with date info and event text
    """
    # Find the date element
    date_elem = item.find(".//tei:date", TEI_NS)
    if date_elem is None:
        return {}

    # Extract date attributes
    date_attrs = {
        "when": date_elem.get("when"),
        "notBefore": date_elem.get("notBefore"),
        "notAfter": date_elem.get("notAfter"),
        "cert": date_elem.get("cert"),
        "calendar": date_elem.get("calendar"),
    }

    # Get the date text (display text like "August 29" or "Im Jahr")
    date_text = _extract_text(date_elem)

    # Get the event text (everything in the item except the date element)
    full_text = _extract_text(item)
    event_text = full_text
    if date_text and full_text.startswith(date_text):
        event_text = full_text[len(date_text) :].strip()

    return {
        "date_display": date_text,
        "when": date_attrs["when"],
        "notBefore": date_attrs["notBefore"],
        "notAfter": date_attrs["notAfter"],
        "cert": date_attrs["cert"],
        "event": event_text,
    }


def register_chronology_tools(  # noqa: C901
    mcp: FastMCP,
    get_client: ClientGetter,
) -> None:
    """Register chronology retrieval tools on the given MCP server.

    Args:
        mcp: The FastMCP server instance to register tools on
        get_client: Async function that returns an ExistDBClient
    """

    @mcp.tool
    async def get_chronology_entry(
        date: str,
        ctx: Context | None = None,
    ) -> list[dict]:
        """Retrieve chronology entries for a specific date.

        PURPOSE: Access events from Schleiermacher's life on a specific date

        WHEN TO USE:
        - User asks what happened on a specific date
        - User wants biographical information for a particular day
        - After search → get full chronology entry

        WHEN NOT TO USE:
        - For date range → use get_chronology_entries()
        - For entire year → use get_chronology_year()
        - For keyword search → use search_documents()

        Args:
            date: Date in ISO 8601 format (YYYY-MM-DD), e.g., "1785-08-29"
            ctx: FastMCP Context

        Returns:
            List of dictionaries with date info and event descriptions.
            Multiple events may occur on the same date.
        """
        if not date:
            raise ToolError("date is required")

        # Validate date format
        try:
            datetime.fromisoformat(date)
        except ValueError:
            raise ToolError(
                f"Invalid date format: {date}. Use ISO 8601 format (YYYY-MM-DD)"
            ) from None

        if ctx:
            await ctx.info(f"Fetching chronology entries for: {date}")

        client = await get_client()

        # XQuery to find chronology items with matching date
        xquery = f"""
        declare namespace tei = "http://www.tei-c.org/ns/1.0";

        for $item in collection('{settings.sd_data_path}/Chronologie')//tei:item
        let $date := $item//tei:date
        let $when := $date/@when
        let $notBefore := $date/@notBefore
        let $notAfter := $date/@notAfter
        where $when = '{date}'
           or ($notBefore <= '{date}' and $notAfter >= '{date}')
        return $item
        """

        try:
            result = await client.execute_xquery(xquery)
        except Exception as e:
            raise ToolError(f"Error retrieving chronology for {date}: {e}") from e

        if not result or result.strip() == "":
            return []

        # Wrap results in root element for parsing
        wrapped_result = f"<results>{result}</results>"

        try:
            root = etree.fromstring(wrapped_result.encode("utf-8"))
        except etree.XMLSyntaxError as e:
            raise ToolError(f"Error parsing chronology XML: {e}") from e

        entries = []
        for item in root.findall(".//tei:item", TEI_NS):
            parsed = _parse_chronology_item(item)
            if parsed:
                entries.append(parsed)

        if ctx and entries:
            await ctx.info(f"Found {len(entries)} chronology entries for {date}")

        return entries

    @mcp.tool
    async def get_chronology_entries(
        date_from: str,
        date_to: str,
        ctx: Context | None = None,
    ) -> list[dict]:
        """Retrieve chronology entries for a date range.

        PURPOSE: Access events from Schleiermacher's life across a time period

        WHEN TO USE:
        - User asks what happened during a specific period
        - User wants biographical timeline for a date range
        - For temporal analysis of Schleiermacher's life events

        WHEN NOT TO USE:
        - For single date → use get_chronology_entry()
        - For entire year → use get_chronology_year()
        - For keyword search → use search_documents()

        Args:
            date_from: Start date in ISO 8601 format (YYYY-MM-DD)
            date_to: End date in ISO 8601 format (YYYY-MM-DD)
            ctx: FastMCP Context

        Returns:
            List of dictionaries with date info and event descriptions,
            sorted chronologically. Includes both specific dates and date ranges
            that overlap with the query range.
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
            await ctx.info(f"Fetching chronology entries from {date_from} to {date_to}")

        client = await get_client()

        # XQuery to find chronology items in the date range
        # Include items where:
        # - @when is within range
        # - date range (@notBefore/@notAfter) overlaps with query range
        xquery = f"""
        declare namespace tei = "http://www.tei-c.org/ns/1.0";

        for $item in collection('{settings.sd_data_path}/Chronologie')//tei:item
        let $date := $item//tei:date
        let $when := $date/@when
        let $notBefore := $date/@notBefore
        let $notAfter := $date/@notAfter
        where ($when >= '{date_from}' and $when <= '{date_to}')
           or ($notBefore and $notAfter and
               not($notAfter < '{date_from}' or $notBefore > '{date_to}'))
        order by
            if ($when) then $when
            else if ($notBefore) then $notBefore
            else '0000-00-00'
        return $item
        """

        try:
            result = await client.execute_xquery(xquery)
        except Exception as e:
            raise ToolError(
                f"Error retrieving chronology from {date_from} to {date_to}: {e}"
            ) from e

        if not result or result.strip() == "":
            return []

        # Wrap results in root element for parsing
        wrapped_result = f"<results>{result}</results>"

        try:
            root = etree.fromstring(wrapped_result.encode("utf-8"))
        except etree.XMLSyntaxError as e:
            raise ToolError(f"Error parsing chronology XML: {e}") from e

        entries = []
        for item in root.findall(".//tei:item", TEI_NS):
            parsed = _parse_chronology_item(item)
            if parsed:
                entries.append(parsed)

        if ctx and entries:
            await ctx.info(
                f"Found {len(entries)} chronology entries from {date_from} to {date_to}"
            )

        return entries

    @mcp.tool
    async def get_chronology_year(
        year: int,
        ctx: Context | None = None,
    ) -> dict:
        """Retrieve all chronology entries for a specific year.

        PURPOSE: Access complete biographical timeline for a year in Schleiermacher's life

        WHEN TO USE:
        - User asks "What happened in 1785?"
        - User wants overview of activities in a specific year
        - For annual biographical summaries

        WHEN NOT TO USE:
        - For specific date → use get_chronology_entry()
        - For date range spanning multiple years → use get_chronology_entries()
        - For keyword search → use search_documents()

        Args:
            year: Year (e.g., 1785)
            ctx: FastMCP Context

        Returns:
            Dictionary with year, heading, and list of chronology entries.
            Entries are sorted chronologically within the year.
        """
        if not year:
            raise ToolError("year is required")

        # Validate year
        if year < 1768 or year > 1834:
            raise ToolError(
                f"Year {year} is outside Schleiermacher's lifetime (1768-1834)"
            )

        if ctx:
            await ctx.info(f"Fetching chronology for year: {year}")

        client = await get_client()

        # XQuery to load the chronology document for this year directly
        # Each year has its own XML file: 1768.xml, 1772.xml, etc.
        xquery = f"""
        declare namespace tei = "http://www.tei-c.org/ns/1.0";

        let $doc := doc('{settings.sd_data_path}/Chronologie/Chronologie/{year}.xml')
        return
            if ($doc) then
                <year>
                    <heading>{{$doc//tei:div/tei:head/text()}}</heading>
                    <items>{{
                        for $item in $doc//tei:item
                        return $item
                    }}</items>
                </year>
            else
                ()
        """

        try:
            result = await client.execute_xquery(xquery)
        except Exception as e:
            raise ToolError(f"Error retrieving chronology for year {year}: {e}") from e

        if not result or result.strip() == "":
            raise ToolError(
                f"No chronology found for year {year}. "
                f"Chronology covers Schleiermacher's lifetime (1768-1834)."
            )

        try:
            root = etree.fromstring(result.encode("utf-8"))
        except etree.XMLSyntaxError as e:
            raise ToolError(f"Error parsing chronology XML: {e}") from e

        # Extract heading
        heading_elem = root.find(".//heading")
        heading = (
            heading_elem.text if heading_elem is not None else f"Chronology {year}"
        )

        # Extract all items
        items_container = root.find(".//items")
        entries = []

        if items_container is not None:
            for item in items_container.findall(".//tei:item", TEI_NS):
                parsed = _parse_chronology_item(item)
                if parsed:
                    entries.append(parsed)

        if ctx:
            await ctx.info(f"Found {len(entries)} entries for year {year}")

        return {
            "year": year,
            "heading": heading,
            "entries": entries,
        }
