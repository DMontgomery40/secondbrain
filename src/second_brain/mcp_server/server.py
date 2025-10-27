from __future__ import annotations

"""Minimal MCP server skeleton exposing search endpoints (stub).

This is a placeholder to integrate with MCP later.
"""

from typing import Any, Dict, List

try:
    from mcp.server import Server  # type: ignore
except Exception:  # pragma: no cover - optional
    Server = object  # type: ignore

from ..database import Database


class SecondBrainMCPServer:
    def __init__(self, db_path: str | None = None):
        self.server = Server("secondbrain-mcp") if isinstance(Server, type) else None
        self.db = Database() if db_path is None else Database(db_path=db_path)

    async def run(self) -> None:  # pragma: no cover - stub
        # TODO: Define tools/routes using MCP SDK as needed
        # For now, just keep the process alive
        import asyncio

        while True:
            await asyncio.sleep(1)

