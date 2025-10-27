"""MCP Server for Second Brain - Exposes visual memory to AI tools."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field
import structlog

from mcp.server.fastmcp import FastMCP, Context
from ..database.db import Database
from ..config import Config

logger = structlog.get_logger()


# Pydantic models for structured responses

class TextBlock(BaseModel):
    """Represents an OCR-extracted text block from a screenshot."""
    block_id: str
    text: str
    confidence: Optional[float] = None
    block_type: Optional[str] = None


class FrameMetadata(BaseModel):
    """Metadata for a captured screenshot frame."""
    frame_id: str
    timestamp: int
    iso_timestamp: str
    window_title: Optional[str] = None
    app_name: Optional[str] = None
    app_bundle_id: Optional[str] = None
    file_path: str
    screen_resolution: Optional[str] = None


class SearchResult(BaseModel):
    """A single search result combining frame and text block data."""
    frame: FrameMetadata
    text_block: TextBlock
    relevance_score: Optional[float] = Field(
        None,
        description="BM25 relevance score (lower is better)"
    )


class SearchResults(BaseModel):
    """Collection of search results."""
    query: str
    total_results: int
    results: List[SearchResult]


class FrameContext(BaseModel):
    """Complete context for a specific frame."""
    frame: FrameMetadata
    text_blocks: List[TextBlock]
    screenshot_path: str


class Timeline(BaseModel):
    """Chronological sequence of frames."""
    start_timestamp: int
    end_timestamp: int
    frame_count: int
    frames: List[FrameMetadata]


class AppActivity(BaseModel):
    """Application-specific frame activity."""
    app_bundle_id: str
    app_name: Optional[str] = None
    frame_count: int
    frames: List[FrameMetadata]


class AppStats(BaseModel):
    """Statistics for an application."""
    app_bundle_id: str
    app_name: str
    first_seen: int
    last_seen: int
    frame_count: int


class UsageStats(BaseModel):
    """Overall usage statistics."""
    total_frames: int
    total_text_blocks: int
    total_apps: int
    database_size_mb: float
    oldest_frame: Optional[int] = None
    newest_frame: Optional[int] = None
    top_apps: List[AppStats]


def create_mcp_server(
    config: Optional[Config] = None,
    db: Optional[Database] = None
) -> FastMCP:
    """
    Create and configure the MCP server for Second Brain.

    Args:
        config: Configuration instance (defaults to global config)
        db: Database instance (creates new if not provided)

    Returns:
        Configured FastMCP server instance
    """
    config = config or Config()
    db = db or Database(config=config)

    mcp = FastMCP("Second Brain Memory")

    def _parse_date(date_str: Optional[str]) -> Optional[int]:
        """Convert YYYY-MM-DD string to Unix timestamp."""
        if not date_str:
            return None
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return int(dt.timestamp())
        except ValueError:
            logger.warning("invalid_date_format", date_str=date_str)
            return None

    def _frame_to_metadata(frame: dict) -> FrameMetadata:
        """Convert database frame dict to FrameMetadata model."""
        return FrameMetadata(
            frame_id=frame["frame_id"],
            timestamp=frame["timestamp"],
            iso_timestamp=datetime.fromtimestamp(frame["timestamp"]).isoformat(),
            window_title=frame.get("window_title"),
            app_name=frame.get("app_name"),
            app_bundle_id=frame.get("app_bundle_id"),
            file_path=frame["file_path"],
            screen_resolution=frame.get("screen_resolution")
        )

    def _text_block_to_model(block: dict) -> TextBlock:
        """Convert database text block dict to TextBlock model."""
        return TextBlock(
            block_id=block["block_id"],
            text=block["text"],
            confidence=block.get("confidence"),
            block_type=block.get("block_type")
        )

    @mcp.tool()
    async def search_memory(
        query: str,
        app_filter: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 10,
        ctx: Optional[Context] = None
    ) -> SearchResults:
        """
        Search visual memory using full-text search across OCR-extracted text.

        This searches all captured screenshots and their OCR text content. Results are
        ranked by BM25 relevance (lower score = better match).

        Args:
            query: Search query (supports FTS5 syntax, e.g., "python OR javascript")
            app_filter: Optional app bundle ID to filter (e.g., "com.apple.Safari")
            start_date: Optional start date in YYYY-MM-DD format
            end_date: Optional end date in YYYY-MM-DD format
            limit: Maximum number of results (default: 10, max: 100)

        Returns:
            SearchResults with matching frames and text blocks

        Examples:
            - search_memory("authentication error")
            - search_memory("def process_data", app_filter="com.microsoft.VSCode")
            - search_memory("TODO", start_date="2025-10-01", end_date="2025-10-27")
        """
        if ctx:
            await ctx.info(f"Searching visual memory for: {query}")

        limit = min(limit, 100)  # Cap at 100 results

        start_ts = _parse_date(start_date)
        end_ts = _parse_date(end_date)

        try:
            results = db.search_text(
                query=query,
                app_filter=app_filter,
                start_timestamp=start_ts,
                end_timestamp=end_ts,
                limit=limit
            )

            search_results = []
            for row in results:
                frame = FrameMetadata(
                    frame_id=row["frame_id"],
                    timestamp=row["timestamp"],
                    iso_timestamp=datetime.fromtimestamp(row["timestamp"]).isoformat(),
                    window_title=row.get("window_title"),
                    app_name=row.get("app_name"),
                    app_bundle_id=row.get("app_bundle_id"),
                    file_path=row["file_path"],
                    screen_resolution=None
                )

                text_block = TextBlock(
                    block_id=row["block_id"],
                    text=row["text"],
                    confidence=row.get("confidence"),
                    block_type=None
                )

                search_results.append(SearchResult(
                    frame=frame,
                    text_block=text_block,
                    relevance_score=row.get("score")
                ))

            if ctx:
                await ctx.info(f"Found {len(search_results)} results")

            return SearchResults(
                query=query,
                total_results=len(search_results),
                results=search_results
            )

        except Exception as e:
            logger.error("search_memory_error", error=str(e))
            if ctx:
                await ctx.error(f"Search failed: {str(e)}")
            return SearchResults(query=query, total_results=0, results=[])

    @mcp.tool()
    async def get_frame_context(
        frame_id: str,
        ctx: Optional[Context] = None
    ) -> FrameContext:
        """
        Get complete context for a specific frame including all OCR text blocks.

        This retrieves detailed information about a captured screenshot, including
        all extracted text blocks and the path to the screenshot file.

        Args:
            frame_id: The unique frame identifier

        Returns:
            FrameContext with frame metadata, text blocks, and screenshot path

        Example:
            get_frame_context("550e8400-e29b-41d4-a716-446655440000")
        """
        if ctx:
            await ctx.info(f"Retrieving context for frame: {frame_id}")

        try:
            # Get frame metadata
            frame_data = db.get_frame(frame_id)
            if not frame_data:
                if ctx:
                    await ctx.error(f"Frame not found: {frame_id}")
                raise ValueError(f"Frame not found: {frame_id}")

            # Get text blocks
            text_blocks_data = db.get_text_blocks_by_frame(frame_id)

            frame = _frame_to_metadata(frame_data)
            text_blocks = [_text_block_to_model(block) for block in text_blocks_data]

            # Construct full screenshot path
            frames_dir = config.get_frames_dir()
            screenshot_path = str(frames_dir / frame_data["file_path"])

            return FrameContext(
                frame=frame,
                text_blocks=text_blocks,
                screenshot_path=screenshot_path
            )

        except Exception as e:
            logger.error("get_frame_context_error", error=str(e), frame_id=frame_id)
            if ctx:
                await ctx.error(f"Failed to get frame context: {str(e)}")
            raise

    @mcp.tool()
    async def get_timeline(
        start_date: str,
        end_date: str,
        app_filter: Optional[str] = None,
        limit: int = 50,
        ctx: Optional[Context] = None
    ) -> Timeline:
        """
        Get chronological sequence of frames within a time range.

        This retrieves all captured frames between two dates, optionally filtered
        by application. Useful for reconstructing work sessions or activity patterns.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            app_filter: Optional app bundle ID to filter
            limit: Maximum number of frames (default: 50, max: 500)

        Returns:
            Timeline with frames in chronological order

        Example:
            get_timeline("2025-10-26", "2025-10-27", app_filter="com.apple.Terminal")
        """
        if ctx:
            await ctx.info(f"Retrieving timeline from {start_date} to {end_date}")

        start_ts = _parse_date(start_date)
        end_ts = _parse_date(end_date)

        if not start_ts or not end_ts:
            error_msg = "Invalid date format. Use YYYY-MM-DD"
            if ctx:
                await ctx.error(error_msg)
            raise ValueError(error_msg)

        limit = min(limit, 500)  # Cap at 500 frames

        try:
            frames_data = db.get_frames(
                limit=limit,
                app_bundle_id=app_filter,
                start_timestamp=start_ts,
                end_timestamp=end_ts
            )

            frames = [_frame_to_metadata(f) for f in frames_data]

            if ctx:
                await ctx.info(f"Retrieved {len(frames)} frames")

            return Timeline(
                start_timestamp=start_ts,
                end_timestamp=end_ts,
                frame_count=len(frames),
                frames=frames
            )

        except Exception as e:
            logger.error("get_timeline_error", error=str(e))
            if ctx:
                await ctx.error(f"Failed to get timeline: {str(e)}")
            raise

    @mcp.tool()
    async def get_app_activity(
        app_bundle_id: str,
        limit: int = 20,
        ctx: Optional[Context] = None
    ) -> AppActivity:
        """
        Get recent frames from a specific application.

        This retrieves the most recent captured frames from a particular application,
        useful for understanding recent work in a specific tool (IDE, browser, terminal).

        Args:
            app_bundle_id: Application bundle identifier (e.g., "com.microsoft.VSCode")
            limit: Maximum number of frames (default: 20, max: 200)

        Returns:
            AppActivity with recent frames from the specified application

        Examples:
            - get_app_activity("com.microsoft.VSCode")
            - get_app_activity("com.apple.Safari", limit=50)
        """
        if ctx:
            await ctx.info(f"Retrieving activity for app: {app_bundle_id}")

        limit = min(limit, 200)  # Cap at 200 frames

        try:
            frames_data = db.get_frames_by_app(
                app_bundle_id=app_bundle_id,
                limit=limit
            )

            frames = [_frame_to_metadata(f) for f in frames_data]

            app_name = frames[0].app_name if frames else None

            if ctx:
                await ctx.info(f"Found {len(frames)} frames")

            return AppActivity(
                app_bundle_id=app_bundle_id,
                app_name=app_name,
                frame_count=len(frames),
                frames=frames
            )

        except Exception as e:
            logger.error("get_app_activity_error", error=str(e), app_bundle_id=app_bundle_id)
            if ctx:
                await ctx.error(f"Failed to get app activity: {str(e)}")
            raise

    @mcp.tool()
    async def get_usage_stats(
        ctx: Optional[Context] = None
    ) -> UsageStats:
        """
        Get overall usage statistics and most-used applications.

        This provides a high-level summary of captured data including total frames,
        text blocks, database size, and top applications by usage.

        Returns:
            UsageStats with system-wide statistics

        Example:
            get_usage_stats()
        """
        if ctx:
            await ctx.info("Retrieving usage statistics")

        try:
            db_stats = db.get_database_stats()
            app_stats_data = db.get_app_usage_stats(limit=10)

            top_apps = [
                AppStats(
                    app_bundle_id=app["app_bundle_id"],
                    app_name=app["app_name"],
                    first_seen=app["first_seen"],
                    last_seen=app["last_seen"],
                    frame_count=app["frame_count"]
                )
                for app in app_stats_data
            ]

            db_size_mb = db_stats["database_size_bytes"] / (1024 * 1024)

            return UsageStats(
                total_frames=db_stats["frame_count"],
                total_text_blocks=db_stats["text_block_count"],
                total_apps=db_stats["window_count"],
                database_size_mb=round(db_size_mb, 2),
                oldest_frame=db_stats.get("oldest_frame_timestamp"),
                newest_frame=db_stats.get("newest_frame_timestamp"),
                top_apps=top_apps
            )

        except Exception as e:
            logger.error("get_usage_stats_error", error=str(e))
            if ctx:
                await ctx.error(f"Failed to get usage stats: {str(e)}")
            raise

    return mcp


def main():
    """Entry point for running MCP server standalone."""
    import asyncio
    from mcp.server.stdio import stdio_server

    config = Config()
    mcp = create_mcp_server(config=config)

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await mcp.run(
                read_stream,
                write_stream,
                mcp.create_initialization_options()
            )

    asyncio.run(run())


if __name__ == "__main__":
    main()
