"""Tests for capture service."""

import stat
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.second_brain.capture import CaptureService
from src.second_brain.config import Config


@pytest.fixture
def config(tmp_path, monkeypatch):
    """Create isolated test configuration with temporary directories."""
    data_dir = tmp_path / "second-brain"
    frames_dir = data_dir / "frames"
    database_dir = data_dir / "database"
    embeddings_dir = data_dir / "embeddings"
    logs_dir = data_dir / "logs"
    config_dir = data_dir / "config"

    monkeypatch.setattr(
        Config,
        "get_data_dir",
        staticmethod(lambda: data_dir),
    )
    monkeypatch.setattr(
        Config,
        "get_frames_dir",
        staticmethod(lambda: frames_dir),
    )
    monkeypatch.setattr(
        Config,
        "get_database_dir",
        staticmethod(lambda: database_dir),
    )
    monkeypatch.setattr(
        Config,
        "get_embeddings_dir",
        staticmethod(lambda: embeddings_dir),
    )
    monkeypatch.setattr(
        Config,
        "get_logs_dir",
        staticmethod(lambda: logs_dir),
    )

    config_path = config_dir / "settings.json"
    config = Config(config_path=config_path)
    config.set("capture.fps", 1)
    config.set("capture.max_disk_usage_gb", 100)
    config.set("capture.min_free_space_gb", 10)
    return config


@pytest.fixture
def capture_service(config):
    """Create capture service instance."""
    return CaptureService(config)


def test_capture_service_initialization(capture_service):
    """Test capture service initializes correctly."""
    assert capture_service.fps == 1
    assert capture_service.format == "png"
    assert capture_service.running is False
    assert capture_service.frames_captured == 0


@pytest.mark.asyncio
async def test_capture_frame(capture_service, tmp_path):
    """Test single frame capture."""
    # Mock screencapture command
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(returncode=0)
        
        # Mock file creation
        with patch.object(Path, 'stat') as mock_stat:
            mock_stat.return_value = Mock(
                st_size=1024000,
                st_mode=stat.S_IFREG,
            )
            
            metadata = await capture_service.capture_frame()
            
            assert metadata is not None
            assert "frame_id" in metadata
            assert "timestamp" in metadata
            assert "file_path" in metadata


def test_get_stats(capture_service):
    """Test getting capture statistics."""
    stats = capture_service.get_stats()
    
    assert "running" in stats
    assert "frames_captured" in stats
    assert "fps" in stats
    assert stats["running"] is False
    assert stats["frames_captured"] == 0


@pytest.mark.asyncio
async def test_stop_capture(capture_service):
    """Test stopping capture service."""
    capture_service.running = True
    capture_service.stop()
    
    assert capture_service.running is False
