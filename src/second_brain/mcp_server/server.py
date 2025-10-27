"""
MCP Server exposing SecondBrain functionality.
Runs as separate service, doesn't interfere with main app.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource

from ..database import Database
from ..config import Config

logger = structlog.get_logger()


class SecondBrainMCPServer:
    """MCP Server for Second Brain memory system."""

    def __init__(self, db_path: Optional[str] = None, config: Optional[Config] = None):
        """Initialize MCP server.

        Args:
            db_path: Path to database file (uses config default if None)
            config: Configuration instance
        """
        self.config = config or Config()
        self.server = Server("secondbrain-mcp")
        self.db_path = db_path or str(self.config.get_database_dir() / "memory.db")
        self.database = Database(config=self.config)

        self._register_tools()
        logger.info("mcp_server_initialized", db_path=self.db_path)

    def _register_tools(self):
        """Register MCP tools and handlers."""

        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available tools."""
            return [
                Tool(
                    name="search_memory",
                    description="Search screen memory using full-text or semantic search",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query"
                            },
                            "semantic": {
                                "type": "boolean",
                                "description": "Use semantic search instead of full-text",
                                "default": False
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results",
                                "default": 20
                            },
                            "app_bundle_id": {
                                "type": "string",
                                "description": "Filter by application bundle ID"
                            },
                            "start_time": {
                                "type": "string",
                                "description": "ISO format start time"
                            },
                            "end_time": {
                                "type": "string",
                                "description": "ISO format end time"
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="get_screenshot",
                    description="Get screenshot and metadata for a specific frame",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "frame_id": {
                                "type": "string",
                                "description": "Frame ID to retrieve"
                            }
                        },
                        "required": ["frame_id"]
                    }
                ),
                Tool(
                    name="get_frames_by_time",
                    description="Get frames within a time range",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "start_time": {
                                "type": "string",
                                "description": "ISO format start time"
                            },
                            "end_time": {
                                "type": "string",
                                "description": "ISO format end time"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results",
                                "default": 100
                            }
                        },
                        "required": ["start_time", "end_time"]
                    }
                ),
                Tool(
                    name="get_app_activity",
                    description="Get application usage statistics",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "app_bundle_id": {
                                "type": "string",
                                "description": "Filter by specific application"
                            },
                            "start_time": {
                                "type": "string",
                                "description": "ISO format start time"
                            },
                            "end_time": {
                                "type": "string",
                                "description": "ISO format end time"
                            }
                        }
                    }
                ),
                Tool(
                    name="analyze_activity",
                    description="Analyze user activity patterns over time",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "start_time": {
                                "type": "string",
                                "description": "ISO format start time"
                            },
                            "end_time": {
                                "type": "string",
                                "description": "ISO format end time"
                            },
                            "group_by": {
                                "type": "string",
                                "enum": ["hour", "day", "app"],
                                "description": "How to group results",
                                "default": "hour"
                            }
                        },
                        "required": ["start_time", "end_time"]
                    }
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls."""
            logger.info("mcp_tool_called", tool=name, arguments=arguments)

            if name == "search_memory":
                return await self._handle_search_memory(arguments)
            elif name == "get_screenshot":
                return await self._handle_get_screenshot(arguments)
            elif name == "get_frames_by_time":
                return await self._handle_get_frames_by_time(arguments)
            elif name == "get_app_activity":
                return await self._handle_get_app_activity(arguments)
            elif name == "analyze_activity":
                return await self._handle_analyze_activity(arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")

    async def _handle_search_memory(self, args: Dict[str, Any]) -> List[TextContent]:
        """Handle search_memory tool call."""
        query = args["query"]
        semantic = args.get("semantic", False)
        limit = args.get("limit", 20)
        app_bundle_id = args.get("app_bundle_id")
        start_time = args.get("start_time")
        end_time = args.get("end_time")

        results = self.database.search_frames(
            query=query,
            semantic=semantic,
            limit=limit,
            app_bundle_id=app_bundle_id,
            start_time=start_time,
            end_time=end_time
        )

        if not results:
            return [TextContent(
                type="text",
                text=f"No results found for query: '{query}'"
            )]

        response_text = f"Found {len(results)} results for '{query}':\n\n"
        for idx, result in enumerate(results, 1):
            response_text += f"{idx}. Frame {result.get('frame_id', 'unknown')}\n"
            response_text += f"   Time: {result.get('timestamp', 'unknown')}\n"
            response_text += f"   App: {result.get('app_name', 'unknown')}\n"
            response_text += f"   Text: {result.get('text', '')[:200]}...\n\n"

        return [TextContent(type="text", text=response_text)]

    async def _handle_get_screenshot(self, args: Dict[str, Any]) -> List[TextContent]:
        """Handle get_screenshot tool call."""
        frame_id = args["frame_id"]

        frame = self.database.get_frame(frame_id)
        if not frame:
            return [TextContent(
                type="text",
                text=f"Frame not found: {frame_id}"
            )]

        response_text = f"Frame: {frame_id}\n"
        response_text += f"Timestamp: {frame.get('timestamp', 'unknown')}\n"
        response_text += f"App: {frame.get('app_name', 'unknown')} ({frame.get('app_bundle_id', 'unknown')})\n"
        response_text += f"Window: {frame.get('window_title', 'unknown')}\n"
        response_text += f"Screenshot: {frame.get('file_path', 'unknown')}\n"

        text_blocks = self.database.get_frame_text(frame_id)
        if text_blocks:
            response_text += f"\nExtracted text ({len(text_blocks)} blocks):\n"
            for block in text_blocks:
                response_text += f"{block.get('text', '')}\n"

        return [TextContent(type="text", text=response_text)]

    async def _handle_get_frames_by_time(self, args: Dict[str, Any]) -> List[TextContent]:
        """Handle get_frames_by_time tool call."""
        start_time = args["start_time"]
        end_time = args["end_time"]
        limit = args.get("limit", 100)

        frames = self.database.get_frames_by_time_range(
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )

        if not frames:
            return [TextContent(
                type="text",
                text=f"No frames found between {start_time} and {end_time}"
            )]

        response_text = f"Found {len(frames)} frames between {start_time} and {end_time}:\n\n"
        for frame in frames:
            response_text += f"- {frame.get('timestamp')}: {frame.get('app_name')} - {frame.get('window_title', 'N/A')}\n"

        return [TextContent(type="text", text=response_text)]

    async def _handle_get_app_activity(self, args: Dict[str, Any]) -> List[TextContent]:
        """Handle get_app_activity tool call."""
        app_bundle_id = args.get("app_bundle_id")
        start_time = args.get("start_time")
        end_time = args.get("end_time")

        stats = self.database.get_app_stats(
            app_bundle_id=app_bundle_id,
            start_time=start_time,
            end_time=end_time
        )

        if not stats:
            return [TextContent(
                type="text",
                text="No application activity found"
            )]

        response_text = "Application Activity:\n\n"
        for app in stats:
            response_text += f"App: {app.get('app_name', 'unknown')} ({app.get('app_bundle_id', 'unknown')})\n"
            response_text += f"  Frames: {app.get('frame_count', 0)}\n"
            response_text += f"  First seen: {app.get('first_seen', 'unknown')}\n"
            response_text += f"  Last seen: {app.get('last_seen', 'unknown')}\n\n"

        return [TextContent(type="text", text=response_text)]

    async def _handle_analyze_activity(self, args: Dict[str, Any]) -> List[TextContent]:
        """Handle analyze_activity tool call."""
        start_time = args["start_time"]
        end_time = args["end_time"]
        group_by = args.get("group_by", "hour")

        analysis = self.database.analyze_activity(
            start_time=start_time,
            end_time=end_time,
            group_by=group_by
        )

        if not analysis:
            return [TextContent(
                type="text",
                text=f"No activity found between {start_time} and {end_time}"
            )]

        response_text = f"Activity Analysis ({group_by} grouping):\n\n"
        for group in analysis:
            response_text += f"{group.get('group', 'unknown')}: {group.get('count', 0)} frames\n"

        return [TextContent(type="text", text=response_text)]

    async def run(self, transport: str = "stdio"):
        """Run the MCP server.

        Args:
            transport: Transport type ("stdio" or "sse")
        """
        logger.info("starting_mcp_server", transport=transport)

        if transport == "stdio":
            from mcp.server.stdio import stdio_server
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="secondbrain-mcp",
                        server_version="1.0.0",
                        capabilities=self.server.get_capabilities(
                            notification_options=None,
                            experimental_capabilities={}
                        )
                    )
                )
        else:
            raise ValueError(f"Unsupported transport: {transport}")

    def close(self):
        """Close database connection."""
        self.database.close()
        logger.info("mcp_server_closed")
