"""Tests for MCP server."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from second_brain.mcp.server import create_mcp_server
from second_brain.config import Config


@pytest.fixture
def mock_db():
    """Create a mock database for testing."""
    db = Mock()

    # Mock search_text
    db.search_text.return_value = [
        {
            "frame_id": "test-frame-1",
            "timestamp": 1730000000,
            "window_title": "Terminal",
            "app_name": "Terminal",
            "app_bundle_id": "com.apple.Terminal",
            "file_path": "2025/10/26/14-53-20-123.png",
            "block_id": "test-block-1",
            "text": "Error: authentication failed",
            "confidence": 0.98,
            "score": 1.234
        }
    ]

    # Mock get_frame
    db.get_frame.return_value = {
        "frame_id": "test-frame-1",
        "timestamp": 1730000000,
        "window_title": "Terminal",
        "app_name": "Terminal",
        "app_bundle_id": "com.apple.Terminal",
        "file_path": "2025/10/26/14-53-20-123.png",
        "screen_resolution": "1920x1080"
    }

    # Mock get_text_blocks_by_frame
    db.get_text_blocks_by_frame.return_value = [
        {
            "block_id": "test-block-1",
            "frame_id": "test-frame-1",
            "text": "Error: authentication failed",
            "normalized_text": "error authentication failed",
            "confidence": 0.98,
            "block_type": "terminal"
        }
    ]

    # Mock get_frames
    db.get_frames.return_value = [
        {
            "frame_id": "test-frame-1",
            "timestamp": 1730000000,
            "window_title": "VSCode",
            "app_name": "Visual Studio Code",
            "app_bundle_id": "com.microsoft.VSCode",
            "file_path": "2025/10/26/14-53-20-123.png",
            "screen_resolution": "1920x1080"
        }
    ]

    # Mock get_frames_by_app
    db.get_frames_by_app.return_value = [
        {
            "frame_id": "test-frame-1",
            "timestamp": 1730000000,
            "window_title": "VSCode",
            "app_name": "Visual Studio Code",
            "app_bundle_id": "com.microsoft.VSCode",
            "file_path": "2025/10/26/14-53-20-123.png",
            "screen_resolution": "1920x1080"
        }
    ]

    # Mock get_database_stats
    db.get_database_stats.return_value = {
        "frame_count": 1000,
        "text_block_count": 3500,
        "window_count": 10,
        "database_size_bytes": 1024 * 1024 * 500,  # 500 MB
        "oldest_frame_timestamp": 1729000000,
        "newest_frame_timestamp": 1730000000
    }

    # Mock get_app_usage_stats
    db.get_app_usage_stats.return_value = [
        {
            "app_bundle_id": "com.microsoft.VSCode",
            "app_name": "Visual Studio Code",
            "first_seen": 1729000000,
            "last_seen": 1730000000,
            "frame_count": 500
        }
    ]

    return db


@pytest.fixture
def mock_config():
    """Create a mock config for testing."""
    config = Mock(spec=Config)
    config.get_frames_dir.return_value = "/tmp/frames"
    return config


def test_create_mcp_server(mock_config, mock_db):
    """Test that MCP server can be created."""
    with patch('second_brain.mcp.server.Database', return_value=mock_db):
        mcp = create_mcp_server(config=mock_config, db=mock_db)
        assert mcp is not None
        assert mcp.name == "Second Brain Memory"


@pytest.mark.asyncio
async def test_search_memory_tool(mock_config, mock_db):
    """Test search_memory tool."""
    with patch('second_brain.mcp.server.Database', return_value=mock_db):
        mcp = create_mcp_server(config=mock_config, db=mock_db)

        # Get the search_memory tool
        tools = mcp.list_tools()
        search_tool = next((t for t in tools if t["name"] == "search_memory"), None)
        assert search_tool is not None

        # Test tool call
        result = await mcp.call_tool("search_memory", {
            "query": "authentication error",
            "limit": 5
        })

        assert result is not None
        assert "query" in result
        assert "results" in result
        assert len(result["results"]) > 0


@pytest.mark.asyncio
async def test_get_frame_context_tool(mock_config, mock_db):
    """Test get_frame_context tool."""
    with patch('second_brain.mcp.server.Database', return_value=mock_db):
        mcp = create_mcp_server(config=mock_config, db=mock_db)

        # Get the get_frame_context tool
        tools = mcp.list_tools()
        frame_tool = next((t for t in tools if t["name"] == "get_frame_context"), None)
        assert frame_tool is not None

        # Test tool call
        result = await mcp.call_tool("get_frame_context", {
            "frame_id": "test-frame-1"
        })

        assert result is not None
        assert "frame" in result
        assert "text_blocks" in result
        assert result["frame"]["frame_id"] == "test-frame-1"


@pytest.mark.asyncio
async def test_get_timeline_tool(mock_config, mock_db):
    """Test get_timeline tool."""
    with patch('second_brain.mcp.server.Database', return_value=mock_db):
        mcp = create_mcp_server(config=mock_config, db=mock_db)

        # Get the get_timeline tool
        tools = mcp.list_tools()
        timeline_tool = next((t for t in tools if t["name"] == "get_timeline"), None)
        assert timeline_tool is not None

        # Test tool call
        result = await mcp.call_tool("get_timeline", {
            "start_date": "2025-10-26",
            "end_date": "2025-10-27",
            "limit": 50
        })

        assert result is not None
        assert "frames" in result
        assert "frame_count" in result


@pytest.mark.asyncio
async def test_get_app_activity_tool(mock_config, mock_db):
    """Test get_app_activity tool."""
    with patch('second_brain.mcp.server.Database', return_value=mock_db):
        mcp = create_mcp_server(config=mock_config, db=mock_db)

        # Get the get_app_activity tool
        tools = mcp.list_tools()
        app_tool = next((t for t in tools if t["name"] == "get_app_activity"), None)
        assert app_tool is not None

        # Test tool call
        result = await mcp.call_tool("get_app_activity", {
            "app_bundle_id": "com.microsoft.VSCode",
            "limit": 20
        })

        assert result is not None
        assert "frames" in result
        assert "app_bundle_id" in result
        assert result["app_bundle_id"] == "com.microsoft.VSCode"


@pytest.mark.asyncio
async def test_get_usage_stats_tool(mock_config, mock_db):
    """Test get_usage_stats tool."""
    with patch('second_brain.mcp.server.Database', return_value=mock_db):
        mcp = create_mcp_server(config=mock_config, db=mock_db)

        # Get the get_usage_stats tool
        tools = mcp.list_tools()
        stats_tool = next((t for t in tools if t["name"] == "get_usage_stats"), None)
        assert stats_tool is not None

        # Test tool call
        result = await mcp.call_tool("get_usage_stats", {})

        assert result is not None
        assert "total_frames" in result
        assert "total_text_blocks" in result
        assert "top_apps" in result
        assert result["total_frames"] == 1000


def test_mcp_server_has_all_tools(mock_config, mock_db):
    """Test that all expected tools are registered."""
    with patch('second_brain.mcp.server.Database', return_value=mock_db):
        mcp = create_mcp_server(config=mock_config, db=mock_db)

        tools = mcp.list_tools()
        tool_names = [t["name"] for t in tools]

        expected_tools = [
            "search_memory",
            "get_frame_context",
            "get_timeline",
            "get_app_activity",
            "get_usage_stats"
        ]

        for expected_tool in expected_tools:
            assert expected_tool in tool_names, f"Missing tool: {expected_tool}"


def test_tool_schemas_are_valid(mock_config, mock_db):
    """Test that all tools have valid schemas."""
    with patch('second_brain.mcp.server.Database', return_value=mock_db):
        mcp = create_mcp_server(config=mock_config, db=mock_db)

        tools = mcp.list_tools()

        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert tool["description"], f"Tool {tool['name']} has no description"
