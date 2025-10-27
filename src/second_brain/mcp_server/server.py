from __future__ import annotations

"""MCP server exposing SecondBrain search and frame access tools.

Implements a working MCP server using FastMCP with HTTP transport on port 3000.
"""

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP  # type: ignore

from ..database import Database


class SecondBrainMCPServer:
    def __init__(self, db_path: Optional[str] = None):
        self.db = Database() if db_path is None else Database(db_path=db_path)
        self.server = FastMCP("secondbrain-mcp")

        @self.server.tool(name="search_memory", description="Full-text search across captured text", structured_output=True)
        def search_memory(query: str, limit: int = 10, app: Optional[str] = None) -> Dict[str, Any]:
            results = self.db.search_text(query=query, app_filter=app, limit=limit)
            # Normalize output
            out: List[Dict[str, Any]] = []
            for r in results:
                out.append(
                    {
                        "frame_id": r.get("frame_id"),
                        "timestamp": r.get("timestamp"),
                        "app_bundle_id": r.get("app_bundle_id"),
                        "app_name": r.get("app_name"),
                        "window_title": r.get("window_title"),
                        "text": r.get("text", ""),
                        "score": r.get("score"),
                    }
                )
            return {"results": out}

        @self.server.tool(name="get_frame", description="Get frame and text blocks by frame_id", structured_output=True)
        def get_frame(frame_id: str) -> Dict[str, Any]:
            frame = self.db.get_frame(frame_id)
            if not frame:
                return {"frame": None, "text_blocks": []}
            blocks = self.db.get_text_blocks_by_frame(frame_id)
            return {"frame": frame, "text_blocks": blocks}

        @self.server.tool(name="get_apps", description="Top application usage stats", structured_output=True)
        def get_apps(limit: int = 10) -> Dict[str, Any]:
            stats = self.db.get_app_usage_stats(limit=limit)
            return {"apps": stats}

    async def run(self, host: str = "127.0.0.1", port: int = 3000) -> None:
        await self.server.run_streamable_http_async(host=host, port=port)
